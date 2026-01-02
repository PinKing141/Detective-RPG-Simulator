from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.truth_generator import generate_case
from noir.deduction.board import DeductionBoard, MethodType, TimeBucket
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import EvidenceType, RoleTag
from noir.investigation.actions import arrest, interview, request_cctv, set_hypothesis, submit_forensics
from noir.investigation.leads import build_leads
from noir.investigation.outcomes import resolve_case_outcome
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def _bucket_from_window(window: tuple[int, int]) -> TimeBucket:
    start, end = window
    mid = int(round((start + end) / 2))
    hour = mid % 24
    if 5 <= hour < 12:
        return TimeBucket.MORNING
    if 12 <= hour < 17:
        return TimeBucket.AFTERNOON
    if 17 <= hour < 21:
        return TimeBucket.EVENING
    return TimeBucket.MIDNIGHT


def _method_from_forensics(items: list) -> MethodType:
    for item in items:
        if not isinstance(item, ForensicsResult):
            continue
        if item.method_category == "sharp":
            return MethodType.SHARP
        if item.method_category == "blunt":
            return MethodType.BLUNT
        if item.method_category == "poison":
            return MethodType.POISON
    return MethodType.UNKNOWN


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

    if path_name == "witness_cctv":
        interview(truth, presentation, state, witness.id, location_id)
        request_cctv(truth, presentation, state, location_id)
        method = MethodType.UNKNOWN
        evidence = [
            item for item in presentation.evidence if isinstance(item, (WitnessStatement, CCTVReport))
        ]
    elif path_name == "witness_forensics":
        interview(truth, presentation, state, witness.id, location_id)
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        method = _method_from_forensics(presentation.evidence)
        evidence = [
            item for item in presentation.evidence if isinstance(item, (WitnessStatement, ForensicsResult))
        ]
    else:
        raise ValueError(f"Unknown path: {path_name}")

    witness_item = next((item for item in evidence if isinstance(item, WitnessStatement)), None)
    time_bucket = (
        _bucket_from_window(witness_item.reported_time_window)
        if witness_item
        else TimeBucket.MIDNIGHT
    )
    evidence_ids = [item.id for item in evidence if item.id in state.knowledge.known_evidence]
    set_hypothesis(state, board, suspect.id, method, time_bucket, evidence_ids)
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
    _run_path(seed, "witness_cctv")
    _run_path(seed, "witness_forensics")


if __name__ == "__main__":
    main()
