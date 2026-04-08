from noir.cases.truth_generator import generate_case
from noir.domain.enums import ConfidenceBand
from noir.domain.enums import RoleTag
from noir.domain.enums import EventKind
from noir.nemesis.state import NemesisCasePlan
from noir.presentation.evidence import CCTVReport, ForensicObservation, WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng



def _plan(approach: str, control: str, cleanup: str, exit_style: str) -> NemesisCasePlan:
	return NemesisCasePlan(
		is_nemesis_case=True,
		method_category="sharp",
		visibility=2,
		component_values={
			"approach": approach,
			"control": control,
			"method": "sharp",
			"cleanup": cleanup,
			"exit": exit_style,
		},
	)


def _primary_exit_time(truth, case_facts) -> int:
	offender_id = case_facts["offender_id"]
	crime_scene_id = case_facts["crime_scene_id"]
	for _, location_id, data in truth.graph.edges(offender_id, data=True):
		if data.get("edge_type") != "located_at":
			continue
		if location_id == crime_scene_id:
			return int(data["exit_time"])
	raise AssertionError("Primary offender location not found")


def test_generate_case_threads_nemesis_components_into_truth() -> None:
	truth, case_facts = generate_case(
		Rng(19),
		case_id="case_mo_truth",
		nemesis_plan=_plan("break_in", "restraints", "wipe", "vehicle"),
	)

	assert truth.case_meta["approach_style"] == "break_in"
	assert truth.case_meta["control_style"] == "restraints"
	assert truth.case_meta["cleanup_style"] == "wipe"
	assert truth.case_meta["exit_style"] == "vehicle"
	assert truth.case_meta["access_path"] == "forced_entry"
	assert _primary_exit_time(truth, case_facts) == case_facts["crime_time"]
	assert any(
		event.kind == EventKind.CONFRONTATION and event.metadata.get("control_style") == "restraints"
		for event in truth.events.values()
	)


def test_project_case_surfaces_cleanup_and_exit_footprint() -> None:
	truth, _ = generate_case(
		Rng(23),
		case_id="case_mo_projection",
		nemesis_plan=_plan("lure", "intimidation", "staging", "misdirection"),
	)

	presentation = project_case(truth, Rng(23))
	observations = [
		item.observation
		for item in presentation.evidence
		if isinstance(item, ForensicObservation)
	]

	assert any("drawn into routine contact" in observation for observation in observations)
	assert any("coercive force" in observation or "dominate the encounter" in observation for observation in observations)
	assert any("deliberately arranged" in observation for observation in observations)
	assert any("confuse direction of travel" in observation for observation in observations)


def test_project_case_surfaces_nemesis_signature() -> None:
	from noir.nemesis.state import create_nemesis_state
	from noir.world.state import WorldState

	world = WorldState()
	world.nemesis_state = create_nemesis_state(Rng(91))
	truth, _ = generate_case(
		Rng(91),
		case_id="case_signature_projection",
		world=world,
		nemesis_plan=_plan("lure", "restraints", "none", "walkaway"),
	)

	presentation = project_case(truth, Rng(91))
	observations = [
		item.observation
		for item in presentation.evidence
		if isinstance(item, ForensicObservation)
	]

	assert any("A " in observation and "is left" in observation for observation in observations)


def test_project_case_includes_a_false_suspect_trail() -> None:
	truth, _ = generate_case(Rng(37), case_id="case_false_trail")
	presentation = project_case(truth, Rng(37))
	innocent_ids = {
		person.id
		for person in truth.people.values()
		if RoleTag.OFFENDER not in person.role_tags and RoleTag.VICTIM not in person.role_tags
	}

	assert innocent_ids
	assert any(
		set(getattr(item, "observed_person_ids", [])).intersection(innocent_ids)
		for item in presentation.evidence
		if isinstance(item, (CCTVReport, WitnessStatement))
	)


def test_false_trail_never_outranks_best_real_hit() -> None:
	order = {
		ConfidenceBand.WEAK: 1,
		ConfidenceBand.MEDIUM: 2,
		ConfidenceBand.STRONG: 3,
	}
	for seed in (19, 41, 73):
		truth, _ = generate_case(Rng(seed), case_id=f"case_balance_{seed}")
		presentation = project_case(truth, Rng(seed))
		offender = next(person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags)
		red_id = truth.case_meta.get("red_herring_suspect_id")
		real_hits = [
			item.confidence
			for item in presentation.evidence
			if offender.id in getattr(item, "observed_person_ids", [])
		]
		false_hits = [
			item.confidence
			for item in presentation.evidence
			if red_id and any(str(pid) == str(red_id) for pid in getattr(item, "observed_person_ids", []))
		]
		if real_hits and false_hits:
			assert max(order[value] for value in false_hits) <= max(order[value] for value in real_hits)


def test_seed_37_keeps_a_real_suspect_trail() -> None:
	truth, case_facts = generate_case(Rng(37), case_id="case_seed_37_path")
	presentation = project_case(truth, Rng(37))
	offender_id = case_facts["offender_id"]

	assert any(
		offender_id in getattr(item, "observed_person_ids", [])
		for item in presentation.evidence
		if isinstance(item, (CCTVReport, WitnessStatement))
	)


def test_false_trail_uses_both_cctv_and_witness_media() -> None:
	media_by_seed = {}
	for seed in (11, 19):
		truth, _ = generate_case(Rng(seed), case_id=f"case_false_trail_medium_{seed}")
		project_case(truth, Rng(seed))
		media_by_seed[seed] = truth.case_meta.get("red_herring_medium")

	assert media_by_seed[11] == "witness"
	assert media_by_seed[19] == "cctv"
