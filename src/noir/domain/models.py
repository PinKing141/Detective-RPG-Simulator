"""Domain models for canonical Truth."""

from __future__ import annotations

from typing import Dict, List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from noir.domain.enums import EventKind, ItemType, RoleTag


class GameEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    name: str


class Person(GameEntity):
    age_range: str = "adult"
    role_tags: List[RoleTag] = Field(default_factory=list)
    traits: Dict[str, float | str] = Field(default_factory=dict)


class Location(GameEntity):
    district: str = "central"
    access_level: str = "public"
    tags: List[str] = Field(default_factory=list)


class Item(GameEntity):
    item_type: ItemType = ItemType.PERSONAL
    properties: Dict[str, str] = Field(default_factory=dict)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: EventKind
    timestamp: int
    location_id: UUID
    participants: List[UUID] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)
