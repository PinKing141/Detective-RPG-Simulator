"""World state and continuity helpers for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.investigation.costs import PRESSURE_LIMIT, clamp
from noir.investigation.outcomes import ArrestResult, CaseOutcome, TRUST_LIMIT
from noir.util.rng import Rng


class DistrictStatus(StrEnum):
    CALM = "calm"
    TENSE = "tense"
    VOLATILE = "volatile"


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
    nemesis_activity: int = 0
    tick: int = 0
    district_status: dict[str, DistrictStatus] = field(default_factory=dict)
    location_status: dict[str, DistrictStatus] = field(default_factory=dict)
    case_history: list[CaseRecord] = field(default_factory=list)
    people_index: dict[str, PersonRecord] = field(default_factory=dict)

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
                notes=list(outcome.notes),
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

    def context_lines(self, district: str, location_name: str) -> list[str]:
        status = self.district_status_for(district)
        location_status = self.location_status_for(location_name)
        lines = [
            self._pressure_line(),
            self._trust_line(),
            self._district_line(status),
            self._location_line(location_status),
        ]
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
