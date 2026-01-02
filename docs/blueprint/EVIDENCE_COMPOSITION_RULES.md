# Evidence Composition Rules (Phase 1 and Phase 2 Seam)

This document locks the Phase 1 probable cause rule and defines how a future
"Timeline Analysis" evidence class can be added in Phase 2 without rebalancing.

## Part I - Phase 1 Condition Check (Lockable Rule)

Implement this rule now and then freeze it.

### Step 1 - Classify evidence used in the hypothesis

For the hypothesis evidence set, compute:

```
classes_present = {
    testimonial,
    physical,
    temporal
}
```

### Step 2 - Determine whether temporal evidence is structural

In Phase 1, temporal evidence is structural only if anchored:

```
temporal_is_structural =
    temporal_present
    AND non_testimonial_present
    AND temporal_is_coherent
```

Where:

```
non_testimonial_present = physical_present
```

### Step 3 - Count structural classes

```
structural_classes = set()

if testimonial_present:
    structural_classes.add("testimonial")

if physical_present:
    structural_classes.add("physical")

if temporal_is_structural:
    structural_classes.add("temporal")
```

### Step 4 - Resolve outcome tier

```
if len(structural_classes) >= 2 and "testimonial" not only:
    CLEAN
elif len(structural_classes) >= 1:
    SHAKY
else:
    FAILED
```

Design invariant (copy verbatim into code comments):

Phase 1 arrests require at least two structural evidence classes for a clean
outcome. Temporal reasoning only becomes structural when anchored by
non-testimonial evidence.

Once this yields:
- testimonial-only -> shaky
- testimonial + physical -> shaky/clean
- physical + temporal -> clean

Stop tuning.

## Part II - Timeline Analysis (Phase 2 Safe Extension)

### What timeline analysis is not

It is not:
- raw CCTV
- witness recollection
- inferred from testimony
- a renamed timeline overlap

Those are still testimonial.

### What timeline analysis is

Timeline Analysis is a derived artifact produced by investigation effort that
constrains opportunity independently of testimony.

### Phase 2 evidence class extension

Add one new evidence subtype:

```
EvidenceClass: ANALYTICAL_TEMPORAL
```

This is non-testimonial.

Examples of sources:
- transit logs
- access records
- phone pings (aggregated, anonymized)
- reconstructed movement windows
- entry/exit timing inconsistencies

The player does not see raw data. They receive a conclusion artifact.

Example artifact (Phase 2):

```
Timeline Analysis
Conclusion:
- Only one individual could reach the location during the window
Confidence: Medium
Basis:
- Access logs
- Travel feasibility
- Window narrowing
```

### How this slots into the existing rule

In Phase 2:

```
non_testimonial_present =
    physical_present
    OR analytical_temporal_present
```

Nothing else changes.

### Why this is architecturally correct

- No weakening of testimonial rules
- No special-case timeline hacks
- No threshold retuning
- A new non-testimonial class unlocks a new clean path

## Part III - Phase 2 Sanity Check

Phase 1 (current):

| Evidence mix           | Outcome |
| ---------------------- | ------- |
| Witness only           | Failed  |
| CCTV only              | Failed  |
| Witness + CCTV         | Shaky   |
| Witness + Forensics    | Shaky   |
| CCTV + Forensics       | Clean   |
| Temporal + Testimonial | Shaky   |

Phase 2 (with Timeline Analysis):

| Evidence mix                            | Outcome |
| --------------------------------------- | ------- |
| Timeline Analysis only                  | Failed  |
| Timeline Analysis + Witness             | Shaky   |
| Timeline Analysis + Forensics           | Clean   |
| Timeline Analysis + Witness + CCTV      | Shaky   |
| Timeline Analysis + Forensics + Witness | Clean   |

## One rule that must never be broken

No evidence derived from testimony may ever be reclassified as non-testimonial.

Timeline analysis must be computed, constrained, and survive independently of
witnesses. If this rule holds, the system will not collapse later.
