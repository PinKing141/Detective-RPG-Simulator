"""Truth queries for Phase 0 investigations."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from noir.domain.enums import EventKind
from noir.truth.graph import TruthState
from noir.util.time import TimeWindow

MIN_TRAVEL_TIME = 1


def where_was(truth: TruthState, person_id: UUID, window: TimeWindow) -> list[UUID]:
    locations: list[UUID] = []
    for _, loc_id, data in truth.graph.edges(person_id, data=True):
        if data.get("edge_type") != "located_at":
            continue
        entry = data.get("entry_time")
        exit_time = data.get("exit_time", entry)
        if entry is None:
            continue
        edge_window = TimeWindow(start=entry, end=exit_time)
        if edge_window.overlaps(window):
            locations.append(loc_id)
    return locations


def events_in_window(
    truth: TruthState, kind: EventKind, start: int, end: int
) -> list:
    return [
        event
        for event in truth.events.values()
        if event.kind == kind and start <= event.timestamp <= end
    ]


def could_travel(from_loc: UUID, to_loc: UUID, window: TimeWindow) -> bool:
    if from_loc == to_loc:
        return True
    travel_window = window.normalized()
    return (travel_window.end - travel_window.start) >= MIN_TRAVEL_TIME


def has_precondition(truth: TruthState, event_id: UUID) -> bool:
    for _, _, data in truth.graph.edges(event_id, data=True):
        if data.get("edge_type") == "enabled_by":
            return True
    return False
