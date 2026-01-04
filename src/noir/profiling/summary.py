"""Profiling summary builder for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass

from noir.domain.enums import EvidenceType
from noir.investigation.costs import PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.util.grammar import normalize_line


@dataclass(frozen=True)
class ProfilingSummary:
    working_frame: list[str]
    focus_shifts: list[str]
    risk_notes: list[str]


def _known_items(presentation, state: InvestigationState):
    known_ids = set(state.knowledge.known_evidence)
    return [item for item in presentation.evidence if item.id in known_ids]


def _temporal_conflict(items, suspect_id) -> bool:
    windows: list[tuple[int, int]] = []
    for item in items:
        if isinstance(item, WitnessStatement):
            windows.append(item.reported_time_window)
        elif isinstance(item, CCTVReport):
            windows.append(item.time_window)
    if len(windows) < 2:
        return False
    start = max(window[0] for window in windows)
    end = min(window[1] for window in windows)
    return start > end


def _evidence_profile(items) -> dict[str, int]:
    counts = {"testimonial": 0, "physical": 0}
    for item in items:
        if item.evidence_type in (EvidenceType.TESTIMONIAL, EvidenceType.CCTV):
            counts["testimonial"] += 1
        elif item.evidence_type == EvidenceType.FORENSICS:
            counts["physical"] += 1
    return counts


def build_profiling_summary(
    presentation,
    state: InvestigationState,
    hypothesis,
    context_lines: list[str] | None = None,
) -> ProfilingSummary:
    items = _known_items(presentation, state)
    counts = _evidence_profile(items)
    mostly_testimonial = counts["testimonial"] > 0 and counts["physical"] == 0
    weak_physical = any(
        isinstance(item, ForensicsResult) and item.confidence.value == "weak"
        for item in items
    )
    conflict = _temporal_conflict(items, hypothesis.suspect_id) if hypothesis else False
    under_pressure = state.pressure >= max(1, PRESSURE_LIMIT - 1)
    low_time = state.time >= max(1, TIME_LIMIT - 2)
    about_to_arrest = hypothesis is not None

    if conflict:
        working_frame = [
            "Current supports do not cohere; contradictions increase interpretive risk.",
            "The case contains competing readings that cannot be collapsed yet.",
        ]
        if context_lines:
            working_frame = list(context_lines) + working_frame
        focus_shifts = [
            "Prioritise resolving the contradiction before expanding scope.",
            "Check whether the conflict is source failure rather than event failure.",
            "Prefer constraints that do not share the same failure mode.",
        ]
        risk_notes = [
            "Additional evidence of the same kind will not resolve the split.",
            "An arrest under contradiction will almost always degrade outcomes.",
        ]
        return ProfilingSummary(working_frame, focus_shifts, risk_notes)

    if under_pressure or low_time:
        working_frame = [
            "Pressure is shaping what you can still learn, not what is true.",
            "Time limits are beginning to function as evidence erosion.",
        ]
        if context_lines:
            working_frame = list(context_lines) + working_frame
        focus_shifts = [
            "Front-load the most perishable leads.",
            "Choose one corroboration pillar and pursue it fully.",
            "Avoid actions that spike pressure unless you are prepared to commit early.",
        ]
        risk_notes = [
            "Waiting may reduce clarity rather than increase it.",
            "A faster commitment is viable, but consequences will carry.",
        ]
        return ProfilingSummary(working_frame, focus_shifts, risk_notes)

    if mostly_testimonial:
        working_frame = [
            "Current reads are constrained by testimony and memory-dependent detail.",
            "Most supports currently describe proximity, not linkage.",
        ]
        if context_lines:
            working_frame = list(context_lines) + working_frame
        focus_shifts = [
            "Prioritise non-testimonial corroboration of presence.",
            "Seek a constraint that survives cross-checking: access, movement, or artifacts.",
            "Treat additional interviews as diminishing returns unless they add contradiction.",
        ]
        risk_notes = [
            "Without independent support, any commitment remains vulnerable to reversal.",
            "More statements may add volume, not certainty.",
        ]
        return ProfilingSummary(working_frame, focus_shifts, risk_notes)

    if counts["physical"] > 0 and weak_physical:
        working_frame = [
            "Physical traces are present, but they do not yet anchor to a person or route.",
            "Artifacts suggest contact, but attribution remains open.",
        ]
        if context_lines:
            working_frame = list(context_lines) + working_frame
        focus_shifts = [
            "Convert trace into linkage: ownership, access, opportunity, or transfer path.",
            "Use timeline constraints to test feasibility rather than searching for more traces.",
            "Avoid over-committing to a single interpretation of weak physical evidence.",
        ]
        risk_notes = [
            "A clean narrative cannot be built from weak artifacts alone.",
            "This line can strengthen quickly with one corroborating constraint.",
        ]
        return ProfilingSummary(working_frame, focus_shifts, risk_notes)

    if about_to_arrest:
        working_frame = [
            "Your working hypothesis has supports, but relies on one pillar more than corroboration.",
            "The current case shape allows commitment, but not closure.",
        ]
        if context_lines:
            working_frame = list(context_lines) + working_frame
        focus_shifts = [
            "If committing now, choose the narrowest claim you can defend.",
            "If delaying, prioritise a single corroboration action rather than broad searching.",
            "Avoid taking one more action unless it adds a different evidence class.",
        ]
        risk_notes = [
            "This arrest will be judged on coherence, not quantity.",
            "A clean outcome typically requires at least two independent pillars.",
        ]
        return ProfilingSummary(working_frame, focus_shifts, risk_notes)

    working_frame = [
        "Available information reduces the space of possibilities, but does not settle attribution.",
    ]
    if context_lines:
        working_frame = list(context_lines) + working_frame
    focus_shifts = [
        "Prioritise corroboration from a different evidence class.",
        "Resolve the time window before committing to an arrest.",
        "Look for contradictions rather than additional detail from the same source.",
    ]
    risk_notes = [
        "This approach remains sensitive to missing corroboration.",
    ]
    return ProfilingSummary(working_frame, focus_shifts, risk_notes)


def format_profiling_summary(
    summary: ProfilingSummary,
    include_title: bool = True,
) -> list[str]:
    lines: list[str] = []
    if include_title:
        lines.append("Profiling summary")
        lines.append("")
    for line in summary.working_frame:
        lines.append(normalize_line(line))
    lines.append("")
    lines.append("Focus shifts")
    for line in summary.focus_shifts:
        lines.append(f"- {normalize_line(line)}")
    lines.append("")
    lines.append("Risk notes")
    for line in summary.risk_notes:
        lines.append(f"- {normalize_line(line)}")
    return lines
