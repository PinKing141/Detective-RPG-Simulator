# Phase 3 - Living World and Memory (Design Contract)

## Phase 3 Design Question (Singular, Non-Negotiable)

Does the world remember what the player did and react in ways that feel consistent over time?

If Phase 1 proved reasoning under uncertainty,
and Phase 2 proved systems interacting without convergence,
then Phase 3 proves continuity.

Not realism. Not scale. Not simulation. Continuity.

## What Phase 3 Is Actually For

Phase 3 exists to answer one emotional question:
"Did that matter?"

If the answer is yes, the world feels alive even if it is small.

## What Phase 3 Is Not

- Open world
- City simulator
- NPC daily schedules
- Deep social graphs
- Nemesis endgame
- Long narrative prose
- Emergent storytelling for its own sake

If you add any of these, you have skipped ahead and broken the roadmap.

## The Three Pillars of Phase 3

Phase 3 consists of exactly three systems. If you add more, you are overbuilding.

### 1) Persistent World State (Memory, Not Simulation)

Purpose: ensure the world does not reset emotionally or structurally between cases.

Persist aggregates only:
- trust_level (already exists as trust in InvestigationState)
- pressure_level (already exists as pressure in InvestigationState)
- district_status (calm / tense / volatile)
- location_status (calm / tense / volatile)
- nemesis_activity (heat or activity level, no adaptation yet)

No individual NPC memory yet.
No long histories.
No event chains.

What this enables:
- cases start differently based on previous outcomes
- the same action has different consequences later
- early mistakes echo forward

### 2) Event Autonomy (Things Happen Without You)

Purpose: break the feeling that the world waits for player input.

Rule: events may occur without player action, but never without explanation.

Phase 3-safe autonomous events:
- a new crime occurs while you wait on results
- a witness becomes unavailable
- media attention spikes
- a lead goes cold
- the nemesis acts again (no adaptation yet)

Not allowed:
- random disasters
- surprise punishment
- untelegraphed failures

Autonomy must feel inevitable, not arbitrary.

### 3) Narrative Continuity (Callbacks, Not Cutscenes)

Purpose: make the world feel cohesive without writing a novel.

Continuity looks like:
- descriptions change
- tone shifts
- references recur
- names and places resurface

Not allowed:
- long dialogues
- backstory dumps
- cinematic scenes

Example:
"The station is quiet." becomes
"The station is tense. Phones ring constantly. No one meets your eye."

## Phase 3 Tasks (Concrete, Minimal)

### Task 1 - World State Container

Add a persistent structure that lives across cases.

Suggested fields:
- trust_level (reuse existing trust)
- pressure_level (reuse existing pressure)
- district_status
- nemesis_activity

Rules:
- values carry across cases
- values modify starting conditions
- values never decide outcomes directly

### Task 1b - Naming Policy (Phase 3, Scoped)

Purpose: keep casts readable, non-repetitive, and deterministic while using the
existing names database (gender + country fields). This is a generator with
constraints, not a random picker.

Rules (implemented):
- Default format: First Last.
- Uniqueness: no duplicate full names within a case.
- Avoid repeating first names within a case; avoid visually similar first names.
- Use a per-case country mix (primary + secondary), then sample names from it.
- Forenames can be filtered by gender if known; otherwise treat gender as unknown.
- Prefer neutral surnames; fall back to any surname when needed.
- Apply recent-use penalties across cases (avoid repeating first/last names in
  a rolling window).
- Deterministic draws per seed (stable RNG use).

Rules (deferred):
- Tone tags (grounded/stylised/archaic) are not in the DB yet.
- Role-based naming bias is not applied until tone tags exist.
- Person return continuity requires a people_index table (Phase 3+ extension).

### Task 1c - Identity Hooks (Phase 3, Scoped)

Purpose: store optional identity hooks for continuity and access context only.

Fields (nullable):
- country_of_origin
- religion_affiliation
- religion_observance
- community_connectedness

Rules:
- These do not infer guilt or profile outcomes.
- These influence access/cooperation context only.
- Use in text as neutral constraints, not conclusions.

### Task 2 - Case Start Modifiers

Each new case reads from world state:
- lower trust -> fewer cooperative witnesses (reduce cooperation, weaker testimonial confidence)
- higher pressure -> shorter lead deadlines
- volatile district -> faster escalation notes

No new UI screens.
Just different starting conditions and clearer consequences.

### Task 3 - Autonomous Event Scheduler

Add a lightweight scheduler that can trigger:
- "While you were doing X, Y happened."

Rules:
- triggered by time, not randomness alone
- explained in-world
- logged for post-hoc clarity

### Task 4 - World-Referencing Text Hooks

Update existing text output to reference state:
- case briefings
- action results
- profiling summaries
- outcome summaries

This is mostly language, not logic.
Reuse UI language rules and profiling summary pack.
Case briefing may include a single neutral line when a returning NPC is present
("A familiar name is attached to the file.").

## What Phase 3 Still Does Not Add

- nemesis learning or strategy changes
- persistent NPC emotional states
- player home life
- moral meters
- complex social simulation

If you feel tempted, you are thinking about Phase 4 or 5.

## Phase 3 Exit Criteria (Literal Checklist)

Memory:
- past cases change future case conditions
- world does not reset emotionally
- player notices continuity without being told

Autonomy:
- events occur without player input
- player cannot pause the world indefinitely
- every autonomous event is explainable

Coherence:
- callbacks feel intentional, not random
- descriptions reflect accumulated pressure
- the city feels different after time passes

Restraint:
- no new systems added beyond the three pillars
- no realism-only features added
- no narrative bloat

If all boxes are checked, stop immediately.

## Common Phase 3 Failure Modes

- adding more NPCs instead of more memory
- adding schedules instead of consequences
- adding drama instead of continuity
- adding lore instead of reaction

If you catch yourself writing backstory, stop.

## How Phase 3 Sets Up Phase 4 (Without Doing It)

Phase 3 does not conclude the story.
It ensures the ending is earned.

By Phase 4:
- the player already feels watched by the world
- consequences already echo
- the nemesis already feels present

Phase 4 resolves what Phase 3 made meaningful.

## Final Truth

A living world is not built by simulating life.
It is built by remembering consequences.
