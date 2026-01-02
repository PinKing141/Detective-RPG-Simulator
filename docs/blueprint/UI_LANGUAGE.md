# UI Language Design - Non-Robotic by Construction

## Core Principle (Non-Negotiable)

The UI never states conclusions.
It reports observations, constraints, and tensions.
The player performs inference.

If the UI explains too much, it becomes robotic.
If it lists facts, it becomes mechanical.
If it frames uncertainty, it feels human.

## Language Tiers (Foundation)

Every UI message must belong to exactly one tier.
Never mix tiers in the same message.

### Tier 1 - Observation (Raw, Boring, Trustworthy)

Purpose: convey what exists without interpretation.
Tone: flat, factual, minimal.

Used for:
- Evidence acquisition
- Logs
- Artifact inspection

Rules:
- No verbs implying intent
- No conclusions
- No adjectives beyond confidence/time
- No narrative framing

Template:
```
[Source]
Observation:
- What was observed
- When (approximate)
- Reliability indicator
```

Examples

Witness statement
```
Witness Statement
Observation:
- Morgan Iverson was seen near the alley
- Time: approximately 9:00 pm
- Reliability: high
```

Forensics
```
Forensic Report
Observation:
- Trace material recovered from doorway
- Match confidence: low
```

This tier is allowed to feel dry.
Dry equals credible.

### Tier 2 - Constraint (Where Intelligence Appears)

Purpose: narrow possibility space without asserting truth.
Tone: careful, analytical, conditional.

Used for:
- Timeline reasoning
- Opportunity narrowing
- Access limitations
- Timeline Analysis (Phase 2)

Rules:
- Always conditional ("suggests", "limits", "cannot exclude")
- Never names a culprit
- Never claims certainty
- Never references hidden truth

Template:
```
Constraint Analysis
Based on available information:
- What is limited
- What remains possible
- What cannot be confirmed
```

Examples

Timeline constraint (Phase 1)
```
Timeline Assessment
Based on current evidence:
- Access to the scene appears limited between 8:40-9:10 pm
- Only one known individual could reach the location during this window
- This does not confirm involvement
```

Timeline Analysis (Phase 2)
```
Timeline Analysis
Based on transit records and access logs:
- Movement during the critical window was highly constrained
- Alternative routes appear infeasible
- Presence remains circumstantial
```

This tier is where the game feels smart without being arrogant.

### Tier 3 - Interpretive Summary (Player-Facing Reasoning Mirror)

Purpose: reflect the player's hypothesis back to them without validating it.
Tone: neutral, reflective, cautious.

Used for:
- Hypothesis summary
- Pre-arrest review
- Case wrap-up framing

Rules:
- Never says "correct" or "wrong"
- Uses "supports", "relies on", "lacks"
- Explicitly lists gaps

Template:
```
Current Hypothesis
Claims:
- ...
Support:
- ...
Gaps:
- ...
```

Example
```
Current Hypothesis
Claims:
- Morgan Iverson was present during the incident window

Support:
- Witness statement (high confidence)
- Timeline constraint (limited access)

Gaps:
- No physical evidence links suspect to the scene
- Method remains unknown
```

This makes the player feel responsible.

### Tier 4 - Consequence (Never Moralize)

Purpose: explain outcomes without judgment.
Tone: procedural, grounded, institutional.

Used for:
- Arrest outcomes
- Escalation
- World reaction

Rules:
- No "you failed"
- No emotional language
- Always explain why
- Always show effect

Template:
```
Outcome
Assessment:
- ...
Factors:
- ...
Effect:
- ...
```

Example
```
Arrest Outcome: Shaky

Assessment:
- Case relied primarily on testimonial evidence

Factors:
- No independent corroboration
- Timeline constraints were suggestive but incomplete

Effect:
- Oversight increased
- Cooperation reduced
```

This feels fair even when negative.

## Anti-Robotic Ruleset

These are hard constraints. Violating them will make the game feel artificial.

Rule 1: No sentence may contain more than one inference.
Bad:
This suggests the suspect likely committed the crime.
Good:
This limits who could have been present.

Rule 2: Never use solver vocabulary.
Banned words:
- correct
- wrong
- solution
- culprit
- answer
- proof
Allowed:
- supports
- conflicts with
- remains unclear
- limits
- consistent with

Rule 3: Uncertainty must be explicitly named.
Bad:
The timeline is unclear.
Good:
The timeline relies on incomplete access records.

Rule 4: Evidence never speaks for itself.
No:
This places the suspect at the scene.
Yes:
This suggests proximity to the location.

Rule 5: Lists must be interpretable, not exhaustive.
Never show everything.
Show:
- what matters now
- what is missing
- what is risky

This avoids checklist gameplay.

## How This Evolves Without Breaking

Phase 1:
- Mostly Tier 1 + Tier 3
- Minimal Tier 2
- Consequences are short

Phase 2:
- Tier 2 expands (Timeline Analysis)
- Tier 3 gains more nuance
- Tier 4 consequences deepen

No tier changes. No rewrites. Just more instances.
That is why this scales.

## Final Design Law

The UI should always feel like a careful professional trying not to overstate their case.

If the UI ever sounds confident, clever, or dramatic, it has gone too far.
