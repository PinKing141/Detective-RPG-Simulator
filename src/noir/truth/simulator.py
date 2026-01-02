"""Truth simulator hooks for investigation actions."""

from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from noir.domain.enums import EventKind
from noir.truth.graph import TruthState


def apply_action(
    truth: TruthState,
    kind: EventKind,
    timestamp: int,
    location_id: UUID,
    participants: Optional[Iterable[UUID]] = None,
    metadata: Optional[dict[str, str]] = None,
):
    return truth.record_event(
        kind=kind,
        timestamp=timestamp,
        location_id=location_id,
        participants=participants,
        metadata=metadata,
    )
