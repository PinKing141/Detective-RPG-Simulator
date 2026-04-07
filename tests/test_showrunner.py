from noir.showrunner.pacing import SEASON_EPISODE_COUNT, schedule_case_payload, season_beat_for_episode
from noir.showrunner.scheduler import advance_episode, ensure_case_queue
from noir.world.state import CampaignState


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