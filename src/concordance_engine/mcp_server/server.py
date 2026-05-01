"""MCP server exposing the Concordance Engine verifier layer.

Run as:
    python -m concordance_engine.mcp_server
or after install:
    concordance-mcp

Configure Claude Desktop with:
{
  "mcpServers": {
    "concordance": {
      "command": "concordance-mcp"
    }
  }
}

Or for development from the source tree:
{
  "mcpServers": {
    "concordance": {
      "command": "python",
      "args": ["-m", "concordance_engine.mcp_server"],
      "env": {"PYTHONPATH": "/path/to/Lighthouse/lw/01_engine/concordance-engine/src"}
    }
  }
}

This file requires the `mcp` package (mcp >= 1.0.0). Install via:
    pip install -e ".[mcp]"

Environment variables:
    CONCORDANCE_API_URL   - Override the API base URL (default: https://narrowhighway.com)
    CONCORDANCE_API_KEY   - API key for authenticated endpoints
"""
from __future__ import annotations

import json
import os
import time as _time
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

mcp = FastMCP("concordance")

# Hosted API -- set CONCORDANCE_API_URL to override.
CONCORDANCE_API_URL = os.environ.get(
    "CONCORDANCE_API_URL",
    "https://narrowhighway.com",
)
CONCORDANCE_API_KEY = os.environ.get(
    "CONCORDANCE_API_KEY",
    "lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4",
)


# ---------------------------------------------------------------------------
# Full engine
# ---------------------------------------------------------------------------

