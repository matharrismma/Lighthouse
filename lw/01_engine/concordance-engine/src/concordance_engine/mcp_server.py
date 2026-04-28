"""Concordance Engine MCP Server.

Exposes the verifier layer as tools any MCP-capable assistant can call.
Communicates over stdio using JSON-RPC 2.0 per the MCP specification.

Run as: `concordance-mcp` (after pip install) or `python -m concordance_engine.mcp_server`.

Register with Claude Desktop by adding to claude_desktop_config.json:
    {
      "mcpServers": {
        "concordance": {
          "command": "concordance-mcp"
        }
      }
    }

The server exposes:
  * Domain-specific verification tools (chemistry, physics, math, stats, code,
    biology, governance) that return CONFIRMED, MISMATCH, NOT_APPLICABLE, or ERROR
  * A full-packet validator that runs all four gates

No network calls. Code execution in the CS verifier runs in a restricted
namespace (no __import__, open, eval, exec, compile).
"""
from __future__ import annotations
import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from .verifiers import chemistry, physics, mathematics, statistics, computer_science, biology, governance
from .engine import EngineConfig, validate_packet


# ── JSON-RPC framing over stdio ──────────────────────────────────────────────

def _read_message() -> Optional[Dict[str, Any]]:
    """Read a single JSON-RPC message from stdin (one line per message)."""
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return _read_message()
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}


