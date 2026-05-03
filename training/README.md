# Training Kit

Everything you need to fine-tune a model on the Concordance Engine's
behavior — its protocol, its verdicts, its voice. Drop-in for HuggingFace
PEFT/LoRA, OpenAI fine-tune API, or Anthropic message formatting.

This is also the project's **catechism**: the place where the four-gate
protocol is taught, in worked examples, in the same voice the engine
uses. A model that has trained on this should land at the same gates a
faithful reviewer would.

---

## Two protocols, four gates each

The project has two "four gates" patterns. They are complementary, not
competing.

| Pattern | Where it lives | Gate names | What it does |
|---|---|---|---|
| **Reasoning** | `eval/`, `training/data/conversational_*.jsonl`, the front-page form | RED → FLOOR → WAY → EXECUTION | Walks a model through deciding what to do about a scenario |
| **Validation** | `src/concordance_engine/`, the packet API | RED → FLOOR → BROTHERS → GOD | Validates a structured packet and records the verdict |

The reasoning protocol is what an LLM **performs** turn-by-turn. The
validation protocol is what the engine **enforces** on a packet. Train
on both. The reasoning protocol teaches the model how to think; the
validation protocol teaches it the packet shape it can submit to the
live engine for permanent record.

---

## What's in this kit

```
training/
├── README.md                  ← this file
├── SYSTEM_PROMPT.md           ← canonical system prompt (reasoning protocol)
├── FORMAT.md                  ← JSONL schema for training items
├── BASELINE.md                ← what to expect; current numbers
├── CATECHISM.md               ← Q&A teaching the protocol from first principles
├── data/
│   ├── conversational_train.jsonl   ← hand-written items, RED/FLOOR/WAY/EXECUTION format
│   ├── packet_train.jsonl           ← hand-written packet → verdict pairs, engine format
│   └── README.md                     ← schema and provenance
├── loader.py                  ← JSONL → HF datasets / OpenAI / Anthropic
├── score.py                   ← wrap eval/run_eval.py with cleaner CLI
└── adapters/
    ├── README.md
    ├── openai_finetune.py     ← OpenAI fine-tune API
    ├── huggingface_sft.py     ← HF + PEFT LoRA SFT loop
    └── anthropic_messages.py  ← format items for the Claude messages API
```

---

## Quickstart

### 1. Score the heuristic baseline

```bash
PYTHONPATH=src python eval/run_eval.py --mode=heuristic
```

Tells you how well the *dataset's own assistant turns* line up with the
expected halt gates. Anything you train should beat the heuristic by a
non-trivial margin; if it doesn't, your training data is contaminated or
the model isn't learning the protocol.

### 2. Convert training data to your provider's format

```bash
# HuggingFace datasets format (for SFT with peft/trl)
python training/loader.py \
    --in training/data/conversational_train.jsonl \
    --format hf \
    --out training/data/hf_train

# OpenAI fine-tune JSONL
python training/loader.py \
    --in training/data/conversational_train.jsonl \
    --format openai \
    --out training/data/openai_train.jsonl

# Anthropic message format (for batched scoring)
python training/loader.py \
    --in training/data/conversational_train.jsonl \
    --format anthropic \
    --out training/data/anthropic_train.jsonl
```

### 3. Fine-tune

Pick the adapter for your stack:

```bash
# OpenAI fine-tune via API
python training/adapters/openai_finetune.py \
    --train training/data/openai_train.jsonl

# HuggingFace + PEFT LoRA (single GPU)
python training/adapters/huggingface_sft.py \
    --train training/data/hf_train \
    --base-model meta-llama/Llama-3.1-8B-Instruct \
    --output ./out
```

### 4. Score the fine-tuned model

```bash
# Generate predictions on eval/eval_chat.jsonl
python training/adapters/openai_finetune.py \
    --predict --model <your-fine-tuned-id> \
    --in eval/eval_chat.jsonl \
    --out preds.jsonl

# Score against expected halt gates
python training/score.py --predictions preds.jsonl
```

A successful run reports overall accuracy plus per-domain breakdown plus
the most-confused gate pairs.

---

## Adding training items

The seed `conversational_train.jsonl` is hand-written and small (≤ 30
items). Quality over quantity. Two principles for additions:

1. **Keep the seed clean.** No items copied from `eval/eval_chat.jsonl` —
   the eval is your held-out test set; contaminating it with training
   data invalidates your numbers.
2. **Cover the gates.** When you add an item, check that you're not
   over-representing one halt gate. The seed targets roughly even
   distribution: ~25% halts at RED, ~25% at FLOOR, ~25% at WAY, ~25%
   PASS-through (NONE).

Item shape lives in `FORMAT.md`. The system prompt lives in
`SYSTEM_PROMPT.md` — copy it verbatim into every new item's system role.

---

## Relationship to the engine

This kit teaches *behavior*. The engine in `src/concordance_engine/`
enforces *correctness*. They are independent layers:

- A well-trained model can produce a packet that the engine still
  REJECTs (because the math doesn't balance, or required fields are
  missing). That's a feature, not a bug — the engine is the second line
  of defense after the model's own reasoning.
- Conversely, the engine can PASS a packet that came from a poorly
  reasoning model. The engine doesn't validate wisdom; it validates
  structure. The training kit is what closes that gap.

Together, they implement the principle: **a trained model produces good
packets, and a deterministic engine checks them.** Either alone is
weaker; both together is the architecture.

---

## License

The training data, system prompts, and scripts in this directory are
released under Apache 2.0, matching the engine. The eval dataset and
training items are hand-written; no machine-generated content has been
added unattributed.
