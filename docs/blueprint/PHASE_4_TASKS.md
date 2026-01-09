# Phase 4 - Campaign and Endings (Design Contract)
Roadmap summary: docs/blueprint/ROADMAP.md

Phase 4 design question:
What kind of detective was the player in this world, and what did that cost?

Phase 4 is not:
- a plot dump
- a lore reveal
- a nemesis boss fight
- a true ending hunt

Phase 4 only reads systems. It does not add new mechanics.

Prerequisites:
- Phase 3C establishes episode titles + recap framing (Phase 4 uses it; no new UI panels).
- Phase 3D establishes signature patterns and a tracker.
- Phase 3E establishes a persistent offender with light adaptation + nemesis_exposure.
- Phase 3F establishes multi-site cases and location visits (Phase 4 schedules, not invents).
- Phase 3G establishes the Unsub profile board (Phase 4 consumes it for closing-in).
- Phase 3H establishes analyst tools (Rossmo-lite + tech sweep) as inputs, not new systems.

Nemesis scope rules:
- Exactly one adaptive Nemesis at a time.
- Up to two non-adaptive serial offenders may run concurrently as noise.
- Copycats appear only after the Nemesis has been seen twice.
- A new Nemesis replaces the old one only after capture, death, disappearance,
  or a lost trail.

## 1) What Phase 4 is allowed to add

### A) Endings (plural, non-hierarchical)
- Multiple valid endings.
- No good/bad or true/false hierarchy.
- Endings are coherent outcomes of behavior.

Examples:
- Cases solved, trust eroded.
- Few arrests, high legitimacy.
- Nemesis caught, city destabilized.
- Nemesis never caught, harm contained.

### B) Early endings (critical)
Early conclusions are allowed and must feel complete.

Triggers can include:
- Trust collapse
- Excessive pressure
- Persistent nemesis disengagement
- Ethical withdrawal (refusing risky arrests)

Rule: early endings are full epilogues, not failure screens.

### C) Behavioral aggregation (not stats)
Phase 4 synthesizes patterns from:
- arrest timing
- escalation tolerance
- pressure vs patience
- accuracy and reversals
- omission patterns
- nemesis interaction frequency

No new mechanics. No new meters shown to the player.

### D) Nemesis resolution
Capture, exposure, disappearance, retirement, unresolved pursuit are all valid.
The nemesis never defines the ending. The player's approach does.

## 2) What Phase 4 must not add
- New investigation mechanics
- New profiling logic
- Late-game difficulty spikes
- Moral judgment labels

## 3) Phase 4 deliverables (artifacts you should point to)
- Campaign state model (season progress, pressure, trust, nemesis_exposure, closing-in counters).
- Case queue and pacing rules (tension wave, multi-site scheduling).
- Nemesis arc controller (closing-in logic fed by 3G/3H outputs).
- Detective identity metrics (DIM) and counterplay rules.
- Endings system (early + final endings).
- Epilogue generator (identity-based summary).
- Save/load includes campaign + ending flags.

## Phase 4 fairness rules (anti-cheat)
- Capture requires both pattern confidence and operational readiness; no hidden thresholds.
- Misses are explained in-world and tied to player choices (warrant denial, raid burn).
- Every miss yields concrete progression (new constraint, motif detail, narrowed zone).
- Same inputs must produce the same outcomes (determinism over drama).

## 4) Ending taxonomy (behavioral axes, not scores)

Core principle:
Endings describe behavior under pressure, not judgments.

Four axes (do not add more):
- Certainty vs restraint (early arrest vs delayed action).
- Institutional trust (legitimacy preserved vs burned).
- Harm containment (contain without closure vs accept escalation).
- Nemesis orientation (pursuit-focused vs containment-focused).

Ending clusters (descriptive, not rigid classes):
- Containment detective.
- Results detective.
- Process detective.
- Hunter.
- Fracture (inconsistent approach).

## 5) Early ending triggers (complete-feeling conclusions)

Valid triggers (use 3 to 4 total):
- Institutional breakdown (trust collapses, access restricted).
- Public crisis saturation (pressure spikes, confidence lost).
- Nemesis disengagement (pursuit abandoned).
- Ethical withdrawal (restraint repeated, risk refused).

Rule: early endings are full epilogues, never "game over."

## 6) Campaign structure (the season spine)

Core variables (minimal):
- episode_index or season_day
- case_queue (active + upcoming)
- pressure
- trust
- clearance_rate (optional)
- nemesis_exposure (reuse Phase 3E; do not add a duplicate meter)
- closing_in counters (pattern, narrowing, proof)

Pacing rule:
Maintain a tension wave (spike, relief, spike, endgame).
After major failure, schedule cooldown cases. After easy wins, raise stakes.

## 7) Nemesis arc resolution (endgame loop)

Closing-in requirements (three distinct types):
- Pattern confidence (signature recognition strength).
- Narrowing (suspect space, zones, victim type, access).
- Proof threshold (actionable without coin-flip).

Rule: these are fed by Phase 3G/3H outputs. Phase 4 must not introduce new profiling logic.

Endgame trigger:
Unlock one operation style for v1 (pick one):
- surveillance
- bait
- warrant
- raid

## 8) Detective identity metrics (DIM) and counterplay

DIM counters (counts and thresholds, not continuous stats):
- Coercive: intimidation, forced entry, early arrest
- Analytical: forensics, timeline analysis, corroboration
- Social: rapport interviews, witness networks, soft pressure
- Risky: acting before probable cause, skipping corroboration

Rules:
- A style becomes dominant only after 2 to 3 cases.
- Nemesis counterplay triggers only when dominance is stable.
- Counterplay examples: aggression feeder, forensic countermeasures.

