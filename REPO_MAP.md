# REPO_MAP — the whole repository, in one place

**Purpose:** a durable inventory so no session (human or AI) re-derives what already exists. Written 2026-06-12 after a full seven-part survey. Counts are approximate; **`GET /capabilities` is the live source of truth** for verifier/tool/domain counts — never hardcode them. For working conventions read [AGENTS.md](AGENTS.md) and [FOR_AI_AGENTS.md](FOR_AI_AGENTS.md); this file is the "what exists, and where" map.

**One-line:** a Christian, Scripture-anchored **verification engine** (serves Jesus Christ) that runs claims/decisions through four deterministic gates (RED -> FLOOR -> BROTHERS -> GOD), VERIFIES derivations across ~66 domains, NEVER fabricates, and seals tamper-evident receipts. Live at https://narrowhighway.com. Repo `github.com/matharrismma/Lighthouse`.

> **READ THIS FIRST — three traps that waste tokens:**
> 1. **The engine is huge and already built.** ~66 verifiers, ~50 API endpoints, 187 site pages, 6 formal canons, full test+benchmark suite, media pipeline, client apps. Before building ANYTHING, check here + grep + `/capabilities`.
> 2. **There are duplicate/archived engine trees.** Canonical engine = **`src/concordance_engine/`**. `lw/01_engine/` and `lw/_archive_iterations/` are OLD snapshots (one slated for deletion). Don't read/edit the archives as if live.
> 3. **The almanac corpus (`data/almanac/entries.jsonl`) is a thin discovery layer on top of the canons.** A low "connection-card count" for a domain does NOT mean the domain is thin — check the canon + verifier + packets first (the biology miscount, 2026-06-12).

---

## Where it lives — the five surfaces (routing)

One engine, several faces; each surface has one job. Public GitHub holds code + a taste, **never the full corpus** — the moat is the live system + trust, not the static data. "Can't get lost" is answered by `.org` (verified truth, permanent + citable) plus a private backup of the full substrate — not by putting the corpus on public GitHub.

| Surface | Role | What's there |
|---|---|---|
| **narrowhighway.com** | the app | the verifier in use, the MCP for agents, decision/walk surfaces — the operator's & agents' working tool |
| **narrowhighway.org** | core / authority / registry | the unchanging reference: `/identity`, `/verified` (sealed proofs), `/atlas` (the map), the codex, the canons. Where verified truth lives permanently. **LIVE.** |
| **narrowhighway.tv** | gift / sprawl | TV & radio for the whole family, the Almanac (human face), channels, games, home-economics. Free, curated, given. **LIVE.** |
| **GitHub (public)** `matharrismma/Lighthouse` | open foundation | code, canons, docs, REPO_MAP, the wedge — *how it works + a taste*. NOT the 52MB `data/cards`. |
| **Private backup** (Cloudflare R2) | insurance | encrypted tarball of the full substrate (`data/cards` + seals/ledger), closing the node single-point-of-failure. `local/backup_to_r2.sh`. |

Rule: `.com` = the working tool · `.org` = the authority you cite · `.tv` = the gift you give · GitHub = how it works · R2 = the vault.

## The two trees (built 2026-06-12) — read this for the recent core

The corpus is now organized as **two trees on one ground** (`data/codex/NESTING.md`):
- **Math tree (the Tree of Knowledge — "numbers don't lie"):** the six domain canons + the periodic table of recurring forms, crowned by `connection_reality_is_mappable`. The gap analysis (`data/codex/GAP_ANALYSIS.md`) audited all six canons.
- **Language tree (the Tree of Life — the Word):** **88 `kind:'teaching'` cards** — every teaching of Christ from the Beatitudes through Revelation, each on its original Greek (via `/scripture/original`), crowned by `teaching_the_words_of_christ_are_the_architecture`. Map: `data/codex/TEACHINGS_OF_CHRIST_REVIEW.md`.
- **The moat between them:** **18 `bridge_*` cards** (origin `moat_dig_two_trees`) — each a teaching/sign of Christ bonded to a *verified, sealed* form (mustard=exponential, leaven=diffusion, words-remain=invariant, the 153 catch=the 17th triangular number per Augustine, …). The un-copyable asset: a word + a proof, laced.
- **Surfaces:** `site/proof-bridges.html` (the checkable-witness wall — every bridge with a live seal), `site/ten-second-proof.html`, `docs/THE_WEDGE.md` (the agent-floor pitch).
- **Measures:** `tools/fruit_ranking.py` + `data/codex/FRUIT_RANKING.md` (the fruit test, turned inward — which ideas bear most; re-runnable).
- **Backups:** `local/backup_to_drive.ps1` (the 12 TB D: vault, daily) + `local/backup_to_r2.sh` (offsite option).
- **RESERVED:** the keystone — the *join* of the two trees, Christ the Logos in whom both hold (Col 1:17 / John 1). Pointed at from every side; set only by the operator. Never auto-sealed.

