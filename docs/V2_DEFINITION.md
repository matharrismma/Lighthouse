# Lighthouse 2.0 — The Floor, Defined

> "A position is not a position and can't be improved until it is identified. I cannot measure what I do not define." — the operator

1.0 is **vibe-coded** (not a slight — it found the shape). 2.0 takes the best of it and
starts fresh: **extremely targeted, scalable, and defined precisely enough to be measured.**
1.0 is frozen to local disk, kept, never deleted.

This document is the *definition* — the floor. Everything below is grounded in a full read of
the 1.0 codebase (≈58k lines in `api/`, ≈53k in `concordance_engine/`, 211 site pages), not memory.

---

## 0. The strategic shape: one foundation, two reaches

**The foundation is the Bible.** Not a module, not an add-on — the bedrock the whole engine is
built on and from: "other foundation can no man lay than that is laid, which is Jesus Christ"
(1 Cor 3:11). The truth-commitment (the engine serves truth because Truth is a Person, John 14:6),
the design disciplines (conduit not source · points-not-idol · witness not proof · decrease), and
Scripture in the substrate are foundational on BOTH surfaces. **We are not hiding from the faith.**

From that one foundation the engine reaches the world two ways:

- **`.com` — the reach.** A secular *surface*. It meets the world in the world's own language —
  truth, verification, a re-checkable receipt — with no religious wording on the surface. This is
  Paul at the Areopagus (Acts 17): reasoning from what they already accept, quoting their own
  poets, never once moving the foundation. Speaking the hearer's tongue is not shame; it is love
  (1 Cor 9:19–22, "all things to all men, that I might by all means save some").
- **`.org` — the witness.** The same engine with the foundation made *explicit* on the surface:
  canon, Scripture, theology, the Shepherd, the SourceLayers — the Rock named.

**One engine, one foundation, two surfaces — chosen by config.** The faith is NEVER the removable
layer; if anything, the secular presentation is the outward reach built on the rock. `.org` does
not *add* the foundation — it *surfaces* it. `.com` does not *remove* it — it stands on it and
openly links to it.

**Why this is the mission, not a retreat from it:** all truth is already His — "in whom are hid
all the treasures of wisdom and knowledge" (Col 2:3); "the fear of the LORD is the beginning of
knowledge" (Prov 1:7); math and logic are the order written into creation (Rom 2:14–15; Ps 24:1).
A clean truth tool stands on the biblical foundation whether or not its surface says so, and it
**calibrates people toward reality by being true** — the recorded discipline
`calibrate_men_not_build_toward_god` made architectural. The `.com` is the porch, the `.org` the
sanctuary, the door between them open.

**The guardrail (load-bearing):**
1. **No bait-and-switch.** `.com` is a genuine truth tool, never a covert funnel. Honest on both surfaces.
2. **The surface differs; the foundation never does.** The seal discipline and **0 false-positives**
   hold identically on both — truth is His whether or not it is labeled.
3. **Never hidden in shame** (Mk 8:38). The witness is full on `.org` and openly linked from `.com`.
4. **Decrease still wins** (John 3:30): the user leaves nearer the truth and needing the tool less.

---

## 0.5 The build discipline: rebuild it like a watch (Calibre 44)

2.0 is engineered like a fine mechanical movement — the operator's **Calibre 44** package is the
exemplar (kept in `engineering-reference/`). The horology maps onto the engine, principle for principle:

- **Christ at the center — the mainspring.** A watch's power comes from the mainspring at the heart,
  and every wheel turns from the center. Christ is the center of the architecture and the power that
  drives the train ("by him all things consist," Col 1:17). Nothing is hidden — the exhibition
  caseback shows the movement: `.org` shows it named, `.com` shows it working.
- **Machine-honest finish.** "No Geneva stripes pretending to be hand-applied. The beauty is the
  accuracy of the machine work itself." → the engine never launders. The receipt, the seal, the
  reproducibility ARE the beauty; no decoration pretending to be what it is not.
- **Any shop can fix it.** "No proprietary tools, no single-source materials, no factory return."
  → sovereign + stdlib-first. Any competent engineer can open it, understand it, and service it with
  standard tools — no vendor lock-in; the community maintains it forever, offline.
- **Harrison's constancy.** Flat torque → a constant rate at any state of wind. → determinism: the
  same claim yields the same `(verdict, trail, seal)` on the first call and the millionth.
- **Railroad ruggedness.** Overbuilt "not because the engineering demands it, but because the owner's
  life does." → fail-closed, 0 false-positives, the benchmark as proof — overbuilt for the one who
  depends on it.
- **The unibody.** "The case IS the mainplate" — one integrated block, no redundant ring or disc →
  38 mm usable from a 42 mm case. → eliminate the intermediary cruft (the 1.0 monolith + duplication);
  integrate; more capability from fewer parts.
- **Every omitted complication is a part that cannot fail.** "No manual wind (3 fewer parts), no
  seconds hand (removes the hacking complication) — one fewer mechanism to fail, one fewer thing to
  explain." → the scope discipline: a feature earns its place against the cost of its failure surface,
  or it stays out.
- **A bounded, counted parts manifest, locked before build.** 44 functional parts, 17 jewels, pivot
  map solved, open items CLOSED, Rev J.1 **LOCKED**. → the floor is enumerated and locked before we
  machine it. "I cannot measure what I do not define" — the parts manifest IS the definition.

The complications (the verifiers, the seal, the ledger, the ranker) mount on the going train and are
powered from the center. Build the movement first; add a complication only when it has earned its
place and its mechanism is solved.

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
| 7 | **Surface** | The face over the shared foundation — identity + which layers/verifiers are *surfaced*. `.com` = secular reach; `.org` = explicit witness. | `.com` surface shows zero religious wording. |

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
concordance/                      # THE MOVEMENT — one engine, sovereign, stdlib-first, on the foundation
  foundation/      the mainspring + mainplate: truth-model · the disciplines · Scripture substrate
                     (Christ at the center; load-bearing on BOTH surfaces)
  engine.py        the going train — validate_and_seal: claim → gates → verifiers → (verdict, trail, seal)
  gates.py         RED · FLOOR · PATH · (wait/witness)
  verifiers/       57 secular complications (always) + scripture · theology · witness (surfaced on .org)
  cas.py           content-addressed seal store (SHA-256, 256-way sharded)        [already clean]
  ledger.py        append-only hash chain + precedent search                      [already clean]
  ranker.py        IDF/full-text retrieval over the keeping
  layers.py        SourceLayer per surface (secular default; witness layers on .org)
  branding.py      identity injected per surface (no hardcoded identity at import)
  config.py        EngineConfig(surface="secular"|"witness") — foundation shared either way
  agent/  coach/   secular orchestration (NL→domain dispatch, authorization)
  heavy deps lazy: sympy/scipy/numpy load ONLY for a math/physics/stats claim

web/                              # THE CASE + DIAL — thin FastAPI, split by the seams app.py never had
  handlers/    HTTP routes by concern (verify, keep, intake, public)
  services/    domain logic (no business logic inside route functions)
  generation/  pluggable LLM adapters (the non-deterministic edge, always flagged)
  data/        storage abstraction (cards, ledger, cas, corpus)
  middleware/  auth · telemetry · safety
  witness/     the witness routers (/shepherd /codex /scripture) — surfaced when surface=witness
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
3. **Repo strategy** — one repo, two surface-builds, the witness config-gated inside the one
   engine (recommended), vs. two repos.
4. **When to scaffold** — freeze 1.0 and stand up the empty 2.0 core skeleton now, or keep refining
   this definition first.
```
