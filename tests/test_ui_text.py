"""Readability pass tests for the UI text helpers.

These cover the player-facing string shapes that the Textual app and
the CLI both rely on. Pure-function tests — no UI standup required.
"""

from __future__ import annotations

from noir.narrative.gaze import GazeMode
from noir.investigation.op_pipeline import (
    EVIDENCE_REQUIRED_SUMMARY,
    HYPOTHESIS_REQUIRED_SUMMARY,
    WARRANT_REQUIRED_FOR_RAID,
)
from noir.investigation.operations import OperationType
from noir.ui.text import (
    HeaderSnapshot,
    NO_ACTIONS_YET,
    NO_WORLD_NOTES,
    POST_ARREST_TITLE,
    TAB_LABELS,
    compose_debrief_case_block,
    compose_episode_banner,
    compose_episode_log_line,
    compose_header_line,
    compose_hypothesis_line,
    compose_intro_help_line,
    compose_load_confirmation,
    compose_now_line,
    compose_save_confirmation,
    compose_save_prompt,
    compose_snapshot_block,
    tab_label,
)


# ---------------------------------------------------------------------------
# Tab labels stay canonical and detail-pane titles reuse them
# ---------------------------------------------------------------------------


def test_tab_label_returns_canonical_string() -> None:
    assert tab_label("evidence") == "Case File"
    assert tab_label("leads") == "Leads"
    assert tab_label("pois") == "Scene"
    assert tab_label("profile") == "Profile"
    assert tab_label("pattern") == "Pattern"
    assert tab_label("summary") == "Debrief"


def test_tab_label_set_is_complete_and_unique() -> None:
    assert len(set(TAB_LABELS.values())) == len(TAB_LABELS)


# ---------------------------------------------------------------------------
# Header line
# ---------------------------------------------------------------------------


def _snap(**overrides) -> HeaderSnapshot:
    defaults: dict = dict(
        case_id="23-001",
        episode_code="S1E2",
        episode_title="Hard to Swallow",
        time=4,
        pressure=3,
        trust=4,
        gaze_mode=GazeMode.FORENSIC,
    )
    defaults.update(overrides)
    return HeaderSnapshot(**defaults)


def test_header_line_uses_pipe_separators_and_consistent_field_names() -> None:
    line = compose_header_line(_snap())

    assert "Case 23-001" in line
    assert 'S1E2 "Hard to Swallow"' in line
    assert "Time 4/" in line
    assert "Pressure 3/" in line
    assert "Trust 4/" in line
    assert "Gaze: Forensic" in line
    assert line.count(" | ") >= 4


def test_header_line_omits_episode_when_unknown() -> None:
    line = compose_header_line(_snap(episode_code="", episode_title=""))

    assert "S1E2" not in line
    assert line.startswith("Case 23-001 | Time")


# ---------------------------------------------------------------------------
# Episode banner / log line — must not drift
# ---------------------------------------------------------------------------


def test_episode_banner_and_log_line_use_the_same_dash() -> None:
    banner = compose_episode_banner("S1E2", "Hard to Swallow")
    log_line = compose_episode_log_line("S1E2", "Hard to Swallow")

    assert "EPISODE S1E2 - Hard to Swallow" in banner
    assert log_line == "Episode S1E2 - Hard to Swallow"
    # Both forms use ASCII hyphen, not em-dash, so they cannot drift.
    assert "—" not in banner
    assert "—" not in log_line


def test_episode_banner_falls_back_when_missing_title() -> None:
    banner = compose_episode_banner("", "")
    assert "EPISODE" in banner.splitlines()[1]


# ---------------------------------------------------------------------------
# Snapshot block — consistent label style (no colons)
# ---------------------------------------------------------------------------


def test_snapshot_block_uses_label_value_pairs_without_colons() -> None:
    block = compose_snapshot_block("harbor", "Dock Office", pressure=2, trust=4)

    assert block[0] == "Case snapshot"
    assert block[1] == "District harbor"
    assert block[2] == "Location Dock Office"
    assert block[3].startswith("Pressure 2/")
    assert block[4].startswith("Trust 4/")
    for line in block[1:]:
        assert ":" not in line


# ---------------------------------------------------------------------------
# "What matters now" line
# ---------------------------------------------------------------------------


def _now_kwargs(**overrides):
    base = dict(
        pressure=2,
        trust=4,
        tension=40,
        nemesis_clock=2,
        nemesis_clock_max=10,
        nemesis_confronted=False,
        endgame_ready=False,
        pending_lead_count=3,
    )
    base.update(overrides)
    return base


def test_now_line_prioritises_endgame() -> None:
    line = compose_now_line(**_now_kwargs(endgame_ready=True, pressure=5))
    assert line.startswith("Now:")
    assert "endgame" in line.lower()


