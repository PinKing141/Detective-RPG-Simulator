"""Case truth generator for Phase 0."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from noir.cases.archetypes import PHASE0_MODULATORS
from noir.domain.enums import EventKind, ItemType, RoleTag
from noir.domain.models import Item, Location, Person
from noir.naming import NamePick, load_name_generator
from noir.truth.graph import TruthState
from noir.util.rng import Rng
from noir.world.state import WorldState
DISTRICTS = ["harbor", "midtown", "old_quarter", "riverside"]
PUBLIC_LOCATIONS = [
    "Marlowe Diner",
    "Harbor Warehouse",
    "Crossline Motel",
]
PRIVATE_LOCATIONS = [
    "Riverside Apartment",
    "Northline Rowhouse",
]
WEAPONS = ["Kitchen Knife", "Box Cutter", "Glass Shard"]
ACCESS_PATHS = ["forced_entry", "social_entry", "trusted_contact"]
MOTIVES = ["money", "revenge", "obsession", "concealment", "thrill"]
RELATIONSHIP_DISTANCES = ["intimate", "acquaintance", "stranger"]

_NAME_GENERATOR = None


def _name_context(rng: Rng):
    global _NAME_GENERATOR
    if _NAME_GENERATOR is None:
        _NAME_GENERATOR = load_name_generator()
    return _NAME_GENERATOR.start_case(rng)


def _name_pick(rng: Rng, context) -> NamePick:
    return context.next_name_pick(rng)


def _method_category(weapon_name: str) -> str:
    lowered = weapon_name.lower()
    if "poison" in lowered:
        return "poison"
    if "blunt" in lowered or "bat" in lowered or "hammer" in lowered:
        return "blunt"
    return "sharp"


def generate_case(
    rng: Rng,
    case_id: str | None = None,
    world: Optional[WorldState] = None,
) -> tuple[TruthState, Dict[str, UUID | int | str]]:
    case_id = case_id or f"case_{rng.seed}"
    truth = TruthState(case_id=case_id, seed=rng.seed)

    competence = round(rng.random(), 2)
    risk_tolerance = round(rng.random(), 2)
    relationship_distance = rng.choice(RELATIONSHIP_DISTANCES)

    if risk_tolerance >= 0.6:
        location_name = rng.choice(PUBLIC_LOCATIONS)
        location_tags = ["crime_scene", "cctv", "public"]
    else:
        location_name = rng.choice(PRIVATE_LOCATIONS)
        location_tags = ["crime_scene", "private"]

    name_rng = rng.fork("names")
    name_context = _name_context(name_rng)

    crime_scene = Location(
        name=location_name,
        district=rng.choice(DISTRICTS),
        tags=location_tags,
    )
    truth.add_location(crime_scene)

    returning_witness = None
    if world:
        returning_witness = world.pick_returning_person(
            name_rng, RoleTag.WITNESS.value, chance=0.25
        )

    victim_pick = _name_pick(name_rng, name_context)
    victim_traits: dict[str, float | str] = {}
    if victim_pick.country:
        victim_traits["country_of_origin"] = victim_pick.country
    victim = Person(
        name=victim_pick.full,
        role_tags=[RoleTag.VICTIM],
        traits=victim_traits,
    )
    offender_pick = _name_pick(name_rng, name_context)
    offender_traits: dict[str, float | str] = {
        "competence": competence,
        "risk_tolerance": risk_tolerance,
        "relationship_distance": relationship_distance,
    }
    if offender_pick.country:
        offender_traits["country_of_origin"] = offender_pick.country
    offender = Person(
        name=offender_pick.full,
        role_tags=[RoleTag.SUSPECT, RoleTag.OFFENDER],
        traits=offender_traits,
    )
    if returning_witness:
        witness_traits: dict[str, float | str] = {}
        if returning_witness.country_of_origin:
            witness_traits["country_of_origin"] = returning_witness.country_of_origin
        witness = Person(
            id=UUID(returning_witness.person_id),
            name=returning_witness.name,
            role_tags=[RoleTag.WITNESS],
            traits=witness_traits,
        )
    else:
        witness_pick = _name_pick(name_rng, name_context)
        witness_traits: dict[str, float | str] = {}
        if witness_pick.country:
            witness_traits["country_of_origin"] = witness_pick.country
        witness = Person(
            name=witness_pick.full,
            role_tags=[RoleTag.WITNESS],
            traits=witness_traits,
        )
    truth.add_person(victim)
    truth.add_person(offender)
    truth.add_person(witness)

    weapon = Item(name=rng.choice(WEAPONS), item_type=ItemType.WEAPON)
    method_category = _method_category(weapon.name)
    truth.add_item(weapon)

    crime_time = rng.randint(20, 22)
    approach_time = crime_time - 1
    discovery_time = crime_time + 2

    truth.set_location(victim.id, crime_scene.id, entry_time=crime_time - 1, exit_time=crime_time + 1)
    truth.set_location(offender.id, crime_scene.id, entry_time=crime_time - 1, exit_time=crime_time + 1)
    truth.set_location(witness.id, crime_scene.id, entry_time=crime_time - 2, exit_time=crime_time)

    truth.possess(offender.id, weapon.id, start_time=crime_time - 2, end_time=crime_time)

    access_path = rng.choice(ACCESS_PATHS)
    motive = rng.choice(MOTIVES)
    if relationship_distance == "intimate":
        motive = rng.choice(["revenge", "obsession", "concealment"])
        access_path = "trusted_contact"
    elif relationship_distance == "stranger":
        motive = rng.choice(["thrill", "money"])
        access_path = "forced_entry"

    truth.record_event(
        kind=EventKind.APPROACH,
        timestamp=approach_time,
        location_id=crime_scene.id,
        participants=[offender.id, victim.id],
        metadata={
            "method": weapon.name,
            "method_category": method_category,
            "access_path": access_path,
        },
    )
    kill_event = truth.record_event(
        kind=EventKind.KILL,
        timestamp=crime_time,
        location_id=crime_scene.id,
        participants=[offender.id, victim.id],
        metadata={
            "method": weapon.name,
            "method_category": method_category,
            "weapon_id": str(weapon.id),
            "motive_category": motive,
        },
    )
    truth.record_event(
        kind=EventKind.DISCOVERY,
        timestamp=discovery_time,
        location_id=crime_scene.id,
        participants=[witness.id],
        metadata={"found_victim_id": str(victim.id)},
    )
    truth.link_causal(kill_event.id, weapon.id)

    truth.case_meta.update(
        {
            "active_modulators": [mod.value for mod in PHASE0_MODULATORS],
            "competence": competence,
            "risk_tolerance": risk_tolerance,
            "relationship_distance": relationship_distance,
            "access_path": access_path,
            "motive_category": motive,
            "location_name": crime_scene.name,
            "method_category": method_category,
        }
    )

    case_facts: Dict[str, UUID | int | str] = {
        "case_id": case_id,
        "crime_time": crime_time,
        "crime_scene_id": crime_scene.id,
        "victim_id": victim.id,
        "offender_id": offender.id,
        "witness_id": witness.id,
        "weapon_id": weapon.id,
    }
    return truth, case_facts
