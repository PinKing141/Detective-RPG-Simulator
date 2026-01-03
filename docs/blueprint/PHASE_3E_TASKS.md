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

Layer C - Exposure (campaign pacing, minimal)
- Exposure rises with visibility, failures, and loud actions.
- Exposure influences escalation and taunting, not truth.
- Exposure is separate from department Pressure.

## Constraints (non-negotiable)
- No DIM or player counterplay traits yet.
- No endgame operations or warrants.
- No additional crime types required.
- Only one persistent offender can adapt at a time.

## Deliverables
- Nemesis profile stored in world persistence.
- Exposure meter tracked per case.
- Simple adaptation applied to the next nemesis case.
- One escalation outcome tied to exposure level.

## Exit checklist
- [ ] Nemesis persists across at least 3 cases.
- [ ] One method changes due to being compromised.
- [ ] Exposure affects visibility or taunting.
- [ ] Nemesis does not dominate all cases.

Stop condition:
If the offender feels persistent without taking over the game, stop.
