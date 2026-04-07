"""
Projector fairness tests.

The projector must:
- Apply temporal fuzzing (time windows should not exactly match truth)
- Not directly expose the offender's ID in evidence without player action
- Assign confidence bands to evidence items
- Produce stable output for the same seed

These tests protect against regressions where the projector leaks truth
state directly into presentation or loses its fuzzing properties.
"""

from __future__ import annotations

import pytest

from noir.cases.truth_generator import generate_case
from noir.domain.enums import ConfidenceBand, EventKind, RoleTag
from noir.presentation.evidence import ForensicObservation, WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=[42, 99, 1337])
def truth_and_pcase(request):
    truth, _ = generate_case(Rng(seed=request.param), case_id=f"fair-{request.param}")
    pcase = project_case(truth, Rng(seed=request.param))
    return truth, pcase


# ---------------------------------------------------------------------------
# Tests: evidence structure
# ---------------------------------------------------------------------------


class TestEvidenceStructure:
    def test_projected_case_has_evidence(self, truth_and_pcase):
        _, pcase = truth_and_pcase
        assert len(pcase.evidence) > 0

    def test_all_evidence_has_confidence_band(self, truth_and_pcase):
        _, pcase = truth_and_pcase
        valid_bands = set(ConfidenceBand)
        for item in pcase.evidence:
            assert item.confidence in valid_bands

    def test_all_evidence_has_summary(self, truth_and_pcase):
        _, pcase = truth_and_pcase
        for item in pcase.evidence:
            assert item.summary and item.summary.strip()

    def test_all_evidence_has_source(self, truth_and_pcase):
        _, pcase = truth_and_pcase
        for item in pcase.evidence:
            assert item.source and item.source.strip()

    def test_case_id_is_preserved(self, truth_and_pcase):
        _, pcase = truth_and_pcase
        assert pcase.case_id


# ---------------------------------------------------------------------------
# Tests: temporal fuzzing
# ---------------------------------------------------------------------------


class TestTemporalFuzzing:
    def test_witness_time_windows_are_within_plausible_range(self, truth_and_pcase):
        truth, pcase = truth_and_pcase
        kill_events = [e for e in truth.events.values() if e.kind == EventKind.KILL]
        if not kill_events:
            pytest.skip("No kill event in case")
        kill_time = kill_events[0].timestamp
        witnesses = [e for e in pcase.evidence if isinstance(e, WitnessStatement)]
        for ws in witnesses:
            lo, hi = ws.reported_time_window
            assert lo <= hi, "Time window must be ordered"
            # Window should not be impossibly far from truth (within ±10 units)
            assert abs(lo - kill_time) <= 10 or abs(hi - kill_time) <= 10

    def test_witness_time_windows_have_valid_order(self, truth_and_pcase):
        """All time windows must be ordered (lo <= hi) — basic fuzzing sanity."""
        _, pcase = truth_and_pcase
        witnesses = [e for e in pcase.evidence if isinstance(e, WitnessStatement)]
        if not witnesses:
            pytest.skip("No witness statements in projected case")
        for ws in witnesses:
            lo, hi = ws.reported_time_window
            assert lo <= hi, f"Time window is inverted: ({lo}, {hi})"


# ---------------------------------------------------------------------------
# Tests: offender identity protection
# ---------------------------------------------------------------------------


class TestOffenderIdentityProtection:
    def test_witness_statements_do_not_declare_guilt_explicitly(
        self, truth_and_pcase
    ):
        """
        Witness statement TEXT should not contain explicit guilt language
        (e.g., "murderer", "killed", "did it"). The player must reason from
        observations to conclusions. observed_person_ids may legitimately
        contain the offender when a witness saw them.
        """
        _, pcase = truth_and_pcase
        guilt_words = {"murderer", "killer", "killed", "did it", "committed"}
        for item in pcase.evidence:
            if isinstance(item, WitnessStatement):
                statement_lower = item.statement.lower()
                for word in guilt_words:
                    assert word not in statement_lower, (
                        f"Explicit guilt language '{word}' found in witness statement"
                    )

    def test_forensic_observations_do_not_name_offender(self, truth_and_pcase):
        """Forensic observations should not contain the offender's name in the finding."""
        truth, pcase = truth_and_pcase
        offender = next(
            p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags
        )
        for item in pcase.evidence:
            if isinstance(item, ForensicObservation):
                assert offender.name not in item.observation, (
                    f"Offender name '{offender.name}' appears in forensic observation"
                )


# ---------------------------------------------------------------------------
# Tests: confidence band distribution
# ---------------------------------------------------------------------------


class TestConfidenceBandDistribution:
    def test_not_all_evidence_is_high_confidence(self, truth_and_pcase):
        """
        A well-calibrated projector should produce a mix of confidence bands,
        not mark everything as STRONG.
        """
        _, pcase = truth_and_pcase
        if len(pcase.evidence) < 2:
            pytest.skip("Too little evidence to test distribution")
        bands = {item.confidence for item in pcase.evidence}
        assert ConfidenceBand.STRONG not in bands or len(bands) > 1, (
            "All evidence is STRONG — projector may not be applying noise"
        )
