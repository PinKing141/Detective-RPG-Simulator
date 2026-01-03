"""Case truth generator for Phase 0."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from noir.cases.archetypes import CaseArchetype, PHASE0_MODULATORS
from noir.domain.enums import EventKind, ItemType, RoleTag
from noir.domain.models import Item, Location, Person
from noir.locations.profiles import build_scene_layout, load_location_profiles
from noir.naming import NamePick, load_name_generator
from noir.truth.graph import TruthState
from noir.util.rng import Rng
from noir.world.state import WorldState
DISTRICTS = ["harbor", "midtown", "old_quarter", "riverside"]
LOCATION_OPTIONS = [
    {"name": "Marlowe Diner", "archetype": "diner"},
    {"name": "Harbor Warehouse", "archetype": "warehouse"},
    {"name": "Crossline Motel", "archetype": "motel"},
    {"name": "Riverside Apartment", "archetype": "apartment_unit"},
    {"name": "Northline Rowhouse", "archetype": "apartment_unit"},
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


def _seed_pois_from_scope(scope_set: dict, zone_templates: dict, rng: Rng) -> list[str]:
    poi_options: list[str] = []
    for zone_id in scope_set.get("zones", []) or []:
        template = zone_templates.get(zone_id, {}) or {}
        poi_options.extend(template.get("poi_templates", []) or [])
    if not poi_options:
        return []
    rng.shuffle(poi_options)
    unique: list[str] = []
    for name in poi_options:
        if name in unique:
            continue
        unique.append(name)
        if len(unique) >= 3:
            break
    return unique


def _location_pick(rng: Rng, risk_tolerance: float) -> dict:
    profiles = load_location_profiles()
    choices: list[dict] = []
    for option in LOCATION_OPTIONS:
        archetype = profiles["archetypes"].get(option["archetype"], {})
        access = archetype.get("access_level", "public")
        is_private = access == "private"
        if risk_tolerance >= 0.6 and not is_private:
            choices.append(option)
        elif risk_tolerance < 0.6 and is_private:
            choices.append(option)
    if not choices:
        choices = LOCATION_OPTIONS
    return rng.choice(choices)


def generate_case(
    rng: Rng,
    case_id: str | None = None,
    world: Optional[WorldState] = None,
    case_archetype: CaseArchetype | None = None,
) -> tuple[TruthState, Dict[str, object]]:
    case_id = case_id or f"case_{rng.seed}"
    truth = TruthState(case_id=case_id, seed=rng.seed)

    competence = round(rng.random(), 2)
    risk_tolerance = round(rng.random(), 2)
    relationship_distance = rng.choice(RELATIONSHIP_DISTANCES)

    location_pick = _location_pick(rng, risk_tolerance)

    location_name = location_pick["name"]
    location_profiles = load_location_profiles()
    archetype_id = location_pick["archetype"]
    archetype = location_profiles["archetypes"].get(archetype_id, {})
    location_tags = ["crime_scene"] + list(archetype.get("tags", []))
    if archetype.get("access_level"):
        location_tags.append(archetype["access_level"])
    if archetype.get("surveillance", {}).get("cctv", 0) >= 0.5:
        location_tags.append("cctv")
    location_tags.append(f"archetype:{archetype_id}")

    name_rng = rng.fork("names")
    name_context = _name_context(name_rng)

    crime_scene = Location(
        name=location_name,
        district=rng.choice(DISTRICTS),
        tags=location_tags,
    )
    truth.add_location(crime_scene)

    case_archetype = case_archetype or CaseArchetype.BASELINE
    scene_mode = (
        "bottom_up"
        if case_archetype in (CaseArchetype.PATTERN, CaseArchetype.CHARACTER)
        else "top_down"
    )
    seed_pois: list[str] | None = None
    if scene_mode == "bottom_up":
        scope_set = location_profiles["scope_sets"].get(archetype.get("scope_set"), {}) or {}
        seed_pois = _seed_pois_from_scope(
            scope_set,
            location_profiles["zone_templates"],
            rng.fork("seed-pois"),
        )
    scene_layout = build_scene_layout(
        rng.fork("scene"),
        archetype_id=archetype_id,
        mode=scene_mode,
        seed_pois=seed_pois,
    )
    primary_poi_id = scene_layout.pois[0].poi_id if scene_layout.pois else None
    body_poi_id = primary_poi_id

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
            "location_archetype": archetype_id,
            "location_scope_set": scene_layout.scope_set,
            "case_archetype": case_archetype.value,
            "scene_layout": {
                "archetype_id": scene_layout.archetype_id,
                "scope_set": scene_layout.scope_set,
                "mode": scene_layout.mode,
                "zones": scene_layout.zones,
                "pois": [
                    {
                        "poi_id": poi.poi_id,
                        "label": poi.label,
                        "zone_id": poi.zone_id,
                        "zone_label": poi.zone_label,
                        "description": poi.description,
                        "tags": list(poi.tags),
                    }
                    for poi in scene_layout.pois
                ],
                "neighbor_slots": scene_layout.neighbor_slots,
            },
            "primary_poi_id": primary_poi_id,
            "body_poi_id": body_poi_id,
        }
    )

    case_facts: Dict[str, object] = {
        "case_id": case_id,
        "crime_time": crime_time,
        "crime_scene_id": crime_scene.id,
        "victim_id": victim.id,
        "offender_id": offender.id,
        "witness_id": witness.id,
        "weapon_id": weapon.id,
        "case_archetype": case_archetype.value,
        "scene_layout": truth.case_meta.get("scene_layout"),
        "primary_poi_id": primary_poi_id or "",
        "body_poi_id": body_poi_id or "",
    }
    return truth, case_facts
