# Migration

## From v1.0.4 to v1.0.5

This release is **additive** — every v1.0.4 packet, MCP call, and CLI invocation continues to work unchanged. Places a 1.0.4 caller might notice:

### MCP server: collapsed to one implementation

Three MCP server entry points existed in 1.0.4. Two were unreachable:
- `src/concordance_engine/mcp_server.py` — shadowed by the package directory of the same name and silently never imported. Now an empty deprecation stub. **Action:** if your config invoked `python -m concordance_engine.mcp_server`, no change needed; the package directory wins anyway.
- `concordance_mcp_server.py` at the repo root — historical 338-line standalone server. Now a 19-line shim that calls `concordance_engine.mcp_server.server.main`. **Action:** if your `claude_desktop_config.json` runs `python /path/to/concordance_mcp_server.py`, it still works. The supported invocation is `concordance-mcp` from the `[mcp]` extra.

### MCP tool count: 11 → 14

Three new tools register: `attest_red`, `attest_floor`, `get_example_packet`. Existing tools are unchanged in name and signature. If you cached the previous tool list, refresh it.

### Verifier expansions (all additive)

- `verify_mathematics(mode=...)` accepts four new modes: `matrix`, `inequality`, `series`, `ode`. Original five (equality, derivative, integral, limit, solve) unchanged.
- `verify_statistics_pvalue` accepts seven new test types: `paired_t`, `one_proportion_z`, `two_proportion_z`, `fisher_exact`, `mannwhitney`, `wilcoxon_signed_rank`, `regression_coefficient_t`. Original five (`two_sample_t`, `one_sample_t`, `z`, `chi2`, `f`) unchanged.
- `verify_statistics_confidence_interval` accepts an optional `spec` kwarg with raw inputs (`mean`, `sd`, `n`, `conf_level`) — when supplied, bounds are recomputed and compared to the claimed `ci_low`/`ci_high`. Without it, behavior is unchanged.
- `verify_physics_conservation` accepts an optional `law` kwarg (`energy` | `momentum` | `charge` | `mass`). When set, keys in `before`/`after` are matched to a named-law profile and multi-key profiles (KE+PE) are summed before the conservation check. Without it, behavior is unchanged.
- `verify_computer_science` accepts two new optional kwargs: `claimed_space_class` (triggers `tracemalloc`-based space-complexity verification) and `determinism_trials` (>=2 enables run-twice equality check).
- `verify_biology` accepts four new optional sub-blocks in the spec: `hardy_weinberg`, `primer`, `molarity`, `mendelian`.
- `verify_governance_decision_packet` accepts an optional `domain` kwarg (`governance` | `business` | `household` | `education` | `church`). When set, the per-domain required+recommended profile is checked alongside the base shape.

### Schema description strings updated; structure unchanged

`schema/packet.schema.json` description strings now mention the new sub-fields. Structural rules still use `additionalProperties: true`, so any 1.0.4 packet still validates without modification.

### Engine wiring extended

`physics.run()` and `computer_science.run()` now route to the new verifiers when the corresponding fields are present in `PHYS_VERIFY` / `CS_VERIFY`:

- `PHYS_VERIFY.law` → `verify_named_conservation`
- `CS_VERIFY.claimed_space_class` → `verify_space_complexity`
- `CS_VERIFY.trials` → `verify_determinism`

Packets without these fields take the v1.0.4 code path.

### Test counts

- `test_verifiers.py`: 64 → 101 cases.
- `test_mcp_tools.py`: was failing on `ImportError: ALL_TOOLS` in 1.0.4; now passes 62 cases.
- `test_canon_validators.py`: was failing on hardcoded `02_canons` path; now passes 5/5 (probes both `canons/` and `lw/02_canons/`).
- `test_engine.py` (74), `test_cli.py` (16): unchanged.

If your CI ran the suites via the old command lines, they continue to work. New in 1.0.5: `pytest tests/` is supported via `tests/conftest.py`, and `.github/workflows/ci.yml` runs the matrix on Python 3.10/3.11/3.12 plus a `ruff` lint pass plus `python scripts/regenerate_manifest.py --check`.

### Removed / deprecated

- `lw/01_engine/concordance-engine/src/concordance_engine/` — the parallel snapshot tree was emptied. Recommended: `git rm -rf` the subtree.
- `src/concordance_engine/mcp_server.py` — the shadowed standalone server is now an inert stub. Recommended: `git rm` it.

