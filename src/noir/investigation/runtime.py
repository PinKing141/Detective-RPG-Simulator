"""Shared runtime rule application for live investigation surfaces."""

from __future__ import annotations

from typing import Any

from noir.investigation.results import ActionOutcome, ActionResult, InvestigationState
from noir.nemesis import apply_nemesis_runtime_interference
from noir.world.autonomy import apply_autonomy
from noir.world.state import WorldState


def apply_runtime_rules(
    case_facts: dict[str, Any],
    state: InvestigationState,
    result: ActionResult,
    *,
    world: WorldState,
    district: str,
) -> ActionResult:
    nemesis_notes = apply_nemesis_runtime_interference(case_facts, state, result)
    autonomy_notes = apply_autonomy(state, world, district)
    if autonomy_notes:
        result.notes.extend(autonomy_notes)
    if nemesis_notes and result.outcome == ActionOutcome.SUCCESS:
        result.summary = f"{result.summary} Nemesis interference cuts into the result."
    return result