# Roadmap

Rule: you do not advance phases until every checkbox is ticked.
Rule: once every checkbox is ticked, you must stop polishing and move on.

## Phase 0 - Foundation (Determinism and core plumbing)
Phase question: Can we generate one solvable case by seed, investigate it, and explain outcomes?

Scope
- Project plumbing (pyproject, config, deterministic RNG).
- Domain models and invariants.
- Truth graph wrapper and queries.
- Case truth generator (one homicide archetype).
- Case skeleton with active modulators (competence, risk_tolerance, relationship_distance).
- Presentation projector with bounded noise.
- Investigation actions and costs.
- Deduction board and arrest thresholds.
- Debug tools (truth dump).
- Content atom proofs (witness lines, profiling blurbs, recap stings).

Deliverables
- config.py with seed and debug flags.
- util/rng.py with a single RNG source.
- TruthState wrapper and query helpers.
- Case generator that produces a coherent timeline.
- Modulator-aware generator that changes evidence footprint.
- Projector that produces evidence with explainable uncertainty.
- Five investigation actions with time and pressure costs:
  - visit_scene, interview, request_cctv, submit_forensics, arrest.
- Text-only deduction board and validation rules with outcome summary.
- Explicit set_hypothesis step (suspect, claims, evidence) required before arrest.
- Dump script that prints truth, timeline, and alibis.
- Content atom pack that demonstrates scalable text variety.

Exit proof
- Same seed produces identical truth and evidence.
- A case can be investigated end-to-end.
- After any outcome, the game explains support and contradiction.
- Truth dump is readable and accurate.

Checklist
- [ ] Single RNG source is used everywhere.
- [ ] TruthState supports add_person, add_location, record_event, and possession.
- [ ] Queries can answer alibi-style questions consistently.
- [ ] Evidence items include source, time collected, and confidence band.
- [ ] Case modulators are limited to three drivers in Phase 0.
- [ ] Investigation actions apply time and pressure costs.
- [ ] Arrest validation returns a legible explanation.
- [ ] Hypothesis submission is explicit and required before arrest.
- [ ] Truth dump exists and reproduces by seed.
- [ ] Content atom proof exists (50 witness lines, 30 profiling lines, 20 recap stings).

Stop condition: If all boxes are ticked, Phase 0 is complete even if UI and prose are ugly.

## Phase 0 closure confirmation
Phase 0 design question:
"Is the game fair, legible, and playable as a reasoning loop?"

Phase 0 is complete when:
- Determinism holds (same seed yields same truth and evidence).
- Truth exists independently, presentation is derived and explainable.
- Actions consume time and pressure, forcing tradeoffs.
- Player commits a hypothesis (suspect, claims, evidence).
- Hypothesis is visible at all times and arrest validates it.
- Outcomes explain support and missing elements in-world.
- Players can revise, gamble, be wrong, and continue.

Phase 0 hard stop rule:
- If the next change improves internal elegance but not player decisions, stop.

Do not add after Phase 0:
- New mechanics (motives, profiling synthesis, playstyle traits, nemesis reactions, memory across cases, relationship systems).
- UI expansion (murder board, visual graphs, maps, multi-panel dashboards).
- Extra evidence types, realism passes, or tuning for feel.

Phase 0.5 - Textual wrapper (presentation only)
- Single screen only. Use a scrollable log and a scrollable detail pane.
- UI reads state and dispatches actions. No logic in widgets.
- Any text that can exceed 5 lines must be scrollable.
- CLI loop must remain playable if Textual breaks.
- Stop when a player can finish a case comfortably for an hour.

## Phase 1 - Vertical Slice
Phase question: Is the core loop fun, fair, and legible?

Design rule:
- Probable cause is composition-based. Testimonial-only mixes never yield a clean arrest.
  Temporal coherence upgrades confidence only when anchored by non-testimonial evidence
  (physical in Phase 1).

