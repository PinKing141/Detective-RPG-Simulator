from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis, ReasoningStep
from noir.domain.enums import RoleTag
from noir.investigation.actions import arrest, interview, set_hypothesis
from noir.investigation.interviews import InterviewApproach
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def _wrong_suspect_id(truth, offender_id):
	for person in truth.people.values():
		if person.id == offender_id:
			continue
		if RoleTag.VICTIM in person.role_tags:
			continue
		return person.id
	raise AssertionError("Expected an innocent suspect candidate")


def test_wrong_arrest_immediately_punishes_state() -> None:
	truth, case_facts = generate_case(Rng(41), case_id="case_wrong_arrest")
	presentation = project_case(truth, Rng(41))
	state = InvestigationState()
	wrong_suspect_id = _wrong_suspect_id(truth, case_facts["offender_id"])
	board = DeductionBoard(
		hypothesis=Hypothesis(
			suspect_id=wrong_suspect_id,
			claims=[ClaimType.PRESENCE, ClaimType.OPPORTUNITY],
			evidence_ids=[item.id for item in presentation.evidence[:2]],
		)
	)

	result = arrest(
		truth,
		presentation,
		state,
		wrong_suspect_id,
		case_facts["crime_scene_id"],
		has_hypothesis=True,
		board=board,
	)

	assert result.outcome.value == "failure"
	assert "Wrong suspect arrested" in result.summary
	assert state.trust == 2
	assert state.pressure == 3
	assert any("real offender" in note.lower() for note in result.notes)


def test_repeat_interview_tracks_memory_and_changes_reaction() -> None:
	truth, case_facts = generate_case(Rng(51), case_id="case_repeat_interview")
	presentation = project_case(truth, Rng(51))
	state = InvestigationState()
	witness_id = case_facts["witness_id"]
	location_id = case_facts["crime_scene_id"]

	first = interview(
		truth,
		presentation,
		state,
		witness_id,
		location_id,
		approach=InterviewApproach.BASELINE,
	)
	second = interview(
		truth,
		presentation,
		state,
		witness_id,
		location_id,
		approach=InterviewApproach.BASELINE,
	)

	interview_state = state.interviews[str(witness_id)]

	assert first.summary != second.summary
	assert interview_state.approach_counts["baseline"] == 2
	assert any("same ground" in second.summary.lower() or "repeating" in note.lower() for note in second.notes)


def test_hypothesis_requires_reasoning_chain() -> None:
	truth, case_facts = generate_case(Rng(61), case_id="case_reasoning_required")
	presentation = project_case(truth, Rng(61))
	state = InvestigationState()
	state.knowledge.known_evidence.extend(item.id for item in presentation.evidence[:2])
	board = DeductionBoard()

	result = set_hypothesis(
		state,
		board,
		case_facts["offender_id"],
		[ClaimType.PRESENCE],
		[item.id for item in presentation.evidence[:1]],
		[],
	)

	assert result.outcome.value == "failure"
	assert "reasoning link" in result.summary.lower()


def test_first_contact_prefers_real_suspect_over_false_lead() -> None:
	truth, case_facts = generate_case(Rng(71), case_id="case_first_contact_fairness")
	presentation = project_case(truth, Rng(71))
	state = InvestigationState()
	witness_id = case_facts["witness_id"]
	location_id = case_facts["crime_scene_id"]
	offender_id = case_facts["offender_id"]
	innocent_id = _wrong_suspect_id(truth, offender_id)
	presentation.evidence = [
		item
		for item in presentation.evidence
		if not (isinstance(item, WitnessStatement) and item.witness_id == witness_id)
	]
	presentation.evidence.extend(
		[
			WitnessStatement(
				evidence_type=EvidenceType.TESTIMONIAL,
				summary="Witness statement (possible match)",
				source="Interview",
				time_collected=1,
				confidence=ConfidenceBand.WEAK,
				witness_id=witness_id,
				statement="I thought it might have been the wrong person.",
				reported_time_window=(20, 21),
				location_id=location_id,
				observed_person_ids=[innocent_id],
				uncertainty_hooks=["Low light leaves room for misidentification."],
			),
			WitnessStatement(
				evidence_type=EvidenceType.TESTIMONIAL,
				summary="Witness statement",
				source="Interview",
				time_collected=1,
				confidence=ConfidenceBand.MEDIUM,
				witness_id=witness_id,
				statement="I saw the real suspect near the scene.",
				reported_time_window=(20, 21),
				location_id=location_id,
				observed_person_ids=[offender_id],
				uncertainty_hooks=[],
			),
		]
	)

	result = interview(
		truth,
		presentation,
		state,
		witness_id,
		location_id,
		approach=InterviewApproach.BASELINE,
	)

	revealed = [item for item in result.revealed if isinstance(item, WitnessStatement)]

	assert len(revealed) >= 2
	assert offender_id in revealed[0].observed_person_ids
	assert innocent_id in revealed[1].observed_person_ids
