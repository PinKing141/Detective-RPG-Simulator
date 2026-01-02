"""Threshold checks for arrests in Phase 0."""

from __future__ import annotations

from dataclasses import dataclass

from noir.investigation.costs import PRESSURE_LIMIT
from noir.investigation.results import InvestigationState


@dataclass(frozen=True)
class ArrestAssessment:
    is_probable: bool
    explanation: list[str]


def evaluate_arrest(
    state: InvestigationState, min_evidence: int = 2, evidence_count: int | None = None
) -> ArrestAssessment:
    explanation: list[str] = []
    count = evidence_count if evidence_count is not None else len(state.knowledge.known_evidence)
    if count < min_evidence:
        explanation.append("Not enough evidence for probable cause.")
    if state.pressure > PRESSURE_LIMIT:
        explanation.append("Institutional pressure is too high to justify an arrest.")
    is_probable = count >= min_evidence and state.pressure <= PRESSURE_LIMIT
    if is_probable:
        explanation.append("Probable cause established.")
    return ArrestAssessment(is_probable=is_probable, explanation=explanation)
