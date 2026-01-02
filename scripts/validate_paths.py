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
from noir.investigation.actions import arrest, interview, request_cctv, set_hypothesis, submit_forensics
from noir.investigation.leads import build_leads
from noir.investigation.outcomes import resolve_case_outcome
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng

def _find_seed(start_seed: int, max_tries: int) -> int | None:
    for seed in range(start_seed, start_seed + max_tries):
        rng = Rng(seed)
        truth, _ = generate_case(rng, case_id=f"case_{seed}")
        presentation = project_case(truth, rng.fork("projection"))
        types = {item.evidence_type for item in presentation.evidence}
        if (
            EvidenceType.TESTIMONIAL in types
            and EvidenceType.CCTV in types
            and EvidenceType.FORENSICS in types
        ):
            return seed
    return None


def _supported_claims(presentation, evidence_ids: list, suspect_id) -> list[ClaimType]:
    claims: list[ClaimType] = []
    for claim in ClaimType:
        support = support_for_claims(presentation, evidence_ids, suspect_id, [claim])
        if support.supports:
            claims.append(claim)
    return claims


def _run_path(seed: int, path_name: str) -> None:
    rng = Rng(seed)
    truth, case_facts = generate_case(rng, case_id=f"case_{seed}")
    presentation = project_case(truth, rng.fork("projection"))
    state = InvestigationState()
    state.leads = build_leads(presentation, start_time=state.time)
    board = DeductionBoard()

    witness = next((p for p in truth.people.values() if RoleTag.WITNESS in p.role_tags), None)
    suspect = next((p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags), None)
    if witness is None or suspect is None:
        print(f"[{path_name}] Missing witness or suspect; cannot validate.")
        return

    location_id = case_facts["crime_scene_id"]
    item_id = case_facts["weapon_id"]

    if path_name == "witness_only":
        interview(truth, presentation, state, witness.id, location_id)
        claims = [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
        evidence = [item for item in presentation.evidence if isinstance(item, WitnessStatement)]
    elif path_name == "cctv_only":
        request_cctv(truth, presentation, state, location_id)
        claims = [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
        evidence = [item for item in presentation.evidence if isinstance(item, CCTVReport)]
    elif path_name == "forensics_only":
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        claims = [ClaimType.BEHAVIOR]
        evidence = [item for item in presentation.evidence if isinstance(item, ForensicsResult)]
    elif path_name == "witness_cctv":
        interview(truth, presentation, state, witness.id, location_id)
        request_cctv(truth, presentation, state, location_id)
        claims = [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
        evidence = [
            item for item in presentation.evidence if isinstance(item, (WitnessStatement, CCTVReport))
        ]
    elif path_name == "witness_forensics":
        interview(truth, presentation, state, witness.id, location_id)
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        claims = [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
        evidence = [
            item for item in presentation.evidence if isinstance(item, (WitnessStatement, ForensicsResult))
        ]
    elif path_name == "cctv_forensics":
        request_cctv(truth, presentation, state, location_id)
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        claims = [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
        evidence = [
            item for item in presentation.evidence if isinstance(item, (CCTVReport, ForensicsResult))
        ]
    elif path_name == "aggressive":
        interview(truth, presentation, state, witness.id, location_id)
        evidence = [item for item in presentation.evidence if isinstance(item, WitnessStatement)]
        claims = _supported_claims(
            presentation,
            [item.id for item in evidence if item.id in state.knowledge.known_evidence],
            suspect.id,
        )
    elif path_name == "cautious":
        interview(truth, presentation, state, witness.id, location_id)
        request_cctv(truth, presentation, state, location_id)
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        evidence = [
            item
            for item in presentation.evidence
            if isinstance(item, (WitnessStatement, CCTVReport, ForensicsResult))
        ]
        claims = _supported_claims(
            presentation,
            [item.id for item in evidence if item.id in state.knowledge.known_evidence],
            suspect.id,
        )
    else:
        raise ValueError(f"Unknown path: {path_name}")

    evidence_ids = [item.id for item in evidence if item.id in state.knowledge.known_evidence]
    if not evidence_ids:
        print("")
        print(f"[{path_name}]")
        print("No evidence collected for this path. Skipping.")
        return
    if not claims:
        claims = [ClaimType.PRESENCE]
    set_hypothesis(state, board, suspect.id, claims, evidence_ids)
    arrest(truth, presentation, state, suspect.id, location_id, has_hypothesis=True)
    board.sync_from_state(state)
    validation = validate_hypothesis(truth, board, presentation, state)
    outcome = resolve_case_outcome(validation)

    print("")
    print(f"[{path_name}]")
    print(f"Evidence used: {len(evidence_ids)}")
    print(f"Validation: {validation.summary}")
    if validation.supports:
        print("- Supports:")
        for line in validation.supports:
            print(f"  - {line}")
    if validation.missing:
        print("- Missing:")
        for line in validation.missing:
            print(f"  - {line}")
    print(f"Outcome: {outcome.arrest_result}")
    for note in outcome.notes:
        print(f"- {note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate alternative investigation paths.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--max-tries", type=int, default=50)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Use the exact seed even if it lacks CCTV/forensics evidence.",
    )
    args = parser.parse_args()

    seed = args.seed
    if not args.force:
        found = _find_seed(args.seed, args.max_tries)
        if found is None:
            print("No seed found with testimonial + CCTV + forensics evidence.")
            print("Try --force to run the exact seed anyway.")
            return
        seed = found

    print(f"Validating alternative paths on seed {seed}.")
    for path in [
        "witness_only",
        "cctv_only",
        "forensics_only",
        "witness_cctv",
        "witness_forensics",
        "cctv_forensics",
        "aggressive",
        "cautious",
    ]:
        _run_path(seed, path)


if __name__ == "__main__":
    main()
