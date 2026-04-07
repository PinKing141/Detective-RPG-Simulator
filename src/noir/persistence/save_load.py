"""JSON save/load helpers for resumable investigations."""

from __future__ import annotations

from pathlib import Path
import json
from uuid import UUID

from noir.investigation.interviews import BaselineProfile, InterviewPhase, InterviewState
from noir.investigation.leads import Lead, LeadStatus, NeighborLead
from noir.investigation.results import InvestigationState, LocationState
from noir.locations.profiles import ScenePOI
from noir.presentation.evidence import (
	CCTVReport,
	ForensicObservation,
	ForensicsResult,
	PresentationCase,
	WitnessStatement,
)
from noir.presentation.knowledge import KnowledgeState
from noir.profiling.profile import OffenderProfile, ProfileDrive, ProfileMobility, ProfileOrganization


SAVE_VERSION = 1

_EVIDENCE_TYPES = {
	"WitnessStatement": WitnessStatement,
	"CCTVReport": CCTVReport,
	"ForensicsResult": ForensicsResult,
	"ForensicObservation": ForensicObservation,
}


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[3]


def _save_dir(path: Path | None = None) -> Path:
	target = path or (_repo_root() / "data" / "saves")
	target.mkdir(parents=True, exist_ok=True)
	return target


def _save_path(case_id: str, path: Path | None = None) -> Path:
	return _save_dir(path) / f"{case_id}.json"


def save_investigation(
	case_id: str,
	seed: int,
	state: InvestigationState,
	presentation: PresentationCase,
	path: Path | None = None,
) -> Path:
	payload = {
		"version": SAVE_VERSION,
		"case_id": case_id,
		"seed": int(seed),
		"state": _serialize_state(state),
		"presentation": _serialize_presentation(presentation),
	}
	save_path = _save_path(case_id, path)
	save_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
	return save_path


