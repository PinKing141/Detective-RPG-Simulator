"""Ending logic for early and endgame conclusions."""

from __future__ import annotations

from dataclasses import dataclass

from noir.investigation.costs import PRESSURE_LIMIT
from noir.investigation.outcomes import TRUST_LIMIT
from noir.world.state import WorldState


@dataclass
class EndingResult:
    kind: str
    title: str
    lines: list[str]


def check_early_ending(world: WorldState) -> EndingResult | None:
    if world.trust <= 1:
        lines = [
            "Institutional support breaks before the work is finished.",
            _identity_line(world),
            _city_line(world),
            "Someone else picks up the file, but the shape of it stays with you.",
        ]
        return EndingResult(
            kind="institutional_breakdown",
            title="EARLY ENDING - INSTITUTIONAL BREAKDOWN",
            lines=_compact(lines),
        )
    if world.pressure >= PRESSURE_LIMIT:
        lines = [
            "Public pressure spikes beyond what the unit can absorb.",
            _identity_line(world),
            _city_line(world),
            "The season closes under scrutiny, not closure.",
        ]
        return EndingResult(
            kind="public_crisis",
            title="EARLY ENDING - PUBLIC CRISIS",
            lines=_compact(lines),
        )
    return None


def build_final_ending(world: WorldState) -> EndingResult:
    result = world.campaign.endgame_result or "unresolved"
    title_map = {
        "captured_clean": "SEASON END - CAPTURED",
        "captured_shaky": "SEASON END - CAPTURED (SHAKY)",
        "raid_wrong": "SEASON END - COLLAPSE",
        "unresolved": "SEASON END - UNRESOLVED",
    }
    lines = [
        _result_line(result),
        _identity_line(world),
        _city_line(world),
        "The work doesn't end. It just stops needing you.",
    ]
    return EndingResult(
        kind=result,
        title=title_map.get(result, "SEASON END"),
        lines=_compact(lines),
    )


def _result_line(result: str) -> str:
    if result == "captured_clean":
        return "You closed the arc with a clean operation and a firm case file."
    if result == "captured_shaky":
        return "You brought them in, but the proof stayed thin."
    if result == "raid_wrong":
        return "The raid broke the arc without closing it."
    return "The season ends without certainty, only the weight of the work."


def _identity_line(world: WorldState) -> str:
    dominant = world.campaign.identity.dominant
    if dominant == "analytical":
        return "You built cases through analysis and corroboration."
    if dominant == "social":
        return "You leaned on rapport and patience to move people."
    if dominant == "coercive":
        return "You pushed hard when the clock was loud."
    return "You moved between methods, never settling into one."


def _city_line(world: WorldState) -> str:
    if world.pressure >= 4:
        return "The city closes ranks; scrutiny remains high."
    if world.trust >= TRUST_LIMIT - 1:
        return "The city breathes easier; trust steadies for now."
    return "The city keeps moving, carrying the cases with it."


def _compact(lines: list[str]) -> list[str]:
    return [line for line in lines if line]
