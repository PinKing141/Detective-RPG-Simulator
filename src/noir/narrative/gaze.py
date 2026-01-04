"""Presentation-only gaze filters for Phase 3C."""

from __future__ import annotations

from enum import StrEnum

from noir.narrative.grammar import normalize_line


class GazeMode(StrEnum):
    FORENSIC = "forensic"
    BEHAVIORAL = "behavioral"


def gaze_label(mode: GazeMode) -> str:
    if mode == GazeMode.BEHAVIORAL:
        return "Behavioral"
    return "Forensic"


def format_witness_lines(
    time_phrase: str,
    statement: str,
    note: str | None,
    confidence: str,
    uncertainty_hooks: list[str],
    mode: GazeMode,
) -> list[str]:
    statement = normalize_line(statement)
    if mode == GazeMode.BEHAVIORAL:
        timing_label = "Timing"
        statement_label = "Account"
        note_label = "Reading"
    else:
        timing_label = "Time window"
        statement_label = "Observation"
        note_label = "Constraint"
    lines = [
        f"{timing_label}: {time_phrase} (estimate)",
        f"{statement_label}: {statement}",
    ]
    if note:
        cleaned = note.replace("Detective note:", "").strip()
        cleaned = normalize_line(cleaned)
        lines.append(f"{note_label}: {cleaned}")
    if uncertainty_hooks:
        lines.append("Uncertainty:")
        lines.extend(f"- {normalize_line(hook)}" for hook in uncertainty_hooks)
    lines.append(f"Confidence: {confidence}")
    return lines


def format_forensic_lines(
    observation: str,
    confidence: str,
    tod_phrase: str | None,
    stage_hint: str | None,
    mode: GazeMode,
) -> list[str]:
    observation = normalize_line(observation)
    if stage_hint:
        stage_hint = normalize_line(stage_hint)
    if mode == GazeMode.BEHAVIORAL:
        obs_label = "Scene read"
        tod_label = "Timing"
        stage_label = "Condition note"
    else:
        obs_label = "Observation"
        tod_label = "Estimated TOD"
        stage_label = "Stage hint"
    lines = [f"{obs_label}: {observation}"]
    if tod_phrase:
        lines.append(f"{tod_label}: {tod_phrase}")
    if stage_hint:
        lines.append(f"{stage_label}: {stage_hint}")
    lines.append(f"Confidence: {confidence}")
    return lines


def format_cctv_lines(
    summary: str,
    time_phrase: str,
    note: str | None,
    confidence: str,
    mode: GazeMode,
) -> list[str]:
    summary = normalize_line(summary)
    if mode == GazeMode.BEHAVIORAL:
        time_label = "Timing"
        note_label = "Read"
        summary_label = "Capture"
    else:
        time_label = "Time window"
        note_label = "Constraint"
        summary_label = "Observation"
    lines = [
        f"{summary_label}: {summary}",
        f"{time_label}: {time_phrase}",
    ]
    if note:
        cleaned = note.replace("Detective note:", "").strip()
        cleaned = normalize_line(cleaned)
        lines.append(f"{note_label}: {cleaned}")
    lines.append(f"Confidence: {confidence}")
    return lines


def format_forensics_result_lines(
    finding: str,
    method_category: str | None,
    confidence: str,
    mode: GazeMode,
) -> list[str]:
    finding = normalize_line(finding)
    if mode == GazeMode.BEHAVIORAL:
        finding_label = "Trace read"
        method_label = "Method class"
    else:
        finding_label = "Finding"
        method_label = "Method category"
    lines = [f"{finding_label}: {finding}"]
    if method_category:
        lines.append(f"{method_label}: {method_category}")
    lines.append(f"Confidence: {confidence}")
    return lines
