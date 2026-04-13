"""Support helpers for investigation actions."""

from __future__ import annotations

from collections import Counter
from typing import Callable
from uuid import UUID

from noir.domain.enums import ConfidenceBand, EvidenceType, EventKind, RoleTag
from noir.domain.models import Person
from noir.investigation.costs import (
    ActionType,
    COSTS,
    PRESSURE_LIMIT,
    clamp,
    would_exceed_limits,
)
from noir.investigation.dialog_graph import (
    load_interview_graph,
    render_dialog_text,
    resolve_dialog_role_key,
    select_choice_index,
)
from noir.investigation.interviews import (
    InterviewApproach,
    InterviewState,
    InterviewTheme,
)
from noir.investigation.leads import (
    LEAD_ACTIONS,
    LEAD_DEADLINES,
    LEAD_LABELS,
    Lead,
    LeadStatus,
    lead_for_type,
)
from noir.investigation.outcomes import TRUST_LIMIT
from noir.investigation.results import InvestigationState
from noir.narrative.styles import build_witness_line
from noir.naming import load_name_generator
from noir.presentation.evidence import EvidenceItem, PresentationCase
from noir.truth.graph import TruthState
from noir.util.rng import Rng

_NAME_GENERATOR = None


def _neighbor_name_pick(truth: TruthState, rng: Rng):
    global _NAME_GENERATOR
    if _NAME_GENERATOR is None:
        _NAME_GENERATOR = load_name_generator()
    context = _NAME_GENERATOR.start_case(rng)
    for person in truth.people.values():
        name = person.name
        if not name:
            continue
        context.used_full.add(name.lower())
        first = name.split(" ", 1)[0]
        context.used_first.add(first.lower())
        context.used_first_keys.add(first.lower())
    return context.next_name_pick(rng)


def _weighted_choice(rng: Rng, options: dict[str, float]) -> str | None:
    if not options:
        return None
    total = sum(max(0.0, value) for value in options.values())
    if total <= 0:
        return rng.choice(list(options.keys()))
    pick = rng.random() * total
    cumulative = 0.0
    for key, weight in options.items():
        cumulative += max(0.0, weight)
        if pick <= cumulative:
            return key
    return next(iter(options.keys()))


def _neighbor_role_label(role: str | None) -> str:
    if not role:
        return "local witness"
    role = role.replace("_", " ").strip()
    return role


def _neighbor_relation(role: str | None, lead_label: str) -> tuple[str, str]:
    label = lead_label.lower()
    if role in {"resident", "neighbor", "tenant"} or "neighbor" in label:
        return "neighbor", "acquaintance"
    if role in {"guest", "visitor"} or "guest" in label:
        return "acquaintance", "acquaintance"
    if role in {"staff", "security", "maintenance", "clerk"}:
        return "colleague", "acquaintance"
    return "stranger", "stranger"


def _district_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _district_counts(truth: TruthState) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in truth.events.values():
        location = truth.locations.get(event.location_id)
        if location and location.district:
            counts[str(location.district)] += 1
    if not counts:
        for location in truth.locations.values():
            if location.district:
                counts[str(location.district)] += 1
    return counts


def _time_bucket(hour: int) -> str:
    value = hour % 24
    if 5 <= value < 12:
        return "morning"
    if 12 <= value < 17:
        return "afternoon"
    if 17 <= value < 21:
        return "evening"
    return "midnight"


def _append_analyst_notes(state: InvestigationState, lines: list[str]) -> None:
    if not lines:
        return
    if state.analyst_notes:
        state.analyst_notes.append("")
    state.analyst_notes.extend(lines)


def _mark_style(state: InvestigationState, style: str | None) -> None:
    if not style:
        return
    state.style_counts[style] = state.style_counts.get(style, 0) + 1


