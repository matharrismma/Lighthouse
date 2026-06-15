# Standalone Model — Operator Runbook

> **Load-bearing distinction — read this before everything else.**
>
> This is **not** a project to build an AI. We are not training a model that
> answers questions. We are growing an **organism** that tests every answer
> against an external reference, through many small distributed rules, with a
> signed trail showing why. See [`/organic-design.html`](../site/organic-design.html).
>
> The "standalone model" goal does **not** mean replacing the engine with the
> fine-tune. It means swapping out **one organ** (the LLM that produces the
> draft) for a sovereign one. **The gates, the verifiers, the witness step,
> the audit trail, the substrate — all stay around the model whatever the
> model is.**
>
> Anything in this document that sounds like "the fine-tuned model will
> answer questions for us" is shorthand. The fine-tuned model **produces
> drafts that the rest of the body judges.** If you ever find yourself
> wanting to skip the gates because "the model is good enough now," stop.
> That is the failure mode this whole architecture exists to refuse.

This document walks the operator from today's state (the mechanism running
through Anthropic) to a deployed, standalone fine-tuned model serving the
same `/api/generate-gated` endpoint. Same gates. Same verifiers. Same trail
format. Same schema. **One different organ.**

Everything below is reproducible. Cost and time estimates are real.

---

## The fast sovereign path — stand on our own *today* (no fine-tune required)

> Added 2026-06-15. The fine-tune (Phases 4–7) makes a model that is *ours*.
> But sovereignty does not require it: the gates + verifiers + witness + signed
> trail are what make the engine trustworthy, and **they work around any model.**
> So the shortest path to "stand on our own" is to point the drafting organ at
> an **open model you run yourself.**

`OpenAICompatibleAdapter` (in `api/generate_gated.py`) speaks the OpenAI
`/v1/chat/completions` wire format that every local runtime exposes — Ollama,
llama.cpp server, vLLM, LM Studio, text-generation-webui — and every cloud
provider too. **Stdlib only**; the engine host needs no torch/transformers (the
model is served wherever the compute is). *"We can work with anything, but we
stand on our own."*

### Stand alone in five steps
1. On a machine with a GPU (your Mac works): install **Ollama** (ollama.com).
2. Pull an open model: `ollama pull llama3.1`  (or `mistral`, `qwen2.5`).
3. Start it: `ollama serve` → serves `http://localhost:11434/v1`.
4. Point the engine at it (env on the engine host):
   ```
   NH_OPENAI_BASE_URL=http://localhost:11434/v1
   NH_OPENAI_MODEL=llama3.1
   # NH_OPENAI_API_KEY=...   # only for cloud endpoints; local needs none
   ```
5. Call with `base_model: "openai"` (or `"ollama:llama3.1"`):
   ```
   POST /api/generate-gated   { "prompt": "...", "base_model": "openai" }
   ```
   The local model drafts; the **gates, verifiers, witness step, and signed
   trail are identical** to the Anthropic path. Zero external dependency, $0 per
   call, no API key, no rate limit, no provider policy drift.

The fine-tune below then *specializes* this same local organ to our corpus — an
optimization on top of an already-sovereign engine, **not a prerequisite for
sovereignty.** "Work with anything" is the same switch: set `NH_OPENAI_BASE_URL`
to OpenRouter / Together / Groq / a vLLM box (+ `NH_OPENAI_API_KEY`) and use
`base_model: "openai:<model>"`.

---

## The trajectory

