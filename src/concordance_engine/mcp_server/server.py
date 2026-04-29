"""MCP server exposing the Concordance Engine verifier layer.

Run as:
    python -m concordance_engine.mcp_server
or after install:
    concordance-mcp

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS) with:
{
  "mcpServers": {
    "concordance-engine": {
      "command": "concordance-mcp"
    }
  }
}

Or for development from the source tree:
{
  "mcpServers": {
    "concordance-engine": {
      "command": "python",
      "args": ["-m", "concordance_engine.mcp_server"],
      "env": {"PYTHONPATH": "/path/to/01_engine/concordance-engine/src"}
    }
  }
}

This file expects the `mcp` package (mcp >= 1.0.0). Install via:
    pip install -e ".[mcp]"
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP SDK not installed. Run: pip install -e \".[mcp]\" "
        "from the concordance-engine directory."
    ) from e

from . import tools

mcp = FastMCP("concordance-engine")

CONCORDANCE_API_URL = os.environ.get(
    "CONCORDANCE_API_URL",
    "https://lighthouse-production-3f9a.up.railway.app",
)


# ─────────────────────────────────────────────────────────────────────────
# Top-level engine
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def validate_packet(packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """Run a packet through the full Concordance Engine: RED, FLOOR, BROTHERS, GOD.

    Use this when you have a complete decision/proposal/research packet with
    a `domain` field. The engine routes to the appropriate validator and
    verifier, then enforces witness count and time-wait gates.

    Returns: {overall: PASS|REJECT|QUARANTINE, gate_results: [...]}.
    """
    # -- 1. Try Railway API (writes to Evidence Ledger) ----------------------
    if CONCORDANCE_API_URL:
        try:
            pkt = {**packet}
            import time as _time
            if "created_epoch" not in pkt:
                pkt["created_epoch"] = now_epoch or int(_time.time())
            payload = json.dumps({"packet": pkt}).encode()
            req = urllib.request.Request(
                f"{CONCORDANCE_API_URL.rstrip('/')}/validate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                api_result = json.loads(resp.read().decode())
            api_result["_source"] = "api"
            return api_result
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            pass  # fall through to local engine

    # -- 2. Local fallback (offline) -----------------------------------------
    out = tools.validate_packet(packet, now_epoch)
    out["_source"] = "local"
    return out


# ─────────────────────────────────────────────────────────────────────────
# Chemistry
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_chemistry(equation: str, temperature_K: Optional[float] = None) -> Dict[str, Any]:
    """Verify a chemical equation balances (atoms and charge) and optionally
    that the temperature is physical (positive Kelvin).

    Equation format: '2 H2 + O2 -> 2 H2O'. Supports nested groups (Cu(OH)2),
    charges (Fe^2+, MnO4^-), and ionic forms. On MISMATCH, returns the
    correctly balanced coefficients in `data.balanced_lhs` / `balanced_rhs`.
    """
    return tools.verify_chemistry(equation, temperature_K)


# ─────────────────────────────────────────────────────────────────────────
# Physics
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_physics_dimensional(equation: str, symbols: Dict[str, str]) -> Dict[str, Any]:
    """Verify both sides of a physics equation reduce to the same SI dimensions.

    `symbols` maps each variable in the equation to its named unit
    (e.g. {"F": "newton", "m": "kilogram", "a": "meter/second**2"}).
    Both sides are converted to base SI units (kg, m, s, A, K, mol, cd)
    and compared.
    """
    return tools.verify_physics_dimensional(equation, symbols)


@mcp.tool()
def verify_physics_conservation(
    before: Dict[str, float],
    after: Dict[str, float],
    tolerance_relative: float = 1e-6,
    tolerance_absolute: float = 0.0,
) -> Dict[str, Any]:
    """Verify each named conserved quantity (momentum, energy, charge, ...)
    is preserved within tolerance.

    `before` and `after` are dicts of quantity_name -> numeric_value.
    A quantity passes if its relative change <= tolerance_relative OR
    its absolute change <= tolerance_absolute.
    """
    return tools.verify_physics_conservation(before, after, tolerance_relative, tolerance_absolute)


# ─────────────────────────────────────────────────────────────────────────
# Mathematics
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_mathematics(mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Sympy-based math verification across five modes.

    mode: one of 'equality', 'derivative', 'integral', 'limit', 'solve'.

    params per mode:
      equality:    {expr_a, expr_b, variables: [...]}
      derivative:  {function, variable, claimed_derivative}
      integral:    {integrand, variable, claimed_antiderivative}
      limit:       {function, variable, point, claimed_limit}
      solve:       {equation, variable, claimed_solutions: [...]}
    """
    return tools.verify_mathematics(mode, params)


