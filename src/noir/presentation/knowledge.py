"""Player knowledge container for Phase 0."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known_evidence: list[UUID] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
