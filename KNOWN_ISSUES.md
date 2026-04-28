# Known Issues

Tracked here so the README and onboarding remain honest about what works.

## tests/test_mcp_tools.py — ImportError on `ALL_TOOLS`

**Symptom**

```
ImportError: cannot import name 'ALL_TOOLS' from 'concordance_engine.mcp_server.tools'
```

**Cause**

`tests/test_mcp_tools.py` imports `ALL_TOOLS` and uses it as a `dict[name -> callable]` (line 52: `name in ALL_TOOLS and callable(ALL_TOOLS[name])`). The current `src/concordance_engine/mcp_server/tools.py` exports `TOOLS` (a `list[dict]` of MCP tool descriptors) and `TOOL_BY_NAME` (a `dict` keyed by name, but the values are descriptors — not callables).

The test was written against a prior tool-module API and was never re-synced when `tools.py` switched to the descriptor/registry shape.

**Fix sketch**

Either:
1. Add `ALL_TOOLS = {fn.__name__: fn for fn in [validate_packet, verify_chemistry, ...]}` at the bottom of `tools.py` so the test's expected shape (`dict[name -> callable]`) is satisfied; or
2. Rewrite the test to walk `TOOLS` / `TOOL_BY_NAME` and resolve each entry's callable through `call_tool(name, args)`.

Option 1 is the smaller diff. Option 2 is closer to how the MCP server actually dispatches.

**Affected files**

- `tests/test_mcp_tools.py`
- `lw/01_engine/concordance-engine/tests/test_mcp_tools.py` (mirror — fix both)

## tests/test_canon_validators.py — path resolution requires lw/ layout

`test_canon_validators.py` resolves canons via `Path(__file__).resolve().parents[3] / "02_canons"`. That works when run from `lw/01_engine/concordance-engine/tests/` (parents[3] = `Lighthouse/lw/`). It does not work from the top-level `tests/` directory because `parents[3]` walks above the repo.

Top-level `canons/` is the right target for that layout but the file hard-codes `02_canons`. Either parameterize the canon-root path or duplicate the test for the top-level layout.

## Two parallel `src/` trees

`src/concordance_engine/` and `lw/01_engine/concordance-engine/src/concordance_engine/` are near-duplicates. Top-level is newer (Apr 28); lw is Apr 27. They diverge on `engine.py`, `verifiers/computer_science.py`, `verifiers/statistics.py` (mostly comment/whitespace, but enough that test counts differ: top-level has 74/64 engine/verifier tests; lw has 70/53).

Pick one as canonical. Suggested: top-level `src/` is the active development tree; treat `lw/01_engine/concordance-engine/` as a frozen reference snapshot or delete it.

## `concordance_engine-1.0.4/README.md` is byte-for-byte identical to top-level README.md

It's a frozen v1.0.4 distribution snapshot. Either mark it explicitly as a release artifact and stop maintaining it, or remove it from the repo. Currently any README edit has to be made twice to keep it in sync.
