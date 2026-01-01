# Architecture

This document defines the non-negotiable architecture boundaries and data flow.

## Core principles
1) Truth vs Presentation: Truth is canonical history. Presentation is noisy, partial, and sometimes deceptive. Presentation never rewrites Truth.
2) Truth is append-only: past events are not edited. Corrections are new events.
3) Evidence is causal: every clue traces to Truth or an explicit lie mechanism.
4) Noise is explainable: uncertainty has a reason the player can later understand.
5) Player solves by reasoning: no magic deduction buttons.
6) Nemesis rule: signature is fixed, MO adapts, adaptation is readable.
7) Showrunner rule: controls pacing and spotlight only; never invents truth to force drama.
8) Debuggability: every case is reproducible by seed and case ID.

## State model and flow
- TruthState: canonical world history, timeline, and relationships.
- PresentationCase: player-facing evidence projected from TruthState with noise.
- InvestigatorState: what the player knows, clocks, costs, and hypothesis board.

Flow:
1) Truth generator builds a case in TruthState.
2) Projector derives PresentationCase from TruthState.
3) UI presents PresentationCase and the deduction board.
4) Investigation actions apply costs and update TruthState through the simulator.
5) Narrative formats results; it does not decide results.

## Module boundaries
- domain: data models, enums, ontology, and invariants.
- truth: graph wrapper, simulator, queries, exporters.
- presentation: projector, erosion/noise, evidence objects, knowledge.
- investigation: actions, costs, thresholds, results.
- deduction: hypothesis board, scoring, validation.
- narrative: NLG, styles, recaps.
- nemesis: state, signature, MO adaptation, director hooks.
- showrunner: pacing and scheduling (spotlight control only).
- persistence: save/load and migrations.
- ui: Textual app, screens, widgets, rendering.

## Allowed dependencies
- domain and util are the base.
- truth imports domain and util only.
- presentation reads truth and domain; never writes truth.
- investigation writes truth only through simulator; never edits presentation directly.
- deduction reads presentation and investigation results; writes only player hypothesis state.
- narrative reads results and knowledge; never changes outcomes.
- ui reads presentation and results; no direct access to truth.

## Determinism and reproducibility
- Single RNG source seeded in config and passed explicitly.
- Case ID and seed stored in saves and dumps.
- Truth dumps must reproduce a case without side effects.

## Invariants and validation
- Invariants live in domain/rules.py.
- All writes to TruthState go through validators.
- Violations fail early and loudly.

## Persistence contract
- Save files store: seed, truth snapshot, presentation state, clocks, and hypothesis state.
- Load never re-simulates unless explicitly requested.
