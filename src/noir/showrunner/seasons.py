"""Season themes and mainline beat scheduling for the campaign spine.

A season is the container that turns a string of isolated cases into an
arc. Each season has a thematic identity, a planned shape (which slots
hold mandatory mainline beats versus variable filler), and a target
tension curve. The same five-episode rhythm from ``pacing`` continues to
apply, but seasons stamp themes/beats onto each scheduled payload so
later layers (UI, endings, briefings) can read the arc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from noir.cases.archetypes import CaseArchetype
from noir.showrunner.pacing import SEASON_EPISODE_COUNT


@dataclass(frozen=True)
class MainlineBeat:
    """A locked story slot in a season."""

    slot: int
    label: str
    archetype: CaseArchetype


@dataclass(frozen=True)
class SeasonTheme:
    slug: str
    title: str
    opening_line: str
    finale_line: str
    mainline_beats: tuple[MainlineBeat, ...] = field(default_factory=tuple)

    def beat_for_slot(self, slot: int) -> MainlineBeat | None:
        for beat in self.mainline_beats:
            if beat.slot == slot:
                return beat
        return None


_THEMES: tuple[SeasonTheme, ...] = (
    SeasonTheme(
        slug="harbor_murders",
        title="The Harbor Murders",
        opening_line="The harbor reports another body at dawn; the season opens on tide-rotten ground.",
        finale_line="Whatever has been working the harbor wants to be seen tonight.",
        mainline_beats=(
            MainlineBeat(slot=1, label="harbor_inciting", archetype=CaseArchetype.BASELINE),
            MainlineBeat(slot=3, label="harbor_midseason", archetype=CaseArchetype.PRESSURE),
            MainlineBeat(slot=SEASON_EPISODE_COUNT, label="harbor_finale", archetype=CaseArchetype.PATTERN),
        ),
    ),
    SeasonTheme(
        slug="city_hall_rot",
        title="Rot in City Hall",
        opening_line="A clerk's death lands on your desk; nobody upstairs wants it lingering.",
        finale_line="The paper trail finally crosses the wrong office.",
        mainline_beats=(
            MainlineBeat(slot=1, label="hall_inciting", archetype=CaseArchetype.BASELINE),
            MainlineBeat(slot=3, label="hall_midseason", archetype=CaseArchetype.FORESHADOWING),
            MainlineBeat(slot=SEASON_EPISODE_COUNT, label="hall_finale", archetype=CaseArchetype.PATTERN),
        ),
    ),
    SeasonTheme(
        slug="riverside_silence",
        title="Riverside Silence",
        opening_line="A neighborhood that used to call you stops answering the phone.",
        finale_line="Whatever the riverside is hiding has run out of patience with you.",
        mainline_beats=(
            MainlineBeat(slot=2, label="river_inciting", archetype=CaseArchetype.CHARACTER),
            MainlineBeat(slot=3, label="river_midseason", archetype=CaseArchetype.PRESSURE),
            MainlineBeat(slot=SEASON_EPISODE_COUNT, label="river_finale", archetype=CaseArchetype.PATTERN),
        ),
    ),
)


def theme_for_season(season_index: int) -> SeasonTheme:
    """Pick a deterministic theme for a season index (1-based)."""

    normalized = max(1, int(season_index))
    return _THEMES[(normalized - 1) % len(_THEMES)]


def mainline_beat_for(season_index: int, season_episode: int) -> MainlineBeat | None:
    return theme_for_season(season_index).beat_for_slot(season_episode)


def all_themes() -> tuple[SeasonTheme, ...]:
    return _THEMES
