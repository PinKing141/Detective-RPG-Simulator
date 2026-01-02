"""Result structures for investigation actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.investigation.costs import ActionType
from noir.presentation.evidence import EvidenceItem
from noir.presentation.knowledge import KnowledgeState


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
    knowledge: KnowledgeState = field(default_factory=KnowledgeState)


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
