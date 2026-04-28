"""MCP tool implementations.

Two consumers share these implementations:
  * FastMCP server (``server.py``) imports the function-style API directly.
    Used in production when the official `mcp` SDK is installed.
  * Stdlib server (``stdlib_server.py``) uses the list-style API
    (``TOOLS``, ``list_tools``, ``call_tool``). Used as a fallback or for
    testing in environments without the SDK.

Both call the same underlying verifier code, so behavior is identical.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..engine import EngineConfig, validate_packet as _engine_validate
from ..verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance,
)
from ..verifiers.base import VerifierResult


def _r(r: VerifierResult) -> Dict[str, Any]:
    return {"status": r.status, "detail": r.detail, "data": r.data}


# ─────────────────────────────────────────────────────────────────────
# Function-style API (FastMCP)
# ─────────────────────────────────────────────────────────────────────

def validate_packet(packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    res = _engine_validate(packet, now_epoch=now_epoch, config=cfg)
    return {
        "overall": res.overall,
        "gate_results": [
            {"gate": gr.gate, "status": gr.status,
             "reasons": gr.reasons, "details": gr.details}
            for gr in res.gate_results
        ],
    }


def verify_chemistry(equation: str, temperature_K: Optional[float] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    eq_r = chemistry.verify_equation(equation, balance_if_unbalanced=True)
    out["equation"] = _r(eq_r)
    if eq_r.status == "MISMATCH" and eq_r.data and "balanced_lhs" in eq_r.data:
        out["balanced_form"] = f"{eq_r.data['balanced_lhs']} -> {eq_r.data['balanced_rhs']}"
        out["balanced_coefficients"] = eq_r.data.get("balanced_coefficients")
    if temperature_K is not None:
        out["temperature"] = _r(chemistry.verify_temperature(temperature_K))
    return out


def verify_physics_dimensional(equation: str, symbols: Dict[str, str]) -> Dict[str, Any]:
    return _r(physics.verify_dimensional_consistency(equation, symbols))


def verify_physics_conservation(
    before: Dict[str, float], after: Dict[str, float],
    tolerance_relative: float = 1e-6, tolerance_absolute: float = 0.0,
) -> Dict[str, Any]:
    return _r(physics.verify_conservation(
        before, after,
        tolerance_relative=tolerance_relative,
        tolerance_absolute=tolerance_absolute,
    ))


def verify_mathematics(mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Five-mode dispatcher. mode = equality|derivative|integral|limit|solve."""
    mode = (mode or "").lower()
    out: Dict[str, Any] = {}

    import sympy as sp

    if mode == "equality":
        return _r(mathematics.verify_equality(params))

    if mode == "derivative":
        function = params["function"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        actual = sp.diff(f, x)
        out["computed_derivative"] = str(actual)
        if "claimed_derivative" in params:
            out.update(_r(mathematics.verify_derivative(params)))
        else:
            out["status"] = "CONFIRMED"
            out["detail"] = f"d/d{variable} of {function} = {actual}"
        return out

    if mode == "integral":
        integrand = params["integrand"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(integrand, locals={variable: x})
        try:
            anti = sp.integrate(f, x)
            out["computed_antiderivative"] = str(anti)
        except Exception as e:
            out["computed_antiderivative"] = None
            out["compute_error"] = str(e)
        if "claimed_antiderivative" in params:
            out.update(_r(mathematics.verify_integral(params)))
        return out

    if mode == "limit":
        function = params["function"]
        variable = params.get("variable", "x")
        point = params["point"]
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        try:
            actual = sp.limit(f, x, sp.sympify(str(point)))
            out["computed_limit"] = str(actual)
        except Exception as e:
            out["computed_limit"] = None
            out["compute_error"] = str(e)
        if "claimed_limit" in params:
            out.update(_r(mathematics.verify_limit(params)))
        return out

    if mode == "solve":
        eq = params["equation"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        if "=" in eq and "==" not in eq:
            lhs, rhs = eq.split("=", 1)
            eq_expr = sp.sympify(lhs, locals={variable: x}) - sp.sympify(rhs, locals={variable: x})
        else:
            eq_expr = sp.sympify(eq, locals={variable: x})
        actual = [str(s) for s in sp.solve(eq_expr, x)]
        out["computed_solutions"] = actual
        if "claimed_solutions" in params:
            out.update(_r(mathematics.verify_solve(params)))
        return out

    return {"status": "ERROR", "detail": f"unknown mode {mode!r}",
            "data": {"valid_modes": ["equality", "derivative", "integral", "limit", "solve"]}}


def verify_statistics_pvalue(spec: Dict[str, Any]) -> Dict[str, Any]:
    return _r(statistics.verify_pvalue_calibration(spec))


def verify_statistics_multiple_comparisons(
    raw_p_values: List[float], method: str, alpha: float = 0.05,
    claimed_rejected_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    spec = {"raw_p_values": raw_p_values, "method": method, "alpha": alpha}
    if claimed_rejected_indices is not None:
        spec["claimed_rejected_indices"] = claimed_rejected_indices
    return _r(statistics.verify_multiple_comparisons(spec))


def verify_statistics_confidence_interval(
    estimate: float, ci_low: float, ci_high: float,
) -> Dict[str, Any]:
    return _r(statistics.verify_confidence_interval({
        "estimate": estimate, "ci_low": ci_low, "ci_high": ci_high,
    }))


def verify_computer_science(
    code: str,
    function_name: Optional[str] = None,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    input_generator: Optional[str] = None,
    claimed_class: Optional[str] = None,
    sizes: Optional[List[int]] = None,
    tolerance: float = 0.40,
) -> Dict[str, Any]:
    out = {"static_termination": _r(computer_science.verify_static_termination(code))}
    if function_name and test_cases:
        out["functional_correctness"] = _r(computer_science.verify_functional_correctness({
            "code": code, "function_name": function_name, "test_cases": test_cases,
        }))
    if function_name and input_generator and claimed_class:
        spec = {
            "code": code, "function_name": function_name,
            "input_generator": input_generator, "claimed_class": claimed_class,
            "tolerance": tolerance,
        }
        if sizes is not None:
            spec["sizes"] = sizes
        out["runtime_complexity"] = _r(computer_science.verify_runtime_complexity(spec))
    return out


def verify_biology(
    n_replicates: Optional[int] = None,
    min_replicates: int = 3,
    assay_classes: Optional[List[str]] = None,
    min_assay_classes: int = 2,
    dose_response: Optional[Dict[str, Any]] = None,
    power_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    spec: Dict[str, Any] = {}
    if n_replicates is not None:
        spec["n_replicates"] = n_replicates
        spec["min_replicates"] = min_replicates
    if assay_classes is not None:
        spec["assay_classes"] = assay_classes
        spec["min_assay_classes"] = min_assay_classes
    if dose_response is not None:
        spec["dose_response"] = dose_response
    if power_analysis is not None:
        spec["power_analysis"] = power_analysis
    results = biology.run({"BIO_VERIFY": spec})
    return {"checks": [_r(r) for r in results]}


def verify_governance_decision_packet(
    decision_packet: Dict[str, Any],
    witness_count: Optional[int] = None,
) -> Dict[str, Any]:
    out = {"shape": _r(governance.verify_decision_packet_shape(decision_packet))}
    if witness_count is not None:
        out["witness_consistency"] = _r(
            governance.verify_witness_count_consistency(
                decision_packet, {"witness_count": witness_count}
            )
        )
    return out


def get_example_packet(name: str) -> Dict[str, Any]:
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "examples",
    )
    candidates = [
        f"sample_packet_{name}.json",
        f"sample_packet_{name}_verify.json",
        f"sample_packet_jda_{name}.json",
        f"{name}.json",
    ]
    for c in candidates:
        path = os.path.join(examples_dir, c)
        if os.path.exists(path):
            with open(path) as f:
                return {"name": c, "packet": json.load(f)}
    available = sorted([f for f in os.listdir(examples_dir) if f.endswith(".json")])
    return {"error": f"no example named {name!r}", "available": available}


# ─────────────────────────────────────────────────────────────────────
# List-style API (stdlib server)
# ─────────────────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "validate_packet",
        "description": (
            "Run a packet through the full Four-Gates engine (RED, FLOOR, BROTHERS, GOD). "
            "Routes to the domain validator and verifier, then enforces witness-count and "
            "time-wait gates. Returns overall PASS / REJECT / QUARANTINE plus gate-by-gate detail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "packet": {"type": "object"},
                "now_epoch": {"type": "integer"},
            },
            "required": ["packet"],
        },
        "fn": lambda a: validate_packet(a["packet"], a.get("now_epoch")),
    },
    {
        "name": "verify_chemistry",
        "description": (
            "Verify a chemical equation balances, or compute the smallest balancing "
            "coefficients. Handles charges (Fe^2+, MnO4^-) and nested groups (Cu(OH)2). "
            "Optionally checks temperature_K is positive."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string"},
                "temperature_K": {"type": "number"},
            },
            "required": ["equation"],
        },
        "fn": lambda a: verify_chemistry(a["equation"], a.get("temperature_K")),
    },
    {
        "name": "verify_physics_dimensional",
        "description": (
            "Verify both sides of a physics equation reduce to the same SI units. "
            "Substitutes unit expressions for symbols, converts to base SI."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string"},
                "symbols": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "required": ["equation", "symbols"],
        },
        "fn": lambda a: verify_physics_dimensional(a["equation"], a["symbols"]),
    },
    {
        "name": "verify_physics_conservation",
        "description": "Verify per-quantity conservation between before and after states within tolerance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "object", "additionalProperties": {"type": "number"}},
                "after": {"type": "object", "additionalProperties": {"type": "number"}},
                "tolerance_relative": {"type": "number", "default": 1e-6},
                "tolerance_absolute": {"type": "number", "default": 0.0},
            },
            "required": ["before", "after"],
        },
        "fn": lambda a: verify_physics_conservation(
            a["before"], a["after"],
            a.get("tolerance_relative", 1e-6), a.get("tolerance_absolute", 0.0),
        ),
    },
    {
        "name": "verify_mathematics",
        "description": (
            "Sympy-based math verification. mode = equality | derivative | integral | "
            "limit | solve. Returns the computed answer when applicable, plus YES/NO if a "
            "claim was supplied."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["equality", "derivative", "integral", "limit", "solve"]},
                "params": {"type": "object"},
            },
            "required": ["mode", "params"],
        },
        "fn": lambda a: verify_mathematics(a["mode"], a["params"]),
    },
    {
        "name": "verify_statistics_pvalue",
        "description": (
            "Recompute a p-value from supplied test inputs and verify against claimed_p. "
            "Tests: two_sample_t, one_sample_t, z, chi2, f."
        ),
        "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
        "fn": lambda a: verify_statistics_pvalue(a["spec"]),
    },
    {
        "name": "verify_statistics_multiple_comparisons",
        "description": "Apply Bonferroni or BH/FDR to raw p-values; return adjusted p and rejected indices.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_p_values": {"type": "array", "items": {"type": "number"}},
                "method": {"type": "string", "enum": ["bonferroni", "bh"]},
                "alpha": {"type": "number", "default": 0.05},
                "claimed_rejected_indices": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["raw_p_values", "method"],
        },
        "fn": lambda a: verify_statistics_multiple_comparisons(
            a["raw_p_values"], a["method"], a.get("alpha", 0.05),
            a.get("claimed_rejected_indices"),
        ),
    },
    {
        "name": "verify_statistics_confidence_interval",
        "description": "Verify a CI is well-formed (low <= high) and contains the point estimate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "estimate": {"type": "number"},
                "ci_low": {"type": "number"},
                "ci_high": {"type": "number"},
            },
            "required": ["estimate", "ci_low", "ci_high"],
        },
        "fn": lambda a: verify_statistics_confidence_interval(
            a["estimate"], a["ci_low"], a["ci_high"],
        ),
    },
    {
        "name": "verify_computer_science",
        "description": (
            "Verify Python code: termination (static AST), functional correctness "
            "(restricted-namespace execution), runtime complexity (log-log slope fit). "
            "Returns whichever checks the supplied inputs enable."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "function_name": {"type": "string"},
                "test_cases": {"type": "array"},
                "input_generator": {"type": "string"},
                "claimed_class": {"type": "string", "enum": ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n**2)", "O(n**3)"]},
                "sizes": {"type": "array", "items": {"type": "integer"}},
                "tolerance": {"type": "number", "default": 0.40},
            },
            "required": ["code"],
        },
        "fn": lambda a: verify_computer_science(
            a["code"], a.get("function_name"), a.get("test_cases"),
            a.get("input_generator"), a.get("claimed_class"),
            a.get("sizes"), a.get("tolerance", 0.40),
        ),
    },
    {
        "name": "verify_biology",
        "description": (
            "Run biology design checks: replicate count, orthogonal assay diversity, "
            "dose-response monotonicity, sample-size adequacy via two-sample t power."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "n_replicates": {"type": "integer"},
                "min_replicates": {"type": "integer", "default": 3},
                "assay_classes": {"type": "array", "items": {"type": "string"}},
                "min_assay_classes": {"type": "integer", "default": 2},
                "dose_response": {"type": "object"},
                "power_analysis": {"type": "object"},
            },
        },
        "fn": lambda a: verify_biology(
            a.get("n_replicates"), a.get("min_replicates", 3),
            a.get("assay_classes"), a.get("min_assay_classes", 2),
            a.get("dose_response"), a.get("power_analysis"),
        ),
    },
    {
        "name": "verify_governance_decision_packet",
        "description": (
            "Structural check on a governance / business / household / education / "
            "church decision packet. Verifies title, scope, red_items, floor_items, "
            "way_path, execution_steps, witnesses are present and well-formed. "
            "Use BEFORE bringing a decision to a board meeting."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision_packet": {"type": "object"},
                "witness_count": {"type": "integer"},
            },
            "required": ["decision_packet"],
        },
        "fn": lambda a: verify_governance_decision_packet(
            a["decision_packet"], a.get("witness_count"),
        ),
    },
    {
        "name": "get_example_packet",
        "description": (
            "Return a canonical example packet by name. Names: chemistry, physics, math, "
            "statistics, cs, cs_runtime, biology, governance, jda_phase1_fund."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        "fn": lambda a: get_example_packet(a["name"]),
    },
]


TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools() -> List[Dict[str, Any]]:
    """Return MCP-shaped tool definitions (no `fn` field)."""
    return [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}", "available": list(TOOL_BY_NAME.keys())}
    try:
        return tool["fn"](arguments or {})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
