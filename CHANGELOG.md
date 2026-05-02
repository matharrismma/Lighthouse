# Changelog

## v1.1.0 — 2026-05-01 (live deployment + Layer 0 + training kit)

### Live deployment
- **Engine is live at `https://narrowhighway.com`.** Windows desktop running uvicorn behind a Cloudflare Tunnel; cloudflared registered as a Windows service; `Concordance-API` scheduled task auto-starts uvicorn on user logon. Operational scripts in `local/`.
- **Tunnel token rotation script** (`local/rotate_tunnel_token.ps1`) — uses Cloudflare API to PATCH the tunnel secret without deleting the tunnel; saves the new connector token to `C:\Concordance\tunnel.token` (locked to user via ACL); reinstalls the cloudflared service.
- **Operational helpers**: `go_live.ps1` (one-shot bring-up), `finish_rotation.ps1` (rotation recovery), `repair_cloudflared.ps1` (service repair). All `local/*.ps1` now read tunnel token from `C:\Concordance\tunnel.token` rather than embedding it.

### New endpoints
- **`POST /reflect`** — preview-mode evaluation: same gates as `/submit`, no ledger write. For rehearsal before commitment.
- **`POST /confess`** — record an agent's recognition that a prior packet was wrong. New ledger entry with `overall: CONFESSION` referencing the prior seq + packet hash.
- **`GET /dispatch`** — filtered ledger search (domain, overall, packet_id, time range; AND semantics).
- **`GET /stats`** — aggregate ledger counts by verdict and domain.
- **`GET /about`** — service metadata: version, engine availability, layer-0 status, ledger total, chain validity, license, source, server epoch.
- **`POST /triangulate`** — interpretation drift check against original-language Strong's. Pairs with the `triangulate_claim` MCP tool.
- **`GET /scripture/{ref}`** and **`GET /strong/{number}`** — Layer 0 lookup endpoints.
- **`GET /favicon.svg`, `/favicon.ico`, `/robots.txt`, `/sitemap.xml`** — cleared 404s for crawlers and browsers.
- **`/submit` GOD-bypass for casual visitors** — public form gets meaningful PASS/REJECT verdicts instead of unwaitable QUARANTINE. `/validate` retains strict timing.

### Layer 0 (Scripture) integration
- **`src/concordance_engine/verifiers/scripture.py`** — moved from the historical `lw/01_engine/` subtree into the canonical engine; registered as a *cross-cutting* verifier (runs on every packet regardless of domain). Graceful when Layer 0 data isn't provisioned.
- **`drift_check.py` activated** — the only triangulation module that wasn't previously imported is now wired through `triangulate_claim()`. Returns per-Strong's-key semantic ranges so a reviewer can compare an interpretation claim to attested word meaning.
- **MCP tools**: `resolve_scripture_ref`, `word_study`, `verify_scripture_anchors`, `triangulate_claim`. Total tool count: 18.

### Ledger helpers
- `Ledger.get_by_seq()` — exact sequence lookup.
- `Ledger.get_by_packet_hash()` — hash lookup.
- `Ledger.iter_filtered()` — filtered iteration with AND semantics over domain / overall / packet_id / time range.
- `Ledger.stats()` — aggregate counts.

### Training kit (`training/`)
- **CATECHISM.md** — the doctrinal core: Q&A teaching the four-gate protocol from first principles.
- **SYSTEM_PROMPT.md** — the canonical prompt used in every training item (and at inference time).
- **FORMAT.md** — JSONL schema spec for training items.
- **BASELINE.md** — heuristic baseline (~76%) and tier targets for fine-tuned models.
- **`data/conversational_train.jsonl`** (20 items) and **`data/packet_train.jsonl`** (8 items) — hand-written seeds covering all five governance-cluster domains and gate halt points.
- **`loader.py`** — converts JSONL to HF datasets / OpenAI fine-tune / Anthropic Messages / eval-predictions formats.
- **`score.py`** — wraps `eval/run_eval.py` with cleaner CLI; reports vs. heuristic baseline.
- **`adapters/`** — minimal scripts for OpenAI fine-tune API, HuggingFace + PEFT LoRA, Anthropic Messages inference.

