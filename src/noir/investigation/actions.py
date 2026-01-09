"""Phase 1 investigation actions."""

from __future__ import annotations

from collections import Counter
from typing import Callable, Optional
from uuid import UUID

from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis
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
    choice_label_for,
    load_default_interview_graph,
    render_dialog_text,
    select_choice_index,
)
from noir.investigation.interviews import (
    InterviewApproach,
    InterviewPhase,
    InterviewState,
    InterviewTheme,
    baseline_hooks,
    build_baseline_profile,
)
from noir.investigation.leads import (
    Lead,
    LEAD_ACTIONS,
    LEAD_DEADLINES,
    LEAD_LABELS,
    LeadStatus,
    NeighborLead,
    apply_lead_decay,
    format_neighbor_lead,
    lead_for_type,
    mark_lead_resolved,
    shorten_lead,
    update_lead_statuses,
)
from noir.investigation.operations import (
    OperationPlan,
    OperationTier,
    OperationType,
    WarrantType,
    resolve_operation,
)
from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.locations.profiles import load_location_profiles
from noir.presentation.evidence import CCTVReport, EvidenceItem, PresentationCase, WitnessStatement
from noir.naming import load_name_generator
from noir.presentation.erosion import confidence_from_window, fuzz_time
from noir.truth.simulator import apply_action
from noir.truth.graph import TruthState
from noir.util.grammar import place_with_article
from noir.util.rng import Rng
from noir.profiling.profile import (
    OffenderProfile,
    ProfileDrive,
    ProfileMobility,
    ProfileOrganization,
)
from noir.investigation.outcomes import TRUST_LIMIT

_NAME_GENERATOR = None
DEFAULT_DISTRICTS = ["harbor", "midtown", "old_quarter", "riverside"]


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


def _apply_cooperation_decay(state: InvestigationState, revealed: list[EvidenceItem]) -> list[str]:
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
) -> str | None:
    graph = load_default_interview_graph()
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


