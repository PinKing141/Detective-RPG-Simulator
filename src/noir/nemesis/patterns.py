"""Phase 3D proto-nemesis pattern tracking (run-only, deterministic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from noir.util.rng import Rng
from noir.util.grammar import normalize_line


class PatternType(StrEnum):
    NONE = "none"
    SIGNATURE = "signature"
    COPYCAT = "copycat"
    RED_HERRING = "red_herring"
    BACKGROUND = "background"


_LABEL_LADDER = [
    "Noted Similarity",
    "Recurring Detail",
    "Pattern Worth Monitoring",
    "Possible Imitation",
    "Consistent With Prior Incidents",
]

_RED_HERRING_SOURCES = [
    "Local ritual or community practice.",
    "Victim behavior artifacts.",
    "Media-inspired mimicry.",
    "Coincidental staging or environment.",
]


@dataclass(frozen=True)
class Motif:
    id: int
    name: str
    category: str
    token: str | None = None
    staging: str | None = None
    trace: str | None = None
    style: str | None = None
    message: str | None = None
    discoverability: list[str] = field(default_factory=list)
    copycat_risk: str = "Medium"

    def detail_label(self) -> tuple[str | None, str | None]:
        if self.staging:
            return "Staging", self.staging
        if self.trace:
            return "Trace", self.trace
        if self.style:
            return "Style", self.style
        return None, None


@dataclass(frozen=True)
class MotifObservation:
    token_status: str
    staging_status: str
    message_status: str


@dataclass(frozen=True)
class PatternAddendum:
    case_id: str
    label: str
    observations: list[str]
    assessment_lines: list[str]
    action_lines: list[str]

    def render(self) -> list[str]:
        lines: list[str] = [
            "CASE FILE ADDENDUM - INTERNAL NOTE",
            "",
            "Summary:",
            "A detail observed in this incident resembles elements seen previously.",
            f"Status: {self.label}",
            "",
            "Observations:",
        ]
        for line in self.observations:
            lines.append(f"- {normalize_line(line)}")
        lines.extend(
            [
                "",
                "Assessment:",
            ]
        )
        lines.extend(normalize_line(line) for line in self.assessment_lines)
        lines.extend(
            [
                "",
                "Action:",
            ]
        )
        lines.extend(normalize_line(line) for line in self.action_lines)
        return lines


def _motif_meta(motif: Motif | None) -> dict[str, Any] | None:
    if motif is None:
        return None
    return {
        "id": motif.id,
        "name": motif.name,
        "category": motif.category,
        "token": motif.token,
        "staging": motif.staging,
        "trace": motif.trace,
        "style": motif.style,
        "message": motif.message,
        "discoverability": list(motif.discoverability),
        "copycat_risk": motif.copycat_risk,
    }


def _observation_meta(observation: MotifObservation | None) -> dict[str, str] | None:
    if observation is None:
        return None
    return {
        "token_status": observation.token_status,
        "staging_status": observation.staging_status,
        "message_status": observation.message_status,
    }


@dataclass(frozen=True)
class PatternCasePlan:
    case_id: str
    case_index: int
    pattern_type: PatternType
    label: str | None
    primary: Motif | None
    support: Motif | None
    observation: MotifObservation | None
    support_present: bool
    red_herring_source: str | None = None

    def to_case_meta(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_index": self.case_index,
            "pattern_type": self.pattern_type.value,
            "label": self.label,
            "primary": _motif_meta(self.primary),
            "support": _motif_meta(self.support),
            "observation": _observation_meta(self.observation),
            "support_present": self.support_present,
            "red_herring_source": self.red_herring_source,
        }


def _motifs_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "assets" / "text_atoms" / "nemesis_motifs.yml"


def _load_motifs(path: Path | None = None) -> list[Motif]:
    motif_path = path or _motifs_path()
    data = yaml.safe_load(motif_path.read_text(encoding="utf-8")) or {}
    motifs: list[Motif] = []
    for item in data.get("motifs", []) or []:
        motifs.append(
            Motif(
                id=int(item.get("id")),
                name=str(item.get("name", "")).strip(),
                category=str(item.get("category", "")).strip(),
                token=item.get("token"),
                staging=item.get("staging"),
                trace=item.get("trace"),
                style=item.get("style"),
                message=item.get("message"),
                discoverability=list(item.get("discoverability", []) or []),
                copycat_risk=str(item.get("copycat_risk", "Medium")),
            )
        )
    return motifs


def _primary_motifs(motifs: list[Motif]) -> list[Motif]:
    return [motif for motif in motifs if motif.category != "forensic_trace"]


def _support_motifs(motifs: list[Motif]) -> list[Motif]:
    return [motif for motif in motifs if motif.category == "forensic_trace"]


class PatternTracker:
    """Run-only pattern tracker for proto-nemesis hints (Phase 3D)."""

    def __init__(self, rng: Rng, motifs: list[Motif]) -> None:
        self._rng = rng
        self._motifs = motifs
        primary = _primary_motifs(motifs)
        support = _support_motifs(motifs)
        if not primary or not support:
            raise ValueError("Motif library requires primary and forensic_trace motifs.")
        self.signature_primary = rng.choice(primary)
        self.signature_support = rng.choice([m for m in support if m.id != self.signature_primary.id])
        self.signature_seen = 0
        self.background_motif: Motif | None = None
        self.background_remaining = 0
        self.last_signature_case: int | None = None
        self.next_signature_case = rng.randint(2, 4)
        self.false_positive_gap = rng.randint(3, 5)
        self.cases_since_false_positive = 0
        self.force_false_positive_next = False
        self._case_plans: dict[str, PatternCasePlan] = {}

    @classmethod
    def from_library(cls, rng: Rng, path: Path | None = None) -> "PatternTracker":
        return cls(rng, _load_motifs(path))

    def plan_case(self, case_id: str, case_index: int) -> PatternCasePlan:
        existing = self._case_plans.get(case_id)
        if existing:
            return existing
        case_rng = self._rng.fork(f"case-{case_index}")
        pattern_type = self._decide_pattern_type(case_index, case_rng)
        if pattern_type == PatternType.NONE:
            self.cases_since_false_positive += 1
            plan = PatternCasePlan(
                case_id=case_id,
                case_index=case_index,
                pattern_type=pattern_type,
                label=None,
                primary=None,
                support=None,
                observation=None,
                support_present=False,
            )
            self._case_plans[case_id] = plan
            return plan
        if pattern_type in (PatternType.COPYCAT, PatternType.RED_HERRING):
            self.cases_since_false_positive = 0
        else:
            self.cases_since_false_positive += 1

        if pattern_type == PatternType.SIGNATURE:
            motif = self.signature_primary
            support = self.signature_support
            observation = self._build_observation(case_rng, motif, drift=True)
            label = self._label_for_signature(observation, support_present=True)
            support_present = True
            red_herring_source = None
            self.signature_seen += 1
            self.last_signature_case = case_index
            self.next_signature_case = case_index + case_rng.randint(2, 4)
        elif pattern_type == PatternType.COPYCAT:
            motif = self.signature_primary
            support = self.signature_support
            observation = self._build_observation(case_rng, motif, drift=False, copycat=True)
            label = self._label_for_copycat(observation)
            support_present = False
            red_herring_source = None
        elif pattern_type == PatternType.BACKGROUND:
            motif = self._background_motif(case_rng)
            support = None
            observation = self._build_observation(case_rng, motif, drift=True)
            label = self._label_for_background(observation)
            support_present = False
            red_herring_source = None
            self.background_remaining = max(0, self.background_remaining - 1)
            if self.background_remaining == 0:
                self.background_motif = None
        else:
            motif = self._red_herring_motif(case_rng)
            support = None
            observation = self._build_observation(case_rng, motif, drift=False, red_herring=True)
            label = _LABEL_LADDER[0]
            support_present = False
            red_herring_source = case_rng.choice(_RED_HERRING_SOURCES)

        plan = PatternCasePlan(
            case_id=case_id,
            case_index=case_index,
            pattern_type=pattern_type,
            label=label,
            primary=motif,
            support=support,
            observation=observation,
            support_present=support_present,
            red_herring_source=red_herring_source,
        )
        self._case_plans[case_id] = plan
        return plan

    def record_case(self, case_id: str, case_index: int) -> PatternAddendum | None:
        plan = self._case_plans.get(case_id)
        if plan is None:
            plan = self.plan_case(case_id, case_index)
        if plan.pattern_type == PatternType.NONE or plan.primary is None or plan.observation is None:
            return None
        motif = plan.primary
        observation = plan.observation
        support = plan.support
        observations: list[str] = [self._motif_line(motif, observation)]
        if support:
            observations.append(self._support_line(support, present=plan.support_present))
        observations.extend(self._status_lines(observation))

        assessment_lines = [
            "This may indicate recurrence, imitation, or coincidence.",
            "Insufficient evidence to draw conclusions.",
        ]
        if plan.pattern_type == PatternType.COPYCAT:
            assessment_lines.append("The placement could reflect imitation rather than continuity.")
        if plan.pattern_type == PatternType.RED_HERRING and plan.red_herring_source:
            assessment_lines.append(plan.red_herring_source)
        if plan.pattern_type == PatternType.BACKGROUND:
            assessment_lines.append("Treat this as a separate line until corroborated.")

        action_lines = ["Continue monitoring in future cases."]
        return PatternAddendum(
            case_id=case_id,
            label=plan.label or _LABEL_LADDER[0],
            observations=observations,
            assessment_lines=assessment_lines,
            action_lines=action_lines,
        )

    def _decide_pattern_type(self, case_index: int, rng: Rng) -> PatternType:
        if self.force_false_positive_next and case_index != self.next_signature_case:
            self.force_false_positive_next = False
            return PatternType.RED_HERRING

        if case_index == self.next_signature_case:
            if self.cases_since_false_positive >= self.false_positive_gap:
                self.force_false_positive_next = True
            return PatternType.SIGNATURE

        if self.background_remaining > 0 and self._background_allowed(case_index):
            return PatternType.BACKGROUND

        if (
            self.signature_seen > 0
            and rng.random() < 0.2
            and self._copycat_allowed(case_index)
        ):
            return PatternType.COPYCAT

        if self.cases_since_false_positive >= self.false_positive_gap:
            return PatternType.RED_HERRING

        if rng.random() < 0.25:
            return PatternType.RED_HERRING

        if self._background_allowed(case_index) and rng.random() < 0.2:
            self.background_remaining = rng.randint(2, 4)
            return PatternType.BACKGROUND

        return PatternType.NONE

    def _background_allowed(self, case_index: int) -> bool:
        if self.last_signature_case is not None:
            if abs(case_index - self.last_signature_case) <= 1:
                return False
        if abs(case_index - self.next_signature_case) <= 1:
            return False
        return True

    def _copycat_allowed(self, case_index: int) -> bool:
        if self.last_signature_case is not None:
            if case_index - self.last_signature_case < 2:
                return False
        if self.next_signature_case - case_index < 2:
            return False
        return self._background_allowed(case_index)

    def _background_motif(self, rng: Rng) -> Motif:
        if self.background_motif is None:
            excluded = {self.signature_primary.id, self.signature_support.id}
            options = [m for m in self._motifs if m.id not in excluded]
            self.background_motif = rng.choice(options)
        return self.background_motif

    def _red_herring_motif(self, rng: Rng) -> Motif:
        options = [m for m in self._motifs if m.id not in {self.signature_primary.id}]
        return rng.choice(options)

    def _build_observation(
        self,
        rng: Rng,
        motif: Motif,
        *,
        drift: bool,
        copycat: bool = False,
        red_herring: bool = False,
    ) -> MotifObservation:
        token_status = "Present"
        staging_status = "Consistent"
        message_status = "Present"
        if copycat:
            staging_status = "Inconsistent"
            message_status = rng.choice(["Altered", "Absent"])
        if red_herring:
            token_status = "Ambiguous"
            staging_status = rng.choice(["Unknown", "Inconsistent"])
            message_status = "Absent"
        if drift and rng.random() < 0.25:
            drift_target = rng.choice(["token", "staging", "message"])
            if drift_target == "token":
                token_status = "Ambiguous"
            elif drift_target == "staging":
                staging_status = "Inconsistent"
            else:
                message_status = rng.choice(["Altered", "Absent"])
        if not motif.token:
            token_status = "Ambiguous"
        label, detail = motif.detail_label()
        if detail is None:
            staging_status = "Unknown"
        if not motif.message:
            message_status = "Absent"
        return MotifObservation(
            token_status=token_status,
            staging_status=staging_status,
            message_status=message_status,
        )

    def _label_for_signature(self, observation: MotifObservation, support_present: bool) -> str:
        integrity = self._integrity_count(observation)
        if integrity < 2:
            return _LABEL_LADDER[0]
        if not support_present:
            return _LABEL_LADDER[3]
        if self.signature_seen >= 3:
            return _LABEL_LADDER[4]
        if self.signature_seen == 2:
            return _LABEL_LADDER[2]
        if self.signature_seen == 1:
            return _LABEL_LADDER[1]
        return _LABEL_LADDER[0]

    def _label_for_copycat(self, observation: MotifObservation) -> str:
        integrity = self._integrity_count(observation)
        if integrity < 2:
            return _LABEL_LADDER[0]
        return _LABEL_LADDER[3]

    def _label_for_background(self, observation: MotifObservation) -> str:
        integrity = self._integrity_count(observation)
        if integrity < 2:
            return _LABEL_LADDER[0]
        if self.background_remaining <= 1:
            return _LABEL_LADDER[2]
        return _LABEL_LADDER[1]

    def _integrity_count(self, observation: MotifObservation) -> int:
        score = 0
        if observation.token_status == "Present":
            score += 1
        if observation.staging_status == "Consistent":
            score += 1
        if observation.message_status == "Present":
            score += 1
        return score

    def _motif_line(self, motif: Motif, observation: MotifObservation) -> str:
        parts: list[str] = [motif.name]
        if motif.token:
            parts.append(f"Token: {motif.token}")
        label, detail = motif.detail_label()
        if detail:
            parts.append(f"{label}: {detail}")
        if motif.message and observation.message_status in {"Present", "Altered"}:
            parts.append(f"Message: {motif.message}")
        return "; ".join(parts)

    def _support_line(self, motif: Motif, present: bool) -> str:
        label, detail = motif.detail_label()
        detail_text = detail or motif.token or motif.name
        if present:
            return f"Supporting trace: {motif.name} ({detail_text})."
        return f"Supporting trace expected: {motif.name}. Not observed."

    def _status_lines(self, observation: MotifObservation) -> list[str]:
        return [
            f"Token: {observation.token_status}.",
            f"Staging: {observation.staging_status}.",
            f"Message: {observation.message_status}.",
        ]
