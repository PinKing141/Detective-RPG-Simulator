"""World state and continuity helpers for Phase 3+."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.cases.archetypes import CaseArchetype
from noir.investigation.costs import PRESSURE_LIMIT, clamp
from noir.nemesis.state import NemesisState
from noir.investigation.outcomes import ArrestResult, CaseOutcome, TRUST_LIMIT
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
class DetectiveIdentityState:
    coercive: int = 0
    analytical: int = 0
    social: int = 0
    risky: int = 0
    dominant: str | None = None
    dominant_streak: int = 0


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
        return cls(
            season_index=int(payload.get("season_index", 1)),
            episode_index=int(payload.get("episode_index", 1)),
            case_queue=list(payload.get("case_queue", []) or []),
            closing_in=closing_in,
            identity=identity,
            ending_flags=list(payload.get("ending_flags", []) or []),
            endgame_state=EndgameState(payload.get("endgame_state", EndgameState.INACTIVE.value)),
            endgame_result=payload.get("endgame_result"),
        )


_TENSION_WAVE = [
    CaseArchetype.CHARACTER,
    CaseArchetype.BASELINE,
    CaseArchetype.PRESSURE,
    CaseArchetype.FORESHADOWING,
    CaseArchetype.PATTERN,
]

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
        return notes

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
        return CaseStartModifiers(
            cooperation=cooperation,
            lead_deadline_delta=lead_deadline_delta,
            briefing_lines=briefing_lines,
        )

    def advance_episode(self) -> None:
        self.campaign.episode_index = max(1, self.campaign.episode_index + 1)

    def ensure_case_queue(self, target_size: int = 1) -> None:
        while len(self.campaign.case_queue) < target_size:
            self.campaign.case_queue.append(self._schedule_case_payload())

    def pop_next_case(self) -> dict[str, str] | None:
        if not self.campaign.case_queue:
            self.ensure_case_queue()
        if not self.campaign.case_queue:
            return None
        return self.campaign.case_queue.pop(0)

    def update_closing_in(
        self,
        pattern_type: str | None,
        profile_used: bool,
        proof_met: bool,
    ) -> None:
        if pattern_type == "signature":
            self.campaign.closing_in.pattern += 1
        if profile_used:
            self.campaign.closing_in.narrowing += 1
        if proof_met:
            self.campaign.closing_in.proof += 1
        self._check_endgame_trigger()

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

    def _schedule_case_payload(self) -> dict[str, str]:
        archetype = self._tension_wave_archetype()
        reason = "tension_wave"
        last_record = self.case_history[-1] if self.case_history else None
        if last_record and last_record.outcome == ArrestResult.FAILED.value:
            archetype = CaseArchetype.CHARACTER
            reason = "cooldown_after_failure"
        elif self.pressure >= 4:
            archetype = CaseArchetype.CHARACTER
            reason = "cooldown_pressure"
        elif self.pressure <= 1 and archetype == CaseArchetype.CHARACTER:
            archetype = CaseArchetype.PRESSURE
            reason = "pressure_spike"
        return {"archetype": archetype.value, "reason": reason}

    def _tension_wave_archetype(self) -> CaseArchetype:
        index = (self.campaign.episode_index - 1) % len(_TENSION_WAVE)
        return _TENSION_WAVE[index]

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
