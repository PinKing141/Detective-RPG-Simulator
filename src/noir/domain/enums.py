"""Shared enums for domain and presentation."""

from __future__ import annotations

from enum import StrEnum


class RoleTag(StrEnum):
    VICTIM = "victim"
    SUSPECT = "suspect"
    WITNESS = "witness"
    OFFENDER = "offender"


class ItemType(StrEnum):
    WEAPON = "weapon"
    DOCUMENT = "document"
    PERSONAL = "personal"


class EventKind(StrEnum):
    APPROACH = "approach"
    CONFRONTATION = "confrontation"
    KILL = "kill"
    DISCOVERY = "discovery"
    INTERVIEW = "interview"
    INVESTIGATE_SCENE = "investigate_scene"
    REQUEST_CCTV = "request_cctv"
    SUBMIT_FORENSICS = "submit_forensics"
    ARREST = "arrest"


class EvidenceType(StrEnum):
    TESTIMONIAL = "testimonial"
    FORENSICS = "forensics"
    CCTV = "cctv"


class ConfidenceBand(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
