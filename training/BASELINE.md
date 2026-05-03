# Baselines

Numbers to beat. If your fine-tuned model doesn't clear these, the
training is not landing. The eval set is `eval/eval_chat.jsonl` (50
items, 5 domains, halt-gate verdicts).

---

## Heuristic baseline

**Method:** Apply a regex to the dataset's own assistant turns; extract
the first `FAIL` gate (or the last gate mentioned for full-pass items).
This is the reference implementation's parser turning the data on
itself — it measures *internal consistency of the dataset*.

**Result (v1.0.5):** ~76% overall accuracy.

The 24% miss rate is primarily on `NONE`/full-pass items: when no gate
fails, the regex picks the last gate mentioned (`EXECUTION`), but the
expected label is `NONE`. This isn't a real failure of the protocol —
it's a labeling convention mismatch — but it does set the floor.

**Run it:**
```bash
PYTHONPATH=src python eval/run_eval.py --mode=heuristic
```

**Treat as the floor:** any trained model that scores at or below 76%
has either failed to learn the protocol or is being trained on
contaminated data (the eval items leaked into training).

---

## Targets for fine-tuned models

| Tier | Overall accuracy | What it means |
|---|---|---|
| **Floor** | ≤ 76% | Equal to or worse than the parse-the-text heuristic. Stop and audit. |
| **Acceptable** | 80–85% | Beat the baseline; training has landed but not optimized. |
| **Good** | 86–90% | Confident gate identification across most domains. |
| **Strong** | > 90% | Near-ceiling on this eval set; remaining errors are usually in genuinely ambiguous items. |

These are *expected* numbers, not promises. The eval set was hand-built
by the project maintainers; a model trained on the seed
(`training/data/conversational_train.jsonl`) and evaluated on
`eval/eval_chat.jsonl` should be in the **Acceptable** tier minimum.

---

## Per-domain expectations

Domains differ in how often each gate is the halt point. Don't expect
uniform accuracy.

| Domain | Items | Tendency |
|---|---|---|
| governance | 14 | Wide gate distribution; hardest. Strong models hit ~85-90%. |
| business | 10 | RED-heavy (deception/exploitation). Easier on average. |
| household | 9 | Personal-life cases; FLOOR/RED frequent. |
| education | 7 | RED on dignity/coercion; FLOOR on safety. |
| church | 5 | RED on coercion; small N → high variance. |

If your model is strong on business and household but weak on
governance, you may have under-represented governance complexity in
training. Add more governance items at higher difficulty.

---

## Per-difficulty expectations

Easy items have one obvious failure named in a single gate. Hard items
require weighing trade-offs and often halt deeper (WAY).

| Difficulty | Strong model |
|---|---|
| easy | 95%+ |
| medium | 85-90% |
| hard | 75-85% |

---

## Confusion patterns to watch

These are the most common failure modes I expect to see in
under-trained models. If your top confusions look different, your
training data likely has a different bias.

- `NONE → EXECUTION` (label-convention mismatch on full-pass items;
  often unfixable without prompt tweaks)
- `WAY → FLOOR` (model halts at FLOOR-CAUTION instead of letting it
  pass through and stopping at WAY)
- `RED → FLOOR` (model gets close but doesn't recognize the
  coercion/Beast pattern)
- `FLOOR → WAY` (model softens a structural problem into a strategic
  one — common voice failure)

---

## Engine packet baseline

For models trained on `training/data/packet_train.jsonl`, the engine
itself is the ground truth. Run the same packet through `/reflect` (or
`validate_packet` MCP tool) and compare to the model's prediction.

A useful command is:

```bash
# Extract every prompt from packet_train.jsonl, send to your model,
# compare verdicts to the engine's actual verdicts.
python training/score_packets.py --train training/data/packet_train.jsonl \
    --model <your-fine-tuned-id>
```

(`score_packets.py` is straightforward to write once you have a model
endpoint; the engine call is `concordance_client.Concordance().reflect(packet)`.)

Strong models should match the engine on >95% of packet predictions —
the verdict shape is highly structured and easier to learn than the
free-form reasoning gates.

---

## When to retrain

- Confusions concentrate on one domain → add training items in that domain
- Confusions concentrate on one halt gate → add training items halting at that gate
- Overall accuracy drops after architectural change → check that the
  system prompt is byte-for-byte identical
- Numbers regress on a specific labeled topic → audit the seed for that
  topic; topic-specific failure usually indicates one bad seed item