def _apply_operation_outcome(
    state: InvestigationState,
    outcome,
    notes: list[str],
    label: str,
) -> None:
    if outcome.pressure_delta:
        state.pressure = int(
            clamp(state.pressure + outcome.pressure_delta, 0, PRESSURE_LIMIT)
        )
    if outcome.trust_delta:
        state.trust = int(clamp(state.trust + outcome.trust_delta, 0, TRUST_LIMIT))
    if outcome.pressure_delta > 0:
        notes.append(f"Pressure rises after the {label}.")
    elif outcome.pressure_delta < 0:
        notes.append(f"Pressure eases after the {label}.")
    if outcome.trust_delta > 0:
        notes.append("Trust improves after the operation.")
    elif outcome.trust_delta < 0:
        notes.append("Trust drops after the operation.")


def _ensure_cctv_lead(state: InvestigationState, notes: list[str]) -> None:
    lead = lead_for_type(state, EvidenceType.CCTV)
    if lead is None:
        deadline = state.time + LEAD_DEADLINES[EvidenceType.CCTV]
        state.leads.append(
            Lead(
                key=EvidenceType.CCTV.value,
                label=LEAD_LABELS[EvidenceType.CCTV],
                evidence_type=EvidenceType.CCTV,
                deadline=deadline,
                action_hint=LEAD_ACTIONS[EvidenceType.CCTV],
            )
        )
        notes.append("CCTV lead opened from analyst sweep.")
        return
    if lead.status == LeadStatus.EXPIRED:
        lead.status = LeadStatus.ACTIVE
        lead.deadline = state.time + LEAD_DEADLINES[EvidenceType.CCTV]
        notes.append("CCTV lead reopened from analyst sweep.")


def _reveal(
    state: InvestigationState,
    presentation: PresentationCase,
    predicate: Callable[[EvidenceItem], bool],
) -> list[EvidenceItem]:
    revealed: list[EvidenceItem] = []
    for item in presentation.evidence:
        if item.id in state.knowledge.known_evidence:
            continue
        if predicate(item):
            state.knowledge.known_evidence.append(item.id)
            revealed.append(item)
    return revealed


def _reveal_limited(
    state: InvestigationState,
    presentation: PresentationCase,
    predicate: Callable[[EvidenceItem], bool],
    limit: int,
) -> list[EvidenceItem]:
    revealed: list[EvidenceItem] = []
    for item in presentation.evidence:
        if item.id in state.knowledge.known_evidence:
            continue
        if predicate(item):
            state.knowledge.known_evidence.append(item.id)
            revealed.append(item)
            if len(revealed) >= limit:
                break
    return revealed


def _matches_location(item: EvidenceItem, location_id: UUID) -> bool:
    item_location = getattr(item, "location_id", None)
    if item_location is None:
        return True
    return item_location == location_id


def _apply_cooperation_decay(
    state: InvestigationState, revealed: list[EvidenceItem]
) -> list[str]:
    if not revealed:
        return []
    if state.cooperation >= 0.5:
        return []
    notes: list[str] = []
    for item in revealed:
        if item.evidence_type != EvidenceType.TESTIMONIAL:
            continue
        item.confidence = ConfidenceBand.WEAK
        item.observed_person_ids = []
        if hasattr(item, "statement"):
            item.statement = "The details are unclear; the witness is unsure."
        notes.append("Low cooperation weakens the witness statement.")
    return notes


def _apply_cost(
    state: InvestigationState, action: ActionType
) -> tuple[bool, str, int, int, float]:
    cost = COSTS[action]
    blocked, reason = would_exceed_limits(state.time, state.pressure, cost)
    if blocked:
        return True, reason, 0, 0, 0.0
    state.time += cost.time
    state.pressure += cost.pressure
    state.cooperation = clamp(state.cooperation + cost.cooperation_delta, 0.0, 1.0)
    return False, "", cost.time, cost.pressure, cost.cooperation_delta


def _interview_rng(truth: TruthState, witness_id: UUID, salt: str) -> Rng:
    base = Rng(truth.seed).fork(f"interview:{witness_id}")
    return base.fork(salt)


