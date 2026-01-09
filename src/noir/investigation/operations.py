"""Operation framework for Phase 4 endgame actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from noir.domain.enums import ConfidenceBand
from noir.presentation.evidence import (
    CCTVReport,
    EvidenceItem,
    ForensicObservation,
    ForensicsResult,
    WitnessStatement,
)

if TYPE_CHECKING:
    from noir.deduction.board import Hypothesis


class OperationType(StrEnum):
    WARRANT = "warrant"
    STAKEOUT = "stakeout"
    BAIT = "bait"
    RAID = "raid"


class WarrantType(StrEnum):
    SEARCH = "search"
    ARREST = "arrest"
    DIGITAL = "digital"
    SURVEILLANCE = "surveillance"


class OperationTier(StrEnum):
    CLEAN = "clean"
    PARTIAL = "partial"
    FAILED = "failed"
    BURN = "burn"


@dataclass
class OperationPlan:
    op_type: OperationType
    warrant_type: WarrantType | None = None
    target_person_id: UUID | None = None
    target_location_id: UUID | None = None
    evidence_ids: list[UUID] = field(default_factory=list)


@dataclass
class OperationOutcome:
    tier: OperationTier
    summary: str
    notes: list[str] = field(default_factory=list)
    pressure_delta: int = 0
    trust_delta: int = 0
    spook_delta: int = 0


def resolve_operation(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None = None,
) -> OperationOutcome:
    if plan.op_type == OperationType.WARRANT:
        return _resolve_warrant(plan, presentation, hypothesis)
    if plan.op_type == OperationType.STAKEOUT:
        return _resolve_stakeout(plan, presentation, hypothesis)
    if plan.op_type == OperationType.BAIT:
        return _resolve_bait(plan, presentation, hypothesis)
    if plan.op_type == OperationType.RAID:
        return _resolve_raid(plan, presentation, hypothesis)
    return OperationOutcome(
        tier=OperationTier.FAILED,
        summary="Operation not available yet.",
        notes=["Operations beyond warrants are not online."],
    )


def _resolve_warrant(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None,
) -> OperationOutcome:
    evidence_items = _collect_evidence(presentation, plan.evidence_ids)
    if len(evidence_items) < 2:
        return OperationOutcome(
            tier=OperationTier.FAILED,
            summary="Warrant denied. The packet is too thin.",
            notes=["Provide at least two corroborating supports."],
            pressure_delta=1,
            trust_delta=-1,
        )

    testimonial = [item for item in evidence_items if _is_testimonial(item)]
    physical = [item for item in evidence_items if _is_physical(item)]
    has_weak = any(item.confidence == ConfidenceBand.WEAK for item in evidence_items)

    timeline_ok, timeline_note = _timeline_coherent(
        testimonial,
        hypothesis.suspect_id if hypothesis else None,
    )

    if physical:
        if has_weak:
            return OperationOutcome(
                tier=OperationTier.PARTIAL,
                summary="Warrant granted with limits.",
                notes=["Support is mixed; scope is narrowed."],
                pressure_delta=1,
            )
        return OperationOutcome(
            tier=OperationTier.CLEAN,
            summary="Warrant granted.",
            notes=["Support meets probable cause standards."],
        )

    if len(testimonial) >= 2 and timeline_ok:
        notes = [
            "Support relies on testimony and a coherent timeline.",
            "Scope is likely to be limited.",
        ]
        return OperationOutcome(
            tier=OperationTier.PARTIAL,
            summary="Warrant granted with limits.",
            notes=notes,
            pressure_delta=1,
        )

    notes = ["Testimonial support is not sufficiently corroborated."]
    if timeline_note:
        notes.append(timeline_note)
    return OperationOutcome(
        tier=OperationTier.FAILED,
        summary="Warrant denied. Support is insufficient.",
        notes=notes,
        pressure_delta=1,
        trust_delta=-1,
    )


def _resolve_stakeout(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None,
) -> OperationOutcome:
    evidence_items, testimonial, physical, has_weak, timeline_ok, timeline_note = (
        _evidence_mix(plan, presentation, hypothesis)
    )
    if not evidence_items:
        return OperationOutcome(
            tier=OperationTier.FAILED,
            summary="Stakeout yields no contact.",
            notes=["No actionable lead anchored the surveillance."],
            pressure_delta=1,
        )
    if physical and timeline_ok:
        notes = ["Observation confirms the suspected window."]
        return OperationOutcome(
            tier=OperationTier.CLEAN,
            summary="Stakeout yields a clear contact.",
            notes=notes,
            pressure_delta=0,
        )
    if physical or timeline_ok:
        notes = ["Observation confirms partial activity near the window."]
        if timeline_note:
            notes.append(timeline_note)
        return OperationOutcome(
            tier=OperationTier.PARTIAL,
            summary="Stakeout yields partial confirmation.",
            notes=notes,
            pressure_delta=1,
        )
    notes = ["No corroboration beyond testimonial cues."]
    if has_weak:
        notes.append("Support is weak; surveillance windows drift.")
    return OperationOutcome(
        tier=OperationTier.FAILED,
        summary="Stakeout produces no useful contact.",
        notes=notes,
        pressure_delta=1,
    )


def _resolve_bait(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None,
) -> OperationOutcome:
    evidence_items, testimonial, physical, has_weak, timeline_ok, timeline_note = (
        _evidence_mix(plan, presentation, hypothesis)
    )
    if not evidence_items:
        return OperationOutcome(
            tier=OperationTier.FAILED,
            summary="Bait fails to draw a response.",
            notes=["The bait lacked a credible hook."],
            pressure_delta=2,
            trust_delta=-1,
            spook_delta=1,
        )
    if physical and timeline_ok and not has_weak:
        return OperationOutcome(
            tier=OperationTier.CLEAN,
            summary="Bait draws a clean contact.",
            notes=["The response aligns with the working profile."],
            pressure_delta=1,
            spook_delta=1,
        )
    if physical or timeline_ok:
        notes = ["The bait draws a near miss, not a commitment."]
        if timeline_note:
            notes.append(timeline_note)
        if has_weak:
            notes.append("Support is thin; expect pushback.")
        return OperationOutcome(
            tier=OperationTier.PARTIAL,
            summary="Bait draws a near miss.",
            notes=notes,
            pressure_delta=1,
            spook_delta=1,
        )
    return OperationOutcome(
        tier=OperationTier.BURN,
        summary="Bait backfires; the target withdraws.",
        notes=["The setup was too visible; the trail cools."],
        pressure_delta=2,
        trust_delta=-1,
        spook_delta=2,
    )


def _resolve_raid(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None,
) -> OperationOutcome:
    evidence_items, testimonial, physical, has_weak, timeline_ok, timeline_note = (
        _evidence_mix(plan, presentation, hypothesis)
    )
    if not evidence_items:
        return OperationOutcome(
            tier=OperationTier.FAILED,
            summary="Raid falls flat.",
            notes=["No corroboration anchored the target."],
            pressure_delta=2,
            trust_delta=-1,
        )
    if physical and not has_weak:
        return OperationOutcome(
            tier=OperationTier.CLEAN,
            summary="Raid hits clean.",
            notes=["Evidence and access align with the plan."],
            pressure_delta=0,
        )
    if physical:
        notes = ["Raid hits, but the proof is thin."]
        if has_weak:
            notes.append("Key supports are weak.")
        return OperationOutcome(
            tier=OperationTier.PARTIAL,
            summary="Raid hits with thin support.",
            notes=notes,
            pressure_delta=1,
        )
    if timeline_ok and testimonial:
        notes = ["Timeline holds, but physical proof is missing."]
        if timeline_note:
            notes.append(timeline_note)
        return OperationOutcome(
            tier=OperationTier.PARTIAL,
            summary="Raid hits on a narrow read.",
            notes=notes,
            pressure_delta=1,
            trust_delta=-1,
        )
    return OperationOutcome(
        tier=OperationTier.BURN,
        summary="Raid hits the wrong target.",
        notes=["Insufficient corroboration; fallout is immediate."],
        pressure_delta=2,
        trust_delta=-2,
        spook_delta=2,
    )


def _collect_evidence(presentation, evidence_ids: list[UUID]) -> list[EvidenceItem]:
    id_set = set(evidence_ids)
    return [item for item in presentation.evidence if item.id in id_set]


def _is_testimonial(item: EvidenceItem) -> bool:
    return isinstance(item, (WitnessStatement, CCTVReport))


def _is_physical(item: EvidenceItem) -> bool:
    return isinstance(item, (ForensicObservation, ForensicsResult))


def _timeline_coherent(
    testimonial_items: list[EvidenceItem],
    suspect_id: UUID | None,
) -> tuple[bool, str | None]:
    if suspect_id is None:
        return False, "No suspect anchored to the timeline."
    windows: list[tuple[int, int]] = []
    for item in testimonial_items:
        if isinstance(item, WitnessStatement):
            if suspect_id in item.observed_person_ids:
                windows.append(item.reported_time_window)
        elif isinstance(item, CCTVReport):
            if suspect_id in item.observed_person_ids:
                windows.append(item.time_window)
    if len(windows) < 2:
        return False, "Timeline needs two independent sources."
    start = max(window[0] for window in windows)
    end = min(window[1] for window in windows)
    if start > end:
        return False, "Temporal sources conflict."
    if (end - start) > 2:
        return False, "Timeline window is too broad."
    return True, None


def _evidence_mix(
    plan: OperationPlan,
    presentation,
    hypothesis: Hypothesis | None,
) -> tuple[
    list[EvidenceItem],
    list[EvidenceItem],
    list[EvidenceItem],
    bool,
    bool,
    str | None,
]:
    evidence_items = _collect_evidence(presentation, plan.evidence_ids)
    testimonial = [item for item in evidence_items if _is_testimonial(item)]
    physical = [item for item in evidence_items if _is_physical(item)]
    has_weak = any(item.confidence == ConfidenceBand.WEAK for item in evidence_items)
    timeline_ok, timeline_note = _timeline_coherent(
        testimonial, hypothesis.suspect_id if hypothesis else None
    )
    return evidence_items, testimonial, physical, has_weak, timeline_ok, timeline_note
