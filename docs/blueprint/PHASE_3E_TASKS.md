# Phase 3E - Persistent Offender (Light Nemesis Memory)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3e---persistent-offender-light-nemesis-memory

Phase question:
Does a single offender persist across cases with minimal adaptation?

Phase 3E is not:
- a full nemesis arc
- endgame operations
- detective identity counterplay
- multiple adaptive offenders

## Scope (allowed)
- One persistent nemesis profile between cases.
- Simple adaptation: avoid the last compromised method.
- Escalation rule: if not caught, next crime is higher visibility.
- Track Nemesis Exposure separately from department Pressure.
- Typology priors (Visionary/Mission/Hedonistic/Power) as selection bias.
- MO vector (approach/control/method/cleanup/exit) with weights and competence.

## Layered design (Phase 3E)
Layer A - Identity (fixed)
- Signature motif (token + staging + message).
- Victimology bias (risk level, occupation cluster, location cluster).
- Comfort zone (district tags).
- Escalation trait (trophy, taunt, body movement).

Layer B - Operations (lightweight)
- MO components with preference weight and competence.
- If a component yields strong evidence: mark as hot, reduce weight next time.
- Low-competence use produces more noise and evidence.
- Leave 1 to 2 deliberate weaknesses to keep the pattern learnable.
- Adaptation cooldown: a compromised component can be deprioritised only once per cooldown window (N=2 cases). During cooldown it may still appear with degraded execution.
- Failure echoes: mistakes change tone or taunting style only, never success odds or method effectiveness.

Layer C - Exposure (campaign pacing, minimal)
- Exposure rises with visibility, failures, and loud actions.
- Exposure influences escalation and taunting, not truth.
- Exposure is separate from department Pressure.
- Exposure regression: low-visibility success can reduce exposure slowly, but never below the previous baseline.
- Escalation ceiling: visibility can rise only to pre-catastrophic tiers in Phase 3E (no Phase 4 spectacle).

## Constraints (non-negotiable)
- No DIM or player counterplay traits yet.
- No endgame operations or warrants.
- No additional crime types required.
- Only one persistent offender can adapt at a time.
- No internal or UI certainty flags (cap at "likely same actor" only).
- Background serial offenders may persist 2 to 3 cases but must terminate before becoming pattern-dominant.

This phase cannot answer:
- Who the nemesis is.
- Why they kill.
- Whether escalation is deliberate.
- Whether the player is winning or losing.

## Deliverables
- Nemesis profile stored in world persistence.
- Exposure meter tracked per case.
- Simple adaptation applied to the next nemesis case.
- One escalation outcome tied to exposure level.
- Adaptation cooldown enforced.
- Failure echoes visible in tone only.
- Exposure regression implemented.
## Current implementation gaps (code audit)
Last updated: 2026-01-08
- Persistent nemesis profile stored between cases (identity packet + MO vector) is not implemented.
- Adaptation cooldown, exposure regression, and escalation cap are not implemented.
- Exposure meter is not tracked separately from department Pressure.
  - Code refs: src/noir/world/state.py, src/noir/nemesis/*

## Exit checklist
- [ ] Nemesis persists across at least 3 cases.
- [ ] One method changes due to being compromised.
- [ ] Exposure affects visibility or taunting.
- [ ] Nemesis does not dominate all cases.
- [ ] Adaptation respects cooldown windows.
- [ ] Escalation never exceeds the Phase 3 ceiling.
- [ ] Exposure can regress under low-visibility outcomes.
- [ ] Nemesis memory affects tone, not competence.
- [ ] No internal or UI certainty flags exist.

Stop condition:
If the offender feels persistent without taking over the game, stop.