@mcp.tool()
def validate_packet(packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """Run all four gates against a decision or claim packet: RED, FLOOR, BROTHERS, GOD.

    RED     -- Rejects coercion, unilateral authority, rights violations, hard computational failures.
    FLOOR   -- Rejects structurally incomplete or internally inconsistent packets.
    BROTHERS -- Quarantines if insufficient witnesses or review window has not elapsed.
    GOD     -- Records permanently in the append-only ledger if all prior gates pass.

    Attempts the hosted API first (writes to the Evidence Ledger);
    falls back to local computation if the API is unreachable.

    Returns: {overall: PASS|QUARANTINE|REJECT, gate_results: [...]}.
    """
    if CONCORDANCE_API_URL:
        try:
            pkt = {**packet}
            if "created_epoch" not in pkt:
                pkt["created_epoch"] = now_epoch or int(_time.time())
            payload = json.dumps({"packet": pkt}).encode()
            headers = {"Content-Type": "application/json"}
            if CONCORDANCE_API_KEY:
                headers["x-api-key"] = CONCORDANCE_API_KEY
            req = urllib.request.Request(
                f"{CONCORDANCE_API_URL.rstrip('/')}/validate",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                api_result = json.loads(resp.read().decode())
            api_result["_source"] = "api"
            return api_result
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            pass
    out = tools.validate_packet(packet, now_epoch)
    out["_source"] = "local"
    return out


# ---------------------------------------------------------------------------
# Chemistry
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_chemistry(equation: str, temperature_K: Optional[float] = None) -> Dict[str, Any]:
    """Verify a chemical equation balances (atoms and charge) and optionally
    that the temperature is physical (positive Kelvin).

    Equation format: '2 H2 + O2 -> 2 H2O'. Supports nested groups (Cu(OH)2),
    charges (Fe^2+, MnO4^-), and ionic forms. On MISMATCH, returns the
    correctly balanced coefficients in data.balanced_lhs / balanced_rhs.
    """
    return tools.verify_chemistry(equation, temperature_K)


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_physics_dimensional(equation: str, symbols: Dict[str, str]) -> Dict[str, Any]:
    """Verify both sides of a physics equation reduce to the same SI dimensions.

    symbols maps each variable to its named unit
    (e.g. {"F": "newton", "m": "kilogram", "a": "meter/second**2"}).
    Both sides are converted to base SI units and compared.
    """
    return tools.verify_physics_dimensional(equation, symbols)


@mcp.tool()
def verify_physics_conservation(
    before: Dict[str, float],
    after: Dict[str, float],
    tolerance_relative: float = 1e-6,
    tolerance_absolute: float = 0.0,
) -> Dict[str, Any]:
    """Verify each named conserved quantity is preserved within tolerance.

    before and after are dicts of quantity_name -> numeric_value.
    A quantity passes if its relative change <= tolerance_relative OR
    its absolute change <= tolerance_absolute.
    """
    return tools.verify_physics_conservation(before, after, tolerance_relative, tolerance_absolute)


# ---------------------------------------------------------------------------
# Mathematics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_mathematics(mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Sympy-based math verification across nine modes.

    mode: equality | derivative | integral | limit | solve | matrix | inequality | series | ode

    params per mode:
      equality:    {expr_a, expr_b, variables: [...]}
      derivative:  {function, variable, claimed_derivative}
      integral:    {integrand, variable, claimed_antiderivative}
      limit:       {function, variable, point, claimed_limit}
      solve:       {equation, variable, claimed_solutions: [...]}
    """
    return tools.verify_mathematics(mode, params)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_statistics_pvalue(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute a p-value from supplied test inputs and verify against claimed_p.

    spec must include 'test' (one of: two_sample_t, one_sample_t, z, chi2, f)
    plus the corresponding inputs. Optional: claimed_p (to verify), tolerance (default 1e-3).
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


# ---------------------------------------------------------------------------
# Computer Science
# ---------------------------------------------------------------------------

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
    """Verify Python code: static termination, functional correctness, runtime complexity.

    Always runs static termination scan. If function_name + test_cases are
    given, executes each test case in a restricted namespace and compares
    outputs. If function_name + input_generator + claimed_class are given,
    times the function at log-spaced sizes and verifies the O() class.

    Code runs in a restricted namespace: no __import__, open, eval, exec.
    """
    return tools.verify_computer_science(
        code, function_name, test_cases, input_generator,
        claimed_class, sizes, tolerance
    )


# ---------------------------------------------------------------------------
# Biology (standard + nested health control systems)
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_biology(
    n_replicates: Optional[int] = None,
    min_replicates: int = 3,
    assay_classes: Optional[List[str]] = None,
    min_assay_classes: int = 2,
    dose_response: Optional[Dict[str, Any]] = None,
    power_analysis: Optional[Dict[str, Any]] = None,
    bio_control: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run biology checks: replicate count, assay diversity, dose-response
    monotonicity, sample-size power, and nested health control systems.

    Standard checks (any combination):
      n_replicates + min_replicates -- replicate count adequacy
      assay_classes + min_assay_classes -- orthogonal assay diversity
      dose_response -- {doses, responses, expected_direction}
      power_analysis -- {effect_size, alpha, n_per_group, [target_power]}

    Health control systems check (bio_control dict):
      failure_mode: setpoint_drift | loop_saturation | compensation_collapse |
                    cross_layer_override | sensor_failure
      failure_layer: L1 | L2 | L3 | L4 | L5 | L6
      intervention_layers: [L1, L3, ...]
      upper_layer_driver_addressed: bool  (required for cross_layer_override)
      setpoint_shift_mechanism_stated: bool  (required for setpoint_drift)
      sensor_recalibration_plan: bool  (required for sensor_failure)

    Returns: {checks: [{status, detail, data}, ...]}
    """
    return tools.verify_biology(
        n_replicates, min_replicates, assay_classes, min_assay_classes,
        dose_response, power_analysis, bio_control=bio_control
    )


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_governance_decision_packet(
    decision_packet: Dict[str, Any],
    witness_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Verify a governance / business / household / education / church decision packet.

    Required fields: title, scope (adapter|local|mesh|canon|kernel), red_items,
    floor_items, way_path, execution_steps, witnesses.

    Optional: scripture_anchors, wait_window_seconds.

    If witness_count is provided, also checks DECISION_PACKET.witnesses length matches.
    """
    return tools.verify_governance_decision_packet(decision_packet, witness_count)


def main() -> None:
    """Entry point for the MCP server. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
