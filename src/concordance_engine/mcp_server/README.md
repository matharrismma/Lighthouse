# Concordance Engine MCP Server

Exposes the seven verifier domains, the attestation layer, and the full engine pipeline as MCP tools so Claude (and any other MCP-capable AI assistant) can validate its own claims before stating them.

Once connected, the assistant can:

- balance chemical equations and catch mistakes in its own chemistry
- verify the dimensional consistency of physics equations it writes
- check named conservation laws (energy, momentum, charge, mass)
- recompute p-values from supplied test inputs and catch fabricated statistics (12 test types)
- run code it generates against test cases, verify the claimed time and space complexity, and confirm determinism
- check biology dose-response curves, sample-size adequacy, Hardy-Weinberg consistency, primer Tm/GC, molarity arithmetic, and Mendelian-ratio chi-squared
- verify that a decision packet has all the required parts, optionally against per-domain (governance/business/household/education/church) profiles
- run the RED- or FLOOR-attestation validator standalone without the full pipeline

## Install

From the repository root:

```bash
pip install -e ".[mcp]"
```

This adds the `mcp>=1.0.0` dependency and registers the `concordance-mcp` script.

## Running

```bash
concordance-mcp
# or
python -m concordance_engine.mcp_server
```

The server runs over stdio and waits for an MCP client to connect.

## Connect Claude Desktop

Edit your Claude Desktop config:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "concordance-engine": {
      "command": "concordance-mcp"
    }
  }
}
```

For development directly from the source tree (no install needed):

```json
{
  "mcpServers": {
    "concordance-engine": {
      "command": "python",
      "args": ["-m", "concordance_engine.mcp_server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Lighthouse/src"
      }
    }
  }
}
```

Restart Claude Desktop. The tools appear in the tool picker.

## Connect Claude Code

```bash
claude mcp add concordance-engine -- concordance-mcp
```

Or from the source tree:

```bash
claude mcp add concordance-engine -- python -m concordance_engine.mcp_server
```

## Tools exposed (14)

### Verifiers (11)

| Tool | What it does |
|---|---|
| `validate_packet` | Full engine pipeline (RED/FLOOR/BROTHERS/GOD + verifiers) on a complete decision packet |
| `verify_chemistry` | Balance equation, check positive temperature |
| `verify_physics_dimensional` | Reduce both sides to base SI units, compare |
| `verify_physics_conservation` | Compare before/after dicts within tolerance; optional `law` (energy/momentum/charge/mass) enforces a named-law key profile |
| `verify_mathematics` | sympy verification: equality, derivative, integral, limit, solve, **matrix**, **inequality**, **series**, **ode** |
| `verify_statistics_pvalue` | Recompute p from inputs and compare to claim. Tests: `two_sample_t`, `one_sample_t`, **`paired_t`**, `z`, `chi2`, `f`, **`one_proportion_z`**, **`two_proportion_z`**, **`fisher_exact`**, **`mannwhitney`**, **`wilcoxon_signed_rank`**, **`regression_coefficient_t`** |
| `verify_statistics_multiple_comparisons` | Bonferroni / BH rejection set |
| `verify_statistics_confidence_interval` | CI well-formed and contains estimate; with `spec` raw inputs, also recomputes bounds |
| `verify_computer_science` | Static termination, functional correctness, runtime complexity, **space complexity**, **determinism (run-twice)** |
| `verify_biology` | Replicates, orthogonal assays, dose-response, power, **Hardy-Weinberg chi²**, **primer Tm/GC sanity**, **molarity arithmetic**, **Mendelian ratio chi²** |
| `verify_governance_decision_packet` | Structural completeness; optional `domain` activates per-domain (business / household / education / church) required+recommended profile |

### Attestation (2, new in 1.0.5)

| Tool | What it does |
|---|---|
| `attest_red` | Run only the RED-gate attestation validator for the packet's domain. Returns `{overall, results}` without invoking the verifier layer or other gates |
| `attest_floor` | Same, for FLOOR |

### Utilities (1)

| Tool | What it does |
|---|---|
| `get_example_packet` | Return a canonical example packet by name (chemistry, physics, math, math_matrix, math_inequality, statistics, stats_paired_t, cs, cs_runtime, cs_determinism, biology, biology_hardy_weinberg, governance, business_decision, jda_phase1_fund) |

Each tool returns a dict with `status` (CONFIRMED / MISMATCH / ERROR / NOT_APPLICABLE), a human-readable `detail` string, and structured `data` where applicable.

## Testing without MCP

The tool functions are plain Python and can be exercised directly without the MCP SDK installed. The `ALL_TOOLS` dict in `concordance_engine.mcp_server.tools` maps each tool name to its callable:

```python
from concordance_engine.mcp_server.tools import ALL_TOOLS
print(ALL_TOOLS["verify_chemistry"]("C3H8 + 5 O2 -> 3 CO2 + 4 H2O"))
# {"equation": {"status": "CONFIRMED", "detail": "balanced", ...}}
```

`tests/test_mcp_tools.py` exercises every tool plus error paths (62 test cases as of v1.0.5).

## Conversational examples

> **User:** Is the equation `MnO4^- + 5 Fe^2+ + 8 H+ -> Mn^2+ + 5 Fe^3+ + 4 H2O` balanced?
>
> Claude calls `verify_chemistry`, gets CONFIRMED, replies "Yes, both atoms and charge balance."

> **User:** Write a function that returns the nth Fibonacci number, then verify it.
>
> Claude writes the code, calls `verify_computer_science(code=..., function_name="fib", test_cases=[...], determinism_trials=3)`, gets CONFIRMED on correctness and determinism, replies with the working code and verification.

> **User:** I want to reject the null in this paired t-test. mean_diff=0.5, sd_diff=1.0, n=20.
>
> Claude calls `verify_statistics_pvalue(spec={"test":"paired_t", ...})`, gets the recomputed p, replies with the actual value rather than guessing.

> **User:** Is energy conserved if KE goes from 5 to 8 and PE goes from 10 to 7?
>
> Claude calls `verify_physics_conservation(before={"KE":5,"PE":10}, after={"KE":8,"PE":7}, law="energy")`, gets CONFIRMED (total 15 → 15), replies that energy is conserved (KE↑3, PE↓3).

> **User:** I'm drafting a board decision. Help me check it.
>
> Claude drafts a `DECISION_PACKET`, calls `verify_governance_decision_packet(decision_packet=..., domain="business")`, sees it's missing `fiduciary_basis`, asks the user, calls again, gets CONFIRMED.

## Limitations and notes

- Code execution in `verify_computer_science` runs in a restricted namespace. No `__import__`, `open`, `eval`, `exec`, `compile`. Suitable for user-controlled snippets, not untrusted input. Functions that need `random` or other restricted imports will surface as ERROR — fail-closed by design.
- Runtime complexity verification uses real wall-clock time. Results can be noisy for very fast functions; the tool auto-tunes iteration count to a 50 ms target window.
- Space complexity uses `tracemalloc` peak; same noise caveats apply.
- The tool functions never raise exceptions. On bad input they return `{"status": "ERROR", "detail": "..."}`. This makes them safe to call from inside an LLM tool loop.
- The MCP server runs over stdio. For network deployment, the underlying `tools` module can be wrapped in any RPC framework.
