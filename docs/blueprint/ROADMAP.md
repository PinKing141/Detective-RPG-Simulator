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
- Presentation projector with bounded noise.
- Investigation actions and costs.
- Deduction board and arrest thresholds.
- Debug tools (truth dump).

Deliverables
- config.py with seed and debug flags.
- util/rng.py with a single RNG source.
- TruthState wrapper and query helpers.
- Case generator that produces a coherent timeline.
- Projector that produces evidence with explainable uncertainty.
- Five investigation actions with time and heat costs.
- Text-only deduction board and validation rules.
- Dump script that prints truth, timeline, and alibis.

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
- [ ] Investigation actions apply time and heat costs.
- [ ] Arrest validation returns a legible explanation.
- [ ] Truth dump exists and reproduces by seed.

Stop condition: If all boxes are ticked, Phase 0 is complete even if UI and prose are ugly.

## Phase 1 - Vertical Slice
Phase question: Is the core loop fun, fair, and legible?

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
- [ ] Profiling changes priorities and hypotheses, not certainty.
- [ ] Time pressure invalidates some actions (real trade-offs).
- [ ] Evidence reliability produces meaningful doubt and alternative interpretations.
- [ ] Systems constrain each other (choices exclude other choices).

Anti-optimization proof
- [ ] Interviewing everyone creates a cost (time, heat, cooperation).
- [ ] Running every test is impossible (resource gates).
- [ ] Aggressive play causes downstream problems (trust, legal thresholds, nemesis adaptation).
- [ ] Cautious play causes different downstream problems (time loss, escalation elsewhere).

Divergence proof
- [ ] Cautious vs aggressive detectives diverge in outcomes.
- [ ] Empathy vs intimidation diverge in outcomes.
- [ ] The nemesis reacts to style, not just progress.

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
