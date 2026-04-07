from noir.domain.enums import RoleTag
from noir.cases.truth_generator import generate_case
from noir.investigation.actions import follow_neighbor_lead
from noir.investigation.dialog_graph import load_interview_graph, resolve_dialog_role_key
from noir.investigation.leads import NeighborLead
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import PresentationCase
from noir.util.rng import Rng


def test_role_specific_interview_graphs_load() -> None:
    for role_key in (
        "default",
        "neighbor",
        "hostile_witness",
        "suspect",
        "staff",
        "passerby",
        "intimate",
    ):
        graph = load_interview_graph(role_key)
        assert graph is not None
        assert graph.root_node_id == "START"
        assert graph.has_node("BASELINE_PRESENCE")
        assert graph.has_node("THEME_ACCIDENTAL_AFTER")


def test_dialog_role_resolution_prefers_live_persona_signals() -> None:
    assert resolve_dialog_role_key([RoleTag.OFFENDER], {}, motive_to_lie=False) == "suspect"
    assert resolve_dialog_role_key([RoleTag.WITNESS], {"witness_role": "neighbor"}, motive_to_lie=False) == "neighbor"
    assert resolve_dialog_role_key([RoleTag.WITNESS], {"witness_role": "security"}, motive_to_lie=False) == "staff"
    assert resolve_dialog_role_key([RoleTag.WITNESS], {"witness_role": "commuter"}, motive_to_lie=False) == "passerby"
    assert resolve_dialog_role_key(
        [RoleTag.WITNESS],
        {},
        motive_to_lie=False,
        relationship_closeness="intimate",
        relationship_type="partner",
    ) == "intimate"
    assert resolve_dialog_role_key([RoleTag.WITNESS], {}, motive_to_lie=True) == "hostile_witness"
    assert resolve_dialog_role_key([RoleTag.WITNESS], {}, motive_to_lie=False) == "default"


def test_follow_neighbor_lead_uses_role_specific_witness_lines() -> None:
    truth, case_facts = generate_case(Rng(31), case_id="case_dialog_staff")
    presentation = PresentationCase(case_id="case_dialog_staff", seed=31, evidence=[])
    lead = NeighborLead(
        slot_id="staff:1",
        label="Security witness",
        hearing_bias=0.65,
        witness_roles={"security": 1.0},
    )
    state = InvestigationState(neighbor_leads=[lead])

    result = follow_neighbor_lead(
        truth,
        presentation,
        state,
        case_facts["crime_scene_id"],
        lead,
    )

    assert result.outcome.value == "success"
    assert result.revealed
    statement = result.revealed[0].statement.lower()
    assert statement.startswith("as a security")
    assert any(
        token in statement
        for token in ("cameras", "service route", "closing up", "back area", "staff")
    )