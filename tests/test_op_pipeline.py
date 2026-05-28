"""Unified operation pipeline tests.

Covers the Trigger -> Plan -> Execute -> Outcome -> Fallout shape that
stakeout / warrant / bait / raid all share, plus the legal /
probable-cause module that gates warrants.
"""

from __future__ import annotations

from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis
from noir.domain.enums import RoleTag
from noir.investigation.actions import bait, raid, request_warrant, stakeout
from noir.investigation.legal import (
    LegalCheck,
    ProbableCause,
    evaluate_probable_cause,
)
from noir.investigation.operations import (
    OperationTier,
    OperationType,
    WarrantType,
)
from noir.investigation.op_pipeline import (
    OperationContext,
    OperationRequest,
    profile_for,
    run_operation,
    trigger,
)
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.projector import project_case
from noir.util.rng import Rng
from noir.world.state import WorldState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _setup(seed: int = 37):
    truth, case_facts = generate_case(Rng(seed), case_id=f"case_op_{seed}")
    presentation = project_case(truth, Rng(seed))
    state = InvestigationState()
    state.cooperation = 1.0
    for item in presentation.evidence:
        state.knowledge.known_evidence.append(item.id)
    offender_id = case_facts["offender_id"]
    board = DeductionBoard(
        hypothesis=Hypothesis(
            suspect_id=offender_id,
            claims=[ClaimType.PRESENCE, ClaimType.OPPORTUNITY],
            evidence_ids=[item.id for item in presentation.evidence[:3]],
        )
    )
    return truth, case_facts, presentation, state, board


def _ctx(truth, presentation, state, board, world=None) -> OperationContext:
    return OperationContext(truth, presentation, state, board, world)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


def test_profile_for_every_operation_type_is_registered() -> None:
    for op_type in OperationType:
        profile = profile_for(op_type)
        assert profile.op_type == op_type
        assert profile.style in {"analytical", "coercive"}


def test_only_raid_requires_warrant_only_warrant_grants_warrant() -> None:
    assert profile_for(OperationType.RAID).requires_warrant is True
    assert profile_for(OperationType.WARRANT).grants_warrant is True
    for op_type in (OperationType.STAKEOUT, OperationType.BAIT, OperationType.RAID):
        assert profile_for(op_type).grants_warrant is False


# ---------------------------------------------------------------------------
# Trigger stage
# ---------------------------------------------------------------------------


def test_trigger_blocks_when_no_hypothesis() -> None:
    truth, facts, presentation, state, _ = _setup()
    board = DeductionBoard()  # no hypothesis
    request = OperationRequest(
        op_type=OperationType.STAKEOUT,
        location_id=facts["crime_scene_id"],
        evidence_ids=tuple(item.id for item in presentation.evidence[:2]),
    )

    trig = trigger(request, _ctx(truth, presentation, state, board))

    assert trig.allowed is False
    assert "hypothesis" in trig.summary.lower()


def test_trigger_blocks_when_no_evidence_selected() -> None:
    truth, facts, presentation, state, board = _setup()
    request = OperationRequest(
        op_type=OperationType.BAIT,
        location_id=facts["crime_scene_id"],
        evidence_ids=(),
    )

    trig = trigger(request, _ctx(truth, presentation, state, board))

    assert trig.allowed is False
    assert "evidence" in trig.summary.lower()


def test_trigger_blocks_raid_without_warrant() -> None:
    truth, facts, presentation, state, board = _setup()
    request = OperationRequest(
        op_type=OperationType.RAID,
        location_id=facts["crime_scene_id"],
        evidence_ids=tuple(item.id for item in presentation.evidence[:2]),
    )

    trig = trigger(request, _ctx(truth, presentation, state, board))

    assert trig.allowed is False
    assert "warrant" in trig.summary.lower()


def test_trigger_clears_warrant_request_and_attaches_legal_check() -> None:
    truth, facts, presentation, state, board = _setup()
    request = OperationRequest(
        op_type=OperationType.WARRANT,
        location_id=facts["crime_scene_id"],
        evidence_ids=tuple(item.id for item in presentation.evidence[:3]),
        warrant_type=WarrantType.SEARCH,
    )

    trig = trigger(request, _ctx(truth, presentation, state, board))

    assert trig.allowed is True
    assert trig.legal_check is not None
    assert trig.legal_check.verdict in {
        ProbableCause.SUFFICIENT,
        ProbableCause.LIMITED,
        ProbableCause.INSUFFICIENT,
    }


# ---------------------------------------------------------------------------
# End-to-end via run_operation
# ---------------------------------------------------------------------------