# ─────────────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_statistics_pvalue(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute a p-value from supplied test inputs and verify against claimed_p.

    spec must include 'test' (one of: two_sample_t, one_sample_t, z, chi2, f)
    plus the corresponding inputs:
      two_sample_t: n1, n2, mean1, mean2, sd1, sd2, [tail]
      one_sample_t: n, mean, sd, [mu0, tail]
      z:            z, [tail]
      chi2:         statistic, df
      f:            statistic, df1, df2

    Optional: claimed_p (to verify), tolerance (default 1e-3).
    """
    return tools.verify_statistics_pvalue(spec)


@mcp.tool()
def verify_statistics_multiple_comparisons(
    raw_p_values: List[float],
    method: str,
    alpha: float = 0.05,
    claimed_rejected_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Apply Bonferroni or BH (Benjamini-Hochberg) correction and verify the
    rejection set at alpha matches the claim, if a claim is provided.
    """
    return tools.verify_statistics_multiple_comparisons(
        raw_p_values, method, alpha, claimed_rejected_indices
    )


@mcp.tool()
def verify_statistics_confidence_interval(
    estimate: float, ci_low: float, ci_high: float
) -> Dict[str, Any]:
    """Verify a CI is well-formed (low <= high) and contains the point estimate."""
    return tools.verify_statistics_confidence_interval(estimate, ci_low, ci_high)


# ─────────────────────────────────────────────────────────────────────────
# Computer Science
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_computer_science(
    code: str,
    function_name: Optional[str] = None,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    input_generator: Optional[str] = None,
    claimed_class: Optional[str] = None,
    sizes: Optional[List[int]] = None,
    tolerance: float = 0.40,
) -> Dict[str, Any]:
    """Verify Python code: termination, functional correctness, runtime complexity.

    Always runs static termination scan. If function_name + test_cases are
    given, executes each test case in a restricted namespace and compares
    outputs. If function_name + input_generator + claimed_class are given,
    times the function at log-spaced input sizes and verifies the slope
    matches the claimed O() class.

    Code runs in a restricted namespace: no __import__, open, eval, exec,
    compile. Suitable for user-controlled snippets, not untrusted input.
    """
    return tools.verify_computer_science(
        code, function_name, test_cases, input_generator,
        claimed_class, sizes, tolerance
    )


# ─────────────────────────────────────────────────────────────────────────
# Biology
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_biology(
    n_replicates: Optional[int] = None,
    min_replicates: int = 3,
    assay_classes: Optional[List[str]] = None,
    min_assay_classes: int = 2,
    dose_response: Optional[Dict[str, Any]] = None,
    power_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run biology checks: replicate count >= minimum, orthogonal assay
    diversity, dose-response monotonicity, sample-size adequacy via
    two-sample t-test power calculation.

    All parameters are optional. Whichever inputs you provide, the
    corresponding check runs. dose_response is a dict with
    {doses, responses, expected_direction (increasing|decreasing)}.
    power_analysis is {effect_size, alpha, n_per_group, [target_power]}.
    """
    return tools.verify_biology(
        n_replicates, min_replicates, assay_classes, min_assay_classes,
        dose_response, power_analysis
    )


# ─────────────────────────────────────────────────────────────────────────
# Governance
# ─────────────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_governance_decision_packet(
    decision_packet: Dict[str, Any],
    witness_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Verify a governance / business / household / education / church decision packet.

    Required fields: title, scope (adapter|mesh|canon), red_items (list of
    forbidden categories), floor_items (list of protective constraints),
    way_path (string describing the chosen path), execution_steps (list),
    witnesses (list of names or roles).

    Optional fields: scripture_anchors, wait_window_seconds.

    If witness_count is provided, also checks that DECISION_PACKET.witnesses
    length matches the top-level count.
    """
    return tools.verify_governance_decision_packet(decision_packet, witness_count)


def main() -> None:
    """Entry point for the MCP server. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