def _write_message(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# ── Tool helpers ─────────────────────────────────────────────────────────────

def _format_result(verifier_result) -> str:
    """Render a VerifierResult as a single text block for the MCP client."""
    parts = [f"[{verifier_result.status}] {verifier_result.name}"]
    if verifier_result.detail:
        parts.append(verifier_result.detail)
    if verifier_result.data:
        parts.append("Data: " + json.dumps(verifier_result.data, default=str))
    return "\n".join(parts)


def _text_content(text: str) -> List[Dict[str, str]]:
    return [{"type": "text", "text": text}]


# ── Tool definitions (name → (description, inputSchema, handler)) ────────────

TOOLS: Dict[str, Dict[str, Any]] = {}


def _register(name: str, description: str, input_schema: Dict[str, Any], handler):
    TOOLS[name] = {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "_handler": handler,
    }


# Chemistry --------------------------------------------------------------------

def _chem_balance(args: Dict[str, Any]) -> str:
    eq = args["equation"]
    r = chemistry.verify_equation(eq, balance_if_unbalanced=True)
    return _format_result(r)


_register(
    "chemistry_verify_equation",
    "Verify or balance a chemical equation. Parses formulas with nested groups "
    "(e.g. Cu(OH)2) and charges (e.g. Fe^2+, MnO4^-). If coefficients are stated "
    "and balance, returns CONFIRMED. If they don't balance, returns MISMATCH with "
    "the correct smallest integer coefficients. Examples: 'C3H8 + 5 O2 -> 3 CO2 + 4 H2O', "
    "'MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O'.",
    {
        "type": "object",
        "properties": {
            "equation": {
                "type": "string",
                "description": "A chemical equation with '->' or '→' separating reactants and products. Species are joined by ' + ' (whitespace required). Coefficients may be omitted to request balancing."
            }
        },
        "required": ["equation"],
    },
    _chem_balance,
)


def _chem_temperature(args: Dict[str, Any]) -> str:
    r = chemistry.verify_temperature(args["temperature_K"])
    return _format_result(r)


_register(
    "chemistry_verify_temperature",
    "Verify a temperature is a positive absolute temperature (Kelvin > 0).",
    {
        "type": "object",
        "properties": {
            "temperature_K": {
                "type": "number",
                "description": "Temperature in Kelvin. Must be > 0."
            }
        },
        "required": ["temperature_K"],
    },
    _chem_temperature,
)


# Physics ----------------------------------------------------------------------

def _phys_dim(args: Dict[str, Any]) -> str:
    r = physics.verify_dimensional_consistency(args["equation"], args["symbols"])
    return _format_result(r)


_register(
    "physics_verify_dimensions",
    "Verify both sides of an equation have the same SI dimensions. Substitutes "
    "unit expressions for each named symbol, converts to base SI units (kg, m, s, "
    "A, K, mol, cd), and compares unit signatures. Recognized units include newton, "
    "joule, watt, pascal, kilogram, meter, second, ampere, kelvin, etc.",
    {
        "type": "object",
        "properties": {
            "equation": {
                "type": "string",
                "description": "Equation with '=' between sides, e.g. 'F = m * a' or 'KE = m * v**2 / 2'."
            },
            "symbols": {
                "type": "object",
                "description": "Map of variable name to unit string. E.g. {\"F\": \"newton\", \"m\": \"kilogram\", \"a\": \"meter/second**2\"}.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["equation", "symbols"],
    },
    _phys_dim,
)


def _phys_conservation(args: Dict[str, Any]) -> str:
    r = physics.verify_conservation(
        args["before"], args["after"],
        tolerance_relative=args.get("tolerance_relative", 1e-6),
        tolerance_absolute=args.get("tolerance_absolute", 0.0),
    )
    return _format_result(r)


_register(
    "physics_verify_conservation",
    "Verify named quantities are conserved between before and after states "
    "within tolerance. Returns per-quantity diffs.",
    {
        "type": "object",
        "properties": {
            "before": {"type": "object", "description": "Map of quantity name to numeric value before."},
            "after": {"type": "object", "description": "Map of quantity name to numeric value after."},
            "tolerance_relative": {"type": "number", "default": 1e-6},
            "tolerance_absolute": {"type": "number", "default": 0.0},
        },
        "required": ["before", "after"],
    },
    _phys_conservation,
)


# Mathematics ------------------------------------------------------------------

def _math_equality(args: Dict[str, Any]) -> str:
    r = mathematics.verify_equality(args)
    return _format_result(r)


_register(
    "math_verify_equality",
    "Verify two expressions are symbolically equal via sympy.simplify(a - b) == 0.",
    {
        "type": "object",
        "properties": {
            "expr_a": {"type": "string"},
            "expr_b": {"type": "string"},
            "variables": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["expr_a", "expr_b"],
    },
    _math_equality,
)


def _math_derivative(args: Dict[str, Any]) -> str:
    r = mathematics.verify_derivative(args)
    return _format_result(r)


_register(
    "math_verify_derivative",
    "Verify a claimed derivative. If wrong, returns the actual derivative.",
    {
        "type": "object",
        "properties": {
            "function": {"type": "string", "description": "Function to differentiate, e.g. 'sin(x)'."},
            "variable": {"type": "string", "default": "x"},
            "claimed_derivative": {"type": "string"},
        },
        "required": ["function", "claimed_derivative"],
    },
    _math_derivative,
)


def _math_integral(args: Dict[str, Any]) -> str:
    r = mathematics.verify_integral(args)
    return _format_result(r)


_register(
    "math_verify_integral",
    "Verify a claimed antiderivative by differentiating it and comparing to the integrand.",
    {
        "type": "object",
        "properties": {
            "integrand": {"type": "string"},
            "variable": {"type": "string", "default": "x"},
            "claimed_antiderivative": {"type": "string"},
        },
        "required": ["integrand", "claimed_antiderivative"],
    },
    _math_integral,
)


def _math_limit(args: Dict[str, Any]) -> str:
    r = mathematics.verify_limit(args)
    return _format_result(r)


_register(
    "math_verify_limit",
    "Verify a claimed limit. Use 'oo' or 'inf' for infinity.",
    {
        "type": "object",
        "properties": {
            "function": {"type": "string"},
            "variable": {"type": "string", "default": "x"},
            "point": {"description": "Numeric value, 'oo', or '-oo'."},
            "claimed_limit": {},
        },
        "required": ["function", "point", "claimed_limit"],
    },
    _math_limit,
)


def _math_solve(args: Dict[str, Any]) -> str:
    r = mathematics.verify_solve(args)
    return _format_result(r)


_register(
    "math_verify_solve",
    "Verify claimed solutions to an equation. The equation may use 'lhs = rhs' or "
    "be supplied as 'expr' (taken as expr = 0).",
    {
        "type": "object",
        "properties": {
            "equation": {"type": "string"},
            "variable": {"type": "string", "default": "x"},
            "claimed_solutions": {"type": "array"},
        },
        "required": ["equation", "claimed_solutions"],
    },
    _math_solve,
)


# Statistics -------------------------------------------------------------------

def _stat_pvalue(args: Dict[str, Any]) -> str:
    r = statistics.verify_pvalue_calibration(args)
    return _format_result(r)


_register(
    "statistics_recompute_pvalue",
    "Recompute a p-value from supplied test inputs and verify against a claimed value. "
    "Supported tests: two_sample_t (Welch's), one_sample_t, z, chi2, f.",
    {
        "type": "object",
        "properties": {
            "test": {"type": "string", "enum": ["two_sample_t", "welch_t", "one_sample_t", "z", "chi2", "f"]},
            "claimed_p": {"type": "number"},
            "tolerance": {"type": "number", "default": 1e-3},
            "tail": {"type": "string", "enum": ["two-sided", "greater", "less"], "default": "two-sided"},
            "n1": {"type": "integer"}, "n2": {"type": "integer"},
            "mean1": {"type": "number"}, "mean2": {"type": "number"},
            "sd1": {"type": "number"}, "sd2": {"type": "number"},
            "n": {"type": "integer"}, "mean": {"type": "number"}, "sd": {"type": "number"},
            "mu0": {"type": "number"},
            "z": {"type": "number"},
            "statistic": {"type": "number"},
            "df": {"type": "integer"}, "df1": {"type": "integer"}, "df2": {"type": "integer"},
        },
        "required": ["test"],
    },
    _stat_pvalue,
)


def _stat_multcomp(args: Dict[str, Any]) -> str:
    r = statistics.verify_multiple_comparisons(args)
    return _format_result(r)


_register(
    "statistics_multiple_comparisons",
    "Recompute Bonferroni or BH/FDR-corrected p-values and verify the claimed "
    "rejection set against the computed one.",
    {
        "type": "object",
        "properties": {
            "raw_p_values": {"type": "array", "items": {"type": "number"}},
            "method": {"type": "string", "enum": ["bonferroni", "bonf", "bh", "benjamini-hochberg", "fdr"]},
            "alpha": {"type": "number", "default": 0.05},
            "claimed_rejected_indices": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["raw_p_values", "method"],
    },
    _stat_multcomp,
)


def _stat_ci(args: Dict[str, Any]) -> str:
    r = statistics.verify_confidence_interval(args)
    return _format_result(r)


_register(
    "statistics_check_confidence_interval",
    "Verify a confidence interval is well-formed (low <= high) and contains the estimate.",
    {
        "type": "object",
        "properties": {
            "estimate": {"type": "number"},
            "ci_low": {"type": "number"},
            "ci_high": {"type": "number"},
        },
        "required": ["estimate", "ci_low", "ci_high"],
    },
    _stat_ci,
)


# Computer Science -------------------------------------------------------------

def _cs_termination(args: Dict[str, Any]) -> str:
    r = computer_science.verify_static_termination(args["code"])
    return _format_result(r)


_register(
    "code_verify_termination",
    "AST scan for obvious non-termination patterns (while True without break/return, "
    "unguarded recursion). Static analysis cannot decide the halting problem in "
    "general, but it catches the easy cases.",
    {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    },
    _cs_termination,
)


def _cs_correctness(args: Dict[str, Any]) -> str:
    r = computer_science.verify_functional_correctness(args)
    return _format_result(r)


_register(
    "code_verify_correctness",
    "Execute supplied Python code in a restricted namespace and verify the named "
    "function passes the supplied test cases. Restricted namespace blocks __import__, "
    "open, eval, exec, compile.",
    {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "function_name": {"type": "string"},
            "test_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "args": {"type": "array"},
                        "kwargs": {"type": "object"},
                        "expected": {},
                    },
                },
            },
        },
        "required": ["code", "function_name", "test_cases"],
    },
    _cs_correctness,
)


def _cs_complexity(args: Dict[str, Any]) -> str:
    r = computer_science.verify_runtime_complexity(args)
    return _format_result(r)


_register(
    "code_verify_complexity",
    "Measure runtime at log-spaced input sizes and verify the log-log slope matches "
    "the claimed O() class. Slow tests get more iterations automatically. "
    "Recognized classes: O(1), O(log n), O(n), O(n log n), O(n**2), O(n**3).",
    {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "function_name": {"type": "string"},
            "input_generator": {
                "type": "string",
                "description": "Python code defining `def gen(n): return ...` returning the function's args (list)."
            },
            "claimed_class": {"type": "string"},
            "sizes": {"type": "array", "items": {"type": "integer"}},
            "tolerance": {"type": "number", "default": 0.40},
            "target_seconds": {"type": "number", "default": 0.05},
        },
        "required": ["code", "function_name", "input_generator", "claimed_class"],
    },
    _cs_complexity,
)


