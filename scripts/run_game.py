from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.archetypes import CaseArchetype
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
from noir.investigation.outcomes import TRUST_LIMIT, resolve_case_outcome
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.locations.profiles import ScenePOI
from noir.presentation.evidence import ForensicObservation, WitnessStatement
from noir.presentation.projector import project_case
from noir.profiling.summary import build_profiling_summary, format_profiling_summary
from noir.util.rng import Rng
from noir.persistence.db import WorldStore
from noir.world.autonomy import apply_autonomy
from noir.world.state import CaseStartModifiers, PersonRecord, WorldState


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


def _poi_display_label(state: InvestigationState, poi: ScenePOI) -> str:
    label = f"{poi.zone_label} - {poi.label}"
    if state.body_poi_id and poi.poi_id == state.body_poi_id:
        return f"{label} (body)"
    return label


def _choose_poi(state: InvestigationState) -> ScenePOI | None:
    unvisited = [poi for poi in state.scene_pois if poi.poi_id not in state.visited_poi_ids]
    if not unvisited:
        return None
    print("Choose a scene area to inspect:")
    for idx, poi in enumerate(unvisited, start=1):
        print(f"{idx}) {_poi_display_label(state, poi)}")
    choice = input("> ").strip()
    if not choice.isdigit():
        return None
    index = int(choice) - 1
    if index < 0 or index >= len(unvisited):
        return None
    return unvisited[index]

def _primary_role_tag(role_tags: list[RoleTag]) -> str:
    if RoleTag.WITNESS in role_tags:
        return RoleTag.WITNESS.value
    if RoleTag.OFFENDER in role_tags:
        return RoleTag.OFFENDER.value
    if RoleTag.VICTIM in role_tags:
        return RoleTag.VICTIM.value
    if RoleTag.SUSPECT in role_tags:
        return RoleTag.SUSPECT.value
    return "unknown"


def _sync_people(world: WorldState, truth, case_id: str, tick: int) -> None:
    for person in truth.people.values():
        person_id = str(person.id)
        existing = world.people_index.get(person_id)
        country = None
        if isinstance(person.traits, dict):
            country = person.traits.get("country_of_origin")
        record = PersonRecord(
            person_id=person_id,
            name=person.name,
            role_tag=_primary_role_tag(list(person.role_tags)),
            country_of_origin=country if isinstance(country, str) else None,
            religion_affiliation=None,
            religion_observance=None,
            community_connectedness=None,
            created_in_case_id=existing.created_in_case_id if existing else case_id,
            last_seen_case_id=case_id,
            last_seen_tick=tick,
        )
        world.upsert_person(record)


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


def _poi_lines(state: InvestigationState) -> list[str]:
    if not state.scene_pois:
        return ["(none)"]
    lines: list[str] = []
    for idx, poi in enumerate(state.scene_pois, start=1):
        status = "visited" if poi.poi_id in state.visited_poi_ids else "unvisited"
        lines.append(f"{idx}) {_poi_display_label(state, poi)} ({status})")
    return lines


