"""Invariant checks for Truth state."""

from __future__ import annotations

from typing import Mapping
from uuid import UUID


def ensure_entity_exists(entity_id: UUID, entity_map: Mapping[UUID, object], label: str) -> None:
    if entity_id not in entity_map:
        raise KeyError(f"Unknown {label} id: {entity_id}")


def validate_time_interval(start: int, end: int | None) -> None:
    if end is not None and end < start:
        raise ValueError("end time must be >= start time")
