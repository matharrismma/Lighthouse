"""
Concordance Engine MCP Server — narrowhighway.com

An authority-based verification and decision-recording engine for AI agents.

When an agent is about to take an irreversible action, state a computational
fact, or record a governance decision, this engine checks that claim against
fixed external authorities before it proceeds. It does not poll other models.
It does not require consensus. It computes.

Four-gate validation for decisions:
  RED      — scans for coercion, unilateral authority, rights violations
  FLOOR    — verifies structural completeness
  BROTHERS — confirms witness count and elapsed review time
  GOD      — records permanently if prior gates clear

Computational verifiers for claims:
  Chemistry   — equation balancing, charge conservation
  Physics     — dimensional consistency, conservation laws
  Mathematics — symbolic equality, derivatives, integrals, limits
  Statistics  — p-value recomputation, multiple comparison correction
  CS          — static termination, functional correctness, complexity
  Biology     — replication standards, dose-response, power analysis
  Governance  — decision packet structural completeness

All verifiers are deterministic and run locally. No network calls. No LLM.
Results are CONFIRMED, MISMATCH, ERROR, or SKIPPED — never ambiguous.

API reference: https://narrowhighway.com/docs
Source: https://github.com/matharrismma/Lighthouse
"""
from __future__ import annotations
import json
import time
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from concordance_engine.engine import EngineConfig, validate_packet
from concordance_engine.verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance,
)

mcp = FastMCP("concordance")

_DEFAULT_CONFIG = EngineConfig(run_verifiers=True)


def _verifier_to_dict(vr) -> Dict[str, Any]:
    return {"name": vr.name, "status": vr.status, "detail": vr.detail, "data": vr.data}


def _result_to_dict(result) -> Dict[str, Any]:
    return {
        "overall": result.overall,
        "gate_results": [
            {
                "gate": gr.gate,
                "status": gr.status,
                "reasons": gr.reasons,
                "details": gr.details,
            }
            for gr in result.gate_results
        ],
    }


@mcp.tool()
def validate_packet_tool(
    packet: Dict[str, Any],
    now_epoch: int | None = None,
    skip_wait_window: bool = False,
) -> Dict[str, Any]:
    """Check a governance or scientific decision packet through the four-gate engine.

    Call this tool before:
    - Recording, executing, or recommending any irreversible decision
    - Committing resources, personnel, or authority on behalf of an organization
    - Finalizing a claim that will be treated as an institutional record

    Do NOT call this for routine information retrieval, conversation, or
    reversible suggestions. Call it when the action cannot be undone.

    Gates run in order. First failure determines the verdict:
      RED      — REJECT if coercion, unilateral authority, or rights violations detected
      FLOOR    — REJECT if structurally incomplete or internally inconsistent
      BROTHERS — QUARANTINE if insufficient witnesses or review time has not elapsed
      GOD      — PASS, decision recorded permanently

    Packet schema (governance domain):
    {
      "domain": "governance",
      "witness_count": <int>,
      "created_epoch": <unix timestamp when decision was first proposed>,
      "DECISION_PACKET": {
        "title": "<short description>",
        "decision": "<what is being decided>",
        "rationale": "<why>",
        "scope": "adapter|local|mesh|canon|kernel",
        "red_items": ["<what was checked for coercion>", ...],
        "floor_items": ["<minimum standards confirmed>", ...],
        "way_path": "<process followed>",
        "execution_steps": ["<step 1>", ...],
        "witnesses": ["<name>", ...],
        "witness_count": <int>,
        "scripture_anchors": ["<ref>", ...]  // optional
      }
    }

    Returns overall verdict (PASS | REJECT | QUARANTINE) with per-gate detail
    and specific reasons for any failure, allowing the agent to correct and retry.

    Set skip_wait_window=True when validating packet structure without requiring
    the review window to have elapsed (useful for pre-flight checks).
    """
    effective_now = now_epoch
    if skip_wait_window:
        effective_now = 9_999_999_999
    elif effective_now is None:
        effective_now = int(time.time())

    result = validate_packet(packet, now_epoch=effective_now, config=_DEFAULT_CONFIG)
    return _result_to_dict(result)


