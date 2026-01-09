"""Project Truth into player-facing evidence."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from noir.domain.enums import ConfidenceBand, EvidenceType, EventKind, ItemType, RoleTag
from noir.presentation.evidence import (
    CCTVReport,
    ForensicObservation,
    ForensicsResult,
    PresentationCase,
    WitnessStatement,
)
from noir.presentation.erosion import confidence_from_window, fuzz_time, maybe_omit
from noir.truth.graph import TruthState
from noir.util.grammar import place_with_article
from noir.util.rng import Rng
from noir.locations.profiles import load_location_profiles


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


def _poi_name(poi_id: str) -> str:
    parts = poi_id.split(":")
    if len(parts) >= 2:
        return parts[1]
    return poi_id


_LOG_POI_NAMES = {
    "logbook",
    "register",
    "receipt_bin",
    "badge_gate",
    "reader",
    "turnstile",
    "ticket_machine",
    "reception",
    "front_office",
    "front_desk",
    "desk",
    "monitor",
    "security_desk",
    "cashier",
    "till",
    "mail_area",
    "gate",
    "entry_gate",
}

_CCTV_POI_NAMES = {
    "monitor",
    "security_desk",
    "reception",
    "front_office",
    "front_desk",
}


def _is_log_poi(poi_id: str, tags: list[str]) -> bool:
    name = _poi_name(poi_id)
    if name in _LOG_POI_NAMES:
        return True
    if "security" in tags or "service" in tags:
        return True
    return False


def _is_cctv_poi(poi_id: str, tags: list[str]) -> bool:
    name = _poi_name(poi_id)
    if name in _CCTV_POI_NAMES:
        return True
    if "security" in tags:
        return True
    return False


def _method_category_from_item(name: str) -> str:
    lowered = name.lower()
    if "poison" in lowered:
        return "poison"
    if "blunt" in lowered or "bat" in lowered or "hammer" in lowered:
        return "blunt"
    return "sharp"


def _time_bucket(hour: int) -> str:
    value = hour % 24
    if 5 <= value < 12:
        return "morning"
    if 12 <= value < 17:
        return "afternoon"
    if 17 <= value < 21:
        return "evening"
    return "midnight"


def _downgrade(confidence: ConfidenceBand) -> ConfidenceBand:
    if confidence == ConfidenceBand.STRONG:
        return ConfidenceBand.MEDIUM
    if confidence == ConfidenceBand.MEDIUM:
        return ConfidenceBand.WEAK
    return confidence


def _weighted_choice(rng: Rng, options: dict[str, float]) -> str | None:
    if not options:
        return None
    total = sum(max(0.0, value) for value in options.values())
    if total <= 0:
        return rng.choice(list(options.keys()))
    pick = rng.random() * total
    cumulative = 0.0
    for key, weight in options.items():
        cumulative += max(0.0, weight)
        if pick <= cumulative:
            return key
    return next(iter(options.keys()))


def _uuid_from(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _pattern_plan(truth: TruthState) -> dict[str, Any] | None:
    plan = truth.case_meta.get("pattern_plan")
    if isinstance(plan, dict):
        return plan
    return None


def _article_for(value: str) -> str:
    if not value:
        return "A"
    return "An" if value[0].lower() in "aeiou" else "A"


def _pattern_confidence(observation: dict[str, str] | None) -> ConfidenceBand:
    confidence = ConfidenceBand.MEDIUM
    if not observation:
        return confidence
    if observation.get("token_status") in {"Ambiguous", "Absent"}:
        confidence = _downgrade(confidence)
    if observation.get("staging_status") in {"Inconsistent", "Unknown"}:
        confidence = _downgrade(confidence)
    if observation.get("message_status") in {"Altered", "Absent"}:
        confidence = _downgrade(confidence)
    return confidence


def _pattern_primary_observation(
    motif: dict[str, Any],
    observation: dict[str, str] | None,
) -> str:
    token = motif.get("token") or motif.get("name") or "detail"
    staging = motif.get("staging")
    style = motif.get("style")
    message = motif.get("message")
    category = motif.get("category")
    if category == "linguistic_signature":
        if style:
            text = f"{_article_for(token)} {token} follows a {style} pattern."
        else:
            text = f"{_article_for(token)} {token} is present at the scene."
    elif staging:
        text = f"{_article_for(token)} {token} is noted {staging}."
    else:
        text = f"{_article_for(token)} {token} is noted at the scene."
    if message and observation and observation.get("message_status") in {"Present", "Altered"}:
        if observation.get("message_status") == "Altered":
            text = f"{text} The wording is incomplete but reads: {message}"
        else:
            text = f"{text} A note reads: {message}"
    return text


def _pattern_support_observation(motif: dict[str, Any]) -> str:
    trace = motif.get("trace") or motif.get("name") or "trace detail"
    return f"Trace suggests {trace}."


def _pattern_poi_id(
    category: str | None,
    body_poi_id: str | None,
    entry_poi_id: str | None,
    non_body_poi_ids: list[str],
    rng: Rng,
) -> str | None:
    candidates: list[str] = []
    if category == "linguistic_signature":
        candidates = [poi for poi in non_body_poi_ids if poi]
        if not candidates and entry_poi_id:
            candidates = [entry_poi_id]
    else:
        candidates.extend([poi for poi in (body_poi_id, entry_poi_id) if poi])
        candidates.extend([poi for poi in non_body_poi_ids if poi])
    if not candidates:
        return body_poi_id or entry_poi_id
    return rng.choice(candidates)


def _rigor_stage(hours_since: int) -> str:
    if hours_since <= 3:
        return "Rigor is beginning."
    if hours_since <= 8:
        return "Rigor is established."
    return "Rigor is fading."


def _tod_sigma(tags: list[str]) -> float:
    sigma = 1.5
    if "outdoor" in tags or "open" in tags:
        sigma += 0.9
    if "transit" in tags:
        sigma += 0.5
    if "nightlife" in tags or "roadside" in tags:
        sigma += 0.4
    if "industrial" in tags or "service" in tags:
        sigma += 0.5
    if "commercial" in tags:
        sigma += 0.2
    if "public" in tags:
        sigma += 0.3
    if "private" in tags:
        sigma -= 0.2
    if "interior" in tags:
        sigma -= 0.2
    if "lodging" in tags or "residential" in tags or "medical" in tags:
        sigma -= 0.3
    if "institution" in tags:
        sigma -= 0.2
    return _clamp(sigma, 0.8, 3.0)


def _wound_class(method_category: str) -> str:
    if method_category == "blunt":
        return "laceration"
    if method_category == "poison":
        return "no_obvious_trauma"
    return "incision"


def project_case(truth: TruthState, rng: Rng) -> PresentationCase:
    evidence: List = []

    kill_events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    if not kill_events:
        return PresentationCase(case_id=truth.case_id, seed=truth.seed, evidence=[])
    kill_event = sorted(kill_events, key=lambda e: e.timestamp)[0]
    discovery_events = [event for event in truth.events.values() if event.kind == EventKind.DISCOVERY]
    discovery_time = (
        sorted(discovery_events, key=lambda e: e.timestamp)[0].timestamp
        if discovery_events
        else kill_event.timestamp + 2
    )

    location_entries = truth.case_meta.get("locations")
    if not isinstance(location_entries, list) or not location_entries:
        location_entries = [
            {
                "location_id": str(kill_event.location_id),
                "archetype_id": truth.case_meta.get("location_archetype"),
                "scene_layout": truth.case_meta.get("scene_layout"),
                "role": "primary",
            }
        ]
    primary_entry = None
    for entry in location_entries:
        entry_id = _uuid_from(entry.get("location_id"))
        if entry_id and entry_id == kill_event.location_id:
            primary_entry = entry
            break
    if primary_entry is None:
        primary_entry = next(
            (entry for entry in location_entries if entry.get("role") == "primary"),
            location_entries[0],
        )

    primary_location_id = _uuid_from(primary_entry.get("location_id")) or kill_event.location_id
    location = truth.locations.get(primary_location_id)
    cctv_available = bool(location and "cctv" in location.tags)
    location_archetype = primary_entry.get("archetype_id") or truth.case_meta.get("location_archetype")
    profiles = load_location_profiles()
    archetype = profiles["archetypes"].get(location_archetype, {}) if location_archetype else {}
    presence_curve = archetype.get("presence_curve", {}) or {}
    visibility = archetype.get("visibility", {}) or {}
    surveillance = archetype.get("surveillance", {}) or {}
    logs = archetype.get("logs", []) or []
    scene_layout = primary_entry.get("scene_layout") or truth.case_meta.get("scene_layout") or {}
    scene_pois = scene_layout.get("pois", []) or []
    poi_ids = [poi.get("poi_id") for poi in scene_pois if poi.get("poi_id")]
    poi_zone = {
        poi.get("poi_id"): poi.get("zone_id") for poi in scene_pois if poi.get("poi_id")
    }
    poi_tags = {
        poi.get("poi_id"): poi.get("tags", [])
        for poi in scene_pois
        if poi.get("poi_id")
    }
    poi_labels = {
        poi.get("poi_id"): poi.get("label")
        for poi in scene_pois
        if poi.get("poi_id")
    }
    primary_poi_id = primary_entry.get("primary_poi_id") or truth.case_meta.get("primary_poi_id")
    body_poi_id = primary_entry.get("body_poi_id") or truth.case_meta.get("body_poi_id") or primary_poi_id
    if not body_poi_id and poi_ids:
        body_poi_id = poi_ids[0]
    if not primary_poi_id:
        primary_poi_id = body_poi_id
    obs_poi_ids = list(poi_ids)
    if obs_poi_ids:
        obs_rng = rng.fork("scene-observations")
        obs_rng.shuffle(obs_poi_ids)
    non_body_poi_ids = [poi_id for poi_id in obs_poi_ids if poi_id != body_poi_id]
    wound_poi_id = body_poi_id or primary_poi_id
    tod_poi_id = body_poi_id or primary_poi_id
    entry_poi_id = non_body_poi_ids[0] if non_body_poi_ids else (body_poi_id or primary_poi_id)

    bucket = _time_bucket(kill_event.timestamp)
    presence = float(presence_curve.get(bucket, 0.5))
    visibility_score = (
        float(visibility.get("lighting", 0.5))
        + (1.0 - float(visibility.get("occlusion", 0.5)))
        + (1.0 - float(visibility.get("noise", 0.5)))
    ) / 3.0

    offender = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )
    competence = _float_trait(offender, "competence", 0.5)
    risk_tolerance = _float_trait(offender, "risk_tolerance", 0.5)
    access_path = truth.case_meta.get("access_path", "")
    method_category = "sharp"
    if kill_event.metadata and "method_category" in kill_event.metadata:
        method_category = str(kill_event.metadata.get("method_category"))

    witnesses = [
        person for person in truth.people.values() if RoleTag.WITNESS in person.role_tags
    ]
    if witnesses:
        for witness in witnesses:
            witness_rng = rng.fork(f"witness:{witness.id}")
            relation = (
                truth.relationship_between(witness.id, offender.id) if offender else None
            )
            closeness = str(relation.get("closeness", "stranger")) if relation else "stranger"
            if closeness == "intimate":
                sigma = 3.0
            elif closeness == "acquaintance":
                sigma = 2.0
            else:
                sigma = 1.5
            time_window = fuzz_time(kill_event.timestamp, sigma=sigma, rng=witness_rng)
            confidence = confidence_from_window(time_window)
            if presence < 0.25 or visibility_score < 0.35:
                confidence = _downgrade(confidence)
            observed_person_ids = []
            if offender and presence >= 0.25:
                see_chance = presence * visibility_score
                if closeness in {"intimate", "acquaintance"}:
                    see_chance += 0.1
                if risk_tolerance >= 0.6:
                    see_chance += 0.1
                if cctv_available:
                    see_chance -= 0.1
                if witness_rng.random() < _clamp(see_chance, 0.1, 0.85):
                    observed_person_ids.append(offender.id)
            location_name = location.name if location else "building"
            place = place_with_article(location_name)
            heard_prefix = "I think I heard" if confidence == ConfidenceBand.WEAK else "I heard"
            saw_prefix = "I think I saw" if confidence == ConfidenceBand.WEAK else "I saw"
            statement = f"{heard_prefix} a struggle near {place}."
            if offender and observed_person_ids:
                statement = f"{saw_prefix} {offender.name} outside {place}."
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
                location_id=primary_location_id,
                observed_person_ids=list(kill_event.participants),
                time_window=(kill_event.timestamp - 1, kill_event.timestamp + 1),
            )
        )
        cctv_added = True

    log_candidates = [
        poi_id
        for poi_id in poi_ids
        if _is_log_poi(poi_id, poi_tags.get(poi_id, []))
    ]
    cctv_candidates = [
        poi_id
        for poi_id in poi_ids
        if _is_cctv_poi(poi_id, poi_tags.get(poi_id, []))
    ]
    log_rng = rng.fork("scene-logs")
    log_sources = [source for source in logs if isinstance(source, str)]
    log_chance = min(0.85, 0.15 * len(log_sources) + float(surveillance.get("cctv", 0.0)))
    poi_digital_added = False
    poi_testimonial_added = False
    log_poi_id = None
    if log_candidates and (log_sources or cctv_candidates):
        omit_chance = _clamp(0.5 - log_chance, 0.05, 0.8)
        if not maybe_omit(omit_chance, log_rng):
            poi_id = log_rng.choice(log_candidates)
            log_label = log_rng.choice(log_sources) if log_sources else "access log"
            label_text = log_label.replace("_", " ").title()
            summary = f"Access log ({label_text})"
            source = "Facility Log"
            confidence = ConfidenceBand.MEDIUM
            if not log_sources:
                summary = "CCTV console still"
                source = "Security Desk"
                confidence = ConfidenceBand.WEAK
            time_window = fuzz_time(
                kill_event.timestamp,
                sigma=2.0,
                rng=log_rng.fork("window"),
            )
            evidence.append(
                CCTVReport(
                    evidence_type=EvidenceType.CCTV,
                    summary=summary,
                    source=source,
                    time_collected=kill_event.timestamp + 1,
                    confidence=confidence,
                    poi_id=poi_id,
                    location_id=primary_location_id,
                    observed_person_ids=[],
                    time_window=time_window,
                )
            )
            cctv_added = True
            poi_digital_added = True
            log_poi_id = poi_id

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
                location_id=primary_location_id,
            )
        )
        forensics_added = True
        break

    if primary_poi_id:
        body_tags = list(poi_tags.get(body_poi_id, []))
        if not body_tags and body_poi_id in poi_zone:
            zone_id = poi_zone.get(body_poi_id)
            body_tags = list(
                profiles.get("zone_templates", {})
                .get(zone_id, {})
                .get("tags", [])
            )
        if location and location.tags:
            for tag in location.tags:
                if tag not in body_tags:
                    body_tags.append(tag)
        tod_window = fuzz_time(
            kill_event.timestamp,
            sigma=_tod_sigma(body_tags),
            rng=rng,
        )
        hours_since = max(1, discovery_time - kill_event.timestamp)
        evidence.append(
            ForensicObservation(
                evidence_type=EvidenceType.FORENSICS,
                summary="Forensic observation (TOD)",
                source="Scene Unit",
                time_collected=kill_event.timestamp + 1,
                confidence=ConfidenceBand.MEDIUM,
                poi_id=tod_poi_id or primary_poi_id,
                observation=f"Body cooling suggests death {_format_time_phrase(tod_window)}.",
                tod_window=tod_window,
                stage_hint=_rigor_stage(hours_since),
                location_id=primary_location_id,
            )
        )
        wound_class = _wound_class(method_category)
        if wound_class == "no_obvious_trauma":
            observation = "No obvious external trauma is visible at first glance."
        elif wound_class == "laceration":
            observation = "Irregular tearing and tissue bridging suggest blunt trauma."
        else:
            observation = "Clean margins suggest a sharp instrument."
        evidence.append(
            ForensicObservation(
                evidence_type=EvidenceType.FORENSICS,
                summary="Forensic observation (wound)",
                source="Scene Unit",
                time_collected=kill_event.timestamp + 1,
                confidence=ConfidenceBand.MEDIUM,
                poi_id=wound_poi_id or primary_poi_id,
                observation=observation,
                wound_class=wound_class,
                location_id=primary_location_id,
            )
        )
        entry_confidence = ConfidenceBand.MEDIUM
        if competence >= 0.7:
            entry_confidence = ConfidenceBand.WEAK
        if access_path == "forced_entry":
            entry_observation = "Scuffing and damage suggest forced entry."
        elif access_path == "trusted_contact":
            entry_observation = "No clear signs of forced entry; access may have been granted."
        else:
            entry_observation = "Entry appears routine; no immediate signs of force."
        evidence.append(
            ForensicObservation(
                evidence_type=EvidenceType.FORENSICS,
                summary="Forensic observation (entry)",
                source="Scene Unit",
                time_collected=kill_event.timestamp + 1,
                confidence=entry_confidence,
                poi_id=entry_poi_id or primary_poi_id,
                observation=entry_observation,
                location_id=primary_location_id,
            )
        )

        extra_pois = [poi_id for poi_id in non_body_poi_ids if poi_id != entry_poi_id]
        extra_notes = [
            "Light scuffing suggests recent movement.",
            "A faint smear indicates contact with a surface.",
            "Dust displacement suggests something was moved.",
            "Small debris points to hurried movement.",
        ]
        obs_rng = rng.fork("poi-trace")
        obs_rng.shuffle(extra_pois)
        for poi_id in extra_pois:
            if poi_id == log_poi_id:
                continue
            tags = poi_tags.get(poi_id, [])
            if not poi_digital_added and (
                _is_cctv_poi(poi_id, tags) or _is_log_poi(poi_id, tags)
            ):
                poi_rng = obs_rng.fork(f"poi-digital:{poi_id}")
                label = poi_rng.choice(log_sources) if log_sources else "access log"
                summary = f"Access log ({label.replace('_', ' ').title()})"
                source = "Facility Log"
                confidence = ConfidenceBand.MEDIUM
                if not log_sources:
                    summary = "CCTV console still"
                    source = "Security Desk"
                    confidence = ConfidenceBand.WEAK
                time_window = fuzz_time(
                    kill_event.timestamp,
                    sigma=2.0,
                    rng=poi_rng.fork("window"),
                )
                evidence.append(
                    CCTVReport(
                        evidence_type=EvidenceType.CCTV,
                        summary=summary,
                        source=source,
                        time_collected=kill_event.timestamp + 1,
                        confidence=confidence,
                        poi_id=poi_id,
                        location_id=kill_event.location_id,
                        observed_person_ids=[],
                        time_window=time_window,
                    )
                )
                cctv_added = True
                poi_digital_added = True
                continue
            if witnesses and not poi_testimonial_added and presence >= 0.35:
                poi_rng = obs_rng.fork(f"poi-witness:{poi_id}")
                witness = poi_rng.choice(witnesses)
                time_window = fuzz_time(kill_event.timestamp, sigma=2.0, rng=poi_rng)
                confidence = confidence_from_window(time_window)
                if presence < 0.3 or visibility_score < 0.35:
                    confidence = _downgrade(confidence)
                see_chance = presence * visibility_score
                if risk_tolerance >= 0.6:
                    see_chance += 0.1
                observed_person_ids: list = []
                if offender and poi_rng.random() < _clamp(see_chance, 0.1, 0.75):
                    observed_person_ids.append(offender.id)
                poi_label = poi_labels.get(poi_id) or _poi_name(poi_id)
                poi_phrase = poi_label.lower()
                heard_prefix = "I think I heard" if confidence == ConfidenceBand.WEAK else "I heard"
                saw_prefix = "I think I saw" if confidence == ConfidenceBand.WEAK else "I saw"
                statement = f"{heard_prefix} movement near the {poi_phrase}."
                if offender and observed_person_ids:
                    statement = f"{saw_prefix} {offender.name} near the {poi_phrase}."
                evidence.append(
                    WitnessStatement(
                        evidence_type=EvidenceType.TESTIMONIAL,
                        summary="Witness statement (scene)",
                        source=witness.name,
                        time_collected=kill_event.timestamp + 1,
                        confidence=confidence,
                        witness_id=witness.id,
                        statement=statement,
                        reported_time_window=time_window,
                        location_id=kill_event.location_id,
                        observed_person_ids=observed_person_ids,
                        poi_id=poi_id,
                        uncertainty_hooks=["Scene-level account; no formal interview."],
                    )
                )
                poi_testimonial_added = True
                continue
            observation = obs_rng.choice(extra_notes)
            evidence.append(
                ForensicObservation(
                    evidence_type=EvidenceType.FORENSICS,
                    summary="Forensic observation (trace)",
                    source="Scene Unit",
                    time_collected=kill_event.timestamp + 1,
                    confidence=ConfidenceBand.WEAK,
                    poi_id=poi_id or primary_poi_id,
                    observation=observation,
                    location_id=primary_location_id,
                )
            )

        pattern_plan = _pattern_plan(truth)
        if pattern_plan and pattern_plan.get("pattern_type") != "none":
            primary = pattern_plan.get("primary")
            observation = pattern_plan.get("observation")
            support = pattern_plan.get("support")
            support_present = bool(pattern_plan.get("support_present"))
            if primary and observation and observation.get("token_status") != "Absent":
                pattern_poi_rng = rng.fork("pattern-poi")
                poi_id = _pattern_poi_id(
                    primary.get("category"),
                    body_poi_id,
                    entry_poi_id,
                    non_body_poi_ids,
                    pattern_poi_rng,
                )
                evidence.append(
                    ForensicObservation(
                        evidence_type=EvidenceType.FORENSICS,
                        summary="Forensic observation (scene detail)",
                        source="Scene Unit",
                        time_collected=kill_event.timestamp + 1,
                        confidence=_pattern_confidence(observation),
                        poi_id=poi_id or primary_poi_id,
                        observation=_pattern_primary_observation(primary, observation),
                        location_id=primary_location_id,
                    )
                )
            if support and support_present:
                evidence.append(
                    ForensicObservation(
                        evidence_type=EvidenceType.FORENSICS,
                        summary="Forensic observation (trace)",
                        source="Forensics Lab",
                        time_collected=kill_event.timestamp + 2,
                        confidence=ConfidenceBand.MEDIUM,
                        poi_id=entry_poi_id or primary_poi_id,
                        observation=_pattern_support_observation(support),
                        location_id=primary_location_id,
                    )
                )

    secondary_entries = [entry for entry in location_entries if entry is not primary_entry]
    if secondary_entries:
        offsite_rng = rng.fork("offsite")
        for idx, entry in enumerate(secondary_entries):
            entry_location_id = _uuid_from(entry.get("location_id"))
            if not entry_location_id:
                continue
            entry_location = truth.locations.get(entry_location_id)
            entry_layout = entry.get("scene_layout") or {}
            entry_pois = entry_layout.get("pois", []) or []
            entry_poi_ids = [poi.get("poi_id") for poi in entry_pois if poi.get("poi_id")]
            entry_poi_tags = {
                poi.get("poi_id"): poi.get("tags", [])
                for poi in entry_pois
                if poi.get("poi_id")
            }
            entry_poi_labels = {
                poi.get("poi_id"): poi.get("label")
                for poi in entry_pois
                if poi.get("poi_id")
            }
            entry_archetype_id = entry.get("archetype_id")
            entry_archetype = (
                profiles["archetypes"].get(entry_archetype_id, {}) if entry_archetype_id else {}
            )
            entry_presence_curve = entry_archetype.get("presence_curve", {}) or {}
            entry_visibility = entry_archetype.get("visibility", {}) or {}
            entry_surveillance = entry_archetype.get("surveillance", {}) or {}
            entry_logs = entry_archetype.get("logs", []) or []
            bucket = _time_bucket(kill_event.timestamp)
            entry_presence = float(entry_presence_curve.get(bucket, 0.35))
            noise = float(entry_visibility.get("noise", 0.4))
            witness_weight = max(0.05, entry_presence * (1.0 - noise))
            cctv_weight = float(entry_surveillance.get("cctv", 0.0))
            logs_weight = min(0.8, 0.2 + (0.1 * len(entry_logs))) if entry_logs else 0.0
            choice = _weighted_choice(
                offsite_rng.fork(f"choice:{idx}"),
                {"cctv": cctv_weight, "logs": logs_weight, "witness": witness_weight},
            )
            if choice in {"cctv", "logs"}:
                log_candidates = [
                    poi_id
                    for poi_id in entry_poi_ids
                    if _is_log_poi(poi_id, entry_poi_tags.get(poi_id, []))
                ]
                cctv_candidates = [
                    poi_id
                    for poi_id in entry_poi_ids
                    if _is_cctv_poi(poi_id, entry_poi_tags.get(poi_id, []))
                ]
                entry_poi_id = None
                if choice == "logs" and log_candidates:
                    entry_poi_id = offsite_rng.choice(log_candidates)
                elif cctv_candidates:
                    entry_poi_id = offsite_rng.choice(cctv_candidates)
                elif entry_poi_ids:
                    entry_poi_id = offsite_rng.choice(entry_poi_ids)
                log_label = None
                if choice == "logs" and entry_logs:
                    log_label = offsite_rng.choice(entry_logs)
                summary = "CCTV report (off-site)"
                source = "Off-site CCTV"
                confidence = ConfidenceBand.WEAK
                if log_label:
                    summary = f"Access log ({log_label.replace('_', ' ').title()})"
                    source = "Facility Log"
                    confidence = ConfidenceBand.MEDIUM
                time_window = fuzz_time(
                    kill_event.timestamp + offsite_rng.randint(-2, 2),
                    sigma=2.5,
                    rng=offsite_rng.fork(f"window:{idx}"),
                )
                evidence.append(
                    CCTVReport(
                        evidence_type=EvidenceType.CCTV,
                        summary=summary,
                        source=source,
                        time_collected=kill_event.timestamp + 1,
                        confidence=confidence,
                        location_id=entry_location_id,
                        observed_person_ids=[],
                        time_window=time_window,
                        poi_id=entry_poi_id,
                    )
                )
                cctv_added = True
                continue

            if choice == "witness" and witnesses:
                witness = offsite_rng.choice(witnesses)
                time_window = fuzz_time(
                    kill_event.timestamp + offsite_rng.randint(-2, 2),
                    sigma=2.5,
                    rng=offsite_rng.fork(f"witness-window:{idx}"),
                )
                confidence = confidence_from_window(time_window)
                if entry_presence < 0.3:
                    confidence = _downgrade(confidence)
                place = place_with_article(entry_location.name if entry_location else "location")
                statement = f"I heard activity near {place}."
                observed_person_ids: list = []
                evidence.append(
                    WitnessStatement(
                        evidence_type=EvidenceType.TESTIMONIAL,
                        summary="Witness statement (off-site)",
                        source=witness.name,
                        time_collected=kill_event.timestamp + 1,
                        confidence=confidence,
                        witness_id=witness.id,
                        statement=statement,
                        reported_time_window=time_window,
                        location_id=entry_location_id,
                        observed_person_ids=observed_person_ids,
                        poi_id=None,
                        uncertainty_hooks=["Off-site account; limited context."],
                    )
                )
                continue

            entry_poi_id = entry_poi_ids[0] if entry_poi_ids else None
            entry_label = entry_poi_labels.get(entry_poi_id) if entry_poi_id else None
            label_text = entry_label or "area"
            evidence.append(
                ForensicObservation(
                    evidence_type=EvidenceType.FORENSICS,
                    summary="Forensic observation (off-site)",
                    source="Scene Unit",
                    time_collected=kill_event.timestamp + 1,
                    confidence=ConfidenceBand.WEAK,
                    poi_id=entry_poi_id,
                    observation=f"Scene note from the {label_text.lower()}.",
                    location_id=entry_location_id,
                )
            )

    if not cctv_added and not forensics_added:
        if cctv_available:
            evidence.append(
                CCTVReport(
                    evidence_type=EvidenceType.CCTV,
                    summary="CCTV report (partial)",
                    source="Traffic Control",
                    time_collected=kill_event.timestamp + 1,
                    confidence=ConfidenceBand.WEAK,
                location_id=primary_location_id,
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
                    location_id=primary_location_id,
                )
            )

    return PresentationCase(case_id=truth.case_id, seed=truth.seed, evidence=evidence)