def _poi_label_for(state: InvestigationState, poi_id: str | None) -> str | None:
    if not poi_id:
        return None
    for poi in state.scene_pois:
        if poi.poi_id == poi_id:
            return _poi_display_label(state, poi)
    return None


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
        elif isinstance(item, ForensicObservation):
            print(f"{idx}) {item.summary}")
            poi_label = _poi_label_for(state, item.poi_id)
            if poi_label:
                print(f"   Location: {poi_label}")
            print(f"   Observation: {item.observation}")
            if item.tod_window:
                print(f"   Estimated TOD: {_format_time_phrase(item.tod_window)}")
            if item.stage_hint:
                print(f"   Stage hint: {item.stage_hint}")
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
    world: WorldState,
    case_id_override: str | None = None,
    case_archetype: CaseArchetype | None = None,
):
    case_rng = base_rng.fork(f"case-{case_index}")
    case_id = case_id_override or f"case_{seed}_{case_index}"
    truth, case_facts = generate_case(
        case_rng, case_id=case_id, world=world, case_archetype=case_archetype
    )
    presentation = project_case(truth, case_rng.fork("projection"))
    location = truth.locations.get(case_facts["crime_scene_id"])
    district = location.district if location else "unknown"
    location_name = location.name if location else "unknown"
    modifiers = world.case_start_modifiers(district, location_name)
    has_returning = world.has_returning_person(truth.people, case_id)
    next_state = InvestigationState(
        pressure=world.pressure,
        trust=world.trust,
        cooperation=modifiers.cooperation,
    )
    next_state.leads = build_leads(
        presentation,
        start_time=next_state.time,
        deadline_delta=modifiers.lead_deadline_delta,
    )
    scene_layout = case_facts.get("scene_layout") or {}
    poi_rows = scene_layout.get("pois", []) or []
    next_state.scene_pois = [ScenePOI(**row) for row in poi_rows if isinstance(row, dict)]
    body_poi_id = case_facts.get("body_poi_id") or case_facts.get("primary_poi_id")
    next_state.body_poi_id = body_poi_id or None
    _sync_people(world, truth, case_id, world.tick)
    if has_returning:
        modifiers = CaseStartModifiers(
            cooperation=modifiers.cooperation,
            lead_deadline_delta=modifiers.lead_deadline_delta,
            briefing_lines=modifiers.briefing_lines
            + ["A familiar name is attached to the file."],
        )

    board = DeductionBoard()
    location_id = case_facts["crime_scene_id"]
    item_id = case_facts["weapon_id"]
    return (
        truth,
        presentation,
        next_state,
        board,
        location_id,
        item_id,
        district,
        location_name,
        modifiers,
    )


def _find_seed_with_observed(
    start_seed: int, max_tries: int, case_archetype: CaseArchetype | None
) -> int | None:
    for seed in range(start_seed, start_seed + max_tries):
        base_rng = Rng(seed)
        case_rng = base_rng.fork("case-1")
        truth, _ = generate_case(
            case_rng, case_id=f"case_{seed}_1", case_archetype=case_archetype
        )
        presentation = project_case(truth, case_rng.fork("projection"))
        for item in presentation.evidence:
            observed = getattr(item, "observed_person_ids", None)
            if observed and item.evidence_type in (EvidenceType.TESTIMONIAL, EvidenceType.CCTV):
                return seed
    return None


