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
3) Run the CLI loop:
   `python scripts/run_game.py --seed 101`
4) Run the Textual TUI:
   `python scripts/run_textual.py --seed 101`

Useful flags:
- `--case-archetype pattern|character` (force bottom-up scene mode for those cases)
- `--gaze forensic|behavioral` (presentation lens)
- `--no-world-db` (skip persistence)
- `--smoke --smoke-find` (short non-interactive path)

## Layout
- src/noir: core systems
- assets/text_atoms: generator-ready text packs
- data/schemas: location and evidence schema
- scripts: CLI/TUI entry points
- tests: invariants and regression tests
