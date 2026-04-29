# MCP Server Quick Start

This wraps the Concordance Engine as a tool any MCP-compatible AI client can call. After setup, an LLM can validate a chemical equation, balance it if wrong, check a physics equation's units, recompute a p-value, verify a Python function, or grade a decision packet, all by calling the engine.

## Install

```bash
# from the repository root
pip install -e ".[mcp]"
```

That installs the package, its scientific dependencies (sympy, numpy, scipy), and the optional `mcp` SDK that powers the server. Confirm with:

```bash
PYTHONPATH=src python tests/test_engine.py
```

You should see "All tests passed" with the current test counts (see README for the exact number — counts shift as the suite grows).

## Wire to Claude Desktop

Edit your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "concordance-engine": {
      "command": "concordance-mcp"
    }
  }
}
```

`concordance-mcp` is a console script installed by the `[mcp]` extra. It is the supported entry point. (A top-level `concordance_mcp_server.py` exists in the repo as a thin shim for legacy instructions; you do not need it.)

## Wire to Claude Code

```bash
claude mcp add concordance-engine -- concordance-mcp
```

## What it exposes

The full table lives in [README.md](../README.md#mcp-tools-exposed). Briefly: the eleven verifier tools (`verify_chemistry`, `verify_physics_dimensional`, `verify_physics_conservation`, `verify_mathematics`, `verify_statistics_pvalue`, `verify_statistics_multiple_comparisons`, `verify_statistics_confidence_interval`, `verify_computer_science`, `verify_biology`, `verify_governance_decision_packet`, plus the full-pipeline `validate_packet`), the two attestation tools (`attest_red`, `attest_floor`), and the example-fetcher (`get_example_packet`).

## Try it

In Claude Desktop, paste:

> Use the concordance tool to check whether `H2 + O2 -> H2O` is balanced. If not, give me the correct coefficients.

Claude calls `verify_chemistry`, sees the imbalance, and reports back: balances as `2 H2 + O2 -> 2 H2O`.

Or for governance:

> I need to draft a decision packet for approving a producer cooperative member contract. Walk me through the required fields, then check the draft with `verify_governance_decision_packet`.

Claude builds the packet interactively, runs the verifier, and refines until it passes.

## Stays local

No network calls. No data leaves your machine. The engine and verifiers are pure Python plus sympy/scipy/numpy.

## Performance

Most verifiers return in milliseconds. Two exceptions:
- `verify_computer_science` runtime complexity measures wall-clock time deliberately. 5-30 seconds depending on size and class.
- `validate_packet` runs all applicable verifiers, so packets exercising several can take a second or two.

## Caveats

The CS verifier executes user-supplied code in a restricted Python namespace (no `__import__`, no `open`, no `exec`, no `eval`). It is intended for code the user controls. Do not pass untrusted code to it.

Schema validation falls back to a structural check when `jsonschema` is not installed; install with `pip install -e ".[schema]"` to enable full JSON-Schema validation.

The runtime-complexity verifier's measurement is noisy at small input sizes. Default tolerance on the log-log slope is 0.40, which catches O(n) vs O(n²) but does not reliably distinguish O(n) from O(n log n).
