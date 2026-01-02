# Profiling Summary Language Pack

This pack follows the UI tier rules:
- Tier 2 (Constraint): narrows, never concludes.
- Tier 3 (Interpretive Summary): mirrors the player's situation, never validates.
- No solver vocabulary.
- No new truth facts.
- No accuracy boosts.
- No numeric meters shown.
- Output is focus shifts, not answers.

## What the Profiling Summary Is Allowed To Do

- Reframe uncertainty (what matters next, what is fragile).
- Suggest investigation priorities (higher value to corroborate X).
- Warn about risk (this rests on testimony, pressure likely to escalate).
- Highlight contradictions and missing corroboration.

## What It Is Not Allowed To Do

- Identify a demographic ("white male", "late 20s").
- Name a weapon or method unless already surfaced by evidence.
- Assert intent ("planned", "enjoys", "hates").
- Declare likelihood of guilt ("most likely", "probable offender").
- Produce new facts or insider insights.

## Vocabulary Constraints

Use: suggests, indicates, consistent with, difficult to exclude, constrained by,
vulnerable to, relies on, lacks, conflicts with.

Avoid: correct, wrong, culprit, suspect is, the killer, proof, confirms, definitively.

## Output Structure

The Profiling Summary always renders in three blocks. No extra blocks.

### Block A - Working Frame (Tier 2)

One or two sentences: what the investigation is currently constrained by.

Templates:
- "Current reads are constrained by [limitation]."
- "The picture relies heavily on [source type]; independent corroboration remains limited."
- "Available information reduces the space of possibilities, but does not settle attribution."

### Block B - Focus Shifts (Tier 2)

3 to 5 bullet points. Each bullet is one action-oriented priority.

Bullet templates (pick 3 to 5):
- "Prioritise corroboration of [claim] from a non-testimonial source."
- "Treat [evidence class] as fragile until supported by [other class]."
- "Resolve the time window before committing to an arrest."
- "Expect cooperation to degrade if pressure rises; front-load key interviews."
- "If you pursue [action], you may lose access to [lead] before expiry."
- "Look for contradictions rather than additional detail from the same witness."

### Block C - Risk Notes (Tier 3)

2 to 3 short lines that reflect consequences and uncertainty.

Templates:
- "This approach will remain shaky without [missing pillar]."
- "A fast commitment is possible, but will trade certainty for pressure."
- "If leads expire, later conclusions will rely on inference rather than corroboration."

## Phrase Library (By Situation)

These are atoms you can recombine. Use them to avoid repetition while staying controlled.

### 1) Evidence is mostly testimonial

Working frame options:
- "Current reads are constrained by testimony and memory-dependent detail."
- "The case picture rests on statements that can drift under pressure or time."
- "Most supports currently describe proximity, not linkage."

Focus shifts:
- "Prioritise non-testimonial corroboration of presence."
- "Seek a constraint that survives cross-checking: access, movement, or artifacts."
- "Treat additional interviews as diminishing returns unless they add contradiction."

Risk notes:
- "Without independent support, any commitment remains vulnerable to reversal."
- "More statements may add volume, not certainty."

### 2) Evidence is mostly physical or forensic but weak

Working frame:
- "Physical traces are present, but they do not yet anchor to a person or route."
- "Artifacts suggest contact, but attribution remains open."

Focus shifts:
- "Convert trace into linkage: ownership, access, opportunity, or transfer path."
- "Use timeline constraints to test feasibility rather than searching for more traces."
- "Avoid over-committing to a single interpretation of weak physical evidence."

Risk notes:
- "A clean narrative cannot be built from weak artifacts alone."
- "This line can strengthen quickly with one corroborating constraint."

### 3) Evidence conflicts (contradiction present)

Working frame:
- "Current supports do not cohere; contradictions increase interpretive risk."
- "The case contains competing readings that cannot be collapsed yet."

Focus shifts:
- "Prioritise resolving the contradiction before expanding scope."
- "Check whether the conflict is source failure (memory, access, contamination) rather than event failure."
- "Prefer constraints that do not share the same failure mode."

Risk notes:
- "Additional evidence of the same kind will not resolve the split."
- "An arrest under contradiction will almost always degrade outcomes."

### 4) Player is under time or pressure

Working frame:
- "Pressure is shaping what you can still learn, not what is true."
- "Time limits are beginning to function as evidence erosion."

Focus shifts:
- "Front-load the most perishable leads."
- "Choose one corroboration pillar and pursue it fully."
- "Avoid actions that spike pressure unless you are prepared to commit early."

Risk notes:
- "Waiting may reduce clarity rather than increase it."
- "A faster commitment is viable, but consequences will carry."

### 5) Player is about to arrest

Working frame:
- "Your working hypothesis has supports, but relies on [pillar] more than corroboration."
- "The current case shape allows commitment, but not closure."

Focus shifts:
- "If committing now, choose the narrowest claim you can defend."
- "If delaying, prioritise a single corroboration action rather than broad searching."
- "Avoid taking one more action unless it adds a different evidence class."

Risk notes:
- "This arrest will be judged on coherence, not quantity."
- "A clean outcome typically requires at least two independent pillars."

## Variation Without Chaos (Anti-Robotic Control)

Rotate framing style while keeping meaning constant.

Framing styles (choose one per summary):
1) Procedural: "Current reads are constrained by..."
2) Advisory: "Best next value is..."
3) Cautionary: "This line is vulnerable to..."
4) Triage: "If you do only one thing next..."

Example rotation:
- Case 1 uses Procedural
- Case 2 uses Triage
- Case 3 uses Cautionary

## One Fully Written Example

Scenario: witness + weak forensics, no corroborating constraint, time ticking.

Profiling Summary
"Current reads are constrained by testimony-led supports and low-confidence trace."
"The picture narrows possibilities, but does not settle attribution."

Focus shifts
- "Prioritise corroboration of presence using a non-testimonial source."
- "Resolve the incident window before committing to an arrest."
- "Treat further interviews as diminishing returns unless they add contradiction."
- "Front-load perishable leads; delays will turn gaps into inference."

Risk notes
- "This approach will remain shaky without an independent constraint."
- "A fast commitment is possible, but will trade certainty for pressure."

## Implementation Rule of Thumb

When generating a Profiling Summary, only allow references to:
- evidence categories the player already has
- gaps inferred from missing categories (for example, no independent corroboration)
- pressure or time state (as constraint, not drama)

Never allow references to:
- hidden truth attributes
- nemesis data
- signature unless already surfaced as evidence
