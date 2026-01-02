"""ID helpers for deterministic entity creation."""

from __future__ import annotations

from uuid import UUID, uuid4


def new_id() -> UUID:
    return uuid4()
