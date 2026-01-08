# Phase 3C - Gaze and TV Framing (Presentation Only)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3c---gaze-and-tv-framing-presentation-only

Phase question:
Can presentation deliver the TV-science feel without adding facts?

Phase 3C is not:
- a new evidence system
- a validation modifier
- a separate UI mode that changes truth

## Scope (allowed)
- Detective gaze overlays (forensic vs behavioral) as presentation filters.
- Episode titles, cold opens, end tags, and "Previously on..." recaps.
- Partner or team commentary as flavor lines only.
- Post-arrest debrief vignette (optional, skippable).
- Tracery-based overlays for sensory or psychological framing.

## Core changes
1) Detective gaze overlays
- Same evidence, different lens.
- Forensic gaze emphasizes observation and constraints.
- Behavioral gaze emphasizes uncertainty and motive framing.
- Gaze never adds facts; it only changes phrasing.

2) TV framing
- Episode title per case.
- Cold open (2 to 4 lines) before briefing.
- End tag (1 to 3 lines) after case outcome.
- "Previously on..." recap from last 3 to 6 logged events.

3) Post-arrest debrief
- Single-paragraph statement rendered after arrest outcome.
- Uses consequence-tier language only; no new facts.
- Failed arrests render denial/deflection, not confession.

4) Language discipline
- Follow UI_LANGUAGE tiers (observation, constraint, summary, consequence).
- No new claims are introduced by the gaze layer.
- Micro-expression cues are text-only and non-binding.

## Constraints (non-negotiable)
- Gaze overlays never add evidence or change validation.
- Recaps use existing logs only.
- No new mechanics, costs, or thresholds.
- No stat-gated perception filters in this phase.
- Post-arrest debriefs never add evidence or change outcomes.

## Deliverables
- At least two gaze lenses with distinct phrasing.
- Title and recap generator with deterministic seed.
- Cold open and end tag templates.
- Post-arrest debrief templates (confession/denial/deflection).
- Optional partner/witness recurring lines (presentation only).
## Current implementation gaps (code audit)
Last updated: 2026-01-08
- Resolved: Post-arrest vignette is stored in world history for recaps.
  - Code refs: src/noir/ui/app.py, scripts/run_game.py, src/noir/world/state.py

## Exit checklist
- [x] Same case reads differently under two gazes, with no evidence changes.
- [x] Episode titles, cold opens, and end tags render consistently.
- [x] Recaps draw from logged events only.
- [x] No new facts or validation modifiers exist.

Stop condition:
If TV framing is present and non-invasive, stop.
