"""Season pacing rules for campaign case scheduling."""

from __future__ import annotations

from dataclasses import dataclass

from noir.cases.archetypes import CaseArchetype
from noir.investigation.outcomes import ArrestResult


SEASON_EPISODE_COUNT = 5

_TENSION_WAVE: tuple[tuple[str, CaseArchetype], ...] = (
    ("opening_character", CaseArchetype.CHARACTER),
    ("baseline_groundwork", CaseArchetype.BASELINE),
    ("pressure_spike", CaseArchetype.PRESSURE),
    ("foreshadowing_turn", CaseArchetype.FORESHADOWING),
    ("pattern_reckoning", CaseArchetype.PATTERN),
)


@dataclass(frozen=True)
class SeasonBeat:
    season_episode: int
    label: str
    archetype: CaseArchetype


def season_beat_for_episode(episode_index: int) -> SeasonBeat:
    normalized = max(1, episode_index)
    slot = (normalized - 1) % SEASON_EPISODE_COUNT
    label, archetype = _TENSION_WAVE[slot]
    return SeasonBeat(
        season_episode=slot + 1,
        label=label,
        archetype=archetype,
    )


def schedule_case_payload(
    episode_index: int,
    pressure: int,
    last_outcome: str | None,
    *,
    endgame_ready: bool = False,
) -> dict[str, str]:
    beat = season_beat_for_episode(episode_index)
    archetype = beat.archetype
    reason = "tension_wave"
    beat_label = beat.label

    if last_outcome == ArrestResult.FAILED.value:
        archetype = CaseArchetype.CHARACTER
        reason = "cooldown_after_failure"
        beat_label = "aftermath"
    elif pressure >= 4:
        archetype = CaseArchetype.CHARACTER
        reason = "cooldown_pressure"
        beat_label = "cooldown"
    elif (
        pressure <= 1
        and archetype == CaseArchetype.CHARACTER
        and beat.season_episode > 1
    ):
        archetype = CaseArchetype.PRESSURE
        reason = "pressure_spike"
        beat_label = "pressure_spike"
    elif endgame_ready and beat.season_episode >= SEASON_EPISODE_COUNT - 1:
        archetype = CaseArchetype.PATTERN
        reason = "closing_in"
        beat_label = "closing_in"

    return {
        "archetype": archetype.value,
        "reason": reason,
        "beat": beat_label,
        "episode": str(beat.season_episode),
    }