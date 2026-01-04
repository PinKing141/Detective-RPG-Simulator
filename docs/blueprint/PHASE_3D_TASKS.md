# Phase 3D - Nemesis Pattern Tracker (Proto-Nemesis)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3d---nemesis-pattern-tracker-proto-nemesis

Phase question:
Can players recognize a recurring signature without a full arc?

Phase 3D is not:
- a campaign arc
- nemesis adaptation
- endgame operations
- multiple adaptive killers

## Scope (allowed)
- Signature motif system (token + staging + message).
- Pattern tracker log of observed motifs.
- False positives and unrelated quirks to preserve ambiguity.
- Background serial offenders may appear as non-adaptive noise (short arcs, fixed MO; distinct from copycats).
- No persistence required beyond session memory.
- Pattern assessment labels (Confirmed/Suspected/Imitation/Rejected).
- Copycat checks based on bundle integrity and constraint fit.

## Identity packet (minimal)
- Signature motif token (physical marker).
- Signature staging (body/scene position).
- Message style (note, symbol, call, none).
- Comfort zone (district tags).

Rule:
Identity creates expectation, not certainty.

## Pattern tracker
- Records motifs seen across cases.
- Distinguishes:
  - Nemesis signature (rare).
  - Copycat signature (rarer).
  - Unrelated quirks (common).
- Never declares "confirmed"; only "seen again."
- Uses the case-file template and BAU tone in NEMESIS_MOTIF_LIBRARY.md.
- Pattern updates render as case-file addenda, not raw lists.

## Pattern governance (defensive rules)
Negative evidence handling (absence flags):
- Token: Present / Absent / Ambiguous
- Staging: Consistent / Inconsistent / Unknown
- Message: Present / Altered / Absent
Rule: absence never disproves; it weakens confidence only.

Bundle integrity (internal only):
- Pattern is only suggested when 2 of 3 elements align.
- One motif alone can never advance a pattern state.

Motif drift without adaptation:
- Tokens may appear degraded or incomplete.
- Drift probability is static (non-reactive).

Temporal spacing:
- Signature-like motifs must be separated by 2 to 4 cases.
- Background serial offenders cannot appear adjacent to proto-nemesis hints.

Pattern language escalation (UI only, ordered):
1) Noted Similarity
2) Recurring Detail
3) Pattern Worth Monitoring
4) Possible Imitation
5) Consistent With Prior Incidents
Never go beyond this ladder in Phase 3D.

Red herring sources (explicit):
- Local rituals (religious, cultural)
- Victim behavior artifacts
- Media-inspired mimicry
- Coincidental staging (environmental)
Each false positive maps to one source.

Case-file addendum template (mandatory):
CASE FILE ADDENDUM — INTERNAL NOTE

Summary:
A detail observed in this incident resembles elements seen previously.

Observations:
- [Motif description in plain language]

Assessment:
This may indicate recurrence, imitation, or coincidence.
Insufficient evidence to draw conclusions.

Action:
Continue monitoring in future cases.

Sample addendum (example):
CASE FILE ADDENDUM — INTERNAL NOTE
Status: Recurring Detail

Summary:
A detail observed in this incident resembles elements seen previously.

Observations:
- A stopped clock with the battery removed was placed on the bedside table.

Assessment:
This may indicate recurrence, imitation, or coincidence.
Insufficient evidence to draw conclusions.

Action:
Continue monitoring in future cases.

## Constraints (non-negotiable)
- No persistence beyond the current run.
- No adaptation or counterplay.
- No endgame ops.
- No profiling outputs that name a killer type.
- Only one signature is allowed to be tracked as the proto-nemesis.
- Background serial offenders never adapt and never share the proto-nemesis signature.
- Pattern assessments must be legible and deterministic; no hidden thresholds.

## Deliverables
- Signature motif generator with 3 buckets (token, staging, message).
- Pattern tracker log surfaced in case wrap or briefing.
- At least one false positive per 3 to 5 cases (on average).
- Motif library maintained in docs/blueprint/NEMESIS_MOTIF_LIBRARY.md.
- Generator-ready motifs in assets/text_atoms/nemesis_motifs.yml.

## Exit checklist
- [x] Players notice a recurring motif without certainty.
- [x] False positives appear and are explainable.
- [x] Pattern tracker never declares a solution.
- [x] No nemesis adaptation exists yet.
- [x] Absence of expected motifs is tracked and referenced.
- [x] Single-motif matches never advance pattern state.
- [x] Drift appears without implying adaptation.
- [x] Pattern language escalates without confirming.
- [x] False positives are retrospectively explainable.

Stop condition:
If patterns are recognizable without certainty, stop.

Status: Complete. Phase 3D delivered and locked.
