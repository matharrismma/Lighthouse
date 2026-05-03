# Evidence Ledger

A directory of recorded precedents the engine can use for closest-case
overlay. Each `*.json` file describes one sealed decision: the axis it
sat on, its dimensional coordinates on the scaffold, and the reasoning
trace that can be overlaid onto a similar incoming packet.

The lookup is implemented in `src/concordance_engine/ledger.py` and
queryable via `concordance ledger lookup <packet.json>` or implicitly
via `concordance ask --auto-precedent`.

## Doctrinal commitments

This ledger is bound by the same rules as the engine itself:

- **Discovery, not design.** Distance is measured by shared scaffold
  dimensions, not by an opinion of similarity. If nothing matches,
  the lookup returns `precedent_id=None` — explicit absence, never
  invented.
- **Categorize, don't answer.** Each precedent carries a
  `reasoning_overlay`, not a verdict. Whether the precedent applies
  to a new situation is the human's call.
- **Source hierarchy.** Precedents that cite scripture include the
  layer (`jesus_words` / `bible` / `apostles` / `recognized_elders`)
  on each anchor.

## Precedent file format

```json
{
  "precedent_id": "ledger://decision/2024-11-08/admit-member-007",
  "axis": "governance",
  "dimensions": ["reasoning", "authority_trust", "time_sequence"],
  "summary": "Community admitted member after 90-day restitution.",
  "anchors": [
    {"ref": "Mt 18:15-17", "layer": "jesus_words"},
    {"ref": "Lk 17:3-4", "layer": "jesus_words"}
  ],
  "reasoning_overlay": {
    "step_1": "Confession witnessed by 2+ community members",
    "step_2": "Restitution verified active",
    "step_3": "Observation period satisfied wait window",
    "step_4": "Final vote 4/5 majority"
  }
}
```

The `dimensions` list is the precedent's coordinates on the scaffold;
those are what the lookup compares against.

## Adding a precedent

1. Write a new `*.json` file in this directory.
2. Pick a stable `precedent_id` (URI-style for traceability).
3. List the precedent's scaffold dimensions — pull these from the
   axis's entry in `concordance_engine.grid.AXIS_DIMENSIONS`.
4. Provide a `reasoning_overlay` so future packets that match this
   precedent can render the trace.
