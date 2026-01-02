from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import support_for_claims
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import EvidenceType, RoleTag
from noir.investigation.actions import (
    arrest,
    interview,
    request_cctv,
    set_hypothesis,
    submit_forensics,
    visit_scene,
)
from noir.investigation.costs import ActionType, PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.leads import LeadStatus, build_leads
from noir.investigation.outcomes import TRUST_LIMIT, apply_case_outcome, resolve_case_outcome
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.evidence import WitnessStatement
from noir.presentation.projector import project_case
from noir.profiling.summary import build_profiling_summary, format_profiling_summary
from noir.util.rng import Rng


def _choose_enum(enum_type, label_func=None):
    values = list(enum_type)
    for idx, value in enumerate(values, start=1):
        label = label_func(value) if label_func else value.value
        print(f"{idx}) {label}")
    choice = input("> ").strip()
    if not choice.isdigit():
        return None
    index = int(choice) - 1
    if index < 0 or index >= len(values):
        return None
    return values[index]


def _choose_claims() -> list[ClaimType]:
    options = list(ClaimType)
    print("Choose 1 to 3 claims (comma-separated):")
    for idx, claim in enumerate(options, start=1):
        print(f"{idx}) {_format_claim(claim)}")
    choice = input("> ").strip()
    if not choice:
        return []
    indices = []
    for part in choice.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        indices.append(int(part) - 1)
    selected: list[ClaimType] = []
    for idx in indices:
        if 0 <= idx < len(options):
            selected.append(options[idx])
    return list(dict.fromkeys(selected))


