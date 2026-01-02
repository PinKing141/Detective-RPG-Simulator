"""Phase 1 investigation actions."""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis
from noir.domain.enums import EvidenceType, EventKind
from noir.investigation.costs import ActionType, COSTS, clamp, would_exceed_limits
from noir.investigation.leads import (
    LeadStatus,
    apply_lead_decay,
    lead_for_type,
    mark_lead_resolved,
    update_lead_statuses,
)
from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.presentation.evidence import EvidenceItem, PresentationCase
from noir.truth.simulator import apply_action
from noir.truth.graph import TruthState


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


def visit_scene(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    location_id: UUID,
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
        metadata={"action": "visit_scene"},
    )
    notes = update_lead_statuses(state)
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.FORENSICS)
    lead = lead_for_type(state, EvidenceType.FORENSICS)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed:
        mark_lead_resolved(state, EvidenceType.FORENSICS)
    summary = "You document the scene and collect trace evidence."
    if not revealed:
        summary = "The scene yields no new trace evidence."
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.TESTIMONIAL)
    lead = lead_for_type(state, EvidenceType.TESTIMONIAL)
    if lead and lead.status == LeadStatus.EXPIRED and revealed:
        notes.extend(apply_lead_decay(lead, revealed))
    elif revealed:
        mark_lead_resolved(state, EvidenceType.TESTIMONIAL)
    summary = "The interview yields a usable statement."
    if not revealed:
        summary = "The interview adds nothing new."
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.FORENSICS)
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
