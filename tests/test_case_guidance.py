from noir.cases.truth_generator import generate_case
from noir.investigation.actions import interview
from noir.investigation.guidance import investigation_guidance_lines
from noir.investigation.leads import build_leads
from noir.investigation.results import InvestigationState
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def test_one_witness_first_path_surfaces_stronger_guidance() -> None:
    truth, case_facts = generate_case(Rng(41), case_id="case_guidance_first_witness")
    presentation = project_case(truth, Rng(41).fork("projection"))
    state = InvestigationState()
    state.leads = build_leads(presentation, start_time=state.time)

    witnesses = [person for person in truth.people.values() if "witness" in {tag.value for tag in person.role_tags}]
    assert len(witnesses) >= 2

    interview(
        truth,
        presentation,
        state,
        witnesses[0].id,
        case_facts["crime_scene_id"],
    )

    lines = investigation_guidance_lines(truth, presentation, state)

    assert any("other witnesses" in line.lower() for line in lines)
    assert any("testimony alone" in line.lower() or "lab work" in line.lower() for line in lines)