def load_investigation(
	case_id: str,
	path: Path | None = None,
) -> tuple[int, InvestigationState, PresentationCase] | None:
	save_path = _save_path(case_id, path)
	if not save_path.exists():
		return None
	try:
		payload = json.loads(save_path.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		return None
	if int(payload.get("version", 0)) != SAVE_VERSION:
		return None
	seed = int(payload.get("seed", 0))
	state = _deserialize_state(payload.get("state", {}) or {})
	presentation = _deserialize_presentation(payload.get("presentation", {}) or {})
	return seed, state, presentation


def has_save(case_id: str, path: Path | None = None) -> bool:
	return _save_path(case_id, path).exists()


def delete_save(case_id: str, path: Path | None = None) -> bool:
	save_path = _save_path(case_id, path)
	if not save_path.exists():
		return False
	save_path.unlink()
	return True


def _serialize_state(state: InvestigationState) -> dict:
	return {
		"time": state.time,
		"pressure": state.pressure,
		"trust": state.trust,
		"cooperation": state.cooperation,
		"autonomy_marks": sorted(state.autonomy_marks),
		"knowledge": state.knowledge.model_dump(mode="json"),
		"style_counts": dict(state.style_counts),
		"location_states": {
			key: _serialize_location_state(value) for key, value in state.location_states.items()
		},
		"active_location_id": str(state.active_location_id) if state.active_location_id else None,
		"leads": [_serialize_lead(lead) for lead in state.leads],
		"scene_pois": [_serialize_scene_poi(poi) for poi in state.scene_pois],
		"visited_poi_ids": sorted(state.visited_poi_ids),
		"body_poi_id": state.body_poi_id,
		"interviews": {
			key: _serialize_interview_state(value) for key, value in state.interviews.items()
		},
		"neighbor_leads": [_serialize_neighbor_lead(lead) for lead in state.neighbor_leads],
		"profile": _serialize_profile(state.profile),
		"analyst_notes": list(state.analyst_notes),
		"warrant_grants": sorted(state.warrant_grants),
	}


def _deserialize_state(payload: dict) -> InvestigationState:
	state = InvestigationState(
		time=int(payload.get("time", 0)),
		pressure=int(payload.get("pressure", 0)),
		trust=int(payload.get("trust", 3)),
		cooperation=float(payload.get("cooperation", 1.0)),
		autonomy_marks=set(payload.get("autonomy_marks", []) or []),
		knowledge=KnowledgeState.model_validate(payload.get("knowledge", {}) or {}),
		style_counts={str(key): int(value) for key, value in (payload.get("style_counts", {}) or {}).items()},
		location_states={
			str(key): _deserialize_location_state(value)
			for key, value in (payload.get("location_states", {}) or {}).items()
		},
		active_location_id=_uuid_or_none(payload.get("active_location_id")),
		leads=[_deserialize_lead(entry) for entry in payload.get("leads", []) or []],
		scene_pois=[_deserialize_scene_poi(entry) for entry in payload.get("scene_pois", []) or []],
		visited_poi_ids=set(payload.get("visited_poi_ids", []) or []),
		body_poi_id=payload.get("body_poi_id"),
		interviews={
			str(key): _deserialize_interview_state(value)
			for key, value in (payload.get("interviews", {}) or {}).items()
		},
		neighbor_leads=[_deserialize_neighbor_lead(entry) for entry in payload.get("neighbor_leads", []) or []],
		profile=_deserialize_profile(payload.get("profile")),
		analyst_notes=list(payload.get("analyst_notes", []) or []),
		warrant_grants=set(payload.get("warrant_grants", []) or []),
	)
	return state


def _serialize_location_state(state: LocationState) -> dict:
	return {
		"location_id": str(state.location_id),
		"name": state.name,
		"district": state.district,
		"scene_pois": [_serialize_scene_poi(poi) for poi in state.scene_pois],
		"visited_poi_ids": sorted(state.visited_poi_ids),
		"body_poi_id": state.body_poi_id,
		"neighbor_leads": [_serialize_neighbor_lead(lead) for lead in state.neighbor_leads],
	}


def _deserialize_location_state(payload: dict) -> LocationState:
	return LocationState(
		location_id=UUID(str(payload.get("location_id"))),
		name=str(payload.get("name", "")),
		district=str(payload.get("district", "")),
		scene_pois=[_deserialize_scene_poi(entry) for entry in payload.get("scene_pois", []) or []],
		visited_poi_ids=set(payload.get("visited_poi_ids", []) or []),
		body_poi_id=payload.get("body_poi_id"),
		neighbor_leads=[_deserialize_neighbor_lead(entry) for entry in payload.get("neighbor_leads", []) or []],
	)


def _serialize_scene_poi(poi: ScenePOI) -> dict:
	return {
		"poi_id": poi.poi_id,
		"label": poi.label,
		"zone_id": poi.zone_id,
		"zone_label": poi.zone_label,
		"description": poi.description,
		"tags": list(poi.tags),
	}


def _deserialize_scene_poi(payload: dict) -> ScenePOI:
	return ScenePOI(
		poi_id=str(payload.get("poi_id", "")),
		label=str(payload.get("label", "")),
		zone_id=str(payload.get("zone_id", "")),
		zone_label=str(payload.get("zone_label", "")),
		description=str(payload.get("description", "")),
		tags=list(payload.get("tags", []) or []),
	)


def _serialize_lead(lead: Lead) -> dict:
	return {
		"key": lead.key,
		"label": lead.label,
		"evidence_type": lead.evidence_type.value,
		"deadline": lead.deadline,
		"action_hint": lead.action_hint,
		"status": lead.status.value,
	}


def _deserialize_lead(payload: dict) -> Lead:
	from noir.domain.enums import EvidenceType

	return Lead(
		key=str(payload.get("key", "")),
		label=str(payload.get("label", "")),
		evidence_type=EvidenceType(str(payload.get("evidence_type", "testimonial"))),
		deadline=int(payload.get("deadline", 0)),
		action_hint=str(payload.get("action_hint", "")),
		status=LeadStatus(str(payload.get("status", LeadStatus.ACTIVE.value))),
	)


def _serialize_neighbor_lead(lead: NeighborLead) -> dict:
	return {
		"slot_id": lead.slot_id,
		"label": lead.label,
		"hearing_bias": lead.hearing_bias,
		"witness_roles": dict(lead.witness_roles),
	}


def _deserialize_neighbor_lead(payload: dict) -> NeighborLead:
	return NeighborLead(
		slot_id=str(payload.get("slot_id", "")),
		label=str(payload.get("label", "")),
		hearing_bias=float(payload.get("hearing_bias", 0.3)),
		witness_roles={str(key): float(value) for key, value in (payload.get("witness_roles", {}) or {}).items()},
	)


def _serialize_interview_state(state: InterviewState) -> dict:
	return {
		"phase": state.phase.value,
		"rapport": state.rapport,
		"resistance": state.resistance,
		"fatigue": state.fatigue,
		"baseline_profile": None if state.baseline_profile is None else {
			"avg_sentence_len": state.baseline_profile.avg_sentence_len,
			"pronoun_ratio": state.baseline_profile.pronoun_ratio,
			"tense_pref": state.baseline_profile.tense_pref,
		},
		"last_claims": list(state.last_claims),
		"motive_to_lie": state.motive_to_lie,
		"contradiction_emitted": state.contradiction_emitted,
		"dialog_node_id": state.dialog_node_id,
	}


def _deserialize_interview_state(payload: dict) -> InterviewState:
	baseline = payload.get("baseline_profile")
	baseline_profile = None
	if isinstance(baseline, dict):
		baseline_profile = BaselineProfile(
			avg_sentence_len=float(baseline.get("avg_sentence_len", 0.0)),
			pronoun_ratio=float(baseline.get("pronoun_ratio", 0.0)),
			tense_pref=str(baseline.get("tense_pref", "past")),
		)
	return InterviewState(
		phase=InterviewPhase(str(payload.get("phase", InterviewPhase.BASELINE.value))),
		rapport=float(payload.get("rapport", 0.5)),
		resistance=float(payload.get("resistance", 0.5)),
		fatigue=float(payload.get("fatigue", 0.0)),
		baseline_profile=baseline_profile,
		last_claims=list(payload.get("last_claims", []) or []),
		motive_to_lie=bool(payload.get("motive_to_lie", False)),
		contradiction_emitted=bool(payload.get("contradiction_emitted", False)),
		dialog_node_id=payload.get("dialog_node_id"),
	)


def _serialize_profile(profile: OffenderProfile | None) -> dict | None:
	if profile is None:
		return None
	return {
		"organization": profile.organization.value,
		"drive": profile.drive.value,
		"mobility": profile.mobility.value,
		"evidence_ids": [str(value) for value in profile.evidence_ids],
	}


def _deserialize_profile(payload: dict | None) -> OffenderProfile | None:
	if not payload:
		return None
	return OffenderProfile(
		organization=ProfileOrganization(str(payload.get("organization", ProfileOrganization.UNKNOWN.value))),
		drive=ProfileDrive(str(payload.get("drive", ProfileDrive.UNKNOWN.value))),
		mobility=ProfileMobility(str(payload.get("mobility", ProfileMobility.UNKNOWN.value))),
		evidence_ids=[UUID(str(value)) for value in (payload.get("evidence_ids", []) or [])],
	)


def _uuid_or_none(value: str | None) -> UUID | None:
	if not value:
		return None
	return UUID(str(value))


def _serialize_presentation(presentation: PresentationCase) -> dict:
	return {
		"case_id": presentation.case_id,
		"seed": presentation.seed,
		"evidence": [_serialize_evidence(item) for item in presentation.evidence],
	}


def _deserialize_presentation(payload: dict) -> PresentationCase:
	evidence = [_deserialize_evidence(item) for item in payload.get("evidence", []) or []]
	return PresentationCase(
		case_id=str(payload.get("case_id", "")),
		seed=int(payload.get("seed", 0)),
		evidence=evidence,
	)


def _serialize_evidence(item) -> dict:
	payload = item.model_dump(mode="json")
	payload["__type__"] = item.__class__.__name__
	return payload


def _deserialize_evidence(payload: dict):
	kind = str(payload.get("__type__", "EvidenceItem"))
	data = dict(payload)
	data.pop("__type__", None)
	model = _EVIDENCE_TYPES.get(kind)
	if model is None:
		raise ValueError(f"Unknown evidence type in save payload: {kind}")
	return model.model_validate(data)
