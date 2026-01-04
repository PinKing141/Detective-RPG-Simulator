"""Phase 1 investigation actions."""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis
from noir.domain.enums import ConfidenceBand, EvidenceType, EventKind, RoleTag
from noir.investigation.costs import ActionType, COSTS, clamp, would_exceed_limits
from noir.investigation.interviews import (
    InterviewApproach,
    InterviewPhase,
    InterviewState,
    InterviewTheme,
    baseline_hooks,
    build_baseline_profile,
)
from noir.investigation.leads import (
    LeadStatus,
    apply_lead_decay,
    lead_for_type,
    mark_lead_resolved,
    shorten_lead,
    update_lead_statuses,
)
from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.presentation.evidence import EvidenceItem, PresentationCase, WitnessStatement
from noir.presentation.erosion import fuzz_time
from noir.truth.simulator import apply_action
from noir.truth.graph import TruthState
from noir.util.grammar import place_with_article
from noir.util.rng import Rng


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
    relationship_distance = str(truth.case_meta.get("relationship_distance", "stranger"))
    rng = _interview_rng(truth, witness_id, "motive")
    lie_chance = 0.15 if relationship_distance == "stranger" else 0.45
    if state.cooperation < 0.5:
        lie_chance = min(0.9, lie_chance + 0.2)
    interview_state = InterviewState(motive_to_lie=rng.random() < lie_chance)
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
        lambda item: item.evidence_type == EvidenceType.FORENSICS
        and item.source == "Scene Unit"
        and (item.poi_id == poi_id),
    )
    lead = lead_for_type(state, EvidenceType.FORENSICS)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed and any(item.source == "Forensics Lab" for item in revealed):
        mark_lead_resolved(state, EvidenceType.FORENSICS)
    summary = "You document the scene and collect trace evidence."
    if poi_label:
        summary = f"You document the {poi_label}."
    if not revealed:
        summary = "The scene yields no new trace evidence."
        if poi_label:
            summary = f"The {poi_label} yields no new trace evidence."
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
    apply_action(truth, EventKind.INTERVIEW, state.time, location_id, participants=[person_id])
    notes = update_lead_statuses(state)
    interview_state = _interview_state(state, person_id, truth)
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
            statement = f"I heard a disturbance near {place}."
            if truth_seen and suspect_name:
                statement = f"I saw {suspect_name} outside {place}."
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
        lie_type = "denial"
        force_contradiction = False
        if (
            base_window
            and base_known
            and not interview_state.contradiction_emitted
            and approach == InterviewApproach.PRESSURE
        ):
            force_contradiction = True
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
                interview_state.contradiction_emitted = True
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

        if lie_bias and lie_type == "denial":
            statement = f"I didn't see anyone, just noise around {time_phrase}."
        else:
            statement = f"I saw {suspect_name} near {place} {time_phrase}."
        if not truth_seen and not observed_person_ids:
            statement = f"I heard a disturbance near {place} {time_phrase}."

        hooks = baseline_hooks(interview_state.baseline_profile, statement, template_hooks)
        evidence = WitnessStatement(
            evidence_type=EvidenceType.TESTIMONIAL,
            summary="Witness statement (follow-up)",
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
    apply_action(
        truth,
        EventKind.REQUEST_CCTV,
        state.time,
        location_id,
        metadata={"action": "request_cctv"},
    )
    notes = update_lead_statuses(state)
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.CCTV)
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
        and item.source == "Forensics Lab",
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
