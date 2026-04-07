"""
Structural invariants of TruthState.

Every generated case must satisfy these properties regardless of seed.
Violations here mean the case generator is broken at the root.
"""

from __future__ import annotations

import pytest

from noir.cases.truth_generator import generate_case
from noir.domain.enums import RoleTag
from noir.util.rng import Rng


@pytest.fixture(params=[1, 7, 42, 99, 1337])
def truth_and_meta(request):
    truth, meta = generate_case(Rng(seed=request.param), case_id=f"inv-{request.param}")
    return truth, meta


class TestPersonInvariants:
    def test_exactly_one_victim(self, truth_and_meta):
        truth, _ = truth_and_meta
        victims = [p for p in truth.people.values() if RoleTag.VICTIM in p.role_tags]
        assert len(victims) == 1

    def test_exactly_one_offender(self, truth_and_meta):
        truth, _ = truth_and_meta
        offenders = [p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags]
        assert len(offenders) == 1

    def test_offender_also_tagged_suspect(self, truth_and_meta):
        truth, _ = truth_and_meta
        offender = next(p for p in truth.people.values() if RoleTag.OFFENDER in p.role_tags)
        assert RoleTag.SUSPECT in offender.role_tags

    def test_victim_is_not_offender(self, truth_and_meta):
        truth, _ = truth_and_meta
        victim = next(p for p in truth.people.values() if RoleTag.VICTIM in p.role_tags)
        assert RoleTag.OFFENDER not in victim.role_tags

    def test_all_persons_have_non_empty_names(self, truth_and_meta):
        truth, _ = truth_and_meta
        for person in truth.people.values():
            assert person.name and person.name.strip()

    def test_all_persons_have_role_tags(self, truth_and_meta):
        truth, _ = truth_and_meta
        for person in truth.people.values():
            assert len(person.role_tags) >= 1

    def test_minimum_person_count(self, truth_and_meta):
        """At minimum: victim + offender + at least one witness."""
        truth, _ = truth_and_meta
        assert len(truth.people) >= 3

    def test_all_person_ids_are_unique(self, truth_and_meta):
        truth, _ = truth_and_meta
        ids = [p.id for p in truth.people.values()]
        assert len(ids) == len(set(ids))


class TestLocationInvariants:
    def test_at_least_one_location(self, truth_and_meta):
        truth, _ = truth_and_meta
        assert len(truth.locations) >= 1

    def test_primary_location_has_name(self, truth_and_meta):
        truth, meta = truth_and_meta
        from uuid import UUID
        primary_id = UUID(meta["primary_location_id"]) if isinstance(meta["primary_location_id"], str) else meta["primary_location_id"]
        loc = truth.locations.get(primary_id)
        assert loc is not None
        assert loc.name and loc.name.strip()

    def test_primary_location_has_id(self, truth_and_meta):
        truth, meta = truth_and_meta
        from uuid import UUID
        primary_id = UUID(meta["primary_location_id"]) if isinstance(meta["primary_location_id"], str) else meta["primary_location_id"]
        loc = truth.locations.get(primary_id)
        assert loc is not None
        assert loc.id is not None


class TestMetaInvariants:
    def test_motive_category_present(self, truth_and_meta):
        truth, _ = truth_and_meta
        assert "motive_category" in truth.case_meta
        assert truth.case_meta["motive_category"]

    def test_method_category_present(self, truth_and_meta):
        truth, _ = truth_and_meta
        assert truth.case_meta.get("method_category")

    def test_known_motive_values(self, truth_and_meta):
        truth, _ = truth_and_meta
        valid_motives = {"money", "revenge", "obsession", "concealment", "thrill"}
        assert truth.case_meta["motive_category"] in valid_motives


class TestEventInvariants:
    def test_at_least_one_event_recorded(self, truth_and_meta):
        truth, _ = truth_and_meta
        assert len(truth.events) >= 1

    def test_kill_event_exists(self, truth_and_meta):
        from noir.domain.enums import EventKind
        truth, _ = truth_and_meta
        kill_events = [e for e in truth.events.values() if e.kind == EventKind.KILL]
        assert len(kill_events) >= 1