## 9) Endgame operations framework (stakeout, warrant, bait, raid)

Unifying rule:
Do not build four mini-games. Each operation is a wrapper around the same core pipeline:
1) Trigger condition
2) Plan (commitment)
3) Execute (time passes, risk resolved)
4) Outcome (clean/partial/fail)
5) Fallout (pressure, trust, nemesis spook, legal risk)

Core engine components (one system):
- OperationPlan
- OperationResolver
- OperationOutcome
- FalloutApplier

Operation types (all share the same pipeline):

### Warrant (legal gateway)
Purpose: converts suspicion into legal power. Unlocks search/raid/surveillance.

Warrant types (v1):
- Search warrant (property)
- Arrest warrant (person)
- Digital records warrant
- Surveillance authorization

Requirements (Phase 4):
- At least 2 corroborating supports, with:
  - at least 1 non-testimonial support, or
  - 2 independent testimonial sources plus a coherent timeline

Outcomes:
- Granted
- Granted with limits (scope or time window)
- Denied (fallout: pressure up, trust down, suspect spooks)

### Stakeout (narrowing routine)
Availability:
- Narrowed location or likely next move
- Pattern confidence or reliable lead

Plan options:
- Location
- Duration (short/medium/long)
- Style (covert or assertive)
- Objective (observe, tag, intercept)

Outcomes:
- Breakthrough (unlocks warrant/raid)
- Partial (confirms presence, no proof)
- Burn (spooked, nemesis relocates/escalates)

### Bait (force contact)
Availability:
- Strong pattern confidence
- Predicted targeting rule
- Surveillance or rapid response readiness

Plan options:
- Bait type (decoy person, staged scene item, info leak)
- Safety posture (safe or risky)
- Publicity (quiet or loud)

Outcomes:
- Contact
- Near miss (learn something, no capture)
- Backfire (copycat or collateral; heavy fallout)

### Raid (endgame resolution)
Raid types:
- Search-first (secure, collect, arrest if present)
- Arrest-first (higher risk if wrong)

Preconditions:
- Search-first requires search warrant
- Arrest-first requires arrest warrant or rare exigency

Plan options:
- Entry plan (front/rear/simultaneous)
- Force posture (soft/hard)
- Objective priority (evidence/capture/safety)

Outcomes:
- Clean win (arrest + strong evidence)
- Partial (arrest + weak evidence)
- Wrong target (trust collapse, pressure spike, nemesis adapts)
- Escape (close call, higher future risk)

Endgame ladder (expected flow):
- Stakeout -> Warrant -> Raid
- Bait -> Raid
At least two viable routes must exist.

Endgame support systems (lightweight):
- Suspect spook state (rises with pressure and loud ops; cools with quiet time)
- Trial risk tier (weak/shaky/solid, no courtroom sim)
- Fallout memory flags (wrong raid, warrant denied, bait backfired)

Persistence hooks (minimal SQL fields to add to world storage):
- operations: operation_id, case_id, op_type, target_person_id, target_location_id,
  plan_json, result, started_time, ended_time, fallout_json
- warrants: warrant_id, case_id, warrant_type, target_person_id, target_location_id,
  status, scope_json, support_snapshot_json, issued_time

## 10) Crime type expansion (optional, controlled)
If adding new crime types in Phase 4, they must reuse at least 70 percent of:
- evidence classes
- action set
- validation logic

Use families, not bespoke systems:
- Person crimes: homicide, abduction, stalking
- Property crimes: arson, burglary, vandalism
- Financial/digital: fraud, extortion, identity theft
- Organized/complex: trafficking, corruption, pattern cluster

Only truth generator and projector templates change. No new evidence classes.

## 11) Ending engine (how it should work)

Step 1: Collect behavioral signals
- arrest timing
- evidence thresholds
- pressure trajectory
- trust trajectory
- wrong-arrest rate
- omission patterns
- nemesis interaction frequency

Step 2: Cluster behavior (tendencies, not stats)
Example clusters:
- Containment-focused
- Results-driven
- Process-faithful
- Risk-acceptant
- Public-facing
- Shadow operator
- Fracture (inconsistent)

Step 3: Generate a world state summary
Describe:
- the city
- institutions
- public trust
- crime patterns
- recurring people

Step 4: Write the epilogue (procedural, restrained)
Tone rules:
- observational, not judgmental
- reflective, not congratulatory
- concrete, not abstract
- slightly ambiguous

Template:
1) World state
2) Player pattern
3) Cost
4) Nemesis reflection (optional)
5) Closing line

## 12) Phase 4 ordered task list
- [x] 1) CampaignState model (season progress, pressure/trust, nemesis flags).
- [x] 2) Case queue and pacing (tension wave scheduling).
- [x] 3) Nemesis closing-in progress (pattern, narrowing, proof).
- [x] 4) DIM counters and nemesis counterplay traits.
- [x] 5) Operations framework (warrant, stakeout, bait, raid).
- [x] 6) Endgame operation (pick one style first, add others as wrappers).
- [x] 7) Ending triggers + epilogue generator (early + final).
- [x] 8) Save/load covers campaign + ending state.
- [ ] 9) Optional crime family expansion (if needed).

## 13) Phase 4 exit checklist (hard gate)
- [x] Same seed yields different endings for different playstyles.
- [x] Early endings feel intentional and complete.
- [x] Endings describe behavior, not correctness.
- [x] No new mechanics were added.
- [x] Players can disagree about whether they won.
- [x] A run has a clear beginning, escalation, and endgame.
- [x] Uses Phase 3C framing without expansion.
- [x] Any ending can be explained in-world without code references.

Final rule:
Phase 4 is about recognition, not answers.
If a player reads the ending and thinks "Yes. That was how I played," it worked.
