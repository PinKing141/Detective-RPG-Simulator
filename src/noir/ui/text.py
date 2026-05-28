"""Player-facing string composition helpers.

This module owns the canonical format for headers, banners, snapshots,
tab labels, and the "now" headline shown at the top of every briefing.
The Textual app routes through these helpers so casing, punctuation,
and terminology stay consistent. Pure functions — easy to unit-test
without standing up the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from noir.investigation.costs import PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.outcomes import TRUST_LIMIT
from noir.narrative.gaze import GazeMode, gaze_label


# Canonical tab labels. The detail-pane title for each tab MUST match
# the label exactly; that's enforced by tests below.
TAB_LABELS: dict[str, str] = {
    "evidence": "Case File",
    "leads": "Leads",
    "pois": "Scene",
    "profile": "Profile",
    "pattern": "Pattern",
    "summary": "Debrief",
}


def tab_label(key: str) -> str:
    return TAB_LABELS.get(key, key.title())


@dataclass(frozen=True)
class HeaderSnapshot:
    case_id: str
    episode_code: str
    episode_title: str
    time: int
    pressure: int
    trust: int
    gaze_mode: GazeMode


def compose_header_line(snap: HeaderSnapshot) -> str:
    """Single canonical status line for the top of the case file.

    Format:
      Case 23-001 | S1E2 "Hard to Swallow" | Time 4/12 | Pressure 3/6 | Trust 4/6 | Gaze: Forensic
    """

    parts = [f"Case {snap.case_id}"]
    if snap.episode_code:
        episode = snap.episode_code
        if snap.episode_title:
            episode = f'{episode} "{snap.episode_title}"'
        parts.append(episode)
    parts.append(f"Time {snap.time}/{TIME_LIMIT}")
    parts.append(f"Pressure {snap.pressure}/{PRESSURE_LIMIT}")
    parts.append(f"Trust {snap.trust}/{TRUST_LIMIT}")
    parts.append(f"Gaze: {gaze_label(snap.gaze_mode)}")
    return " | ".join(parts)


def compose_episode_banner(episode_code: str, episode_title: str) -> str:
    """Three-line banner that opens the briefing view.

    Always uses an ASCII em-dash separator and title-style casing so it
    cannot drift from the intro line written to the log.
    """

    label = "EPISODE"
    if episode_code and episode_title:
        label = f"EPISODE {episode_code} - {episode_title}"
    elif episode_code:
        label = f"EPISODE {episode_code}"
    elif episode_title:
        label = f"EPISODE - {episode_title}"
    rule_len = max(28, len(label) + 8)
    rule = "-" * rule_len
    return f"{rule}\n{label}\n{rule}"


def compose_episode_log_line(episode_code: str, episode_title: str) -> str:
    """Single-line variant for the wire log; matches the banner labelling."""

    if episode_code and episode_title:
        return f"Episode {episode_code} - {episode_title}"
    if episode_code:
        return f"Episode {episode_code}"
    return f"Episode - {episode_title}"


def compose_snapshot_block(district: str, location: str, pressure: int, trust: int) -> list[str]:
    """The compact 'Case snapshot' box on the briefing view."""

    return [
        "Case snapshot",
        f"District {district}",
        f"Location {location}",
        f"Pressure {pressure}/{PRESSURE_LIMIT}",
        f"Trust {trust}/{TRUST_LIMIT}",
    ]


def compose_now_line(
    *,
    pressure: int,
    trust: int,
    tension: int,
    nemesis_clock: int,
    nemesis_clock_max: int,
    nemesis_confronted: bool,
    endgame_ready: bool,
    pending_lead_count: int,
) -> str:
    """A single sentence answering 'what should I worry about right now'.

    Priority order, highest urgency first. Each branch is short on
    purpose: this line sits at the very top of the briefing body.
    """

    if endgame_ready:
        return "Now: endgame is armed — the next move closes the season."
    if nemesis_confronted:
        return "Now: the nemesis is pushing back — expect direct interference."
    if nemesis_clock >= nemesis_clock_max - 1:
        return "Now: the nemesis's own clock is almost out."
    if pressure >= PRESSURE_LIMIT - 1:
        return "Now: pressure is critical — command wants movement, not analysis."
    if trust <= 1:
        return "Now: trust is thin — witnesses will not give you the benefit of the doubt."
    if tension >= 75:
        return "Now: the city is loud — move carefully, anything visible escalates."
    if pending_lead_count == 0:
        return "Now: no active leads — open one before the trail goes cold."
    if tension <= 25 and pressure <= 1:
        return "Now: quiet — a good window for groundwork."
    return "Now: work the leads on the board."


def compose_hypothesis_line(
    suspect_name: str | None,
    claim_labels: list[str],
    evidence_count: int,
) -> str:
    """One-line summary of the current hypothesis state."""

    if suspect_name is None:
        return "Hypothesis: none"
    claims = ", ".join(claim_labels) if claim_labels else "none"
    return f"Hypothesis: {suspect_name} | Claims: {claims} | Evidence: {evidence_count}"


def compose_intro_help_line() -> str:
    """One compact help line shown on first case mount only."""

    return (
        "Tip: Enter on the Actions list to act. "
        "Tab cycles panes, G toggles gaze, ? for full help, q to quit."
    )
