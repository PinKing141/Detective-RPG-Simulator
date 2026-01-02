# Rules

This is the design contract. If a feature conflicts with these rules, the feature loses.

## Core fantasy and goal
- You are a detective building cases under uncertainty in a city that reacts to your methods.
- Ultimate goal: conclude the nemesis arc in a way that holds up legally, socially, and morally.
- Victory is plural. Failure is still an ending.

## Do
- Design systems that interact, not isolated mechanics.
- Make failure playable and story-generating.
- Reuse people, places, and consequences.
- Keep prose short, observational, and grounded.
- Force trade-offs; never allow "do everything."

## Do not
- Do not simulate what the player cannot perceive.
- Do not rely on hidden dice for major outcomes.
- Do not add systems that do not change decisions.
- Do not front-load complexity in the first hour.

## Pitfalls to avoid
- Fully random cases with no underlying truth.
- Profiling that always gives the right answer.
- Nemesis escalation on a fixed schedule.
- Infinite side cases with no consequence.
- Long bespoke prose instead of modular text.
- Hard fail states that force reloads.
- Letting optimization erase role-play.

## Guardrails (avoid overreach)
- Use graphs for causality, timelines, and alibi checks only. Do not query them for every micro decision.
- Nemesis adaptation is heuristic weighting. Avoid opaque ML or heavy tuning.
- Showrunner selects which truths surface; it never invents urgent truths that do not exist.
- Profiling reframes; it never resolves or introduces facts.
- Lies are explicit false edges, never silent rewrites.
- Scale only after content atom proofs (witness lines, profiling paragraphs, recap stings).
- Religion, intelligence, and personality are color unless promoted to an active modulator.
- Intelligence is domain competence, not a generic IQ slider.

## Decision and trade-off rules
- Decision gate: you can name the player decision in one sentence.
- Trade-off gate: every use has a cost or locks out alternatives.
- Anti-optimization: no action is always correct; costs and uncertainty must limit it.
- Legibility: outcomes are explainable in-world.
- Failure creates new play, not a dead end.

## Nuance gating
Only simulate nuance if it changes at least one:
- Offender decisions.
- Evidence footprint.
- Investigation choices.
- Interpretation (plausible alternatives).

If it does not change any of those, it is flavor and must be generated cheaply.

## Trait activation limits
- Never let more than 4 traits drive mechanics in a single case.
- Everything else is late-bound color or future-phase material.

## Feature kill criteria (mid-phase)
Gate A - Decision gate (mandatory)
- If you cannot name the decision in one sentence, kill it.

Gate B - Trade-off gate (mandatory)
- If there is no meaningful cost, kill it.

Gate C - Phase fit gate
- Helps current phase: continue.
- Helps a later phase: defer.
- Helps no phase: kill.

Gate D - Behavioral proof gate
- Before building, write: "Players will do X differently because of this."
- If you cannot predict change, kill it.

Automatic kills (no debate)
- It increases internal accuracy without changing player behavior.
- It simulates unseen systems.
- It adds complexity without a new trade-off.
- It creates an always-do-this optimal action.
- It requires external explanation to be understood.

## Design review script
Opening
1) What phase are we in?
2) What is the single question of this phase?
3) What evidence shows we are answering it?

Feature review (repeat per feature)
A) One-sentence definition: what is it and what does the player do with it?
B) Decision and trade-off: which decision changes, what it costs, what it locks out?
C) Failure and fairness: how can it go wrong, and is it explainable?
D) Anti-optimization: can players spam it, and what stops that?

World and nemesis check
- If the player ignores this system, what changes?
- Who remembers it later?
- Does the nemesis react to method, not just progress?

Final kill question
- "If we removed this, would the game lose identity or just detail?"
If the answer is "detail," kill or defer.

Outcome
- Approved, postponed, or killed.

## What not to build
Hard no (never build)
- Full courtroom simulation.
- Open-world travel or driving.
- Perfect forensic realism.
- Hundreds of NPC schedules.
- Huge dialogue trees for everyone.
- Solve-by-guessing endgames.

Soft no (only if the game cannot function without it)
- Multiple nemeses at launch.
- More than 2 or 3 crime types early.
- Skill trees and perk optimization.
- Highly transparent numbers for hidden uncertainty systems.

Build these instead (cheap and high payoff)
- Courtroom sim -> thresholds (detain/arrest/charge/convict) plus DA friction.
- Open-world travel -> time costs, district pressure, and location access gating.
- Perfect forensics -> failure modes (contamination, backlog, partials).
- NPC schedules -> memory, callbacks, and changing cooperation.
- Dialogue trees -> modular statement atoms with tone modifiers.
- Guessing endgame -> case quality and contradiction checks with legible feedback.

## Core stopping rule
If the next change improves internal consistency but does not change player decision-making, stop.

## Institutional pressure terminology
Preferred term: Institutional pressure.

Replace legacy terms:
- Heat -> Pressure
- Heat limit -> Pressure tolerance
- Heat increase -> Pressure rises
- Heat penalty -> Pressure consequence
- High heat -> High scrutiny

UI and narrative phrasing examples:
- "Pressure: 3 / 8"
- "Pressure from command is increasing."
- "The department wants results."
- "You're being watched more closely now."

Hard rule:
Meters should describe social or institutional forces, not player guilt.