### Canon documentation
- **`docs/CANON.md`** — full canonical statement: Authority Stack (`GOD → WORD → RED → LAW → WAY`), kernel nouns, four gates, four actions, operator roles (Keeper / Scribe / Shepherd / Steward), three-ledger model, scope and wait windows.
- **`docs/LAYERS.md`** — system layers (Word → Kernel → Keeper → Steward → Vessel → Lighthouse) with per-layer responsibility, surface, contract, and failure mode.
- **`docs/CONCORDANCE.md`** — technical cross-reference index. Every architectural concern points at the right code or doc.
- **`docs/CONTRIBUTION_PROTOCOL.md`** — canon-scope vs domain-scope rules. Changes that touch kernel nouns, gate ordering, or hash-chain construction follow the same gates the engine enforces on packets.

### Site
- **`site/architecture.svg`** — visual flow diagram (agent → entry point → four gates → verdict → ledger), with Layer 0 as the foundation strip.
- **`site/index.html`** — same-origin `/submit` URL fix (was pointing at old Railway deployment); added favicon link tags; added `Cache-Control: no-cache` so future edits propagate immediately.
- **Static-site mount** — any unmatched GET falls through to `site/`, so the marketing/explainer pages (`how-it-works.html`, `verifiers.html`, etc.) advertised in `sitemap.xml` are now actually served.

### Other docs
- **`FOR_AI_AGENTS.md`** — welcome doc for arriving agents (separate from `AGENTS.md`, which is for coding assistants editing the repo).
- **`COOKBOOK.md`** — copy-paste recipes for chemistry, physics, statistics, CS, governance, multi-domain, scripture-anchored packets, and ledger reads.
- **`GLOSSARY.md`** — every term used across docs.
- **`SECURITY.md`** — vulnerability disclosure policy.
- **`ROADMAP.md`** — what's next.
- **`client/concordance_client.py`** — single-file Python client for the public REST API.

### License realignment
- README, `site/llms.txt`, `api/app.py` OpenAPI description, and `FOR_AI_AGENTS.md` now correctly say **Apache 2.0** (matching `LICENSE` and `pyproject.toml`). Previous claims of MIT in those files were stale from before the v1.0.6 license switch.