def _interview_state(
    state: InvestigationState, witness_id: UUID, truth: TruthState
) -> InterviewState:
    key = str(witness_id)
    existing = state.interviews.get(key)
    if existing:
        return existing
    rng = _interview_rng(truth, witness_id, "motive")
    offender = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    victim = next(
        (person for person in truth.people.values() if RoleTag.VICTIM in person.role_tags),
        None,
    )
    offender_relation = (
        truth.relationship_between(witness_id, offender.id) if offender else None
    )
    victim_relation = (
        truth.relationship_between(witness_id, victim.id) if victim else None
    )
    lie_chance = 0.15
    rapport = 0.5
    resistance = 0.5
    if offender_relation:
        closeness = str(offender_relation.get("closeness", "stranger"))
        rel_type = str(offender_relation.get("relationship_type", "stranger"))
        base = {"stranger": 0.1, "acquaintance": 0.25, "intimate": 0.45}.get(
            closeness, 0.15
        )
        bonus = 0.0
        if rel_type in {"parent", "partner", "lover", "sibling"}:
            bonus += 0.2
        elif rel_type in {"friend", "colleague", "neighbor"}:
            bonus += 0.1
        if closeness == "intimate":
            rapport -= 0.1
            resistance += 0.15
        elif closeness == "acquaintance":
            rapport -= 0.05
            resistance += 0.1
        lie_chance = base + bonus
    elif victim_relation:
        closeness = str(victim_relation.get("closeness", "stranger"))
        if closeness == "intimate":
            rapport += 0.1
            resistance -= 0.05
            lie_chance = min(lie_chance, 0.1)
        elif closeness == "acquaintance":
            rapport += 0.05
            lie_chance = min(lie_chance, 0.12)
    if state.cooperation < 0.5:
        lie_chance = min(0.9, lie_chance + 0.2)
    lie_chance = clamp(lie_chance, 0.05, 0.9)
    interview_state = InterviewState(
        motive_to_lie=rng.random() < lie_chance,
        rapport=clamp(rapport, 0.0, 1.0),
        resistance=clamp(resistance, 0.0, 1.0),
    )
    state.interviews[key] = interview_state
    return interview_state


def _apply_failed_arrest_backlash(
    state: InvestigationState,
    notes: list[str],
    *,
    wrong_suspect: bool,
) -> None:
    state.trust = int(clamp(state.trust - 1, 0, TRUST_LIMIT))
    state.pressure = int(clamp(state.pressure + 1, 0, PRESSURE_LIMIT))
    notes.append("Wrong-arrest fallout hits immediately: trust drops and pressure spikes.")
    if wrong_suspect:
        notes.append("The real offender gets time to bury the trail.")
    else:
        notes.append("Command sees the arrest as premature and pulls harder on the case.")


def _kill_event(truth: TruthState):
    events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    if not events:
        return None
    return sorted(events, key=lambda event: event.timestamp)[0]


def _theme_match(theme: InterviewTheme | None, motive_category: str) -> bool:
    if theme is None:
        return False
    motive = motive_category.lower()
    if motive in {"revenge", "obsession"}:
        return theme == InterviewTheme.BLAME_VICTIM
    if motive in {"money"}:
        return theme == InterviewTheme.CIRCUMSTANCE
    if motive in {"concealment"}:
        return theme == InterviewTheme.ACCIDENTAL
    if motive in {"thrill"}:
        return theme == InterviewTheme.ALTRUISTIC
    return False


def _dialog_statement_from_graph(
    interview_state: InterviewState,
    approach: InterviewApproach,
    theme: InterviewTheme | None,
    context: dict[str, str],
    dialog_choice_index: int | None,
    role_key: str,
) -> str | None:
    graph = load_interview_graph(role_key)
    if graph is None:
        return None
    node_id = interview_state.dialog_node_id or graph.root_node_id
    if not graph.has_node(node_id):
        node_id = graph.root_node_id
    node = graph.node(node_id)
    tags = [approach.value]
    if theme is not None:
        tags.append(f"theme:{theme.value}")
        tags.append(theme.value)
    if (
        dialog_choice_index is not None
        and node.choices
        and 0 <= dialog_choice_index < len(node.choices)
    ):
        next_id = node.choices[dialog_choice_index].leads_to_id
    else:
        choice_index = select_choice_index(node, tags)
        if choice_index is None or not node.choices:
            choice_index = None
        if choice_index is None:
            interview_state.dialog_node_id = node.node_id
            return render_dialog_text(node.text, context) or None
        next_id = node.choices[choice_index].leads_to_id
    if graph.has_node(next_id):
        interview_state.dialog_node_id = next_id
        node = graph.node(next_id)
    else:
        interview_state.dialog_node_id = node.node_id
        return render_dialog_text(node.text, context) or None
    if not node.choices:
        interview_state.dialog_node_id = graph.root_node_id
    rendered = render_dialog_text(node.text, context)
    return rendered or None


