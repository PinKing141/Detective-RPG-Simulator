"""Case truth generator for Phase 0."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from noir.cases.archetypes import CaseArchetype, PHASE0_MODULATORS
from noir.domain.enums import EventKind, ItemType, RoleTag
from noir.domain.models import Item, Location, Person
from noir.locations.profiles import build_scene_layout, load_location_profiles
from noir.naming import NamePick, load_name_generator
from noir.nemesis.state import NemesisCasePlan
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
WEAPONS_BY_METHOD = {
    "sharp": WEAPONS,
    "blunt": ["Crowbar", "Hammer", "Pipe Wrench"],
    "poison": ["Sleeping Pills", "Cleaning Solvent", "Insulin Syringe"],
}
ACCESS_PATHS = ["forced_entry", "social_entry", "trusted_contact"]
MOTIVES = ["money", "revenge", "obsession", "concealment", "thrill"]
RELATIONSHIP_DISTANCES = ["intimate", "acquaintance", "stranger"]
RELATIONSHIP_TYPES = {
    "intimate": ["parent", "partner", "lover", "sibling"],
    "acquaintance": ["friend", "colleague", "neighbor"],
    "stranger": ["stranger"],
}

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


def _pick_closeness(rng: Rng, weights: tuple[float, float, float]) -> str:
    roll = rng.random()
    intimate, acquaintance, stranger = weights
    if roll < intimate:
        return "intimate"
    if roll < intimate + acquaintance:
        return "acquaintance"
    return "stranger"


def _pick_relationship_type(rng: Rng, closeness: str) -> str:
    options = RELATIONSHIP_TYPES.get(closeness, ["stranger"])
    return rng.choice(options)


def _time_bucket(hour: int) -> str:
    value = hour % 24
    if 5 <= value < 12:
        return "morning"
    if 12 <= value < 17:
        return "afternoon"
    if 17 <= value < 21:
        return "evening"
    return "midnight"


def _weighted_choice(rng: Rng, options: dict[str, float]) -> str | None:
    if not options:
        return None
    total = sum(max(0.0, value) for value in options.values())
    if total <= 0:
        return rng.choice(list(options.keys()))
    pick = rng.random() * total
    cumulative = 0.0
    for key, weight in options.items():
        cumulative += max(0.0, weight)
        if pick <= cumulative:
            return key
    return next(iter(options.keys()))


def _witness_count(presence: float, rng: Rng) -> int:
    count = 1
    if presence >= 0.35 and rng.random() < presence:
        count += 1
    if presence >= 0.6 and rng.random() < (presence - 0.2):
        count += 1
    return min(count, 3)


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
    nemesis_plan: NemesisCasePlan | None = None,
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
    presence_curve = archetype.get("presence_curve", {}) or {}
    witness_roles = archetype.get("witness_roles", {}) or {}
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
    witnesses: list[Person] = []
    witness_role = _weighted_choice(rng, witness_roles) or "witness"
    if returning_witness:
        witness_traits: dict[str, float | str] = {"witness_role": witness_role}
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
        witness_traits: dict[str, float | str] = {"witness_role": witness_role}
        if witness_pick.country:
            witness_traits["country_of_origin"] = witness_pick.country
        witness = Person(
            name=witness_pick.full,
            role_tags=[RoleTag.WITNESS],
            traits=witness_traits,
        )
    witnesses.append(witness)
    truth.add_person(victim)
    truth.add_person(offender)
    truth.add_person(witness)

    witness_victim_closeness = _pick_closeness(rng, weights=(0.3, 0.5, 0.2))
    witness_offender_closeness = _pick_closeness(rng, weights=(0.1, 0.4, 0.5))
    witness_victim_relation = _pick_relationship_type(rng, witness_victim_closeness)
    witness_offender_relation = _pick_relationship_type(rng, witness_offender_closeness)
    offender_victim_relation = _pick_relationship_type(rng, relationship_distance)

    truth.add_relationship(
        witness.id, victim.id, witness_victim_relation, witness_victim_closeness
    )
    truth.add_relationship(
        witness.id, offender.id, witness_offender_relation, witness_offender_closeness
    )
    truth.add_relationship(
        offender.id, victim.id, offender_victim_relation, relationship_distance
    )

    method_category_override = None
    nemesis_visibility = 1
    nemesis_degraded = False
    nemesis_tone = None
    if nemesis_plan and nemesis_plan.is_nemesis_case:
        method_category_override = nemesis_plan.method_category
        nemesis_visibility = nemesis_plan.visibility
        nemesis_degraded = nemesis_plan.degraded_execution
        nemesis_tone = nemesis_plan.taunt_style
        if nemesis_degraded:
            competence = min(competence, 0.3)
    weapon_method = method_category_override or rng.choice(list(WEAPONS_BY_METHOD.keys()))
    weapon_name = rng.choice(WEAPONS_BY_METHOD.get(weapon_method, WEAPONS))
    weapon = Item(name=weapon_name, item_type=ItemType.WEAPON)
    method_category = method_category_override or _method_category(weapon.name)
    truth.add_item(weapon)

    crime_time = rng.randint(20, 22)
    approach_time = crime_time - 1
    discovery_time = crime_time + 2

    bucket = _time_bucket(crime_time)
    presence = float(presence_curve.get(bucket, 0.4))
    witness_rng = rng.fork("witnesses")
    target_witness_count = _witness_count(presence, witness_rng)
    while len(witnesses) < target_witness_count:
        witness_pick = _name_pick(name_rng, name_context)
        witness_traits: dict[str, float | str] = {}
        extra_role = _weighted_choice(witness_rng, witness_roles)
        if extra_role:
            witness_traits["witness_role"] = extra_role
        if witness_pick.country:
            witness_traits["country_of_origin"] = witness_pick.country
        extra_witness = Person(
            name=witness_pick.full,
            role_tags=[RoleTag.WITNESS],
            traits=witness_traits,
        )
        truth.add_person(extra_witness)
        witnesses.append(extra_witness)
        extra_victim_closeness = _pick_closeness(witness_rng, weights=(0.1, 0.4, 0.5))
        extra_offender_closeness = _pick_closeness(witness_rng, weights=(0.05, 0.25, 0.7))
        extra_victim_relation = _pick_relationship_type(
            witness_rng, extra_victim_closeness
        )
        extra_offender_relation = _pick_relationship_type(
            witness_rng, extra_offender_closeness
        )
        truth.add_relationship(
            extra_witness.id,
            victim.id,
            extra_victim_relation,
            extra_victim_closeness,
        )
        truth.add_relationship(
            extra_witness.id,
            offender.id,
            extra_offender_relation,
            extra_offender_closeness,
        )

    contradiction_witness = None
    if witnesses:
        contradiction_witness = rng.fork("contradiction").choice(witnesses)

    truth.set_location(victim.id, crime_scene.id, entry_time=crime_time - 1, exit_time=crime_time + 1)
    truth.set_location(offender.id, crime_scene.id, entry_time=crime_time - 1, exit_time=crime_time + 1)
    for scene_witness in witnesses:
        truth.set_location(
            scene_witness.id, crime_scene.id, entry_time=crime_time - 2, exit_time=crime_time
        )

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
        participants=[witnesses[0].id],
        metadata={"found_victim_id": str(victim.id)},
    )
    truth.link_causal(kill_event.id, weapon.id)

    truth.case_meta.update(
        {
            "active_modulators": [mod.value for mod in PHASE0_MODULATORS],
            "competence": competence,
            "risk_tolerance": risk_tolerance,
            "relationship_distance": relationship_distance,
            "witness_victim_relationship": witness_victim_relation,
            "witness_victim_closeness": witness_victim_closeness,
            "witness_offender_relationship": witness_offender_relation,
            "witness_offender_closeness": witness_offender_closeness,
            "offender_victim_relationship": offender_victim_relation,
            "access_path": access_path,
            "motive_category": motive,
            "location_name": crime_scene.name,
            "method_category": method_category,
            "location_archetype": archetype_id,
            "location_scope_set": scene_layout.scope_set,
            "case_archetype": case_archetype.value,
            "witness_ids": [str(scene_witness.id) for scene_witness in witnesses],
            "contradiction_witness_id": str(contradiction_witness.id)
            if contradiction_witness
            else "",
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
            "nemesis_case": bool(nemesis_plan and nemesis_plan.is_nemesis_case),
            "nemesis_method": method_category_override or "",
            "nemesis_visibility": nemesis_visibility,
            "nemesis_degraded": nemesis_degraded,
            "nemesis_tone": nemesis_tone or "",
        }
    )

    case_facts: Dict[str, object] = {
        "case_id": case_id,
        "crime_time": crime_time,
        "crime_scene_id": crime_scene.id,
        "victim_id": victim.id,
        "offender_id": offender.id,
        "witness_id": witness.id,
        "witness_ids": [scene_witness.id for scene_witness in witnesses],
        "weapon_id": weapon.id,
        "case_archetype": case_archetype.value,
        "scene_layout": truth.case_meta.get("scene_layout"),
        "primary_poi_id": primary_poi_id or "",
        "body_poi_id": body_poi_id or "",
        "contradiction_witness_id": contradiction_witness.id
        if contradiction_witness
        else "",
        "nemesis_case": truth.case_meta.get("nemesis_case", False),
        "nemesis_visibility": truth.case_meta.get("nemesis_visibility", 1),
        "nemesis_degraded": truth.case_meta.get("nemesis_degraded", False),
    }
    return truth, case_facts
