"""Load location profiles and build lightweight scene layouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from noir.util.rng import Rng


@dataclass(frozen=True)
class ScenePOI:
    poi_id: str
    label: str
    zone_id: str
    zone_label: str


@dataclass(frozen=True)
class SceneLayout:
    archetype_id: str
    scope_set: str | None
    mode: str
    zones: list[str]
    pois: list[ScenePOI]
    neighbor_slots: list[dict[str, Any]]


_LOCATION_CACHE: dict[str, Any] | None = None


def _locations_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "schemas" / "locations.yml"


def _format_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def load_location_profiles(path: Path | None = None) -> dict[str, Any]:
    """Load location profiles from YAML once and cache them."""
    global _LOCATION_CACHE
    if _LOCATION_CACHE is not None:
        return _LOCATION_CACHE
    location_path = path or _locations_path()
    data = yaml.safe_load(location_path.read_text(encoding="utf-8"))
    archetypes = {item["id"]: item for item in data.get("archetypes", [])}
    scope_sets = data.get("scope_sets", {}) or {}
    zone_templates = data.get("zone_templates", {}) or {}
    _LOCATION_CACHE = {
        "archetypes": archetypes,
        "scope_sets": scope_sets,
        "zone_templates": zone_templates,
        "time_buckets": data.get("time_buckets", []),
    }
    return _LOCATION_CACHE


def _zone_label(zone_templates: dict[str, Any], zone_id: str) -> str:
    template = zone_templates.get(zone_id, {})
    return template.get("display_name") or _format_label(zone_id)


def _poi_label(poi_name: str) -> str:
    return _format_label(poi_name)


def _build_poi_id(zone_id: str, poi_name: str, index: int) -> str:
    return f"{zone_id}:{poi_name}:{index}"


def _zone_map(zone_templates: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for zone_id, template in zone_templates.items():
        for poi_name in template.get("poi_templates", []) or []:
            mapping.setdefault(poi_name, []).append(zone_id)
    return mapping


def _choose_zones(rng: Rng, zones: Iterable[str]) -> list[str]:
    zone_list = list(zones)
    if not zone_list:
        return []
    if len(zone_list) <= 3:
        return zone_list
    target = rng.randint(3, min(5, len(zone_list)))
    rng.shuffle(zone_list)
    return zone_list[:target]


def _assemble_pois(
    rng: Rng,
    zone_templates: dict[str, Any],
    zones: list[str],
) -> list[ScenePOI]:
    pois: list[ScenePOI] = []
    used_templates: set[str] = set()
    for zone_id in zones:
        template = zone_templates.get(zone_id, {})
        poi_options = list(template.get("poi_templates", []) or [])
        if not poi_options:
            continue
        rng.shuffle(poi_options)
        poi_name = poi_options[0]
        used_templates.add(f"{zone_id}:{poi_name}")
        poi_id = _build_poi_id(zone_id, poi_name, len(pois))
        pois.append(
            ScenePOI(
                poi_id=poi_id,
                label=_poi_label(poi_name),
                zone_id=zone_id,
                zone_label=_zone_label(zone_templates, zone_id),
            )
        )
    if len(pois) >= 3:
        return pois[:5]
    candidates: list[ScenePOI] = []
    for zone_id in zones:
        template = zone_templates.get(zone_id, {})
        poi_options = list(template.get("poi_templates", []) or [])
        for poi_name in poi_options:
            key = f"{zone_id}:{poi_name}"
            if key in used_templates:
                continue
            poi_id = _build_poi_id(zone_id, poi_name, len(candidates))
            candidates.append(
                ScenePOI(
                    poi_id=poi_id,
                    label=_poi_label(poi_name),
                    zone_id=zone_id,
                    zone_label=_zone_label(zone_templates, zone_id),
                )
            )
    if not candidates:
        return pois
    rng.shuffle(candidates)
    needed = max(0, 3 - len(pois))
    pois.extend(candidates[:needed])
    return pois[:5]


def build_scene_layout(
    rng: Rng,
    archetype_id: str,
    mode: str = "top_down",
    seed_pois: list[str] | None = None,
) -> SceneLayout:
    profiles = load_location_profiles()
    archetype = profiles["archetypes"].get(archetype_id, {})
    scope_set_id = archetype.get("scope_set")
    scope_sets = profiles["scope_sets"]
    zone_templates = profiles["zone_templates"]
    neighbor_slots = []
    zones: list[str] = []
    pois: list[ScenePOI] = []

    if mode == "bottom_up" and seed_pois:
        poi_to_zone = _zone_map(zone_templates)
        for poi_name in seed_pois:
            zone_ids = poi_to_zone.get(poi_name)
            if not zone_ids:
                continue
            zone_id = zone_ids[0]
            if zone_id not in zones:
                zones.append(zone_id)
            poi_id = _build_poi_id(zone_id, poi_name, len(pois))
            pois.append(
                ScenePOI(
                    poi_id=poi_id,
                    label=_poi_label(poi_name),
                    zone_id=zone_id,
                    zone_label=_zone_label(zone_templates, zone_id),
                )
            )
        if not zones or not pois:
            mode = "top_down"

    if mode == "top_down":
        scope_set = scope_sets.get(scope_set_id, {})
        neighbor_slots = list(scope_set.get("neighbor_slots", []) or [])
        zones = _choose_zones(rng, scope_set.get("zones", []) or [])
        pois = _assemble_pois(rng, zone_templates, zones)

    if not zones:
        zones = []
    if not pois:
        poi_names = archetype.get("poi_templates", []) or []
        for poi_name in poi_names[:5]:
            poi_id = _build_poi_id("scene", poi_name, len(pois))
            pois.append(
                ScenePOI(
                    poi_id=poi_id,
                    label=_poi_label(poi_name),
                    zone_id="scene",
                    zone_label="Scene",
                )
            )
    return SceneLayout(
        archetype_id=archetype_id,
        scope_set=scope_set_id,
        mode=mode,
        zones=zones,
        pois=pois,
        neighbor_slots=neighbor_slots,
    )