def _observed_suspect_id(presentation, evidence_ids: list) -> object | None:
    id_set = set(evidence_ids)
    counts: dict[object, int] = {}
    for item in presentation.evidence:
        if item.id not in id_set:
            continue
        observed = getattr(item, "observed_person_ids", None)
        if not observed:
            continue
        for person_id in observed:
            counts[person_id] = counts.get(person_id, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _supported_claims(presentation, evidence_ids: list, suspect_id) -> list[ClaimType]:
    claims: list[ClaimType] = []
    for claim in ClaimType:
        support = support_for_claims(presentation, evidence_ids, suspect_id, [claim])
        if support.supports:
            claims.append(claim)
    return claims


def _choose_person(truth, role_tag: RoleTag) -> tuple[str, object] | None:
    people = [p for p in truth.people.values() if role_tag in p.role_tags]
    if not people:
        return None
    if len(people) == 1:
        return people[0].name, people[0]
    print("Choose a person:")
    for idx, person in enumerate(people, start=1):
        print(f"{idx}) {person.name}")
    choice = input("> ").strip()
    if not choice.isdigit():
        return None
    index = int(choice) - 1
    if index < 0 or index >= len(people):
        return None
    return people[index].name, people[index]


def _format_claim(claim: ClaimType) -> str:
    mapping = {
        ClaimType.PRESENCE: "Present near the scene",
        ClaimType.OPPORTUNITY: "Opportunity during the time window",
        ClaimType.MOTIVE: "Motive linked to the victim",
        ClaimType.BEHAVIOR: "Behavior aligns with the crime",
    }
    return mapping.get(claim, claim.value)


def _format_hour(hour: int) -> str:
    value = hour % 24
    suffix = "am" if value < 12 else "pm"
    display = value % 12
    if display == 0:
        display = 12
    return f"{display}{suffix}"


def _format_time_phrase(window: tuple[int, int]) -> str:
    start, end = window
    if start == end:
        return f"around {_format_hour(start)}"
    return f"between {_format_hour(start)} and {_format_hour(end)}"


def _format_confidence(confidence) -> str:
    value = confidence.value if hasattr(confidence, "value") else str(confidence)
    mapping = {"strong": "High", "medium": "Medium", "weak": "Low"}
    return mapping.get(value, value.capitalize())


def _witness_note(truth, item: WitnessStatement) -> str:
    if item.observed_person_ids:
        person_id = item.observed_person_ids[0]
        person = truth.people.get(person_id)
        name = person.name if person else "someone"
        return f"Detective note: Suggests proximity near the location ({name})."
    return "Detective note: Suggests activity near the location."


def _lead_lines(state: InvestigationState) -> list[str]:
    if not state.leads:
        return ["(none)"]
    lines: list[str] = []
    for idx, lead in enumerate(state.leads, start=1):
        if lead.status == LeadStatus.ACTIVE:
            status = f"active until t{lead.deadline}"
        elif lead.status == LeadStatus.RESOLVED:
            status = "resolved"
        else:
            status = "expired"
        lines.append(f"{idx}) {lead.label} - {status} ({lead.action_hint})")
    return lines


def _supporting_evidence_lines(presentation, evidence_ids: list) -> list[str]:
    id_set = set(evidence_ids)
    lines: list[str] = []
    for item in presentation.evidence:
        if item.id not in id_set:
            continue
        lines.append(f"{item.summary} ({_format_confidence(item.confidence)})")
    return lines


def _hypothesis_summary_lines(board: DeductionBoard, truth, presentation) -> list[str]:
    if board.hypothesis is None:
        return ["Hypothesis: (none)"]
    suspect = truth.people.get(board.hypothesis.suspect_id)
    suspect_name = suspect.name if suspect else "Unknown"
    lines = [f"Hypothesis: {suspect_name}"]
    claim_text = ", ".join(_format_claim(claim) for claim in board.hypothesis.claims)
    lines.append(f"Claims: {claim_text or '(none)'}")
    evidence_lines = _supporting_evidence_lines(presentation, board.hypothesis.evidence_ids)
    if evidence_lines:
        lines.append("Supporting evidence:")
        lines.extend(f"- {line}" for line in evidence_lines)
    else:
        lines.append("Supporting evidence: (none)")
    claim_support = support_for_claims(
        presentation,
        board.hypothesis.evidence_ids,
        board.hypothesis.suspect_id,
        board.hypothesis.claims,
    )
    if claim_support.missing:
        lines.append("Gaps:")
        lines.extend(f"- {line}" for line in claim_support.missing)
    return lines


def _choose_evidence(truth, presentation, known_ids: list) -> list:
    items = [item for item in presentation.evidence if item.id in set(known_ids)]
    if not items:
        print("No evidence collected yet.")
        return []
    print("Choose 1 to 3 evidence items (comma-separated):")
    for idx, item in enumerate(items, start=1):
        if isinstance(item, WitnessStatement):
            print(f"{idx}) Witness statement")
            print(f"   Time: {_format_time_phrase(item.reported_time_window)} (estimate)")
            print(f"   Statement: {item.statement}")
            print(f"   {_witness_note(truth, item)}")
            print(f"   Confidence: {_format_confidence(item.confidence)}")
        else:
            print(f"{idx}) {item.summary} ({item.evidence_type}, {item.confidence})")
    choice = input("> ").strip()
    if not choice:
        return []
    indices = []
    for part in choice.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        indices.append(int(part) - 1)
    selected = []
    for idx in indices:
        if 0 <= idx < len(items):
            selected.append(items[idx].id)
    return selected


def _start_case(
    base_rng: Rng,
    seed: int,
    case_index: int,
    state: InvestigationState | None,
    case_id_override: str | None = None,
):
    case_rng = base_rng.fork(f"case-{case_index}")
    case_id = case_id_override or f"case_{seed}_{case_index}"
    truth, case_facts = generate_case(case_rng, case_id=case_id)
    presentation = project_case(truth, case_rng.fork("projection"))
    next_state = state or InvestigationState()
    next_state = InvestigationState(
        pressure=next_state.pressure,
        trust=next_state.trust,
    )
    next_state.leads = build_leads(presentation, start_time=next_state.time)
    board = DeductionBoard()
    location_id = case_facts["crime_scene_id"]
    item_id = case_facts["weapon_id"]
    return truth, presentation, next_state, board, location_id, item_id


def _find_seed_with_observed(start_seed: int, max_tries: int) -> int | None:
    for seed in range(start_seed, start_seed + max_tries):
        base_rng = Rng(seed)
        case_rng = base_rng.fork("case-1")
        truth, _ = generate_case(case_rng, case_id=f"case_{seed}_1")
        presentation = project_case(truth, case_rng.fork("projection"))
        for item in presentation.evidence:
            observed = getattr(item, "observed_person_ids", None)
            if observed and item.evidence_type in (EvidenceType.TESTIMONIAL, EvidenceType.CCTV):
                return seed
    return None


def _run_smoke(seed: int, case_id: str | None) -> None:
    base_rng = Rng(seed)
    truth, presentation, state, board, location_id, item_id = _start_case(
        base_rng, seed, 1, None, case_id_override=case_id
    )
    print(f"[smoke] Case {truth.case_id} started.")
    witness = next(
        (p for p in truth.people.values() if RoleTag.WITNESS in p.role_tags), None
    )
    if witness:
        interview(truth, presentation, state, witness.id, location_id)
    request_cctv(truth, presentation, state, location_id)
    visit_scene(truth, presentation, state, location_id)
    board.sync_from_state(state)
    evidence_ids = list(board.known_evidence_ids)
    observed_id = _observed_suspect_id(presentation, evidence_ids)
    if observed_id is None:
        print("[smoke] No suspect observed in evidence; aborting.")
        return
    suspect = truth.people.get(observed_id)
    if suspect is None:
        print("[smoke] Observed suspect missing from truth; aborting.")
        return
    known_items = [item for item in presentation.evidence if item.id in set(evidence_ids)]
    observed_items = [
        item
        for item in known_items
        if getattr(item, "observed_person_ids", None) and suspect.id in item.observed_person_ids
    ]
    selected_items = observed_items + [item for item in known_items if item not in observed_items]
    evidence_ids = [item.id for item in selected_items][:3]
    if not evidence_ids:
        print("[smoke] No evidence collected; aborting.")
        return
    claims = _supported_claims(presentation, evidence_ids, suspect.id)[:3]
    if not claims:
        print("[smoke] No supported claims from evidence; aborting.")
        return
    result = set_hypothesis(
        state,
        board,
        suspect.id,
        claims,
        evidence_ids,
    )
    print(f"[smoke] {result.summary}")
    for line in _hypothesis_summary_lines(board, truth, presentation):
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 playable loop.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a short non-interactive smoke path and exit.",
    )
    parser.add_argument(
        "--smoke-find",
        action="store_true",
        help="Find a nearby seed with observed evidence for smoke mode.",
    )
    parser.add_argument(
        "--smoke-tries",
        type=int,
        default=50,
        help="How many seeds to scan for smoke mode.",
    )
    args = parser.parse_args()

    if args.smoke:
        seed = args.seed
        if args.smoke_find:
            found = _find_seed_with_observed(args.seed, args.smoke_tries)
            if found is None:
                print("[smoke] No seed found with observed evidence.")
                return
            seed = found
            print(f"[smoke] Using seed {seed}.")
        _run_smoke(seed, args.case_id)
        return

    base_rng = Rng(args.seed)
    case_index = 1
    truth, presentation, state, board, location_id, item_id = _start_case(
        base_rng, args.seed, case_index, None, case_id_override=args.case_id
    )

    print(
        f"Case {truth.case_id} started. Investigation time limit {TIME_LIMIT}, "
        f"pressure tolerance {PRESSURE_LIMIT}, trust {state.trust}/{TRUST_LIMIT}."
    )
    print("Type a number to choose an action. Type 'q' to quit.")

    while True:
        print("")
        print(
            f"Investigation Time: {state.time}/{TIME_LIMIT} | "
            f"Pressure: {state.pressure}/{PRESSURE_LIMIT} | "
            f"Trust: {state.trust}/{TRUST_LIMIT}"
        )
        for line in _hypothesis_summary_lines(board, truth, presentation):
            print(line)
        print(f"Evidence known: {len(state.knowledge.known_evidence)}/{len(presentation.evidence)}")
        print("Leads:")
        for line in _lead_lines(state):
            print(f"- {line}")
        print("1) Visit scene")
        print("2) Interview witness")
        print("3) Request CCTV")
        print("4) Submit forensics")
        print("5) Set hypothesis")
        print("6) Profiling summary")
        print("7) Arrest suspect")
        choice = input("> ").strip().lower()
        if choice == "q":
            break

        if choice == "1":
            result = visit_scene(truth, presentation, state, location_id)
        elif choice == "2":
            selection = _choose_person(truth, RoleTag.WITNESS)
            if not selection:
                print("No witness available.")
                continue
            result = interview(truth, presentation, state, selection[1].id, location_id)
        elif choice == "3":
            result = request_cctv(truth, presentation, state, location_id)
        elif choice == "4":
            result = submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        elif choice == "5":
            board.sync_from_state(state)
            selection = _choose_person(truth, RoleTag.OFFENDER)
            if not selection:
                print("No suspect available.")
                continue
            claims = _choose_claims()
            if not claims:
                print("Invalid claim selection.")
                continue
            evidence_ids = _choose_evidence(truth, presentation, board.known_evidence_ids)
            result = set_hypothesis(
                state,
                board,
                selection[1].id,
                claims,
                evidence_ids,
            )
        elif choice == "6":
            summary = build_profiling_summary(presentation, state, board.hypothesis)
            for line in format_profiling_summary(summary):
                print(line)
            continue
        elif choice == "7":
            if board.hypothesis is None:
                print("Set a hypothesis before arrest.")
                continue
            result = arrest(
                truth,
                presentation,
                state,
                board.hypothesis.suspect_id,
                location_id,
                has_hypothesis=True,
            )
        else:
            print("Unknown action.")
            continue

        if result.action == ActionType.SET_HYPOTHESIS and result.outcome == ActionOutcome.SUCCESS:
            print(
                f"{result.summary} (+{result.time_cost} time, +{result.pressure_cost} pressure)"
            )
        else:
            print(f"[{result.action}] {result.summary}")
        if result.revealed:
            for item in result.revealed:
                if isinstance(item, WitnessStatement):
                    print("- New evidence: Witness statement")
                    print(f"  Time: {_format_time_phrase(item.reported_time_window)} (estimate)")
                    print(f"  Statement: {item.statement}")
                    print(f"  {_witness_note(truth, item)}")
                    print(f"  Confidence: {_format_confidence(item.confidence)}")
                else:
                    print(f"- New evidence: {item.summary} ({item.evidence_type}, {item.confidence})")
                if isinstance(item, WitnessStatement):
                    print(f"  Statement: {item.statement}")
        if result.notes:
            for note in result.notes:
                print(f"- {note}")

        if result.action == ActionType.ARREST:
            board.sync_from_state(state)
            validation = validate_hypothesis(truth, board, presentation, state)
            print(validation.summary)
            if validation.supports:
                print("Supports:")
                for line in validation.supports:
                    print(f"- {line}")
            if validation.missing:
                print("Missing:")
                for line in validation.missing:
                    print(f"- {line}")
            if validation.notes:
                print("Notes:")
                for line in validation.notes:
                    print(f"- {line}")
            outcome = resolve_case_outcome(validation)
            print(f"Case outcome: {outcome.arrest_result}.")
            for note in outcome.notes:
                print(f"- {note}")
            state = apply_case_outcome(state, outcome)
            case_index += 1
            truth, presentation, state, board, location_id, item_id = _start_case(
                base_rng, args.seed, case_index, state
            )
            print(
                f"New case {truth.case_id} started. "
                f"Pressure {state.pressure}/{PRESSURE_LIMIT}, "
                f"Trust {state.trust}/{TRUST_LIMIT}."
            )


if __name__ == "__main__":
    main()
