"""Project Truth into player-facing evidence."""

from __future__ import annotations

from typing import List

from noir.domain.enums import ConfidenceBand, EvidenceType, EventKind, ItemType, RoleTag
from noir.presentation.evidence import CCTVReport, ForensicsResult, PresentationCase, WitnessStatement
from noir.presentation.erosion import confidence_from_window, fuzz_time, maybe_omit
from noir.truth.graph import TruthState
from noir.util.rng import Rng


def _float_trait(person, key: str, default: float) -> float:
    if person is None:
        return default
    value = person.traits.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _relationship_distance(person) -> str:
    if person is None:
        return "stranger"
    value = person.traits.get("relationship_distance", "stranger")
    return str(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _format_hour(hour: int) -> str:
    value = hour % 24
    suffix = "am" if value < 12 else "pm"
    display = value % 12
    if display == 0:
        display = 12
    return f"{display}{suffix}"


def _format_time_phrase(window: tuple[int, int]) -> str:
    start, end = window
    if start == end:
        return f"around {_format_hour(start)}"
    return f"between {_format_hour(start)} and {_format_hour(end)}"


def _method_category_from_item(name: str) -> str:
    lowered = name.lower()
    if "poison" in lowered:
        return "poison"
    if "blunt" in lowered or "bat" in lowered or "hammer" in lowered:
        return "blunt"
    return "sharp"


def project_case(truth: TruthState, rng: Rng) -> PresentationCase:
    evidence: List = []

    kill_events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    if not kill_events:
        return PresentationCase(case_id=truth.case_id, seed=truth.seed, evidence=[])
    kill_event = sorted(kill_events, key=lambda e: e.timestamp)[0]

    location = truth.locations.get(kill_event.location_id)
    cctv_available = bool(location and "cctv" in location.tags)

    offender = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    competence = _float_trait(offender, "competence", 0.5)
    risk_tolerance = _float_trait(offender, "risk_tolerance", 0.5)
    relationship_distance = _relationship_distance(offender)

    witness = next(
        (person for person in truth.people.values() if RoleTag.WITNESS in person.role_tags),
        None,
    )
    if witness:
        if relationship_distance == "intimate":
            sigma = 3.0
        elif relationship_distance == "acquaintance":
            sigma = 2.0
        else:
            sigma = 1.5
        time_window = fuzz_time(kill_event.timestamp, sigma=sigma, rng=rng)
        confidence = confidence_from_window(time_window)
        observed_person_ids = []
        if offender:
            if not cctv_available:
                observed_person_ids.append(offender.id)
            elif risk_tolerance >= 0.5 and rng.random() > 0.2:
                observed_person_ids.append(offender.id)
        location_name = location.name if location else "the building"
        heard_prefix = "I think I heard" if confidence == ConfidenceBand.WEAK else "I heard"
        saw_prefix = "I think I saw" if confidence == ConfidenceBand.WEAK else "I saw"
        statement = f"{heard_prefix} a struggle near the {location_name}."
        if offender and observed_person_ids:
            statement = f"{saw_prefix} {offender.name} outside the {location_name}."
        evidence.append(
            WitnessStatement(
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source=witness.name,
                time_collected=kill_event.timestamp + 1,
                confidence=confidence,
                witness_id=witness.id,
                statement=statement,
                reported_time_window=time_window,
                location_id=kill_event.location_id,
                observed_person_ids=observed_person_ids,
            )
        )

    cctv_omit = _clamp(0.6 - (risk_tolerance * 0.4), 0.1, 0.7)
    cctv_added = False
    if cctv_available and not maybe_omit(cctv_omit, rng):
        evidence.append(
            CCTVReport(
                evidence_type=EvidenceType.CCTV,
                summary="CCTV report",
                source="Traffic Control",
                time_collected=kill_event.timestamp + 1,
                confidence=ConfidenceBand.STRONG,
                location_id=kill_event.location_id,
                observed_person_ids=list(kill_event.participants),
                time_window=(kill_event.timestamp - 1, kill_event.timestamp + 1),
            )
        )
        cctv_added = True

    weapon_items = [item for item in truth.items.values() if item.item_type == ItemType.WEAPON]
    forensics_added = False
    for item in weapon_items:
        forensics_omit = _clamp(0.1 + (competence * 0.6), 0.1, 0.8)
        if maybe_omit(forensics_omit, rng):
            continue
        method_category = _method_category_from_item(item.name)
        evidence.append(
            ForensicsResult(
                evidence_type=EvidenceType.FORENSICS,
                summary="Forensics result",
                source="Forensics Lab",
                time_collected=kill_event.timestamp + 2,
                confidence=ConfidenceBand.MEDIUM,
                item_id=item.id,
                finding=f"Trace evidence consistent with {item.name}.",
                method="trace",
                method_category=method_category,
            )
        )
        forensics_added = True
        break

    if not cctv_added and not forensics_added:
        if cctv_available:
            evidence.append(
                CCTVReport(
                    evidence_type=EvidenceType.CCTV,
                    summary="CCTV report (partial)",
                    source="Traffic Control",
                    time_collected=kill_event.timestamp + 1,
                    confidence=ConfidenceBand.WEAK,
                    location_id=kill_event.location_id,
                    observed_person_ids=list(kill_event.participants),
                    time_window=(kill_event.timestamp - 2, kill_event.timestamp + 2),
                )
            )
        elif weapon_items:
            item = weapon_items[0]
            method_category = _method_category_from_item(item.name)
            evidence.append(
                ForensicsResult(
                    evidence_type=EvidenceType.FORENSICS,
                    summary="Forensics result (partial)",
                    source="Forensics Lab",
                    time_collected=kill_event.timestamp + 2,
                    confidence=ConfidenceBand.WEAK,
                    item_id=item.id,
                    finding=f"Partial trace evidence consistent with {item.name}.",
                    method="trace",
                    method_category=method_category,
                )
            )

    return PresentationCase(case_id=truth.case_id, seed=truth.seed, evidence=evidence)