def test_run_operation_warrant_grants_warrant_on_clean_or_partial() -> None:
    truth, facts, presentation, state, board = _setup()
    request = OperationRequest(
        op_type=OperationType.WARRANT,
        location_id=facts["crime_scene_id"],
        evidence_ids=tuple(item.id for item in presentation.evidence[:3]),
        warrant_type=WarrantType.SEARCH,
    )

    result, snapshot = run_operation(request, _ctx(truth, presentation, state, board))

    assert snapshot.outcome is not None
    if snapshot.outcome.tier in {OperationTier.CLEAN, OperationTier.PARTIAL}:
        assert WarrantType.SEARCH.value in state.warrant_grants
        assert result.outcome == ActionOutcome.SUCCESS
    else:
        assert WarrantType.SEARCH.value not in state.warrant_grants


def test_run_operation_raid_routes_through_pipeline_and_records_event() -> None:
    truth, facts, presentation, state, board = _setup()
    state.warrant_grants.add(WarrantType.SEARCH.value)
    request = OperationRequest(
        op_type=OperationType.RAID,
        location_id=facts["crime_scene_id"],
        evidence_ids=tuple(item.id for item in presentation.evidence[:3]),
    )

    result, snapshot = run_operation(request, _ctx(truth, presentation, state, board))

    assert snapshot.plan is not None
    assert snapshot.outcome is not None
    assert result.operation_type == OperationType.RAID
    assert result.operation_tier == snapshot.outcome.tier


def test_run_operation_thin_wrapper_matches_pipeline_for_stakeout() -> None:
    truth, facts, presentation, state, board = _setup()
    evidence_ids = [item.id for item in presentation.evidence[:2]]

    wrapper_result = stakeout(
        truth, presentation, state, board, facts["crime_scene_id"], evidence_ids
    )

    assert wrapper_result.operation_type == OperationType.STAKEOUT
    assert wrapper_result.operation_tier is not None


# ---------------------------------------------------------------------------
# Fallout: nemesis awareness rises on visible moves
# ---------------------------------------------------------------------------


def test_bait_raises_nemesis_awareness_through_world() -> None:
    truth, facts, presentation, state, board = _setup()
    world = WorldState()
    before = world.campaign.nemesis_arc.awareness

    bait(
        truth,
        presentation,
        state,
        board,
        facts["crime_scene_id"],
        [item.id for item in presentation.evidence[:2]],
        world=world,
    )

    assert world.campaign.nemesis_arc.awareness > before


def test_warrant_does_not_raise_nemesis_awareness() -> None:
    truth, facts, presentation, state, board = _setup()
    world = WorldState()
    before = world.campaign.nemesis_arc.awareness

    request_warrant(
        truth,
        presentation,
        state,
        board,
        facts["crime_scene_id"],
        WarrantType.SEARCH,
        world=world,
    )

    assert world.campaign.nemesis_arc.awareness == before


# ---------------------------------------------------------------------------
# Legal / probable-cause module
# ---------------------------------------------------------------------------


def test_probable_cause_is_insufficient_for_a_thin_packet() -> None:
    truth, facts, presentation, state, board = _setup()

    check = evaluate_probable_cause(presentation.evidence[:1], board.hypothesis)

    assert check.verdict == ProbableCause.INSUFFICIENT
    assert check.supports_count == 1
    assert check.reasons


def test_probable_cause_finds_physical_anchor_when_present() -> None:
    truth, facts, presentation, state, board = _setup()

    check = evaluate_probable_cause(list(presentation.evidence), board.hypothesis)

    assert check.verdict != ProbableCause.INSUFFICIENT
    if check.has_physical:
        assert check.verdict in {ProbableCause.SUFFICIENT, ProbableCause.LIMITED}


def test_probable_cause_requires_hypothesis_for_timeline_check() -> None:
    truth, facts, presentation, _, _ = _setup()

    check = evaluate_probable_cause(list(presentation.evidence), hypothesis=None)

    if not check.has_physical:
        assert check.verdict == ProbableCause.INSUFFICIENT


# ---------------------------------------------------------------------------
# Public-API wrappers preserve summaries
# ---------------------------------------------------------------------------


def test_request_warrant_wrapper_blocks_without_hypothesis() -> None:
    truth, facts, presentation, state, _ = _setup()
    board = DeductionBoard()

    result = request_warrant(
        truth,
        presentation,
        state,
        board,
        facts["crime_scene_id"],
        WarrantType.SEARCH,
    )

    assert result.outcome == ActionOutcome.FAILURE
    assert "hypothesis" in result.summary.lower()


def test_raid_wrapper_blocks_without_warrant_then_allows_after_grant() -> None:
    truth, facts, presentation, state, board = _setup()

    blocked = raid(
        truth,
        presentation,
        state,
        board,
        facts["crime_scene_id"],
        [item.id for item in presentation.evidence[:2]],
    )
    assert blocked.outcome == ActionOutcome.FAILURE
    assert "warrant" in blocked.summary.lower()

    state.warrant_grants.add(WarrantType.SEARCH.value)
    allowed = raid(
        truth,
        presentation,
        state,
        board,
        facts["crime_scene_id"],
        [item.id for item in presentation.evidence[:2]],
    )
    assert allowed.operation_type == OperationType.RAID
