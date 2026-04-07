"""
Investigation action cost tests.

Verifies that time/pressure costs are applied correctly, limits block
actions, and state transitions behave as documented in RULES.md.
"""

from __future__ import annotations

import pytest

from noir.cases.truth_generator import generate_case
from noir.investigation.costs import (
    COSTS,
    ActionCost,
    PRESSURE_LIMIT,
    TIME_LIMIT,
    ActionType,
    clamp,
    would_exceed_limits,
)
from noir.investigation.leads import build_leads
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.projector import project_case
from noir.util.rng import Rng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_state():
    return InvestigationState()


@pytest.fixture
def truth_pcase():
    truth, _ = generate_case(Rng(seed=42), case_id="cost-test")
    pcase = project_case(truth, Rng(seed=42))
    return truth, pcase


# ---------------------------------------------------------------------------
# Tests: clamp utility
# ---------------------------------------------------------------------------


class TestClamp:
    def test_clamp_below_min(self):
        assert clamp(-5, 0, 10) == 0

    def test_clamp_above_max(self):
        assert clamp(15, 0, 10) == 10

    def test_clamp_within_range(self):
        assert clamp(5, 0, 10) == 5

    def test_clamp_at_boundary(self):
        assert clamp(0, 0, 10) == 0
        assert clamp(10, 0, 10) == 10


# ---------------------------------------------------------------------------
# Tests: would_exceed_limits
# ---------------------------------------------------------------------------


class TestWouldExceedLimits:
    def test_fresh_state_does_not_exceed(self, fresh_state):
        cost = COSTS[ActionType.VISIT_LOCATION]
        blocked, _ = would_exceed_limits(fresh_state.time, fresh_state.pressure, cost)
        assert not blocked

    def test_maxed_pressure_blocks_action(self, fresh_state):
        # Use ARREST (pressure=2) so any positive pressure cost triggers block at limit
        fresh_state.pressure = PRESSURE_LIMIT
        cost = COSTS[ActionType.ARREST]
        blocked, reason = would_exceed_limits(fresh_state.time, fresh_state.pressure, cost)
        assert blocked
        assert reason

    def test_maxed_time_blocks_action(self, fresh_state):
        fresh_state.time = TIME_LIMIT
        cost = COSTS[ActionType.VISIT_LOCATION]
        blocked, reason = would_exceed_limits(fresh_state.time, fresh_state.pressure, cost)
        assert blocked
        assert reason

    def test_near_limit_still_allowed(self, fresh_state):
        fresh_state.pressure = PRESSURE_LIMIT - 1
        fresh_state.time = TIME_LIMIT - 1
        cost = ActionCost(time=1, pressure=1)
        blocked, _ = would_exceed_limits(fresh_state.time, fresh_state.pressure, cost)
        assert not blocked


# ---------------------------------------------------------------------------
# Tests: cost values are positive and defined for all action types
# ---------------------------------------------------------------------------


class TestCostDefinitions:
    def test_all_action_types_have_costs(self):
        for action_type in ActionType:
            assert action_type in COSTS, f"No cost defined for {action_type}"

    def test_time_costs_are_positive(self):
        for action_type, cost in COSTS.items():
            assert cost.time >= 0, f"{action_type} has negative time cost"

    def test_pressure_costs_are_non_negative(self):
        for action_type, cost in COSTS.items():
            assert cost.pressure >= 0, f"{action_type} has negative pressure cost"

    def test_interview_has_higher_cost_than_or_equal_to_visit(self):
        interview_cost = COSTS[ActionType.INTERVIEW]
        visit_cost = COSTS[ActionType.VISIT_LOCATION]
        assert interview_cost.time >= visit_cost.time


# ---------------------------------------------------------------------------
# Tests: visit_location applies costs
# ---------------------------------------------------------------------------


class TestVisitLocationCosts:
    def _primary_location_id(self, truth):
        """Return the first location UUID from TruthState."""
        return next(iter(truth.locations))

    def test_visit_advances_time(self, truth_pcase, fresh_state):
        from noir.investigation.actions import visit_location

        truth, pcase = truth_pcase
        initial_time = fresh_state.time
        result = visit_location(fresh_state, self._primary_location_id(truth))
        assert fresh_state.time > initial_time

    def test_visit_returns_success_on_fresh_state(self, truth_pcase, fresh_state):
        from noir.investigation.actions import visit_location

        truth, pcase = truth_pcase
        result = visit_location(fresh_state, self._primary_location_id(truth))
        assert result.outcome == ActionOutcome.SUCCESS

    def test_visit_blocked_when_time_limit_reached(self, truth_pcase, fresh_state):
        from noir.investigation.actions import visit_location

        truth, pcase = truth_pcase
        fresh_state.time = TIME_LIMIT
        result = visit_location(fresh_state, self._primary_location_id(truth))
        assert result.outcome == ActionOutcome.FAILURE


# ---------------------------------------------------------------------------
# Tests: lead deadlines
# ---------------------------------------------------------------------------


class TestLeadDeadlines:
    def test_leads_created_with_future_deadlines(self, truth_pcase, fresh_state):
        _, pcase = truth_pcase
        leads = build_leads(pcase, start_time=0)
        for lead in leads:
            assert lead.deadline > 0

    def test_leads_are_initially_active(self, truth_pcase, fresh_state):
        from noir.investigation.leads import LeadStatus

        _, pcase = truth_pcase
        leads = build_leads(pcase, start_time=0)
        for lead in leads:
            assert lead.status == LeadStatus.ACTIVE

    def test_deadline_delta_shortens_window(self, truth_pcase):
        _, pcase = truth_pcase
        leads_normal = build_leads(pcase, start_time=0, deadline_delta=0)
        leads_short = build_leads(pcase, start_time=0, deadline_delta=1)
        for l_n, l_s in zip(leads_normal, leads_short):
            assert l_s.deadline <= l_n.deadline
