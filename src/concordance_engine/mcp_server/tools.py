"""MCP tool implementations.

FastMCP server (server.py) imports the function-style API directly. List-style
API (TOOLS, list_tools, call_tool) used as fallback. ALL_TOOLS exposes a flat
{name: callable} map for tests and embedders.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..engine import (
    EngineConfig, validate_packet as _engine_validate,
    validate_and_seal as _engine_seal,
)
from ..verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance, scripture,
)
from ..verifiers import energy as _energy
from ..verifiers.base import VerifierResult
from ..walkthrough import (
    render_walkthrough, render_walkthrough_compact, render_walkthrough_html,
)
from ..ledger import find_closest as _find_closest


def _r(r: VerifierResult) -> Dict[str, Any]:
    return {"status": r.status, "detail": r.detail, "data": r.data}


# ---------------------------------------------------------------------
# Function-style API
# ---------------------------------------------------------------------

def validate_packet(packet, now_epoch=None):
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


def seal_packet(packet, now_epoch=None, auto_precedent=False):
    """Run a packet through the four gates and return the sealed
    WitnessRecord as JSON. The agent surface for the canonical sealed
    record — same object the human walkthrough renderer consumes.

    When `auto_precedent=True`, the Audit Chain is queried for the
    closest comparable precedent and (if found) sealed into the record.
    """
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet.get("id"),
    )
    return rec.to_dict()


def walkthrough_packet(
    packet,
    now_epoch=None,
    fmt="markdown",
    expand_traces=False,
    auto_precedent=False,
):
    """Run a packet and return a human-readable walkthrough.

    `fmt` selects the renderer: "markdown" (Socratic walk, default),
    "compact" (one-screen status), or "html" (self-contained HTML page).
    `expand_traces=True` adds the verifier trace section to markdown
    and HTML outputs (compact ignores it). `auto_precedent=True` pulls
    in the closest comparable precedent before sealing.
    """
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet.get("id"),
    )
    fmt = (fmt or "markdown").lower()
    if fmt == "compact":
        return render_walkthrough_compact(rec)
    if fmt == "html":
        return render_walkthrough_html(rec, expand_traces=expand_traces)
    return render_walkthrough(rec, expand_traces=expand_traces)


def verify_chemistry(equation, temperature_K=None):
    out = {}
    eq_r = chemistry.verify_equation(equation, balance_if_unbalanced=True)
    out["equation"] = _r(eq_r)
    if eq_r.status == "MISMATCH" and eq_r.data and "balanced_lhs" in eq_r.data:
        out["balanced_form"] = f"{eq_r.data['balanced_lhs']} -> {eq_r.data['balanced_rhs']}"
        out["balanced_coefficients"] = eq_r.data.get("balanced_coefficients")
    if temperature_K is not None:
        out["temperature"] = _r(chemistry.verify_temperature(temperature_K))
    return out


def verify_physics_dimensional(equation, symbols):
    return _r(physics.verify_dimensional_consistency(equation, symbols))


def verify_physics_conservation(before, after, tolerance_relative=1e-6,
                                 tolerance_absolute=0.0, law=None):
    if law:
        return _r(physics.verify_named_conservation(
            law, before, after,
            tolerance_relative=tolerance_relative,
            tolerance_absolute=tolerance_absolute,
        ))
    return _r(physics.verify_conservation(
        before, after,
        tolerance_relative=tolerance_relative,
        tolerance_absolute=tolerance_absolute,
    ))


def verify_mathematics(mode, params):
    """Mode dispatcher: equality|derivative|integral|limit|solve|matrix|inequality|series|ode."""
    mode = (mode or "").lower()
    out = {}
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
    if mode == "matrix":
        return _r(mathematics.verify_matrix(params))
    if mode == "inequality":
        return _r(mathematics.verify_inequality(params))
    if mode == "series":
        return _r(mathematics.verify_series(params))
    if mode == "ode":
        return _r(mathematics.verify_ode(params))
    return {"status": "ERROR", "detail": f"unknown mode {mode!r}",
            "data": {"valid_modes": ["equality", "derivative", "integral", "limit",
                                     "solve", "matrix", "inequality", "series", "ode"]}}


def verify_statistics_pvalue(spec):
    return _r(statistics.verify_pvalue_calibration(spec))


def verify_statistics_multiple_comparisons(raw_p_values, method, alpha=0.05,
                                            claimed_rejected_indices=None):
    spec = {"raw_p_values": raw_p_values, "method": method, "alpha": alpha}
    if claimed_rejected_indices is not None:
        spec["claimed_rejected_indices"] = claimed_rejected_indices
    return _r(statistics.verify_multiple_comparisons(spec))


def verify_statistics_confidence_interval(estimate, ci_low, ci_high, *, spec=None):
    if spec:
        full = dict(spec)
        full.setdefault("estimate", estimate)
        full.setdefault("ci_low", ci_low)
        full.setdefault("ci_high", ci_high)
        return _r(statistics.verify_confidence_interval(full))
    return _r(statistics.verify_confidence_interval({
        "estimate": estimate, "ci_low": ci_low, "ci_high": ci_high,
    }))


def verify_computer_science(code, function_name=None, test_cases=None,
                             input_generator=None, claimed_class=None,
                             sizes=None, tolerance=0.40, *,
                             determinism_trials=None, claimed_space_class=None):
    out = {"static_termination": _r(computer_science.verify_static_termination(code))}
    if function_name and test_cases:
        out["functional_correctness"] = _r(computer_science.verify_functional_correctness({
            "code": code, "function_name": function_name, "test_cases": test_cases,
        }))
    if function_name and input_generator and claimed_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator, "claimed_class": claimed_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["runtime_complexity"] = _r(computer_science.verify_runtime_complexity(spec))
    if function_name and input_generator and claimed_space_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator,
                "claimed_space_class": claimed_space_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["space_complexity"] = _r(computer_science.verify_space_complexity(spec))
    if function_name and test_cases and determinism_trials and determinism_trials >= 2:
        out["determinism"] = _r(computer_science.verify_determinism({
            "code": code, "function_name": function_name,
            "test_cases": test_cases, "trials": determinism_trials,
        }))
    return out


def verify_biology(n_replicates=None, min_replicates=3, assay_classes=None,
                    min_assay_classes=2, dose_response=None, power_analysis=None,
                    *, bio_control=None, hardy_weinberg=None, primer=None,
                    molarity=None, mendelian=None):
    spec = {}
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
    if hardy_weinberg is not None:
        spec["hardy_weinberg"] = hardy_weinberg
    if primer is not None:
        spec["primer"] = primer
    if molarity is not None:
        spec["molarity"] = molarity
    if mendelian is not None:
        spec["mendelian"] = mendelian
    packet = {"BIO_VERIFY": spec}
    if bio_control is not None:
        packet["BIO_CONTROL"] = bio_control
    results = biology.run(packet)
    return {"checks": [_r(r) for r in results]}


def verify_governance_decision_packet(decision_packet, witness_count=None, *, domain=None):
    out = {"shape": _r(governance.verify_decision_packet_shape(decision_packet))}
    if witness_count is not None:
        out["witness_consistency"] = _r(
            governance.verify_witness_count_consistency(
                decision_packet, {"witness_count": witness_count}))
    if domain:
        out["domain_profile"] = _r(governance.verify_domain_profile(domain, decision_packet))
    return out


def verify_energy(spec):
    """Run all applicable energy-system checks against the supplied spec.

    Spec is the contents of the ENERGY_VERIFY field — see
    `concordance_engine.verifiers.energy` docstring for the full
    field reference. Each check fires when its inputs are present;
    unsupplied checks return NOT_APPLICABLE.

    Off-grid system sizing, wire voltage drop, battery sizing,
    solar daily yield, peak-load-vs-inverter, runtime, kWh↔Wh,
    efficiency (with heat-pump COP carve-out), power balance.
    """
    packet = {"ENERGY_VERIFY": spec or {}}
    results = _energy.run(packet)
    return {"checks": [_r(r) for r in results]}


# ---------------------------------------------------------------------
# Domain-attestation tools
# ---------------------------------------------------------------------

def _gate_results_to_payload(grs):
    items = [
        {"gate": gr.gate, "status": gr.status,
         "reasons": list(gr.reasons or []),
         "details": dict(gr.details or {})}
        for gr in (grs or [])
    ]
    overall = "PASS"
    for it in items:
        if it["status"] == "REJECT":
            overall = "REJECT"
            break
        if it["status"] == "QUARANTINE" and overall == "PASS":
            overall = "QUARANTINE"
    return {"overall": overall, "results": items}


def attest_red(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_red(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


def attest_floor(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_floor(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


# ---------------------------------------------------------------------
# Layer 0 / Scripture tools
# ---------------------------------------------------------------------

def resolve_scripture_ref(ref):
    """Look up a scripture reference in the WEB and return its text.
    Accepts forms like "Jn3:16", "John 3:16", "1Co13:4". Returns
    `{ref, web_text, status, detail}`. Status `source_missing` means
    the Layer 0 data has not been provisioned yet — see the detail."""
    return scripture.resolve_ref(ref)


def word_study(strongs_num):
    """Strong's-keyed word study: definition, derivation, every verse
    where the word appears. Accepts "G26", "H2617", etc. Returns
    `{strongs, word, transliteration, definition, derivation, verses,
    occurrence_count}` or a `source_missing` status if Layer 0 has not
    been provisioned."""
    return scripture.word_study(strongs_num)


def verify_scripture_anchors(anchors):
    """Confirm each ref in `anchors` resolves to a real WEB verse.
    Used to catch fabricated scripture citations — the most common
    LLM-failure mode in this domain. Returns the standard verifier
    result shape (CONFIRMED / MISMATCH / SKIPPED)."""
    return _r(scripture.verify_scripture_anchors(list(anchors or [])))


def triangulate_claim(ref, claim, strongs_keys=None):
    """Triangulation: check whether an interpretation `claim` about a
    scripture verse `ref` is consistent with the original-language
    Strong's definitions.

    Without `strongs_keys`, returns NEEDS_MANUAL_VERIFICATION with the
    WEB text and instructions for completing the check. With Strong's
    numbers supplied (e.g. ['G142'] for airo), returns the per-word
    semantic range so a reviewer (or later automated tagging) can
    compare the claim to attested meaning."""
    return scripture.triangulate_claim(ref, claim, strongs_keys=strongs_keys)


def get_example_packet(name):
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "examples")
    candidates = [f"sample_packet_{name}.json", f"sample_packet_{name}_verify.json",
                  f"sample_packet_jda_{name}.json", f"{name}.json"]
    for c in candidates:
        path = os.path.join(examples_dir, c)
        if os.path.exists(path):
            with open(path) as f:
                return {"name": c, "packet": json.load(f)}
    available = sorted([f for f in os.listdir(examples_dir) if f.endswith(".json")])
    return {"error": f"no example named {name!r}", "available": available}


# ---------------------------------------------------------------------
# List-style API
# ---------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {"name": "validate_packet",
     "description": "Run a packet through the full Four-Gates engine.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"},
                                    "now_epoch": {"type": "integer"}},
                     "required": ["packet"]},
     "fn": lambda a: validate_packet(a["packet"], a.get("now_epoch"))},
    {"name": "verify_chemistry",
     "description": "Verify equation balance / suggest balancing coefficients. Optional temperature_K positivity.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "temperature_K": {"type": "number"}},
                     "required": ["equation"]},
     "fn": lambda a: verify_chemistry(a["equation"], a.get("temperature_K"))},
    {"name": "verify_physics_dimensional",
     "description": "Verify both sides of an equation reduce to identical SI units.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "symbols": {"type": "object"}},
                     "required": ["equation", "symbols"]},
     "fn": lambda a: verify_physics_dimensional(a["equation"], a["symbols"])},
    {"name": "verify_physics_conservation",
     "description": "Verify before/after match within tolerance. Optional 'law' (energy|momentum|charge|mass) enforces named-law key/unit profile.",
     "inputSchema": {"type": "object",
                     "properties": {"before": {"type": "object"},
                                    "after": {"type": "object"},
                                    "tolerance_relative": {"type": "number"},
                                    "tolerance_absolute": {"type": "number"},
                                    "law": {"type": "string"}},
                     "required": ["before", "after"]},
     "fn": lambda a: verify_physics_conservation(
        a["before"], a["after"],
        a.get("tolerance_relative", 1e-6), a.get("tolerance_absolute", 0.0),
        law=a.get("law"))},
    {"name": "verify_mathematics",
     "description": "Sympy verification. mode=equality|derivative|integral|limit|solve|matrix|inequality|series|ode.",
     "inputSchema": {"type": "object",
                     "properties": {"mode": {"type": "string"}, "params": {"type": "object"}},
                     "required": ["mode", "params"]},
     "fn": lambda a: verify_mathematics(a["mode"], a["params"])},
    {"name": "verify_statistics_pvalue",
     "description": "Recompute p from inputs and compare to claimed_p. Tests: two_sample_t, one_sample_t, paired_t, z, chi2, f, one_proportion_z, two_proportion_z, fisher_exact, mannwhitney, wilcoxon_signed_rank, regression_coefficient_t.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_statistics_pvalue(a["spec"])},
    {"name": "verify_statistics_multiple_comparisons",
     "description": "Bonferroni or BH/FDR adjustment with rejection-set verification.",
     "inputSchema": {"type": "object",
                     "properties": {"raw_p_values": {"type": "array"},
                                    "method": {"type": "string"},
                                    "alpha": {"type": "number"},
                                    "claimed_rejected_indices": {"type": "array"}},
                     "required": ["raw_p_values", "method"]},
     "fn": lambda a: verify_statistics_multiple_comparisons(
        a["raw_p_values"], a["method"], a.get("alpha", 0.05),
        a.get("claimed_rejected_indices"))},
    {"name": "verify_statistics_confidence_interval",
     "description": "Verify CI well-formed and contains estimate. With 'spec' raw inputs, recompute bounds.",
     "inputSchema": {"type": "object",
                     "properties": {"estimate": {"type": "number"},
                                    "ci_low": {"type": "number"},
                                    "ci_high": {"type": "number"},
                                    "spec": {"type": "object"}},
                     "required": ["estimate", "ci_low", "ci_high"]},
     "fn": lambda a: verify_statistics_confidence_interval(
        a["estimate"], a["ci_low"], a["ci_high"], spec=a.get("spec"))},
    {"name": "verify_computer_science",
     "description": "Verify Python: termination, correctness, runtime O(.), space O(.), determinism.",
     "inputSchema": {"type": "object",
                     "properties": {"code": {"type": "string"},
                                    "function_name": {"type": "string"},
                                    "test_cases": {"type": "array"},
                                    "input_generator": {"type": "string"},
                                    "claimed_class": {"type": "string"},
                                    "claimed_space_class": {"type": "string"},
                                    "sizes": {"type": "array"},
                                    "tolerance": {"type": "number"},
                                    "determinism_trials": {"type": "integer"}},
                     "required": ["code"]},
     "fn": lambda a: verify_computer_science(
        a["code"], a.get("function_name"), a.get("test_cases"),
        a.get("input_generator"), a.get("claimed_class"),
        a.get("sizes"), a.get("tolerance", 0.40),
        determinism_trials=a.get("determinism_trials"),
        claimed_space_class=a.get("claimed_space_class"))},
    {"name": "verify_biology",
     "description": (
         "Biology checks: replicates, assays, dose-response, power, Hardy-Weinberg, "
         "primer Tm/GC, molarity, Mendelian. "
         "Pass bio_control dict to verify nested health control system claims: "
         "failure_mode (setpoint_drift|loop_saturation|compensation_collapse|"
         "cross_layer_override|sensor_failure), failure_layer (L1-L6), "
         "intervention_layers, and required safety fields."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"n_replicates": {"type": "integer"},
                                    "min_replicates": {"type": "integer"},
                                    "assay_classes": {"type": "array"},
                                    "min_assay_classes": {"type": "integer"},
                                    "dose_response": {"type": "object"},
                                    "power_analysis": {"type": "object"},
                                    "bio_control": {"type": "object"},
                                    "hardy_weinberg": {"type": "object"},
                                    "primer": {"type": "object"},
                                    "molarity": {"type": "object"},
                                    "mendelian": {"type": "object"}}},
     "fn": lambda a: verify_biology(
        a.get("n_replicates"), a.get("min_replicates", 3),
        a.get("assay_classes"), a.get("min_assay_classes", 2),
        a.get("dose_response"), a.get("power_analysis"),
        bio_control=a.get("bio_control"),
        hardy_weinberg=a.get("hardy_weinberg"), primer=a.get("primer"),
        molarity=a.get("molarity"), mendelian=a.get("mendelian"))},
    {"name": "verify_governance_decision_packet",
     "description": "Decision packet structural check. Optional 'domain' (governance|business|household|education|church) activates per-domain profile.",
     "inputSchema": {"type": "object",
                     "properties": {"decision_packet": {"type": "object"},
                                    "witness_count": {"type": "integer"},
                                    "domain": {"type": "string"}},
                     "required": ["decision_packet"]},
     "fn": lambda a: verify_governance_decision_packet(
        a["decision_packet"], a.get("witness_count"), domain=a.get("domain"))},
    {"name": "attest_red",
     "description": "Run only the RED-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_red(a["packet"])},
    {"name": "attest_floor",
     "description": "Run only the FLOOR-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_floor(a["packet"])},
    {"name": "resolve_scripture_ref",
     "description": (
         "Look up a scripture reference in the World English Bible and return "
         "its text. Accepts forms like 'Jn3:16', 'John 3:16', '1Co13:4'. "
         "Returns {ref, web_text, status, detail}. Status 'source_missing' "
         "means Layer 0 data has not been provisioned — run "
         "lw/00_source/fetch_sources.py once."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"}},
                     "required": ["ref"]},
     "fn": lambda a: resolve_scripture_ref(a["ref"])},
    {"name": "word_study",
     "description": (
         "Strong's-keyed word study. Pass a Strong's number like 'G26' "
         "(agape) or 'H2617' (chesed). Returns word, transliteration, "
         "definition, derivation, every verse where the word appears, "
         "and occurrence count."),
     "inputSchema": {"type": "object",
                     "properties": {"strongs_num": {"type": "string"}},
                     "required": ["strongs_num"]},
     "fn": lambda a: word_study(a["strongs_num"])},
    {"name": "verify_scripture_anchors",
     "description": (
         "Confirm each ref in 'anchors' resolves to a real WEB verse. Use "
         "this before citing scripture in a load-bearing claim — fabricated "
         "references are the most common LLM failure mode in this domain. "
         "Returns CONFIRMED / MISMATCH / SKIPPED."),
     "inputSchema": {"type": "object",
                     "properties": {"anchors": {"type": "array",
                                                "items": {"type": "string"}}},
                     "required": ["anchors"]},
     "fn": lambda a: verify_scripture_anchors(a["anchors"])},
    {"name": "triangulate_claim",
     "description": (
         "Triangulation: check whether an interpretation 'claim' about a "
         "verse 'ref' survives at all three layers (WEB text, Strong's "
         "original-language meaning, the claim itself). Without "
         "strongs_keys returns NEEDS_MANUAL_VERIFICATION + the WEB text "
         "and instructions. With Strong's numbers supplied, returns the "
         "per-word semantic range so the claim can be checked against "
         "attested meaning."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"},
                                    "claim": {"type": "string"},
                                    "strongs_keys": {"type": "array",
                                                     "items": {"type": "string"}}},
                     "required": ["ref", "claim"]},
     "fn": lambda a: triangulate_claim(a["ref"], a["claim"], a.get("strongs_keys"))},
    {"name": "get_example_packet",
     "description": "Return a canonical example packet by name.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"}},
                     "required": ["name"]},
     "fn": lambda a: get_example_packet(a["name"])},
]


TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools():
    return [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]


def call_tool(name, arguments):
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}", "available": list(TOOL_BY_NAME.keys())}
    try:
        return tool["fn"](arguments or {})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


ALL_TOOLS: Dict[str, Any] = {
    "validate_packet": validate_packet,
    "verify_chemistry": verify_chemistry,
    "verify_physics_dimensional": verify_physics_dimensional,
    "verify_physics_conservation": verify_physics_conservation,
    "verify_mathematics": verify_mathematics,
    "verify_statistics_pvalue": verify_statistics_pvalue,
    "verify_statistics_multiple_comparisons": verify_statistics_multiple_comparisons,
    "verify_statistics_confidence_interval": verify_statistics_confidence_interval,
    "verify_computer_science": verify_computer_science,
    "verify_biology": verify_biology,
    "verify_governance_decision_packet": verify_governance_decision_packet,
    "attest_red": attest_red,
    "attest_floor": attest_floor,
    "resolve_scripture_ref": resolve_scripture_ref,
    "word_study": word_study,
    "verify_scripture_anchors": verify_scripture_anchors,
    "triangulate_claim": triangulate_claim,
    "get_example_packet": get_example_packet,
}
