"""Deduction board state for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from noir.investigation.results import InvestigationState


class MethodType(StrEnum):
    SHARP = "sharp"
    BLUNT = "blunt"
    POISON = "poison"
    UNKNOWN = "unknown"


class TimeBucket(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    MIDNIGHT = "midnight"


@dataclass(frozen=True)
class Hypothesis:
    suspect_id: UUID
    method: MethodType
    time_bucket: TimeBucket
    evidence_ids: list[UUID]


@dataclass
class DeductionBoard:
    hypothesis: Hypothesis | None = None
    known_evidence_ids: list[UUID] = field(default_factory=list)

    def sync_from_state(self, state: InvestigationState) -> None:
        self.known_evidence_ids = list(state.knowledge.known_evidence)
