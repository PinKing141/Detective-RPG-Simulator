# Phase 3H - Analyst Tools (Rossmo-lite + Tech Sweep)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3h---analyst-tools-rossmo-lite--tech-sweep

Phase question:
Can analyst tools guide strategy without acting as a solver?

Phase 3H is not:
- a map UI
- full Rossmo math
- a new evidence class
- NLP/SCAN

## Scope (allowed)
- Rossmo-lite: a constraint output that ranks 2 to 3 likely zones/districts.
- Commuter vs Marauder assumption chosen by the player.
- Tech sweep: a low-friction analysis action that reveals digital/testimonial leads.
- Analyst outputs are phrasing-only constraints, not answers.
- Analyst tools do not unlock arrests or provide certainty.

## Core changes
1) Rossmo-lite (constraint report)
- Input: 2+ case locations (crime scene + related site).
- Output: "Likely zones" list with caveats.
- Output uses Tier 2 language (limits, suggests, cannot exclude).
- Wrong assumptions waste time or narrow the wrong zone.

2) Tech sweep
- Action that yields:
  - new CCTV lead, or
  - a witness contact, or
  - a device log pointer (as a lead, not new evidence class).
- Costs time/pressure.
- Never produces "proof"; it produces a lead to investigate.

3) Analyst governance
- No numeric probabilities in UI.
- No single-answer outputs.
- Reports are optional and skippable.

## Constraints (non-negotiable)
- No heatmap UI.
- No direct identity revelation.
- No new evidence classes (use existing testimonial/temporal/physical).
- No NLP parsing or deception detection.

## Deliverables
- Rossmo-lite report action (text output + lead impact).
- Tech sweep action (lead generation).
- Analyst outputs logged as constraint notes (not evidence).
## Current implementation gaps (code audit)
Last updated: 2026-01-08
- Rossmo-lite is limited by single-location cases (no multi-site inputs yet).
  - Code refs: src/noir/cases/truth_generator.py, src/noir/investigation/actions.py
- Tech sweep has no distinct device-log lead type (CCTV/neighbor only).
  - Code refs: src/noir/investigation/actions.py, src/noir/investigation/leads.py
- Analyst notes are not included in recaps/briefing outputs.
  - Code refs: src/noir/narrative/recaps.py, src/noir/ui/app.py

## Exit checklist
- [ ] Analyst tools change player path choices.
- [ ] Analyst tools never collapse uncertainty.
- [ ] Reports use constraint language only.
- [ ] No new evidence classes were added.

Stop condition:
If analyst tools guide without solving, stop.