## From v0.1
- Old `src/*.py` scripts are now importable as `concordance_engine.*`.
- Use `concordance validate <packet.json>`.

## From v1.0 to v1.0.1
**Schema/engine disconnect resolved.** If you were using the long-form schema (`packet_type`, `provenance`, `claims` with `claim_id/kind`, `constraints`, `hash`), it's preserved at `schema/packet.schema.aspirational.json`. The new `schema/packet.schema.json` matches what the engine actually validates: domain-routed packets with optional `MATH_RED`, `PHYS_CONSERVATION`, `CHEM_SETUP`, `BIO_RED`, `CS_RED`, `STAT_INFERENCE` blocks plus governance text scanning.

If your existing packets used the long-form shape, they'll be rejected by the new schema. Two options:
1. Convert the packets to the engine-aligned shape (see `examples/sample_packet.json`).
2. Switch the CLI to validate against the aspirational schema: `concordance validate <packet> --schema schema/packet.schema.aspirational.json`. Note that this passes structural validation but will be rejected by the engine, since the engine only understands the new shape.

The aspirational schema is preserved so the long-form goal isn't lost. The intention is to grow the engine toward it, not retreat from it.

**Governance scanner now negation-aware.** Phrases like "we will not exploit captive audiences" no longer false-positive on `exploit`. The negation cues (not, no, never, without, prohibit, forbid, refuse, ban, cannot, won't, must not, do not, does not, none, nobody) within five tokens before the keyword suppress the match. Mixed-clause cases ("we never coerce employees, but we will use mandatory surveillance") still catch the un-negated half.

## From v1.0.2 to v1.0.3 (MCP server)

**New: MCP server.** The verifier layer is now exposed as an MCP server so Claude (and any other MCP-capable AI assistant) can call the verifiers from inside a conversation. This is additive — nothing in v1.0.2 is changed, removed, or renamed. The optional `mcp` dependency is required only if you want to run the server.

Install the MCP extra and run the server:
```bash
pip install -e ".[mcp]"
concordance-mcp
```

Connect Claude Desktop via `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "concordance-engine": { "command": "concordance-mcp" }
  }
}
```

See `src/concordance_engine/mcp_server/README.md` for full setup including Claude Code, conversational examples, and limitations.

**No breaking changes.** Packets that validated under v1.0.2 will validate under v1.0.3.

## From v1.0.1 to v1.0.2 (verifier layer)

**New: computational verifiers.** When a packet supplies a `*_VERIFY` block, the engine runs an actual computational check on the artifact. A verifier MISMATCH or ERROR rejects on RED with full failure details. NOT_APPLICABLE is silent (the verifier had nothing to check). See README.md for the recognized fields per domain.

This is additive. Existing packets without `*_VERIFY` blocks continue to validate exactly as they did under v1.0.1.

**New blocks recognized**:
- `MATH_VERIFY` — symbolic equality, derivative, integral, limit, solve
- `PHYS_VERIFY` — dimensional consistency, conservation arithmetic
- `PHYS_CONSTRAINTS`, `PHYS_MEASUREMENTS` — formerly missing from schema
- `CHEM_VERIFY` — equation balance, temperature_K
- `STAT_VERIFY` — p-value recomputation, multiple-comparison correction, CI bounds
- `CS_VERIFY` — static termination, functional correctness, runtime complexity
- `BIO_VERIFY` — replicate count, orthogonal assays, dose-response monotonicity, power
- `DECISION_PACKET` — structural verification of governance/business/household/education/church packets
- `units` — top-level field accepted by the physics validator

**Engine API change**: `EngineConfig` now accepts `run_verifiers: bool = True`. Set to `False` to disable the verifier layer (e.g. for legacy regression tests). Default behavior is verifiers ON.

**Dependency change**: the engine now requires `sympy`, `numpy`, `scipy`. `jsonschema` is moved to optional (`pip install -e ".[schema]"`). Without `jsonschema`, the CLI uses a structural fallback that checks required fields, top-level type, and recognized keys. Install `jsonschema` for the full validator.

**No breaking changes** to the gate sequence, the `validate_packet()` signature, or the result types. A packet that validated under v1.0.1 will validate under v1.0.2.
