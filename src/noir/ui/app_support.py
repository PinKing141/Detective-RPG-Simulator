"""Pure formatting and parsing helpers for the Textual app."""

from __future__ import annotations

from typing import Any

from noir.cases.archetypes import CaseArchetype
from noir.deduction.board import ClaimType
from noir.investigation.interviews import InterviewApproach, InterviewTheme
from noir.investigation.operations import WarrantType
from noir.profiling.profile import ProfileDrive, ProfileMobility, ProfileOrganization


def format_claim(claim: ClaimType) -> str:
    mapping = {
        ClaimType.PRESENCE: "Present near the scene",
        ClaimType.OPPORTUNITY: "Opportunity during the time window",
        ClaimType.MOTIVE: "Motive linked to the victim",
        ClaimType.BEHAVIOR: "Behavior aligns with the crime",
    }
    return mapping.get(claim, claim.value)


def interview_approach_label(approach: InterviewApproach) -> str:
    mapping = {
        InterviewApproach.BASELINE: "Baseline (rapport)",
        InterviewApproach.PRESSURE: "Pressure (challenge)",
        InterviewApproach.THEME: "Motive framing",
    }
    return mapping.get(approach, approach.value)


def interview_theme_label(theme: InterviewTheme) -> str:
    mapping = {
        InterviewTheme.BLAME_VICTIM: "Blame the victim",
        InterviewTheme.CIRCUMSTANCE: "Blame the circumstances",
        InterviewTheme.ALTRUISTIC: "Altruistic motive",
        InterviewTheme.ACCIDENTAL: "Accidental outcome",
    }
    return mapping.get(theme, theme.value)


def profile_org_label(organization: ProfileOrganization) -> str:
    mapping = {
        ProfileOrganization.ORGANIZED: "Organized",
        ProfileOrganization.DISORGANIZED: "Disorganized",
        ProfileOrganization.MIXED: "Mixed",
        ProfileOrganization.UNKNOWN: "Unknown",
    }
    return mapping.get(organization, organization.value)


def profile_drive_label(drive: ProfileDrive) -> str:
    mapping = {
        ProfileDrive.VISIONARY: "Visionary",
        ProfileDrive.MISSION: "Mission-oriented",
        ProfileDrive.HEDONISTIC: "Hedonistic",
        ProfileDrive.POWER_CONTROL: "Power/Control",
        ProfileDrive.UNKNOWN: "Unknown",
    }
    return mapping.get(drive, drive.value)


def profile_mobility_label(mobility: ProfileMobility) -> str:
    mapping = {
        ProfileMobility.MARAUDER: "Marauder (local)",
        ProfileMobility.COMMUTER: "Commuter",
        ProfileMobility.UNKNOWN: "Unknown",
    }
    return mapping.get(mobility, mobility.value)


def warrant_label(warrant_type: WarrantType) -> str:
    mapping = {
        WarrantType.SEARCH: "Search warrant (property)",
        WarrantType.ARREST: "Arrest warrant (person)",
        WarrantType.DIGITAL: "Digital records warrant",
        WarrantType.SURVEILLANCE: "Surveillance authorization",
    }
    return mapping.get(warrant_type, warrant_type.value)


def format_hour(hour: int) -> str:
    value = hour % 24
    suffix = "am" if value < 12 else "pm"
    display = value % 12
    if display == 0:
        display = 12
    return f"{display}{suffix}"


def format_time_phrase(window: tuple[int, int]) -> str:
    start, end = window
    if start == end:
        return f"around {format_hour(start)}"
    return f"between {format_hour(start)} and {format_hour(end)}"


def format_confidence(confidence: Any) -> str:
    value = confidence.value if hasattr(confidence, "value") else str(confidence)
    mapping = {"strong": "High", "medium": "Medium", "weak": "Low"}
    return mapping.get(value, value.capitalize())


def parse_choice(value: str, count: int) -> int | None:
    if not value.isdigit():
        return None
    index = int(value) - 1
    if index < 0 or index >= count:
        return None
    return index


def parse_indices(value: str, items: list[Any]) -> list[Any]:
    indices: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        indices.append(int(part) - 1)
    selected: list[Any] = []
    for idx in indices:
        if 0 <= idx < len(items):
            selected.append(items[idx].id)
    return selected


def parse_multi_choice(value: str, count: int) -> list[int]:
    indices: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        index = int(part) - 1
        if 0 <= index < count:
            indices.append(index)
    return list(dict.fromkeys(indices))


def parse_case_archetype(value: str | CaseArchetype | None) -> CaseArchetype | None:
    if isinstance(value, CaseArchetype):
        return value
    if not value:
        return None
    for archetype in CaseArchetype:
        if archetype.value == value:
            return archetype
    return None