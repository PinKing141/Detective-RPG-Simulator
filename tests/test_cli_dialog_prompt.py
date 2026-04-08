from noir.cases.truth_generator import generate_case
from noir.deduction.board import DeductionBoard
from noir.domain.enums import RoleTag
from noir.investigation.actions import interview
from noir.investigation.leads import build_leads
from noir.domain.models import Person
from noir.investigation.interviews import InterviewState
from noir.investigation.results import InvestigationState
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