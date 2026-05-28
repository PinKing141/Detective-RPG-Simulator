"""Ending logic for early and endgame conclusions.

This module reads the campaign spine state (tension, nemesis arc,
identity, closing-in counters) to pick the right exit. Early endings
fire mid-season as legitimate alternative conclusions; final endings
fire at season finale and grade the whole arc.
"""

from __future__ import annotations

from dataclasses import dataclass

from noir.investigation.costs import PRESSURE_LIMIT
from noir.investigation.outcomes import TRUST_LIMIT
from noir.showrunner.tension import sustained_high
from noir.world.state import EndgameState, WorldState


@dataclass
class EndingResult:
    kind: str
    title: str
    lines: list[str]


def check_early_ending(world: WorldState) -> EndingResult | None:
    """Return an early ending if any trigger has armed and fired.

    Triggers are evaluated in priority order from hardest-stop to
    softest. Only one fires per call.
    """

    if world.trust <= 1:
        return _build(
            kind="institutional_breakdown",
            title="EARLY ENDING - INSTITUTIONAL BREAKDOWN",
            lines=[
                "Institutional support breaks before the work is finished.",
                _identity_line(world),
                _city_line(world),
                "Someone else picks up the file, but the shape of it stays with you.",
            ],
        )
    if world.pressure >= PRESSURE_LIMIT:
        return _build(
            kind="public_crisis",
            title="EARLY ENDING - PUBLIC CRISIS",
            lines=[
                "Public pressure spikes beyond what the unit can absorb.",
                _identity_line(world),
                _city_line(world),
                "The season closes under scrutiny, not closure.",
            ],
        )
    if _burnout_triggered(world):
        return _build(
            kind="burnout",
            title="EARLY ENDING - BURNOUT",
            lines=[
                "The pace breaks you before the case does.",
                _identity_line(world),
                "You file the papers, hand over the box, and walk.",
                "The work stays open behind you.",
            ],
        )
    if _corruption_triggered(world):
        return _build(
            kind="corruption",
            title="EARLY ENDING - CORRUPTION INQUIRY",
            lines=[
                "Internal affairs catches the shape of how you've been working.",
                _identity_line(world),
                "The arc closes with you on the other side of the table.",
                "Whatever you were chasing keeps moving without you.",
            ],
        )
    if _coup_triggered(world):
        world.campaign.nemesis_arc.coup_fired = True
        return _build(
            kind="nemesis_coup",
            title="EARLY ENDING - THE NEMESIS WINS",
            lines=[
                "While you were working the cases, the nemesis ran their own clock down.",
                _identity_line(world),
                _city_line(world),
                "The headlines belong to them now; you read them from the outside.",
            ],
        )
    return None


def build_final_ending(world: WorldState) -> EndingResult:
    """Pick a final ending from the full campaign state.

    The base axis is the endgame_result (clean / shaky / wrong / unresolved).
    The axis is then refined by tension peak, identity, and nemesis arc
    state into one of several authored variants.
    """

    base = world.campaign.endgame_result or "unresolved"
    arc = world.campaign.nemesis_arc
    tension = world.campaign.tension

    if base == "captured_clean":
        if tension.peak >= 85 and world.trust <= 2:
            kind, title, prologue = (
                "pyrrhic",
                "SEASON END - PYRRHIC VICTORY",
                "You closed it, but the cost is sitting in every empty chair.",
            )
        elif (
            world.campaign.identity.dominant == "coercive"
            and world.campaign.identity.coercive >= 4
        ):
            kind, title, prologue = (
                "compromised",
                "SEASON END - COMPROMISED VICTORY",
                "You closed it the only way you know how; the case file doesn't ask why.",
            )
        else:
            kind, title, prologue = (
                "triumphant",
                "SEASON END - TRIUMPHANT",
                "You closed the arc with a clean operation and a firm case file.",
            )
    elif base == "captured_shaky":
        kind, title, prologue = (
            "captured_shaky",
            "SEASON END - CAPTURED (SHAKY)",
            "You brought them in, but the proof stayed thin.",
        )
    elif base == "raid_wrong":
        kind, title, prologue = (
            "defeat",
            "SEASON END - COLLAPSE",
            "The raid broke the arc without closing it.",
        )
    elif arc.confronted:
        kind, title, prologue = (
            "stalemate",
            "SEASON END - STALEMATE",
            "You found them and they found you; nobody walked away with the whole truth.",
        )
    else:
        kind, title, prologue = (
            "unresolved",
            "SEASON END - UNRESOLVED",
            "The season ends without certainty, only the weight of the work.",
        )

    lines = [
        prologue,
        _identity_line(world),
        _city_line(world),
        _arc_line(world),
        "The work doesn't end. It just stops needing you.",
    ]
    return _build(kind=kind, title=title, lines=lines)


def _burnout_triggered(world: WorldState) -> bool:
    return (
        sustained_high(world.campaign, threshold=80, samples=3)
        and world.trust <= 2
        and world.campaign.endgame_state != EndgameState.ACTIVE
    )


def _corruption_triggered(world: WorldState) -> bool:
    identity = world.campaign.identity
    mistakes = world.mistake_history.get("wrong_arrest")
    wrong_count = mistakes.count if mistakes else 0
    return identity.coercive >= 6 and (wrong_count >= 2 or world.trust <= 2)


def _coup_triggered(world: WorldState) -> bool:
    arc = world.campaign.nemesis_arc
    if arc.coup_fired:
        return False
    if world.campaign.endgame_state in {EndgameState.ACTIVE, EndgameState.RESOLVED}:
        return False
    return arc.clock >= arc.clock_max


def _build(*, kind: str, title: str, lines: list[str]) -> EndingResult:
    return EndingResult(kind=kind, title=title, lines=_compact(lines))


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


def _arc_line(world: WorldState) -> str:
    arc = world.campaign.nemesis_arc
    if arc.coup_fired:
        return "The nemesis's plan landed before yours; that file stays open."
    if arc.confronted:
        return "You and the nemesis met in the open before the end."
    if arc.clock >= arc.clock_max - 2:
        return "The nemesis ran their own clock close to the wire."
    return ""


def _compact(lines: list[str]) -> list[str]:
    return [line for line in lines if line]
