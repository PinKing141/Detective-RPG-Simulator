from __future__ import annotations

import argparse

from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import (
    auto_build_reasoning_steps,
    recommended_hypothesis_evidence_ids,
    support_for_claims,
)
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import RoleTag
from noir.investigation.actions import interview, request_cctv, set_hypothesis, submit_forensics
from noir.investigation.leads import build_leads
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def _evaluation_result(
    seed: int,
    tier: str,
    summary: str,
    *,
    supports: list[str] | None = None,
    missing: list[str] | None = None,
    claims: list[str] | None = None,
    evidence: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "seed": seed,
        "tier": tier,
        "summary": summary,
        "supports": list(supports or []),
        "missing": list(missing or []),
        "claims": list(claims or []),
        "evidence": list(evidence or []),
        "notes": list(notes or []),
    }


def _selected_evidence_lines(presentation, evidence_ids) -> list[str]:
    evidence_set = set(evidence_ids)
    lines: list[str] = []
    for item in presentation.evidence:
        if item.id not in evidence_set:
            continue
        confidence = getattr(item, "confidence", None)
        label = confidence.value if hasattr(confidence, "value") else str(confidence)
        lines.append(f"{item.summary} [{label}]")
    return lines


def _supported_claims(presentation, evidence_ids, suspect_id, *, truth, state) -> list[ClaimType]:
    claims: list[ClaimType] = []
    for claim in ClaimType:
        support = support_for_claims(
            presentation,
            evidence_ids,
            suspect_id,
            [claim],
            truth=truth,
            state=state,
        )
        if support.supports:
            claims.append(claim)
    return claims


def evaluate_seed(seed: int) -> dict[str, object]:
    rng = Rng(seed)
    truth, case_facts = generate_case(rng, case_id=f"case_sweep_{seed}")
    presentation = project_case(truth, rng.fork("projection"))
    state = InvestigationState()
    state.leads = build_leads(presentation, start_time=state.time)
    board = DeductionBoard()

    witnesses = [
        person for person in truth.people.values() if RoleTag.WITNESS in person.role_tags
    ]
    suspect = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    if not witnesses or suspect is None:
        return _evaluation_result(
            seed,
            "failed",
            "missing witness or suspect",
            missing=["Case projection did not surface both a witness route and an offender route."],
        )

    location_id = case_facts["crime_scene_id"]
    item_id = case_facts["weapon_id"]

    interview(truth, presentation, state, witnesses[0].id, location_id)
    request_cctv(truth, presentation, state, location_id)
    submit_forensics(truth, presentation, state, location_id, item_id=item_id)
    for witness in witnesses[1:]:
        interview(truth, presentation, state, witness.id, location_id)

    board.sync_from_state(state)
    candidate_ids = list(board.known_evidence_ids)
    claims = _supported_claims(
        presentation,
        candidate_ids,
        suspect.id,
        truth=truth,
        state=state,
    )[:3]
    if not claims:
        return _evaluation_result(
            seed,
            "failed",
            "no supported claims",
            missing=["Collected evidence never supports a submit-ready claim set."],
        )

    evidence_ids = recommended_hypothesis_evidence_ids(
        presentation,
        candidate_ids,
        suspect.id,
        claims,
        truth=truth,
        state=state,
        limit=3,
    )
    if not evidence_ids:
        return _evaluation_result(
            seed,
            "failed",
            "no recommended evidence",
            claims=[claim.value for claim in claims],
            missing=["Scoring could not assemble a compact evidence set for the current claims."],
        )

    reasoning_steps = auto_build_reasoning_steps(
        presentation,
        evidence_ids,
        suspect.id,
        claims,
        truth=truth,
        state=state,
    )
    result = set_hypothesis(
        state,
        board,
        suspect.id,
        claims,
        evidence_ids,
        reasoning_steps,
    )
    if result.outcome != ActionOutcome.SUCCESS:
        return _evaluation_result(
            seed,
            "failed",
            result.summary,
            claims=[claim.value for claim in claims],
            evidence=_selected_evidence_lines(presentation, evidence_ids),
            missing=[result.summary],
        )

    validation = validate_hypothesis(truth, board, presentation, state)
    return _evaluation_result(
        seed,
        validation.tier.value,
        validation.summary,
        supports=list(validation.supports),
        missing=list(validation.missing),
        claims=[claim.value for claim in claims],
        evidence=_selected_evidence_lines(presentation, evidence_ids),
        notes=list(validation.notes),
    )


