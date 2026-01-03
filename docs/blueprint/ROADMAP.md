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

Phase 2 guardrails (identity and language)
- Profiling language may reference community-linked cooperation as a lens only.
- No protected-attribute inference (country, religion, gender) in profiling.
- No demographic "likely offender" outputs. Identity remains a contextual hook only.

## Phase 3 - Living World
Phase question: Does the world remember and react?

Phase 3 naming policy (generator rules)
- Default display format: First Last. Official format: LAST, First.
- Short reference style is consistent (choose one: First or Detective Last).
- Uniqueness: no duplicate full names within a case.
- Avoid repeating first names within a case unless intentionally related.
- Use per-case country distribution (primary + secondary), then sample within it.
- Forename can be gender-filtered when known; surname defaults to neutral.
- Apply recent-use penalties across cases (rolling windows for first/last names).
- Deterministic draws per seed (stable RNG order).
- Name hygiene: remove or quarantine famous names, joke names, slur-adjacent
  strings, hard-to-render characters, and tone-breaking fantasy names.

Identity hooks (Phase 3 scope)
- Country and religion are stored as optional hooks, not deterministic traits.
- These hooks affect access, schedules, and cooperation, not guilt.
- No profiling outputs that infer criminality from identity.

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
Full spec: docs/blueprint/PHASE_4_TASKS.md

Phase 4 is about campaign closure and identity reflection. It reads existing systems.
It does not add new investigation mechanics or late-game difficulty spikes.

Phase 4 identity use (safe scope)
- Country/religion can add narrative texture and social stakes.
- Community relationships can carry forward as cooperation modifiers.
- Still no guilt inference from identity; these are context only.

Phase 4 deliverables (artifacts)
- Campaign state model (season progress, pressure/trust, arc flags).
- Case queue and pacing rules (tension wave).
- Nemesis arc controller (closing-in logic).
- Endings system (early + final endings).
- Epilogue generator (identity-based summary).
- Episode framing (titles, cold opens, end tags, "Previously on...").
- Save/load includes campaign and ending flags.

Phase 4 systems (what to build)
1) Campaign structure
   - Variables: episode_index, case_queue, pressure, trust, clearance_rate (optional),
     nemesis_progress, nemesis_risk.
   - Pacing rule: spike, relief, spike, endgame (no invented drama).
2) Nemesis arc resolution
   - Closing-in requirements: pattern confidence, narrowing, proof threshold.
   - Endgame operation: pick one (surveillance, bait, warrant, raid).
3) Endings
   - Early endings: trust collapse, pressure saturation, nemesis disengagement,
     ethical withdrawal. Must feel complete.
   - Final endings: nemesis outcome + city outcome + detective identity.
4) Detective identity synthesis
   - Behavior signals: arrest timing, evidence reliance, pressure tolerance,
     trust trajectory, coercive vs empathetic approaches.
5) TV framing
   - Episode title, cold open, end tag.
   - "Previously on..." recap from last 3 to 6 events.
6) Endgame operations framework (single pipeline)
   - Unified flow: trigger -> plan -> execute -> outcome -> fallout.
   - Operation wrappers: warrant, stakeout, bait, raid.
   - No mini-games; all ops share one resolver and fallout model.
7) Warrant requirements
   - At least 2 corroborating supports with:
     - 1 non-testimonial support, or
     - 2 independent testimonial sources plus coherent timeline.
8) Endgame ladder
   - Stakeout -> Warrant -> Raid
   - Bait -> Raid
   - At least two viable routes to closure.
9) Minimal persistence for operations (Phase 4 storage)
   - operations table: op_type, target, plan, result, fallout, time.
   - warrants table: type, target, status, scope, support snapshot.
10) Optional crime variety (controlled expansion)
   - Use 4 families (person, property, financial, organized).
   - Reuse at least 70 percent of evidence, actions, and validation.
   - Only generator/projector templates change. No new evidence classes.

Phase 4 ordered task list
1. CampaignState model (season progress, pressure/trust, nemesis flags).
2. Case queue and pacing (tension wave scheduling).
3. Nemesis closing-in progress (pattern, narrowing, proof).
4. Operations framework (warrant, stakeout, bait, raid).
5. Endgame operation (pick one style first, then add wrappers).
6. Ending triggers + epilogue generator (early + final).
7. TV framing (titles, recaps, end tags).
8. Save/load covers campaign + ending state.
9. Optional crime family expansion (if needed).

Phase 4 exit checklist (hard gate)
Campaign completeness
- [ ] A run has a clear beginning, escalation, and endgame.
- [ ] Pressure/trust curves feel like a season, not random spikes.
Nemesis resolution
- [ ] Player can reach an endgame state by skill, not luck.
- [ ] Nemesis can be caught, lost, or forced underground with legible causes.
Endings
- [ ] At least 3 distinct final endings exist.
- [ ] At least 2 early endings exist and feel complete.
- [ ] Endings reflect player method, not correctness.
TV feel
- [ ] Each case has a title + short intro + short outro.
- [ ] "Previously on..." recap uses logged events and is readable.
Legibility
- [ ] For any ending, the player can explain why it happened in-world.

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
