# Dialog Tree Reuse Notes (dialog-tree-py-master)

Purpose: capture the pieces worth reusing from `dialog-tree-py-master` before deleting it, so we can wire a dialogue/interview graph later without re-reading the repo.

## What to reuse
- `dialog-tree-py-master/dialog_tree/graph.py`
  - `DialogGraph`, `DialogNode`, `DialogChoice` (simple node + choice graph).
  - Deterministic traversal with `current_node()` and `make_choice()`.
- `dialog-tree-py-master/dialog_tree/config_file.py`
  - JSON-to-graph loader (sequence or explicit graph).
- `dialog-tree-py-master/examples/text_adventure_game/__main__.py`
  - CLI-style usage pattern for prompt/choice flow.

## What to ignore
- All Pygame UI (`dialog_component.py`, `ui.py`, image/sound hooks).
- Animations, graphics, sound, screen shake.
- Anything under `examples/animated_dialog`, `examples/custom_app`, `examples/slideshow`.

## Minimal JSON schema we can keep (graph mode)
We can retain the graph JSON layout, but add conditions/effects for interview logic.

Baseline (from dialog-tree):
- `graph.root`
- `graph.nodes[]` with `id`, `text`, `choices[]` (`text`, `leads_to`)

Additions needed for our game:
- `node.tags` (optional: baseline, follow_up, confrontation, exit)
- `choice.conditions` (array of small checks)
- `choice.effects` (array of state updates)
- `node.emissions` (evidence emission hints)

### Tiny JSON example (matches current InterviewState)
```json
{
  "graph": {
    "root": "START",
    "nodes": [
      {
        "id": "START",
        "text": "",
        "choices": [
          {
            "text": "Baseline",
            "leads_to": "BASELINE",
            "tags": ["baseline"],
            "conditions": {"min_rapport": 0.3, "phase": "baseline"}
          },
          {
            "text": "Pressure",
            "leads_to": "PRESSURE",
            "tags": ["pressure"],
            "conditions": {"max_resistance": 0.8}
          }
        ]
      },
      {
        "id": "BASELINE",
        "text": "I heard a disturbance near {place} {time_phrase}."
      }
    ]
  }
}
```

Conditions map directly to `InterviewState` fields:
- `phase`, `rapport`, `resistance`, `fatigue`

## How this plugs into our action system
Use it as the data model for `interview` actions without creating a separate subsystem.

Suggested wiring:
1) `interview` action loads a `DialogGraph` for the target NPC.
2) `InterviewState` tracks:
   - `node_id` (current dialog node)
   - `rapport`, `resistance`, `fatigue`
   - `turns`, `last_choice`, `last_effects`
3) On choice:
   - Evaluate `conditions` against `InterviewState`, evidence flags, and NPC traits.
   - Apply `effects` (rapport/resistance shifts, pressure delta, lead unlock).
   - Trigger `emissions` to surface evidence items.
4) Return the new node text + choices as the interview output.

## Missing features to add (when we wire it up)
- Conditions:
  - `min_rapport`, `max_resistance`, `requires_evidence`, `requires_lead`, `npc_trait`.
- Effects:
  - `rapport_delta`, `resistance_delta`, `fatigue_delta`, `pressure_delta`,
    `emit_evidence_id`, `expire_lead`.
- Guardrails:
  - No choice should directly "solve" a case.
  - Confession is an outcome, not a guaranteed node.

## Integration touchpoints (our repo)
- `src/noir/investigation/actions.py`: call dialog engine for interview.
- `src/noir/narrative/*`: render dialog node text (Tier 1/2 voice).
- `src/noir/deduction/*`: evidence emissions still flow into hypothesis.

## Why this is enough
The dialog-tree graph is a clean, lightweight traversal core. We only need to:
- add condition/effect evaluation, and
- map outcomes to evidence emissions + interview state.