## Top-level layout (1,417 tracked files + untracked data)

| Dir | Files | What it is |
|---|---:|---|
| `lw/` | 320 | The "Lighthouse" layers: seed, scripture source, **6 canons**, 4-gate kernel, frontend demos, training data, NHANES validation study, hardware playbooks, calibre, ledger, archives |
| `site/` | 227 | The public website (187 HTML pages) — no build step, plain HTML/CSS/JS + PWA |
| `src/` | 162 | **The Concordance Engine** — verifiers, domains, gates, signing, witness, ledger, polymathic, scripture/LSP |
| `data/` | 124 tracked | Corpus, packets, trust indexes, codex indexes, archetypes, protocols (+ ~11K UNTRACKED `data/cards/`) |
| `tools/` | 122 | Reusable utilities: surfacers, generators, media/FAST pipeline, ops |
| `api/` | 92 | FastAPI server — ~50 endpoints incl. `POST /derivation/verify`, the live moat |
| `scripts/` | 88 | Extractors, ingesters, **seeders** (`seed/seed_all.sh`), page-wiring |
| `tests/` | 75 | Test suite across ~60 domains + engine + API + MCP |
| `eval/` | 38 | Eval harness + head-to-head benchmark (Claude alone vs +tools) |
| `local/` | 34 | Operator/deploy tooling (backup, docker, systemd, diagnose) |
| `docs/` | 26 | Architecture + operator + hosting docs (CANON, LAYERS, KERNEL, GLOSSARY...) |
| `android/` | 22 | Native Android client (journal/ledger, Web Share, NFC) |
| `examples/` | 21 | Sample decision packets per domain |
| `client/` | 14 | Capture-anywhere bridges: telegram, meshtastic, nostr, ipfs, tor, email |
| `integrations/` | 2 | `odysseus` (PewDiePie self-hosted-AI piggyback) |
| Root | ~28 | Orientation docs (AGENTS, FOR_AI_AGENTS, COOKBOOK, OPERATOR, ROADMAP, GLOSSARY, KNOWN_ISSUES), `concordance_mcp_server.py`, Dockerfile, railway.toml, pyproject.toml |

---

## `src/concordance_engine/` — the engine (canonical)

