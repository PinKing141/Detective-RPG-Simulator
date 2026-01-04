"""SQLite persistence for Phase 3 world memory."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from noir.world.state import (
    CaseRecord,
    DistrictStatus,
    EpisodeTitleState,
    PersonRecord,
    WorldState,
)


class WorldStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self.conn.close()

    def reset_world_state(self) -> None:
        cur = self.conn.cursor()
        for table in (
            "world_state",
            "episode_title_state",
            "case_history",
            "district_status",
            "location_status",
            "people_index",
        ):
            cur.execute(f"DELETE FROM {table}")
        self.conn.commit()

    def load_world_state(self) -> WorldState:
        cur = self.conn.cursor()
        cur.execute("SELECT trust_level, pressure_level, tick, nemesis_activity FROM world_state WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            state = WorldState()
            self.save_world_state(state)
            return state
        state = WorldState(
            trust=int(row["trust_level"]),
            pressure=int(row["pressure_level"]),
            tick=int(row["tick"]),
            nemesis_activity=int(row["nemesis_activity"]),
        )
        cur.execute("SELECT used_ids, recent_registers, recent_tags FROM episode_title_state WHERE id = 1")
        row = cur.fetchone()
        if row is not None:
            state.episode_titles = EpisodeTitleState(
                used_ids=json.loads(row["used_ids"] or "[]"),
                recent_registers=json.loads(row["recent_registers"] or "[]"),
                recent_tags=json.loads(row["recent_tags"] or "[]"),
            )
        cur.execute("SELECT district, status FROM district_status")
        for entry in cur.fetchall():
            status = DistrictStatus(entry["status"])
            state.district_status[entry["district"]] = status
        cur.execute("SELECT location, status FROM location_status")
        for entry in cur.fetchall():
            status = DistrictStatus(entry["status"])
            state.location_status[entry["location"]] = status
        cur.execute(
            "SELECT person_id, name, role_tag, country_of_origin, religion_affiliation, "
            "religion_observance, community_connectedness, created_in_case_id, "
            "last_seen_case_id, last_seen_tick FROM people_index"
        )
        for entry in cur.fetchall():
            record = PersonRecord(
                person_id=entry["person_id"],
                name=entry["name"],
                role_tag=entry["role_tag"],
                country_of_origin=entry["country_of_origin"],
                religion_affiliation=entry["religion_affiliation"],
                religion_observance=entry["religion_observance"],
                community_connectedness=entry["community_connectedness"],
                created_in_case_id=entry["created_in_case_id"],
                last_seen_case_id=entry["last_seen_case_id"],
                last_seen_tick=int(entry["last_seen_tick"]),
            )
            state.people_index[record.person_id] = record
        cur.execute(
            "SELECT case_id, seed, district, started_tick, ended_tick, outcome, trust_delta, pressure_delta, notes "
            "FROM case_history ORDER BY ended_tick DESC"
        )
        for entry in cur.fetchall():
            notes = [note for note in (entry["notes"] or "").split(" | ") if note]
            state.case_history.append(
                CaseRecord(
                    case_id=entry["case_id"],
                    seed=int(entry["seed"]),
                    district=entry["district"],
                    started_tick=int(entry["started_tick"]),
                    ended_tick=int(entry["ended_tick"]),
                    outcome=entry["outcome"],
                    trust_delta=int(entry["trust_delta"]),
                    pressure_delta=int(entry["pressure_delta"]),
                    notes=notes,
                )
            )
        return state

    def save_world_state(self, state: WorldState) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO world_state (id, trust_level, pressure_level, tick, nemesis_activity)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                trust_level = excluded.trust_level,
                pressure_level = excluded.pressure_level,
                tick = excluded.tick,
                nemesis_activity = excluded.nemesis_activity
            """,
            (state.trust, state.pressure, state.tick, state.nemesis_activity),
        )
        cur.execute(
            """
            INSERT INTO episode_title_state (id, used_ids, recent_registers, recent_tags)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                used_ids = excluded.used_ids,
                recent_registers = excluded.recent_registers,
                recent_tags = excluded.recent_tags
            """,
            (
                json.dumps(state.episode_titles.used_ids),
                json.dumps(state.episode_titles.recent_registers),
                json.dumps(state.episode_titles.recent_tags),
            ),
        )
        cur.execute("DELETE FROM district_status")
        for district, status in state.district_status.items():
            cur.execute(
                "INSERT INTO district_status (district, status) VALUES (?, ?)",
                (district, status.value),
            )
        cur.execute("DELETE FROM location_status")
        for location, status in state.location_status.items():
            cur.execute(
                "INSERT INTO location_status (location, status) VALUES (?, ?)",
                (location, status.value),
            )
        cur.execute("DELETE FROM people_index")
        for record in state.people_index.values():
            cur.execute(
                """
                INSERT INTO people_index (
                    person_id,
                    name,
                    role_tag,
                    country_of_origin,
                    religion_affiliation,
                    religion_observance,
                    community_connectedness,
                    created_in_case_id,
                    last_seen_case_id,
                    last_seen_tick
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.person_id,
                    record.name,
                    record.role_tag,
                    record.country_of_origin,
                    record.religion_affiliation,
                    record.religion_observance,
                    record.community_connectedness,
                    record.created_in_case_id,
                    record.last_seen_case_id,
                    record.last_seen_tick,
                ),
            )
        self.conn.commit()

    def record_case(self, record: CaseRecord) -> None:
        notes = " | ".join(record.notes)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO case_history (
                case_id,
                seed,
                district,
                started_tick,
                ended_tick,
                outcome,
                trust_delta,
                pressure_delta,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.case_id,
                record.seed,
                record.district,
                record.started_tick,
                record.ended_tick,
                record.outcome,
                record.trust_delta,
                record.pressure_delta,
                notes,
            ),
        )
        self.conn.commit()

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                trust_level INTEGER NOT NULL,
                pressure_level INTEGER NOT NULL,
                tick INTEGER NOT NULL,
                nemesis_activity INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS episode_title_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                used_ids TEXT,
                recent_registers TEXT,
                recent_tags TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS case_history (
                case_id TEXT PRIMARY KEY,
                seed INTEGER NOT NULL,
                district TEXT NOT NULL,
                started_tick INTEGER NOT NULL,
                ended_tick INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                trust_delta INTEGER NOT NULL,
                pressure_delta INTEGER NOT NULL,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS district_status (
                district TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS location_status (
                location TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS people_index (
                person_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role_tag TEXT NOT NULL,
                country_of_origin TEXT,
                religion_affiliation TEXT,
                religion_observance TEXT,
                community_connectedness TEXT,
                created_in_case_id TEXT NOT NULL,
                last_seen_case_id TEXT NOT NULL,
                last_seen_tick INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()
