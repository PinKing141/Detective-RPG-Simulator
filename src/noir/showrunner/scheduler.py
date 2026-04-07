"""Case queue helpers for season-based play."""

from __future__ import annotations

from typing import TYPE_CHECKING

from noir.showrunner.pacing import SEASON_EPISODE_COUNT, schedule_case_payload

if TYPE_CHECKING:
    from noir.world.state import CampaignState, CaseRecord


def ensure_case_queue(
    campaign: "CampaignState",
    pressure: int,
    case_history: list["CaseRecord"],
    *,
    target_size: int = 1,
    endgame_ready: bool = False,
) -> None:
    while len(campaign.case_queue) < target_size:
        queue_offset = len(campaign.case_queue)
        absolute_episode = campaign.episode_index + queue_offset
        season_offset = max(0, absolute_episode - 1) // SEASON_EPISODE_COUNT
        season_index = campaign.season_index + season_offset
        season_episode = ((absolute_episode - 1) % SEASON_EPISODE_COUNT) + 1
        last_outcome = case_history[-1].outcome if case_history else None
        payload = schedule_case_payload(
            season_episode,
            pressure,
            last_outcome,
            endgame_ready=endgame_ready,
        )
        payload["season"] = str(season_index)
        campaign.case_queue.append(payload)


def pop_next_case(
    campaign: "CampaignState",
    pressure: int,
    case_history: list["CaseRecord"],
    *,
    endgame_ready: bool = False,
) -> dict[str, str] | None:
    if not campaign.case_queue:
        ensure_case_queue(
            campaign,
            pressure,
            case_history,
            target_size=1,
            endgame_ready=endgame_ready,
        )
    if not campaign.case_queue:
        return None
    return campaign.case_queue.pop(0)


def advance_episode(campaign: "CampaignState") -> None:
    next_episode = campaign.episode_index + 1
    if next_episode > SEASON_EPISODE_COUNT:
        campaign.season_index += 1
        campaign.episode_index = 1
        campaign.case_queue.clear()
        return
    campaign.episode_index = next_episode