def test_now_line_flags_nemesis_pushback_over_pressure() -> None:
    line = compose_now_line(**_now_kwargs(nemesis_confronted=True, pressure=5))
    assert "nemesis" in line.lower()


def test_now_line_flags_critical_pressure() -> None:
    line = compose_now_line(**_now_kwargs(pressure=5))
    assert "pressure" in line.lower()


def test_now_line_flags_thin_trust() -> None:
    line = compose_now_line(**_now_kwargs(trust=1))
    assert "trust" in line.lower()


def test_now_line_flags_no_active_leads() -> None:
    line = compose_now_line(**_now_kwargs(pending_lead_count=0))
    assert "lead" in line.lower()


def test_now_line_offers_quiet_window_when_state_is_calm() -> None:
    line = compose_now_line(**_now_kwargs(tension=10, pressure=0, pending_lead_count=4))
    assert "quiet" in line.lower()


def test_now_line_always_begins_with_now() -> None:
    line = compose_now_line(**_now_kwargs())
    assert line.startswith("Now:")


# ---------------------------------------------------------------------------
# Hypothesis line
# ---------------------------------------------------------------------------


def test_hypothesis_line_handles_no_hypothesis() -> None:
    assert compose_hypothesis_line(None, [], 0) == "Hypothesis: none"


def test_hypothesis_line_formats_claims_and_evidence() -> None:
    line = compose_hypothesis_line(
        "Mina Vale", ["Present near the scene", "Motive linked to the victim"], 3
    )
    assert line == (
        "Hypothesis: Mina Vale | "
        "Claims: Present near the scene, Motive linked to the victim | "
        "Evidence: 3"
    )


# ---------------------------------------------------------------------------
# Intro help
# ---------------------------------------------------------------------------


def test_intro_help_line_is_a_single_compact_sentence() -> None:
    line = compose_intro_help_line()
    assert "\n" not in line
    assert "q to quit" in line


# ---------------------------------------------------------------------------
# Debrief case block matches the snapshot style (no colons)
# ---------------------------------------------------------------------------


def test_debrief_case_block_uses_bare_label_value_style() -> None:
    block = compose_debrief_case_block(
        "23-014",
        "harbor",
        "Dock Office",
        scene_mode="interior",
        pattern_label="Burned bridge",
    )

    assert block == [
        "Case 23-014",
        "District harbor",
        "Location Dock Office",
        "Scene mode interior",
        "Pattern Burned bridge",
    ]
    for line in block:
        assert ":" not in line


def test_debrief_case_block_skips_optional_fields_when_empty() -> None:
    block = compose_debrief_case_block("23-014", "harbor", "Dock Office")

    assert block == [
        "Case 23-014",
        "District harbor",
        "Location Dock Office",
    ]


# ---------------------------------------------------------------------------
# Save / load wording: one canonical form everywhere
# ---------------------------------------------------------------------------


def test_save_confirmation_uses_canonical_form() -> None:
    assert compose_save_confirmation("/tmp/save.json") == (
        "Investigation saved to /tmp/save.json."
    )


def test_load_confirmation_uses_canonical_form() -> None:
    assert compose_load_confirmation("23-014") == (
        "Investigation loaded for 23-014."
    )


def test_save_prompt_uses_canonical_form() -> None:
    prompt = compose_save_prompt("23-014")
    assert prompt.startswith("Saved investigation found for 23-014.")
    assert prompt.endswith("[Y/n] ")


# ---------------------------------------------------------------------------
# Constants used by detail panes
# ---------------------------------------------------------------------------


def test_post_arrest_title_has_no_case_id() -> None:
    # The title must not embed any technical identifier.
    assert POST_ARREST_TITLE == "Post-arrest statement"
    assert "(" not in POST_ARREST_TITLE


def test_placeholder_strings_are_parenthesised_one_liners() -> None:
    assert NO_ACTIONS_YET.startswith("(") and NO_ACTIONS_YET.endswith(")")
    assert NO_WORLD_NOTES.startswith("(") and NO_WORLD_NOTES.endswith(")")


# ---------------------------------------------------------------------------
# Drift canary: every operation type has both gate-strings in the pipeline
# ---------------------------------------------------------------------------


def test_every_operation_type_has_a_hypothesis_required_summary() -> None:
    for op_type in OperationType:
        message = HYPOTHESIS_REQUIRED_SUMMARY[op_type]
        assert message.startswith("Set a hypothesis before ")
        assert message.endswith(".")


def test_every_operation_type_has_an_evidence_required_summary() -> None:
    for op_type in OperationType:
        message = EVIDENCE_REQUIRED_SUMMARY[op_type]
        assert message.startswith("Select supporting evidence before ")
        assert message.endswith(".")


def test_warrant_required_for_raid_message_is_a_single_sentence() -> None:
    assert "\n" not in WARRANT_REQUIRED_FOR_RAID
    assert WARRANT_REQUIRED_FOR_RAID.endswith(".")
