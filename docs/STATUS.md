# Project status -- the honest map

This is the map-never-launder discipline turned on the project itself: what is *real*,
what is *seed*, what is *concept*. The engine's whole value is that it does not claim what
it cannot show -- so neither should its own description. When a doc, page, or pitch says a
surface is "done," check it here first. Every line below is grounded in a real count or
file path; where a headline number rests on a definition, the definition is stated.

_Last reconciled: 2026-06-16 (full review; same-day: tutor-shape fix, extended integrity suite, companion unification)._

**Legend**
- **REAL** -- working code with real data/usage; the claim holds as stated.
- **SEED** -- working code over a deliberately small, curated dataset; a demo, not yet at scale.
- **BUILT-EMPTY** -- the code is complete and wired, but there is ~zero real data/usage behind it.
- **CONCEPT** -- documented intent; little or no implementation yet.
- **PoC** -- proven end-to-end once, at toy scale; not a usable product.

---

## The instrument (verify + map + sovereignty) -- REAL

| Surface | State | The honest detail |
|---|---|---|
| Verification engine | **REAL** | 64 deterministic `verify_*` domains; no network/LLM/randomness/clock in the math path. Fail-closed: a verifier passes only on CONFIRMED; exception/unknown/malformed input -> ERROR/BROKEN, never a silent pass. |
| Zero-false-positive guarantee | **REAL** | Pinned by offline tests: a 14-domain TRUE/FALSE proof (`tests/test_no_false_positives_multidomain.py`) **plus an 18-case near-miss suite** that survives the subtle traps -- `(x+1)**2=x**2+1`, off-by-a-constant antiderivatives, unbalanced equations, BB84 insecure-claimed-secure (`tests/test_no_false_positives_extended.py`) -- + the trust-path suite (`tests/test_derivation_pipeline.py`). Public benchmark: 58/58, 0 false seals. |
| The `check` / derivation pipeline | **REAL** | Single source of truth behind the MCP tool and `/derivation/verify`. The one Anthropic call only FORMALIZES prose into steps; the verdict stays deterministic (a wrong formalization shows up as BROKEN). |
| Coordinate map / vine | **REAL** (with a precise meaning) | 1,684 nodes, 2,363 edges; `vine_validity 0.999` is a real graph-reachability metric. **It measures internal connectivity to the designated root nodes -- NOT truth, NOT external grounding.** |
| Card library | **REAL** | 11,085 cards on disk, tracked in git (off-machine backup exists for the content). |
| Empirical grounding | **REAL, with a stated definition** | "100% grounded" is true **by classification, not by 100% external sourcing**: of 64 verifiers, 29 are data-grounded (external or embedded standards), 32 are pure-compute (need no data), 3 are non-empirical (philosophy/rhetoric/theology, grounded in the Word). 0 need-but-lack data. Pure-compute checks *relationships*, not real-world ground-truth. |
| Scripture / concordance | **REAL** | Original languages (Hebrew/Greek + Strong's), WEB translation, BDB/Thayer lexicon, Matthew Henry commentary, Spurgeon sermon index, `concord` (term-convergence across attributed takes), `cross_references` (344,799 openbible.info/TSK links), and a front door at `/concordance.html`. All ATTRIBUTED; the engine surfaces, never authors. |
| Sovereignty stack | **REAL / most shippable** | `OpenAICompatibleAdapter` is stdlib-only and runs the engine standalone against a local model (Ollama) at $0/call. The physical-token write-gate is LIVE in prod (`CONCORDANCE_MODE=restricted`, token mounted) guarding substrate writes. |

---

## The church (people, agents, served need) -- mostly SEED / empty / concept

The instrument is strong; the community it is meant to serve is built as code but largely
unpopulated. Stated plainly so no one mistakes scaffolding for a congregation.

| Surface | State | The honest detail |
|---|---|---|
| Corpus prompt set | **REAL** | `data/prompt_sets/v1.jsonl` = 1,752 prompts, assembled offline (no API cost). |
| Fine-tuned "sovereign model" | **PoC** | One MLX LoRA adapter (4-bit Mistral-7B, 41MB) on **28 training pairs, never evaluated** (`eval_scores: {}`). The pipeline is proven end-to-end; **this is not a usable model** -- do not represent it as one. |
| Gated generation (`run_gated`) | **PARTIAL** | The full RED->LLM->verifiers->FLOOR->BROTHERS->GOD pipeline runs, but with only **2 verifiers** by default (`scripture_anchors` + keyword `theology_doctrine`), not the 64; it is **not exposed as a public endpoint**. BROTHERS gate honestly returns `deferred` (zero witnesses). Ed25519 signing is TODO (the SHA-256 hash is the integrity guarantee today). |
| Apothecary | **SEED** | Working deterministic compounder over the substrate + **12 herb monographs**; compound records are test-only. A real reference primitive, not yet a real apothecary. NOT medical advice. |
| Coach / lifelong tutor | **SEED** | Now **7 subjects / 69 units** (phonics 35, math 10, science 7, bible 5, reading/writing/social-studies 4 each), served via `/curriculum` to `/read.html` with interaction chunks (sound-it-out/blend for reading; a ten-frame to 20 for math). **Honesty note:** the tutor rendered BLANK behind HTTP 200s until 2026-06-16 -- `/curriculum` returns `{tracks:{...}}` but the loader read flat `d[key]`; fixed (`d.tracks||d`), proven (0->7 subjects), now guarded by `tools/check_surfaces.py` + `tests/test_surface_contract.py`. Still a demo-scale curriculum, not "capture a generation." |
| Community / contributors | **BUILT-EMPTY** | Full code (handles, Ed25519 anchor, append-only log, tier ladder) with **0 registered contributors**. |
| Peer federation | **BUILT-EMPTY** | Sync code + token-guarded `/chain/receive`, but **0 peers** (single node). |
| Missions (the Acts-2 local community) | **CONCEPT** | No code, no `data/missions/`. The telos, not yet an implementation. |
| Giving / serve-the-least | **verifier REAL, flow CONCEPT** | `verify_giving` proves a *provided* donation chain conserves value (no leakage); **no money actually flows** through any surface. |
| Food system | **CONCEPT** | Long-arc intent; no implementation beyond nutrition/agriculture verifiers. Software serves it; it never "feeds" anyone -- do not claim otherwise. |

---

## Testing posture

- **Trust path: strong** -- 58/58 public benchmark + offline tests: the cardinal guarantee across 14 domains **+ 18 near-miss cases**, fail-closed paths, Scripture-tool honesty contracts, the anti-idol guardrail, and a surface contract that locks the tutor-shape fix.
- **Still thin** -- ~10 of 386 HTTP routes are tested; the broad MCP tool surface (data lookups) is lightly covered. The benchmark's live mode still depends on prod being up (the multi-domain proofs are offline). A standing surface health check (`tools/check_surfaces.py`) now verifies the public doors return real DATA (curriculum units, brain nodes), not just 200 -- added after it caught the blank tutor.

## One honest line

The instrument -- verify, map, sovereignty -- is real and strong. The church -- people,
agents, missions, served need -- is built as code but essentially unpopulated. Standing on
our own is the most shippable lever today; serving the least needs real content and real
people, not more code.
