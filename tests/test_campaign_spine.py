"""Phase 4 campaign spine tests.

Covers the cross-cutting layer:
  - Season theme + mainline beat injection in the case queue
  - Tension wave target curve and event-driven shifts
  - Nemesis clock + awareness counters + confrontation latch
  - Early endings: burnout, corruption, nemesis coup
  - Final endings: triumphant / pyrrhic / compromised / stalemate / defeat
  - Save / load round-trip for all new campaign fields
"""

from __future__ import annotations

from noir.investigation.outcomes import ArrestResult, CaseOutcome
from noir.narrative.endings import build_final_ending, check_early_ending
from noir.showrunner.pacing import SEASON_EPISODE_COUNT
from noir.showrunner.scheduler import advance_episode, ensure_case_queue, pop_next_case
from noir.showrunner.seasons import (
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
from noir.world.state import (
    CampaignState,
    EndgameState,
    MistakeRecord,
    WorldState,
)


# ---------------------------------------------------------------------------
# Season themes + mainline beats
# ---------------------------------------------------------------------------


def test_theme_is_deterministic_per_season_index() -> None:
    first = theme_for_season(1)
    second = theme_for_season(2)
    again = theme_for_season(1)
    assert first.slug == again.slug
    assert first.slug != second.slug


def test_mainline_beat_overrides_archetype_in_queue() -> None:
    campaign = CampaignState(season_index=1, episode_index=1)

    ensure_case_queue(campaign, pressure=0, case_history=[], target_size=SEASON_EPISODE_COUNT)

    theme = theme_for_season(1)
    queue_by_episode = {payload["episode"]: payload for payload in campaign.case_queue}
    for beat in theme.mainline_beats:
        payload = queue_by_episode[str(beat.slot)]
        assert payload["mainline"] == "true"
        assert payload["beat"] == beat.label
        assert payload["archetype"] == beat.archetype.value
        assert payload["season_theme"] == theme.slug


def test_popping_a_mainline_case_marks_it_completed_and_prevents_duplicates() -> None:
    campaign = CampaignState(season_index=1, episode_index=1)
    ensure_case_queue(campaign, pressure=0, case_history=[], target_size=1)
    first = pop_next_case(campaign, pressure=0, case_history=[])
    assert first is not None

    # If the first slot was a mainline beat, popping should have recorded it
    if first.get("mainline") == "true":
        assert first["beat"] in campaign.season_beats_completed

    # Re-fill with the same slot offset and the mainline should not be injected again
    campaign.episode_index = 1
    campaign.case_queue.clear()
    ensure_case_queue(campaign, pressure=0, case_history=[], target_size=1)
    second = pop_next_case(campaign, pressure=0, case_history=[])
    if first.get("mainline") == "true":
        assert second != first or second.get("mainline") == "false"


def test_advance_episode_resets_beats_on_season_roll() -> None:
    campaign = CampaignState(season_index=1, episode_index=SEASON_EPISODE_COUNT)
    campaign.season_beats_completed.append("harbor_finale")

    advance_episode(campaign)

    assert campaign.season_index == 2
    assert campaign.season_beats_completed == []
    assert campaign.season_theme == theme_for_season(2).slug


# ---------------------------------------------------------------------------
# Tension wave
# ---------------------------------------------------------------------------


def test_target_curve_rises_into_the_finale() -> None:
    targets = [target_for_episode(slot) for slot in range(1, SEASON_EPISODE_COUNT + 1)]
    assert targets[-1] == max(targets), "finale slot should hold the highest target"
    assert targets[0] < targets[2], "opener should be quieter than midseason spike"


def test_apply_event_moves_value_and_records_history() -> None:
    campaign = CampaignState()
    start = campaign.tension.value

    apply_event(campaign, TensionEvent.CASE_FAILED)

    assert campaign.tension.value > start
    assert campaign.tension.history[-1] == start
    assert campaign.tension.peak >= campaign.tension.value


def test_tension_clamped_to_zero_and_hundred() -> None:
    campaign = CampaignState()
    for _ in range(20):
        apply_event(campaign, TensionEvent.CASE_FAILED)
    assert campaign.tension.value <= 100

    for _ in range(40):
        apply_event(campaign, TensionEvent.QUIET_BEAT)
    assert campaign.tension.value >= 0


def test_recommend_bias_pushes_breather_when_above_target() -> None:
    campaign = CampaignState()
    campaign.tension.value = 90
    assert recommend_archetype_bias(campaign, season_episode=1) == "need_breather"

    campaign.tension.value = 5
    assert recommend_archetype_bias(campaign, season_episode=3) == "need_raise"


def test_sustained_high_requires_recent_history() -> None:
    campaign = CampaignState()
    assert not sustained_high(campaign, threshold=80, samples=3)
    campaign.tension.record(82)
    campaign.tension.record(85)
    campaign.tension.record(88)
    assert sustained_high(campaign, threshold=80, samples=3)


def test_gap_is_positive_when_below_target() -> None:
    campaign = CampaignState()
    campaign.tension.value = 10
    assert gap_to_target(campaign, season_episode=3) > 0


# ---------------------------------------------------------------------------
# Case outcomes wire into tension + nemesis arc
# ---------------------------------------------------------------------------


def test_failed_case_outcome_raises_tension() -> None:
    world = WorldState()
    start = world.campaign.tension.value

    world.apply_case_outcome(
        CaseOutcome(arrest_result=ArrestResult.FAILED, trust_delta=-2, pressure_delta=3, notes=[]),
        case_id="c1",
        seed=1,
        district="harbor",
        location_name="Dock",
        started_tick=0,
        ended_tick=1,
    )

    assert world.campaign.tension.value > start


def test_successful_case_lowers_tension() -> None:
    world = WorldState()
    world.campaign.tension.value = 60

    world.apply_case_outcome(
        CaseOutcome(arrest_result=ArrestResult.SUCCESS, trust_delta=1, pressure_delta=-1, notes=[]),
        case_id="c2",
        seed=2,
        district="harbor",
        location_name="Dock",
        started_tick=0,
        ended_tick=1,
    )

    assert world.campaign.tension.value < 60


def test_advance_episode_ticks_nemesis_clock_and_returns_notes() -> None:
    world = WorldState()
    world.campaign.nemesis_arc.clock = world.campaign.nemesis_arc.clock_max - 1

    notes = world.advance_episode()

    assert world.campaign.nemesis_arc.clock == world.campaign.nemesis_arc.clock_max
    assert world.campaign.nemesis_arc.coup_fired is True
    assert any("clock" in line.lower() for line in notes)


def test_update_closing_in_raises_nemesis_awareness() -> None:
    world = WorldState()
    before = world.campaign.nemesis_arc.awareness

    world.update_closing_in("signature", profile_used=True, proof_met=True)

    assert world.campaign.nemesis_arc.awareness > before


def test_confrontation_latches_when_progress_and_awareness_align() -> None:
    world = WorldState()
    for _ in range(3):
        world.update_closing_in("signature", profile_used=True, proof_met=True)

    arc = world.campaign.nemesis_arc
    assert arc.confronted is True


# ---------------------------------------------------------------------------
# Early endings
# ---------------------------------------------------------------------------


def test_burnout_ending_requires_sustained_high_tension_and_low_trust() -> None:
    world = WorldState()
    world.trust = 2
    for value in (82, 85, 88, 90):
        world.campaign.tension.record(value)

    result = check_early_ending(world)

    assert result is not None
    assert result.kind == "burnout"


def test_corruption_ending_fires_on_coercive_dominance_and_wrong_arrests() -> None:
    world = WorldState()
    world.campaign.identity.coercive = 6
    world.mistake_history["wrong_arrest"] = MistakeRecord(key="wrong_arrest", count=2, last_case_id="c1")

    result = check_early_ending(world)

    assert result is not None
    assert result.kind == "corruption"


def test_coup_ending_fires_when_clock_maxes_outside_endgame() -> None:
    world = WorldState()
    world.campaign.nemesis_arc.clock = world.campaign.nemesis_arc.clock_max
    world.campaign.nemesis_arc.coup_fired = False

    result = check_early_ending(world)

    assert result is not None
    assert result.kind == "nemesis_coup"
    assert world.campaign.nemesis_arc.coup_fired is True


def test_coup_ending_does_not_fire_after_endgame_active() -> None:
    world = WorldState()
    world.campaign.nemesis_arc.clock = world.campaign.nemesis_arc.clock_max
    world.campaign.endgame_state = EndgameState.ACTIVE

    result = check_early_ending(world)

    assert result is None


def test_institutional_breakdown_still_takes_priority() -> None:
    world = WorldState()
    world.trust = 1
    world.campaign.nemesis_arc.clock = world.campaign.nemesis_arc.clock_max

    result = check_early_ending(world)

    assert result is not None
    assert result.kind == "institutional_breakdown"


# ---------------------------------------------------------------------------
# Final endings
# ---------------------------------------------------------------------------


def test_clean_capture_under_peak_tension_yields_pyrrhic() -> None:
    world = WorldState()
    world.trust = 2
    world.campaign.endgame_result = "captured_clean"
    world.campaign.tension.peak = 90

    ending = build_final_ending(world)

    assert ending.kind == "pyrrhic"


def test_clean_capture_with_coercive_identity_yields_compromised() -> None:
    world = WorldState()
    world.campaign.endgame_result = "captured_clean"
    world.campaign.identity.dominant = "coercive"
    world.campaign.identity.coercive = 6

    ending = build_final_ending(world)

    assert ending.kind == "compromised"


def test_clean_capture_in_calm_state_yields_triumphant() -> None:
    world = WorldState()
    world.trust = 5
    world.campaign.endgame_result = "captured_clean"

    ending = build_final_ending(world)

    assert ending.kind == "triumphant"


def test_raid_wrong_yields_defeat() -> None:
    world = WorldState()
    world.campaign.endgame_result = "raid_wrong"

    ending = build_final_ending(world)

    assert ending.kind == "defeat"


def test_confronted_without_capture_yields_stalemate() -> None:
    world = WorldState()
    world.campaign.endgame_result = None
    world.campaign.nemesis_arc.confronted = True

    ending = build_final_ending(world)

    assert ending.kind == "stalemate"


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------


def test_campaign_state_to_dict_round_trip_preserves_spine_fields() -> None:
    campaign = CampaignState(season_index=2, episode_index=3)
    campaign.tension.record(40)
    campaign.tension.record(70)
    campaign.nemesis_arc.clock = 4
    campaign.nemesis_arc.awareness = 3
    campaign.nemesis_arc.confronted = True
    campaign.season_theme = "harbor_murders"
    campaign.season_beats_completed.append("harbor_inciting")
    campaign.case_queue.append({"archetype": "pressure", "beat": "midseason", "episode": "3"})

    payload = campaign.to_dict()
    restored = CampaignState.from_dict(payload)

    assert restored.tension.value == campaign.tension.value
    assert restored.tension.peak == campaign.tension.peak
    assert restored.tension.history == campaign.tension.history
    assert restored.nemesis_arc.clock == 4
    assert restored.nemesis_arc.awareness == 3
    assert restored.nemesis_arc.confronted is True
    assert restored.season_theme == "harbor_murders"
    assert restored.season_beats_completed == ["harbor_inciting"]
    assert restored.case_queue == campaign.case_queue


def test_world_store_persists_spine_fields(tmp_path) -> None:
    from noir.persistence.db import WorldStore

    path = tmp_path / "world.db"
    store = WorldStore(path)
    world = store.load_world_state()
    world.campaign.tension.record(55)
    world.campaign.tension.record(80)
    world.campaign.nemesis_arc.clock = 5
    world.campaign.nemesis_arc.awareness = 4
    world.campaign.season_theme = "city_hall_rot"
    world.campaign.season_beats_completed.append("hall_inciting")
    store.save_world_state(world)
    store.close()

    store = WorldStore(path)
    reloaded = store.load_world_state()
    store.close()

    assert reloaded.campaign.tension.value == 80
    assert reloaded.campaign.tension.peak == 80
    assert reloaded.campaign.nemesis_arc.clock == 5
    assert reloaded.campaign.nemesis_arc.awareness == 4
    assert reloaded.campaign.season_theme == "city_hall_rot"
    assert reloaded.campaign.season_beats_completed == ["hall_inciting"]


def test_mainline_beat_lookup_returns_archetype_for_known_slot() -> None:
    theme = theme_for_season(1)
    assert theme.mainline_beats
    first_slot = theme.mainline_beats[0].slot
    beat = mainline_beat_for(1, first_slot)
    assert beat is not None
    assert beat.archetype == theme.mainline_beats[0].archetype
