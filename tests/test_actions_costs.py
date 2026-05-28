from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis, ReasoningStep
from noir.domain.enums import RoleTag
from noir.domain.models import Location, Person
from noir.investigation.actions import arrest, interview, set_hypothesis
from noir.investigation.interviews import InterviewApproach
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, WitnessStatement
from noir.presentation.evidence import PresentationCase
from noir.presentation.projector import project_case
from noir.truth.graph import TruthState
from noir.util.rng import Rng


def _wrong_suspect_id(truth, offender_id):
	for person in truth.people.values():
		if person.id == offender_id:
			continue
		if RoleTag.VICTIM in person.role_tags:
			continue
		return person.id
	raise AssertionError("Expected an innocent suspect candidate")


def _manual_suspect_case() -> tuple[TruthState, PresentationCase, InvestigationState, object, object, object]:
	truth = TruthState(case_id="case_manual_suspect", seed=17)
	scene = Location(name="Dock Warehouse")
	victim = Person(name="Etta Vale", role_tags=[RoleTag.VICTIM])
	suspect = Person(name="Mara Flint", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT])
	witness = Person(name="Jon Vale", role_tags=[RoleTag.WITNESS])
	truth.add_location(scene)
	truth.add_person(victim)
	truth.add_person(suspect)
	truth.add_person(witness)
	truth.record_event(RoleTag.__mro__[1].KILL if False else __import__("noir.domain.enums", fromlist=["EventKind"]).EventKind.KILL, 20, scene.id, participants=[suspect.id, victim.id])
	presentation = PresentationCase(case_id=truth.case_id, seed=truth.seed, evidence=[])
	state = InvestigationState()
	return truth, presentation, state, suspect, witness, scene


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


def test_pressure_interview_turns_known_contradiction_into_suspect_confrontation() -> None:
	truth, presentation, state, suspect, witness, scene = _manual_suspect_case()
	suspect_id = suspect.id
	witness_id = witness.id
	location_id = scene.id

	interview(truth, presentation, state, suspect_id, location_id, approach=InterviewApproach.BASELINE)
	contradiction = WitnessStatement(
		evidence_type=EvidenceType.TESTIMONIAL,
		summary="Witness statement",
		source="Interview",
		time_collected=state.time,
		confidence=ConfidenceBand.MEDIUM,
		witness_id=witness_id,
		statement="I saw the suspect in the scene window.",
		reported_time_window=(20, 21),
		location_id=location_id,
		observed_person_ids=[suspect_id],
		uncertainty_hooks=[],
	)
	presentation.evidence.append(contradiction)
	state.knowledge.known_evidence.append(contradiction.id)

	result = interview(
		truth,
		presentation,
		state,
		suspect_id,
		location_id,
		approach=InterviewApproach.PRESSURE,
	)

	assert result.outcome.value == "success"
	assert "confrontation" in result.summary.lower()
	assert any("confrontational" in note.lower() for note in result.notes)
	assert any(item.summary == "Suspect statement (confrontation)" for item in result.revealed)
	assert state.interviews[str(suspect_id)].phase == "confrontation"
	assert any(event.kind.value == "confrontation" for event in truth.events.values())


def test_suspect_confrontation_can_break_into_confession() -> None:
	truth, presentation, state, suspect, witness, scene = _manual_suspect_case()
	suspect_id = suspect.id
	witness_id = witness.id
	location_id = scene.id

	interview(truth, presentation, state, suspect_id, location_id, approach=InterviewApproach.BASELINE)
	first = WitnessStatement(
		evidence_type=EvidenceType.TESTIMONIAL,
		summary="Witness statement",
		source="Interview",
		time_collected=state.time,
		confidence=ConfidenceBand.MEDIUM,
		witness_id=witness_id,
		statement="I saw the suspect near the scene.",
		reported_time_window=(20, 21),
		location_id=location_id,
		observed_person_ids=[suspect_id],
		uncertainty_hooks=[],
	)
	second = CCTVReport(
		evidence_type=EvidenceType.CCTV,
		summary="CCTV report",
		source="Camera",
		time_collected=state.time,
		confidence=ConfidenceBand.STRONG,
		location_id=location_id,
		observed_person_ids=[suspect_id],
		time_window=(20, 21),
	)
	presentation.evidence.extend([first, second])
	state.knowledge.known_evidence.extend([first.id, second.id])

	result = interview(
		truth,
		presentation,
		state,
		suspect_id,
		location_id,
		approach=InterviewApproach.PRESSURE,
	)

	assert result.outcome.value == "success"
	assert "confession" in result.summary.lower()
	assert any("confession recorded" in note.lower() for note in result.notes)
	assert any(item.summary == "Suspect statement (confession)" for item in result.revealed)
	assert state.interviews[str(suspect_id)].confession_recorded is True
	assert state.interviews[str(suspect_id)].phase == "confession"