```
                 ┌─────────────────────────────────────┐
PHASE 1  ✅      │ Mechanism wrapper                    │  POST /api/generate-gated
DONE             │ AnthropicAdapter → schema v1         │  → /d/<slug> records
                 │ api/generate_gated.py                │
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 2  ✅      │ Benchmark suite                      │  /benchmark.html
DONE             │ baseline vs gated, real metrics      │  data/eval/prompts_v1.jsonl
                 │ tools/run_benchmark.py               │  data/benchmark/runs/...
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 3  ✅      │ Corpus extractor                     │  data/training_corpus/
DONE             │ schema: training_pair/1              │  corpus-<kind>-<stamp>.jsonl
                 │ tools/export_corpus.py               │
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 4          │ Grow the corpus                      │  ~5,000-20,000 pairs
TO RUN           │ tools/generate_corpus.py             │  Cost: $15-60 in Anthropic
                 │ (uses Anthropic to seed real pairs)  │  Time: hours per 1k prompts
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 5          │ Fine-tune on Mac (PoC)               │  Mistral 7B + QLoRA
TO RUN           │ tools/finetune_mlx.py                │  Cost: $0 (your hardware)
                 │ → data/models/mlx/<run-id>/          │  Time: 2-6 hours
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 6          │ Cloud GPU fine-tune (production)     │  Llama 3.1 8B / Mixtral
TO RUN           │ tools/finetune_hf.py                 │  Cost: $20-200 per run
                 │ → data/models/hf/<run-id>/           │  Time: 4-24h on RunPod
                 └─────────────────────────────────────┘
                                  │
                                  ▼
                 ┌─────────────────────────────────────┐
PHASE 7          │ Register + benchmark + deploy        │  POST /api/generate-gated
TO RUN           │ tools/model_registry.py register     │  base_model: "local:..."
                 │ tools/run_benchmark.py --base local  │  Same trail. New model.
                 └─────────────────────────────────────┘
```

---

## What's already in place (you don't have to do these)

| File | Purpose |
|---|---|
| `api/generate_gated.py` | The mechanism module — gates, verifiers, adapters, pipeline. Pluggable base LLM via the `BaseModelAdapter` protocol. Schema `narrowhighway.gated_response/1`. |
| `api/app.py` | Engine route `POST /api/generate-gated` and SSR `/d/<slug>` renderer for `kind=gated-generation`. Supports `base_model: "anthropic" | "echo" | "local" | "local:<id>"`. |
| `tools/run_benchmark.py` | Side-by-side baseline vs gated on the eval set; supports `--base local[:<id>]`; publishes results to `site/benchmark/latest/` for `/benchmark.html`. |
| `tools/export_corpus.py` | Converts `/d/<slug>` records to JSONL training pairs (schema `narrowhighway.training_pair/1`). Hash-deduplicated. |
| `tools/generate_corpus.py` | Generates new `/d/<slug>` records by running a prompt list through the gated pipeline. Cost-capped. |
| `tools/finetune_mlx.py` | Apple Silicon QLoRA fine-tune via `mlx-lm`. For Phase 5 (PoC). |
| `tools/finetune_hf.py` | Transformers + PEFT LoRA fine-tune (CUDA). For Phase 6 (production). |
| `tools/model_registry.py` | Track trained models, their corpus hash, hyperparams, eval scores. |
| `data/eval/prompts_v1.jsonl` | 30 curated eval prompts (10 doctrinal / 10 factual / 10 adversarial). |
| `site/benchmark.html` | Live benchmark results page. |

---

## What you do next (Phase 4 onward)

### Phase 4 — Grow the corpus

The mechanism produces one training pair per gated call. For a useful
fine-tune you want 2k–10k+ pairs minimum. Today you have ~30 from
benchmarking; you need a larger curated prompt set and a corpus generation
run against it.

**Recommended prompt set composition (for a 5k-pair starter corpus):**

- ~1,500 doctrinal: theology questions, scripture readings, historical
  Christian-thought prompts. Expand from `data/eval/prompts_v1.jsonl`.
- ~1,500 family/practical: child-rearing-with-the-faith questions,
  curriculum-vetting, sermon-discernment requests. These are the questions
  visitors will actually ask.
- ~1,500 factual / academic: prompts that exercise the domain verifiers
  (physics, statistics, history, biology). Drives generalization.
- ~500 adversarial: prompt-injection variants, fabricated-citation traps,
  doctrinal-drift attempts. Teaches the model to RED-gate itself.

