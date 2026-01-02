# PHASE 1 - PLAYABLE INVESTIGATION
Exit checklist (binary / non-negotiable)

Rule:
- If every box is checked, Phase 1 is complete and you must stop.
- If any box is unchecked, you are not allowed to move on.

## 1. Core loop proof (foundational)
- [x] A case is generated from a single hidden truth.
- [x] All evidence shown to the player is derived from that truth.
- [x] The case is solvable without using every action.
- [x] The player can reach a wrong conclusion and continue playing.
- [x] The game never reveals the correct solution explicitly.

Stop test:
- If a player can brute-force by doing everything, fail.

## 2. Hypothesis model (critical)
- [x] Hypotheses use claims, not solver facts.
- [x] Hypotheses do not require weapon, method, or cause of death.
- [x] Hypothesis inputs are interpretive (presence, opportunity, motive, behavior).
- [x] Hypotheses can be partial or weak and still actionable.
- [x] Hypothesis must be set before arrest.

Auto-fail conditions:
- [x] Player is asked to choose sharp / blunt / poison.
- [x] Player is asked to name the exact method.

If either is true, fail.

## 3. Always-visible hypothesis summary
- [x] Current hypothesis is visible at all times.
- [x] Summary clearly shows suspect, claims, supporting evidence, and gaps.
- [x] Evidence is never auto-interpreted for the player.
- [x] Player must decide whether support is enough.

Stop test:
- If the UI allows action without the player seeing their own reasoning, fail.

## 4. Evidence implies, never states
- [x] Evidence descriptions state claims, not conclusions.
- [x] No evidence uses labels like "confirms", "proves", or "places suspect".
- [x] Confidence is shown as qualitative (high / medium / low).
- [x] Time is always approximate or windowed unless directly observed.

Auto-fail conditions:
- [x] Evidence explains what it means.
- [x] Evidence collapses uncertainty.

If either is true, fail.

## 5. Arrest as commitment (not selection)
- [x] Arrest is only possible after setting a hypothesis.
- [x] Arrest commits to the current interpretation.
- [x] No correctness prompt appears before arrest.
- [x] Player can arrest with incomplete or weak support.

Stop test:
- If arrest feels like "choose the right answer", fail.

## 6. Validation and outcome legibility
- [x] Validation explains outcomes in-world.
- [x] Validation includes what worked, what failed, why it failed, and consequences.
- [x] No percentages or hidden rolls shown.
- [x] No "wrong" or "correct" language used.

Stop test:
- If you cannot explain an outcome without referencing code, fail.

## 7. Consequence system (required)
- [x] Case outcome record exists (success / partial / failed).
- [x] Wrong arrest modifies trust / pressure / scrutiny.
- [x] Consequences persist into the next case.
- [x] The game continues after failure.
- [x] No long-term memory beyond next case.
- [x] No nemesis logic.
- [x] No NPC grudges.

Stop test:
- If failure only affects the current case, fail.

## 8. Lead clock and inaction pressure
- [x] Each case has limited actionable leads.
- [x] Leads expire based on time or inaction.
- [x] Expired leads weaken, vanish, or contradict.
- [x] Doing nothing is a meaningful decision.

Stop test:
- If waiting has no downside, fail.

## 9. Alternative path validation
- [x] Same seed can be played at least two ways.
- [x] Different evidence paths produce different hypotheses.
- [x] Different hypotheses can both be viable.
- [x] Outcomes differ meaningfully (not just faster/slower).

Stop test:
- If all optimal play converges, fail.

## 10. Phase boundary enforcement
- [x] No weapon specificity added.
- [x] No profiling accuracy boosts.
- [x] No behavioral certainty systems.
- [x] No nemesis adaptation.
- [x] No narrative callbacks or world memory.

Auto-fail conditions:
- [x] Any system added that reduces uncertainty.
- [x] Any system added for realism.

If either is true, fail.

## Final phase 1 exit rule

Phase 1 ends when player behavior diverges under uncertainty.
Not when systems feel deep.
Not when text feels polished.
Not when realism improves.

If every box above is ticked, Phase 1 is done. Stop.