def _dialog_relationship_profile(
    truth: TruthState,
    person_id: UUID,
) -> tuple[str | None, str | None]:
    victim = next(
        (person for person in truth.people.values() if RoleTag.VICTIM in person.role_tags),
        None,
    )
    offender = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    relations = []
    if victim is not None:
        victim_relation = truth.relationship_between(person_id, victim.id)
        if victim_relation:
            relations.append(victim_relation)
    if offender is not None:
        offender_relation = truth.relationship_between(person_id, offender.id)
        if offender_relation:
            relations.append(offender_relation)
    for relation in relations:
        if str(relation.get("closeness", "") or "").lower() == "intimate":
            return str(relation.get("closeness", "") or ""), str(
                relation.get("relationship_type", "") or ""
            )
    if relations:
        relation = relations[0]
        return str(relation.get("closeness", "") or ""), str(
            relation.get("relationship_type", "") or ""
        )
    return None, None


def _dialog_role_key(
    truth: TruthState,
    person: Person,
    interview_state: InterviewState,
) -> str:
    relationship_closeness, relationship_type = _dialog_relationship_profile(truth, person.id)
    return resolve_dialog_role_key(
        person.role_tags,
        person.traits if isinstance(person.traits, dict) else None,
        motive_to_lie=interview_state.motive_to_lie,
        relationship_closeness=relationship_closeness,
        relationship_type=relationship_type,
    )


def _witness_line_category(
    role: str | None,
    neighbor_role: str | None = None,
    relationship_closeness: str | None = None,
) -> str:
    witness_role = str(role or "").lower()
    relation = str(neighbor_role or "").lower()
    staff_roles = {
        "staff",
        "security",
        "maintenance",
        "clerk",
        "cashier",
        "bartender",
        "attendant",
        "concierge",
        "manager",
        "reception",
        "receptionist",
    }
    passerby_roles = {
        "passerby",
        "visitor",
        "guest",
        "commuter",
        "driver",
        "customer",
        "pedestrian",
        "outsider",
    }
    if str(relationship_closeness or "").lower() == "intimate":
        return "intimate_lines"
    if witness_role in {"neighbor", "resident", "tenant"} or any(
        token in relation for token in ("neighbor", "resident", "tenant")
    ):
        return "neighbor_lines"
    if witness_role in staff_roles or any(token in relation for token in staff_roles):
        return "staff_lines"
    if witness_role in passerby_roles:
        return "passerby_lines"
    return "lines"


def _replace_subject_reference(line: str, subject_name: str | None) -> str:
    if not subject_name:
        return line
    replacements = ("someone", "a person", "a figure", "a face")
    updated = line
    lowered = updated.lower()
    for target in replacements:
        index = lowered.find(target)
        if index >= 0:
            return updated[:index] + subject_name + updated[index + len(target):]
    return updated


def _anchor_witness_line(line: str, place: str) -> str:
    lowered = line.lower()
    if any(
        token in lowered
        for token in (" near ", " outside ", " inside ", " by ", " around ", place.lower())
    ):
        return line
    suffix = f" near {place}."
    if line.endswith("."):
        return line[:-1] + suffix
    return line + suffix


def _live_witness_line(
    rng: Rng,
    category: str,
    place: str,
    subject_name: str | None = None,
) -> str:
    line = build_witness_line(rng, category) or "I heard a disturbance."
    line = _replace_subject_reference(line, subject_name)
    return _anchor_witness_line(line, place)