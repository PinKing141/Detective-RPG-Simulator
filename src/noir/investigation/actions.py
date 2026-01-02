"""Phase 0 investigation actions."""

from __future__ import annotations

from typing import Callable, Optional
from uuid import UUID

from noir.deduction.board import DeductionBoard, Hypothesis, MethodType, TimeBucket
from noir.domain.enums import EvidenceType, EventKind
from noir.investigation.costs import ActionType, COSTS, clamp, would_exceed_limits
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.FORENSICS)
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.TESTIMONIAL)
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.CCTV)
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
    revealed = _reveal(state, presentation, lambda item: item.evidence_type == EvidenceType.FORENSICS)
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
    outcome = ActionOutcome.SUCCESS
    summary = "Arrest attempted."
    return ActionResult(
        action=ActionType.ARREST,
        outcome=outcome,
        summary=summary,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        cooperation_change=coop_delta,
    )


def set_hypothesis(
    state: InvestigationState,
    board: DeductionBoard,
    suspect_id: UUID,
    method: MethodType,
    time_bucket: TimeBucket,
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

    board.hypothesis = Hypothesis(
        suspect_id=suspect_id,
        method=method,
        time_bucket=time_bucket,
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
    )
