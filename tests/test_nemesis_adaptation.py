from uuid import uuid4

from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.investigation.costs import ActionType
from noir.investigation.runtime import apply_runtime_rules
from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.nemesis.director_hooks import apply_nemesis_runtime_interference
from noir.nemesis.state import (
	NemesisComponent,
	NemesisComponentType,
	NemesisProfile,
	NemesisState,
	NemesisTypology,
	apply_nemesis_case_outcome,
	plan_nemesis_case,
)
from noir.presentation.evidence import ForensicObservation
from noir.util.rng import Rng
from noir.world.state import WorldState


def _component(
	component_type: NemesisComponentType,
	value: str,
	*,
	weight: float,
	competence: float,
	compromised: bool = False,
	avoid_cooldown: int = 0,
) -> NemesisComponent:
	return NemesisComponent(
		component_type=component_type,
		value=value,
		weight=weight,
		competence=competence,
		compromised=compromised,
		avoid_cooldown=avoid_cooldown,
	)


def _state() -> NemesisState:
	profile = NemesisProfile(
		typology=NemesisTypology.VISIONARY,
		signature_token="thread knot",
		signature_staging="posed",
		signature_message="silent",
		victimology_bias="mixed",
		comfort_zones=["harbor"],
		escalation_trait="taunting",
	)
	components = [
		_component(NemesisComponentType.APPROACH, "lure", weight=1.4, competence=0.7),
		_component(NemesisComponentType.APPROACH, "break_in", weight=0.7, competence=0.5),
		_component(NemesisComponentType.CONTROL, "restraints", weight=1.2, competence=0.8),
		_component(NemesisComponentType.CONTROL, "surprise", weight=0.8, competence=0.5),
		_component(
			NemesisComponentType.METHOD,
			"sharp",
			weight=1.8,
			competence=0.9,
			compromised=True,
		),
		_component(NemesisComponentType.METHOD, "blunt", weight=1.0, competence=0.8),
		_component(NemesisComponentType.METHOD, "poison", weight=0.4, competence=0.4),
		_component(NemesisComponentType.CLEANUP, "wipe", weight=1.1, competence=0.7),
		_component(NemesisComponentType.CLEANUP, "none", weight=0.9, competence=0.4),
		_component(NemesisComponentType.EXIT, "vehicle", weight=1.3, competence=0.75),
		_component(NemesisComponentType.EXIT, "walkaway", weight=0.8, competence=0.5),
	]
	return NemesisState(
		profile=profile,
		mo_components=components,
		exposure=3,
		exposure_baseline=2,
		cases_until_next=0,
		escalation_cap=3,
	)


def test_plan_nemesis_case_carries_full_component_vector() -> None:
	state = _state()

	plan = plan_nemesis_case(state, Rng(7))

	assert plan.is_nemesis_case is True
	assert plan.method_category == plan.component_values["method"]
	assert set(plan.component_values) == {"approach", "control", "method", "cleanup", "exit"}
	assert plan.visibility == 2


def test_plan_nemesis_case_starts_cooldown_for_compromised_method() -> None:
	state = _state()

	plan_nemesis_case(state, Rng(11))

	sharp = next(comp for comp in state.mo_components if comp.value == "sharp")
	assert sharp.avoid_cooldown == 2


def test_apply_outcome_marks_compromised_method_and_penalizes_it() -> None:
	state = _state()
	sharp = next(comp for comp in state.mo_components if comp.value == "sharp")
	sharp.compromised = False
	start_weight = sharp.weight
	start_competence = sharp.competence

	notes = apply_nemesis_case_outcome(
		state,
		True,
		2,
		"failed",
		"sharp",
		True,
		Rng(17),
		selected_components={
			"approach": "lure",
			"control": "restraints",
			"method": "sharp",
			"cleanup": "wipe",
			"exit": "vehicle",
		},
	)

	assert "Pattern file notes a compromised method." in notes
	assert sharp.compromised is True
	assert sharp.weight < start_weight
	assert sharp.competence < start_competence


def test_low_visibility_success_regresses_exposure_without_dropping_below_baseline() -> None:
	state = _state()

	apply_nemesis_case_outcome(
		state,
		True,
		1,
		"success",
		"blunt",
		False,
		Rng(23),
		selected_components={"method": "blunt"},
	)
	assert state.exposure == 2
	assert state.exposure_baseline == 2

	apply_nemesis_case_outcome(
		state,
		True,
		1,
		"success",
		"blunt",
		False,
		Rng(29),
		selected_components={"method": "blunt"},
	)
	assert state.exposure == 2


def test_failed_case_uses_counterplay_tone_when_present() -> None:
	state = _state()
	state.profile.counterplay_traits.append("aggression_feeder")

	apply_nemesis_case_outcome(
		state,
		True,
		2,
		"failed",
		"blunt",
		False,
		Rng(31),
		selected_components={"method": "blunt"},
	)

	assert state.profile.failure_echo == "baiting"


def test_runtime_interference_perturbs_first_eligible_action() -> None:
	state = InvestigationState()
	result = ActionResult(
		action=ActionType.VISIT_SCENE,
		outcome=ActionOutcome.SUCCESS,
		summary="You document the scene.",
		time_cost=1,
		pressure_cost=0,
		cooperation_change=0.0,
		revealed=[
			ForensicObservation(
				evidence_type=EvidenceType.FORENSICS,
				summary="Forensic observation",
				source="Scene Unit",
				time_collected=1,
				confidence=ConfidenceBand.MEDIUM,
				observation="Light scuffing suggests recent movement.",
				location_id=uuid4(),
			)
		],
	)

	notes = apply_nemesis_runtime_interference(
		{
			"nemesis_case": True,
			"nemesis_components": {
				"approach": "lure",
				"control": "intimidation",
				"method": "sharp",
				"cleanup": "wipe",
				"exit": "misdirection",
			},
		},
		state,
		result,
	)

	assert notes
	assert result.revealed[0].confidence == ConfidenceBand.WEAK
	assert state.pressure == 1
	assert any("scene looks lightly scrubbed" in note.lower() for note in notes)
	assert apply_nemesis_runtime_interference({"nemesis_case": True}, state, result) == []


def test_runtime_rules_apply_shared_nemesis_effects() -> None:
	state = InvestigationState()
	world = WorldState()
	result = ActionResult(
		action=ActionType.VISIT_SCENE,
		outcome=ActionOutcome.SUCCESS,
		summary="You document the scene.",
		time_cost=1,
		pressure_cost=0,
		cooperation_change=0.0,
		revealed=[
			ForensicObservation(
				evidence_type=EvidenceType.FORENSICS,
				summary="Forensic observation",
				source="Scene Unit",
				time_collected=1,
				confidence=ConfidenceBand.MEDIUM,
				observation="Light scuffing suggests recent movement.",
				location_id=uuid4(),
			)
		],
	)

	apply_runtime_rules(
		{
			"nemesis_case": True,
			"nemesis_components": {
				"approach": "lure",
				"control": "intimidation",
				"method": "sharp",
				"cleanup": "wipe",
				"exit": "misdirection",
			},
		},
		state,
		result,
		world=world,
		district="harbor",
	)

	assert result.revealed[0].confidence == ConfidenceBand.WEAK
	assert state.pressure == 1
	assert "Nemesis interference cuts into the result." in result.summary
