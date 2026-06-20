# Self-host — the engine, standing on its own

Narrow Highway is built to run **anywhere**, owing no provider for its core. This
directory is the proof and the quickstart.

## Prove it first

```bash
python selfhost/preflight.py
```

This makes **zero network calls** for the core. It confirms the deterministic
engine verifies truth, catches falsehood, and signs its own seals — with no cloud
key. Exit 0 means the sovereign core is operational.

## What's sovereign vs. optional

| layer | needs | sovereign? |
|---|---|---|
| **Deterministic core** — verifiers, the elimination trail, the seal | `sympy numpy scipy cryptography` (pip) + the offline data | ✅ fully — no provider, no key, no network |
| **Grounding (Layer 0)** — Scripture, lexicons, elements, nuclides, tzdata, OEIS, USDA… | the `data/` + `lw/00_source/` bundle (ships with the repo) | ✅ offline, ownable |
| **Web/API** | `fastapi uvicorn` (pip) | ✅ runs locally |
| **Assistant voice** (generation) | a model — **local** (Ollama, `$0`) or cloud (optional) | ✅ via local model; cloud is "work with anything," never required |

The product — a *computed receipt, not a "trust me"* — lives entirely in the
sovereign core. The model only **threads** attributed pieces (the Bumblebee
discipline); it never authors truth, so a small **local** model suffices.

## Run anywhere

```bash
# 1. core + server deps (offline-installable from a wheel cache if air-gapped)
pip install sympy numpy scipy cryptography fastapi uvicorn

# 2. (optional) sovereign generation — a local model, zero cloud
#    Ollama: https://ollama.com  →  ollama pull qwen2.5:3b
export NH_OPENAI_BASE_URL=http://localhost:11434/v1
export NH_OPENAI_MODEL=qwen2.5:3b

# 3. run the engine
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

The deterministic core needs **no** `ANTHROPIC_API_KEY`. Set one only if you want
the cloud as the (optional) assistant draft model; with `base_model=ollama` (or a
registered `local:<id>` adapter) generation runs fully local at `$0`/call.

## Sovereign generation — validated

The full gated pipeline (RED → draft → verifiers → FLOOR → BROTHERS → GOD) has been
run end-to-end on a local `qwen2.5:3b` with **no cloud calls** (~8s on 4 CPU cores,
no GPU) and produced a correct, cited answer that passed the gates. Point any
caller at `POST /api/generate-gated` with `{"base_model": "ollama:qwen2.5:3b"}`.

## Resilience / offline survival

- **Content is ownable:** the `data/` bundle (Scripture in many tongues, the card
  substrate, Layer-0 sources) is files on disk — copyable to a microSD, carried
  hand to hand, served with no internet.
- **Identity is your own:** seals are Ed25519 signatures from local keys.
- **No single provider can switch it off:** the core has no remote dependency; the
  assistant voice falls to a local model.

The narrow road is the free road. This runs without anyone's permission.
