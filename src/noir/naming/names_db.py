"""Name generation with case constraints and DB-backed sampling."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import re
import sqlite3

from noir.util.rng import Rng

DEFAULT_FIRST_NAMES = ["Alex", "Blake", "Casey", "Drew", "Morgan", "Riley"]
DEFAULT_LAST_NAMES = ["Hale", "Iverson", "Kerr", "Lane", "Maddox", "Sloane"]

RECENT_FIRST_WINDOW = 40
RECENT_LAST_WINDOW = 80
MAX_ATTEMPTS = 12
PRIMARY_COUNTRY_WEIGHT = 0.7


def _name_key(name: str) -> str:
    cleaned = re.sub(r"[^a-z]", "", name.lower())
    return re.sub(r"(.)\1+", r"\1", cleaned)


def _is_readable(name: str) -> bool:
    if len(name) > 20:
        return False
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z' -]*$", name))


class NameDatabase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._forename_max = self._max_rowid("forenames")
        self._surname_max = self._max_rowid("surnames")

    def close(self) -> None:
        self.conn.close()

    def random_country(self, rng: Rng) -> str | None:
        return self._random_value(
            table="forenames",
            max_rowid=self._forename_max,
            column="country",
            rng=rng,
            filters=["country IS NOT NULL", "country != ''"],
        )

    def random_forename(
        self, rng: Rng, country: str | None, gender: str | None
    ) -> str | None:
        return self._random_name(
            table="forenames",
            max_rowid=self._forename_max,
            rng=rng,
            country=country,
            gender=gender,
        )

    def random_surname(self, rng: Rng, country: str | None) -> str | None:
        return self._random_name(
            table="surnames",
            max_rowid=self._surname_max,
            rng=rng,
            country=country,
            gender=None,
            prefer_neutral=True,
        )

    def _max_rowid(self, table: str) -> int:
        cur = self.conn.cursor()
        cur.execute(f"SELECT MAX(rowid) AS max_id FROM {table}")
        row = cur.fetchone()
        return int(row["max_id"] or 0)

    def _random_value(
        self,
        table: str,
        max_rowid: int,
        column: str,
        rng: Rng,
        filters: list[str],
    ) -> str | None:
        if max_rowid <= 0:
            return None
        clause = " AND ".join(filters) if filters else "1=1"
        rowid = rng.randint(1, max_rowid)
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT {column} FROM {table} WHERE rowid >= ? AND {clause} LIMIT 1",
            (rowid,),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(f"SELECT {column} FROM {table} WHERE {clause} LIMIT 1")
            row = cur.fetchone()
        value = row[column] if row else None
        if value is None or str(value).strip() == "":
            return None
        return str(value)

    def _random_name(
        self,
        table: str,
        max_rowid: int,
        rng: Rng,
        country: str | None,
        gender: str | None,
        prefer_neutral: bool = False,
    ) -> str | None:
        if max_rowid <= 0:
            return None
        filters: list[tuple[list[str], list[object]]] = []
        if country and gender:
            filters.append((["country = ?", "gender = ?"], [country, gender]))
        if country and gender is None and prefer_neutral:
            filters.append((["country = ?", "(gender IS NULL OR gender = '')"], [country]))
        if country:
            filters.append((["country = ?"], [country]))
        if gender:
            filters.append((["gender = ?"], [gender]))
        if prefer_neutral:
            filters.append((["(gender IS NULL OR gender = '')"], []))
        filters.append(([], []))

        for clauses, params in filters:
            clause = " AND ".join(clauses) if clauses else "1=1"
            rowid = rng.randint(1, max_rowid)
            cur = self.conn.cursor()
            cur.execute(
                f"SELECT name FROM {table} WHERE rowid >= ? AND {clause} LIMIT 1",
                [rowid] + params,
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    f"SELECT name FROM {table} WHERE {clause} LIMIT 1",
                    params,
                )
                row = cur.fetchone()
            if row is None:
                continue
            return row["name"]
        return None


@dataclass(frozen=True)
class NamePick:
    first: str
    last: str
    country: str | None

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"


@dataclass
class NameUsage:
    recent_first: deque[str] = field(default_factory=lambda: deque(maxlen=RECENT_FIRST_WINDOW))
    recent_last: deque[str] = field(default_factory=lambda: deque(maxlen=RECENT_LAST_WINDOW))

    def record(self, first: str, last: str) -> None:
        self.recent_first.append(first)
        self.recent_last.append(last)

    def recently_used_first(self, first: str) -> bool:
        return first in self.recent_first

    def recently_used_last(self, last: str) -> bool:
        return last in self.recent_last


@dataclass
class CaseNameContext:
    generator: "NameGenerator"
    country_weights: list[tuple[str | None, float]]
    used_full: set[str] = field(default_factory=set)
    used_first: set[str] = field(default_factory=set)
    used_first_keys: set[str] = field(default_factory=set)

    def next_name_pick(self, rng: Rng, gender: str | None = None) -> NamePick:
        return self.generator._generate_name_pick(rng, self, gender)

    def next_full_name(self, rng: Rng, gender: str | None = None) -> str:
        return self.next_name_pick(rng, gender).full


@dataclass
class NameGenerator:
    db: NameDatabase | None
    fallback_first: list[str]
    fallback_last: list[str]
    usage: NameUsage = field(default_factory=NameUsage)

    def start_case(self, rng: Rng) -> CaseNameContext:
        country_weights = self._pick_case_countries(rng)
        return CaseNameContext(generator=self, country_weights=country_weights)

    def full_name(self, rng: Rng) -> str:
        context = self.start_case(rng)
        return context.next_full_name(rng)

    def _pick_case_countries(self, rng: Rng) -> list[tuple[str | None, float]]:
        if not self.db:
            return [(None, 1.0)]
        primary = self.db.random_country(rng)
        secondary: list[str] = []
        for _ in range(2):
            candidate = self.db.random_country(rng)
            if candidate and candidate != primary and candidate not in secondary:
                secondary.append(candidate)
        if primary is None:
            return [(None, 1.0)]
        if not secondary:
            return [(primary, 1.0)]
        secondary_weight = (1.0 - PRIMARY_COUNTRY_WEIGHT) / len(secondary)
        weights = [(primary, PRIMARY_COUNTRY_WEIGHT)]
        weights.extend((country, secondary_weight) for country in secondary)
        return weights

    def _pick_country(self, rng: Rng, context: CaseNameContext) -> str | None:
        if not context.country_weights:
            return None
        pick = rng.random()
        cumulative = 0.0
        for country, weight in context.country_weights:
            cumulative += weight
            if pick <= cumulative:
                return country
        return context.country_weights[-1][0]

    def _generate_name_pick(
        self,
        rng: Rng,
        context: CaseNameContext,
        gender: str | None,
    ) -> NamePick:
        for _ in range(MAX_ATTEMPTS):
            country = self._pick_country(rng, context)
            first = self._pick_first(rng, country, gender)
            last = self._pick_last(rng, country)
            if not first or not last:
                continue
            full = f"{first} {last}"
            if not self._is_allowed_name(first, last, full, context):
                continue
            self._record_name(first, last, full, context)
            return NamePick(first=first, last=last, country=country)
        fallback = self._fallback_name(rng, context)
        parts = fallback.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else rng.choice(self.fallback_last)
        return NamePick(first=first, last=last, country=None)

    def _pick_first(self, rng: Rng, country: str | None, gender: str | None) -> str | None:
        if self.db:
            return self.db.random_forename(rng, country=country, gender=gender)
        return rng.choice(self.fallback_first)

    def _pick_last(self, rng: Rng, country: str | None) -> str | None:
        if self.db:
            return self.db.random_surname(rng, country=country)
        return rng.choice(self.fallback_last)

    def _is_allowed_name(
        self,
        first: str,
        last: str,
        full: str,
        context: CaseNameContext,
    ) -> bool:
        if not _is_readable(first) or not _is_readable(last):
            return False
        full_key = full.lower()
        first_key = _name_key(first)
        if full_key in context.used_full:
            return False
        if first.lower() in context.used_first:
            return False
        if first_key in context.used_first_keys:
            return False
        if self.usage.recently_used_first(first):
            return False
        if self.usage.recently_used_last(last):
            return False
        return True

    def _record_name(
        self,
        first: str,
        last: str,
        full: str,
        context: CaseNameContext,
    ) -> None:
        context.used_full.add(full.lower())
        context.used_first.add(first.lower())
        context.used_first_keys.add(_name_key(first))
        self.usage.record(first, last)

    def _fallback_name(self, rng: Rng, context: CaseNameContext) -> str:
        for _ in range(MAX_ATTEMPTS):
            first = rng.choice(self.fallback_first)
            last = rng.choice(self.fallback_last)
            full = f"{first} {last}"
            if self._is_allowed_name(first, last, full, context):
                self._record_name(first, last, full, context)
                return full
        return f"{rng.choice(self.fallback_first)} {rng.choice(self.fallback_last)}"

    @staticmethod
    def format_official(full_name: str) -> str:
        parts = full_name.split(" ", 1)
        if len(parts) < 2:
            return full_name.upper()
        return f"{parts[1].upper()}, {parts[0]}"

    @staticmethod
    def format_short(full_name: str, style: str = "first") -> str:
        parts = full_name.split(" ", 1)
        if style == "detective_last" and len(parts) > 1:
            return f"Detective {parts[1]}"
        return parts[0]


def default_db_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "names" / "names.db"


def load_name_generator(path: Path | None = None) -> NameGenerator:
    db_path = path or default_db_path()
    db = NameDatabase(db_path) if db_path.exists() else None
    return NameGenerator(
        db=db,
        fallback_first=list(DEFAULT_FIRST_NAMES),
        fallback_last=list(DEFAULT_LAST_NAMES),
    )
