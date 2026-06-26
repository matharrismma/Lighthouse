# Lighthouse 2.0 — The Floor, Defined

> "A position is not a position and can't be improved until it is identified. I cannot measure what I do not define." — the operator

1.0 is **vibe-coded** (not a slight — it found the shape). 2.0 takes the best of it and
starts fresh: **extremely targeted, scalable, and defined precisely enough to be measured.**
1.0 is frozen to local disk, kept, never deleted.

This document is the *definition* — the floor. Everything below is grounded in a full read of
the 1.0 codebase (≈58k lines in `api/`, ≈53k in `concordance_engine/`, 211 site pages), not memory.

---

## 0. The strategic shape: two faces, one engine

- **`.com` is secular.** A clean deterministic truth/claim-verification engine. No religious
  reference. Serves everyone.
- **`.org` carries the witness.** The same engine + the Christian overlay (canon, scripture,
  theology, the Shepherd, the SourceLayers).
- **They are NOT two codebases.** They are one core + a pluggable overlay, selected by config.

**Why this is coherent with the mission (the honest assay):** the secular core is the
*natural-law / base-programming* layer — math, physics, logic, the order written into creation,
true for everyone regardless of creed (Rom 2:14–15; "the earth is the LORD's," Ps 24:1). A clean
truth tool that clears falsehood **calibrates people toward reality by being true** — it points
to the Author without naming Him (general revelation / common grace). The `.org` overlay is
special revelation made explicit. This is the recorded discipline
`calibrate_men_not_build_toward_god` made architectural: the `.com` is the porch, the `.org` is
the sanctuary, and the door between them is **open and honest**.

**The one guardrail (load-bearing):**
1. **No bait-and-switch.** `.com` is a genuine truth tool, never a covert funnel. Honest on both faces.
2. **Secular ≠ watered down.** The seal discipline and **0 false-positives** hold identically on
   both faces. Truth is His whether or not it is labeled.
3. **The witness is full and discoverable, never hidden in shame** (Mk 8:38). `.org` keeps the
   whole gospel; the `.com` plainly links to it.
4. **Decrease still wins** (John 3:30): success = the user leaves nearer the truth and needing the
   tool less.

---

## 1. THE FLOOR — the irreducible primitives

2.0 is exactly these seven primitives. Anything not serving them is out of scope for v1.

| # | Primitive | Definition | How it is MEASURED |
|---|-----------|------------|--------------------|
| 1 | **Claim** | A structured assertion: `{domain, spec}` (or plain text the router resolves). | Schema-valid / not. |
| 2 | **Verifier** | A *pure deterministic function* `spec → verdict + worked trail`. No I/O, no LLM. | Same input → same output, always. |
| 3 | **Verdict** | `PASS \| REJECT \| QUARANTINE` + the **worked math** (the elimination trail). | Reproducible; benchmark: 58/58, **0 false-positives**. |
| 4 | **Seal** | Content-addressed (SHA-256 of canonical JSON) record of `{claim, verdict, trail}`. | Anyone can re-fetch and re-verify the hash. |
| 5 | **Ledger** | Append-only hash chain of seals. | Chain integrity verifiable end-to-end. |
| 6 | **Ranker** | Retrieval over the keeping (precedent + corpus) by IDF/full-text. | Relevant precedent returned for a query. |
| 7 | **Overlay** | A pluggable identity + verifier + source-layer set. `.com` = secular; `.org` = +witness. | `.com` build contains zero religious symbols. |

**The definition in one line:** *every answer is a `(verdict, trail, seal)` — three things, each
independently checkable.* That is the floor. That is what "hands you a receipt, not a trust-me"
means, made precise. The measure of 2.0 is: **reproducibility, zero false-positives, and
re-checkability** — and now they are defined, so they can be tracked release over release.

---

## 2. The secular / .org split is a config switch (not a fork)

Grounded finding: the core is **~6/10 separated today, ~9/10 after five small refactors.** The
religious coupling is shallow and enumerable. The overlay seam:

| Hotspot (1.0) | Today | 2.0 fix |
|---|---|---|
| `verifiers/__init__.py` imports `scripture` **eagerly**, runs on every packet | tangled | lazy; registered only by the overlay |
| `witness_record.py` hardcodes `SourceLayer = jesus_words\|bible\|apostles\|elders` | tangled | `layers.py`: secular `primary/secondary/tertiary/reference`; overlay registers the witness layers |
| `__init__.py` `IDENTITY` broadcasts "serves Jesus Christ" at import | tangled | `branding.py`; identity injected at instantiation per face |
| `verifiers/witness.py` enforces the religious layer enum | tangled | valid-layers injected via `EngineConfig` |
| `verifiers/governance.py` embeds `1 Cor 14:40` as the anchor | light | keep the structural check; anchor moves to overlay |
| `grid.py` has a `"scripture"` axis | minor | axes pluggable; overlay-only |
| `engine.py` WAY gate comments cite "Biblical Alignment Protocol"; `"canon"` scope | minor | rename gate `PATH`; neutral scope names |
| `mcp_server/tools.py` imports `theology_doctrine` eagerly | light | conditional registration by `CONCORDANCE_MODE=com\|org` |
| `api/app.py` mounts `/shepherd /codex /scripture /teach` unconditionally | light | overlay router, mounted only on `.org` |

**Verifier inventory (grounded): 57 secular, 4 religious** (`scripture`, `scripture_anchors`,
`theology_doctrine`, `witness`) + 1 hybrid (`governance`, structural check is secular). The
secular set spans math, physics, chemistry, biology, earth/space, finance, law, CS, linguistics,
etc. — a genuinely strong standalone product.