# Biology ---------------------------------------------------------------------

def _bio_replicates(args: Dict[str, Any]) -> str:
    r = biology.verify_replicates(args)
    return _format_result(r)


_register(
    "biology_check_replicates",
    "Verify n_replicates is at or above the minimum (default 3).",
    {
        "type": "object",
        "properties": {
            "n_replicates": {"type": "integer"},
            "min_replicates": {"type": "integer", "default": 3},
        },
        "required": ["n_replicates"],
    },
    _bio_replicates,
)


def _bio_assays(args: Dict[str, Any]) -> str:
    r = biology.verify_orthogonal_assays(args)
    return _format_result(r)


_register(
    "biology_check_orthogonal_assays",
    "Verify the number of distinct assay classes is at or above the minimum.",
    {
        "type": "object",
        "properties": {
            "assay_classes": {"type": "array", "items": {"type": "string"}},
            "min_assay_classes": {"type": "integer", "default": 2},
        },
        "required": ["assay_classes"],
    },
    _bio_assays,
)


def _bio_dose_response(args: Dict[str, Any]) -> str:
    spec = {"dose_response": args}
    r = biology.verify_dose_response_monotonicity(spec)
    return _format_result(r)


_register(
    "biology_check_dose_response",
    "Verify a dose-response curve is monotonic in the expected direction "
    "(or flag non-monotonic responses).",
    {
        "type": "object",
        "properties": {
            "doses": {"type": "array", "items": {"type": "number"}},
            "responses": {"type": "array", "items": {"type": "number"}},
            "expected_direction": {"type": "string", "enum": ["increasing", "decreasing"]},
            "tolerance": {"type": "number", "default": 0.0},
        },
        "required": ["doses", "responses"],
    },
    _bio_dose_response,
)


