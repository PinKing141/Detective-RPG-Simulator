"""Evidence models for Presentation."""

from __future__ import annotations

from typing import Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from noir.domain.enums import ConfidenceBand, EvidenceType


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    evidence_type: EvidenceType
    summary: str
    source: str
    time_collected: int
    confidence: ConfidenceBand


class WitnessStatement(EvidenceItem):
    witness_id: UUID
    statement: str
    reported_time_window: Tuple[int, int]
    location_id: UUID
    observed_person_ids: list[UUID] = Field(default_factory=list)


class CCTVReport(EvidenceItem):
    location_id: UUID
    observed_person_ids: list[UUID]
    time_window: Tuple[int, int]


class ForensicsResult(EvidenceItem):
    item_id: UUID
    finding: str
    method: str
    method_category: str


class PresentationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    seed: int
    evidence: list[EvidenceItem]
