"""
Persistence and save/load round-trip tests.

Covers:
- WorldStore: world state persists and reloads correctly
- WorldStore: case history records survive round-trip
- save_load: investigation state serializes and restores without loss
- save_load: PresentationCase evidence survives round-trip
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from noir.persistence.db import WorldStore
from noir.persistence.save_load import (
    delete_save,
    has_save,
    load_investigation,
    save_investigation,
)
from noir.world.state import CaseRecord, WorldState


# ---------------------------------------------------------------------------
# WorldStore tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    path = tmp_path / "test_world.db"
    store = WorldStore(path)
    yield store
    store.close()


class TestWorldStoreRoundTrip:
    def test_fresh_load_returns_default_state(self, tmp_db):
        state = tmp_db.load_world_state()
        assert isinstance(state, WorldState)
        assert state.trust >= 0
        assert state.pressure >= 0

    def test_trust_persists(self, tmp_db):
        state = tmp_db.load_world_state()
        state.trust = 4
        tmp_db.save_world_state(state)
        reloaded = tmp_db.load_world_state()
        assert reloaded.trust == 4

    def test_pressure_persists(self, tmp_db):
        state = tmp_db.load_world_state()
        state.pressure = 3
        tmp_db.save_world_state(state)
        reloaded = tmp_db.load_world_state()
        assert reloaded.pressure == 3

    def test_tick_persists(self, tmp_db):
        state = tmp_db.load_world_state()
        state.tick = 7
        tmp_db.save_world_state(state)
        reloaded = tmp_db.load_world_state()
        assert reloaded.tick == 7

    def test_nemesis_exposure_persists(self, tmp_db):
        state = tmp_db.load_world_state()
        state.nemesis_exposure = 2
        tmp_db.save_world_state(state)
        reloaded = tmp_db.load_world_state()
        assert reloaded.nemesis_exposure == 2

    def test_multiple_saves_use_latest(self, tmp_db):
        state = tmp_db.load_world_state()
        state.trust = 1
        tmp_db.save_world_state(state)
        state.trust = 5
        tmp_db.save_world_state(state)
        reloaded = tmp_db.load_world_state()
        assert reloaded.trust == 5


class TestCaseHistory:
    def _make_record(self, seed=42) -> CaseRecord:
        return CaseRecord(
            case_id=str(uuid4()),
            seed=seed,
            district="harbor",
            started_tick=0,
            ended_tick=5,
            outcome="clean_arrest",
            trust_delta=1,
            pressure_delta=-1,
            notes=["First arrest", "Nemesis sighted"],
        )

    def test_record_case_survives_reload(self, tmp_db):
        tmp_db.load_world_state()  # initialize world_state row
        record = self._make_record()
        tmp_db.record_case(record)
        state = tmp_db.load_world_state()
        ids = [r.case_id for r in state.case_history]
        assert record.case_id in ids

    def test_case_fields_are_preserved(self, tmp_db):
        tmp_db.load_world_state()  # initialize world_state row
        record = self._make_record(seed=99)
        tmp_db.record_case(record)
        state = tmp_db.load_world_state()
        stored = next(r for r in state.case_history if r.case_id == record.case_id)
        assert stored.seed == 99
        assert stored.district == "harbor"
        assert stored.outcome == "clean_arrest"
        assert stored.trust_delta == 1
        assert stored.pressure_delta == -1

    def test_notes_are_preserved(self, tmp_db):
        tmp_db.load_world_state()  # initialize world_state row
        record = self._make_record()
        tmp_db.record_case(record)
        state = tmp_db.load_world_state()
        stored = next(r for r in state.case_history if r.case_id == record.case_id)
        assert "First arrest" in stored.notes
        assert "Nemesis sighted" in stored.notes

    def test_reset_clears_history(self, tmp_db):
        record = self._make_record()
        tmp_db.record_case(record)
        tmp_db.reset_world_state()
        state = tmp_db.load_world_state()
        assert len(state.case_history) == 0


# ---------------------------------------------------------------------------
# save_load round-trip tests
# ---------------------------------------------------------------------------


@pytest.fixture
def full_investigation(generated_case, projected_case):
    """A generated truth + projected case with a minimal InvestigationState."""
    from noir.investigation.results import InvestigationState
    from noir.investigation.leads import build_leads

    truth, meta = generated_case
    pcase = projected_case
    state = InvestigationState()
    state.time = 3
    state.pressure = 1
    state.trust = 2
    state.cooperation = 0.8
    state.autonomy_marks = {"coercive"}
    state.knowledge.notes.append("Something suspicious about the timeline.")
    state.analyst_notes = ["Offender has high competence rating."]
    state.warrant_grants = {"warrant_001"}
    state.leads = build_leads(pcase, start_time=0)
    return truth, meta, pcase, state


class TestSaveLoadRoundTrip:
    def test_has_save_false_before_saving(self, tmp_path, full_investigation):
        _, meta, _, _ = full_investigation
        case_id = meta["case_id"]
        assert not has_save(case_id, base=tmp_path)

    def test_save_creates_file(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        assert has_save(meta["case_id"], base=tmp_path)

    def test_load_returns_none_when_no_save(self, tmp_path, full_investigation):
        _, meta, _, _ = full_investigation
        result = load_investigation(meta["case_id"], base=tmp_path)
        assert result is None

    def test_seed_survives_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        seed, _, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert seed == pcase.seed

    def test_time_survives_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert restored_state.time == state.time

    def test_pressure_survives_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert restored_state.pressure == state.pressure

    def test_autonomy_marks_survive_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert restored_state.autonomy_marks == state.autonomy_marks

    def test_warrant_grants_survive_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert restored_state.warrant_grants == state.warrant_grants

    def test_analyst_notes_survive_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert restored_state.analyst_notes == state.analyst_notes

    def test_leads_survive_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, restored_state, _ = load_investigation(meta["case_id"], base=tmp_path)
        assert len(restored_state.leads) == len(state.leads)
        for orig, restored in zip(state.leads, restored_state.leads):
            assert orig.key == restored.key
            assert orig.deadline == restored.deadline
            assert orig.status == restored.status

    def test_evidence_count_survives_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, _, restored_pcase = load_investigation(meta["case_id"], base=tmp_path)
        assert len(restored_pcase.evidence) == len(pcase.evidence)

    def test_evidence_types_survive_round_trip(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        _, _, restored_pcase = load_investigation(meta["case_id"], base=tmp_path)
        orig_types = sorted(e.evidence_type.value for e in pcase.evidence)
        restored_types = sorted(e.evidence_type.value for e in restored_pcase.evidence)
        assert orig_types == restored_types

    def test_delete_save_removes_file(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        assert has_save(meta["case_id"], base=tmp_path)
        delete_save(meta["case_id"], base=tmp_path)
        assert not has_save(meta["case_id"], base=tmp_path)

    def test_load_after_delete_returns_none(self, tmp_path, full_investigation):
        _, meta, pcase, state = full_investigation
        save_investigation(meta["case_id"], pcase.seed, state, pcase, base=tmp_path)
        delete_save(meta["case_id"], base=tmp_path)
        assert load_investigation(meta["case_id"], base=tmp_path) is None
