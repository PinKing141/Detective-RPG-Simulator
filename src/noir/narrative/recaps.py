"""Episode framing helpers for Phase 3C."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from noir.util.rng import Rng
from noir.world.state import CaseRecord, EpisodeTitleState, WorldState
from noir.narrative.grammar import normalize_line, normalize_lines, place_with_article


@dataclass(frozen=True)
class EpisodeTitle:
    text: str
    register: str
    tags: tuple[str, ...] = ()
    nemesis_only: bool = False
    weight: float = 1.0


_TITLE_LIBRARY = [
    EpisodeTitle("Plain Sight", "A", ("surveillance", "misdirection")),
    EpisodeTitle("Somebody's Watching", "A", ("surveillance", "paranoia")),
    EpisodeTitle("Unfinished Business", "A", ("recurrence", "escalation")),
    EpisodeTitle("No Good Deed", "A", ("motive", "moral")),
    EpisodeTitle("Dead of Night", "A", ("night", "concealment")),
    EpisodeTitle("Out of Time", "A", ("time_pressure", "escalation")),
    EpisodeTitle("Hard to Swallow", "A", ("poison", "denial")),
    EpisodeTitle("A Thin Line", "A", ("ethics", "pressure")),
    EpisodeTitle("The Last Straw", "A", ("trigger", "breakdown")),
    EpisodeTitle("Past Due", "A", ("debt", "recurrence")),
    EpisodeTitle("Open and Shut", "A", ("certainty", "twist")),
    EpisodeTitle("Bad Blood", "A", ("family", "legacy")),
    EpisodeTitle("By the Book", "A", ("procedure", "conflict")),
    EpisodeTitle("On the Record", "A", ("media", "exposure")),
    EpisodeTitle("Under the Surface", "A", ("hidden_cause", "misdirection")),
    EpisodeTitle("In Cold Print", "A", ("case_file", "paper_trail")),
    EpisodeTitle("Nothing Personal", "A", ("targeting", "deflection")),
    EpisodeTitle("Close to Home", "A", ("personal", "proximity")),
    EpisodeTitle("All Quiet", "A", ("dread", "calm")),
    EpisodeTitle("The Long Way Round", "A", ("misdirection", "alibi")),
    EpisodeTitle("Broken Mirror", "B", ("identity", "distortion")),
    EpisodeTitle("Cold Ashes", "B", ("arson", "aftermath")),
    EpisodeTitle("Black Water", "B", ("disposal", "concealment")),
    EpisodeTitle("Silent Door", "B", ("entry", "intrusion")),
    EpisodeTitle("Glass House", "B", ("secrets", "exposure")),
    EpisodeTitle("Rust Belt", "B", ("pressure", "decay")),
    EpisodeTitle("Paper Trail", "B", ("documents", "corruption")),
    EpisodeTitle("Hollow Witness", "B", ("testimony", "manipulation")),
    EpisodeTitle("Open Wound", "B", ("trauma", "escalation")),
    EpisodeTitle("Loose Thread", "B", ("lead", "unraveling")),
    EpisodeTitle("Iron Promise", "B", ("oath", "motive")),
    EpisodeTitle("Dead Letter", "B", ("missing_comms", "misdirection")),
    EpisodeTitle("Burned Bridge", "B", ("relationships", "retaliation")),
    EpisodeTitle("Red Line", "B", ("boundary", "escalation")),
    EpisodeTitle("Empty Chair", "B", ("absence", "interrogation")),
    EpisodeTitle("Stolen Breath", "B", ("strangulation", "control")),
    EpisodeTitle("Second Skin", "B", ("disguise", "identity")),
    EpisodeTitle("Blind Corner", "B", ("ambush", "error")),
    EpisodeTitle("Faded Ink", "B", ("old_cases", "recurrence")),
    EpisodeTitle("Sealed Room", "B", ("locked_room", "contradiction")),
    EpisodeTitle("Compulsion", "C", ("ritual", "recurrence")),
    EpisodeTitle("Machismo", "C", ("ego", "violence")),
    EpisodeTitle("Silence", "C", ("non_cooperation", "intimidation")),
    EpisodeTitle("Exposure", "C", ("media", "risk")),
    EpisodeTitle("Vanity", "C", ("image", "attention")),
    EpisodeTitle("Hunger", "C", ("need", "obsession")),
    EpisodeTitle("Contagion", "C", ("copycat", "spread")),
    EpisodeTitle("Inheritance", "C", ("legacy", "family")),
    EpisodeTitle("Confession", "C", ("pressure", "interrogation")),
    EpisodeTitle("Alibi", "C", ("timeline", "contradiction")),
    EpisodeTitle("Immunity", "C", ("protected", "politics")),
    EpisodeTitle("Redemption", "C", ("moral", "twist")),
    EpisodeTitle("Obsession", "C", ("stalking", "fixation")),
    EpisodeTitle("Ransom", "C", ("abduction", "leverage")),
    EpisodeTitle("Collateral", "C", ("stakes", "spillover")),
    EpisodeTitle("Restraint", "C", ("control", "captivity")),
    EpisodeTitle("Threshold", "C", ("probable_cause", "decision")),
    EpisodeTitle("Deception", "C", ("lying", "misdirection")),
    EpisodeTitle("Compliance", "C", ("coercion", "interrogation")),
    EpisodeTitle("Recurrence", "C", ("pattern", "nemesis_hint")),
    EpisodeTitle("All the Devils Are Here", "D", ("nemesis", "convergence"), True),
    EpisodeTitle("The Past Doesn't Stay Buried", "D", ("recurrence", "dread")),
    EpisodeTitle("Nothing Ends Clean", "D", ("consequence", "realism")),
    EpisodeTitle("You Don't Get to Leave", "D", ("captivity", "control")),
    EpisodeTitle("Everyone Has a Price", "D", ("corruption", "leverage")),
    EpisodeTitle("This Was Never Random", "D", ("pattern", "nemesis_hint")),
    EpisodeTitle("They Knew You'd Come", "D", ("trap", "nemesis")),
    EpisodeTitle("We've Seen This Before", "D", ("copycat", "recurrence")),
    EpisodeTitle("It Was Always Personal", "D", ("motive", "identity")),
    EpisodeTitle("The City Keeps Score", "D", ("living_world", "consequence")),
    EpisodeTitle("Someone Is Writing the Rules", "D", ("nemesis", "escalation")),
    EpisodeTitle("You Missed the Moment", "D", ("lead_decay", "consequence")),
    EpisodeTitle("It Doesn't Add Up", "D", ("timeline", "contradiction")),
    EpisodeTitle("No One Tells the Whole Truth", "D", ("testimony", "doubt")),
    EpisodeTitle("You Can't Save Everyone", "D", ("pressure", "failure")),
    EpisodeTitle("He Wanted to Be Caught", "D", ("provocation", "nemesis")),
    EpisodeTitle("You're Not the Only Hunter", "D", ("nemesis", "parity")),
    EpisodeTitle("This Is What You Chose", "D", ("responsibility", "consequence")),
    EpisodeTitle("It's Not Over", "D", ("recurrence", "return")),
    EpisodeTitle("The Pattern Has a Name", "D", ("nemesis", "reveal"), True),
]

_USED_TITLE_IDS: set[int] = set()
_RECENT_REGISTERS: list[str] = []
_RECENT_TAGS: list[str] = []


def _allowed_registers(kind: str, rng: Rng) -> list[str]:
    if kind == "nemesis":
        registers = ["B", "D"]
        if rng.random() < 0.1:
            registers.append("C")
        return registers
    if kind == "copycat":
        return ["A", "B", "D"]
    if kind in {"opener", "finale"}:
        return ["D", "B"]
    registers = ["A", "B"]
    if rng.random() < 0.1:
        registers.append("C")
    return registers


def _weighted_choice(
    rng: Rng, items: list[tuple[int, EpisodeTitle]], weights: list[float]
) -> tuple[int, EpisodeTitle]:
    total = sum(weights)
    if total <= 0:
        return items[0]
    pick = rng.random() * total
    upto = 0.0
    for (idx, entry), weight in zip(items, weights):
        upto += weight
        if pick <= upto:
            return idx, entry
    return items[-1]

_COLD_OPEN_TEMPLATES = [
    "A call comes in from {place}.",
    "The scene is quiet when you arrive at {place}.",
    "The first report points to {place}.",
    "The case begins in {place}.",
    "Tonight starts at {place}.",
]

_END_TAGS_SUCCESS = [
    "The report holds, for now.",
    "The file closes clean.",
    "The city exhales for a night.",
]

_END_TAGS_PARTIAL = [
    "The charge stands, but it is thin.",
    "You have a name, not a lock.",
    "The file stays open in spirit.",
]

_END_TAGS_FAILED = [
    "The file stays open.",
    "The city remembers the gap.",
    "The night moves on without closure.",
]

_PARTNER_LINES = [
    "Your partner keeps the room moving.",
    "The team runs the file while you head out.",
    "A colleague flags a thread worth pulling.",
    "The squad room is quiet, but the phones are not.",
    "The case file feels heavier than it looks.",
    "Someone on the team already pulled the last report.",
    "A partner asks for the short version, then the long one.",
    "The unit watches the clock as the city wakes.",
]


def build_episode_title(
    rng: Rng,
    location_name: str,
    district: str,
    episode_kind: str = "normal",
    case_tags: Iterable[str] | None = None,
    title_state: EpisodeTitleState | None = None,
) -> str:
    allowed = _allowed_registers(episode_kind, rng)
    tags = tuple(dict.fromkeys(case_tags or []))
    used_ids = _USED_TITLE_IDS
    recent_registers = _RECENT_REGISTERS
    recent_tags = _RECENT_TAGS
    if title_state is not None:
        used_ids = set(title_state.used_ids)
        recent_registers = title_state.recent_registers
        recent_tags = title_state.recent_tags
    candidates = []
    for idx, entry in enumerate(_TITLE_LIBRARY):
        if entry.register not in allowed:
            continue
        if entry.nemesis_only and episode_kind != "nemesis":
            continue
        if idx in _USED_TITLE_IDS:
            continue
        candidates.append((idx, entry))
    if not candidates:
        candidates = [(idx, entry) for idx, entry in enumerate(_TITLE_LIBRARY) if entry.register in allowed]
    weights: list[float] = []
    recent_registers = _RECENT_REGISTERS[-3:]
    recent_tags = set(_RECENT_TAGS[-8:])
    for _, entry in candidates:
        score = entry.weight
        if tags and set(entry.tags) & set(tags):
            overlap = set(entry.tags) & set(tags)
            score += 2.0 + min(2.5, 0.5 * len(overlap))
        if recent_registers:
            if entry.register == recent_registers[-1]:
                score *= 0.55
            if entry.register in recent_registers:
                score *= 0.75
        if recent_tags and entry.tags:
            overlap = set(entry.tags) & recent_tags
            if overlap:
                score *= max(0.45, 0.85 ** len(overlap))
        if episode_kind == "nemesis" and entry.register == "D":
            score *= 1.25
        if episode_kind == "nemesis" and "recurrence" in entry.tags:
            score *= 1.2
        weights.append(score)
    chosen_index, entry = _weighted_choice(rng, candidates, weights)
    if title_state is not None:
        if chosen_index not in title_state.used_ids:
            title_state.used_ids.append(chosen_index)
        title_state.recent_registers.append(entry.register)
        title_state.recent_registers[:] = title_state.recent_registers[-3:]
        title_state.recent_tags.extend(entry.tags)
        title_state.recent_tags[:] = title_state.recent_tags[-8:]
    else:
        _USED_TITLE_IDS.add(chosen_index)
        _RECENT_REGISTERS.append(entry.register)
        _RECENT_REGISTERS[:] = _RECENT_REGISTERS[-3:]
        _RECENT_TAGS.extend(entry.tags)
        _RECENT_TAGS[:] = _RECENT_TAGS[-8:]
    return entry.text


def build_cold_open(rng: Rng, location_name: str) -> list[str]:
    templates = list(_COLD_OPEN_TEMPLATES)
    rng.shuffle(templates)
    place = place_with_article(location_name)
    return normalize_lines([templates[0].format(place=place)])


def build_end_tag(rng: Rng, outcome: str) -> list[str]:
    tag_lines: list[str] = []
    if outcome == "success":
        pool = _END_TAGS_SUCCESS
    elif outcome == "partial":
        pool = _END_TAGS_PARTIAL
    else:
        pool = _END_TAGS_FAILED
    tag_lines.append(rng.choice(pool))
    return normalize_lines(tag_lines)


def build_previously_on(world: WorldState, limit: int = 4) -> list[str]:
    if not world.case_history:
        return []
    recent: Iterable[CaseRecord] = world.case_history[-limit:]
    lines: list[str] = ["Previously on..."]
    for record in recent:
        note = ""
        if record.notes:
            note = f" {record.notes[0]}"
        lines.append(f"Case {record.case_id} closed ({record.outcome}).{note}")
    return normalize_lines(lines)


def build_partner_line(rng: Rng, chance: float = 0.6) -> list[str]:
    if rng.random() > chance:
        return []
    return normalize_lines([rng.choice(_PARTNER_LINES)])
