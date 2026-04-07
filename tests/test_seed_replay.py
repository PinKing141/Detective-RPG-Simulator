"""
Seed determinism tests.

Guarantees: given the same seed, generate_case() produces byte-for-byte
identical TruthState structure every time. Different seeds produce
different cases. The presentation layer is also deterministic.
"""

from __future__ import annotations

import pytest

from noir.cases.truth_generator import generate_case
from noir.domain.enums import RoleTag
from noir.presentation.projector import project_case
from noir.util.rng import Rng


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fingerprint(truth) -> dict:
    """Stable structural fingerprint of a TruthState for equality checks."""
    people = sorted(
        (p.name, sorted(t.value for t in p.role_tags))
        for p in truth.people.values()
    )
    offender = next(
        (p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags),
        None,
    )
    victim = next(
        (p for p in truth.people.values() if RoleTag.VICTIM in p.role_tags),
        None,
    )
    primary_location = next(iter(truth.locations.values()), None)
    return {
        "people": people,
        "offender_name": offender.name if offender else None,
        "victim_name": victim.name if victim else None,
        "location_name": primary_location.name if primary_location else None,
        "person_count": len(truth.people),
    }


def _pcase_fingerprint(pcase) -> dict:
    return {
        "case_id": pcase.case_id,
        "seed": pcase.seed,
        "evidence_count": len(pcase.evidence),
        "evidence_types": sorted(e.evidence_type.value for e in pcase.evidence),
    }


# ---------------------------------------------------------------------------
# Tests: same seed -> identical output
# ---------------------------------------------------------------------------


class TestSameSeedProducesSameCase:
    def test_people_names_are_identical(self):
        t1, _ = generate_case(Rng(seed=1), case_id="c1")
        t2, _ = generate_case(Rng(seed=1), case_id="c1")
        names1 = sorted(p.name for p in t1.people.values())
        names2 = sorted(p.name for p in t2.people.values())
        assert names1 == names2

    def test_person_count_is_identical(self):
        t1, _ = generate_case(Rng(seed=7), case_id="c1")
        t2, _ = generate_case(Rng(seed=7), case_id="c1")
        assert len(t1.people) == len(t2.people)

    def test_offender_is_identical(self):
        t1, _ = generate_case(Rng(seed=13), case_id="c1")
        t2, _ = generate_case(Rng(seed=13), case_id="c1")
        off1 = next(p for p in t1.people.values() if RoleTag.OFFENDER in p.role_tags)
        off2 = next(p for p in t2.people.values() if RoleTag.OFFENDER in p.role_tags)
        assert off1.name == off2.name

    def test_victim_is_identical(self):
        t1, _ = generate_case(Rng(seed=21), case_id="c1")
        t2, _ = generate_case(Rng(seed=21), case_id="c1")
        v1 = next(p for p in t1.people.values() if RoleTag.VICTIM in p.role_tags)
        v2 = next(p for p in t2.people.values() if RoleTag.VICTIM in p.role_tags)
        assert v1.name == v2.name

    def test_location_is_identical(self):
        t1, _ = generate_case(Rng(seed=33), case_id="c1")
        t2, _ = generate_case(Rng(seed=33), case_id="c1")
        loc1 = next(iter(t1.locations.values()), None)
        loc2 = next(iter(t2.locations.values()), None)
        assert loc1 is not None and loc2 is not None
        assert loc1.name == loc2.name

    def test_full_fingerprint_matches(self):
        t1, _ = generate_case(Rng(seed=42), case_id="c1")
        t2, _ = generate_case(Rng(seed=42), case_id="c1")
        assert _fingerprint(t1) == _fingerprint(t2)

    def test_meta_motive_is_identical(self):
        _, m1 = generate_case(Rng(seed=55), case_id="c1")
        _, m2 = generate_case(Rng(seed=55), case_id="c1")
        assert m1.get("motive_category") == m2.get("motive_category")

    @pytest.mark.parametrize("seed", [1, 7, 42, 99, 1337, 9999])
    def test_multiple_seeds_are_self_consistent(self, seed):
        t1, m1 = generate_case(Rng(seed=seed), case_id="rep")
        t2, m2 = generate_case(Rng(seed=seed), case_id="rep")
        assert _fingerprint(t1) == _fingerprint(t2)
        assert m1.get("motive_category") == m2.get("motive_category")


# ---------------------------------------------------------------------------
# Tests: different seeds -> different cases
# ---------------------------------------------------------------------------


class TestDifferentSeedsProduceDifferentCases:
    def test_offenders_differ_across_seeds(self):
        """With high probability, two different seeds yield different offenders."""
        results = set()
        for seed in range(20):
            truth, _ = generate_case(Rng(seed=seed), case_id="x")
            offender = next(
                p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags
            )
            results.add(offender.name)
        assert len(results) >= 3

    def test_seeds_1_and_2_differ(self):
        t1, _ = generate_case(Rng(seed=1), case_id="c1")
        t2, _ = generate_case(Rng(seed=2), case_id="c1")
        assert _fingerprint(t1) != _fingerprint(t2)


# ---------------------------------------------------------------------------
# Tests: presentation layer determinism
# ---------------------------------------------------------------------------


class TestProjectionDeterminism:
    def test_same_seed_same_evidence_count(self):
        truth, _ = generate_case(Rng(seed=42), case_id="c1")
        pc1 = project_case(truth, Rng(seed=42))
        pc2 = project_case(truth, Rng(seed=42))
        assert len(pc1.evidence) == len(pc2.evidence)

    def test_same_seed_same_evidence_types(self):
        truth, _ = generate_case(Rng(seed=42), case_id="c1")
        pc1 = project_case(truth, Rng(seed=42))
        pc2 = project_case(truth, Rng(seed=42))
        types1 = sorted(e.evidence_type.value for e in pc1.evidence)
        types2 = sorted(e.evidence_type.value for e in pc2.evidence)
        assert types1 == types2

    def test_presentation_fingerprint_is_stable(self):
        truth, _ = generate_case(Rng(seed=77), case_id="c1")
        pc1 = project_case(truth, Rng(seed=77))
        pc2 = project_case(truth, Rng(seed=77))
        assert _pcase_fingerprint(pc1) == _pcase_fingerprint(pc2)
