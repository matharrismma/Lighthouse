# Project status -- the honest map

This is the map-never-launder discipline turned on the project itself: what is *real*,
what is *seed*, what is *concept*. The engine's whole value is that it does not claim what
it cannot show -- so neither should its own description. When a doc, page, or pitch says a
surface is "done," check it here first. Every line below is grounded in a real count or
file path; where a headline number rests on a definition, the definition is stated.

_Last reconciled: 2026-06-19 (discovery/indexability pass: the verified record, proofs, and curriculum made crawlable; the map extended — grid map / locate / arrangement probe / placeholders / scholar grounding; the Missions primitive built CONCEPT→SEED; surface tests hardened. Prior: 2026-06-16 tutor-shape fix, extended integrity suite, companion unification.)._

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
| Gated generation (`run_gated`) | **PARTIAL** | The full RED->LLM->verifiers->FLOOR->BROTHERS->GOD pipeline runs, with a small default verifier set (`scripture_anchors` + keyword `theology_doctrine`), not all 64. It **IS exposed publicly** at `POST /api/generate-gated` (public-safe: rate-limited + budget-gated; kept out of the OpenAPI schema, `include_in_schema=False` — verified live 2026-06-19: route returns 422 on empty body, i.e. present). BROTHERS gate honestly returns `deferred` (zero witnesses). Ed25519 signing is TODO (the SHA-256 hash is the integrity guarantee today). |
| Apothecary | **SEED** | Working deterministic compounder over the substrate + **12 herb monographs**; compound records are test-only. A real reference primitive, not yet a real apothecary. NOT medical advice. |
| Coach / lifelong tutor | **SEED** | Now **7 subjects / 69 units** (phonics 35, math 10, science 7, bible 5, reading/writing/social-studies 4 each), served via `/curriculum` to `/read.html` with interaction chunks (sound-it-out/blend for reading; a ten-frame to 20 for math). **Honesty note:** the tutor rendered BLANK behind HTTP 200s until 2026-06-16 -- `/curriculum` returns `{tracks:{...}}` but the loader read flat `d[key]`; fixed (`d.tracks||d`), proven (0->7 subjects), now guarded by `tools/check_surfaces.py` + `tests/test_surface_contract.py`. Still a demo-scale curriculum, not "capture a generation." |
| Community / contributors | **BUILT-EMPTY** | Full code (handles, Ed25519 anchor, append-only log, tier ladder) with **0 registered contributors**. |
| Peer federation | **BUILT-EMPTY** | Sync code + token-guarded `/chain/receive`, but **0 peers** (single node). |
| Missions (the Acts-2 local community) | **SEED** (2026-06-19) | Built: `api/missions.py` (append-only ledger) + REST (`GET /missions`, `GET /missions/{id}` content-negotiated crawlable HTML/JSON, rate-limited `POST` create/join/resource) + MCP tool `missions` + `site/missions.html`. People AND agents can join; resource shelf (offer/need). Honest guardrails baked in: software only SEEDS/FACILITATES (never feeds/houses/heals), points to Christ not idol, locally sovereign. **Still SEED:** 1 example mission, 0 real ones; no offline-gather flow, no per-mission sovereign organ, no food-system tie (long arc). |
| Giving / serve-the-least | **verifier REAL, flow CONCEPT** | `verify_giving` proves a *provided* donation chain conserves value (no leakage); **no money actually flows** through any surface. |
| Food system | **CONCEPT** | Long-arc intent; no implementation beyond nutrition/agriculture verifiers. Software serves it; it never "feeds" anyone -- do not claim otherwise. |

---

## Discovery & reach (made crawlable 2026-06-19) -- REAL surfaces; publish levers Matt-gated

The #1 bottleneck is discovery, not product. The unique verified content was JS-rendered
(invisible to search + AI retrieval, which already cite the site ~186x/30d); now it is
server-rendered and crawlable.

| Surface | State | The honest detail |
|---|---|---|
| Crawlable tested record | **REAL** | `/almanac/book` server-renders all ~1,684 entries (~1.35M chars; was ~1,640 on the JS page); `/curriculum/book` renders all 69 units; `/verified` content-negotiates to a hub linking all 627 proven claims. |
| Crawlable proofs (the moat) | **REAL** | `/seal/{hash}` server-renders the proof (claim, verdict, confirmed chain, integrity hash) with schema.org ClaimReview for browsers/crawlers; raw JSON for agents. Was a redirect to a JS shell. |
| Crawl gates | **REAL** | robots.txt unblocked the proofs and gave the named AI/search crawlers the same guardrails; llms.txt advertises the crawlable record. |
| The map, extended | **REAL** | `/grid.html` draws all 11 dimensions + a data-derived "two trees" view; `/grid/locate` (owned prose→dimension parser), `/grid/probe` (the arrangement's own disconfirmers), `/placeholders` (graded; SUSY honestly weakened, two-poles refined). |
| Scholarly grounding | **REAL** | `/scholar/lookup` + MCP `scholar`: OpenAlex/Crossref/Unpaywall; returns the lawful open-access copy or null (never a pirated copy). The workspace routes research queries here. |
| MCP registry listing | **PREPARED, not submitted** | `discovery/server.json` verified-ready (canonical remotes, valid schema, live `initialize` 200). Publishing authenticates as the operator -- Matt-gated, like the community-list PRs and a distribution channel. |

---

## Testing posture

- **Trust path: strong** -- 58/58 public benchmark + offline tests: the cardinal guarantee across 14 domains **+ 18 near-miss cases**, fail-closed paths, Scripture-tool honesty contracts, the anti-idol guardrail, and a surface contract that locks the tutor-shape fix.
- **Still thin** -- ~10 of 386 HTTP routes have dedicated tests; the broad MCP tool surface (data lookups) is lightly covered. The benchmark's live mode still depends on prod being up (the multi-domain proofs are offline). A standing surface health check (`tools/check_surfaces.py`) now verifies **16 public doors** return real DATA (curriculum units, brain nodes, proven-claim counts, grid dimensions, missions, and that a seal SERVER-renders its proof), not just 200 -- extended 2026-06-19 to cover the crawlable record + the Acts-2 missions. Offline source-contract guards (`tests/test_surface_contract.py`, 8 tests) lock the shapes so they can't be quietly removed.

## One honest line

The instrument -- verify, map, sovereignty -- is real and strong, and (2026-06-19) now
DISCOVERABLE: the verified record, the proofs, and the curriculum are crawlable, and the
registry listing is one operator command from live. The church -- people, agents, missions,
served need -- is built as code (Missions now a working SEED) but essentially unpopulated:
0 real missions, 0 contributors, 0 peers. The remaining levers are not more code -- they are
the operator-gated publish steps (registry, channels) and real people and content. Standing
on our own and being findable are done; being *found and joined* is the next threshold.