A reasonable expanded prompt set lives at `data/prompt_sets/`. To produce
one, you can either:

  (a) Hand-curate (~few hours of work), OR
  (b) Use Anthropic to generate them: ask Claude to produce 50 prompts in
      each category; verify, save. Cost: ~$1 to generate ~5k prompts via
      meta-prompting. Then dedupe and tag.

**Generate the corpus** (run on Matt's Windows box — engine + Anthropic
API key already configured):

```powershell
# Dry run first to confirm prompt set parses (no API cost):
python tools/generate_corpus.py --prompts data/prompt_sets/v1.jsonl --base echo --limit 10

# Real run with cost cap (kill switch at $15):
python tools/generate_corpus.py --prompts data/prompt_sets/v1.jsonl --base anthropic --max-cost 15 --sleep 0.3
```

The script:
- Skips duplicates (any prompt already in `data/discernments/`)
- Halts if accumulated cost exceeds `--max-cost`
- Logs to `logs/generate_corpus.log`
- Writes one `/d/<slug>.json` per prompt

**Export to training pairs:**

```powershell
python tools/export_corpus.py
```

Output appears at `data/training_corpus/corpus-gated-generation-<stamp>.jsonl`
plus a `manifest-<stamp>.json` with the file list, stats, and SHA256s.

---

### Phase 5 — PoC fine-tune (Mac M-series, free)

Prereqs on the Mac:
```bash
pip install mlx-lm
```

On the Windows machine (or wherever you ran the corpus generator), copy
the corpus + run-prep over to the Mac. Easiest: OneDrive sync (already
in place) or scp.

On the Mac:

```bash
cd ~/path/to/Lighthouse

# Smaller model for ≤16 GB Macs:
python tools/finetune_mlx.py \
  --corpus data/training_corpus/corpus-gated-generation-20260601-X.jsonl \
  --base mlx-community/Mistral-7B-Instruct-v0.3-4bit \
  --epochs 3 --lora-rank 8 --lora-alpha 16

# OR for ≤8 GB Macs (smaller base):
python tools/finetune_mlx.py \
  --corpus ... \
  --base mlx-community/Llama-3.2-3B-Instruct-4bit \
  --epochs 3 --lora-rank 8
```

Expected time: 2-6 hours for a 5k-pair, 3-epoch run on Mistral 7B 4-bit.

Output: `data/models/mlx/mlx-Mistral-7B-Instruct-...../`
- `adapters/` — LoRA adapter weights
- `manifest.json` — run metadata
- `data/{train,valid,test}.jsonl` — the data splits used

Register the model:

```bash
python tools/model_registry.py register \
  --base mlx-community/Mistral-7B-Instruct-v0.3-4bit \
  --adapter data/models/mlx/<run-id>/adapters/ \
  --backend mlx \
  --corpus data/training_corpus/corpus-gated-generation-...jsonl \
  --run <run-id> \
  --hyperparams '{"epochs":3,"lora_rank":8,"lora_alpha":16}'
```

This returns the model's `id` (something like `nh-7B-Instruct-1a2b3c-20260601-120000`).

Run the benchmark against the new model:

```bash
python tools/run_benchmark.py --base local --limit 30
```

This invokes the LocalModelAdapter, runs the same 30 prompts the
Anthropic-based benchmark used. Aggregate metrics + per-prompt results land
at `site/benchmark/latest/`. The page at `/benchmark.html` shows them.

Compare to the Anthropic baseline — same prompts, same metrics, different
model. Watch the four key axes:

