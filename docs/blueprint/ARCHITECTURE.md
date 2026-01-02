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

## Case generation layers
- Layer 1: Case skeleton (always present).
  - Who, victim, offender.
  - Where and when.
  - Method and access path.
  - Motive category.
  - 2-3 key timeline events.
- Layer 2: Modulators (small set per case).
  - Only traits that change decisions, evidence, or interpretation.
  - Phase 0 modulators: competence, risk_tolerance, relationship_distance.
- Layer 3: Color (late-bound).
  - Used for prose texture only unless promoted by a later phase.
  - Generated at write-time, not simulated deep.

## Truth graph topology
- Use a temporal MultiDiGraph for the canonical truth layer.
- Nodes: people, locations, items, events.
- Edge categories:
  - state relationship: start_time, end_time
  - transient action: timestamp, duration
  - spatial position: entry_time, exit_time
  - causal link: precondition_id
- Time is first-class. Queries slice windows for alibis and causality.

## Noisy channel projection
- Presentation is a projection of Truth through bounded noise.
- Erosion types:
  - temporal fuzzing (memory decay)
  - informational omission (missed or decayed evidence)
  - deception (explicit false edges)
- Deception is explicit. It never rewrites Truth.

## Nemesis mechanics
- Signature is a fixed post-processing ritual applied to crimes.
- MO is adaptive weighting, not opaque ML.
- Proficiency increases with use and reduces execution noise.
- Compromised methods reduce weight and push exploration.

## Showrunner archetypes
- Pressure: resource attrition with short timers and high visibility.
- Pattern: copy Nemesis MO without signature to create false positives.
- Character: center on high-affinity NPCs for narrative depth.
- Foreshadowing: failed or non-lethal events that hint at new MO.

## Deduction validation
- Player builds a hypothesis graph from evidence.
- Validation uses ontology mapping and soft matching for partial credit.
  - Example: STABBED matches ATTACKED_WITH_SHARP_OBJECT.

## UI presentation (Textual)
- Dashboard layout: header, map, board, wire.
- Rich renders artifacts (autopsy, case files, reports) as panels and tables.

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