- **`verifiers/*.py`** (~66) — the un-copyable core. Each exposes `run(packet) -> list[VerifierResult]` (CONFIRMED / MISMATCH / NOT_APPLICABLE / ERROR). Covers exact sciences (math, physics, chemistry, statistics, number_theory, geometry, linear_algebra), physics extensions (atomic, nuclear, optics, thermo, quantum_computing, ephemeris), life sciences (biology, genetics, ecology, nutrition, medicine, exercise), earth sciences (astronomy, meteorology, geology, oceanography, hydrology, soil, geography), engineering (electrical, materials, construction, manufacturing, networking, operations_research, energy), governance/social (governance, economics, finance, labor, law, real_estate), language/logic (linguistics, formal_logic, music_theory, rhetoric, philosophy, information_theory, cryptography, cybersecurity), and the cross-cutting `scripture.py`, `witness.py`, `phase.py`, `theology_doctrine.py`, `layer_zero_grounding.py`.
- **`domains/*.py`** (~36) — per-domain attestation validators (`validate_red`, `validate_floor`).
- **Engine core:** `engine.py` (4-gate orchestration), `gates.py`, `packet.py`, `validate.py`, `walkthrough.py`/`atlas.py` (Socratic renderers — close with a question, never a verdict), `grid.py` (36-axis scaffold, 7 structural members).
- **Crypto/seal:** `signing.py` (Ed25519 canonical), `witness_record.py` (frozen, source-hierarchy anchors: jesus_words->bible->apostles->elders), `ledger.py` (append-only SHA-256 chain), `case_index.py`/`cas.py` (content-addressed), `nostr_anchor.py` (BIP-340), `lsp.py` (deterministic chunk+hash for scripture-edition integrity), `investment_packet.py` (privacy bands).
- **Scripture:** `scripture_retrieval.py` (WEB + Strong's), original-language Greek/Hebrew (MorphGNT / Westminster Leningrad).
- **Cross-domain:** `agent/` (poly_agent, claude_agent oracle, dispatch = deterministic regex NL->domain, rule_extractor = self-teaching, quarantine_keeper), `coach/` (steward corridor + tokens), `synthesist.py`, `nl_to_packet.py`.
- **MCP:** `mcp_server/server.py` + `tools.py` (the public agent tool surface).

## `api/` — the live server (FastAPI, narrowhighway.com)

- **Moat endpoints:** `POST /derivation/verify` (seal a multi-step proof chain -> `receipt.cite_url` = `/seal/<hash>`), `POST /derivation/solve`, `POST /narrow/eliminate` + `/narrow/verify` + `GET /narrow/predicates`.
- **Discovery (public):** `GET /identity`, `/capabilities` (live counts), `/verified` (sealed-proof index), `/seal/{ref}`.
- **Knowledge:** `codex.py` (`/codex/index/scripture` cross-ref graph), `original_language.py` (`/scripture/original`), `apothecary.py` (`/apothecary`), `almanac`, `atlas.py`, `places.py`.
- **Triad:** `shepherd.py` (Socratic pre-flight interview), `cards.py` (everything-is-a-card substrate + walks), `narrowing.py`, `funnel.py` (private->public gate), `well_retriever.py`.
- **Operator (IP-gated `/keep/*`):** `keep_dashboard.py` (one aggregated snapshot), intake/quarantine/airlock, `engine_feed.py`, `trust_index.py`, `deep_health.py`.
- **Platform:** `market.py` (free marketplace), `wallet.py`, FAST channels (`fast_live.py`), `radio.py`, `periodicals.py`, `tts.py`, `local_llm.py` (Ollama fallback), i18n.
- Entry: `app.py` (mounts routers); `shema.py` (Deut 6:4-9 confession at startup).

## `lw/` — the wider Lighthouse

- **`00_seed/`** — minimal plantable public-domain package. **`00_source/`** — Scripture triangulation engine (Hebrew/Greek/WEB/Strong's + drift_check). **REUSABLE.**
- **`02_canons/`** — SIX formal domain canons (**biology, chemistry_full, computer_science, mathematics, physics, statistics**), each with `canon.yaml` (module registry), `core/*_core.yaml` (FROZEN NOUNS = the domain primitives/slots), modules (with triggers), schema, templates, validator. **THIS IS THE AUTHORITATIVE GRID** — gap analysis runs against it (see `data/codex/GAP_ANALYSIS.md`). Biology's 10 frozen nouns: CELL, COMPARTMENT, GENOME, EXPRESSION, PROTEOME, METABOLISM, SIGNAL, FEEDBACK, FITNESS, POPULATION.
- **`03_kernel/`** — minimal 4-gate reference: `the_way_kernel_min.py`, `keeper_gate.py`, `problem_engine.py`, `firewall.py` (hardware gate state machine).
- **`04_frontend/`** (four-gates demo, edge PWA), **`05_training/`** (LoRA train/eval jsonl), **`06_validation/`** (NHANES pre-registered falsification study — portable, rigorous), **`07_hardware/`** (Node Hardware Playbooks), **calibre** (formation engine MILK->MEAT), **ledger** (precedent JSONs), **`_archive_iterations/` (OLD — do not use)**.

## `site/` — public web (187 HTML pages, no framework)

Sections: **engine** (index, how-it-works, gates, theory, verifiers, walks) - **knowledge** (codex + xref/themes/seal, atlas/map, apothecary, almanac/daily/today/seeds/recipes/shelves, cards/cards-dev) - **faith/community** (prayer, testimony, curriculum, household, shepherd-room, assembly + channels: hymns/sermons/scifi-theatre/hundred-acre) - **media** (listen, radio, podcast-theatre, watch, hymns) - **games** (chess, bible-trivia, wilderness-trail) - **tools/** (calculator, dictionary, thesaurus, maps, music, periodic, typing, wiki, graph, draw) - **submission** (scribe, publish, submit-*, curate, packets) - **identity** (profile, you, about, welcome, install) - **operator** (dashboard, operator, engine-queue, inbox) - **wallet** (transparency, help). Shell: `nh-shell.js/css`, `vibe.css`, PWA (`manifest.json`, `sw.js`), i18n. `mac/` + `windows/` wrappers. **Do NOT rebuild any of these — extend.**

## `data/` (tracked) — the substrates

- **`almanac/entries.jsonl`** (~1,414) — the verified corpus (connections, assessments, sayings, protocols). The discovery-loop output. Deployed by scp to the node.
- **`packets/*.jsonl`** (~50 domains) + **`trust_index/*.json`** (~50) — example packets + per-domain confidence. The test/validation harness data.
- **`codex/`** — STRUCTURE/AUTHORITY_SPINE/NESTING/GAP_ANALYSIS/REPO_MAP docs + generated indexes: `cards_dev.json` (~5,119 cards), `connections.json` (~211), `scripture.json` (~2,921 xrefs), `themes.json` (~138).
- **`archetypes/`** (bible/history/literature patterns), **`protocols/scripture_protocols.jsonl`** (~36), **`agent_training/*.jsonl`** (oracle feedback logs), **`body/layers.jsonl`** (5 body systems), **`herbs/monographs.jsonl`** (12), **`apothecary_compounds/`**, **`science/units.jsonl`**, **`mind/practices.jsonl`**.
- **UNTRACKED:** `data/cards/` (~11,085 flat `card_n_*`/`card_c_*` files — Easton dictionary, patristics, classics, connections). Deployed by scp/tarball (LF filelists; node uses `python3`).

## `tools/` + `scripts/` — reusable (don't rebuild)

- **Seeders:** `scripts/seed/seed_all.sh` (5 waves, ~1,431 seeds, ~60 domains). **Extractors:** `extract_easton.py` (3,962 entries), `extract_*` (WEB, classics, devotionals, proverbs, pilgrim, aesop...). **Surfacers:** `surface_easton/wisdom/psalms/patristics...` (JSONL -> cards with authority tiers).
- **Discovery/moat:** `grow_verified.py`, `discover_connection.py`, `suggest_connections.py`, `axis_coverage.py`.
- **Media/FAST:** `build_pilot.py` (idempotent video orchestrator), `fast_channel_*` (HLS/MRSS/YouTube-live/bumpers), `animation_orchestrator.py`, `render_*`.
- **Ops/cost:** `engine_daily.py` (nightly entry point), `engine_watchdog.py`, `steward_airlock.py` (deterministic quarantine triage), `spend_guard.py` (Anthropic budget ceiling), `witness_pool_items.py` (Deut 19:15 automation), `model_registry.py`.

## tests/ + eval/ — what's proven

- **tests/** (~75): engine 4-gate pipeline, ~60 domain verifiers, API, CLI, MCP, witness/ledger/journal, signing. Run: `PYTHONPATH=src python tests/test_engine.py` (+ verifiers/cli/mcp/canon).
- **eval/**: gate-extraction eval (50 items, ~76% heuristic baseline) + **`benchmark/`** (Claude alone vs Claude+tools, chemistry/physics/stats, real cost ~$0.05/run). A documented 722-claim deterministic benchmark reported 100%/domain (verify before quoting).

## Clients & integrations

- **`android/`** native client; **`client/`** capture-anywhere bridges (watch-folder, Apple Shortcut, telegram, meshtastic LoRa-mesh, nostr, ipfs, tor, email); **`local/`** deploy/ops; **`integrations/odysseus`** (offer NH's MCP as the verification floor for self-hosted AI).
- **MCP:** `concordance_mcp_server.py` -> `src/.../mcp_server/`. OpenAI-required `search`+`fetch` tools added for ChatGPT discoverability (connect `https://narrowhighway.com/mcp`).

---

## Immutable decisions (do NOT contradict — from AGENTS.md/CANON)

1. Gate order **RED -> FLOOR -> BROTHERS -> GOD** is fixed. 2. Engine **never self-confirms** (BROTHERS=witness, GOD=wait exist for that). 3. **O(1) authority validation**, never O(n^2) consensus/voting. 4. **Layer 0 (Scripture) is locked** — original languages + Strong's + WEB; no paraphrase drift. 5. **Ledger append-only, tamper-evident.** 6. **MCP tools never raise** — return `{"status":"ERROR",...}`. 7. **No `final_answer`** — the engine eliminates what is false; the trail IS the reasoning. 8. README/`/capabilities` are the source of truth for counts.

## Ops constraints (this project, standing)

Deploys = **scp to `nh@nh-engine-1:~/Lighthouse/`** (git is backup-only; node uses `python3`; LF filelists). **NEVER `git add -A`** (untracked secrets: `Runway API.txt`, `client_secret_*.json`, `Concordance passphrase.txt`); commit by explicit path. **Claude commits to main; Matt runs `git push`** (interactive). Engine/seal = PROD only. Operator-gated (surface, don't do): outward posts/publishing, `witness --apply`. PURE ASCII output (Windows cp1252). **Col 1:17 / the Jesus-phase keystone + the witness-list are RESERVED for Matt's lead.**
