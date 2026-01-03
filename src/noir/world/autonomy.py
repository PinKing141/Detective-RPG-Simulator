"""Autonomous event scheduler for Phase 3 continuity."""

from __future__ import annotations

from dataclasses import dataclass

from noir.investigation.costs import PRESSURE_LIMIT, clamp
from noir.investigation.results import InvestigationState
from noir.world.state import DistrictStatus, WorldState


@dataclass(frozen=True)
class AutonomyEvent:
    key: str
    trigger_time: int
    note: str
    pressure_delta: int = 0
    cooperation_delta: float = 0.0


BASE_EVENTS: list[AutonomyEvent] = [
    AutonomyEvent(
        key="media_attention",
        trigger_time=2,
        note="Media attention spikes while you wait.",
        pressure_delta=1,
    ),
    AutonomyEvent(
        key="witness_fatigue",
        trigger_time=4,
        note="Witness cooperation softens as time passes.",
        cooperation_delta=-0.1,
    ),
    AutonomyEvent(
        key="secondary_incident",
        trigger_time=6,
        note="A fresh incident hits the desk, stretching resources.",
        pressure_delta=1,
    ),
]


def apply_autonomy(
    state: InvestigationState, world: WorldState, district: str
) -> list[str]:
    status = world.district_status_for(district)
    schedule = _schedule_for_status(status)
    notes: list[str] = []
    for event in schedule:
        if event.key in state.autonomy_marks:
            continue
        if state.time < event.trigger_time:
            continue
        state.autonomy_marks.add(event.key)
        if event.pressure_delta:
            state.pressure = int(
                clamp(state.pressure + event.pressure_delta, 0, PRESSURE_LIMIT)
            )
        if event.cooperation_delta:
            state.cooperation = clamp(
                state.cooperation + event.cooperation_delta, 0.0, 1.0
            )
        notes.append(event.note)
    return notes


def _schedule_for_status(status: DistrictStatus) -> list[AutonomyEvent]:
    if status == DistrictStatus.VOLATILE:
        shift = -1
    elif status == DistrictStatus.CALM:
        shift = 1
    else:
        shift = 0
    schedule: list[AutonomyEvent] = []
    for event in BASE_EVENTS:
        trigger = max(1, event.trigger_time + shift)
        schedule.append(
            AutonomyEvent(
                key=event.key,
                trigger_time=trigger,
                note=event.note,
                pressure_delta=event.pressure_delta,
                cooperation_delta=event.cooperation_delta,
            )
        )
    return schedule
