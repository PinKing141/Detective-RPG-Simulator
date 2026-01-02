"""Deduction validation for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from noir.deduction.board import DeductionBoard, MethodType, TimeBucket
from noir.deduction.scoring import support_for_method, support_for_suspect
from noir.domain.enums import EventKind, RoleTag
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


def _truth_method(truth: TruthState) -> str | None:
    kill_events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    if not kill_events:
        return None
    event = sorted(kill_events, key=lambda e: e.timestamp)[0]
    return event.metadata.get("method_category")


def _truth_time_bucket(truth: TruthState) -> TimeBucket | None:
    kill_events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    if not kill_events:
        return None
    timestamp = sorted(kill_events, key=lambda e: e.timestamp)[0].timestamp
    hour = timestamp % 24
    if 5 <= hour < 12:
        return TimeBucket.MORNING
    if 12 <= hour < 17:
        return TimeBucket.AFTERNOON
    if 17 <= hour < 21:
        return TimeBucket.EVENING
    return TimeBucket.MIDNIGHT


def _confidence_label(confidence) -> str:
    value = confidence.value if hasattr(confidence, "value") else str(confidence)
    return value


def _stronger_confidence(current: str | None, candidate: str) -> str:
    order = {"weak": 1, "medium": 2, "strong": 3}
    if current is None:
        return candidate
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


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


def _arrest_tier(
    truth: TruthState,
    hypothesis,
    presentation,
    evidence_ids,
    is_correct: bool,
) -> tuple[ArrestTier, dict[str, str]]:
    if not is_correct:
        return ArrestTier.FAILED, {}
    classes = _evidence_class_confidence(presentation, evidence_ids)
    truth_bucket = _truth_time_bucket(truth)
    if truth_bucket and truth_bucket == hypothesis.time_bucket:
        # Temporal support counts only if corroborated by physical evidence in Phase 1.
        if "physical" in classes and "testimonial" in classes:
            classes["temporal"] = classes.get("testimonial", "medium")
    has_physical = "physical" in classes
    has_weak = any(value == "weak" for value in classes.values())
    if len(classes) >= 2 and has_physical and not has_weak:
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

    suspect_support = support_for_suspect(
        presentation, hypothesis.evidence_ids, hypothesis.suspect_id
    )
    method_support = support_for_method(
        presentation, hypothesis.evidence_ids, hypothesis.method
    )

    supports = suspect_support.supports + method_support.supports
    missing = suspect_support.missing + method_support.missing

    truth_method = _truth_method(truth)
    if hypothesis.method != MethodType.UNKNOWN:
        if truth_method and truth_method == hypothesis.method.value:
            supports.append("Method matches the case truth.")
        elif truth_method:
            missing.append("Method does not fit the case truth.")

    truth_bucket = _truth_time_bucket(truth)
    if truth_bucket and truth_bucket == hypothesis.time_bucket:
        supports.append("Time window matches the case timeline.")
    elif truth_bucket:
        missing.append("Time window does not match the case timeline.")

    tier, classes = _arrest_tier(truth, hypothesis, presentation, hypothesis.evidence_ids, is_correct)
    if not arrest_assessment.is_probable:
        tier = ArrestTier.FAILED
    if "testimonial" in classes and "physical" not in classes:
        missing.append("No physical corroboration supports the arrest.")
    if "physical" in classes and "testimonial" not in classes:
        missing.append("No testimonial evidence anchors the narrative.")
    if any(value == "weak" for value in classes.values()):
        missing.append("One or more evidence classes are weak.")

    if tier == ArrestTier.CLEAN:
        summary = "Arrest holds. The case is likely to stick."
    elif tier == ArrestTier.SHAKY:
        summary = "Arrest is shaky. The case may not hold."
    else:
        summary = "Arrest collapses. The case is not supported."

    notes = list(arrest_assessment.explanation)
    if not is_correct and hypothesis.suspect_id:
        notes.append("The suspect does not match the case truth.")

    return ValidationResult(
        is_correct_suspect=is_correct,
        probable_cause=arrest_assessment.is_probable,
        tier=tier,
        summary=summary,
        supports=supports,
        missing=missing,
        notes=notes,
    )
