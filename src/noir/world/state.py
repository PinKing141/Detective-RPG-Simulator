"""World state and continuity helpers for Phase 3+."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.cases.archetypes import CaseArchetype
from noir.investigation.costs import PRESSURE_LIMIT, clamp
from noir.nemesis.state import NemesisState
from noir.investigation.outcomes import ArrestResult, CaseOutcome, TRUST_LIMIT
from noir.showrunner.scheduler import (
    advance_episode as advance_campaign_episode,
    ensure_case_queue as ensure_scheduled_case_queue,
    pop_next_case as pop_scheduled_case,
)
from noir.util.rng import Rng


class DistrictStatus(StrEnum):
    CALM = "calm"
    TENSE = "tense"
    VOLATILE = "volatile"


class EndgameState(StrEnum):
    INACTIVE = "inactive"
    READY = "ready"
    ACTIVE = "active"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    seed: int
    district: str
    started_tick: int
    ended_tick: int
    outcome: str
    trust_delta: int
    pressure_delta: int
    notes: list[str]


@dataclass(frozen=True)
class CaseStartModifiers:
    cooperation: float
    lead_deadline_delta: int
    briefing_lines: list[str]


@dataclass
class EpisodeTitleState:
    used_ids: list[int] = field(default_factory=list)
    recent_registers: list[str] = field(default_factory=list)
    recent_tags: list[str] = field(default_factory=list)


@dataclass
class ClosingInState:
    pattern: int = 0
    narrowing: int = 0
    proof: int = 0


@dataclass
class TensionState:
    """Campaign-level tension wave value (0-100) plus short history.

    The history is the last several values, used so that endings and
    pacing can read sustained pressure rather than a single instant.
    """

    value: int = 20
    history: list[int] = field(default_factory=list)
    peak: int = 20

    def record(self, new_value: int) -> None:
        bounded = max(0, min(int(new_value), 100))
        self.history.append(self.value)
        if len(self.history) > 8:
            del self.history[0 : len(self.history) - 8]
        self.value = bounded
        if bounded > self.peak:
            self.peak = bounded


@dataclass
class NemesisCampaignState:
    """Counters for the slow-burn nemesis arc across a season.

    ``clock`` is the nemesis's own plan progress and ticks forward each
    episode regardless of player action. ``awareness`` rises when the
    player makes loud or public moves and feeds back into how hostile
    nemesis-driven events are. ``confronted`` flips once both player
    progress and awareness have crossed their thresholds.
    """

    clock: int = 0
    clock_max: int = 10
    awareness: int = 0
    awareness_max: int = 10
    confronted: bool = False
    coup_fired: bool = False


@dataclass
class DetectiveIdentityState:
    coercive: int = 0
    analytical: int = 0
    social: int = 0
    risky: int = 0
    dominant: str | None = None
    dominant_streak: int = 0


@dataclass
class NPCMemoryRecord:
    person_id: str
    last_tone: str = "neutral"
    impact: str = "neutral"
    promise_integrity: str = "unknown"
    exposure_events: list[str] = field(default_factory=list)
    last_case_id: str = ""


@dataclass
class LocationReputationRecord:
    location_name: str
    trust_trend: int = 0
    friction: int = 0
    safety_noise: int = 0
    heat: int = 0


@dataclass
class MistakeRecord:
    key: str
    count: int = 0
    last_case_id: str = ""


@dataclass
class EscalationThread:
    key: str
    severity: int = 1
    timer: int = 0
    mutation: str = "dormant"


@dataclass
class CampaignState:
    season_index: int = 1
    episode_index: int = 1
    case_queue: list[dict[str, str]] = field(default_factory=list)
    closing_in: ClosingInState = field(default_factory=ClosingInState)
    identity: DetectiveIdentityState = field(default_factory=DetectiveIdentityState)
    ending_flags: list[str] = field(default_factory=list)
    endgame_state: EndgameState = EndgameState.INACTIVE
    endgame_result: str | None = None
    tension: TensionState = field(default_factory=TensionState)
    nemesis_arc: NemesisCampaignState = field(default_factory=NemesisCampaignState)
    season_theme: str = ""
    season_beats_completed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "season_index": self.season_index,
            "episode_index": self.episode_index,
            "case_queue": list(self.case_queue),
            "closing_in": {
                "pattern": self.closing_in.pattern,
                "narrowing": self.closing_in.narrowing,
                "proof": self.closing_in.proof,
            },
            "identity": {
                "coercive": self.identity.coercive,
                "analytical": self.identity.analytical,
                "social": self.identity.social,
                "risky": self.identity.risky,
                "dominant": self.identity.dominant,
                "dominant_streak": self.identity.dominant_streak,
            },
            "ending_flags": list(self.ending_flags),
            "endgame_state": self.endgame_state.value,
            "endgame_result": self.endgame_result,
            "tension": {
                "value": self.tension.value,
                "history": list(self.tension.history),
                "peak": self.tension.peak,
            },
            "nemesis_arc": {
                "clock": self.nemesis_arc.clock,
                "clock_max": self.nemesis_arc.clock_max,
                "awareness": self.nemesis_arc.awareness,
                "awareness_max": self.nemesis_arc.awareness_max,
                "confronted": self.nemesis_arc.confronted,
                "coup_fired": self.nemesis_arc.coup_fired,
            },
            "season_theme": self.season_theme,
            "season_beats_completed": list(self.season_beats_completed),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "CampaignState":
        closing = payload.get("closing_in", {}) or {}
        closing_in = ClosingInState(
            pattern=int(closing.get("pattern", 0)),
            narrowing=int(closing.get("narrowing", 0)),
            proof=int(closing.get("proof", 0)),
        )
        identity_payload = payload.get("identity", {}) or {}
        identity = DetectiveIdentityState(
            coercive=int(identity_payload.get("coercive", 0)),
            analytical=int(identity_payload.get("analytical", 0)),
            social=int(identity_payload.get("social", 0)),
            risky=int(identity_payload.get("risky", 0)),
            dominant=identity_payload.get("dominant"),
            dominant_streak=int(identity_payload.get("dominant_streak", 0)),
        )
        tension_payload = payload.get("tension", {}) or {}
        tension = TensionState(
            value=int(tension_payload.get("value", 20)),
            history=[int(v) for v in (tension_payload.get("history", []) or [])],
            peak=int(tension_payload.get("peak", tension_payload.get("value", 20))),
        )
        nemesis_payload = payload.get("nemesis_arc", {}) or {}
        nemesis_arc = NemesisCampaignState(
            clock=int(nemesis_payload.get("clock", 0)),
            clock_max=int(nemesis_payload.get("clock_max", 10)),
            awareness=int(nemesis_payload.get("awareness", 0)),
            awareness_max=int(nemesis_payload.get("awareness_max", 10)),
            confronted=bool(nemesis_payload.get("confronted", False)),
            coup_fired=bool(nemesis_payload.get("coup_fired", False)),
        )
        return cls(
            season_index=int(payload.get("season_index", 1)),
            episode_index=int(payload.get("episode_index", 1)),
            case_queue=list(payload.get("case_queue", []) or []),
            closing_in=closing_in,
            identity=identity,
            ending_flags=list(payload.get("ending_flags", []) or []),
            endgame_state=EndgameState(payload.get("endgame_state", EndgameState.INACTIVE.value)),
            endgame_result=payload.get("endgame_result"),
            tension=tension,
            nemesis_arc=nemesis_arc,
            season_theme=str(payload.get("season_theme", "") or ""),
            season_beats_completed=list(payload.get("season_beats_completed", []) or []),
        )

_ENDGAME_PATTERN_MIN = 2
_ENDGAME_NARROWING_MIN = 2
_ENDGAME_PROOF_MIN = 1


@dataclass(frozen=True)
class PersonRecord:
    person_id: str
    name: str
    role_tag: str
    country_of_origin: str | None
    religion_affiliation: str | None
    religion_observance: str | None
    community_connectedness: str | None
    created_in_case_id: str
    last_seen_case_id: str
    last_seen_tick: int


@dataclass
class WorldState:
    trust: int = 3
    pressure: int = 0
    nemesis_exposure: int = 0
    nemesis_state: NemesisState | None = None
    tick: int = 0
    district_status: dict[str, DistrictStatus] = field(default_factory=dict)
    location_status: dict[str, DistrictStatus] = field(default_factory=dict)
    case_history: list[CaseRecord] = field(default_factory=list)
    people_index: dict[str, PersonRecord] = field(default_factory=dict)
    npc_memory: dict[str, NPCMemoryRecord] = field(default_factory=dict)
    location_reputation: dict[str, LocationReputationRecord] = field(default_factory=dict)
    mistake_history: dict[str, MistakeRecord] = field(default_factory=dict)
    unresolved_threads: dict[str, EscalationThread] = field(default_factory=dict)
    episode_titles: EpisodeTitleState = field(default_factory=EpisodeTitleState)
    campaign: CampaignState = field(default_factory=CampaignState)

    def district_status_for(self, district: str) -> DistrictStatus:
        if district in self.district_status:
            return self.district_status[district]
        status = self._baseline_status()
        self.district_status[district] = status
        return status

    def apply_case_outcome(
        self,
        outcome: CaseOutcome,
        case_id: str,
        seed: int,
        district: str,
        location_name: str,
        started_tick: int,
        ended_tick: int,
        extra_notes: list[str] | None = None,
    ) -> list[str]:
        self.trust = int(clamp(self.trust + outcome.trust_delta, 0, TRUST_LIMIT))
        self.pressure = int(clamp(self.pressure + outcome.pressure_delta, 0, PRESSURE_LIMIT))
        self.tick = max(self.tick, ended_tick)
        notes: list[str] = []
        current = self.district_status_for(district)
        shifted = self._shift_status(current, outcome.arrest_result)
        if shifted != current:
            self.district_status[district] = shifted
            notes.append(f"District status shifted to {shifted.value}.")
        location_current = self.location_status_for(location_name)
        location_shifted = self._shift_status(location_current, outcome.arrest_result)
        if location_shifted != location_current:
            self.location_status[location_name] = location_shifted
            notes.append(f"Location status shifted to {location_shifted.value}.")
        record_notes = list(outcome.notes)
        if extra_notes:
            record_notes.extend([note for note in extra_notes if note])
        self.case_history.append(
            CaseRecord(
                case_id=case_id,
                seed=seed,
                district=district,
                started_tick=started_tick,
                ended_tick=ended_tick,
                outcome=outcome.arrest_result.value,
                trust_delta=outcome.trust_delta,
                pressure_delta=outcome.pressure_delta,
                notes=record_notes,
            )
        )
        self._apply_consequence_memory(
            outcome=outcome,
            case_id=case_id,
            location_name=location_name,
        )
        self._advance_unresolved_threads(case_id)
        tension_notes = self._apply_tension_for_outcome(outcome.arrest_result)
        notes.extend(tension_notes)
        return notes

    def _apply_tension_for_outcome(self, arrest_result: ArrestResult) -> list[str]:
        from noir.showrunner.tension import TensionEvent, apply_event

        event_map = {
            ArrestResult.SUCCESS: TensionEvent.CASE_SUCCESS,
            ArrestResult.PARTIAL: TensionEvent.CASE_PARTIAL,
            ArrestResult.FAILED: TensionEvent.CASE_FAILED,
        }
        event = event_map.get(arrest_result)
        if event is None:
            return []
        before = self.campaign.tension.value
        after = apply_event(self.campaign, event)
        if after != before:
            return [f"Campaign tension shifted from {before} to {after}."]
        return []

    def case_start_modifiers(
        self, district: str, location_name: str
    ) -> CaseStartModifiers:
        status = self.district_status_for(district)
        location_status = self.location_status_for(location_name)
        cooperation = clamp(0.4 + (self.trust / TRUST_LIMIT) * 0.6, 0.2, 1.0)
        lead_deadline_delta = 0
        if self.pressure >= 5:
            lead_deadline_delta = 2
        elif self.pressure >= 3:
            lead_deadline_delta = 1
        if location_status == DistrictStatus.VOLATILE:
            lead_deadline_delta = max(lead_deadline_delta, 2)
        elif location_status == DistrictStatus.TENSE:
            lead_deadline_delta = max(lead_deadline_delta, 1)
        briefing_lines: list[str] = []
        briefing_lines.extend(self.context_lines(district, location_name))
        recent_case = self.case_history[-1] if self.case_history else None
        if recent_case is not None:
            if recent_case.outcome == ArrestResult.FAILED.value:
                cooperation = clamp(cooperation - 0.15, 0.2, 1.0)
                lead_deadline_delta = max(lead_deadline_delta, 2)
                briefing_lines.append(
                    "Wrong-arrest fallout carries over: witnesses are tighter and command wants a faster correction."
                )
            elif recent_case.outcome == ArrestResult.SUCCESS.value:
                cooperation = clamp(cooperation + 0.05, 0.2, 1.0)
                briefing_lines.append(
                    "Last case bought you a little breathing room; people are more willing to talk."
                )
            else:
                briefing_lines.append(
                    "Last case held, but only barely; command wants cleaner proof this time."
                )
        closing = self.campaign.closing_in
        if closing.pattern or closing.narrowing or closing.proof:
            briefing_lines.append(
                "The pattern board is still live; this case starts under the weight of what you already know."
            )
        location_rep = self.location_reputation_for(location_name)
        if location_rep.friction >= 2:
            cooperation = clamp(cooperation - 0.1, 0.2, 1.0)
            lead_deadline_delta = max(lead_deadline_delta, 1)
            briefing_lines.append(
                f"{location_name} is still wary after earlier operations; access requests will take longer."
            )
        for thread in self.unresolved_threads.values():
            if thread.severity >= 2:
                lead_deadline_delta = max(lead_deadline_delta, 1)
                briefing_lines.append(
                    f"Unresolved thread '{thread.key}' has escalated ({thread.mutation}); fallout is bleeding into this case."
                )
        return CaseStartModifiers(
            cooperation=cooperation,
            lead_deadline_delta=lead_deadline_delta,
            briefing_lines=briefing_lines,
        )

    def advance_episode(self) -> list[str]:
        notes = self._tick_nemesis_clock()
        advance_campaign_episode(self.campaign)
        return notes

    def _tick_nemesis_clock(self) -> list[str]:
        from noir.showrunner.tension import TensionEvent, apply_event

        arc = self.campaign.nemesis_arc
        if self.campaign.endgame_state == EndgameState.RESOLVED:
            return []
        if arc.clock >= arc.clock_max:
            return []
        arc.clock = min(arc.clock_max, arc.clock + 1)
        apply_event(self.campaign, TensionEvent.NEMESIS_TICK)
        notes: list[str] = []
        if arc.clock >= arc.clock_max and not arc.coup_fired:
            arc.coup_fired = True
            notes.append(
                "Nemesis clock has run out; the antagonist's own plan has reached its move."
            )
        elif arc.clock == arc.clock_max - 2:
            notes.append("The nemesis's plan is closing on its own deadline.")
        return notes

    def raise_nemesis_awareness(self, delta: int = 1) -> list[str]:
        from noir.showrunner.tension import TensionEvent, apply_event

        arc = self.campaign.nemesis_arc
        before = arc.awareness
        arc.awareness = max(0, min(arc.awareness_max, arc.awareness + int(delta)))
        notes: list[str] = []
        if arc.awareness > before:
            apply_event(self.campaign, TensionEvent.PUBLIC_MOVE)
        if not arc.confronted and self._confrontation_ready():
            arc.confronted = True
            apply_event(self.campaign, TensionEvent.NEMESIS_CONFRONT)
            notes.append(
                "Nemesis is now aware enough to push back directly; expect retaliation."
            )
        return notes

    def _confrontation_ready(self) -> bool:
        arc = self.campaign.nemesis_arc
        closing = self.campaign.closing_in
        player_progress = closing.pattern + closing.narrowing + closing.proof
        return player_progress >= 3 and arc.awareness >= max(3, arc.awareness_max // 2)

    def ensure_case_queue(self, target_size: int = 1) -> None:
        ensure_scheduled_case_queue(
            self.campaign,
            self.pressure,
            self.case_history,
            target_size=target_size,
            endgame_ready=self.endgame_ready(),
        )

    def pop_next_case(self) -> dict[str, str] | None:
        return pop_scheduled_case(
            self.campaign,
            self.pressure,
            self.case_history,
            endgame_ready=self.endgame_ready(),
        )

    def update_closing_in(
        self,
        pattern_type: str | None,
        profile_used: bool,
        proof_met: bool,
    ) -> list[str]:
        progress = 0
        if pattern_type == "signature":
            self.campaign.closing_in.pattern += 1
            progress += 1
        if profile_used:
            self.campaign.closing_in.narrowing += 1
            progress += 1
        if proof_met:
            self.campaign.closing_in.proof += 1
            progress += 1
        self._check_endgame_trigger()
        notes: list[str] = []
        if progress > 0:
            notes.extend(self.raise_nemesis_awareness(progress))
        return notes

    def endgame_ready(self) -> bool:
        return self.campaign.endgame_state in {EndgameState.READY, EndgameState.ACTIVE}

    def activate_endgame(self) -> None:
        if self.campaign.endgame_state == EndgameState.READY:
            self.campaign.endgame_state = EndgameState.ACTIVE

    def resolve_endgame(self, result: str) -> None:
        self.campaign.endgame_state = EndgameState.RESOLVED
        self.campaign.endgame_result = result

    def _check_endgame_trigger(self) -> None:
        if self.campaign.endgame_state != EndgameState.INACTIVE:
            return
        closing = self.campaign.closing_in
        if (
            closing.pattern >= _ENDGAME_PATTERN_MIN
            and closing.narrowing >= _ENDGAME_NARROWING_MIN
            and closing.proof >= _ENDGAME_PROOF_MIN
        ):
            self.campaign.endgame_state = EndgameState.READY

    def update_identity(
        self,
        style_counts: dict[str, int],
        risky_flag: bool,
    ) -> list[str]:
        identity = self.campaign.identity
        identity.coercive += int(style_counts.get("coercive", 0))
        identity.analytical += int(style_counts.get("analytical", 0))
        identity.social += int(style_counts.get("social", 0))
        if risky_flag:
            identity.risky += 1

        case_counts = {
            "coercive": int(style_counts.get("coercive", 0)),
            "analytical": int(style_counts.get("analytical", 0)),
            "social": int(style_counts.get("social", 0)),
        }
        dominant = None
        if case_counts:
            max_value = max(case_counts.values())
            if max_value > 0:
                top = [key for key, value in case_counts.items() if value == max_value]
                if len(top) == 1:
                    dominant = top[0]
        if dominant:
            if identity.dominant == dominant:
                identity.dominant_streak += 1
            else:
                identity.dominant = dominant
                identity.dominant_streak = 1
        else:
            identity.dominant_streak = 0

        notes: list[str] = []
        if (
            self.nemesis_state
            and identity.dominant
            and identity.dominant_streak >= 2
        ):
            counterplay_map = {
                "coercive": "aggression_feeder",
                "analytical": "forensic_countermeasures",
                "social": "rapport_resistant",
            }
            note_map = {
                "coercive": "Pattern file suggests the offender adapts to pressure tactics.",
                "analytical": "Pattern file notes increased forensic countermeasures.",
                "social": "Pattern file notes growing resistance to rapport tactics.",
            }
            trait = counterplay_map.get(identity.dominant)
            if trait and trait not in self.nemesis_state.profile.counterplay_traits:
                self.nemesis_state.profile.counterplay_traits.append(trait)
                note = note_map.get(identity.dominant)
                if note:
                    notes.append(note)
        return notes

    def context_lines(self, district: str, location_name: str) -> list[str]:
        status = self.district_status_for(district)
        location_status = self.location_status_for(location_name)
        lines = [
            self._pressure_line(),
            self._trust_line(),
        ]
        if status != DistrictStatus.CALM:
            lines.append(self._district_line(status))
        if location_status != DistrictStatus.CALM:
            lines.append(self._location_line(location_status))
        return [line for line in lines if line]

    def location_status_for(self, location_name: str) -> DistrictStatus:
        if location_name in self.location_status:
            return self.location_status[location_name]
        status = self._baseline_status()
        self.location_status[location_name] = status
        return status

    def pick_returning_person(
        self,
        rng: Rng,
        role_tag: str,
        chance: float = 0.25,
    ) -> PersonRecord | None:
        if not self.people_index or rng.random() > chance:
            return None
        candidates = [
            record
            for record in self.people_index.values()
            if record.role_tag == role_tag
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda record: record.person_id)
        return rng.choice(candidates)

    def upsert_person(self, record: PersonRecord) -> None:
        self.people_index[record.person_id] = record

    def has_returning_person(self, people, case_id: str) -> bool:
        for person in people.values():
            record = self.people_index.get(str(person.id))
            if record and record.last_seen_case_id != case_id:
                return True
        return False

    def _baseline_status(self) -> DistrictStatus:
        if self.pressure >= 4:
            return DistrictStatus.VOLATILE
        if self.pressure >= 2:
            return DistrictStatus.TENSE
        return DistrictStatus.CALM

    def _shift_status(
        self, current: DistrictStatus, outcome: ArrestResult
    ) -> DistrictStatus:
        order = [DistrictStatus.CALM, DistrictStatus.TENSE, DistrictStatus.VOLATILE]
        index = order.index(current)
        if outcome == ArrestResult.SUCCESS:
            index -= 1
        elif outcome == ArrestResult.FAILED:
            index += 1
        index = max(0, min(index, len(order) - 1))
        return order[index]

    def _pressure_line(self) -> str:
        if self.pressure >= 4:
            return "Pressure is high; the department expects quick movement."
        if self.pressure <= 1:
            return "Pressure is low; you have a little room."
        return "Pressure is steady; expect scrutiny to build."

    def _trust_line(self) -> str:
        if self.trust <= 2:
            return "Trust is thin; witnesses are guarded."
        if self.trust >= 5:
            return "Trust holds; cooperation is steady."
        return "Trust is mixed; cooperation may vary."

    def _district_line(self, status: DistrictStatus) -> str:
        if status == DistrictStatus.VOLATILE:
            return "District status: volatile. Leads may collapse quickly."
        if status == DistrictStatus.TENSE:
            return "District status: tense. Expect slower cooperation."
        return "District status: calm."

    def _location_line(self, status: DistrictStatus) -> str:
        if status == DistrictStatus.VOLATILE:
            return "Location status: volatile. The scene feels unstable."
        if status == DistrictStatus.TENSE:
            return "Location status: tense. Expect tightened access."
        return "Location status: calm."

    def location_reputation_for(self, location_name: str) -> LocationReputationRecord:
        record = self.location_reputation.get(location_name)
        if record is None:
            record = LocationReputationRecord(location_name=location_name)
            self.location_reputation[location_name] = record
        return record

    def remember_npc_interaction(
        self,
        person_id: str,
        case_id: str,
        tone: str,
        impact: str = "neutral",
        promise_integrity: str = "unknown",
        exposure_event: str | None = None,
    ) -> None:
        record = self.npc_memory.get(person_id)
        if record is None:
            record = NPCMemoryRecord(person_id=person_id)
            self.npc_memory[person_id] = record
        record.last_tone = tone
        record.impact = impact
        record.promise_integrity = promise_integrity
        if exposure_event:
            record.exposure_events.append(exposure_event)
        record.last_case_id = case_id

    def register_unresolved_thread(self, key: str, timer: int = 1) -> None:
        self.unresolved_threads[key] = EscalationThread(key=key, timer=max(timer, 0))

    def resolve_thread(self, key: str) -> None:
        self.unresolved_threads.pop(key, None)

    def _apply_consequence_memory(
        self,
        outcome: CaseOutcome,
        case_id: str,
        location_name: str,
    ) -> None:
        rep = self.location_reputation_for(location_name)
        if outcome.arrest_result == ArrestResult.SUCCESS:
            rep.trust_trend = max(-3, min(3, rep.trust_trend + 1))
            rep.friction = max(0, rep.friction - 1)
            rep.safety_noise = max(0, rep.safety_noise - 1)
            return
        if outcome.arrest_result == ArrestResult.FAILED:
            rep.trust_trend = max(-3, min(3, rep.trust_trend - 1))
            rep.friction = min(3, rep.friction + 1)
            rep.safety_noise = min(3, rep.safety_noise + 1)
            rep.heat = min(3, rep.heat + 1)
            mistake = self.mistake_history.get("wrong_arrest")
            if mistake is None:
                mistake = MistakeRecord(key="wrong_arrest")
                self.mistake_history[mistake.key] = mistake
            mistake.count += 1
            mistake.last_case_id = case_id

    def _advance_unresolved_threads(self, case_id: str) -> None:
        for thread in self.unresolved_threads.values():
            if thread.timer > 0:
                thread.timer -= 1
                continue
            thread.severity = min(3, thread.severity + 1)
            thread.timer = 1
            if thread.severity == 2:
                thread.mutation = "new victims and wider rumor spread"
            elif thread.severity >= 3:
                thread.mutation = "copycat noise and tighter political scrutiny"
            mistake = self.mistake_history.get(f"ignored:{thread.key}")
            if mistake is None:
                mistake = MistakeRecord(key=f"ignored:{thread.key}")
                self.mistake_history[mistake.key] = mistake
            mistake.count += 1
            mistake.last_case_id = case_id
