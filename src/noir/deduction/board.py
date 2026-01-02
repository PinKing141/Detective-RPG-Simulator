"""Deduction board state for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from noir.investigation.results import InvestigationState


class ClaimType(StrEnum):
    PRESENCE = "presence"
    OPPORTUNITY = "opportunity"
    MOTIVE = "motive"
    BEHAVIOR = "behavior"


@dataclass(frozen=True)
class Hypothesis:
    suspect_id: UUID
    claims: list[ClaimType]
    evidence_ids: list[UUID]


@dataclass
class DeductionBoard:
    hypothesis: Hypothesis | None = None
    known_evidence_ids: list[UUID] = field(default_factory=list)

    def sync_from_state(self, state: InvestigationState) -> None:
        self.known_evidence_ids = list(state.knowledge.known_evidence)
