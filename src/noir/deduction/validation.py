"""Deduction validation for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import support_for_claims
from noir.domain.enums import RoleTag
from noir.investigation.results import InvestigationState
from noir.investigation.thresholds import evaluate_arrest
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.truth.graph import TruthState


class ArrestTier(StrEnum):
    CLEAN = "clean"
    SHAKY = "shaky"
    FAILED = "failed"


@dataclass
class ValidationResult:
    is_correct_suspect: bool
    probable_cause: bool
    tier: ArrestTier
    summary: str
    supports: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _offender_id(truth: TruthState) -> UUID | None:
    offenders = [p.id for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags]
    return offenders[0] if offenders else None


def _confidence_label(confidence) -> str:
    value = confidence.value if hasattr(confidence, "value") else str(confidence)
    return value


def _stronger_confidence(current: str | None, candidate: str) -> str:
    order = {"weak": 1, "medium": 2, "strong": 3}
    if current is None:
        return candidate
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def _append_unique(items: list[str], line: str) -> None:
    if line not in items:
        items.append(line)


def _evidence_class_confidence(presentation, evidence_ids) -> dict[str, str]:
    classes: dict[str, str] = {}
    for item in presentation.evidence:
        if item.id not in set(evidence_ids):
            continue
        if isinstance(item, (WitnessStatement, CCTVReport)):
            label = _confidence_label(item.confidence)
            classes["testimonial"] = _stronger_confidence(classes.get("testimonial"), label)
        if isinstance(item, ForensicsResult):
            label = _confidence_label(item.confidence)
            classes["physical"] = _stronger_confidence(classes.get("physical"), label)
    return classes


def _temporal_confidence(
    hypothesis,
    presentation,
    evidence_ids,
) -> str | None:
    if ClaimType.OPPORTUNITY not in set(hypothesis.claims):
        return None
    windows: list[tuple[int, int]] = []
    confidence: str | None = None
    suspect_placed = False
    for item in presentation.evidence:
        if item.id not in set(evidence_ids):
            continue
        if isinstance(item, WitnessStatement):
            windows.append(item.reported_time_window)
            confidence = _stronger_confidence(confidence, _confidence_label(item.confidence))
            if hypothesis.suspect_id in item.observed_person_ids:
                suspect_placed = True
        if isinstance(item, CCTVReport):
            windows.append(item.time_window)
            confidence = _stronger_confidence(confidence, _confidence_label(item.confidence))
            if hypothesis.suspect_id in item.observed_person_ids:
                suspect_placed = True

    if not windows or not suspect_placed:
        return None
    start = max(window[0] for window in windows)
    end = min(window[1] for window in windows)
    if start > end:
        return None
    if (end - start) > 2:
        return None
    return confidence or "medium"


def _arrest_tier(
    truth: TruthState,
    hypothesis,
    presentation,
    evidence_ids,
    is_correct: bool,
    temporal_confidence: str | None,
) -> tuple[ArrestTier, dict[str, str]]:
    if not is_correct:
        return ArrestTier.FAILED, {}
    classes = _evidence_class_confidence(presentation, evidence_ids)
    if temporal_confidence and "physical" in classes:
        # Temporal evidence becomes structural only when anchored by
        # non-testimonial corroboration.
        classes["temporal"] = temporal_confidence
    has_non_testimonial = "physical" in classes or "temporal" in classes
    has_weak = any(value == "weak" for value in classes.values())
    if len(classes) >= 2 and has_non_testimonial and not has_weak:
        return ArrestTier.CLEAN, classes
    if classes:
        return ArrestTier.SHAKY, classes
    return ArrestTier.FAILED, classes


def validate_hypothesis(
    truth: TruthState,
    board: DeductionBoard,
    presentation,
    state: InvestigationState,
) -> ValidationResult:
    if board.hypothesis is None:
        return ValidationResult(
            is_correct_suspect=False,
            probable_cause=False,
            tier=ArrestTier.FAILED,
            summary="No hypothesis submitted.",
            missing=["Submit a hypothesis before arrest."],
        )

    hypothesis = board.hypothesis
    arrest_assessment = evaluate_arrest(
        state, evidence_count=len(hypothesis.evidence_ids)
    )
    offender_id = _offender_id(truth)
    is_correct = offender_id is not None and hypothesis.suspect_id == offender_id

    claim_support = support_for_claims(
        presentation, hypothesis.evidence_ids, hypothesis.suspect_id, hypothesis.claims
    )
    supports = list(claim_support.supports)
    missing = list(claim_support.missing)

    temporal_confidence = _temporal_confidence(
        hypothesis, presentation, hypothesis.evidence_ids
    )
    tier, classes = _arrest_tier(
        truth,
        hypothesis,
        presentation,
        hypothesis.evidence_ids,
        is_correct,
        temporal_confidence,
    )
    if not arrest_assessment.is_probable:
        tier = ArrestTier.FAILED
    if "testimonial" in classes and "physical" not in classes and "temporal" not in classes:
        _append_unique(missing, "No physical corroboration anchors the account.")
    if "physical" in classes and "testimonial" not in classes:
        _append_unique(missing, "No testimonial evidence anchors the account.")
    if "temporal" in classes:
        _append_unique(supports, "Timeline forms a tight opportunity window.")
    elif temporal_confidence:
        _append_unique(
            missing,
            "Timeline is suggestive but unanchored without physical corroboration.",
        )
    else:
        _append_unique(missing, "Timeline is too broad to close opportunity.")
    if any(value == "weak" for value in classes.values()):
        _append_unique(missing, "One or more evidence classes are weak.")

    if tier == ArrestTier.CLEAN:
        summary = "Arrest holds. The case is likely to stick."
    elif tier == ArrestTier.SHAKY:
        summary = "Arrest is shaky. The case may not hold."
    else:
        summary = "Arrest collapses. The case is not supported."

    notes = list(arrest_assessment.explanation)
    return ValidationResult(
        is_correct_suspect=is_correct,
        probable_cause=arrest_assessment.is_probable,
        tier=tier,
        summary=summary,
        supports=supports,
        missing=missing,
        notes=notes,
    )
