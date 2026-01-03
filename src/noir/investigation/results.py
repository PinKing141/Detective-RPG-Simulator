"""Result structures for investigation actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from noir.investigation.costs import ActionType
from noir.investigation.interviews import InterviewState
from noir.presentation.evidence import EvidenceItem
from noir.presentation.knowledge import KnowledgeState
from noir.locations.profiles import ScenePOI


class ActionOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    NO_EFFECT = "no_effect"


@dataclass
class InvestigationState:
    time: int = 0
    pressure: int = 0
    trust: int = 3
    cooperation: float = 1.0
    autonomy_marks: set[str] = field(default_factory=set)
    knowledge: KnowledgeState = field(default_factory=KnowledgeState)
    leads: list["Lead"] = field(default_factory=list)
    scene_pois: list[ScenePOI] = field(default_factory=list)
    visited_poi_ids: set[str] = field(default_factory=set)
    body_poi_id: str | None = None
    interviews: dict[str, InterviewState] = field(default_factory=dict)
    neighbor_leads: list["NeighborLead"] = field(default_factory=list)


if TYPE_CHECKING:
    from noir.investigation.leads import Lead
    from noir.investigation.leads import NeighborLead


@dataclass
class ActionResult:
    action: ActionType
    outcome: ActionOutcome
    summary: str
    time_cost: int
    pressure_cost: int
    cooperation_change: float
    revealed: list[EvidenceItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
