"""Episode framing helpers for Phase 3C."""

from __future__ import annotations

from typing import Iterable

from noir.util.rng import Rng
from noir.world.state import CaseRecord, WorldState


_TITLE_TEMPLATES = [
    "The {place}",
    "{place} After Dark",
    "The {district} File",
    "Silence in {place}",
    "{place} at Dusk",
    "The {district} Watch",
]

_COLD_OPEN_TEMPLATES = [
    "A call comes in from {place}.",
    "The scene is quiet when you arrive at {place}.",
    "The first report points to {place}.",
    "The case begins in {place}.",
    "Tonight starts at {place}.",
]

_END_TAGS_SUCCESS = [
    "The report holds, for now.",
    "The file closes clean.",
    "The city exhales for a night.",
]

_END_TAGS_PARTIAL = [
    "The charge stands, but it is thin.",
    "You have a name, not a lock.",
    "The file stays open in spirit.",
]

_END_TAGS_FAILED = [
    "The file stays open.",
    "The city remembers the gap.",
    "The night moves on without closure.",
]

_PARTNER_LINES = [
    "Your partner keeps the room moving.",
    "The team runs the file while you head out.",
    "A colleague flags a thread worth pulling.",
    "The squad room is quiet, but the phones are not.",
    "The case file feels heavier than it looks.",
    "Someone on the team already pulled the last report.",
    "A partner asks for the short version, then the long one.",
    "The unit watches the clock as the city wakes.",
]


def build_episode_title(rng: Rng, location_name: str, district: str) -> str:
    template = rng.choice(_TITLE_TEMPLATES)
    title = template.format(place=location_name, district=district.replace("_", " ").title())
    return title


def build_cold_open(rng: Rng, location_name: str) -> list[str]:
    templates = list(_COLD_OPEN_TEMPLATES)
    rng.shuffle(templates)
    line_count = rng.randint(2, 4)
    lines = []
    for template in templates[:line_count]:
        lines.append(template.format(place=location_name))
    return lines


def build_end_tag(rng: Rng, outcome: str) -> list[str]:
    tag_lines: list[str] = []
    if outcome == "success":
        pool = _END_TAGS_SUCCESS
    elif outcome == "partial":
        pool = _END_TAGS_PARTIAL
    else:
        pool = _END_TAGS_FAILED
    tag_lines.append(rng.choice(pool))
    return tag_lines


def build_previously_on(world: WorldState, limit: int = 4) -> list[str]:
    if not world.case_history:
        return []
    recent: Iterable[CaseRecord] = world.case_history[-limit:]
    lines: list[str] = ["Previously on..."]
    for record in recent:
        note = ""
        if record.notes:
            note = f" {record.notes[0]}"
        lines.append(f"{record.case_id} closed ({record.outcome}).{note}")
    return lines


def build_partner_line(rng: Rng, chance: float = 0.6) -> list[str]:
    if rng.random() > chance:
        return []
    return [rng.choice(_PARTNER_LINES)]
