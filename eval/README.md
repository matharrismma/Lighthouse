# Eval

Conversational eval data for the Four-Gates protocol and a runner that scores model outputs against it.

## Files

| File | Purpose |
|---|---|
| `eval_chat.jsonl` | 50 eval items: `id`, `domain`, `difficulty`, `labels`, `halt_gate_expected` (`RED`/`FLOOR`/`WAY`/`EXECUTION`/`NONE`), and `messages` (system + user + canonical assistant) |
| `full_eval_dataset_with_metadata.json` | Same content with richer metadata envelope |
| `run_eval.py` | Heuristic baseline + score-predictions modes |
| `adapter_example.py` | Reference adapter showing how to plug an LLM into the runner |
| `sample_predictions.jsonl` | Sample 50-line predictions file (heuristic baseline output) |

## Two relationships to the engine

The eval data is **prompt-based**: the model is asked to reason in RED → FLOOR → WAY → EXECUTION order and produce a verdict. The engine in `src/concordance_engine/` is **packet-based**: it consumes a structured packet and runs four gates. They overlap conceptually; they do not share an input format. The runner here scores prompt-based behavior. Bridging the two — auto-extracting a packet from each eval prompt and running it through `validate_packet` — remains open work.

## Quickstart

```bash
# 1. Heuristic baseline (extract halt gate from the dataset's own assistant turn).
#    Measures dataset internal consistency. ~76% as of v1.0.5; failures are
#    mostly NONE / full-pass items.
PYTHONPATH=src python eval/run_eval.py --mode=heuristic

# 2. Score a model's predictions against the dataset.
PYTHONPATH=src python eval/run_eval.py --mode=score \
    --predictions eval/sample_predictions.jsonl

# 3. Plug in a real model. See eval/adapter_example.py — three-line adapter
#    for OpenAI or Anthropic. Then:
python eval/adapter_example.py    # writes eval/echo_predictions.jsonl
PYTHONPATH=src python eval/run_eval.py --mode=score \
    --predictions eval/echo_predictions.jsonl
```

## Predictions JSONL format

Each line:

```json
{"id": "EVAL-0001", "predicted_halt_gate": "FLOOR"}
```

`predicted_halt_gate` is one of `RED`, `FLOOR`, `WAY`, `EXECUTION`, `NONE`, or `UNKNOWN`. The runner compares against `halt_gate_expected` per item and reports overall accuracy plus the most-common confusions.

## Adding new eval items

Append a JSONL line to `eval_chat.jsonl` with the same shape:

```json
{"id": "EVAL-0051", "domain": "business", "difficulty": "medium",
 "halt_gate_expected": "FLOOR", "labels": ["accountability"],
 "messages": [
    {"role": "system", "content": "<protocol prompt>"},
    {"role": "user", "content": "<scenario>"},
    {"role": "assistant", "content": "RED GATE: PASS\nFLOOR GATE: FAIL\n..."}
 ]}
```

Re-run `--mode=heuristic` to confirm the new item parses cleanly.
