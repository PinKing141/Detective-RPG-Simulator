"""Shared pytest fixtures for Detective RPG Simulator tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path for all tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from noir.naming.names_db import load_name_generator
from noir.util.rng import Rng
from noir.world.state import WorldState


@pytest.fixture(autouse=True)
def patch_name_generator(monkeypatch):
    """
    Patch the name generator to use fallback names instead of the LFS-tracked
    SQLite database, which may be absent or a Git LFS pointer in CI.

    A fresh generator is injected before each test so that the usage-deque
    state does not accumulate across calls (which would break seed-replay
    determinism tests).
    """
    import noir.cases.truth_generator as tg

    def _fresh_name_context(rng):
        """Return a name context from a stateless generator each call."""
        fresh_ng = load_name_generator(path=Path("/nonexistent/names.db"))
        return fresh_ng.start_case(rng)

    monkeypatch.setattr(tg, "_name_context", _fresh_name_context)
    yield


@pytest.fixture
def rng42():
    return Rng(seed=42)


@pytest.fixture
def rng99():
    return Rng(seed=99)


@pytest.fixture
def default_world():
    return WorldState()


@pytest.fixture
def generated_case(rng42):
    from noir.cases.truth_generator import generate_case

    truth, meta = generate_case(rng42, case_id="test-case-42")
    return truth, meta


@pytest.fixture
def projected_case(generated_case, rng42):
    from noir.presentation.projector import project_case

    truth, _ = generated_case
    return project_case(truth, Rng(seed=42))


@pytest.fixture
def tmp_save_dir(tmp_path):
    return tmp_path