def _bio_power(args: Dict[str, Any]) -> str:
    spec = {"power_analysis": args}
    r = biology.verify_sample_size_powered(spec)
    return _format_result(r)


_register(
    "biology_check_power",
    "Verify sample size is adequate to detect the supplied effect size at the "
    "supplied alpha and target power, using a two-sample t-test approximation.",
    {
        "type": "object",
        "properties": {
            "effect_size": {"type": "number"},
            "alpha": {"type": "number", "default": 0.05},
            "n_per_group": {"type": "integer"},
            "target_power": {"type": "number", "default": 0.80},
        },
        "required": ["effect_size", "n_per_group"],
    },
    _bio_power,
)


# Governance ------------------------------------------------------------------

def _gov_decision(args: Dict[str, Any]) -> str:
    dp = args["decision_packet"]
    r1 = governance.verify_decision_packet_shape(dp)
    out = [_format_result(r1)]
    if "witness_count" in args:
        r2 = governance.verify_witness_count_consistency(dp, {"witness_count": args["witness_count"]})
        out.append(_format_result(r2))
    return "\n\n".join(out)


_register(
    "governance_verify_decision_packet",
    "Verify a governance/business/household/education/church DECISION_PACKET has "
    "the required structural parts: title, scope (adapter/mesh/canon), red_items, "
    "floor_items, way_path, execution_steps, witnesses. Optionally cross-checks "
    "named witnesses against a top-level witness_count.",
    {
        "type": "object",
        "properties": {
            "decision_packet": {
                "type": "object",
                "description": "DECISION_PACKET object with required fields.",
            },
            "witness_count": {
                "type": "integer",
                "description": "Optional top-level witness count to cross-check against named witnesses.",
            },
        },
        "required": ["decision_packet"],
    },
    _gov_decision,
)


