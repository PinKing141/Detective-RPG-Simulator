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

## Constraints (non-negotiable)
- No persistence beyond the current run.
- No adaptation or counterplay.
- No endgame ops.
- No profiling outputs that name a killer type.
- Only one signature is allowed to be tracked as the proto-nemesis.

## Deliverables
- Signature motif generator with 3 buckets (token, staging, message).
- Pattern tracker log surfaced in case wrap or briefing.
- At least one false positive per 3 to 5 cases (on average).
- Motif library maintained in docs/blueprint/NEMESIS_MOTIF_LIBRARY.md.
- Generator-ready motifs in assets/text_atoms/nemesis_motifs.yml.

## Exit checklist
- [ ] Players notice a recurring motif without certainty.
- [ ] False positives appear and are explainable.
- [ ] Pattern tracker never declares a solution.
- [ ] No nemesis adaptation exists yet.

Stop condition:
If patterns are recognizable without certainty, stop.
