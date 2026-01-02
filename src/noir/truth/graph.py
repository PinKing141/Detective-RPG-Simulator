"""Truth graph wrapper around NetworkX."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional
from uuid import UUID

import networkx as nx

from noir.domain import rules
from noir.domain.enums import EventKind
from noir.domain.models import Event, Item, Location, Person


@dataclass
class TruthState:
    case_id: str
    seed: int
    graph: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    people: Dict[UUID, Person] = field(default_factory=dict)
    locations: Dict[UUID, Location] = field(default_factory=dict)
    items: Dict[UUID, Item] = field(default_factory=dict)
    events: Dict[UUID, Event] = field(default_factory=dict)
    case_meta: Dict[str, object] = field(default_factory=dict)

    def add_person(self, person: Person) -> None:
        self.people[person.id] = person
        self.graph.add_node(person.id, node_type="person", name=person.name)

    def add_location(self, location: Location) -> None:
        self.locations[location.id] = location
        self.graph.add_node(location.id, node_type="location", name=location.name)

    def add_item(self, item: Item) -> None:
        self.items[item.id] = item
        self.graph.add_node(item.id, node_type="item", name=item.name)

    def record_event(
        self,
        kind: EventKind,
        timestamp: int,
        location_id: UUID,
        participants: Optional[Iterable[UUID]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Event:
        rules.ensure_entity_exists(location_id, self.locations, "location")
        event = Event(
            kind=kind,
            timestamp=timestamp,
            location_id=location_id,
            participants=list(participants or []),
            metadata=metadata or {},
        )
        self.events[event.id] = event
        self.graph.add_node(
            event.id,
            node_type="event",
            kind=event.kind,
            timestamp=event.timestamp,
        )
        self.graph.add_edge(event.id, location_id, edge_type="event_at")
        for person_id in event.participants:
            rules.ensure_entity_exists(person_id, self.people, "person")
            self.graph.add_edge(event.id, person_id, edge_type="involves")
        return event

    def set_location(
        self,
        person_id: UUID,
        location_id: UUID,
        entry_time: int,
        exit_time: int | None = None,
    ) -> None:
        rules.ensure_entity_exists(person_id, self.people, "person")
        rules.ensure_entity_exists(location_id, self.locations, "location")
        rules.validate_time_interval(entry_time, exit_time)
        self.graph.add_edge(
            person_id,
            location_id,
            edge_type="located_at",
            entry_time=entry_time,
            exit_time=exit_time,
        )

    def possess(
        self,
        person_id: UUID,
        item_id: UUID,
        start_time: int,
        end_time: int | None = None,
    ) -> None:
        rules.ensure_entity_exists(person_id, self.people, "person")
        rules.ensure_entity_exists(item_id, self.items, "item")
        rules.validate_time_interval(start_time, end_time)
        self.graph.add_edge(
            person_id,
            item_id,
            edge_type="possesses",
            start_time=start_time,
            end_time=end_time,
        )

    def link_causal(self, event_id: UUID, precondition_id: UUID) -> None:
        if event_id not in self.events:
            raise KeyError(f"Unknown event id: {event_id}")
        self.graph.add_edge(event_id, precondition_id, edge_type="enabled_by")