def summarize_results(results: list[dict[str, object]]) -> dict[str, object]:
    tier_counts: dict[str, int] = {}
    for result in results:
        tier = str(result["tier"])
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    clean_count = tier_counts.get("clean", 0)
    total = len(results)
    clean_rate = clean_count / total if total else 0.0
    return {
        "tier_counts": tier_counts,
        "clean_count": clean_count,
        "clean_rate": clean_rate,
        "non_clean": [result for result in results if result["tier"] != "clean"],
    }


def triage_candidates(results: list[dict[str, object]], limit: int = 10) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    shaky = [result for result in results if result["tier"] == "shaky"]
    if len(shaky) >= limit:
        return shaky[:limit]
    failed = [result for result in results if result["tier"] == "failed"]
    return shaky + failed[: max(0, limit - len(shaky))]


def ci_recommendation(clean_rate: float, target_clean_rate: float | None) -> str | None:
    if target_clean_rate is None:
        return None
    if clean_rate >= target_clean_rate:
        return (
            "Target clean rate met. --fail-on-non-clean fits a non-blocking CI/reporting job, "
            "but it is still too strict for a blocking gate."
        )
    return (
        "Target clean rate missed. Keep --fail-on-non-clean out of automation for now and "
        "track clean rate until the sweep stabilizes."
    )


def _parse_seed_list(raw: str) -> list[int]:
    seeds: list[int] = []
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        seeds.append(int(value))
    if not seeds:
        raise ValueError("expected at least one seed")
    return seeds


def _print_summary(label: str, results: list[dict[str, object]]) -> dict[str, object]:
    summary = summarize_results(results)
    tier_counts = summary["tier_counts"]
    print(label)
    for tier in sorted(tier_counts):
        print(f"{tier}: {tier_counts[tier]}")
    print(
        f"Clean rate: {summary['clean_rate']:.1%} "
        f"({summary['clean_count']}/{len(results)})"
    )

    non_clean = summary["non_clean"]
    if non_clean:
        print("\nNon-clean seeds:")
        for result in non_clean:
            print(f"- seed {result['seed']}: {result['tier']} ({result['summary']})")
    return summary


def _print_triage(results: list[dict[str, object]], limit: int) -> None:
    triage = triage_candidates(results, limit=limit)
    if not triage:
        return
    print(f"\nSeed triage (up to {limit} shaky/non-clean cases):")
    for result in triage:
        print(f"- seed {result['seed']}: {result['tier']} ({result['summary']})")
        claims = list(result.get("claims", []))
        if claims:
            print(f"  claims: {', '.join(claims)}")
        evidence = list(result.get("evidence", []))
        if evidence:
            print("  evidence:")
            for line in evidence:
                print(f"    - {line}")
        missing = list(result.get("missing", []))
        if missing:
            print("  gaps:")
            for line in missing[:3]:
                print(f"    - {line}")
        notes = list(result.get("notes", []))
        if notes:
            print(f"  notes: {notes[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample careful-route case quality across a seed range.")
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument(
        "--triage-seeds",
        type=str,
        help="Comma-separated seed list to re-run as a focused triage pass.",
    )
    parser.add_argument(
        "--triage-limit",
        type=int,
        default=10,
        help="Maximum number of shaky/non-clean seeds to expand in the triage section.",
    )
    parser.add_argument(
        "--target-clean-rate",
        type=float,
        help="Optional clean-rate target expressed as a decimal, for example 0.60.",
    )
    parser.add_argument("--fail-on-non-clean", action="store_true")
    args = parser.parse_args()

    if args.count <= 0:
        parser.error("--count must be positive")
    if args.triage_limit < 0:
        parser.error("--triage-limit cannot be negative")
    if args.target_clean_rate is not None and not 0.0 <= args.target_clean_rate <= 1.0:
        parser.error("--target-clean-rate must be between 0.0 and 1.0")

    if args.triage_seeds:
        seeds = _parse_seed_list(args.triage_seeds)
        results = [evaluate_seed(seed) for seed in seeds]
        summary = _print_summary(f"Triaged seeds: {', '.join(str(seed) for seed in seeds)}", results)
        _print_triage(results, limit=max(len(seeds), args.triage_limit))
    else:
        results = [evaluate_seed(seed) for seed in range(args.start_seed, args.start_seed + args.count)]
        summary = _print_summary(
            f"Sampled seeds {args.start_seed}..{args.start_seed + args.count - 1}",
            results,
        )
        _print_triage(results, limit=args.triage_limit)

    recommendation = ci_recommendation(summary["clean_rate"], args.target_clean_rate)
    if recommendation:
        print(f"\nCI recommendation: {recommendation}")

    non_clean = summary["non_clean"]
    if args.fail_on_non_clean and non_clean:
        raise SystemExit(1)


if __name__ == "__main__":
    main()