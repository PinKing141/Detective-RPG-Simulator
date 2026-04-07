from noir.cases.truth_generator import generate_case
from noir.domain.enums import EventKind
from noir.nemesis.state import NemesisCasePlan
from noir.presentation.evidence import ForensicObservation
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
