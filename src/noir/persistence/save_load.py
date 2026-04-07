"""Save/load for in-progress investigations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from noir.investigation.interviews import BaselineProfile, InterviewPhase, InterviewState
from noir.investigation.leads import Lead, LeadStatus, NeighborLead
from noir.investigation.results import InvestigationState, LocationState
from noir.locations.profiles import ScenePOI
from noir.presentation.evidence import (
    CCTVReport,
    EvidenceType,
    ForensicObservation,
    ForensicsResult,
    PresentationCase,
    WitnessStatement,
)
from noir.presentation.knowledge import KnowledgeState
from noir.profiling.profile import OffenderProfile, ProfileDrive, ProfileMobility, ProfileOrganization

SAVE_VERSION = 1

_EVIDENCE_DESERIALIZERS = {
    EvidenceType.TESTIMONIAL: WitnessStatement,
    EvidenceType.CCTV: CCTVReport,
    EvidenceType.FORENSICS: ForensicsResult,
    "forensic_observation": ForensicObservation,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def saves_dir(base: Path | None = None) -> Path:
    root = base or Path(__file__).resolve().parents[3]
    d = root / "data" / "saves"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_path(case_id: str, base: Path | None = None) -> Path:
    return saves_dir(base) / f"{_safe_filename(case_id)}.json"


def has_save(case_id: str, base: Path | None = None) -> bool:
    return save_path(case_id, base).exists()


def delete_save(case_id: str, base: Path | None = None) -> None:
    path = save_path(case_id, base)
    if path.exists():
        path.unlink()


def save_investigation(
    case_id: str,
    case_seed: int,
    inv_state: InvestigationState,
    presentation: PresentationCase,
    base: Path | None = None,
) -> Path:
    """Serialize investigation progress to a JSON save file."""
    payload = {
        "version": SAVE_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "case_seed": case_seed,
        "case_id": case_id,
        "investigation_state": _serialize_inv_state(inv_state),
        "presentation_case": _serialize_presentation(presentation),
    }
    path = save_path(case_id, base)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_investigation(
    case_id: str,
    base: Path | None = None,
) -> tuple[int, InvestigationState, PresentationCase] | None:
    """
    Load a saved investigation.

    Returns (case_seed, InvestigationState, PresentationCase) or None if
    no save exists or the save version is incompatible.
    """
    path = save_path(case_id, base)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("version") != SAVE_VERSION:
        return None
    try:
        seed = int(data["case_seed"])
        inv_state = _deserialize_inv_state(data["investigation_state"])
        presentation = _deserialize_presentation(data["presentation_case"])
    except (KeyError, TypeError, ValueError):
        return None
    return seed, inv_state, presentation


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _safe_filename(case_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in case_id)


def _uuid_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


# -- InvestigationState -----------------------------------------------------


def _serialize_inv_state(s: InvestigationState) -> dict:
    return {
        "time": s.time,
        "pressure": s.pressure,
        "trust": s.trust,
        "cooperation": s.cooperation,
        "autonomy_marks": sorted(s.autonomy_marks),
        "knowledge": s.knowledge.model_dump(mode="json"),
        "style_counts": s.style_counts,
        "location_states": {
            k: _serialize_location_state(v) for k, v in s.location_states.items()
        },
        "active_location_id": _uuid_or_none(s.active_location_id),
        "leads": [_serialize_lead(lead) for lead in s.leads],
        "scene_pois": [_serialize_scene_poi(poi) for poi in s.scene_pois],
        "visited_poi_ids": sorted(s.visited_poi_ids),
        "body_poi_id": s.body_poi_id,
        "interviews": {
            k: _serialize_interview_state(v) for k, v in s.interviews.items()
        },
        "neighbor_leads": [_serialize_neighbor_lead(nl) for nl in s.neighbor_leads],
        "profile": _serialize_profile(s.profile),
        "analyst_notes": s.analyst_notes,
        "warrant_grants": sorted(s.warrant_grants),
    }


def _deserialize_inv_state(d: dict) -> InvestigationState:
    s = InvestigationState()
    s.time = int(d.get("time", 0))
    s.pressure = int(d.get("pressure", 0))
    s.trust = int(d.get("trust", 3))
    s.cooperation = float(d.get("cooperation", 1.0))
    s.autonomy_marks = set(d.get("autonomy_marks", []))
    s.knowledge = KnowledgeState.model_validate(d.get("knowledge", {}))
    s.style_counts = {k: int(v) for k, v in d.get("style_counts", {}).items()}
    s.location_states = {
        k: _deserialize_location_state(v)
        for k, v in d.get("location_states", {}).items()
    }
    raw_loc = d.get("active_location_id")
    s.active_location_id = UUID(raw_loc) if raw_loc else None
    s.leads = [_deserialize_lead(l) for l in d.get("leads", [])]
    s.scene_pois = [_deserialize_scene_poi(p) for p in d.get("scene_pois", [])]
    s.visited_poi_ids = set(d.get("visited_poi_ids", []))
    s.body_poi_id = d.get("body_poi_id")
    s.interviews = {
        k: _deserialize_interview_state(v) for k, v in d.get("interviews", {}).items()
    }
    s.neighbor_leads = [_deserialize_neighbor_lead(nl) for nl in d.get("neighbor_leads", [])]
    s.profile = _deserialize_profile(d.get("profile"))
    s.analyst_notes = d.get("analyst_notes", [])
    s.warrant_grants = set(d.get("warrant_grants", []))
    return s


# -- LocationState ----------------------------------------------------------


def _serialize_location_state(ls: LocationState) -> dict:
    return {
        "location_id": str(ls.location_id),
        "name": ls.name,
        "district": ls.district,
        "scene_pois": [_serialize_scene_poi(p) for p in ls.scene_pois],
        "visited_poi_ids": sorted(ls.visited_poi_ids),
        "body_poi_id": ls.body_poi_id,
        "neighbor_leads": [_serialize_neighbor_lead(nl) for nl in ls.neighbor_leads],
    }


def _deserialize_location_state(d: dict) -> LocationState:
    return LocationState(
        location_id=UUID(d["location_id"]),
        name=d["name"],
        district=d["district"],
        scene_pois=[_deserialize_scene_poi(p) for p in d.get("scene_pois", [])],
        visited_poi_ids=set(d.get("visited_poi_ids", [])),
        body_poi_id=d.get("body_poi_id"),
        neighbor_leads=[_deserialize_neighbor_lead(nl) for nl in d.get("neighbor_leads", [])],
    )


# -- ScenePOI ---------------------------------------------------------------


def _serialize_scene_poi(poi: ScenePOI) -> dict:
    return {
        "poi_id": poi.poi_id,
        "label": poi.label,
        "zone_id": poi.zone_id,
        "zone_label": poi.zone_label,
        "description": poi.description,
        "tags": list(poi.tags),
    }


def _deserialize_scene_poi(d: dict) -> ScenePOI:
    return ScenePOI(
        poi_id=d["poi_id"],
        label=d["label"],
        zone_id=d["zone_id"],
        zone_label=d["zone_label"],
        description=d.get("description", ""),
        tags=d.get("tags", []),
    )


# -- Lead -------------------------------------------------------------------


def _serialize_lead(lead: Lead) -> dict:
    return {
        "key": lead.key,
        "label": lead.label,
        "evidence_type": lead.evidence_type.value,
        "deadline": lead.deadline,
        "action_hint": lead.action_hint,
        "status": lead.status.value,
    }


def _deserialize_lead(d: dict) -> Lead:
    return Lead(
        key=d["key"],
        label=d["label"],
        evidence_type=EvidenceType(d["evidence_type"]),
        deadline=int(d["deadline"]),
        action_hint=d["action_hint"],
        status=LeadStatus(d.get("status", LeadStatus.ACTIVE)),
    )


# -- NeighborLead -----------------------------------------------------------


def _serialize_neighbor_lead(nl: NeighborLead) -> dict:
    return {
        "slot_id": nl.slot_id,
        "label": nl.label,
        "hearing_bias": nl.hearing_bias,
        "witness_roles": nl.witness_roles,
    }


def _deserialize_neighbor_lead(d: dict) -> NeighborLead:
    return NeighborLead(
        slot_id=d["slot_id"],
        label=d["label"],
        hearing_bias=float(d["hearing_bias"]),
        witness_roles={k: float(v) for k, v in d.get("witness_roles", {}).items()},
    )


# -- InterviewState ---------------------------------------------------------


def _serialize_interview_state(s: InterviewState) -> dict:
    return {
        "phase": s.phase.value,
        "rapport": s.rapport,
        "resistance": s.resistance,
        "fatigue": s.fatigue,
        "baseline_profile": _serialize_baseline_profile(s.baseline_profile),
        "last_claims": s.last_claims,
        "motive_to_lie": s.motive_to_lie,
        "contradiction_emitted": s.contradiction_emitted,
        "dialog_node_id": s.dialog_node_id,
    }


def _deserialize_interview_state(d: dict) -> InterviewState:
    s = InterviewState()
    s.phase = InterviewPhase(d.get("phase", InterviewPhase.BASELINE))
    s.rapport = float(d.get("rapport", 0.5))
    s.resistance = float(d.get("resistance", 0.5))
    s.fatigue = float(d.get("fatigue", 0.0))
    s.baseline_profile = _deserialize_baseline_profile(d.get("baseline_profile"))
    s.last_claims = d.get("last_claims", [])
    s.motive_to_lie = bool(d.get("motive_to_lie", False))
    s.contradiction_emitted = bool(d.get("contradiction_emitted", False))
    s.dialog_node_id = d.get("dialog_node_id")
    return s


def _serialize_baseline_profile(bp: BaselineProfile | None) -> dict | None:
    if bp is None:
        return None
    return {
        "avg_sentence_len": bp.avg_sentence_len,
        "pronoun_ratio": bp.pronoun_ratio,
        "tense_pref": bp.tense_pref,
    }


def _deserialize_baseline_profile(d: dict | None) -> BaselineProfile | None:
    if d is None:
        return None
    return BaselineProfile(
        avg_sentence_len=float(d["avg_sentence_len"]),
        pronoun_ratio=float(d["pronoun_ratio"]),
        tense_pref=str(d["tense_pref"]),
    )


# -- OffenderProfile --------------------------------------------------------


def _serialize_profile(profile: OffenderProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "organization": profile.organization.value,
        "drive": profile.drive.value,
        "mobility": profile.mobility.value,
        "evidence_ids": [str(eid) for eid in profile.evidence_ids],
    }


def _deserialize_profile(d: dict | None) -> OffenderProfile | None:
    if d is None:
        return None
    return OffenderProfile(
        organization=ProfileOrganization(d.get("organization", "unknown")),
        drive=ProfileDrive(d.get("drive", "unknown")),
        mobility=ProfileMobility(d.get("mobility", "unknown")),
        evidence_ids=[UUID(eid) for eid in d.get("evidence_ids", [])],
    )


# -- PresentationCase -------------------------------------------------------


def _serialize_presentation(pc: PresentationCase) -> dict:
    items = []
    for item in pc.evidence:
        raw = item.model_dump(mode="json")
        raw["__type__"] = type(item).__name__
        items.append(raw)
    return {
        "case_id": pc.case_id,
        "seed": pc.seed,
        "evidence": items,
    }


_CLASS_MAP = {
    "WitnessStatement": WitnessStatement,
    "CCTVReport": CCTVReport,
    "ForensicsResult": ForensicsResult,
    "ForensicObservation": ForensicObservation,
}


def _deserialize_presentation(d: dict) -> PresentationCase:
    evidence = []
    for raw in d.get("evidence", []):
        type_name = raw.pop("__type__", None)
        cls = _CLASS_MAP.get(type_name)
        if cls is not None:
            evidence.append(cls.model_validate(raw))
    return PresentationCase(
        case_id=d["case_id"],
        seed=int(d["seed"]),
        evidence=evidence,
    )
