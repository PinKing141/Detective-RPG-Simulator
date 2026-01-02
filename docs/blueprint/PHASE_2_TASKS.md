# Phase 2 - System Interaction and Divergence

Short answer first: yes, this draft is solid and correctly scoped.
This document is the locked Phase 2 execution plan with the three necessary gaps closed.

## 1) Validation: What Is Already Correct

- Phase goal is correct: systems interact, no dominant path, no certainty collapse.
- Constraints are correct: no new truth facts, no accuracy boosts, no new evidence classes, no nemesis or world memory.
- Ordering is correct: interpretive systems before pressure systems.
- Test philosophy is correct: same seed, different paths, different outcomes beyond speed.

## 2) The Three Gaps That Must Be Closed

### Gap 1 - No explicit inference pressure control
Failure mode: players feel that waiting always increases certainty.

### Gap 2 - No rule for conflicting evidence
Failure mode: contradictions get resolved implicitly by code and feel arbitrary.

### Gap 3 - No hard Phase 2 exit proof
Failure mode: endless tuning and accidental scope drift.

## 3) Minimal Additions (Phase 2 Safe)

### Addition 1 - Inference pressure rule
Purpose: prevent certainty collapse without randomness.

Rule:
- Inference pressure increases as evidence accumulates without corroboration.

Practical effect:
- Adding more of the same class does not improve confidence.
- Mixed reliability can stall or destabilize a hypothesis.
- Waiting longer can make decisions harder, not easier.

Implementation (minimal):
- Track evidence diversity, not quantity.
- Penalize confidence when evidence overlaps the same claim or failure mode.
- No UI meter; reflect only in outcome summaries.

### Addition 2 - Explicit conflict handling
Rule:
- Conflicting evidence never cancels out; it increases interpretive risk.

Effect:
- Hypothesis remains viable.
- Arrest outcome degrades due to instability.

### Addition 3 - Phase 2 exit criteria
Phase 2 is complete when all four are true:
1) Two different playstyles on the same seed produce different trust/pressure states and lead availability.
2) Waiting longer can make outcomes worse.
3) More evidence does not always increase confidence.
4) Players report hesitation even with "enough" evidence.

If all four are true, stop immediately.

## 4) Final Phase 2 Task List (Locked)

### Task 1 - Profiling as a lens (not certainty)
Add a lightweight profiling summary view.

Output:
- Focus shifts only (examples: "interviews higher value", "avoid escalation").

Language pack:
- Use docs/blueprint/PROFILING_SUMMARY_LANGUAGE.md as the Tier 2 and Tier 3 output guide.

Constraints:
- No new truth facts.
- No accuracy boosts.
- No resolving claims.

Success condition:
- Profiling changes what players try, not what is true.

### Task 2 - Evidence reliability as doubt
Introduce reliability effects that change support strength, not data.

Rules:
- Weak testimonial alone yields shaky outcomes.
- Mixed reliability increases instability.
- Repeated same-class evidence has diminishing impact.

Constraints:
- No numeric meters.
- No explicit probabilities.

### Task 3 - Inference pressure (new)
Add inference pressure based on evidence diversity.

Rules:
- More of the same does not improve certainty.
- Conflicting evidence increases risk.
- Waiting can destabilize hypotheses.

Constraints:
- No new UI elements.
- Reflected only in outcome explanations.

### Task 4 - Action tradeoffs that force omission
Make exhaustive investigation impossible.

Mechanics:
- Time and pressure costs.
- Cooperation decay on repetition.
- Soft lockouts via lead expiry.

Constraints:
- No new screens.
- Lives in action outcomes only.

### Task 5 - Aggressive vs cautious divergence
Ensure divergent consequences:
- Aggressive: higher pressure, lower trust, faster closure.
- Cautious: slower time, lead preservation, different failure modes.

Requirement:
- Outcomes must differ in at least two dimensions.

### Task 6 - Evidence interaction locks
Add 1-2 minimal lock rules.

Examples:
- Interviewing one witness makes another uncooperative.
- Early arrest closes a forensic path.

Constraints:
- Keep it legible.
- No cascading locks.

### Task 7 - Alternative path validation
Re-run the same seed with:
- Path A: cautious, evidence-heavy.
- Path B: aggressive, early commitment.

Verify:
- Different hypotheses.
- Different outcomes.
- Different world pressures.

## Phase boundary enforcement

Do not add:
- Nemesis adaptation.
- Persistent world memory.
- New evidence classes.
- New case types.

## Phase 2 exit criteria (hard stop)

Stop when:
- More evidence does not guarantee confidence.
- Waiting can worsen outcomes.
- Two paths diverge meaningfully.
- Players hesitate even when "ready".

If true, Phase 2 is complete. Stop.