# Full engine -----------------------------------------------------------------

def _full_packet(args: Dict[str, Any]) -> str:
    """Run a complete packet through all four gates."""
    packet = args["packet"]
    now_epoch = args.get("now_epoch")
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    res = validate_packet(packet, now_epoch=now_epoch, config=cfg)
    summary = [f"Overall: {res.overall}"]
    for gr in res.gate_results:
        line = f"{gr.gate}: {gr.status}"
        if gr.reasons:
            for reason in gr.reasons[:5]:
                line += f"\n  - {reason}"
        summary.append(line)
    return "\n".join(summary)


_register(
    "validate_full_packet",
    "Run a complete packet through all four gates (RED, FLOOR, BROTHERS, GOD) "
    "including domain validators and computational verifiers. Use this when the "
    "packet supplies multiple verification artifacts at once, or when you want "
    "to check the gate sequence rather than a single verifier.",
    {
        "type": "object",
        "properties": {
            "packet": {
                "type": "object",
                "description": "Full packet JSON. Must include 'domain'. Optional fields: scope, created_epoch, witness_count, required_witnesses, plus any domain-specific RED/FLOOR/VERIFY blocks.",
            },
            "now_epoch": {
                "type": "integer",
                "description": "Override current Unix epoch for testing the GOD gate. Omit to use system time.",
            },
        },
        "required": ["packet"],
    },
    _full_packet,
)


# ── JSON-RPC handlers ────────────────────────────────────────────────────────

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "concordance-engine", "version": "1.0.2"}


def handle_initialize(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    return _result(req_id, {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": SERVER_INFO,
        "capabilities": {
            "tools": {"listChanged": False},
        },
    })


def handle_tools_list(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    listed = []
    for name, t in TOOLS.items():
        listed.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        })
    return _result(req_id, {"tools": listed})


def handle_tools_call(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments", {})
    if name not in TOOLS:
        return _error(req_id, -32601, f"Unknown tool: {name}")
    handler = TOOLS[name]["_handler"]
    try:
        text = handler(args)
        return _result(req_id, {
            "content": _text_content(text),
            "isError": False,
        })
    except Exception as e:
        return _result(req_id, {
            "content": _text_content(f"Error in {name}: {type(e).__name__}: {e}\n{traceback.format_exc()}"),
            "isError": True,
        })


def handle_ping(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    return _result(req_id, {})


HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
    "ping": handle_ping,
}


# ── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    """Read JSON-RPC requests from stdin, dispatch, write responses to stdout."""
    while True:
        msg = _read_message()
        if msg is None:
            break
        # Notifications have no id and expect no response
        if "id" not in msg:
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params", {}) or {}

        # Pre-existing parse error
        if "error" in msg:
            _write_message(msg)
            continue

        handler = HANDLERS.get(method)
        if handler is None:
            _write_message(_error(req_id, -32601, f"Method not found: {method}"))
            continue

        try:
            response = handler(req_id, params)
        except Exception as e:
            response = _error(req_id, -32603, f"Internal error: {e}",
                              data=traceback.format_exc())
        _write_message(response)


if __name__ == "__main__":
    main()