def visit_location(
    state: InvestigationState,
    location_id: UUID,
    location_name: str | None = None,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.VISIT_LOCATION
    )
    if blocked:
        return ActionResult(
            action=ActionType.VISIT_LOCATION,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    state.active_location_id = location_id
    destination = location_name or "a new location"
    summary = f"Travelled to {destination}."
    return ActionResult(
        action=ActionType.VISIT_LOCATION,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
    )


def visit_scene(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
    poi_id: str | None = None,
    poi_label: str | None = None,
    poi_description: str | None = None,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(state, ActionType.VISIT_SCENE)
    if blocked:
        return ActionResult(
            action=ActionType.VISIT_SCENE,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    apply_action(
        truth,
        EventKind.INVESTIGATE_SCENE,
        state.time,
        location_id,
        metadata={"action": "visit_scene", "poi_id": str(poi_id) if poi_id else ""},
    )
    notes = update_lead_statuses(state)
    if poi_description:
        notes.append(f"Scene note: {poi_description}")
    if poi_id:
        state.visited_poi_ids.add(poi_id)
    revealed = _reveal(
        state,
        presentation,
        lambda item: _matches_location(item, location_id)
        and (item.poi_id == poi_id if poi_id else item.source == "Scene Unit"),
    )
    if revealed:
        revealed_by_type: dict[EvidenceType, list[EvidenceItem]] = {}
        for item in revealed:
            revealed_by_type.setdefault(item.evidence_type, []).append(item)
        for evidence_type, items in revealed_by_type.items():
            lead = lead_for_type(state, evidence_type)
            if lead and lead.status == LeadStatus.EXPIRED:
                notes.extend(apply_lead_decay(lead, items))
            elif lead:
                mark_lead_resolved(state, evidence_type)
        notes.extend(_apply_cooperation_decay(state, revealed))
    summary = "You document the scene and collect evidence."
    if poi_label:
        summary = f"You document the {poi_label}."
    if not revealed:
        summary = "The scene yields no new evidence."
        if poi_label:
            summary = f"The {poi_label} yields no new evidence."
    return ActionResult(
        action=ActionType.VISIT_SCENE,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        revealed=revealed,
        notes=notes,
    )


def interview(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    person_id: UUID,
    location_id: UUID,
    approach: InterviewApproach = InterviewApproach.BASELINE,
    theme: InterviewTheme | None = None,
    dialog_choice_index: int | None = None,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(state, ActionType.INTERVIEW)
    if blocked:
        return ActionResult(
            action=ActionType.INTERVIEW,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    style = "coercive" if approach == InterviewApproach.PRESSURE else "social"
    _mark_style(state, style)
    apply_action(truth, EventKind.INTERVIEW, state.time, location_id, participants=[person_id])
    notes = update_lead_statuses(state)
    interview_state = _interview_state(state, person_id, truth)
    if dialog_choice_index is not None:
        graph = load_default_interview_graph()
        if graph is not None:
            node_id = interview_state.dialog_node_id or graph.root_node_id
            label = choice_label_for(graph, node_id, dialog_choice_index)
            if label:
                notes.append(f"Interview prompt: {label}.")
    if interview_state.phase == InterviewPhase.SHUTDOWN:
        notes.append("The witness refuses to continue.")
        return ActionResult(
            action=ActionType.INTERVIEW,
            outcome=ActionOutcome.FAILURE,
            summary="Interview (shutdown) yields no statement.",
            time_cost=time_cost,
            pressure_cost=pressure_cost,
            cooperation_change=coop_delta,
            notes=notes,
        )

    witness_statements = [
        item
        for item in presentation.evidence
        if isinstance(item, WitnessStatement) and item.witness_id == person_id
    ]
    base_statement = witness_statements[0] if witness_statements else None
    base_known = bool(
        base_statement and base_statement.id in state.knowledge.known_evidence
    )
    base_window = base_statement.reported_time_window if base_statement else None
    kill_event = _kill_event(truth)
    location = truth.locations.get(location_id)
    location_name = location.name if location else "location"
    place = place_with_article(location_name)
    suspect = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    suspect_name = suspect.name if suspect else "someone"
    suspect_id = suspect.id if suspect else None
    truth_seen = bool(base_statement and suspect_id and suspect_id in base_statement.observed_person_ids)

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

    def _contradiction_window(window: tuple[int, int]) -> tuple[int, int]:
        start, end = window
        if start >= 6:
            return (max(0, start - 6), max(0, start - 4))
        if end <= 17:
            return (min(23, end + 4), min(23, end + 6))
        return (max(0, start - 6), max(0, start - 4))

    def _maybe_add_detail_statement(
        revealed: list[EvidenceItem],
        time_window: tuple[int, int] | None,
    ) -> None:
        if len(revealed) >= 2 or time_window is None:
            return
        detail_candidates = [
            item
            for item in presentation.evidence
            if isinstance(item, WitnessStatement)
            and item.witness_id == person_id
            and item.summary == "Witness statement (detail)"
            and item.id not in state.knowledge.known_evidence
        ]
        if detail_candidates:
            for item in detail_candidates[: max(0, 2 - len(revealed))]:
                state.knowledge.known_evidence.append(item.id)
                revealed.append(item)
            return
        if interview_state.rapport < 0.55 or state.cooperation < 0.4:
            return
        detail_rng = _interview_rng(truth, person_id, f"detail:{state.time}:{approach}")
        if detail_rng.random() > 0.35:
            return
        detail_window = time_window
        if (detail_window[1] - detail_window[0]) >= 2:
            detail_window = (detail_window[0] + 1, detail_window[1] - 1)
        detail_phrase = _format_time_phrase(detail_window)
        detail_statement = f"I remember the timing more clearly: {detail_phrase}."
        observed_ids: list[UUID] = []
        if truth_seen and suspect_id:
            detail_statement = f"They were nearby {detail_phrase}."
            observed_ids = [suspect_id]
        evidence = WitnessStatement(
            evidence_type=EvidenceType.TESTIMONIAL,
            summary="Witness statement (detail)",
            source="Interview",
            time_collected=state.time,
            confidence=ConfidenceBand.MEDIUM,
            witness_id=person_id,
            statement=detail_statement,
            reported_time_window=detail_window,
            location_id=location_id,
            observed_person_ids=observed_ids,
            uncertainty_hooks=["Added detail under rapport."],
        )
        presentation.evidence.append(evidence)
        state.knowledge.known_evidence.append(evidence.id)
        revealed.append(evidence)

    if approach == InterviewApproach.BASELINE:
        revealed = _reveal_limited(
            state,
            presentation,
            lambda item: item.evidence_type == EvidenceType.TESTIMONIAL
            and getattr(item, "witness_id", None) == person_id,
            limit=2,
        )
        if revealed and interview_state.baseline_profile is None:
            interview_state.baseline_profile = build_baseline_profile(revealed[0].statement)
        if interview_state.baseline_profile is None and base_statement:
            interview_state.baseline_profile = build_baseline_profile(base_statement.statement)
        if not revealed and kill_event and not witness_statements:
            rng = _interview_rng(truth, person_id, f"baseline:{state.time}")
            time_window = fuzz_time(kill_event.timestamp, sigma=1.5, rng=rng)
            time_phrase = _format_time_phrase(time_window)
            statement = f"I heard a disturbance near {place}."
            if truth_seen and suspect_name:
                statement = f"I saw {suspect_name} outside {place}."
            dialog_context = {
                "place": place,
                "suspect": suspect_name,
                "time_phrase": time_phrase,
                "approach": approach.value,
            }
            dialog_statement = _dialog_statement_from_graph(
                interview_state, approach, theme, dialog_context, dialog_choice_index
            )
            if dialog_statement:
                statement = dialog_statement
            hooks = baseline_hooks(interview_state.baseline_profile, statement, [])
            evidence = WitnessStatement(
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source="Interview",
                time_collected=state.time,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=person_id,
                statement=statement,
                reported_time_window=time_window,
                location_id=location_id,
                observed_person_ids=[suspect_id] if truth_seen and suspect_id else [],
                uncertainty_hooks=hooks,
            )
            presentation.evidence.append(evidence)
            state.knowledge.known_evidence.append(evidence.id)
            revealed = [evidence]
            interview_state.baseline_profile = build_baseline_profile(statement)
        interview_state.phase = InterviewPhase.BASELINE
        interview_state.rapport = clamp(interview_state.rapport + 0.05, 0.0, 1.0)
        interview_state.resistance = clamp(interview_state.resistance - 0.05, 0.0, 1.0)
        interview_state.fatigue = clamp(interview_state.fatigue + 0.05, 0.0, 1.0)
        detail_window = base_window
        if detail_window is None and revealed:
            first = revealed[0]
            if isinstance(first, WitnessStatement):
                detail_window = first.reported_time_window
        _maybe_add_detail_statement(revealed, detail_window)
        lead = lead_for_type(state, EvidenceType.TESTIMONIAL)
        if lead and lead.status == LeadStatus.EXPIRED and revealed:
            notes.extend(apply_lead_decay(lead, revealed))
        elif revealed:
            mark_lead_resolved(state, EvidenceType.TESTIMONIAL)
        notes.extend(_apply_cooperation_decay(state, revealed))
        summary = f"Interview ({approach.value}) yields a usable statement."
        if not revealed:
            summary = f"Interview ({approach.value}) adds nothing new."
        return ActionResult(
            action=ActionType.INTERVIEW,
            outcome=ActionOutcome.SUCCESS,
            summary=summary,
            time_cost=time_cost,
            pressure_cost=pressure_cost,
            cooperation_change=coop_delta,
            revealed=revealed,
            notes=notes,
        )

    if approach == InterviewApproach.PRESSURE:
        interview_state.phase = InterviewPhase.PRESSURE
        interview_state.rapport = clamp(interview_state.rapport - 0.1, 0.0, 1.0)
        interview_state.resistance = clamp(interview_state.resistance + 0.1, 0.0, 1.0)
        interview_state.fatigue = clamp(interview_state.fatigue + 0.2, 0.0, 1.0)
        state.cooperation = clamp(state.cooperation - 0.1, 0.0, 1.0)
    elif approach == InterviewApproach.THEME:
        interview_state.phase = InterviewPhase.THEME
        match = _theme_match(theme, str(truth.case_meta.get("motive_category", "")))
        if match:
            interview_state.rapport = clamp(interview_state.rapport + 0.05, 0.0, 1.0)
            interview_state.resistance = clamp(interview_state.resistance - 0.15, 0.0, 1.0)
        else:
            interview_state.resistance = clamp(interview_state.resistance + 0.05, 0.0, 1.0)
        interview_state.fatigue = clamp(interview_state.fatigue + 0.1, 0.0, 1.0)

    if interview_state.resistance >= 0.85 or interview_state.rapport <= 0.15:
        interview_state.phase = InterviewPhase.SHUTDOWN
        lead = lead_for_type(state, EvidenceType.TESTIMONIAL)
        if lead:
            lead.status = LeadStatus.EXPIRED
        notes.append("The witness shuts down; the lead goes cold.")
        return ActionResult(
            action=ActionType.INTERVIEW,
            outcome=ActionOutcome.FAILURE,
            summary=f"Interview ({approach.value}) triggers a shutdown.",
            time_cost=time_cost,
            pressure_cost=pressure_cost,
            cooperation_change=coop_delta,
            notes=notes,
        )

    revealed: list[EvidenceItem] = []
    followup_candidates = [
        item
        for item in witness_statements
        if item.summary == "Witness statement (follow-up)"
    ]
    skip_new_followup = False
    if followup_candidates:
        revealed = _reveal_limited(
            state,
            presentation,
            lambda item: item.evidence_type == EvidenceType.TESTIMONIAL
            and getattr(item, "witness_id", None) == person_id
            and getattr(item, "summary", "") == "Witness statement (follow-up)",
            limit=2,
        )
        skip_new_followup = True
    if kill_event and not skip_new_followup:
        rng = _interview_rng(truth, person_id, f"followup:{state.time}:{approach}")
        if base_window:
            time_window = base_window
        else:
            time_window = fuzz_time(kill_event.timestamp, sigma=2.0, rng=rng)
        lie_bias = interview_state.motive_to_lie and interview_state.resistance >= 0.4
        if approach == InterviewApproach.THEME and _theme_match(theme, str(truth.case_meta.get("motive_category", ""))):
            lie_bias = False
        contradiction_id = truth.case_meta.get("contradiction_witness_id")
        force_contradiction = (
            base_window
            and not interview_state.contradiction_emitted
            and (
                not contradiction_id
                or str(contradiction_id) == str(person_id)
            )
        )
        lie_type = "denial"
        if lie_bias and rng.random() > 0.5:
            lie_type = "misdirection"
        if lie_bias:
            shift = rng.choice([-3, 3])
            time_window = (
                max(0, min(23, time_window[0] + shift)),
                max(0, min(23, time_window[1] + shift)),
            )
        if force_contradiction and base_window:
            options: list[tuple[int, int]] = []
            early_start = max(0, base_window[0] - 4)
            early_end = max(0, base_window[0] - 2)
            if early_end < base_window[0]:
                options.append((early_start, early_end))
            late_start = min(23, base_window[1] + 2)
            late_end = min(23, base_window[1] + 4)
            if late_start > base_window[1]:
                options.append((late_start, late_end))
            if options:
                time_window = rng.choice(options)
            else:
                time_window = _contradiction_window(base_window)
            interview_state.contradiction_emitted = True
            lie_bias = True
            lie_type = "denial"
        elif approach in (InterviewApproach.PRESSURE, InterviewApproach.THEME):
            if (time_window[1] - time_window[0]) >= 2:
                time_window = (time_window[0] + 1, time_window[1] - 1)

        confidence = ConfidenceBand.MEDIUM
        if interview_state.fatigue >= 0.6 or interview_state.resistance >= 0.75:
            confidence = ConfidenceBand.WEAK
        if interview_state.resistance <= 0.3 and len(state.knowledge.known_evidence) >= 2:
            interview_state.phase = InterviewPhase.CONFESSION
            confidence = ConfidenceBand.STRONG
            notes.append("The witness concedes under pressure.")
            notes.append("Confession recorded.")

        time_phrase = _format_time_phrase(time_window)
        template_hooks: list[str] = []
        if lie_bias:
            template_hooks.append("Statement feels rehearsed.")
        if force_contradiction:
            template_hooks.append("Timeline conflicts with an earlier account.")
        if approach == InterviewApproach.PRESSURE:
            template_hooks.append("Timing is delivered quickly, without detail.")
        if approach == InterviewApproach.THEME and theme is not None:
            template_hooks.append("Framing steers the narrative rather than facts.")

        observed_person_ids: list[UUID] = []
        if lie_bias and lie_type == "misdirection" and suspect_id:
            observed_person_ids = [suspect_id]
        elif not lie_bias and truth_seen and suspect_id:
            observed_person_ids = [suspect_id]

        confession = interview_state.phase == InterviewPhase.CONFESSION
        if confession:
            if truth_seen and suspect_name:
                statement = (
                    f"I should have said this earlier. I saw {suspect_name} near {place} "
                    f"{time_phrase}. I held it back because I did not want trouble."
                )
            else:
                statement = (
                    f"I should have said this earlier. I heard the disturbance near {place} "
                    f"{time_phrase}. I kept quiet because I did not want trouble."
                )
            template_hooks.append("Concession under pressure.")
        elif lie_bias and lie_type == "denial":
            statement = f"I didn't see anyone, just noise around {time_phrase}."
        else:
            statement = f"I saw {suspect_name} near {place} {time_phrase}."
        if not truth_seen and not observed_person_ids and not confession:
            statement = f"I heard a disturbance near {place} {time_phrase}."
        if not lie_bias and not confession:
            dialog_context = {
                "place": place,
                "suspect": suspect_name,
                "time_phrase": time_phrase,
                "approach": approach.value,
            }
            dialog_statement = _dialog_statement_from_graph(
                interview_state, approach, theme, dialog_context, dialog_choice_index
            )
            if dialog_statement:
                statement = dialog_statement
        if confession and truth_seen and suspect_id:
            observed_person_ids = [suspect_id]

        hooks = baseline_hooks(interview_state.baseline_profile, statement, template_hooks)
        summary = "Witness statement (follow-up)"
        if confession:
            summary = "Witness statement (confession)"
        evidence = WitnessStatement(
            evidence_type=EvidenceType.TESTIMONIAL,
            summary=summary,
            source="Interview",
            time_collected=state.time,
            confidence=confidence,
            witness_id=person_id,
            statement=statement,
            reported_time_window=time_window,
            location_id=location_id,
            observed_person_ids=observed_person_ids,
            uncertainty_hooks=hooks,
        )
        presentation.evidence.append(evidence)
        state.knowledge.known_evidence.append(evidence.id)
        revealed.append(evidence)
        interview_state.last_claims = ["presence", "opportunity"]
        if interview_state.baseline_profile is None:
            interview_state.baseline_profile = build_baseline_profile(statement)

    detail_window = base_window
    if detail_window is None and revealed:
        first = revealed[0]
        if isinstance(first, WitnessStatement):
            detail_window = first.reported_time_window
    if detail_window is None and kill_event:
        detail_rng = _interview_rng(truth, person_id, f"detail:{state.time}:followup")
        detail_window = fuzz_time(kill_event.timestamp, sigma=2.5, rng=detail_rng)
    _maybe_add_detail_statement(revealed, detail_window)

    lead = lead_for_type(state, EvidenceType.TESTIMONIAL)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed:
        mark_lead_resolved(state, EvidenceType.TESTIMONIAL)
    notes.extend(_apply_cooperation_decay(state, revealed))
    summary = f"Interview ({approach.value}) yields a usable statement."
    if not revealed:
        summary = f"Interview ({approach.value}) adds nothing new."
    return ActionResult(
        action=ActionType.INTERVIEW,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        revealed=revealed,
        notes=notes,
    )


def follow_neighbor_lead(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
    lead: NeighborLead | None,
) -> ActionResult:
    if lead is None or lead not in state.neighbor_leads:
        return ActionResult(
            action=ActionType.FOLLOW_NEIGHBOR,
            outcome=ActionOutcome.FAILURE,
            summary="No neighbor lead available.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.FOLLOW_NEIGHBOR
    )
    if blocked:
        return ActionResult(
            action=ActionType.FOLLOW_NEIGHBOR,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "social")
    notes = update_lead_statuses(state)
    rng = Rng(truth.seed).fork(f"neighbor:{lead.slot_id}:{state.time}")
    role = _weighted_choice(rng, lead.witness_roles) or "witness"
    role_label = _neighbor_role_label(role)
    name_pick = _neighbor_name_pick(truth, rng)
    traits: dict[str, float | str] = {"neighbor_role": role_label, "neighbor_slot": lead.slot_id}
    if name_pick.country:
        traits["country_of_origin"] = name_pick.country
    witness = Person(
        name=name_pick.full,
        role_tags=[RoleTag.WITNESS],
        traits=traits,
    )
    truth.add_person(witness)
    victim = next(
        (person for person in truth.people.values() if RoleTag.VICTIM in person.role_tags),
        None,
    )
    if victim:
        relation_type, closeness = _neighbor_relation(role, lead.label)
        truth.add_relationship(witness.id, victim.id, relation_type, closeness)
    apply_action(
        truth,
        EventKind.INTERVIEW,
        state.time,
        location_id,
        participants=[witness.id],
        metadata={"action": "neighbor_lead", "slot_id": lead.slot_id},
    )
    location = truth.locations.get(location_id)
    place = place_with_article(location.name if location else "location")
    suspect = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    suspect_name = suspect.name if suspect else "someone"
    suspect_id = suspect.id if suspect else None
    risk_tolerance = 0.5
    if suspect and isinstance(suspect.traits, dict):
        risk_value = suspect.traits.get("risk_tolerance")
        if isinstance(risk_value, (int, float)):
            risk_tolerance = float(risk_value)
    see_chance = min(0.85, max(0.15, lead.hearing_bias + (risk_tolerance * 0.2)))
    saw_suspect = rng.random() < see_chance
    if lead.hearing_bias < 0.35 and rng.random() < 0.6:
        saw_suspect = False
    kill_event = _kill_event(truth)
    base_time = kill_event.timestamp if kill_event else state.time
    sigma = 1.2 + (1.0 - lead.hearing_bias) * 2.0
    time_window = fuzz_time(base_time, sigma=sigma, rng=rng)
    confidence = confidence_from_window(time_window)
    uncertainty_hooks: list[str] = []
    if not saw_suspect:
        uncertainty_hooks.append("Account is based on sound rather than sight.")
    if lead.hearing_bias < 0.35:
        uncertainty_hooks.append("Audibility was low from the neighbor position.")
        confidence = ConfidenceBand.WEAK
    elif lead.hearing_bias < 0.45 and saw_suspect:
        uncertainty_hooks.append("Visibility was partial from the witness position.")
    elif lead.hearing_bias >= 0.55 and saw_suspect and confidence == ConfidenceBand.MEDIUM:
        confidence = ConfidenceBand.STRONG
    if saw_suspect:
        statement = f"As a {role_label}, I saw {suspect_name} near {place}."
    else:
        statement = f"As a {role_label}, I heard a disturbance near {place}."
    observed_person_ids = [suspect_id] if saw_suspect and suspect_id else []
    evidence = WitnessStatement(
        evidence_type=EvidenceType.TESTIMONIAL,
        summary="Witness statement (neighbor)",
        source="Neighbor lead",
        time_collected=state.time,
        confidence=confidence,
        witness_id=witness.id,
        statement=statement,
        reported_time_window=time_window,
        location_id=location_id,
        observed_person_ids=observed_person_ids,
        uncertainty_hooks=uncertainty_hooks,
    )
    presentation.evidence.append(evidence)
    state.knowledge.known_evidence.append(evidence.id)
    revealed = [evidence]
    lead_clock = lead_for_type(state, EvidenceType.TESTIMONIAL)
    if lead_clock and lead_clock.status == LeadStatus.EXPIRED:
        notes.extend(apply_lead_decay(lead_clock, revealed))
    notes.extend(_apply_cooperation_decay(state, revealed))
    if lead in state.neighbor_leads:
        state.neighbor_leads.remove(lead)
    notes.append(f"Neighbor lead followed: {format_neighbor_lead(lead)}.")
    summary = "Neighbor lead yields a usable statement."
    return ActionResult(
        action=ActionType.FOLLOW_NEIGHBOR,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        revealed=revealed,
        notes=notes,
    )


def request_cctv(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(state, ActionType.REQUEST_CCTV)
    if blocked:
        return ActionResult(
            action=ActionType.REQUEST_CCTV,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    apply_action(
        truth,
        EventKind.REQUEST_CCTV,
        state.time,
        location_id,
        metadata={"action": "request_cctv"},
    )
    notes = update_lead_statuses(state)
    revealed = _reveal(
        state,
        presentation,
        lambda item: item.evidence_type == EvidenceType.CCTV
        and _matches_location(item, location_id),
    )
    lead = lead_for_type(state, EvidenceType.CCTV)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed:
        mark_lead_resolved(state, EvidenceType.CCTV)
    witness_lead = shorten_lead(state, EvidenceType.TESTIMONIAL, delta=1)
    if witness_lead and witness_lead.status == LeadStatus.EXPIRED:
        known = [
            item
            for item in presentation.evidence
            if item.id in set(state.knowledge.known_evidence)
            and item.evidence_type == EvidenceType.TESTIMONIAL
        ]
        if known:
            notes.extend(apply_lead_decay(witness_lead, known))
        notes.append("Witness lead went cold after the CCTV request.")
    summary = "CCTV footage arrives."
    if not revealed:
        summary = "No usable CCTV footage is available."
    return ActionResult(
        action=ActionType.REQUEST_CCTV,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        revealed=revealed,
        notes=notes,
    )


def submit_forensics(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
    item_id: Optional[UUID] = None,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(state, ActionType.SUBMIT_FORENSICS)
    if blocked:
        return ActionResult(
            action=ActionType.SUBMIT_FORENSICS,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    metadata = {"action": "submit_forensics"}
    if item_id:
        metadata["item_id"] = str(item_id)
    apply_action(
        truth,
        EventKind.SUBMIT_FORENSICS,
        state.time,
        location_id,
        metadata=metadata,
    )
    notes = update_lead_statuses(state)
    revealed = _reveal(
        state,
        presentation,
        lambda item: item.evidence_type == EvidenceType.FORENSICS
        and item.source == "Forensics Lab"
        and _matches_location(item, location_id),
    )
    lead = lead_for_type(state, EvidenceType.FORENSICS)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed:
        mark_lead_resolved(state, EvidenceType.FORENSICS)
    summary = "Forensics returns a report."
    if not revealed:
        summary = "Forensics finds nothing conclusive."
    return ActionResult(
        action=ActionType.SUBMIT_FORENSICS,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        revealed=revealed,
        notes=notes,
    )


def rossmo_lite(
    truth: TruthState,
    state: InvestigationState,
    mobility: ProfileMobility | None = None,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.ANALYST_ROSSMO
    )
    if blocked:
        return ActionResult(
            action=ActionType.ANALYST_ROSSMO,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    notes = update_lead_statuses(state)
    lines: list[str] = []
    counts = _district_counts(truth)
    if counts:
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if len(ordered) <= 1:
            lines.append("Single-site signal; spatial clustering is weak.")
        top = [district for district, _ in ordered[:3]]
        zone_list = ", ".join(_district_label(district) for district in top)
        lines.append(f"Spatial clustering favors {zone_list}.")
    else:
        lines.append("No spatial signal yet; too few sites to infer a zone.")
    assumption = mobility or ProfileMobility.UNKNOWN
    if assumption == ProfileMobility.MARAUDER:
        lines.append("Assumption: local offender; focus on nearby districts.")
    elif assumption == ProfileMobility.COMMUTER:
        lines.append("Assumption: commuter pattern; watch transit edges.")
    else:
        lines.append("Assumption: mobility unknown; treat as a weak constraint.")
    _append_analyst_notes(state, lines)
    notes.extend(lines)
    return ActionResult(
        action=ActionType.ANALYST_ROSSMO,
        outcome=ActionOutcome.SUCCESS,
        summary="Rossmo-lite assessment logged.",
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
    )


def tech_sweep(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
) -> ActionResult:
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.ANALYST_SWEEP
    )
    if blocked:
        return ActionResult(
            action=ActionType.ANALYST_SWEEP,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    notes = update_lead_statuses(state)
    rng = Rng(truth.seed).fork(f"tech_sweep:{state.time}")
    profiles = load_location_profiles()
    archetype_id = None
    for entry in truth.case_meta.get("locations", []) or []:
        entry_id = entry.get("location_id")
        if entry_id and str(location_id) == str(entry_id):
            archetype_id = entry.get("archetype_id")
            break
    if not archetype_id:
        archetype_id = truth.case_meta.get("location_archetype")
    archetype = profiles["archetypes"].get(archetype_id, {}) if archetype_id else {}
    presence_curve = archetype.get("presence_curve", {}) or {}
    surveillance = archetype.get("surveillance", {}) or {}
    logs = archetype.get("logs", []) or []
    kill_event = _kill_event(truth)
    bucket = _time_bucket(kill_event.timestamp if kill_event else state.time)
    presence = float(presence_curve.get(bucket, 0.4))
    cctv_weight = float(surveillance.get("cctv", 0.0))
    logs_weight = min(0.8, 0.2 + (0.1 * len(logs))) if logs else 0.0
    witness_weight = presence
    choice = None
    if max(cctv_weight, logs_weight, witness_weight) > 0.05:
        choice = _weighted_choice(
            rng,
            {"cctv": cctv_weight, "logs": logs_weight, "witness": witness_weight},
        )

    lines: list[str] = []
    if choice in {"cctv", "logs"}:
        _ensure_cctv_lead(state, notes)
        if choice == "logs" and logs:
            sample = ", ".join(logs[:2])
            lines.append(f"Access logs flag usable records ({sample}).")
        else:
            lines.append("Camera coverage appears usable for the scene window.")
        if not any(item.evidence_type == EvidenceType.CCTV for item in presentation.evidence):
            time_window = fuzz_time(
                kill_event.timestamp if kill_event else state.time,
                sigma=2.5,
                rng=rng,
            )
            report = CCTVReport(
                evidence_type=EvidenceType.CCTV,
                summary="CCTV report (partial)",
                source="Tech sweep",
                time_collected=state.time,
                confidence=ConfidenceBand.WEAK,
                location_id=location_id,
                observed_person_ids=[],
                time_window=time_window,
            )
            presentation.evidence.append(report)
    elif choice == "witness":
        witness_roles = {
            str(role): float(weight)
            for role, weight in (archetype.get("witness_roles", {}) or {}).items()
        }
        if not witness_roles:
            witness_roles = {"passerby": 1.0}
        noise = float(archetype.get("visibility", {}).get("noise", 0.4))
        hearing_bias = max(0.15, min(0.75, presence * (1.0 - noise) + 0.1))
        slot_id = f"tech_sweep:{state.time}"
        state.neighbor_leads.append(
            NeighborLead(
                slot_id=slot_id,
                label="Tech sweep contact",
                hearing_bias=hearing_bias,
                witness_roles=witness_roles,
            )
        )
        lines.append("Tech sweep identifies a potential witness contact.")
    else:
        lines.append("Tech sweep finds no actionable trail.")

    if bucket:
        lines.append(f"Activity pattern suggests {bucket} visibility.")
    _append_analyst_notes(state, lines)
    notes.extend(lines)
    return ActionResult(
        action=ActionType.ANALYST_SWEEP,
        outcome=ActionOutcome.SUCCESS,
        summary="Tech sweep logged.",
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
    )


def request_warrant(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    board: DeductionBoard,
    location_id: UUID,
    warrant_type: WarrantType,
    evidence_ids: list[UUID] | None = None,
) -> ActionResult:
    if board.hypothesis is None:
        return ActionResult(
            action=ActionType.REQUEST_WARRANT,
            outcome=ActionOutcome.FAILURE,
            summary="Set a hypothesis before requesting a warrant.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.REQUEST_WARRANT
    )
    if blocked:
        return ActionResult(
            action=ActionType.REQUEST_WARRANT,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if evidence_ids is None:
        evidence_ids = list(board.hypothesis.evidence_ids)
    if not evidence_ids:
        return ActionResult(
            action=ActionType.REQUEST_WARRANT,
            outcome=ActionOutcome.FAILURE,
            summary="Select supporting evidence before requesting a warrant.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    plan = OperationPlan(
        op_type=OperationType.WARRANT,
        warrant_type=warrant_type,
        target_person_id=board.hypothesis.suspect_id,
        target_location_id=location_id,
        evidence_ids=list(evidence_ids),
    )
    outcome = resolve_operation(plan, presentation, board.hypothesis)
    apply_action(
        truth,
        EventKind.REQUEST_WARRANT,
        state.time,
        location_id,
        participants=[board.hypothesis.suspect_id],
        metadata={"action": "request_warrant", "warrant_type": warrant_type.value},
    )
    notes = update_lead_statuses(state)
    notes.extend(outcome.notes)
    _apply_operation_outcome(state, outcome, notes, "warrant decision")
    action_outcome = (
        ActionOutcome.SUCCESS
        if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
        else ActionOutcome.FAILURE
    )
    if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}:
        state.warrant_grants.add(warrant_type.value)
    return ActionResult(
        action=ActionType.REQUEST_WARRANT,
        outcome=action_outcome,
        summary=outcome.summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
        operation_type=OperationType.WARRANT,
        operation_tier=outcome.tier,
    )


def stakeout(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    board: DeductionBoard,
    location_id: UUID,
    evidence_ids: list[UUID],
) -> ActionResult:
    if board.hypothesis is None:
        return ActionResult(
            action=ActionType.STAKEOUT,
            outcome=ActionOutcome.FAILURE,
            summary="Set a hypothesis before running a stakeout.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if not evidence_ids:
        return ActionResult(
            action=ActionType.STAKEOUT,
            outcome=ActionOutcome.FAILURE,
            summary="Select supporting evidence before running a stakeout.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.STAKEOUT
    )
    if blocked:
        return ActionResult(
            action=ActionType.STAKEOUT,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "analytical")
    plan = OperationPlan(
        op_type=OperationType.STAKEOUT,
        target_person_id=board.hypothesis.suspect_id,
        target_location_id=location_id,
        evidence_ids=list(evidence_ids),
    )
    outcome = resolve_operation(plan, presentation, board.hypothesis)
    apply_action(
        truth,
        EventKind.STAKEOUT,
        state.time,
        location_id,
        participants=[board.hypothesis.suspect_id],
        metadata={"action": "stakeout"},
    )
    notes = update_lead_statuses(state)
    notes.extend(outcome.notes)
    _apply_operation_outcome(state, outcome, notes, "stakeout")
    action_outcome = (
        ActionOutcome.SUCCESS
        if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
        else ActionOutcome.FAILURE
    )
    return ActionResult(
        action=ActionType.STAKEOUT,
        outcome=action_outcome,
        summary=outcome.summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
        operation_type=OperationType.STAKEOUT,
        operation_tier=outcome.tier,
    )


def bait(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    board: DeductionBoard,
    location_id: UUID,
    evidence_ids: list[UUID],
) -> ActionResult:
    if board.hypothesis is None:
        return ActionResult(
            action=ActionType.BAIT,
            outcome=ActionOutcome.FAILURE,
            summary="Set a hypothesis before running a bait operation.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if not evidence_ids:
        return ActionResult(
            action=ActionType.BAIT,
            outcome=ActionOutcome.FAILURE,
            summary="Select supporting evidence before running bait.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.BAIT
    )
    if blocked:
        return ActionResult(
            action=ActionType.BAIT,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "coercive")
    plan = OperationPlan(
        op_type=OperationType.BAIT,
        target_person_id=board.hypothesis.suspect_id,
        target_location_id=location_id,
        evidence_ids=list(evidence_ids),
    )
    outcome = resolve_operation(plan, presentation, board.hypothesis)
    apply_action(
        truth,
        EventKind.BAIT,
        state.time,
        location_id,
        participants=[board.hypothesis.suspect_id],
        metadata={"action": "bait"},
    )
    notes = update_lead_statuses(state)
    notes.extend(outcome.notes)
    _apply_operation_outcome(state, outcome, notes, "bait operation")
    action_outcome = (
        ActionOutcome.SUCCESS
        if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
        else ActionOutcome.FAILURE
    )
    return ActionResult(
        action=ActionType.BAIT,
        outcome=action_outcome,
        summary=outcome.summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
        operation_type=OperationType.BAIT,
        operation_tier=outcome.tier,
    )


def raid(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    board: DeductionBoard,
    location_id: UUID,
    evidence_ids: list[UUID],
) -> ActionResult:
    if board.hypothesis is None:
        return ActionResult(
            action=ActionType.RAID,
            outcome=ActionOutcome.FAILURE,
            summary="Set a hypothesis before running a raid.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if not (
        WarrantType.ARREST.value in state.warrant_grants
        or WarrantType.SEARCH.value in state.warrant_grants
    ):
        return ActionResult(
            action=ActionType.RAID,
            outcome=ActionOutcome.FAILURE,
            summary="Raid requires an arrest or search warrant.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if not evidence_ids:
        return ActionResult(
            action=ActionType.RAID,
            outcome=ActionOutcome.FAILURE,
            summary="Select supporting evidence before running a raid.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.RAID
    )
    if blocked:
        return ActionResult(
            action=ActionType.RAID,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    _mark_style(state, "coercive")
    plan = OperationPlan(
        op_type=OperationType.RAID,
        target_person_id=board.hypothesis.suspect_id,
        target_location_id=location_id,
        evidence_ids=list(evidence_ids),
    )
    outcome = resolve_operation(plan, presentation, board.hypothesis)
    apply_action(
        truth,
        EventKind.RAID,
        state.time,
        location_id,
        participants=[board.hypothesis.suspect_id],
        metadata={"action": "raid"},
    )
    notes = update_lead_statuses(state)
    notes.extend(outcome.notes)
    _apply_operation_outcome(state, outcome, notes, "raid")
    action_outcome = (
        ActionOutcome.SUCCESS
        if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
        else ActionOutcome.FAILURE
    )
    return ActionResult(
        action=ActionType.RAID,
        outcome=action_outcome,
        summary=outcome.summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
        operation_type=OperationType.RAID,
        operation_tier=outcome.tier,
    )


def arrest(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    person_id: UUID,
    location_id: UUID,
    has_hypothesis: bool,
) -> ActionResult:
    if not has_hypothesis:
        return ActionResult(
            action=ActionType.ARREST,
            outcome=ActionOutcome.FAILURE,
            summary="No hypothesis submitted.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(state, ActionType.ARREST)
    if blocked:
        return ActionResult(
            action=ActionType.ARREST,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    apply_action(
        truth,
        EventKind.ARREST,
        state.time,
        location_id,
        participants=[person_id],
        metadata={"action": "arrest", "person_id": str(person_id)},
    )
    notes = update_lead_statuses(state)
    outcome = ActionOutcome.SUCCESS
    summary = "Arrest attempted."
    return ActionResult(
        action=ActionType.ARREST,
        outcome=outcome,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
    )


def set_hypothesis(
    state: InvestigationState,
    board: DeductionBoard,
    suspect_id: UUID,
    claims: list[ClaimType],
    evidence_ids: list[UUID],
) -> ActionResult:
    if len(evidence_ids) < 1 or len(evidence_ids) > 3:
        return ActionResult(
            action=ActionType.SET_HYPOTHESIS,
            outcome=ActionOutcome.FAILURE,
            summary="Hypothesis not set. At least 1 supporting evidence is required.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    if len(claims) < 1 or len(claims) > 3:
        return ActionResult(
            action=ActionType.SET_HYPOTHESIS,
            outcome=ActionOutcome.FAILURE,
            summary="Hypothesis not set. Select 1 to 3 claims.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    known_ids = set(state.knowledge.known_evidence)
    if not set(evidence_ids).issubset(known_ids):
        return ActionResult(
            action=ActionType.SET_HYPOTHESIS,
            outcome=ActionOutcome.FAILURE,
            summary="Hypothesis uses evidence you have not collected.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )

    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.SET_HYPOTHESIS
    )
    if blocked:
        return ActionResult(
            action=ActionType.SET_HYPOTHESIS,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
    )

    notes = update_lead_statuses(state)
    _mark_style(state, "analytical")
    board.hypothesis = Hypothesis(
        suspect_id=suspect_id,
        claims=list(dict.fromkeys(claims)),
        evidence_ids=list(evidence_ids),
    )
    summary = "Hypothesis submitted."
    return ActionResult(
        action=ActionType.SET_HYPOTHESIS,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
    )


def set_profile(
    state: InvestigationState,
    organization: ProfileOrganization,
    drive: ProfileDrive,
    mobility: ProfileMobility,
    evidence_ids: list[UUID],
) -> ActionResult:
    if len(evidence_ids) < 1 or len(evidence_ids) > 3:
        return ActionResult(
            action=ActionType.SET_PROFILE,
            outcome=ActionOutcome.FAILURE,
            summary="Profile not set. At least 1 supporting evidence is required.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
    known_ids = set(state.knowledge.known_evidence)
    if not set(evidence_ids).issubset(known_ids):
        return ActionResult(
            action=ActionType.SET_PROFILE,
            outcome=ActionOutcome.FAILURE,
            summary="Profile uses evidence you have not collected.",
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )

    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        state, ActionType.SET_PROFILE
    )
    if blocked:
        return ActionResult(
            action=ActionType.SET_PROFILE,
            outcome=ActionOutcome.FAILURE,
            summary=reason,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
    )

    notes = update_lead_statuses(state)
    _mark_style(state, "analytical")
    state.profile = OffenderProfile(
        organization=organization,
        drive=drive,
        mobility=mobility,
        evidence_ids=list(evidence_ids),
    )
    summary = "Profile submitted."
    return ActionResult(
        action=ActionType.SET_PROFILE,
        outcome=ActionOutcome.SUCCESS,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
        notes=notes,
    )
