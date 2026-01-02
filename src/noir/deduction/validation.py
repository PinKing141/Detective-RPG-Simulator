"""Deduction validation for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from noir.deduction.board import DeductionBoard, MethodType, TimeBucket
from noir.deduction.scoring import support_for_method, support_for_suspect
from noir.domain.enums import EventKind, RoleTag
from noir.investigation.results import InvestigationState
from noir.investigation.thresholds import evaluate_arrest
from noir.truth.graph import TruthState


@dataclass
class ValidationResult:
    is_correct_suspect: bool
    probable_cause: bool
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

    if not arrest_assessment.is_probable:
        summary = "Arrest fails probable cause."
    elif is_correct:
        summary = "Arrest holds. The case is likely to stick."
    else:
        summary = "Arrest collapses. The case is not supported."

    notes = list(arrest_assessment.explanation)
    if not is_correct and hypothesis.suspect_id:
        notes.append("The suspect does not match the case truth.")

    return ValidationResult(
        is_correct_suspect=is_correct,
        probable_cause=arrest_assessment.is_probable,
        summary=summary,
        supports=supports,
        missing=missing,
        notes=notes,
    )
