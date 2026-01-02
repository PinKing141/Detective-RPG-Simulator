# PHASE 1 - PLAYABLE INVESTIGATION
Exit checklist (binary / non-negotiable)

Rule:
- If every box is checked, Phase 1 is complete and you must stop.
- If any box is unchecked, you are not allowed to move on.

## 1. Core loop proof (foundational)
- [ ] A case is generated from a single hidden truth.
- [ ] All evidence shown to the player is derived from that truth.
- [ ] The case is solvable without using every action.
- [ ] The player can reach a wrong conclusion and continue playing.
- [ ] The game never reveals the correct solution explicitly.

Stop test:
- If a player can brute-force by doing everything, fail.

## 2. Hypothesis model (critical)
- [ ] Hypotheses use claims, not solver facts.
- [ ] Hypotheses do not require weapon, method, or cause of death.
- [ ] Hypothesis inputs are interpretive (presence, opportunity, motive, behavior).
- [ ] Hypotheses can be partial or weak and still actionable.
- [ ] Hypothesis must be set before arrest.

Auto-fail conditions:
- [ ] Player is asked to choose sharp / blunt / poison.
- [ ] Player is asked to name the exact method.

If either is true, fail.

## 3. Always-visible hypothesis summary
- [ ] Current hypothesis is visible at all times.
- [ ] Summary clearly shows suspect, claims, supporting evidence, and gaps.
- [ ] Evidence is never auto-interpreted for the player.
- [ ] Player must decide whether support is enough.

Stop test:
- If the UI allows action without the player seeing their own reasoning, fail.

## 4. Evidence implies, never states
- [ ] Evidence descriptions state claims, not conclusions.
- [ ] No evidence uses labels like "confirms", "proves", or "places suspect".
- [ ] Confidence is shown as qualitative (high / medium / low).
- [ ] Time is always approximate or windowed unless directly observed.

Auto-fail conditions:
- [ ] Evidence explains what it means.
- [ ] Evidence collapses uncertainty.

If either is true, fail.

## 5. Arrest as commitment (not selection)
- [ ] Arrest is only possible after setting a hypothesis.
- [ ] Arrest commits to the current interpretation.
- [ ] No correctness prompt appears before arrest.
- [ ] Player can arrest with incomplete or weak support.

Stop test:
- If arrest feels like "choose the right answer", fail.

## 6. Validation and outcome legibility
- [ ] Validation explains outcomes in-world.
- [ ] Validation includes what worked, what failed, why it failed, and consequences.
- [ ] No percentages or hidden rolls shown.
- [ ] No "wrong" or "correct" language used.

Stop test:
- If you cannot explain an outcome without referencing code, fail.

## 7. Consequence system (required)
- [ ] Case outcome record exists (success / partial / failed).
- [ ] Wrong arrest modifies trust / pressure / scrutiny.
- [ ] Consequences persist into the next case.
- [ ] The game continues after failure.
- [ ] No long-term memory beyond next case.
- [ ] No nemesis logic.
- [ ] No NPC grudges.

Stop test:
- If failure only affects the current case, fail.

## 8. Lead clock and inaction pressure
- [ ] Each case has limited actionable leads.
- [ ] Leads expire based on time or inaction.
- [ ] Expired leads weaken, vanish, or contradict.
- [ ] Doing nothing is a meaningful decision.

Stop test:
- If waiting has no downside, fail.

## 9. Alternative path validation
- [ ] Same seed can be played at least two ways.
- [ ] Different evidence paths produce different hypotheses.
- [ ] Different hypotheses can both be viable.
- [ ] Outcomes differ meaningfully (not just faster/slower).

Stop test:
- If all optimal play converges, fail.

## 10. Phase boundary enforcement
- [ ] No weapon specificity added.
- [ ] No profiling accuracy boosts.
- [ ] No behavioral certainty systems.
- [ ] No nemesis adaptation.
- [ ] No narrative callbacks or world memory.

Auto-fail conditions:
- [ ] Any system added that reduces uncertainty.
- [ ] Any system added for realism.

If either is true, fail.

## Final phase 1 exit rule

Phase 1 ends when player behavior diverges under uncertainty.
Not when systems feel deep.
Not when text feels polished.
Not when realism improves.

If every box above is ticked, Phase 1 is done. Stop.
