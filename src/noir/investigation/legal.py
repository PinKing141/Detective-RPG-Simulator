"""Legal / probable-cause checks for the operation pipeline.

This module owns the rigor that keeps the detective fantasy honest:
a warrant must have enough corroborated support before a judge will
grant it, and the rules are the same whether the player or a test
asks. The checks here are pure functions; they read the evidence
packet and the working hypothesis and return a structured verdict
with the *reasons* attached so the UI can show the player why a
request held or failed.
"""

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


class ProbableCause(StrEnum):
    """Three-band verdict on whether the packet meets probable cause."""

    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class LegalCheck:
    verdict: ProbableCause
    reasons: list[str] = field(default_factory=list)
    supports_count: int = 0
    has_physical: bool = False
    timeline_ok: bool = False


def evaluate_probable_cause(
    evidence_items: list[EvidenceItem],
    hypothesis: "Hypothesis | None",
) -> LegalCheck:
    """Run the warrant-grade probable cause check on a packet.

    The thresholds mirror the legacy warrant resolver so existing
    tier outcomes are preserved.
    """

    if len(evidence_items) < 2:
        return LegalCheck(
            verdict=ProbableCause.INSUFFICIENT,
            reasons=["Packet needs at least two corroborating supports."],
            supports_count=len(evidence_items),
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
            return LegalCheck(
                verdict=ProbableCause.LIMITED,
                reasons=["Mixed support — scope will be narrowed."],
                supports_count=len(evidence_items),
                has_physical=True,
                timeline_ok=timeline_ok,
            )
        return LegalCheck(
            verdict=ProbableCause.SUFFICIENT,
            reasons=["Physical corroboration anchors the packet."],
            supports_count=len(evidence_items),
            has_physical=True,
            timeline_ok=timeline_ok,
        )

    if len(testimonial) >= 2 and timeline_ok:
        return LegalCheck(
            verdict=ProbableCause.LIMITED,
            reasons=[
                "Support rests on testimony with a coherent timeline.",
                "Scope will be limited.",
            ],
            supports_count=len(evidence_items),
            has_physical=False,
            timeline_ok=True,
        )

    reasons = ["Testimonial support is not sufficiently corroborated."]
    if timeline_note:
        reasons.append(timeline_note)
    return LegalCheck(
        verdict=ProbableCause.INSUFFICIENT,
        reasons=reasons,
        supports_count=len(evidence_items),
        has_physical=False,
        timeline_ok=False,
    )


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
