"""Case outcome tracking for Phase 1 consequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.deduction.validation import ArrestTier, ValidationResult
from noir.investigation.costs import PRESSURE_LIMIT, clamp
from noir.investigation.results import InvestigationState


class ArrestResult(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    WRONG = "wrong"


@dataclass(frozen=True)
class CaseOutcome:
    arrest_result: ArrestResult
    trust_delta: int
    pressure_delta: int
    notes: list[str] = field(default_factory=list)


TRUST_LIMIT = 6


def resolve_case_outcome(validation: ValidationResult) -> CaseOutcome:
    if validation.is_correct_suspect and validation.tier == ArrestTier.CLEAN:
        return CaseOutcome(
            arrest_result=ArrestResult.SUCCESS,
            trust_delta=1,
            pressure_delta=-1,
            notes=["Command is satisfied with the charge."],
        )
    if validation.is_correct_suspect and validation.tier == ArrestTier.SHAKY:
        return CaseOutcome(
            arrest_result=ArrestResult.PARTIAL,
            trust_delta=0,
            pressure_delta=1,
            notes=["The case is right, but the support is thin."],
        )
    if not validation.is_correct_suspect:
        return CaseOutcome(
            arrest_result=ArrestResult.WRONG,
            trust_delta=-2,
            pressure_delta=5,
            notes=[
                "Wrong person charged. The real offender is still out there.",
                "Command is calling for an internal review.",
                "An innocent person just lost their freedom.",
            ],
        )
    # Correct suspect but no probable cause — case collapses at charge
    return CaseOutcome(
        arrest_result=ArrestResult.FAILED,
        trust_delta=-1,
        pressure_delta=3,
        notes=["Right target, but the case won't hold. The charge collapses."],
    )


def apply_case_outcome(state: InvestigationState, outcome: CaseOutcome) -> InvestigationState:
    trust = int(clamp(state.trust + outcome.trust_delta, 0, TRUST_LIMIT))
    pressure = int(clamp(state.pressure + outcome.pressure_delta, 0, PRESSURE_LIMIT))
    return InvestigationState(time=0, pressure=pressure, trust=trust)
