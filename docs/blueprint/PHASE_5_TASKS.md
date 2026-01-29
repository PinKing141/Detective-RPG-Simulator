# Phase 5 - Polish Checklist (UI/CLI Mapped)

Rule: no new systems. Only clarity, readability, and pacing improvements.
Rule: every change must improve comprehension or reduce clutter.

Scope targets
- CLI loop output (scripts/run_game.py)
- TUI layout and panels (src/noir/ui/app.py)
- Recaps, briefings, episode framing (src/noir/narrative/recaps.py, ui briefing)
- Evidence and interview text templates (assets/text_atoms, narrative formatting)

## Global polish gates (must pass)
- [ ] Pressure, Investigation Time, Trust are consistently named and capitalized.
- [ ] No duplicate lines in any briefing, recap, or intro block.
- [ ] Every screen shows "what matters now" within the first 5 lines.
- [ ] Prompts never dump long lists into the wire/log.
- [ ] The selected tab label remains visible and is highlighted (not removed).

## CLI output polish (scripts/run_game.py)
Output areas: case start banner, status line, leads list, action menu, prompt lists.

- [ ] Case start banner is 3-5 lines max, no repetition.
  - Example target: Episode line, location line, pressure/trust line only.
- [ ] Status line is one line and includes Investigation Time / Pressure / Trust.
- [ ] Leads list shows deadlines and status in one line each (no extra commentary).
- [ ] Action list is always 7 lines (or fewer), no extra text between options.
- [ ] Prompt lists are compact and do not repeat statement text.
- [ ] Any failure message is one line plus one explanation line.

## TUI header and tabs (src/noir/ui/app.py)
Output areas: header line, tab bar.

- [ ] Header line fits one line and includes:
  - Case ID, Investigation Time, Pressure, Trust, Gaze, Episode code.
- [ ] Tab labels are: Case File | Leads | Scene | Profile | Pattern | Debrief
- [ ] Selected tab is highlighted, not removed.
- [ ] Gaze hint is visible: "G: toggle gaze".
- [ ] When a prompt is active, wire panel is hidden.

## TUI list panel (left column)
Output areas: evidence list, leads, POIs, neighbor leads.

- [ ] Evidence list is scannable (one line per item).
- [ ] Leads list shows deadline in-line (t2/t4) and resolved/expired.
- [ ] POIs show brief description (one sentence) and visited status.
- [ ] Neighbor leads are shown as "follow-up" leads (no lore text).

## TUI detail panel (right column)
Output areas: prompt content, selected evidence detail, pattern addendum, debrief.

- [ ] Prompt content renders only in detail panel (not in wire).
- [ ] Evidence detail is shown for the selected item only.
- [ ] Pattern addendum uses the case-file template block (not a list).
- [ ] Debrief shows outcome + 1-3 bullet notes only.

## Wire/log behavior (TUI)
Output areas: short action log.

- [ ] Wire is short, one-line entries only.
- [ ] No long statements or prompt lists in wire.
- [ ] On prompt activation: wire hidden; on prompt completion: wire returns.

## Briefing and recap (CLI and TUI)
Output areas: "Previously on...", episode title, cold open.

- [ ] "Previously on..." shows max 3 lines, no duplicates.
- [ ] Episode title line is centered and appears once.
- [ ] Cold open is 2-3 lines, no repetition.
- [ ] Case snapshot box appears before cold open (district, location, pressure/trust).

## Evidence and interview text (templates)
Output areas: witness statement, forensics report, confession output.

- [ ] Statements have consistent casing and punctuation.
- [ ] Time phrasing avoids "between X and X"; use "around" when equal.
- [ ] "The" is used for location names when appropriate (the Harbor Warehouse).
- [ ] Confession output is clearly distinct from baseline/follow-up statements.
- [ ] No solver vocabulary (correct/wrong/proved).

## Operations and endings (Phase 4 outputs)
Output areas: warrant, stakeout, bait, raid, ending epilogue.

- [ ] Warrant packet summary is 3-5 lines, no raw evidence dump.
- [ ] Operation outcome is single block: Assessment -> Factors -> Effect.
- [ ] Ending epilogue is 4-6 lines, no score or moral judgment.
- [ ] Early endings and final endings share the same tone template.

## Grammar and casing pass (whole game)
Output areas: all text outputs.

- [ ] Sentence starts capitalized, ends with punctuation.
- [ ] No missing determiners ("the") for locations.
- [ ] Proper nouns preserved (names, districts).
- [ ] No repeated lines in any single output block.

## Exit checklist (Phase 5)
- [ ] Players can state what matters now (from header + leads).
- [ ] Text is scannable (no block exceeds 8 lines without a heading).
- [ ] Recaps orient without repeating.
- [ ] Every mechanic is learnable through play (no docs required).
- [ ] No new systems added.
- [ ] Every change improves comprehension or pacing.

Stop condition: When polish stops improving comprehension, stop entirely.