@mcp.tool()
def verify_chemistry(equation: str, temperature_K: float | None = None) -> Dict[str, Any]:
    """Verify a chemical equation is balanced before stating it as fact.

    Call this when about to assert that a chemical equation is correct,
    use an equation as the basis for further reasoning, or present reaction
    stoichiometry to a user as verified.

    If unbalanced, the engine computes the correct coefficients via null-space
    solver and returns them so the agent can correct the claim.

    Handles: nested groups (Cu(OH)2), ionic charges (Fe^2+, MnO4^-),
    coefficients, and multi-step redox reactions.

    temperature_K: optionally verify a stated temperature is physically valid (> 0 K).

    Returns CONFIRMED if balanced, MISMATCH with corrected form if not.
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
    """Verify dimensional consistency of a physics equation before stating it as fact.

    Call this when about to assert that a physics equation is dimensionally
    correct, present it as verified, or use it as the basis for calculation.

    Substitutes unit expressions for each symbol and reduces both sides to
    base SI units (kg, m, s, A, K, mol, cd) for comparison.

    symbols: mapping of variable name to unit expression.
      Valid units: newton, joule, watt, pascal, volt, ampere, kilogram,
                   meter, second, kelvin, and combinations thereof.

    Example:
      equation = "F = m * a"
      symbols = {"F": "newton", "m": "kilogram", "a": "meter/second**2"}
      -> CONFIRMED

    Returns CONFIRMED if dimensionally consistent, MISMATCH with unit
    breakdown if not.
    """
    return _verifier_to_dict(physics.verify_dimensional_consistency(equation, symbols))


@mcp.tool()
def verify_mathematics(
    check_type: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Verify a mathematical claim symbolically before stating it as fact.

    Call this when about to assert that two expressions are equal, a derivative
    or integral is correct, a limit evaluates to a specific value, or an equation
    has specific solutions. Use before presenting mathematical claims as verified.

    check_type and required kwargs:
      "equality"   — expr_a, expr_b, variables (list of str)
      "derivative" — function, variable, claimed_derivative
      "integral"   — integrand, variable, claimed_antiderivative
      "limit"      — function, variable, point, claimed_limit
      "solve"      — equation, variable, claimed_solutions (list)

    All symbolic computation uses SymPy. Results are exact, not numeric.

    Returns CONFIRMED if the claim holds symbolically, MISMATCH with the
    computed value if it does not.
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
    """Verify a statistical claim by recomputation before stating it as fact.

    Call this when about to assert a p-value, significance determination,
    corrected threshold, or confidence interval is correct. Use before
    presenting statistical conclusions as verified.

    The engine recomputes the statistic from raw inputs using SciPy and
    compares to the claimed value. It does not trust stated results.

    check_type options and required spec fields:
      "pvalue" — recompute from scratch
        test: two_sample_t | one_sample_t | z | chi2 | f
        claimed_p: <float>
        test-specific: n1, n2, mean1, mean2, sd (for t-tests); etc.

      "significance" — verify claimed significance matches p vs alpha
        p_value, alpha, claimed_significance: true|false

      "effect_size_present" — flag significant results without effect size
        p_value, alpha, effect_size_reported: true|false

      "multiple_comparisons" — verify corrected rejection thresholds
        method: bonferroni|bh
        p_values: [list], alpha, claimed_rejections: [list of bool]

      "confidence_interval" — verify estimate falls within stated CI
        estimate, ci_low, ci_high

    Returns CONFIRMED if the claim is correct, MISMATCH with the recomputed
    value if not.
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
    """Verify correctness and termination properties of code before presenting as verified.

    Call this when about to assert that a function terminates, produces correct
    output for given inputs, or has a specific runtime complexity. Use before
    presenting code behavior claims as verified.

    Always runs:
      Static termination check — detects while True without break,
      unguarded recursion (no base case in if/ternary).

    Runs if function_name + test_cases provided:
      Functional correctness — executes against test cases in a restricted
      sandbox (no __import__, no open, no exec).

    Runs if function_name + input_generator + claimed_class provided:
      Runtime complexity — times at multiple sizes, fits growth curve,
      compares to claimed O() class.

    claimed_class format: "O(n)", "O(n**2)", "O(n log n)", "O(log n)", "O(1)"

    Returns list of results, one per check run.
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
    """Verify biological experimental claims before presenting as verified.

    Call this when about to assert that a biological experiment meets
    replication standards, demonstrates dose-response, or is adequately
    powered. Use before presenting experimental conclusions as verified.

    spec fields (include whichever apply):
      n_replicates, min_replicates (default 3)
        — verify replicate count meets minimum

      assay_classes: [list of str], min_assay_classes (default 2)
        — verify orthogonal assay diversity

      dose_response: {doses: [list], responses: [list], expected_direction: "increasing"|"decreasing"}
        — verify monotonicity

      power_analysis: {effect_size: float, alpha: float, n_per_group: int}
        — verify sample size is adequately powered (uses normal approximation)

    Returns list of results, one per check requested.
    """
    return {"results": [_verifier_to_dict(r) for r in biology.run({"BIO_VERIFY": spec})]}


@mcp.tool()
def verify_governance(decision_packet: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a governance decision packet is structurally complete.

    Call this as a pre-flight check before running the full four-gate engine,
    or when only structural completeness is needed without the witness/timing
    gates. Checks that all required fields are present and non-empty, scope
    is valid, and witness count is internally consistent.

    Required fields: title, scope, red_items, floor_items, way_path,
                     execution_steps, witnesses
    Valid scopes: adapter | local | mesh | canon | kernel

    Returns CONFIRMED if complete, MISMATCH with specific missing fields if not.
    Use the returned field list to construct a complete packet before calling
    validate_packet_tool.
    """
    return _verifier_to_dict(governance.verify_decision_packet_shape(decision_packet))


@mcp.tool()
def suggest_fix(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Run the engine and return specific corrective actions for any failures.

    Call this when validate_packet_tool returned REJECT or QUARANTINE and
    the agent needs to know exactly what to change before retrying.

    Returns the same verdict as validate_packet_tool plus a fix list: each
    entry is a concrete action the agent can take — corrected equation
    coefficients, recomputed p-value, missing fields, witness requirements.

    The fix list is designed to be acted on directly, not summarized.
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
                    f"Dimensional mismatch. LHS={data['lhs_units']}, RHS={data['rhs_units']}."
                )
            elif "recomputed_p" in data:
                fix_hints.append(
                    f"Recomputed p-value is {data['recomputed_p']:.6g}. Correct the claim."
                )
            elif "computed" in data:
                fix_hints.append(
                    f"Engine computed {data['computed']}; claimed {data.get('claimed', '?')}."
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