def _run_smoke(seed: int, case_id: str | None, case_archetype: CaseArchetype | None) -> None:
    base_rng = Rng(seed)
    world = WorldState()
    truth, presentation, state, board, location_id, item_id, _, _, _ = _start_case(
        base_rng,
        seed,
        1,
        world,
        case_id_override=case_id,
        case_archetype=case_archetype,
    )
    print(f"[smoke] Case {truth.case_id} started.")
    witness = next(
        (p for p in truth.people.values() if RoleTag.WITNESS in p.role_tags), None
    )
    if witness:
        interview(truth, presentation, state, witness.id, location_id)
    request_cctv(truth, presentation, state, location_id)
    if state.scene_pois:
        poi = state.scene_pois[0]
        visit_scene(truth, presentation, state, location_id, poi_id=poi.poi_id, poi_label=poi.label)
    else:
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
        "--case-archetype",
        type=str,
        choices=[c.value for c in CaseArchetype],
        default=None,
        help="Force a case archetype (e.g., pattern or character).",
    )
    parser.add_argument(
        "--world-db",
        type=str,
        default=str(ROOT / "data" / "world_state.db"),
        help="SQLite database path for world state.",
    )
    parser.add_argument(
        "--no-world-db",
        action="store_true",
        help="Run without persisting world state.",
    )
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
    case_archetype = CaseArchetype(args.case_archetype) if args.case_archetype else None

    if args.smoke:
        seed = args.seed
        if args.smoke_find:
            found = _find_seed_with_observed(args.seed, args.smoke_tries, case_archetype)
            if found is None:
                print("[smoke] No seed found with observed evidence.")
                return
            seed = found
            print(f"[smoke] Using seed {seed}.")
        _run_smoke(seed, args.case_id, case_archetype)
        return

    world_store = None
    world = WorldState()
    if not args.no_world_db:
        world_store = WorldStore(Path(args.world_db))
        world = world_store.load_world_state()

    base_rng = Rng(args.seed)
    case_index = 1
    case_start_tick = world.tick
    truth, presentation, state, board, location_id, item_id, district, location_name, modifiers = _start_case(
        base_rng,
        args.seed,
        case_index,
        world,
        case_id_override=args.case_id,
        case_archetype=case_archetype,
    )

    print(
        f"Case {truth.case_id} started. Investigation time limit {TIME_LIMIT}, "
        f"pressure tolerance {PRESSURE_LIMIT}, trust {state.trust}/{TRUST_LIMIT}."
    )
    for line in modifiers.briefing_lines:
        print(line)
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
        print("Scene POIs:")
        for line in _poi_lines(state):
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
            body_poi = None
            if state.body_poi_id:
                for poi in state.scene_pois:
                    if (
                        poi.poi_id == state.body_poi_id
                        and poi.poi_id not in state.visited_poi_ids
                    ):
                        body_poi = poi
                        break
            auto_body = False
            if body_poi:
                auto_body = True
                result = visit_scene(
                    truth,
                    presentation,
                    state,
                    location_id,
                    poi_id=body_poi.poi_id,
                    poi_label=_poi_display_label(state, body_poi),
                )
            else:
                poi = _choose_poi(state)
                if poi:
                    result = visit_scene(
                        truth,
                        presentation,
                        state,
                        location_id,
                        poi_id=poi.poi_id,
                        poi_label=_poi_display_label(state, poi),
                    )
                else:
                    result = visit_scene(truth, presentation, state, location_id)
            if auto_body and any(
                poi.poi_id not in state.visited_poi_ids for poi in state.scene_pois
            ):
                result.notes.append(
                    "Other scene areas remain; visit the scene again to inspect another area."
                )
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
            context_lines = world.context_lines(district, location_name)
            summary = build_profiling_summary(
                presentation,
                state,
                board.hypothesis,
                context_lines=context_lines,
            )
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

        autonomy_notes = apply_autonomy(state, world, district)
        if autonomy_notes:
            result.notes.extend(autonomy_notes)

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
                elif isinstance(item, ForensicObservation):
                    print(f"- New evidence: {item.summary}")
                    poi_label = _poi_label_for(state, item.poi_id)
                    if poi_label:
                        print(f"  Location: {poi_label}")
                    print(f"  Observation: {item.observation}")
                    if item.tod_window:
                        print(f"  Estimated TOD: {_format_time_phrase(item.tod_window)}")
                    if item.stage_hint:
                        print(f"  Stage hint: {item.stage_hint}")
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
            case_end_tick = case_start_tick + state.time
            world_notes = world.apply_case_outcome(
                outcome,
                truth.case_id,
                args.seed,
                district,
                location_name,
                case_start_tick,
                case_end_tick,
            )
            if world_store:
                world_store.save_world_state(world)
                world_store.record_case(world.case_history[-1])
            for note in world_notes:
                print(f"- {note}")
            case_index += 1
            case_start_tick = world.tick
            truth, presentation, state, board, location_id, item_id, district, location_name, modifiers = _start_case(
                base_rng,
                args.seed,
                case_index,
                world,
                case_archetype=case_archetype,
            )
            print(
                f"New case {truth.case_id} started. "
                f"Pressure {state.pressure}/{PRESSURE_LIMIT}, "
                f"Trust {state.trust}/{TRUST_LIMIT}."
            )
            for line in modifiers.briefing_lines:
                print(line)

    if world_store:
        world_store.save_world_state(world)
        world_store.close()


if __name__ == "__main__":
    main()
