"""Concordance Engine MCP Server.

Exposes the four-gate validation engine and its computational verifiers as
MCP tools that any compatible AI client (Claude Desktop, Cursor, Continue,
custom agents) can call during reasoning.

Usage:
    pip install mcp sympy scipy numpy
    pip install -e /path/to/concordance-engine
    python concordance_mcp_server.py

Then point your MCP client at this server. For Claude Desktop, add to
~/Library/Application Support/Claude/claude_desktop_config.json (macOS) or
%APPDATA%\\Claude\\claude_desktop_config.json (Windows):

    {
      "mcpServers": {
        "concordance": {
          "command": "python",
          "args": ["/absolute/path/to/concordance_mcp_server.py"]
        }
      }
    }

Tools exposed:
    validate_packet      - run the full four-gate engine on a packet
    verify_chemistry     - balance/check a chemical equation
    verify_physics       - check dimensional consistency of an equation
    verify_mathematics   - check symbolic equality, derivative, integral, etc.
    verify_statistics    - recompute p-values, check multiple-comparison correction
    verify_cs            - check static termination, functional correctness
    verify_biology       - check replicates, dose-response, statistical power
    verify_governance    - check decision packet structural completeness

All tools are deterministic, run locally, and require no network access.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from concordance_engine.engine import EngineConfig, validate_packet
from concordance_engine.verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance,
)

mcp = FastMCP("concordance")

_DEFAULT_CONFIG = EngineConfig(schema_path="", default_scope="adapter", run_verifiers=True)


def _result_to_dict(result):
    """Convert engine result to a plain dict for JSON serialization."""
    return {
        "overall": result.overall,
        "gate_results": [
            {
                "gate": gr.gate,
                "status": gr.status,
                "reasons": list(gr.reasons or []),
                "details": gr.details or {},
            }
            for gr in result.gate_results
        ],
    }


def _verifier_to_dict(vr):
    return {
        "name": vr.name,
        "status": vr.status,
        "detail": vr.detail,
        "data": vr.data or {},
    }


@mcp.tool()
def validate_packet_tool(
    packet: Dict[str, Any],
    now_epoch: int | None = None,
    skip_wait_window: bool = False,
) -> Dict[str, Any]:
    """Run the full four-gate Concordance Engine on a decision packet.

    Gates evaluated in order:
      RED      - forbidden categories + computational verifiers
      FLOOR    - protective constraints
      BROTHERS - witness count threshold
      GOD      - elapsed time since created_epoch

    Returns overall verdict (PASS, REJECT, QUARANTINE) and per-gate detail.
    Set skip_wait_window=True to bypass the GOD-gate wait (useful for testing
    a packet's structural soundness without waiting for the wait window).
    """
    effective_now = now_epoch
    if skip_wait_window:
        effective_now = 9_999_999_999
    elif effective_now is None:
        effective_now = int(time.time())

    # -- 1. Try Railway API (writes to Evidence Ledger) ----------------------
    if CONCORDANCE_API_URL:
        try:
            pkt = {**packet}
            if "created_epoch" not in pkt:
                pkt["created_epoch"] = effective_now
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
    result = validate_packet(packet, now_epoch=effective_now, config=_DEFAULT_CONFIG)
    out = _result_to_dict(result)
    out["_source"] = "local"
    return out


@mcp.tool()
def verify_chemistry(equation: str, temperature_K: float | None = None) -> Dict[str, Any]:
    """Verify or balance a chemical equation.

    Parses formulas with nested groups (Cu(OH)2) and charges (Fe^2+, MnO4^-).
    Confirms stated coefficients balance atoms and charge. If unbalanced,
    computes the smallest balancing coefficients via nullspace solver.

    Examples:
      "2 H2 + O2 -> 2 H2O"           -> CONFIRMED
      "H2 + O2 -> H2O"               -> MISMATCH (auto-balances and reports)
      "MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O"  -> CONFIRMED
    """
    results = []
    results.append(_verifier_to_dict(chemistry.verify_equation(equation)))
    if temperature_K is not None:
        results.append(_verifier_to_dict(chemistry.verify_temperature(temperature_K)))
    return {"results": results}


@mcp.tool()
def verify_physics(
    equation: str,
    symbols: Dict[str, str],
) -> Dict[str, Any]:
    """Check dimensional consistency of a physics equation.

    Substitutes unit expressions for symbols and reduces both sides to base
    SI units (kg, m, s, A, K, mol, cd) for comparison.

    Example:
      verify_physics("F = m * a", {"F": "newton", "m": "kilogram", "a": "meter/second**2"})
      -> CONFIRMED, both sides reduce to kilogram*meter/second**2
    """
    return _verifier_to_dict(physics.verify_dimensional_consistency(equation, symbols))


@mcp.tool()
def verify_mathematics(
    check_type: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Verify mathematical claims symbolically.

    check_type options:
      "equality"   - args: expr_a, expr_b, variables (list)
      "derivative" - args: function, variable, claimed_derivative
      "integral"   - args: integrand, variable, claimed_antiderivative
      "limit"      - args: function, variable, point, claimed_limit
      "solve"      - args: equation, variable, claimed_solutions (list)

    Example:
      verify_mathematics("equality",
                         expr_a="(x+1)**2",
                         expr_b="x**2 + 2*x + 1",
                         variables=["x"])
    """
    fn_map = {
        "equality": mathematics.verify_equality,
        "derivative": mathematics.verify_derivative,
        "integral": mathematics.verify_integral,
        "limit": mathematics.verify_limit,
        "solve": mathematics.verify_solve,
    }
    fn = fn_map.get(check_type)
    if fn is None:
        return {
            "name": "mathematics",
            "status": "ERROR",
            "detail": f"unknown check_type {check_type!r}; valid: {list(fn_map.keys())}",
        }
    return _verifier_to_dict(fn(kwargs))


@mcp.tool()
def verify_statistics(
    check_type: str,
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify statistical claims by recomputation.

    check_type options:
      "pvalue"              - recompute p-value from test inputs (two_sample_t,
                              one_sample_t, z, chi2, f). Required: test, claimed_p,
                              plus test-specific fields (n1, n2, mean1, mean2, etc.)
      "significance"        - check claimed_significance vs p_value at alpha
      "effect_size_present" - require effect size when result is significant
      "multiple_comparisons"- recompute Bonferroni or BH/FDR correction
      "confidence_interval" - check estimate is in [ci_low, ci_high]
    """
    fn_map = {
        "pvalue": statistics.verify_pvalue_calibration,
        "significance": statistics.verify_significance_consistency,
        "effect_size_present": statistics.verify_effect_size_present,
        "multiple_comparisons": statistics.verify_multiple_comparisons,
        "confidence_interval": statistics.verify_confidence_interval,
    }
    fn = fn_map.get(check_type)
    if fn is None:
        return {
            "name": "statistics",
            "status": "ERROR",
            "detail": f"unknown check_type {check_type!r}; valid: {list(fn_map.keys())}",
        }
    return _verifier_to_dict(fn(spec))


@mcp.tool()
def verify_cs(
    code: str,
    function_name: str | None = None,
    test_cases: list | None = None,
    input_generator: str | None = None,
    claimed_class: str | None = None,
) -> Dict[str, Any]:
    """Verify computer science claims about supplied code.

    Always runs static termination check. Optionally runs:
      - functional correctness if test_cases provided
      - runtime complexity if input_generator and claimed_class provided

    Args:
      code:             Python source defining the function
      function_name:    name of the function to test
      test_cases:       list of {args: [...], expected: ...} dicts
      input_generator:  Python source defining `def gen(n)` returning the
                        function's args at size n
      claimed_class:    O() class as string, e.g. "O(n)", "O(n**2)", "O(log n)"

    Code runs in a restricted namespace (no __import__, no open, no exec).
    Do not pass untrusted code.
    """
    results = [_verifier_to_dict(computer_science.verify_static_termination(code))]
    if function_name and test_cases:
        results.append(_verifier_to_dict(
            computer_science.verify_functional_correctness({
                "code": code, "function_name": function_name, "test_cases": test_cases,
            })
        ))
    if function_name and input_generator and claimed_class:
        results.append(_verifier_to_dict(
            computer_science.verify_runtime_complexity({
                "code": code,
                "function_name": function_name,
                "input_generator": input_generator,
                "claimed_class": claimed_class,
            })
        ))
    return {"results": results}


@mcp.tool()
def verify_biology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Verify biology claims about replicates, assays, dose-response, power.

    Recognized fields in spec:
      n_replicates, min_replicates       - replicate count check
      assay_classes, min_assay_classes   - orthogonal assay diversity
      dose_response: {doses, responses, expected_direction}  - monotonicity
      power_analysis: {effect_size, alpha, n_per_group}      - sample size
    """
    return {"results": [_verifier_to_dict(r) for r in biology.run({"BIO_VERIFY": spec})]}


@mcp.tool()
def verify_governance(decision_packet: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a governance decision packet's structural completeness.

    Required fields in decision_packet:
      title, scope, red_items, floor_items, way_path, execution_steps, witnesses

    Optional:
      wait_window_seconds, scripture_anchors

    The verifier checks structural completeness only. It does not judge
    whether a particular decision is wise.
    """
    return _verifier_to_dict(governance.verify_decision_packet_shape(decision_packet))


@mcp.tool()
def suggest_fix(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Run the engine on a packet and, if it rejects, return actionable fix guidance.

    For verifier rejections, the underlying verifier often computes the
    correct answer (e.g. balanced coefficients) and that information is
    surfaced here for the caller to apply.
    """
    result = validate_packet(packet, now_epoch=9_999_999_999, config=_DEFAULT_CONFIG)
    out = _result_to_dict(result)
    if result.overall != "REJECT":
        out["fix"] = None
        return out

    fix_hints = []
    for gr in result.gate_results:
        if gr.status != "REJECT":
            continue
        details = gr.details or {}
        for v in details.get("verifier_failures", []) or []:
            data = v.get("data") or {}
            if "balanced_lhs" in data and "balanced_rhs" in data:
                fix_hints.append(
                    f"Replace equation with balanced form: "
                    f"{data['balanced_lhs']} -> {data['balanced_rhs']}"
                )
            elif "lhs_units" in data and "rhs_units" in data:
                fix_hints.append(
                    f"Dimensional mismatch. LHS={data['lhs_units']}, RHS={data['rhs_units']}. "
                    f"Check unit declarations or correct the equation."
                )
            elif "recomputed_p" in data and "claimed_p" not in v.get("name", ""):
                fix_hints.append(
                    f"Recomputed p-value is {data['recomputed_p']:.6g}. "
                    f"Update the claim to match or correct the test inputs."
                )
            elif "computed" in data:
                fix_hints.append(
                    f"Verifier computed {data['computed']}; you claimed {data.get('claimed', '?')}."
                )
            elif "failures" in data:
                fix_hints.extend(data["failures"])
        for reason in gr.reasons or []:
            if reason and not any(reason in h for h in fix_hints):
                fix_hints.append(reason)
    out["fix"] = fix_hints
    return out


if __name__ == "__main__":
    mcp.run()
