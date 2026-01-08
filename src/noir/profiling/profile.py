"""Working offender profile model (Phase 3+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from noir.domain.enums import EvidenceType
from noir.presentation.evidence import EvidenceItem


class ProfileOrganization(StrEnum):
    ORGANIZED = "organized"
    DISORGANIZED = "disorganized"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ProfileDrive(StrEnum):
    VISIONARY = "visionary"
    MISSION = "mission_oriented"
    HEDONISTIC = "hedonistic"
    POWER_CONTROL = "power_control"
    UNKNOWN = "unknown"


class ProfileMobility(StrEnum):
    MARAUDER = "marauder"
    COMMUTER = "commuter"
    UNKNOWN = "unknown"


@dataclass
class OffenderProfile:
    organization: ProfileOrganization = ProfileOrganization.UNKNOWN
    drive: ProfileDrive = ProfileDrive.UNKNOWN
    mobility: ProfileMobility = ProfileMobility.UNKNOWN
    evidence_ids: list[UUID] = field(default_factory=list)


_ORG_LABELS = {
    ProfileOrganization.ORGANIZED: "Organized",
    ProfileOrganization.DISORGANIZED: "Disorganized",
    ProfileOrganization.MIXED: "Mixed",
    ProfileOrganization.UNKNOWN: "Unknown",
}

_DRIVE_LABELS = {
    ProfileDrive.VISIONARY: "Visionary",
    ProfileDrive.MISSION: "Mission-oriented",
    ProfileDrive.HEDONISTIC: "Hedonistic",
    ProfileDrive.POWER_CONTROL: "Power/Control",
    ProfileDrive.UNKNOWN: "Unknown",
}

_MOBILITY_LABELS = {
    ProfileMobility.MARAUDER: "Marauder (local)",
    ProfileMobility.COMMUTER: "Commuter",
    ProfileMobility.UNKNOWN: "Unknown",
}


def format_profile_lines(
    profile: OffenderProfile | None,
    evidence_items: list[EvidenceItem] | None = None,
) -> list[str]:
    if profile is None:
        return ["(none)"]
    lines = [
        f"Organization: {_ORG_LABELS.get(profile.organization, profile.organization.value)}",
        f"Drive: {_DRIVE_LABELS.get(profile.drive, profile.drive.value)}",
        f"Mobility: {_MOBILITY_LABELS.get(profile.mobility, profile.mobility.value)}",
    ]
    if profile.evidence_ids:
        lines.append("Supporting evidence:")
        if evidence_items:
            id_set = set(profile.evidence_ids)
            matches = [item for item in evidence_items if item.id in id_set]
            if matches:
                for item in matches:
                    lines.append(f"- {item.summary}")
            else:
                lines.append(f"- {len(profile.evidence_ids)} items")
        else:
            lines.append(f"- {len(profile.evidence_ids)} items")
        if evidence_items:
            if matches:
                types = {item.evidence_type for item in matches}
                gaps: list[str] = []
                if EvidenceType.FORENSICS not in types:
                    gaps.append("No physical corroboration.")
                if EvidenceType.CCTV not in types:
                    gaps.append("No visual corroboration.")
                if EvidenceType.TESTIMONIAL not in types:
                    gaps.append("No testimonial support.")
                if gaps:
                    lines.append("Gaps:")
                    for gap in gaps:
                        lines.append(f"- {gap}")
            else:
                lines.append("Gaps:")
                lines.append("- (unknown)")
    return lines
