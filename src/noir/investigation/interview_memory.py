from __future__ import annotations

from noir.investigation.costs import clamp
from noir.investigation.interviews import InterviewApproach, InterviewState, InterviewTheme
from noir.presentation.evidence import EvidenceItem


def interview_memory_key(
    approach: InterviewApproach,
    theme: InterviewTheme | None,
) -> str:
    if approach == InterviewApproach.THEME and theme is not None:
        return f"{approach.value}:{theme.value}"
    return approach.value


def register_interview_memory(
    interview_state: InterviewState,
    approach: InterviewApproach,
    theme: InterviewTheme | None,
    prompt_label: str | None,
) -> tuple[int, bool]:
    memory_key = interview_memory_key(approach, theme)
    repeat_count = interview_state.approach_counts.get(memory_key, 0)
    interview_state.approach_counts[memory_key] = repeat_count + 1
    interview_state.approach_history.append(memory_key)
    repeated_prompt = False
    if prompt_label:
        prompt_key = f"{memory_key}:{prompt_label}"
        repeated_prompt = prompt_key in interview_state.prompt_history
        interview_state.prompt_history.append(prompt_key)
    return repeat_count, repeated_prompt


def apply_revisit_friction(
    interview_state: InterviewState,
    approach: InterviewApproach,
    repeat_count: int,
    repeated_prompt: bool,
) -> None:
    if repeat_count <= 0 and not repeated_prompt:
        return
    repeat_factor = max(1, repeat_count)
    rapport_penalty = 0.03 * repeat_factor
    resistance_increase = 0.06 * repeat_factor
    fatigue_increase = 0.08 * repeat_factor
    if approach == InterviewApproach.PRESSURE:
        rapport_penalty += 0.05
        resistance_increase += 0.05
    elif approach == InterviewApproach.THEME:
        resistance_increase += 0.03
    if repeated_prompt:
        resistance_increase += 0.04
        fatigue_increase += 0.04
    interview_state.rapport = clamp(interview_state.rapport - rapport_penalty, 0.0, 1.0)
    interview_state.resistance = clamp(
        interview_state.resistance + resistance_increase,
        0.0,
        1.0,
    )
    interview_state.fatigue = clamp(interview_state.fatigue + fatigue_increase, 0.0, 1.0)


def revisit_note(
    approach: InterviewApproach,
    repeated_prompt: bool,
) -> str:
    if approach == InterviewApproach.PRESSURE:
        note = "The witness stiffens at the repeated pressure and starts cutting answers short."
    elif approach == InterviewApproach.THEME:
        note = "The witness notices you are pushing the same story and gets more defensive."
    else:
        note = "The witness realizes you are retracing the same ground and starts repeating themselves."
    if repeated_prompt:
        return f"{note} Repeating the same question makes the answer thinner."
    return note


def repeat_prefix(
    statement: str,
    approach: InterviewApproach,
    theme: InterviewTheme | None,
    repeat_count: int,
    repeated_prompt: bool,
) -> str:
    if repeat_count <= 0 and not repeated_prompt:
        return statement
    if approach == InterviewApproach.BASELINE:
        return f"Like I said before, {statement[:1].lower() + statement[1:] if statement else statement}"
    if approach == InterviewApproach.PRESSURE:
        return f"I've already answered that. {statement}"
    theme_label = theme.value.replace("_", " ") if theme is not None else "story"
    return f"You're still pushing the {theme_label} angle. {statement}"


def interview_summary(
    approach: InterviewApproach,
    revealed: list[EvidenceItem],
    repeat_count: int,
    repeated_prompt: bool,
) -> str:
    if repeat_count <= 0 and not repeated_prompt:
        if revealed:
            return f"Interview ({approach.value}) yields a usable statement."
        return f"Interview ({approach.value}) adds nothing new."
    if revealed:
        if approach == InterviewApproach.PRESSURE:
            return "Interview (pressure) forces a grudging repeat with new strain showing."
        if approach == InterviewApproach.THEME:
            return "Interview (theme) reopens the same story from a defensive angle."
        return "Interview (baseline) produces a guarded repeat of the earlier account."
    if approach == InterviewApproach.PRESSURE:
        return "Interview (pressure) hardens the witness with no new detail."
    if approach == InterviewApproach.THEME:
        return "Interview (theme) circles the same story and adds nothing new."
    return "Interview (baseline) circles the same ground."