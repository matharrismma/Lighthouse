# Migration

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
