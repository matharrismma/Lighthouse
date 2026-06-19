# Punch list — 2026-06-19

Supersedes the 2026-05-13 root `PUNCH_LIST.md` (that era's Coach/lens work shipped).
Posture: people, fruit, and multiplication are God's part. This is only what we build.

Tiers are **order of attack**, not what to keep — everything here is in scope.
`[me]` = I can do it · `[Matt]` = your action · effort S/M/L.

---

## ✅ Done this session (for reference)
- Front door re-anchored to lead with verify + the connected map (hero + i18n).
- Operator/back-office pages pulled out of public discovery (robots + de-link).
- MCP stdio bug fixed (scholar → engine package; arrangement/missions → `_engine_get`).
- Scholarly grounding: 19 source families carry re-checkable primary citations.
- Registry listing copy → the receipt hook (server.json + .well-known/mcp).
- Site audit tool + `SITE_AUDIT.md`; sparsity enrichment (tune 28.4¢→24.7¢).

---

## TIER 1 — critical path (the name gets out AND lands somewhere real)

- [ ] **Re-sync `server.json` to the registries** — the listing hook changed; push it. `[Matt]` S
- [ ] **Site reorg step 3: merge duplicate families → canonical hubs with 301 redirects** — 9 map pages → atlas+breath+grid, 9 verify → verifiers+gauntlet, 5 learn → curriculum+read, codex dupes. The real 167→~30 reduction. `[me]` L
- [ ] **SSR / prerender the homepage + key pages** — today the best pages are client-JS-rendered, so a search for "Narrow Highway" hits a shell. The capture half of the citation flywheel. `[me]` M
- [ ] **Validate the spectral arc: does the tune / decay-rate TRACK verified correctness?** — the load-bearing honesty test. Until this passes, the map's "in-tune = true" stays resonance, not evidence. `[me]` M
- [ ] **Re-run `site_audit.py` after each prune step** — confirm the surface actually shrank, nothing rotted. `[me]` S

## TIER 2 — next (consistency, measurement, the connection made navigable)

- [x] ~~**`/mcp.html` landing page → lead with the receipt hook**~~ ✅ 2af5e10 — h1/sub/title/og rewritten around the receipt; one story registry→landing.
- [x] ~~**Harden the `/mcp` 308 redirect**~~ ✅ 2af5e10 — the 308 is spec-correct; real fix was advertising the canonical `/mcp/` everywhere (well-known, mcp-stats, mcp.html) so clients don't hit it; 308 kept as safety net.
- [ ] **Make the map the navigation spine** — Atlas as the navigable connection-map (statistics↔geometry↔probability↔logic↔info-theory↔game-theory). "They all connect" as the IA, not decoration. `[me]` L
- [ ] **Durable install/citation counter + a glance-able dashboard** — measure whether the listings convert (you noted a counter exists; confirm it's readable as a before/after). `[me]` M
- [ ] **Site reorg step 4: retire personal essays + slim the 492 KB `coordinate-map` page** — works/dade/molasses/stack/seeds/odysseus/theory move to a clearly-separate section or go. `[me]` M
- [~] **Continue sparsity enrichment** — round 2 done (4da380d): symmetry +5 carriers → tune 24.7c→20.0c, p 0.385→0.125, alg.conn 29.6→42.6. Dissonance falling monotonically; not yet p<0.05. Ongoing — more thin-dim enrichment + the verification-tracking test. `[me]` M
- [ ] **Mobile/responsive pass** on the re-anchored front door + canonical hubs. `[me]` S

## TIER 3 — nice-to-haves (all in scope)

- [ ] **Set up the Custom GPT** with the Action (config is ready and parked). `[Matt]` S
- [ ] **Full auth-gate for operator pages** (beyond robots + de-link) — flip the coded-but-off Steward token gate. `[me]` M
- [ ] **Build the agent↔map 4 verbs** — locate / navigate-to-dual / see-gaps / grow. `[me]` M
- [ ] **Capture UGM as a placeholder + run the thermodynamics assay** when you give real numbers (mass/ΔT/output). `[me]` S
- [ ] **Curate the 1,706 harvested directives into teachings** — pay once for the past conversations. `[me]` L
- [ ] **Submit to the remaining aggregators** — PulseMCP, Glama, Smithery, mcp.so, Awesome-MCP. `[Matt/me]` S
- [ ] **Seed + operate ONE distribution channel** — pick one, schedule it, don't scatter. `[Matt]` M
- [ ] **Run the NHANES validation pipeline** (nested control systems) — verdicts are still pending a run. `[me]` M
- [ ] **More commentators / concord-score** — deepen the 5th-witness layer. `[me]` M
- [ ] **The fine-tune pass (own-model)** — corpus is prepared; the training run is yours. `[Matt]` L
- [ ] **Offline-bootable microSD image** — make Lockdown/sovereignty real, not aspirational. `[me]` L
- [ ] **Federation peer proof** — stand up a second instance, prove pull+push. `[me]` M
- [ ] **Consolidate the stale planning docs** — 10+ handoff/status/roadmap `.md` files at root have the same sprawl as the site; collapse to one. `[me]` S
- [ ] **app.py monolith decomposition** — deferred; needs supervision (risky live refactor). `[me]` L
- [ ] **~290 generated-file git-tracking decision** — decide what's tracked vs prod-only. `[me]` S

---

## Standing guardrails (apply to every item)
- Benchmark stays 58/58, 0 false-positives. Map never launders — report honest results.
- Engine verifies, never generates. Medicine/herb = reference, not advice.
- Points to Christ, never an idol. Conduit, not source.
- Deploy carefully (commit explicit paths, verify the runtime path, not just HTTP 200).
