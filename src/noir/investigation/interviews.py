"""Stateful interview helpers for Phase 3B."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re

from noir.domain.enums import ConfidenceBand, EvidenceType


class InterviewPhase(StrEnum):
    BASELINE = "baseline"
    PRESSURE = "pressure"
    THEME = "theme"
    SHUTDOWN = "shutdown"
    CONFESSION = "confession"


class InterviewApproach(StrEnum):
    BASELINE = "baseline"
    PRESSURE = "pressure"
    THEME = "theme"


class InterviewTheme(StrEnum):
    BLAME_VICTIM = "blame_victim"
    CIRCUMSTANCE = "circumstance"
    ALTRUISTIC = "altruistic"
    ACCIDENTAL = "accidental"


@dataclass(frozen=True)
class BaselineProfile:
    avg_sentence_len: float
    pronoun_ratio: float
    tense_pref: str


@dataclass
class InterviewState:
    phase: InterviewPhase = InterviewPhase.BASELINE
    rapport: float = 0.5
    resistance: float = 0.5
    fatigue: float = 0.0
    baseline_profile: BaselineProfile | None = None
    last_claims: list[str] = field(default_factory=list)
    motive_to_lie: bool = False
    contradiction_emitted: bool = False


@dataclass(frozen=True)
class ResponseTemplate:
    phase: InterviewPhase
    approach: InterviewApproach
    text: str
    claim_tags: list[str]
    uncertainty_hooks: list[str]
    confidence_band: ConfidenceBand


@dataclass(frozen=True)
class EvidenceEmission:
    evidence_type: EvidenceType
    summary: str
    claim_tags: list[str]
    confidence_band: ConfidenceBand
    uncertainty_hooks: list[str]


_PRONOUNS = {"i", "me", "my", "mine", "myself"}
_PAST_HINTS = {"was", "were", "did", "saw", "heard", "went", "left"}
_PRESENT_HINTS = {"am", "is", "are", "see", "hear", "go", "leave"}


def _sentence_lengths(text: str) -> list[int]:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return [0]
    lengths = []
    for sentence in sentences:
        lengths.append(len(sentence.split()))
    return lengths


def _pronoun_ratio(text: str) -> float:
    tokens = [t.strip(".,!?\"'").lower() for t in text.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0
    pronouns = [t for t in tokens if t in _PRONOUNS]
    return len(pronouns) / len(tokens)


def _tense_pref(text: str) -> str:
    tokens = [t.strip(".,!?\"'").lower() for t in text.split()]
    past = sum(1 for t in tokens if t in _PAST_HINTS)
    present = sum(1 for t in tokens if t in _PRESENT_HINTS)
    if past >= present:
        return "past"
    return "present"


def build_baseline_profile(text: str) -> BaselineProfile:
    lengths = _sentence_lengths(text)
    avg_len = sum(lengths) / max(1, len(lengths))
    return BaselineProfile(
        avg_sentence_len=avg_len,
        pronoun_ratio=_pronoun_ratio(text),
        tense_pref=_tense_pref(text),
    )


def baseline_hooks(
    baseline: BaselineProfile | None,
    current_text: str,
    template_hooks: list[str],
) -> list[str]:
    hooks: list[str] = []
    if baseline is None:
        return list(template_hooks)
    current_profile = build_baseline_profile(current_text)
    if baseline.pronoun_ratio >= 0.08 and current_profile.pronoun_ratio < baseline.pronoun_ratio * 0.6:
        hooks.append("Pronoun use drops from the baseline.")
    if baseline.tense_pref != current_profile.tense_pref:
        hooks.append("Verb tense shifts from the baseline.")
    if current_profile.avg_sentence_len < baseline.avg_sentence_len * 0.6:
        hooks.append("Statements are shorter than baseline.")
    hooks.extend(template_hooks)
    return hooks
