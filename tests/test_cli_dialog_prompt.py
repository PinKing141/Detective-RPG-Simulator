from noir.cases.truth_generator import generate_case
from noir.deduction.board import DeductionBoard
from noir.domain.enums import ConfidenceBand, EvidenceType, EventKind, RoleTag
from noir.domain.models import Location
from noir.investigation.actions import interview
from noir.investigation.dialog_runtime import visible_dialog_prompt_options
from noir.investigation.leads import build_leads
from noir.domain.models import Person
from noir.investigation.interviews import InterviewState
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import PresentationCase, WitnessStatement
from noir.presentation.projector import project_case
from noir.truth.graph import TruthState
from noir.util.rng import Rng
from noir.cli.support import dialog_role_key_for_witness, maybe_print_investigation_guidance


def test_cli_prompt_resolves_staff_witness_graph() -> None:
    truth = TruthState(case_id="case_cli_staff", seed=7)
    witness = Person(name="Mara Flint", role_tags=[RoleTag.WITNESS], traits={"witness_role": "security"})
    truth.add_person(witness)
    state = InvestigationState(interviews={str(witness.id): InterviewState()})

    role_key = dialog_role_key_for_witness(truth, state, witness.id)

    assert role_key == "staff"


def test_cli_prompt_resolves_intimate_relationship_graph() -> None:
    truth = TruthState(case_id="case_cli_intimate", seed=11)
    offender = Person(name="Rian Voss", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT])
    witness = Person(name="Nadia Vale", role_tags=[RoleTag.WITNESS])
    truth.add_person(offender)
    truth.add_person(witness)
    truth.add_relationship(witness.id, offender.id, "partner", "intimate")
    state = InvestigationState(interviews={str(witness.id): InterviewState()})

    role_key = dialog_role_key_for_witness(truth, state, witness.id)

    assert role_key == "intimate"


def test_cli_prints_guidance_lines_for_one_witness_opening(capsys) -> None:
    truth, case_facts = generate_case(Rng(41), case_id="case_cli_guidance")
    presentation = project_case(truth, Rng(41).fork("projection"))
    state = InvestigationState()
    state.leads = build_leads(presentation, start_time=state.time)
    board = DeductionBoard()
    witnesses = [
        person for person in truth.people.values() if RoleTag.WITNESS in person.role_tags
    ]

    assert len(witnesses) >= 2

    result = interview(
        truth,
        presentation,
        state,
        witnesses[0].id,
        case_facts["crime_scene_id"],
    )

    maybe_print_investigation_guidance(result, truth, presentation, state, board)

    output = capsys.readouterr().out
    assert "Guidance: One witness is only a starting point here." in output
    assert "Guidance: The case currently rests on testimony alone." in output


def test_dialog_prompt_hides_contradiction_until_unlocked() -> None:
    truth = TruthState(case_id="case_cli_contradiction", seed=17)
    scene = Location(name="Dock Warehouse")
    suspect = Person(name="Mara Flint", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT])
    witness = Person(name="Jon Vale", role_tags=[RoleTag.WITNESS])
    truth.add_location(scene)
    truth.add_person(suspect)
    truth.add_person(witness)
    truth.record_event(EventKind.KILL, 20, scene.id, participants=[suspect.id])
    state = InvestigationState(interviews={str(suspect.id): InterviewState()})
    presentation = PresentationCase(case_id="case_cli_contradiction", seed=17, evidence=[])

    _, _, hidden_options = visible_dialog_prompt_options(
        truth,
        presentation,
        state,
        suspect.id,
    )

    contradiction = WitnessStatement(
        evidence_type=EvidenceType.TESTIMONIAL,
        summary="Witness statement",
        source="Interview",
        time_collected=1,
        confidence=ConfidenceBand.MEDIUM,
        witness_id=witness.id,
        statement="I saw the suspect near the warehouse in the scene window.",
        reported_time_window=(20, 21),
        location_id=scene.id,
        observed_person_ids=[suspect.id],
        uncertainty_hooks=[],
    )
    presentation.evidence.append(contradiction)
    state.knowledge.known_evidence.append(contradiction.id)

    _, _, unlocked_options = visible_dialog_prompt_options(
        truth,
        presentation,
        state,
        suspect.id,
    )

    hidden_labels = [option.choice.text for option in hidden_options]
    unlocked_labels = [option.choice.text for option in unlocked_options]

    assert "Press the contradiction" not in hidden_labels
    assert "Press the contradiction" in unlocked_labels