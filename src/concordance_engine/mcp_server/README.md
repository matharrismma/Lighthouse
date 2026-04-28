# Concordance Engine MCP Server

Exposes the seven verifier domains plus the full engine pipeline as MCP tools so Claude (and any other MCP-capable AI assistant) can validate its own claims before stating them.

This is the keystone for the AI-tool use case. When this server is connected to your assistant, the assistant can:

- balance chemical equations and catch mistakes in its own chemistry
- verify the dimensional consistency of physics equations it writes
- recompute p-values from supplied test inputs and catch fabricated statistics
- run code it generates against test cases and verify the claimed time complexity
- check biology dose-response curves and sample-size adequacy
- verify that a governance decision packet has all the required parts

## Install

From the `01_engine/concordance-engine/` directory:

```bash
pip install -e ".[mcp]"
```

This adds the `mcp>=1.0.0` dependency and registers the `concordance-mcp` script.

## Running

Either:
```bash
concordance-mcp
```
Or:
```bash
python -m concordance_engine.mcp_server
```

The server runs over stdio and waits for an MCP client to connect.

## Connect Claude Desktop

Edit your Claude Desktop config:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Add the server:

```json
{
  "mcpServers": {
    "concordance-engine": {
      "command": "concordance-mcp"
    }
  }
}
```

Or for development directly from the source tree (no install needed):

```json
{
  "mcpServers": {
    "concordance-engine": {
      "command": "python",
      "args": ["-m", "concordance_engine.mcp_server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/lighthouse-working-package-patched/01_engine/concordance-engine/src"
      }
    }
  }
}
```

Restart Claude Desktop. The tools appear in the tool picker.

## Connect Claude Code

In your project:

```bash
claude mcp add concordance-engine -- concordance-mcp
```

Or for development from the source tree:

```bash
claude mcp add concordance-engine -- python -m concordance_engine.mcp_server
```

(set `PYTHONPATH` in your shell first if running from source).

## Tools exposed

| Tool | What it does |
|---|---|
| `validate_packet` | Full engine pipeline (RED/FLOOR/BROTHERS/GOD + verifiers) on a complete decision packet |
| `verify_chemistry` | Balance equation, check positive temperature |
| `verify_physics_dimensional` | Reduce both sides to base SI units, compare |
| `verify_physics_conservation` | Compare before/after dicts within tolerance |
| `verify_mathematics` | Symbolic equality, derivative, integral, limit, solve via sympy |
| `verify_statistics_pvalue` | Recompute p-value from test inputs, compare to claim |
| `verify_statistics_multiple_comparisons` | Bonferroni / BH rejection set |
| `verify_statistics_confidence_interval` | CI well-formed and contains estimate |
| `verify_computer_science` | Static termination, functional correctness, runtime complexity |
| `verify_biology` | Replicates, orthogonal assays, dose-response, power |
| `verify_governance_decision_packet` | Structural completeness of a governance packet |

Each tool returns a dict with `status` (CONFIRMED / MISMATCH / ERROR / NOT_APPLICABLE), a human-readable `detail` string, and structured `data` where applicable.

## Testing without MCP

The tool functions are plain Python and can be tested without the MCP SDK installed:

```bash
PYTHONPATH=src python tests/test_mcp_tools.py
```

(44 tests; runs in a few seconds; covers every tool plus error paths.)

## Conversational examples

Once connected, you can have exchanges like:

> User: "Is the equation MnO4^- + 5 Fe^2+ + 8 H+ -> Mn^2+ + 5 Fe^3+ + 4 H2O balanced?"
>
> Claude calls `verify_chemistry(equation="MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O")`, gets CONFIRMED, replies "Yes, both atoms and charge balance."

> User: "Write a function that returns the nth Fibonacci number, then verify it."
>
> Claude writes the code, calls `verify_computer_science(code=..., function_name="fib", test_cases=[{"args":[10], "expected":55}])`, gets CONFIRMED, replies with the working code and verification.

> User: "I want to reject the null in this t-test. Mean1=5.0, Mean2=4.5, sd1=sd2=1.0, n1=n2=20. Is p < 0.05?"
>
> Claude calls `verify_statistics_pvalue(spec={"test":"two_sample_t",...})`, gets the recomputed p, replies with the actual value rather than guessing.

> User: "I'm proposing the JDA fund deployment. Help me draft a decision packet."
>
> Claude drafts a `DECISION_PACKET`, calls `verify_governance_decision_packet(...)`, sees it's missing `floor_items`, asks the user for protective constraints, calls again, gets CONFIRMED.

## Limitations and notes

- Code execution in `verify_computer_science` runs in a restricted namespace. No `__import__`, `open`, `eval`, `exec`, `compile`. Suitable for user-controlled snippets, not untrusted input.
- Runtime complexity verification uses real wall-clock time. Results can be noisy for very fast functions; the tool auto-tunes iteration count to a 50 ms target window.
- The tool functions never raise exceptions. On bad input they return `{"status": "ERROR", "detail": "..."}`. This makes them safe to call from inside an LLM tool loop.
- The MCP server runs over stdio. For network deployment, the underlying `tools` module can be wrapped in any RPC framework.
