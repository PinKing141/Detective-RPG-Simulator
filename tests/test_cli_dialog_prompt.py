from noir.domain.enums import RoleTag
from noir.domain.models import Person
from noir.investigation.interviews import InterviewState
from noir.investigation.results import InvestigationState
from noir.truth.graph import TruthState
from scripts.run_game import _dialog_role_key_for_witness


def test_cli_prompt_resolves_staff_witness_graph() -> None:
    truth = TruthState(case_id="case_cli_staff", seed=7)
    witness = Person(name="Mara Flint", role_tags=[RoleTag.WITNESS], traits={"witness_role": "security"})
    truth.add_person(witness)
    state = InvestigationState(interviews={str(witness.id): InterviewState()})

    role_key = _dialog_role_key_for_witness(truth, state, witness.id)

    assert role_key == "staff"


def test_cli_prompt_resolves_intimate_relationship_graph() -> None:
    truth = TruthState(case_id="case_cli_intimate", seed=11)
    offender = Person(name="Rian Voss", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT])
    witness = Person(name="Nadia Vale", role_tags=[RoleTag.WITNESS])
    truth.add_person(offender)
    truth.add_person(witness)
    truth.add_relationship(witness.id, offender.id, "partner", "intimate")
    state = InvestigationState(interviews={str(witness.id): InterviewState()})

    role_key = _dialog_role_key_for_witness(truth, state, witness.id)

    assert role_key == "intimate"