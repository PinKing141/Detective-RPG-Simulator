from noir.investigation.outcomes import ArrestResult, CaseOutcome
from noir.showrunner.pacing import SEASON_EPISODE_COUNT, schedule_case_payload, season_beat_for_episode
from noir.showrunner.scheduler import advance_episode, ensure_case_queue
from noir.world.state import CampaignState, WorldState


def test_schedule_case_payload_uses_wave_and_cooldowns() -> None:
    opening = schedule_case_payload(1, pressure=0, last_outcome=None)
    assert opening["archetype"] == "character"
    assert opening["beat"] == season_beat_for_episode(1).label

    cooldown = schedule_case_payload(2, pressure=4, last_outcome=None)
    assert cooldown["archetype"] == "character"
    assert cooldown["reason"] == "cooldown_pressure"

    closing = schedule_case_payload(SEASON_EPISODE_COUNT, pressure=2, last_outcome=None, endgame_ready=True)
    assert closing["archetype"] == "pattern"
    assert closing["reason"] == "closing_in"


def test_scheduler_rolls_into_a_new_season() -> None:
    campaign = CampaignState(season_index=1, episode_index=SEASON_EPISODE_COUNT)

    advance_episode(campaign)

    assert campaign.season_index == 2
    assert campaign.episode_index == 1
    assert campaign.case_queue == []


def test_scheduler_builds_season_aware_queue_payloads() -> None:
    campaign = CampaignState(season_index=2, episode_index=4)

    ensure_case_queue(campaign, pressure=1, case_history=[], target_size=3)

    assert [payload["season"] for payload in campaign.case_queue] == ["2", "2", "3"]
    assert [payload["episode"] for payload in campaign.case_queue] == ["4", "5", "1"]


def test_case_start_modifiers_reflect_recent_failed_case() -> None:
    world = WorldState()
    world.apply_case_outcome(
        CaseOutcome(
            arrest_result=ArrestResult.FAILED,
            trust_delta=-2,
            pressure_delta=3,
            notes=["Wrong arrest burned the room."],
        ),
        case_id="case_failed",
        seed=7,
        district="harbor",
        location_name="Dock Office",
        started_tick=0,
        ended_tick=4,
    )

    modifiers = world.case_start_modifiers("harbor", "Dock Office")

    assert modifiers.cooperation < 0.6
    assert modifiers.lead_deadline_delta >= 2
    assert any("Wrong-arrest fallout carries over" in line for line in modifiers.briefing_lines)


def test_nemesis_dossier_summarizes_visible_cross_case_file() -> None:
    world = WorldState()

    updated = world.update_nemesis_dossier(
        "case_007",
        signature_meta={
            "token": "tarot card",
            "staging": "posed",
            "message": "taunting note",
            "placement_hint": "near the body",
        },
        pattern_label="Recurring Detail",
        pattern_observations=["A staged token appears in plain view."],
        nemesis_case=True,
        method_category="sharp",
        nemesis_tone="watchful",
        method_compromised=True,
        outcome_notes=["Pattern file notes a compromised method."],
    )

    lines = world.nemesis_dossier_lines()

    assert updated is True
    assert any("Cases filed: 1." in line for line in lines)
    assert any("Repeated traces" in line for line in lines)
    assert any("tarot card left posed." in line for line in lines)
    assert any("Method lines logged" in line for line in lines)
    assert any("case_007: Recurring Detail" in line for line in lines)