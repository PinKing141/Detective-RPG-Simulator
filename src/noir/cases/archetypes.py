"""Case archetype definitions for the showrunner."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CaseArchetype(StrEnum):
    BASELINE = "baseline"
    PRESSURE = "pressure"
    PATTERN = "pattern"
    CHARACTER = "character"
    FORESHADOWING = "foreshadowing"


class ModulatorName(StrEnum):
    COMPETENCE = "competence"
    RISK_TOLERANCE = "risk_tolerance"
    RELATIONSHIP_DISTANCE = "relationship_distance"
    PLANNING_LEVEL = "planning_level"
    PHYSICAL_CAPACITY = "physical_capacity"


PHASE0_MODULATORS = [
    ModulatorName.COMPETENCE,
    ModulatorName.RISK_TOLERANCE,
    ModulatorName.RELATIONSHIP_DISTANCE,
]


@dataclass(frozen=True)
class CaseProfile:
    archetype: CaseArchetype
    description: str
    visibility: int
    timer: int
    pressure: int


DEFAULT_ARCHETYPES = {
    CaseArchetype.PRESSURE: CaseProfile(
        archetype=CaseArchetype.PRESSURE,
        description="High visibility case with a short timer and low complexity.",
        visibility=3,
        timer=2,
        pressure=3,
    ),
    CaseArchetype.PATTERN: CaseProfile(
        archetype=CaseArchetype.PATTERN,
        description="False positive that copies Nemesis MO without signature.",
        visibility=2,
        timer=3,
        pressure=2,
    ),
    CaseArchetype.CHARACTER: CaseProfile(
        archetype=CaseArchetype.CHARACTER,
        description="Case centered on a high-affinity NPC for narrative depth.",
        visibility=1,
        timer=4,
        pressure=1,
    ),
    CaseArchetype.FORESHADOWING: CaseProfile(
        archetype=CaseArchetype.FORESHADOWING,
        description="Non-lethal or failed event hinting at a new MO.",
        visibility=2,
        timer=3,
        pressure=2,
    ),
}
