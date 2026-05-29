"""Tension wave pacing for the campaign spine.

Tension is a campaign-level scalar (0-100) that represents the
subjective intensity of the season. The wave has a planned target curve
per season episode slot, and case-level events nudge the current value
up or down. The scheduler biases case selection toward closing the gap
between the current value and the target.

This module is pure data and helpers — it never mutates anything beyond
the ``CampaignState`` it is handed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from noir.showrunner.pacing import SEASON_EPISODE_COUNT

if TYPE_CHECKING:
    from noir.world.state import CampaignState


class TensionEvent(StrEnum):
    """Named events that adjust campaign tension."""

    CASE_SUCCESS = "case_success"
    CASE_PARTIAL = "case_partial"
    CASE_FAILED = "case_failed"
    PUBLIC_MOVE = "public_move"
    QUIET_BEAT = "quiet_beat"
    NEMESIS_TICK = "nemesis_tick"
    NEMESIS_CONFRONT = "nemesis_confront"
    SEASON_RESET = "season_reset"


_DELTAS: dict[TensionEvent, int] = {
    TensionEvent.CASE_SUCCESS: -12,
    TensionEvent.CASE_PARTIAL: 4,
    TensionEvent.CASE_FAILED: 22,
    TensionEvent.PUBLIC_MOVE: 6,
    TensionEvent.QUIET_BEAT: -8,
    TensionEvent.NEMESIS_TICK: 3,
    TensionEvent.NEMESIS_CONFRONT: 18,
    TensionEvent.SEASON_RESET: -30,
}


# Target curve over a season: setup -> spike -> trough -> rising -> finale peak.
_TARGET_CURVE: tuple[int, ...] = (25, 40, 65, 50, 85)


def target_for_episode(season_episode: int) -> int:
    normalized = max(1, int(season_episode))
    slot = (normalized - 1) % SEASON_EPISODE_COUNT
    if slot < len(_TARGET_CURVE):
        return _TARGET_CURVE[slot]
    return _TARGET_CURVE[-1]


def apply_event(campaign: "CampaignState", event: TensionEvent, magnitude: int = 1) -> int:
    """Apply a named event and return the new tension value."""

    delta = _DELTAS.get(event, 0) * max(1, int(magnitude))
    campaign.tension.record(campaign.tension.value + delta)
    return campaign.tension.value


def gap_to_target(campaign: "CampaignState", season_episode: int) -> int:
    """Positive: current is below target. Negative: above target."""

    return target_for_episode(season_episode) - campaign.tension.value


def sustained_high(campaign: "CampaignState", *, threshold: int = 75, samples: int = 3) -> bool:
    """True when tension has been at-or-above ``threshold`` for ``samples`` records."""

    if campaign.tension.value < threshold:
        return False
    recent = campaign.tension.history[-(samples - 1) :] if samples > 1 else []
    return all(value >= threshold for value in recent) and len(recent) >= max(0, samples - 1)


def recommend_archetype_bias(campaign: "CampaignState", season_episode: int) -> str | None:
    """Suggest a bias label for the scheduler based on the tension gap.

    Returns a short string token the scheduler can interpret:
      - ``"need_raise"`` — tension is well below target, push intensity
      - ``"need_breather"`` — tension is well above target, give relief
      - ``None`` — current value is acceptable for this slot
    """

    gap = gap_to_target(campaign, season_episode)
    if gap >= 20:
        return "need_raise"
    if gap <= -20:
        return "need_breather"
    return None
