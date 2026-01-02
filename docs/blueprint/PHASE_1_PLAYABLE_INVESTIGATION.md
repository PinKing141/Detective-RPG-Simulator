# PHASE 1 - PLAYABLE INVESTIGATION
(Unified Specification and Acceptance Contract)

## Phase 1 Design Question

> Does the player meaningfully reason with incomplete information and feel responsible for outcomes?

If Phase 0 proved:
truth -> evidence -> validation

Phase 1 proves:
reasoning -> risk -> consequence

Phase 1 is not about realism, depth, or content.
It is about player responsibility under uncertainty.

## What Phase 1 Adds (and What It Does Not)

Phase 1 adds:
- Player-facing reasoning.
- Interpretive (not factual) hypotheses.
- Evidence that implies, not answers.
- Consequences that persist beyond a single case.
- Divergent player behavior on the same truth.

Phase 1 does not add:
- Nemesis adaptation.
- Living world persistence.
- Long-term NPC memory.
- Full narrative prose.
- Deep profiling accuracy.
- Weapon or method certainty.

Anything that reduces ambiguity is out of scope.

## Core Phase 1 Goals (Non-Negotiable)

Phase 1 is complete only when all four are true:
1) Players can form a hypothesis before certainty.
2) Players can be wrong for understandable reasons.
3) Different players act at different thresholds.
4) The game never tells the player "the answer."

Everything below enforces these goals.

## 1. Hypothesis Model (Critical Change)

Phase 1 must not ask for:
- Weapon type.
- Exact method.
- Cause of death.
- Omniscient labels (sharp / blunt / poison).

Phase 1 hypothesis model:

Set hypothesis:
- Suspect: (choose)
- Claims: (choose 1-3)

Allowed claim types:
- "Suspect was present near the scene"
- "Suspect had opportunity during the time window"
- "Suspect had motive linked to the victim"
- "Suspect behavior aligns with the crime"

Claims are assertions, not answers.
Later phases may refine them; Phase 1 must not.

Why this is mandatory:
- Player reasons from evidence, not system truth.
- Hypotheses can be partial, weak, or wrong.
- Validation becomes explanatory, not binary.
- Early action becomes a choice, not a guess.

## 2. Evidence Rule (Imply, Never State)

Phase 1 evidence law:
Evidence never tells the player what it means.
It only states what it claims.

Example (correct):
Witness statement
Claim: Morgan Iverson was near the scene
Time: approx. 9:00pm
Confidence: High

Not:
- "Places suspect at scene"
- "Confirms presence"
- "Supports guilt"

Meaning belongs to the player.

## 3. Always-Visible Hypothesis Summary (Required)

Phase 1 requires a persistent hypothesis summary.

Current Hypothesis
Suspect: Morgan Iverson

Claims:
- Present near the scene
- Opportunity during time window

Supporting Evidence:
- Witness statement (strong)
- Partial forensics (weak)

Gaps:
- No corroborating physical evidence
- Time window not fully constrained

This turns the loop from menu-driven into cognitive.

## 4. Arrest Is a Commitment, Not an Action

Phase 1 arrest means:
"I am acting on this interpretation, knowing it may be incomplete."

Arrest flow:
1) Player sets hypothesis.
2) Player reviews supports and gaps.
3) Player commits anyway.
4) Game explains consequences and continues.

No correctness prompt.
No solver UI.
No right answer reveal.

## 5. Validation Must Explain, Not Score

Validation output must always include:

Arrest Outcome: Failed

What worked:
- Presence aligned with witness testimony

What failed:
- No physical evidence linked suspect to scene
- Opportunity window was inconclusive

Why this happened:
- Witness memory degraded
- Forensic confidence was weak

World Effect:
- Pressure rises
- Trust decreased

Rules:
- No percentages.
- No RNG language.
- No "wrong" or "correct."
- Always legible in-world.

## Temporal Gate Rule (Phase 1)

Temporal coherence can upgrade arrest confidence only when anchored by at least one
non-testimonial evidence class (physical in Phase 1). Testimonial-only mixes (witness
and CCTV) remain shaky even if time windows align.

Reference: see docs/blueprint/EVIDENCE_COMPOSITION_RULES.md for the locked rule and
Phase 2 seam.

## Core Proofs (Phase 1 Acceptance Criteria)

Core loop proof:
- Solvable case.
- Evidence derived from truth.
- No brute-force path.
- Wrong conclusions remain playable.

Behavior proof:
- Players choose what not to do.
- Different investigation paths can succeed.

Failure proof:
- Wrong arrests have consequences.
- Missed leads matter.
- Inaction escalates pressure.

Legibility proof:
- Every outcome explainable in-world.

## What You Already Have (Phase 0++)

Already complete:
- Deterministic truth generation.
- Evidence projection with noise.
- Time and pressure costs.
- Hypothesis validation.
- Outcome summaries (supports and missing).

This is a correct Phase 0 foundation.

## What Phase 1 Still Requires (Only Three Things)

Step 1 - Consequence system and case outcome record (do this first).

Minimal structure:
CaseOutcome:
- arrest_result: success | partial | failed
- trust_delta: int
- pressure_delta: int
- notes: list[str]

On case end:
- Apply deltas.
- Start next case with modified trust and pressure.
- Reset investigation state.

No long-term memory.
No NPC grudges.
No nemesis logic.

Step 2 - Lead clock and inaction escalation (second).

Minimal rules:
- Each case has 2-3 leads.
- Each lead expires at time + N.
- When expired, evidence weakens, disappears, or contradicts.

This ensures:
- Waiting is a decision.
- Doing nothing is a choice.
- Time pressure is real.

Step 3 - Validate alternative investigation paths (third and final).

Do not add systems.
Instead:
- Replay the same seed twice.
- Path A: witness and timeline.
- Path B: forensics and opportunity.

Verify:
- Different hypotheses.
- Different arrests.
- Different consequences.

If outcomes converge, stop and fix.

## What Must Not Be Built in Phase 1

Hard no until Phase 2:
- Weapon specificity.
- Profiling accuracy boosts.
- Behavioral certainty systems.
- Nemesis adaptation.
- Narrative callbacks.

If it reduces uncertainty, it does not belong here.

## Phase 1 Stop Conditions (Mandatory)

You must stop when:
- A player can arrest early and fail meaningfully.
- A player can wait and succeed differently.
- The same case produces different outcomes.
- You can explain every outcome without referencing code.

If all are true, Phase 1 is complete. Stop.

## Final Declaration

This document is a binding contract for Phase 1.
You are no longer building foundations.
You are proving player responsibility under uncertainty.
