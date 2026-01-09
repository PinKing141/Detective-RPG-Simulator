# Phase 3G - Unsub Profile Board (Working Profile)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3g---unsub-profile-board-working-profile

Phase question:
Can players build and revise an Unsub profile without it becoming certainty?

Phase 3G is not:
- a solver
- a stat gate
- a "correct profile" reveal
- a new evidence class

## Scope (allowed)
- Working profile board with 3 axes:
  - Organization (organized/disorganized/mixed/unknown)
  - Drive (visionary/mission/hedonistic/power-control/unknown)
  - Mobility (marauder/commuter/unknown)
- Profile is a player commitment (set_profile) with cost.
- Profile can be revised (time/pressure cost).
- Profile lists supporting evidence (by id/summary).
- Profile explicitly lists gaps (missing corroboration).
- Profile never alters truth, validation, or arrest tiers.

## Core changes
1) Profile board view
- Always visible on a Profile tab.
- Shows current profile axes + evidence supports + gaps.
- No numeric confidence; no "likelihood" language.

2) Profile prompts
- Organization -> Drive -> Mobility -> supporting evidence.
- 1 to 3 evidence items required.
- Invalid submissions are blocked and explained.

3) Profile governance
- Profile is interpretive and provisional.
- Profile output uses constraint language (supports/relies on/lacks).
- Profile does not unlock actions or reduce uncertainty.

## Constraints (non-negotiable)
- No "correct profile" check.
- No stat-gated profile facts.
- No auto-profile from evidence.
- No demographic inference (country/religion/gender).

## Deliverables
- Working profile board displayed in UI and CLI.
- Profile revision costs time/pressure.
- Profile summaries are legible and non-judgmental.
## Current implementation gaps (code audit)
Last updated: 2026-01-08
Resolved:
- Profile board UI/action implemented (set_profile flow wired in CLI/TUI).
  - Code refs: src/noir/ui/app.py, src/noir/investigation/actions.py
- Profile state model implemented on InvestigationState (per-case scope).
  - Code refs: src/noir/investigation/results.py, src/noir/profiling/profile.py

## Exit checklist
- [x] Players can set and revise a profile.
- [x] Profile uses only evidence already known.
- [x] Profile never alters arrest validation.
- [x] Profile language frames uncertainty, not certainty.

Stop condition:
If profiles feel useful without becoming answers, stop.
