"""Season pacing and case scheduling helpers."""

from noir.showrunner.pacing import SEASON_EPISODE_COUNT, schedule_case_payload
from noir.showrunner.scheduler import advance_episode, ensure_case_queue, pop_next_case
from noir.showrunner.seasons import (
    MainlineBeat,
    SeasonTheme,
    all_themes,
    mainline_beat_for,
    theme_for_season,
)
from noir.showrunner.tension import (
    TensionEvent,
    apply_event,
    gap_to_target,
    recommend_archetype_bias,
    sustained_high,
    target_for_episode,
)

__all__ = [
    "SEASON_EPISODE_COUNT",
    "MainlineBeat",
    "SeasonTheme",
    "TensionEvent",
    "advance_episode",
    "all_themes",
    "apply_event",
    "ensure_case_queue",
    "gap_to_target",
    "mainline_beat_for",
    "pop_next_case",
    "recommend_archetype_bias",
    "schedule_case_payload",
    "sustained_high",
    "target_for_episode",
    "theme_for_season",
]
