"""Investigation costs and limits for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActionType(StrEnum):
    VISIT_LOCATION = "visit_location"
    VISIT_SCENE = "visit_scene"
    INTERVIEW = "interview"
    FOLLOW_NEIGHBOR = "follow_neighbor"
    REQUEST_CCTV = "request_cctv"
    SUBMIT_FORENSICS = "submit_forensics"
    SET_HYPOTHESIS = "set_hypothesis"
    SET_PROFILE = "set_profile"
    ANALYST_ROSSMO = "analyst_rossmo"
    ANALYST_SWEEP = "analyst_sweep"
    REQUEST_WARRANT = "request_warrant"
    STAKEOUT = "stakeout"
    BAIT = "bait"
    RAID = "raid"
    ARREST = "arrest"


@dataclass(frozen=True)
class ActionCost:
    time: int
    pressure: int
    cooperation_delta: float = 0.0


TIME_LIMIT = 8
PRESSURE_LIMIT = 6

COSTS = {
    ActionType.VISIT_LOCATION: ActionCost(time=1, pressure=1),
    ActionType.VISIT_SCENE: ActionCost(time=1, pressure=0),
    ActionType.INTERVIEW: ActionCost(time=1, pressure=0, cooperation_delta=-0.05),
    ActionType.FOLLOW_NEIGHBOR: ActionCost(time=1, pressure=0, cooperation_delta=-0.05),
    ActionType.REQUEST_CCTV: ActionCost(time=1, pressure=1),
    ActionType.SUBMIT_FORENSICS: ActionCost(time=2, pressure=0),
    ActionType.SET_HYPOTHESIS: ActionCost(time=1, pressure=0),
    ActionType.SET_PROFILE: ActionCost(time=1, pressure=0),
    ActionType.ANALYST_ROSSMO: ActionCost(time=1, pressure=0),
    ActionType.ANALYST_SWEEP: ActionCost(time=1, pressure=1),
    ActionType.REQUEST_WARRANT: ActionCost(time=1, pressure=1),
    ActionType.STAKEOUT: ActionCost(time=2, pressure=1),
    ActionType.BAIT: ActionCost(time=2, pressure=2),
    ActionType.RAID: ActionCost(time=2, pressure=2),
    ActionType.ARREST: ActionCost(time=1, pressure=2),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def would_exceed_limits(time: int, pressure: int, cost: ActionCost) -> tuple[bool, str]:
    if time + cost.time > TIME_LIMIT:
        return True, "No time left for that action."
    if pressure + cost.pressure > PRESSURE_LIMIT:
        return True, "Institutional pressure is too high for that action."
    return False, ""