1. **RED-gate adversarial rejection** — should stay 100% (the RED gate is
   deterministic; the fine-tune doesn't change it).
2. **Citation accuracy** — should stay ≥80% if the fine-tune is healthy.
3. **Doctrine-keyword surfacing** — should track the Anthropic baseline ±20%.
4. **Latency** — Mac M2/M3/M4 inference is roughly 10–80 tokens/sec for
   7B-4bit. Expect 5–20s per prompt (vs ~5s for Anthropic). The trade is
   sovereignty: $0 inference, fully local, no rate limits.

If quality is acceptable: you have a working standalone PoC. If not:
expand the corpus, adjust hyperparams (`lora_rank=16`, `epochs=5`), re-run.

---

### Phase 6 — Production fine-tune (cloud GPU)

For larger models (Llama 3.1 8B/70B, Mistral 8x7B) you need a CUDA GPU.
Cheapest path: RunPod or Vast.ai. A single RTX 4090 hour is $0.40–0.70.
Llama 3.1 8B QLoRA on a 5k-pair corpus takes ~3-8 hours → ~$2-6 per run.

Provision the box, then:

```bash
# On the GPU box:
pip install transformers accelerate peft datasets bitsandbytes trl

# Copy the corpus over (scp / rsync / git):
scp -r data/training_corpus user@gpu:/workspace/

# Run the fine-tune:
python tools/finetune_hf.py \
  --corpus /workspace/training_corpus/corpus-gated-generation-...jsonl \
  --base meta-llama/Llama-3.1-8B-Instruct \
  --epochs 3 --lora-rank 16 --lora-alpha 32 --4bit

# Output appears at data/models/hf/<run-id>/
# Sync the run-id directory back to your local repo's data/models/hf/<run-id>/
```

Register exactly as for the MLX case (`--backend hf`).

---

### Phase 7 — Production deploy

Once a registered model passes the benchmark, swap it into production by
adding to the engine's `.env`:

```
NH_DEFAULT_BASE_MODEL=local:nh-Instruct-1a2b3c-20260601-120000
```

(Or call `/api/generate-gated` with `base_model: "local:<id>"` per-call;
defaults still go to Anthropic until you flip the env var.)

**Important:** make sure the engine's Python environment has the inference
runtime installed (`mlx-lm` for MLX backend, `transformers peft` for HF).
The engine machine (Windows) currently runs neither out of the box.

For MLX models, the engine machine must be Apple Silicon — which it isn't.
So the practical Phase 7 path is:
  - Run the MLX model on the Mac as a tiny inference service (e.g. `mlx_lm.server`)
  - Point the engine at it via a thin HTTP adapter
  - Or, deploy the HF model directly on the engine machine (CUDA preferred)

The exact deployment topology depends on hardware. The adapter abstraction
is ready either way.

---

## What stays constant across all phases

- **Schema:** `narrowhighway.gated_response/1`. Training data from
  every phase reads in every phase. No migrations.
- **Trail format:** ordered events, same shape, regardless of base model.
- **Gates:** RED / FLOOR / BROTHERS / GOD always run. The fine-tune
  affects the LLM step in the middle; the rails around it don't change.
- **Audit:** SHA256 content hash on every response. Ed25519 in v2 once
  the operator's signing key is provisioned.
- **`/d/<slug>` permalink:** every gated response is recorded, regardless
  of model. The substrate accumulates across all phases.

---

## Honest cost + time summary

| Phase | What it costs | What it produces |
|---|---|---|
| 4. Corpus growth | $15-60 Anthropic API, hours of operator time | 5k-10k high-quality training pairs |
| 5. Mac fine-tune | $0 (your hardware), 2-6 hours | First standalone PoC: MLX adapter |
| 6. Cloud fine-tune | $20-200 RunPod, 4-24h compute | Production-grade local model |
| 7. Deploy | Hardware to host the inference, $0-$50/mo | Engine running on own model |

End-to-end from today to deployed: **2-6 weeks** of part-time work for
Matt, depending on corpus size and how many fine-tune iterations are needed.

---

## Status as of this writing

- ✅ All scripts and abstractions in place
- ✅ Schema versioned and stable
- ✅ Benchmark verified against Anthropic baseline (30 prompts, $0.18 spent,
     audit trail 100%, RED-gate 100% correct)
- ✅ Registry empty (no models trained yet — Phase 4 onward is operator work)

The mechanism is the foundation. The model is the goal. The infrastructure
between them is now complete.