### Examples
- **`examples/sample_packet_scripture_anchored.json`** — governance packet with `scripture_anchors` to exercise the cross-cutting scripture verifier.
- **`examples/sample_confession.json`** — example body for `POST /confess` (note: this is not a packet, it's a confession request).

### Bug fixes
- **`/submit` no longer 500s on EngineConfig.** Earlier code passed `wait_window_seconds=0` to `EngineConfig`, which doesn't accept that argument. Removed the bogus arg and replaced with `now_epoch` advancement past the wait window — same intent, working code.
- **Server log encoding.** `start_server.ps1` now writes UTF-8 (was UTF-16 with BOM); uvicorn's stderr lines no longer get wrapped as PowerShell `RemoteException` records.

---

## v1.0.6 — 2026-04-29 (license correction)

- **Corrected the LICENSE file.** The previous LICENSE was a truncated placeholder ("Permission is hereby granted, free of charge, to any person obtaining a copy...") with no copyright holder named — meaning the repo was not actually licensed despite README/pyproject claiming MIT. Replaced with the full standard license text and a named copyright holder (Matthew R. Harris).
- **Switched from MIT to Apache 2.0.** Same permissive grant; adds an explicit patent license that protects users and contributors against patent claims. Also adds a NOTICE file per Apache convention. Updated `pyproject.toml` (`license = {text = "Apache-2.0"}`, OSI classifier to "Apache Software License"), `llms.txt`, and all site footer references.

## v1.0.5 — 2026-04-29 (gap-audit cleanup + verifier expansion)

### Engineering hygiene
- **MCP server collapsed to one implementation.** The shadowed `src/concordance_engine/mcp_server.py` (a 738-line stdlib JSON-RPC server unreachable because Python prefers the package directory of the same name) is now an empty deprecation stub. The root-level `concordance_mcp_server.py` is now a 19-line shim that calls `concordance_engine.mcp_server.server.main`. The supported invocation remains `concordance-mcp` from the `[mcp]` extra.
- **Parallel src/ trees collapsed.** `lw/01_engine/concordance-engine/src/concordance_engine/` (the Apr-27 snapshot that diverged from top-level on `engine.py`, `verifiers/computer_science.py`, `verifiers/statistics.py`) has been emptied. Top-level `src/concordance_engine/` is now the canonical tree.
- **`tests/test_mcp_tools.py` repaired.** `ALL_TOOLS` is now exported from `mcp_server/tools.py` as a `dict[name -> callable]`. The test was rewritten against the actual current API shape (named sub-result keys instead of positional `results[0]`). 62/62 cases pass.
- **`tests/test_canon_validators.py` portable.** Probes `canons/`, `02_canons/`, and `lw/02_canons/` under every ancestor; honors `CONCORDANCE_CANON_ROOT` env override. 5/5 cases pass.
- **`packet_manifest.yaml` regenerated.** SHA-256 hashes now match current file contents (previously stale at v1.0.0).
- **Pytest config + GitHub Actions CI added.** `pyproject.toml` declares `testpaths`; `tests/conftest.py` wraps each script-style suite as a parameterized pytest test. `.github/workflows/ci.yml` runs the full matrix on Python 3.10, 3.11, 3.12 plus a `ruff` lint job.
- **Ruff config added** (`[tool.ruff]` block in `pyproject.toml`).

### New verifier coverage
- **Statistics — six new test types in `verify_pvalue_calibration`:** `paired_t`, `one_proportion_z`, `two_proportion_z`, `fisher_exact`, `mannwhitney`, `wilcoxon_signed_rank`, `regression_coefficient_t`. Existing `two_sample_t / one_sample_t / z / chi2 / f` unchanged.
- **Statistics — CI bound recomputation.** `verify_confidence_interval` now optionally recomputes the CI from raw `mean / sd / n / conf_level` and compares to the claimed bounds.
- **Mathematics — four new modes:** `matrix` (rank, determinant, eigenvalues, trace, transpose, inverse, symmetric, invertible, nullspace_dim), `inequality` (symbolic + sampling fallback), `series` (finite or infinite-bound sympy `Sum`), `ode` (substitute claimed solution and check residual is zero).
- **Computer Science — two new checks:** `verify_space_complexity` (peak memory via `tracemalloc` at log-spaced input sizes; log-log slope fit), `verify_determinism` (run-twice identity check across `trials` repeats per test case).
- **Physics — named-law conservation.** `verify_named_conservation(law=...)` with profiles for `energy` (KE+PE total or E_total), `momentum` (per-component), `charge`, `mass`. Multi-key profiles sum across components rather than checking per-quantity.
- **Biology — four new checks:** `verify_hardy_weinberg` (chi² vs HWE expectation), `verify_primer` (length/GC%/Wallace Tm sanity), `verify_molarity` (M = moles/L = mass/MW/L), `verify_mendelian` (chi² against an expected ratio).
- **Governance — per-domain profiles.** `verify_domain_profile(domain, packet)` with required+recommended field profiles for `business` (officers, fiduciary_basis, dollar_amount, risk_assessment), `household` (budget_category, affected_dependents, time_horizon, alternatives_considered), `education` (affected_cohort, learning_objective, accommodation_plan, policy_reference), `church` (elder_signoff, scripture_anchor, congregation_impact, prayer_record), and `governance` (base shape only).

### New MCP tools
- **`attest_red`, `attest_floor`** — run only the RED- or FLOOR-gate attestation validator for the packet's domain. Doesn't run the verifier layer or any other gate. Useful when an LLM wants a structural-only check without the full pipeline.
- The `verify_*` MCP wrappers exposing the new modes/test-types/profiles are wired through `tools.py`. Total tool count: 14 (was 11).

### Documentation
- **MCP_QUICKSTART.md rewritten.** Removed references to the historical `01_engine/concordance-engine/` layout. Now points at the supported `concordance-mcp` console script with `pip install -e ".[mcp]"`.
- **WALKTHROUGH.md path fixed.** Same layout cleanup.
- **alpha-tester-pack/known_issues.md** annotated as resolved-in-v1.0.4 with a pointer to top-level `KNOWN_ISSUES.md` for current issues.
- **AGENTS.md test counts** stopped drifting — points readers at the README for current numbers.
- **CONTRIBUTING.md** expanded from 4 lines to a real onboarding doc (setup, tests, lint, branch model, "adding a domain", bug-reporting).
- **AUTHORITY.md** filled in (what the software claims authority over, what it doesn't, trust boundaries, versioning).
- **RELEASING.md** added (cut a version, frozen snapshots, release-gate checklist, rollback).
- **canons/README.md** populated with layout, validator contract, and pointer to the active `lw/02_canons/` tree.
- **eval/README.md** added; `eval/run_eval.py` runner shipped (heuristic baseline + score-predictions modes).

### Test counts
- `test_engine.py` 74, `test_verifiers.py` 64, `test_cli.py` 16, `test_mcp_tools.py` 62 (new), `test_canon_validators.py` 5. All five suites pass on Python 3.10.

## v1.0.4 — 2026-04-27 (interface pack + four bug fixes)
- **Bug fix — `verify_statistics_pvalue` tail aliasing.** `tail` parameter now accepts `two`, `two-sided`, `two_sided`, `twosided`, `both`, `2`, plus `right`/`upper`/`>` (greater) and `left`/`lower`/`<` (less). Previously only the canonical `two-sided`/`greater` literals were honored; any other spelling silently fell through to one-tailed-less and flagged correct claims as MISMATCH. Repro: a true two-tailed p of 0.146 returned `recomputed_p=0.927`. New `_normalize_tail` helper raises ValueError on unknown spec instead of guessing.
- **Bug fix — `verify_computer_science.test_cases` argument unpacking.** Test cases now accept `input` as an alias for `args`/`kwargs`: a list/tuple is splatted into positional args, a dict becomes kwargs, a scalar is passed as a single positional. Previously only the canonical `args`/`kwargs` keys worked; passing `{"input": [2, 3]}` called `add([2, 3])` instead of `add(2, 3)` and raised TypeError.
- **Bug fix — schema mismatch between `validate_packet` and `verify_governance_decision_packet`.** New `_normalize_governance_packet` helper auto-wraps flat governance packets into the canonical layered shape: top-level `red_items`/`floor_items`/`way_path`/`execution_steps`/`witnesses` are hoisted into a `DECISION_PACKET` block, `witness_count` is auto-derived from the `witnesses` list, and a synthetic `text` field is built from the structured content so the keyword scanner has something to read. A packet that previously passed the standalone verifier but quarantined in the engine now passes both. The original layered shape (with explicit `DECISION_PACKET`) is unchanged.
- **Bug fix — `wait_window_seconds` semantics.** The packet's `wait_window_seconds` now *raises* the scope-derived floor (cannot lower it). Previously it was silently ignored. Scope still sets the minimum wait (adapter 1h, mesh 24h, canon 7d); a packet declaring `wait_window_seconds: 7200` for adapter scope correctly raises the wait to 2h. Documented in the GOD gate and in `outputs/concordance/known_issues.md`.
- **Interface pack added** at `outputs/concordance/`: glossary defining RED/FLOOR/BROTHERS/GOD/scope/status taxonomy; per-verifier schemas reference; 19-example `training_set.json` doubling as documentation and regression suite; known-issues log with reproductions; canonical decision-packet template and worked example; quickstart for new testers.
- Test suite extended: `tests/test_verifiers.py` 53 → 64 cases (tail aliasing + input-alias unpacking); `tests/test_engine.py` adds 4 cases for flat-packet auto-wrap and wait-window-floor semantics. All pass.

## v1.0.3 — 2026-04-27 (MCP server)
- Added `mcp_server/` module: FastMCP server exposing the verifier layer and the full engine pipeline as MCP tools. Claude (and any other MCP-capable assistant) can call the verifiers from inside a conversation to validate its own claims before stating them.
- Eleven tools registered: `validate_packet` (full pipeline), `verify_chemistry`, `verify_physics_dimensional`, `verify_physics_conservation`, `verify_mathematics`, `verify_statistics_pvalue`, `verify_statistics_multiple_comparisons`, `verify_statistics_confidence_interval`, `verify_computer_science`, `verify_biology`, `verify_governance_decision_packet`.
- `mcp` is an optional dependency (`pip install -e ".[mcp]"`) — the engine runs without it.
- Tool functions live in `mcp_server/tools.py` as plain Python and are testable without the MCP SDK installed. The FastMCP wrappers in `mcp_server/server.py` register them as tools.
- Tools never raise. On bad input they return `{"status": "ERROR", "detail": "..."}` so an LLM tool loop can read the failure mode rather than crash.
- New `concordance-mcp` script entry point (set in pyproject.toml).
- New test suite `tests/test_mcp_tools.py` with 44 cases covering every tool plus error paths.
- New `mcp_server/README.md` with Claude Desktop config, Claude Code setup, conversational examples, and limitations.
- Engine version bumped to 1.0.3.

## v1.0.2 — 2026-04-27 (verifier layer)
- Added `verifiers/` module: actual computational checks of submitted artifacts. Domain validators continue to check attestation f