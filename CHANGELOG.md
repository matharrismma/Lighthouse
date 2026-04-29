# Changelog

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
- Added `verifiers/` module: actual computational checks of submitted artifacts. Domain validators continue to check attestation flags (FLOOR-side: did the author affirm). Verifiers check artifacts (RED-side: do the math, code, units, and statistics actually hold up). Seven verifiers ship:
  - `chemistry`: parses formulas with nested groups and charges; verifies or balances equations via Fraction-based nullspace solver; rejects non-positive temperatures.
  - `physics`: dimensional consistency via sympy.physics.units (converts both sides to base SI units kg/m/s/A/K/mol/cd and compares unit signatures); per-quantity conservation arithmetic with relative+absolute tolerance.
  - `mathematics`: symbolic equality, derivative, integral (via differentiating the claimed antiderivative), limit, and solve via sympy.
  - `statistics`: scipy.stats-based recomputation of p-values from inputs (two-sample t / one-sample t / z / chi² / F); Bonferroni and BH/FDR multiple-comparison correction with rejection-set verification; significance-claim consistency; effect-size-required-when-significant; confidence-interval bounds.
  - `computer_science`: AST-based static termination scan that catches `while True:` without break/return and unguarded recursion (handling IfExp ternaries inside Returns); functional correctness via restricted-namespace execution; runtime complexity verification with auto-tuning iteration count and log-log slope fit on the upper half of input sizes.
  - `biology`: replicate count, orthogonal assay diversity, dose-response monotonicity (with optional expected_direction), sample-size adequacy via two-sample t-test power calculation.
  - `governance`: structural verification of decision packets (title, scope, red_items, floor_items, way_path, execution_steps, witnesses); witness-count consistency between DECISION_PACKET and top-level. Keyword scanner (with negation handling) continues to run alongside as triage.
- Engine now runs verifiers after RED attestation. Verifier MISMATCH or ERROR rejects on RED with full failure details. NOT_APPLICABLE is silent. New `EngineConfig.run_verifiers` flag (default True) toggles the layer.
- **CLI rewritten** with human-readable output. Default format is a summary with per-gate status icons and verifier confirmations or failure details. `--format json` preserves the prior machine-readable output. `--format verbose` includes all gate details. Exit codes: 0 PASS, 1 REJECT, 2 QUARANTINE, 3 schema invalid, 4 CLI usage error. New `--no-verifiers` flag for legacy regression.
- Schema extended: `MATH_VERIFY`, `PHYS_VERIFY`, `CHEM_VERIFY`, `STAT_VERIFY`, `CS_VERIFY`, `BIO_VERIFY`, `DECISION_PACKET` blocks plus `PHYS_CONSTRAINTS`, `PHYS_MEASUREMENTS`, `units`.
- Eight new example packets exercise the verifier layer end-to-end (one per domain plus a CS runtime-complexity case).
- jsonschema is now an optional dependency (`pip install -e ".[schema]"`). When absent, `validate.py` falls back to a structural check (required fields, top-level type, recognized keys).
- Engine dependencies tightened: `sympy`, `numpy`, `scipy` now required.
- New `docs/WALKTHROUGH.md` — end-to-end guide from zero to a verified packet for new users.
- New `verifiers/README.md` — developer doc on adding a new verifier.
- Engine `README.md` rewritten to document the verifier layer.
- New `tests/test_cli.py` — 16 tests covering the CLI wrapper (formats, exit codes, error handling).
- New `tests/test_canon_validators.py` — smoke test confirming each canon-side validator (`02_canons/<domain>/tools/`) imports and runs cleanly. Catches drift between the engine and the canon directories.
- Added `02_canons/biology/tools/validator_biology.py` — biology canon-side validator was missing; now matches the pattern used for math, physics, CS, statistics.
- Fixed minor bug in `10_data/stress_test_harness_stub.py`: collection-name singularization was producing `territorie` instead of `territory`.
- Test suite: 42 → 67 integration cases plus 53 verifier unit tests plus 16 CLI tests plus 5 canon-validator smoke tests. All pass.

## v1.0.1 — 2026-04-27 (patch)
- Fixed schema/engine disconnect. The aspirational long-form schema (packet_type, provenance, claims with claim_id/kind, constraints, hash) was preserved at `schema/packet.schema.aspirational.json`. The new `schema/packet.schema.json` matches what the engine actually validates: domain-routed packets with optional MATH_RED/PHYS_CONSERVATION/CHEM_SETUP/BIO_RED/CS_RED/STAT_INFERENCE blocks plus governance text scanning. CLI `concordance validate` now succeeds against the example packets (previously rejected every test packet on schema validation).
- Replaced `examples/sample_packet.json` with three engine-conforming samples: mathematics, governance, chemistry.
- Added negation-aware scanning to the governance validator. Negation cues (not, no, never, without, prohibit, forbid, refuse, ban, cannot, won't, must not, do not, does not, none, nobody) within five tokens before a forbidden keyword now suppress the match. Removes the most common false positives without pretending to be robust NLP.
- Added honest limitations to the governance validator docstring. Scanner is triage, not decision authority.
- Test suite extended 38 → 42 cases. All pass. Four new cases cover negation handling.

## v1.0
- GitHub-ready packaging (pyproject, module layout, CLI)
- Cleaned engine + validators into importable package
- Added sample packets + pytest skeleton
- Added deterministic hash manifest generator
