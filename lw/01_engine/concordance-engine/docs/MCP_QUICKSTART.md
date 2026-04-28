# MCP Server Quick Start

This wraps the Concordance Engine as a tool any MCP-compatible AI client can call. After setup, an LLM can validate a chemical equation, balance it if wrong, check a physics equation's units, recompute a p-value, verify a Python function, or grade a decision packet, all by calling the engine.

## Install

```bash
# from the engine directory
cd 01_engine/concordance-engine
pip install -e ".[dev]"
pip install mcp
```

Three minutes. Confirms with: `PYTHONPATH=src python tests/test_engine.py` showing 67 tests passing.

## Wire to Claude Desktop

Edit your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add (using the absolute path to your install):

```json
{
  "mcpServers": {
    "concordance": {
      "command": "python",
      "args": [
        "/Users/yourname/lighthouse-working-package/01_engine/concordance-engine/concordance_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/yourname/lighthouse-working-package/01_engine/concordance-engine/src"
      }
    }
  }
}
```

Restart Claude Desktop. The hammer icon at the bottom of the chat window shows "concordance" with nine tools available.

## What it exposes

| Tool | Use case |
|---|---|
| `validate_packet_tool` | Full four-gate validation of a decision packet |
| `verify_chemistry` | Balance/check a chemical equation |
| `verify_physics` | Dimensional consistency check |
| `verify_mathematics` | Symbolic equality, derivative, integral, limit, solve |
| `verify_statistics` | p-value recomputation, multiple comparisons, CI |
| `verify_cs` | Static termination, functional correctness, complexity |
| `verify_biology` | Replicates, dose-response, statistical power |
| `verify_governance` | Decision packet structural completeness |
| `suggest_fix` | Run engine, return actionable corrections on reject |

## Try it

In Claude Desktop, paste:

> Use the concordance tool to check whether `H2 + O2 -> H2O` is balanced. If not, give me the correct coefficients.

Claude calls `verify_chemistry`, sees the imbalance, and reports back: balances as `2 H2 + O2 -> 2 H2O`.

Or for governance:

> I need to draft a JDA decision packet for approving a new producer cooperative member family contract. Walk me through the required fields, then check the draft with the concordance verify_governance tool.

Claude builds the packet interactively, runs verify_governance, and refines until it passes.

## Wire to other clients

The server speaks standard MCP. Cursor, Continue, Cline, and any custom MCP client connect the same way: point them at the script.

## Stays local

No network calls. No data leaves your machine. The engine and verifiers are pure Python plus sympy/scipy/numpy. Suitable for sensitive deliberative work (governance decisions, internal research) where uploading to a cloud API is undesirable.

## Performance

Most verifiers return in milliseconds. Two exceptions:
- `verify_cs` runtime complexity measures wall-clock time deliberately. 5-30 seconds depending on size and class.
- `validate_packet_tool` runs all applicable verifiers, so packets exercising several can take a second or two.

## Caveats

The CS verifier executes user-supplied code in a restricted Python namespace (no `__import__`, no `open`, no `exec`, no `eval`). It is intended for code the user controls. Do not pass untrusted code to `verify_cs`.

The schema validation falls back to a structural check when `jsonschema` is not installed. Install jsonschema for the full validator: `pip install jsonschema`.

The runtime-complexity verifier's measurement is noisy at small input sizes. Default tolerance on the log-log slope is 0.40, which catches O(n) vs O(n²) but does not reliably distinguish O(n) from O(n log n).