---

## 3. Architecture

```
concordance-core/                 # PURE secular library — sovereign, stdlib-first
  engine.py        validate_and_seal: claim → gates → verifiers → (verdict, trail, seal)
  gates.py         RED · FLOOR · PATH · (wait/witness)  [secular naming]
  verifiers/       57 pure deterministic domain verifiers
  cas.py           content-addressed seal store (SHA-256, 256-way sharded)  [already clean]
  ledger.py        append-only hash chain + precedent search                [already clean]
  ranker.py        IDF/full-text retrieval over the keeping
  layers.py        pluggable SourceLayer (secular default)
  branding.py      injected identity (per face)
  config.py        EngineConfig(mode, layers, identity, overlays)
  agent/  coach/   secular orchestration (NL→domain dispatch, authorization)
  heavy deps lazy: sympy/scipy/numpy load ONLY for a math/physics/stats claim

concordance-overlay-faith/        # the .org-only overlay (a separate installable)
  canon.py · scripture verifier · theology_doctrine · witness layers · scripture retrieval
  registers itself into EngineConfig when CONCORDANCE_MODE=org

web/                              # thin FastAPI — split by the seams app.py never had
  handlers/    HTTP routes by concern (verify, keep, intake, public)
  services/    domain logic (no business logic inside route functions)
  generation/  pluggable LLM adapters (the non-deterministic edge, always flagged)
  data/        storage abstraction (cards, ledger, cas, corpus)
  middleware/  auth · telemetry · safety
  overlay/     the .org-only routers (/shepherd /codex /scripture) — mounted by config
  app.py       wiring + router includes ONLY

site/                             # a real build, not 211 hand-authored pages
  src/ + templates/ (Jinja2/Eleventy) → dist/ (static)
  .com build = secular pages; .org build = secular + witness pages; shared base
```

**Principles:** (a) the core is *pure and stateless* → horizontally scalable; the only
serialized point is the ledger write (single-writer; move to Postgres single-writer/many-readers
when it needs to scale). (b) Web never embeds domain logic. (c) The generative/LLM edge is a
named, swappable layer, always flagged "drafted, not verified," never sealed. (d) `.com`/`.org`
diverge only in config + which overlay is installed — **95%+ shared code.**

---

## 4. Port (the gold) vs Shed (the debt)

**PORT — the crown jewels (mostly already clean):**
- The deterministic core: `engine.py`, `gates.py`, `cas.py`, `ledger.py`, `packet.py`,
  `witness_record.py`, `signing.py`, `validate.py` — **zero non-stdlib deps in the hot path.**
- The 57 secular verifiers (+ the data contracts they validate against).
- The data contracts: ledger hash-chain, CAS seal store, the card schema, the case-store
  nearest-neighbor index (rebuildable from the ledger).
- The MCP server (conditional tool registration) + the secular agent/coach orchestration.
- The benchmark (`tools/benchmark_public_verify.py`) → the 2.0 regression gate.

**SHED — into the frozen 1.0 archive, not into 2.0:**
- `api/app.py` as a 21k-line monolith → **refactor into the seams above** (don't port the blob).
- 800 individual `data/cards/*.json` files → **migrate to keyed/indexed JSONL** (one disk hit, not 800).
- 211 hand-authored HTML pages, no build step → **rebuild lean with templates**; `site/_archive/` deleted.
- `lw/` (38,242 iteration-history files), `build/`, `dist/`, `android/`, `mac/`, `integrations/`,
  `training/`, `outreach/`, `research/`, 40+ root handoff/status markdowns → **archive.**
- Every non-floor subsystem (radio, serial, apothecary, schools, market, community, …) → **archive;
  re-admit to 2.0 only when it earns its place against the floor.**

Net: ~40k files → a lean ~4–5k-file 2.0 repo + a frozen `1.0-archive/`.

---

## 5. Targeted scope + scalability

**v1 (targeted) — IN:**
- `concordance-core` (the seven primitives) + the secular overlay default.
- The MCP server (the agent surface — this is where the engine already gets used).
- A lean API exposing `check` → `(verdict, trail, seal)` + seal fetch + ranker search.
- A minimal site: what the engine is, a live "bring a claim → get a receipt" demo, the seal viewer.

**v1 — DEFERRED (archived until earned):** everything else. Scope discipline is the cure for the
168-page sprawl. A subsystem returns only when it serves the floor and pays for its complexity.

**Scalability properties (designed in, not bolted on):** pure verifiers = stateless = scale
horizontally; CAS is already 256-way sharded; lazy heavy deps = fast cold start for the common
case; config-driven faces = no fork to maintain; the single serialized write (ledger) is the one
known bottleneck, with a known fix path (Postgres single-writer).

---

## 6. Freezing 1.0

`.com`/`.org` 1.0 → a read-only local archive (full history, `lw/`, all subsystems, all docs).
Kept as the reference record — the shape that taught us the floor. Nothing deleted; everything
demoted to "frozen reference." 2.0 starts in a clean repo and ports only the gold.

---

## 7. Open forks (the operator's calls)

1. **`.com` positioning + name** — what the secular product *is* to a stranger
   (e.g. "a verification engine that hands you a re-checkable receipt"). Affects copy + the demo.
2. **The targeted v1 scope** — core+verify only (recommended), or +keeping/corpus, or +a secular
   Q&A (Shepherd without the witness)?
3. **Repo strategy** — one repo, two build configs + an optional faith-overlay package
   (recommended), vs. two repos.
4. **When to scaffold** — freeze 1.0 and stand up the empty 2.0 core skeleton now, or keep refining
   this definition first.
```
