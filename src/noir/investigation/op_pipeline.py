"""Unified operation pipeline: Trigger -> Plan -> Execute -> Outcome -> Fallout.

Stakeout, bait, raid, and warrant requests all share the same five-stage
shape. This module owns the shape and the per-stage seams so the public
entry points in ``actions`` are thin wrappers, and so the legal /
probable-cause rigor that gates warrants is visible at the gate rather
than buried inside the resolver.

Stages
------
* **Trigger**  preconditions and cost. Hypothesis present? Evidence
  selected? Required warrants held? Time / pressure budget? Probable
  cause cleared (for warrants)? Returns either a block (with reason) or
  a clearance.
* **Plan**     builds the ``OperationPlan`` carried into execute,
  bundling target, evidence packet, and operation-specific flags.
* **Execute**  deterministic outcome computation against the evidence
  mix and hypothesis. Reuses the existing ``resolve_operation``.
* **Outcome**  the tier + summary + notes block returned by execute.
* **Fallout**  side effects on state and the world: trust/pressure
  deltas on local state, warrant grant on a clean warrant decision,
  nemesis awareness raised on visible moves, lead status sweep,
  style-counter increment, and event-log append.

The orchestrator ``run_operation`` runs the five stages in order and
returns both the ``ActionResult`` and a ``PipelineSnapshot`` that the
UI or tests can inspect for stage-level transparency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from noir.investigation.costs import ActionType, PRESSURE_LIMIT
from noir.investigation.legal import LegalCheck, ProbableCause, evaluate_probable_cause
from noir.investigation.leads import update_lead_statuses
from noir.investigation.operations import (
    OperationOutcome,
    OperationPlan,
    OperationTier,
    OperationType,
    WarrantType,
    resolve_operation,
)
from noir.investigation.outcomes import TRUST_LIMIT
from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.investigation.action_support import _apply_cost, _mark_style
from noir.investigation.costs import clamp
from noir.presentation.evidence import PresentationCase
from noir.domain.enums import EventKind
from noir.truth.simulator import apply_action
from noir.truth.graph import TruthState

if TYPE_CHECKING:
    from noir.deduction.board import DeductionBoard
    from noir.world.state import WorldState


# ---------------------------------------------------------------------------
# Inputs to the pipeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationRequest:
    op_type: OperationType
    location_id: UUID
    evidence_ids: tuple[UUID, ...]
    warrant_type: WarrantType | None = None


@dataclass
class OperationContext:
    truth: TruthState
    presentation: PresentationCase
    state: InvestigationState
    board: "DeductionBoard"
    world: "WorldState | None" = None


# ---------------------------------------------------------------------------
# Stage results
# ---------------------------------------------------------------------------


@dataclass
class TriggerResult:
    allowed: bool
    summary: str = ""
    action_type: ActionType = ActionType.STAKEOUT
    time_cost: int = 0
    pressure_cost: int = 0
    coop_delta: float = 0.0
    legal_check: LegalCheck | None = None


@dataclass
class PipelineSnapshot:
    """Observable view of every stage. Used by tests and the UI."""

    op_type: OperationType
    trigger: TriggerResult
    plan: OperationPlan | None = None
    outcome: OperationOutcome | None = None
    fallout_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-op profile: the only thing that differs between the four operations.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationProfile:
    op_type: OperationType
    action_type: ActionType
    event_kind: EventKind
    style: str
    fallout_label: str
    requires_warrant: bool = False
    raises_awareness: int = 0
    grants_warrant: bool = False


_PROFILES: dict[OperationType, OperationProfile] = {
    OperationType.WARRANT: OperationProfile(
        op_type=OperationType.WARRANT,
        action_type=ActionType.REQUEST_WARRANT,
        event_kind=EventKind.REQUEST_WARRANT,
        style="analytical",
        fallout_label="warrant decision",
        grants_warrant=True,
    ),
    OperationType.STAKEOUT: OperationProfile(
        op_type=OperationType.STAKEOUT,
        action_type=ActionType.STAKEOUT,
        event_kind=EventKind.STAKEOUT,
        style="analytical",
        fallout_label="stakeout",
        raises_awareness=1,
    ),
    OperationType.BAIT: OperationProfile(
        op_type=OperationType.BAIT,
        action_type=ActionType.BAIT,
        event_kind=EventKind.BAIT,
        style="coercive",
        fallout_label="bait operation",
        raises_awareness=2,
    ),
    OperationType.RAID: OperationProfile(
        op_type=OperationType.RAID,
        action_type=ActionType.RAID,
        event_kind=EventKind.RAID,
        style="coercive",
        fallout_label="raid",
        requires_warrant=True,
        raises_awareness=2,
    ),
}


def profile_for(op_type: OperationType) -> OperationProfile:
    return _PROFILES[op_type]


# ---------------------------------------------------------------------------
# Stage 1: TRIGGER
# ---------------------------------------------------------------------------


def trigger(request: OperationRequest, ctx: OperationContext) -> TriggerResult:
    """Gate-keep the operation before any cost is paid.

    Order: hypothesis -> required warrants -> evidence packet ->
    probable-cause (warrants only) -> time/pressure cost.
    """

    profile = profile_for(request.op_type)
    base = TriggerResult(allowed=False, action_type=profile.action_type)

    if ctx.board.hypothesis is None:
        base.summary = _hypothesis_required_summary(request.op_type)
        return base

    if profile.requires_warrant and not _has_actionable_warrant(ctx.state):
        base.summary = WARRANT_REQUIRED_FOR_RAID
        return base

    if not request.evidence_ids:
        base.summary = _evidence_required_summary(request.op_type)
        if request.op_type == OperationType.WARRANT:
            base.summary = "Select supporting evidence before requesting a warrant."
        return base

    if request.op_type == OperationType.WARRANT:
        evidence_items = [
            item
            for item in ctx.presentation.evidence
            if item.id in set(request.evidence_ids)
        ]
        base.legal_check = evaluate_probable_cause(evidence_items, ctx.board.hypothesis)

    blocked, reason, time_cost, pressure_cost, coop_delta = _apply_cost(
        ctx.state, profile.action_type
    )
    if blocked:
        base.summary = reason
        return base

    return TriggerResult(
        allowed=True,
        summary="",
        action_type=profile.action_type,
        time_cost=time_cost,
        pressure_cost=pressure_cost,
        coop_delta=coop_delta,
        legal_check=base.legal_check,
    )


# ---------------------------------------------------------------------------
# Stage 2: PLAN
# ---------------------------------------------------------------------------


def plan(request: OperationRequest, ctx: OperationContext) -> OperationPlan:
    suspect_id = (
        ctx.board.hypothesis.suspect_id if ctx.board.hypothesis is not None else None
    )
    return OperationPlan(
        op_type=request.op_type,
        warrant_type=request.warrant_type,
        target_person_id=suspect_id,
        target_location_id=request.location_id,
        evidence_ids=list(request.evidence_ids),
    )


# ---------------------------------------------------------------------------
# Stage 3+4: EXECUTE -> OUTCOME
# ---------------------------------------------------------------------------


def execute(op_plan: OperationPlan, ctx: OperationContext) -> OperationOutcome:
    return resolve_operation(op_plan, ctx.presentation, ctx.board.hypothesis)


# ---------------------------------------------------------------------------
# Stage 5: FALLOUT
# ---------------------------------------------------------------------------


def fallout(
    outcome: OperationOutcome,
    request: OperationRequest,
    ctx: OperationContext,
) -> list[str]:
    """Apply state and world consequences. Returns the fallout note list."""

    profile = profile_for(request.op_type)
    notes: list[str] = []

    # Local state deltas.
    if outcome.pressure_delta:
        ctx.state.pressure = int(
            clamp(ctx.state.pressure + outcome.pressure_delta, 0, PRESSURE_LIMIT)
        )
    if outcome.trust_delta:
        ctx.state.trust = int(
            clamp(ctx.state.trust + outcome.trust_delta, 0, TRUST_LIMIT)
        )
    if outcome.pressure_delta > 0:
        notes.append(f"Pressure rises after the {profile.fallout_label}.")
    elif outcome.pressure_delta < 0:
        notes.append(f"Pressure eases after the {profile.fallout_label}.")
    if outcome.trust_delta > 0:
        notes.append("Trust improves after the operation.")
    elif outcome.trust_delta < 0:
        notes.append("Trust drops after the operation.")

    # Warrant grant on a successful warrant decision.
    if (
        profile.grants_warrant
        and request.warrant_type is not None
        and outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
    ):
        ctx.state.warrant_grants.add(request.warrant_type.value)

    # World-level nemesis awareness rises on visible / coercive moves.
    if ctx.world is not None and profile.raises_awareness:
        magnitude = profile.raises_awareness
        if outcome.tier == OperationTier.BURN:
            magnitude += 1
        ctx.world.raise_nemesis_awareness(magnitude)

    return notes


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_operation(
    request: OperationRequest,
    ctx: OperationContext,
    *,
    on_blocked: Callable[[ActionResult], None] | None = None,
) -> tuple[ActionResult, PipelineSnapshot]:
    """Run all five stages and return the final ActionResult + snapshot."""

    profile = profile_for(request.op_type)
    snapshot = PipelineSnapshot(
        op_type=request.op_type,
        trigger=TriggerResult(allowed=False, action_type=profile.action_type),
    )

    # Stage 1: Trigger.
    trig = trigger(request, ctx)
    snapshot.trigger = trig
    if not trig.allowed:
        blocked = ActionResult(
            action=trig.action_type,
            outcome=ActionOutcome.FAILURE,
            summary=trig.summary,
            time_cost=0,
            pressure_cost=0,
            cooperation_change=0.0,
        )
        if on_blocked:
            on_blocked(blocked)
        return blocked, snapshot

    _mark_style(ctx.state, profile.style)

    # Stage 2: Plan.
    op_plan = plan(request, ctx)
    snapshot.plan = op_plan

    # Stage 3 + 4: Execute -> Outcome.
    outcome = execute(op_plan, ctx)
    snapshot.outcome = outcome

    # Event log lives between execute and fallout so the world sees
    # the move before fallout is applied.
    if ctx.board.hypothesis is not None:
        apply_action(
            ctx.truth,
            profile.event_kind,
            ctx.state.time,
            request.location_id,
            participants=[ctx.board.hypothesis.suspect_id],
            metadata={"action": profile.action_type.value},
        )

    # Stage 5: Fallout.
    fallout_notes = fallout(outcome, request, ctx)
    snapshot.fallout_notes = fallout_notes

    notes = update_lead_statuses(ctx.state)
    notes.extend(outcome.notes)
    notes.extend(fallout_notes)

    action_outcome = (
        ActionOutcome.SUCCESS
        if outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}
        else ActionOutcome.FAILURE
    )
    return (
        ActionResult(
            action=profile.action_type,
            outcome=action_outcome,
            summary=outcome.summary,
            time_cost=trig.time_cost,
            pressure_cost=trig.pressure_cost,
            cooperation_change=trig.coop_delta,
            notes=notes,
            operation_type=request.op_type,
            operation_tier=outcome.tier,
        ),
        snapshot,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_actionable_warrant(state: InvestigationState) -> bool:
    return (
        WarrantType.ARREST.value in state.warrant_grants
        or WarrantType.SEARCH.value in state.warrant_grants
    )


HYPOTHESIS_REQUIRED_SUMMARY: dict[OperationType, str] = {
    OperationType.WARRANT: "Set a hypothesis before requesting a warrant.",
    OperationType.STAKEOUT: "Set a hypothesis before running a stakeout.",
    OperationType.BAIT: "Set a hypothesis before running a bait operation.",
    OperationType.RAID: "Set a hypothesis before running a raid.",
}

EVIDENCE_REQUIRED_SUMMARY: dict[OperationType, str] = {
    OperationType.WARRANT: "Select supporting evidence before requesting a warrant.",
    OperationType.STAKEOUT: "Select supporting evidence before running a stakeout.",
    OperationType.BAIT: "Select supporting evidence before running bait.",
    OperationType.RAID: "Select supporting evidence before running a raid.",
}

WARRANT_REQUIRED_FOR_RAID = "Raid requires an arrest or search warrant."


def _hypothesis_required_summary(op_type: OperationType) -> str:
    return HYPOTHESIS_REQUIRED_SUMMARY[op_type]


def _evidence_required_summary(op_type: OperationType) -> str:
    return EVIDENCE_REQUIRED_SUMMARY[op_type]
