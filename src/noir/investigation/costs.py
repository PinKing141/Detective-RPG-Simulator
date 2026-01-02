"""Investigation costs and limits for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActionType(StrEnum):
    VISIT_SCENE = "visit_scene"
    INTERVIEW = "interview"
    REQUEST_CCTV = "request_cctv"
    SUBMIT_FORENSICS = "submit_forensics"
    SET_HYPOTHESIS = "set_hypothesis"
    ARREST = "arrest"


@dataclass(frozen=True)
class ActionCost:
    time: int
    heat: int
    cooperation_delta: float = 0.0


TIME_LIMIT = 8
HEAT_LIMIT = 6

COSTS = {
    ActionType.VISIT_SCENE: ActionCost(time=1, heat=0),
    ActionType.INTERVIEW: ActionCost(time=1, heat=0, cooperation_delta=-0.05),
    ActionType.REQUEST_CCTV: ActionCost(time=1, heat=1),
    ActionType.SUBMIT_FORENSICS: ActionCost(time=2, heat=0),
    ActionType.SET_HYPOTHESIS: ActionCost(time=1, heat=0),
    ActionType.ARREST: ActionCost(time=1, heat=2),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def would_exceed_limits(time: int, heat: int, cost: ActionCost) -> tuple[bool, str]:
    if time + cost.time > TIME_LIMIT:
        return True, "No time left for that action."
    if heat + cost.heat > HEAT_LIMIT:
        return True, "Public heat is too high for that action."
    return False, ""