Core loop proof
- [ ] A complete case can be generated from a single hidden Truth state.
- [ ] Evidence is derived from Truth (not spawned as clues first).
- [ ] The player can solve without brute-forcing every action.
- [ ] The player can be wrong and the game continues.

Behavior proof
- [ ] Players prioritize (they choose what not to do).
- [ ] Players hesitate before arresting or accusing.
- [ ] Two competent players can take different paths to a result.
- [ ] There is no "interview everyone / test everything" dominant route.

Failure proof
- [ ] Wrong arrest produces playable consequences (trust, time, politics, nemesis response).
- [ ] Missed lead escalates tension via an explainable clock.
- [ ] Inaction has visible consequences.
- [ ] Fail states create new play, not a dead end.

Legibility proof
- [ ] After any outcome, the game can explain why in-world ("because X, therefore Y").
- [ ] No outcome relies on "the system decided."
- [ ] Players can state what they missed, not just that they lost.

Stop condition: If all boxes are ticked, Phase 1 is complete even if UI and prose are ugly.

## Phase 2 - System Expansion
Phase question: Do systems meaningfully interact without convergence?

Interaction proof
- [x] Profiling changes priorities and hypotheses, not certainty.
- [x] Time pressure invalidates some actions (real trade-offs).
- [x] Evidence reliability produces meaningful doubt and alternative interpretations.
- [x] Systems constrain each other (choices exclude other choices).

Anti-optimization proof
- [x] Interviewing everyone creates a cost (time, pressure, cooperation).
- [x] Running every test is impossible (resource gates).
- [x] Aggressive play causes downstream problems (trust, legal thresholds, nemesis adaptation).
- [x] Cautious play causes different downstream problems (time loss, escalation elsewhere).

Divergence proof
- [x] Cautious vs aggressive detectives diverge in outcomes.
- [x] Empathy vs intimidation diverge in outcomes.
- [x] The nemesis reacts to style, not just progress.

Stop condition: If all boxes are ticked, stop. Roughness is allowed.

## Phase 3 - Living World
Phase question: Does the world remember and react?

Memory proof
- [ ] Named NPCs reference past actions accurately.
- [ ] Locations accrue reputation and it matters.
- [ ] Mistakes resurface later with consequences.
- [ ] Old cases echo into new ones.

Autonomy proof
- [ ] Events occur without the player (clocks advance).
- [ ] Ignored problems escalate or mutate.
- [ ] The nemesis adapts to pressure.
- [ ] The city feels different after 10+ hours.

Perception proof
- [ ] Players notice change without being told explicitly.
- [ ] World descriptions shift meaningfully (tone and practical effect).
- [ ] The world does not reset emotionally between cases.

Stop condition: Do not add background simulation. Memory beats simulation.

## Phase 4 - Campaign and Endings
Phase question: Do conclusions feel earned, varied, and behavior-reflective?

Ending coverage
- [ ] Multiple valid endings exist (not one correct win).
- [ ] Early endings feel complete, not abrupt.
- [ ] Failure endings remain story-complete and playable to credits.
- [ ] Success is not binary (prove/contain/stop vs convict/close).

Identity reflection
- [ ] Ending text reflects methods (by-the-book vs rogue, empathy vs coercion, early arrests vs case-building).
- [ ] The game can answer: "what kind of detective were you?"
- [ ] Two successful runs can produce different epilogues.

Stop condition: Ambiguity is allowed. Total explanation is not required.

## Phase 5 - Polish
Phase question: Is the experience clear, readable, and confident?

Clarity proof
- [ ] Players can state what matters right now.
- [ ] Text is scannable (headings, timestamps, source lines).
- [ ] Recaps orient without repeating everything.
- [ ] Every mechanic is learnable through play.

Restraint proof
- [ ] No new systems are introduced.
- [ ] No realism-only features are introduced.
- [ ] Every polish change improves comprehension or pacing.

Stop condition: When polish stops improving comprehension, stop entirely.
