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
from noir.domain.enums import RoleTag
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


def _format_method(method: MethodType) -> str:
    mapping = {
        MethodType.SHARP: "Sharp force",
        MethodType.BLUNT: "Blunt force",
        MethodType.POISON: "Poison",
        MethodType.UNKNOWN: "Unknown",
    }
    return mapping.get(method, method.value)


def _format_time_bucket(bucket: TimeBucket) -> str:
    return bucket.value.capitalize()


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
        return f"Detective note: Supports presence near the scene ({name})."
    return "Detective note: Supports the timeline near the scene."


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


def _hypothesis_line(board: DeductionBoard, truth) -> str:
    if board.hypothesis is None:
        return "Hypothesis: (none)"
    suspect = truth.people.get(board.hypothesis.suspect_id)
    suspect_name = suspect.name if suspect else "Unknown"
    method = _format_method(board.hypothesis.method)
    time_bucket = _format_time_bucket(board.hypothesis.time_bucket)
    evd_count = len(board.hypothesis.evidence_ids)
    return f"Hypothesis: {suspect_name} | {method} | {time_bucket} | Evd: {evd_count}"


def _supports_line(board: DeductionBoard, presentation) -> str | None:
    if board.hypothesis is None:
        return None
    evidence_ids = set(board.hypothesis.evidence_ids)
    counts = {"strong": 0, "med": 0, "weak": 0}
    for item in presentation.evidence:
        if item.id not in evidence_ids:
            continue
        confidence = getattr(item, "confidence", None)
        if confidence is None:
            continue
        value = confidence.value if hasattr(confidence, "value") else str(confidence)
        if value == "strong":
            counts["strong"] += 1
        elif value == "medium":
            counts["med"] += 1
        elif value == "weak":
            counts["weak"] += 1
    if sum(counts.values()) == 0:
        return None
    return f"Supports: strong {counts['strong']} / med {counts['med']} / weak {counts['weak']}"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 playable loop.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    args = parser.parse_args()

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
        print(_hypothesis_line(board, truth))
        supports_line = _supports_line(board, presentation)
        if supports_line:
            print(supports_line)
        print(f"Evidence known: {len(state.knowledge.known_evidence)}/{len(presentation.evidence)}")
        print("Leads:")
        for line in _lead_lines(state):
            print(f"- {line}")
        print("1) Visit scene")
        print("2) Interview witness")
        print("3) Request CCTV")
        print("4) Submit forensics")
        print("5) Set hypothesis")
        print("6) Arrest suspect")
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
            print("Choose method:")
            method = _choose_enum(MethodType, _format_method)
            if method is None:
                print("Invalid method.")
                continue
            print("Choose time of day:")
            time_bucket = _choose_enum(TimeBucket, _format_time_bucket)
            if time_bucket is None:
                print("Invalid time selection.")
                continue
            evidence_ids = _choose_evidence(truth, presentation, board.known_evidence_ids)
            result = set_hypothesis(
                state,
                board,
                selection[1].id,
                method,
                time_bucket,
                evidence_ids,
            )
        elif choice == "6":
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
