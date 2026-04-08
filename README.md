# Detective RPG Simulator

Procedural noir detective RPG simulator with deterministic cases, legible outcomes,
and a Phase 3 investigative depth loop (POIs, interviews, and gaze filters).

## Docs
- docs/blueprint/ARCHITECTURE.md
- docs/blueprint/RULES.md
- docs/blueprint/ROADMAP.md
- docs/blueprint/PHASE_3A_TASKS.md
- docs/blueprint/PHASE_3B_TASKS.md
- docs/blueprint/PHASE_3C_TASKS.md
- docs/blueprint/PHASE_4_TASKS.md

## Quick start
1) Create and activate a virtual environment.
2) Install dependencies: `pip install -e .`
3) Run the primary Textual presentation:
   `detective-play --seed 101`
4) If you need the fallback surface, run the CLI loop:
   `python scripts/run_game.py --seed 101`

The Textual UI is the intended player-facing presentation. `detective-play` is the default launcher for it. The CLI loop is the backup path for environments where the TUI is unavailable or inconvenient.

Useful flags:
- `--case-archetype pattern|character` (force bottom-up scene mode for those cases)
- `--gaze forensic|behavioral` (presentation lens)
- `--no-world-db` (skip persistence)
- `--smoke --smoke-find` (short non-interactive path)

## Investigation Flow
1. Collect evidence through interviews, CCTV, forensics, and scene actions.
2. Set a hypothesis by choosing a suspect, 1 to 3 claims, 1 to 3 evidence items, and one reasoning link for each claim.
3. Arrest validates the full chain, so clean outcomes depend on corroborated evidence rather than testimony alone.

The CLI and Textual UI both surface early guidance when the case is still too witness-heavy, and both now recommend stronger evidence for the current theory before arrest.

## Saves And Resume
- Saves restore the active hypothesis, selected evidence, and explicit reasoning steps.
- Interview state also persists, including revisit memory and prompt history.
- Loading a save in either the CLI or the Textual UI restores the same board state you left behind.

## Quality Sweep
Run a lightweight route sample outside the strict regression set with:

`python scripts/sweep_case_quality.py --start-seed 1 --count 25`

To re-run the shaky seeds as a focused triage pass, feed them back in directly:

`python scripts/sweep_case_quality.py --triage-seeds 4,7,11,15`

The sweep now reports a clean rate and expands up to 10 shaky or non-clean seeds with the selected claims, evidence mix, and top gaps.

Use `--target-clean-rate 0.60` when you want the script to print whether the current sample is good enough for reporting. `--fail-on-non-clean` is still useful, but it is best treated as a non-blocking CI/reporting signal once the clean rate is consistently at the target you want; it is too strict for a blocking gate while the generator is still expected to produce some shaky cases.

GitHub Actions reporting lives in [.github/workflows/case-quality-report.yml](.github/workflows/case-quality-report.yml). It runs on a weekly schedule and on manual dispatch, keeps the sweep step non-blocking with `continue-on-error: true`, and uploads the captured report files as artifacts. If you already have a shaky-seed list, pass it through the `triage_seeds` workflow input to get a second focused triage artifact without changing the workflow.

## Layout
- src/noir: core systems
- src/noir/ui: primary Textual presentation
- src/noir/cli: launch surfaces for Textual and fallback CLI
- assets/text_atoms: generator-ready text packs
- data/schemas: location and evidence schema
- scripts: CLI/TUI entry points
- tests: invariants and regression tests
