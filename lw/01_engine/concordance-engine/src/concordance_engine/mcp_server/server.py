"""MCP server exposing the Concordance Engine verifier layer.

Run as:
    python -m concordance_engine.mcp_server
or after install:
    concordance-mcp

Configure Claude Desktop (~/.config/Claude/claude_desktop_config.json on Linux,
~/Library/Application Support/Claude/claude_desktop_config.json on macOS) with:

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
      "env": {"PYTHONPATH": "/path/to/concordance-engine/src"}
    }
  }
}

Install: pip install -e ".[mcp]"
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

CONCORDANCE_API_URL = os.environ.get(
    "CONCORDANCE_API_URL",
    "https://lighthouse-production-3f9a.up.railway.app",
)
CONCORDANCE_API_KEY = os.environ.get(
    "CONCORDANCE_API_KEY",
    "lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4",
)


# ---------------------------------------------------------------------
# Governance / decision validation
# ---------------------------------------------------------------------

@mcp.tool()
def validate_packet_tool(packet: Dict[str, Any], now_epoch: Optional[int] = None, skip_wait_window: bool = False) -> Dict[str, Any]:
    """Run a decision packet through all four gates and record it permanently in the ledger.

    WHEN TO CALL THIS TOOL
    Call before any action that cannot be undone without significant cost:
    - Committing budget, funds, or physical resources
    - Removing a person's role, access, or standing
    - Publishing a claim as organizational policy or institutional record
    - Terminating a contract, relationship, or ongoing commitment
    - Executing any multi-step plan whose first step is irreversible

    Do NOT call for: conversation, analysis, reversible suggestions, or information retrieval.

    GATES (run in order; first failure stops the chain):
      RED      - Rejects if coercion, unilateral authority, or rights violations are present
      FLOOR    - Rejects if the packet is structurally incomplete or internally inconsistent
      BROTHERS - Quarantines if insufficient witnesses or the review window has not elapsed
      GOD      - Records permanently if all three prior gates pass

    PACKET FORMAT
    {
      "domain": "governance",           // required
      "witness_count": 2,               // required; must match DECISION_PACKET.witness_count
      "created_epoch": 1700000000,      // unix timestamp when decision was first proposed
      "DECISION_PACKET": {
        "title": "Short label",
        "decision": "The exact action being taken",
        "rationale": "Why this decision is being made",
        "scope": "adapter|local|mesh|canon|kernel",
        "red_items": ["No coercion applied", "Acting within authorized role"],
        "floor_items": ["All required parties informed", "Resources confirmed available"],
        "way_path": "standard",
        "execution_steps": ["Step 1", "Step 2"],
        "witnesses": ["Alice Johnson", "Bob Smith"],
        "witness_count": 2,
        "scripture_anchors": ["Prov 22:16"]   // optional
      }
    }

    RETURNS
    {
      "overall": "PASS" | "QUARANTINE" | "REJECT",
      "gate_results": [
        {"gate": "RED"|"FLOOR"|"BROTHERS"|"GOD", "status": "PASS"|"REJECT"|"QUARANTINE",
         "reasons": ["..."], "details": {...}}
      ],
      "ledger_seq": 42,          // present if PASS — the permanent ledger entry number
      "packet_hash": "sha256...",
      "_source": "api" | "local" // api = written to ledger; local = offline fallback
    }

    RECOVERING FROM REJECTION
    Read gate_results. Find the first gate where status != "PASS". The "reasons" list
    describes exactly what failed. Fix those fields and resubmit.
    QUARANTINE means witnesses or time are insufficient — add witnesses or wait.
    REJECT means a structural or ethical rule was violated — read RED/FLOOR reasons.

    Set skip_wait_window=True to bypass the BROTHERS time check during pre-flight testing.
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


# ---------------------------------------------------------------------
# Domain verifiers — call these before stating a claim as fact
# ---------------------------------------------------------------------

@mcp.tool()
def verify_chemistry(equation: str, temperature_K: Optional[float] = None) -> Dict[str, Any]:
    """Verify that a chemical equation is balanced before stating it as fact.

    WHEN TO CALL THIS TOOL
    Call before asserting that a chemical equation is correct. Examples:
    - "2 H2 + O2 -> 2 H2O" — is this balanced?
    - "Fe + HCl -> FeCl2 + H2" — are atoms and charge conserved?
    - Any equation involving ionic species, charged particles, or nested groups.

    Do NOT call for: naming compounds, describing reactions qualitatively, or any
    claim that does not assert a specific stoichiometric relationship.

    INPUTS
    - equation: string in the form "LHS -> RHS", e.g. "2 H2 + O2 -> 2 H2O"
      Supports nested groups (Cu(OH)2), charges (Fe^2+, MnO4^-), and ionic forms.
    - temperature_K: optional float — if provided, also checks that temperature > 0 K.

    RETURNS
    {
      "equation": {
        "status": "CONFIRMED" | "MISMATCH",
        "detail": "...",
        "data": {
          "balanced_lhs": "2 H2 + O2",   // present on MISMATCH
          "balanced_rhs": "2 H2O",
          "balanced_coefficients": {...}
        }
      },
      "temperature": {"status": "CONFIRMED"|"MISMATCH", ...}  // if temperature_K provided
    }

    On MISMATCH, data.balanced_lhs and data.balanced_rhs contain the correct form.
    Use those values to correct your claim before stating it.
    """
    return tools.verify_chemistry(equation, temperature_K)


@mcp.tool()
def verify_physics(equation: str, symbols: Dict[str, str]) -> Dict[str, Any]:
    """Verify dimensional consistency of a physics equation before stating it as fact.

    WHEN TO CALL THIS TOOL
    Call before asserting that a physics equation is dimensionally correct. Examples:
    - "F = m * a" with F in newtons, m in kilograms, a in meters per second squared
    - "E = m * c**2" with E in joules, m in kilograms, c in meters/second
    - Any equation where you are about to claim the units on both sides match.

    INPUTS
    - equation: string, e.g. "F = m * a"
    - symbols: dict mapping each variable to its unit string.
      Valid named units: newton, joule, watt, pascal, volt, ampere, kilogram,
      meter, second, kelvin, and combinations (e.g. "meter/second**2", "kilogram*meter/second**2").

    RETURNS
    {
      "status": "CONFIRMED" | "MISMATCH",
      "detail": "LHS: kg*m/s^2  RHS: kg*m/s^2  — match",
      "data": {"lhs_units": "...", "rhs_units": "..."}
    }

    On MISMATCH, data shows the actual SI dimensions of each side so you can
    identify which symbol has the wrong unit.
    """
    return tools.verify_physics_dimensional(equation, symbols)


@mcp.tool()
def verify_physics_conservation(
    before: Dict[str, float],
    after: Dict[str, float],
    tolerance_relative: float = 1e-6,
    tolerance_absolute: float = 0.0,
    law: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify that a conserved quantity is preserved across a physical process.

    WHEN TO CALL THIS TOOL
    Call before asserting that energy, momentum, charge, or mass is conserved
    in a process. Examples:
    - Before claiming "energy is conserved in this collision"
    - Before asserting that total momentum before and after an interaction matches
    - Any before/after comparison where conservation is the claim.

    INPUTS
    - before: dict of quantity_name -> numeric value before the process
    - after:  dict of quantity_name -> numeric value after the process
    - tolerance_relative: fractional tolerance (default 1e-6)
    - tolerance_absolute: absolute tolerance (default 0.0)
    - law: optional — "energy"|"momentum"|"charge"|"mass" enforces named-law
      key and unit profiles; omit for generic key-by-key comparison.

    RETURNS
    {
      "status": "CONFIRMED" | "MISMATCH",
      "detail": "...",
      "data": {"quantity_name": {"before": ..., "after": ..., "delta": ...}}
    }
    """
    return tools.verify_physics_conservation(
        before, after, tolerance_relative, tolerance_absolute, law=law
    )


@mcp.tool()
def verify_mathematics(check_type: str, **kwargs) -> Dict[str, Any]:
    """Verify a mathematical claim symbolically using SymPy before stating it as fact.

    WHEN TO CALL THIS TOOL
    Call before asserting that:
    - Two expressions are equal: "x^2 - 1 = (x-1)(x+1)"
    - A derivative is correct: "d/dx sin(x) = cos(x)"
    - An integral is correct: "∫ x dx = x^2/2"
    - A limit evaluates to a specific value: "lim x->0 sin(x)/x = 1"
    - An equation has specific solutions: "x^2 - 1 = 0 has solutions x=1, x=-1"

    check_type OPTIONS and required kwargs:

    "equality"   — expr_a (str), expr_b (str), variables (list of str)
    "derivative" — function (str), variable (str), claimed_derivative (str)
    "integral"   — integrand (str), variable (str), claimed_antiderivative (str)
    "limit"      — function (str), variable (str), point (str), claimed_limit (str)
    "solve"      — equation (str), variable (str), claimed_solutions (list of str)

    RETURNS
    {
      "status": "CONFIRMED" | "MISMATCH",
      "detail": "...",
      "data": {"computed": "...", "claimed": "..."}  // on MISMATCH
    }

    All computation is symbolic (exact), not numeric. MISMATCH includes the
    correct computed value so you can correct your claim immediately.
    """
    return tools.verify_mathematics(check_type, kwargs)


@mcp.tool()
def verify_statistics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a statistical claim — p-value, multiple comparisons, or confidence interval.

    WHEN TO CALL THIS TOOL
    Call before asserting any of the following as fact:
    - A specific p-value: "the two-sample t-test yields p = 0.032"
    - A rejection set after correction: "after Bonferroni, tests 2 and 5 are significant"
    - A confidence interval: "the 95% CI is [1.2, 3.4]"

    spec FORMATS (include "check" to select):

    p-value recomputation:
    {
      "check": "pvalue",
      "test": "two_sample_t"|"one_sample_t"|"paired_t"|"z"|"chi2"|"f"|
              "one_proportion_z"|"two_proportion_z"|"fisher_exact"|
              "mannwhitney"|"wilcoxon_signed_rank"|"regression_coefficient_t",
      ... test-specific inputs (n, mean, sd, etc.) ...,
      "claimed_p": 0.032,    // optional — omit to just compute
      "tolerance": 1e-3      // optional
    }

    multiple comparisons:
    {
      "check": "multiple_comparisons",
      "raw_p_values": [0.01, 0.04, 0.2],
      "method": "bonferroni"|"bh",
      "alpha": 0.05,
      "claimed_rejected_indices": [0, 1]  // optional
    }

    confidence interval:
    {
      "check": "confidence_interval",
      "estimate": 2.3,
      "ci_low": 1.2,
      "ci_high": 3.4
    }

    RETURNS
    {"status": "CONFIRMED"|"MISMATCH", "detail": "...", "data": {...}}
    On MISMATCH, data includes the recomputed correct value.
    """
    check = spec.get("check", "pvalue")
    if check == "multiple_comparisons":
        return tools.verify_statistics_multiple_comparisons(
            spec["raw_p_values"], spec["method"],
            spec.get("alpha", 0.05), spec.get("claimed_rejected_indices")
        )
    if check == "confidence_interval":
        return tools.verify_statistics_confidence_interval(
            spec["estimate"], spec["ci_low"], spec["ci_high"], spec=spec
        )
    return tools.verify_statistics_pvalue(spec)


@mcp.tool()
def verify_cs(
    code: str,
    function_name: Optional[str] = None,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    input_generator: Optional[str] = None,
    claimed_class: Optional[str] = None,
    claimed_space_class: Optional[str] = None,
    sizes: Optional[List[int]] = None,
    tolerance: float = 0.40,
    determinism_trials: Optional[int] = None,
) -> Dict[str, Any]:
    """Verify Python code for termination, correctness, and complexity before stating claims.

    WHEN TO CALL THIS TOOL
    Call before asserting any of the following:
    - "This function always terminates" — static termination analysis
    - "This function returns X for input Y" — functional correctness
    - "This algorithm is O(n log n)" — empirical complexity verification
    - "This function is deterministic" — multiple trial comparison

    INPUTS
    - code: Python source string containing the function to verify
    - function_name: name of the specific function to test (required for correctness/complexity)
    - test_cases: list of {"args": [...], "expected": ...} dicts for correctness testing
    - input_generator: Python expression string that produces a list of inputs at size n,
      e.g. "list(range(n))" — required for complexity testing
    - claimed_class: complexity claim string, e.g. "O(n)", "O(n log n)", "O(n**2)"
    - claimed_space_class: space complexity claim, same format
    - determinism_trials: int >= 2 to run determinism check across multiple executions

    RETURNS
    {
      "static_termination": {"status": "CONFIRMED"|"MISMATCH", ...},
      "functional_correctness": {...},   // if function_name + test_cases provided
      "runtime_complexity": {...},       // if function_name + input_generator + claimed_class
      "space_complexity": {...},         // if claimed_space_class provided
      "determinism": {...}               // if determinism_trials >= 2
    }

    Code runs in a restricted namespace. __import__, open, eval, exec, compile are blocked.
    """
    return tools.verify_computer_science(
        code, function_name, test_cases, input_generator,
        claimed_class, sizes, tolerance,
        determinism_trials=determinism_trials,
        claimed_space_class=claimed_space_class,
    )


@mcp.tool()
def verify_biology(
    n_replicates: Optional[int] = None,
    min_replicates: int = 3,
    assay_classes: Optional[List[str]] = None,
    min_assay_classes: int = 2,
    dose_response: Optional[Dict[str, Any]] = None,
    power_analysis: Optional[Dict[str, Any]] = None,
    hardy_weinberg: Optional[Dict[str, Any]] = None,
    primer: Optional[Dict[str, Any]] = None,
    molarity: Optional[Dict[str, Any]] = None,
    mendelian: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Verify biological experimental claims before stating them as fact.

    WHEN TO CALL THIS TOOL
    Call before asserting any of the following:
    - "We ran sufficient replicates" — provide n_replicates
    - "Our assay diversity is adequate" — provide assay_classes
    - "The dose-response relationship is monotonic" — provide dose_response
    - "Our sample size provides adequate statistical power" — provide power_analysis
    - "This allele frequency is in Hardy-Weinberg equilibrium" — provide hardy_weinberg
    - "This primer has adequate Tm and GC content" — provide primer
    - "This molar concentration is correct" — provide molarity
    - "This inheritance pattern is Mendelian" — provide mendelian

    All parameters are optional. Only the checks for which you supply inputs will run.

    DOSE RESPONSE format:
    {"doses": [0.1, 1, 10], "responses": [2.1, 4.3, 8.9], "expected_direction": "increasing"}

    POWER ANALYSIS format:
    {"effect_size": 0.5, "alpha": 0.05, "n_per_group": 30, "target_power": 0.80}

    HARDY-WEINBERG format:
    {"allele_freq_p": 0.6, "observed_AA": 36, "observed_Aa": 48, "observed_aa": 16, "n": 100}

    PRIMER format:
    {"sequence": "ATCGATCGATCG", "min_tm": 55, "max_tm": 65, "min_gc": 40, "max_gc": 60}

    RETURNS
    {"checks": [{"status": "CONFIRMED"|"MISMATCH", "detail": "...", "data": {...}}, ...]}
    """
    return tools.verify_biology(
        n_replicates, min_replicates, assay_classes, min_assay_classes,
        dose_response, power_analysis,
        hardy_weinberg=hardy_weinberg, primer=primer,
        molarity=molarity, mendelian=mendelian,
    )


@mcp.tool()
def verify_governance(
    decision_packet: Dict[str, Any],
    witness_count: Optional[int] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify the structural completeness of a decision packet before submitting it.

    WHEN TO CALL THIS TOOL
    Call this as a pre-flight check before calling validate_packet_tool.
    Use it to confirm the packet structure is valid before incurring a ledger write.
    Particularly useful when building packets programmatically.

    INPUTS
    - decision_packet: the DECISION_PACKET sub-object (not the full outer packet)
    - witness_count: if provided, checks that decision_packet.witnesses length matches
    - domain: optional — "governance"|"business"|"household"|"education"|"church"
      activates per-domain required-field profile

    Required fields in decision_packet:
      title, decision, rationale, scope, red_items (list), floor_items (list),
      way_path, execution_steps (list), witnesses (list), witness_count (int)

    Optional: scripture_anchors (list of scripture references)

    RETURNS
    {
      "shape": {"status": "CONFIRMED"|"MISMATCH", "detail": "...", "data": {...}},
      "witness_consistency": {...},   // if witness_count provided
      "domain_profile": {...}         // if domain provided
    }

    Fix any MISMATCH fields, then call validate_packet_tool with the full outer packet.
    """
    return tools.verify_governance_decision_packet(decision_packet, witness_count, domain=domain)


@mcp.tool()
def suggest_fix(packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """Run the engine and return concrete corrective actions for any failures.

    WHEN TO CALL THIS TOOL
    Call after validate_packet_tool returns REJECT or QUARANTINE.
    Returns a specific, actionable list of changes to make to the packet
    so that it will pass on resubmission. Act on the list directly.

    RETURNS
    {
      "overall": "PASS"|"QUARANTINE"|"REJECT",
      "gate_results": [...],
      "fixes": [
        {"field": "DECISION_PACKET.witnesses", "issue": "...", "action": "Add at least 2 named witnesses"},
        ...
      ]
    }
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
                result = json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            result = tools.validate_packet(packet, now_epoch)
    else:
        result = tools.validate_packet(packet, now_epoch)

    fixes = []
    for gr in result.get("gate_results", []):
        if gr.get("status") not in ("PASS",):
            for reason in gr.get("reasons", []):
                fixes.append({
                    "gate": gr["gate"],
                    "issue": reason,
                    "action": _reason_to_action(gr["gate"], reason),
                })

    result["fixes"] = fixes
    return result


def _reason_to_action(gate: str, reason: str) -> str:
    reason_lower = reason.lower()
    if gate == "RED":
        if "coer" in reason_lower:
            return "Remove coercive language from 'decision' and 'rationale' fields"
        if "unilateral" in reason_lower or "authority" in reason_lower:
            return "Ensure 'scope' matches your actual authorized role; remove unilateral authority claims"
        return "Review RED gate criteria and remove the flagged language from red_items or rationale"
    if gate == "FLOOR":
        if "witness" in reason_lower:
            return "Add at least 2 named witnesses to DECISION_PACKET.witnesses and update witness_count"
        if "rationale" in reason_lower or "missing" in reason_lower:
            return "Add a non-empty 'rationale' string to DECISION_PACKET"
        if "floor_items" in reason_lower:
            return "Add at least one item to DECISION_PACKET.floor_items"
        if "red_items" in reason_lower:
            return "Add at least one item to DECISION_PACKET.red_items"
        if "scope" in reason_lower:
            return "Set DECISION_PACKET.scope to one of: adapter, local, mesh, canon, kernel"
        return "Check all required DECISION_PACKET fields are present and non-empty"
    if gate == "BROTHERS":
        if "witness" in reason_lower or "count" in reason_lower:
            return "Increase witness_count and add more names to DECISION_PACKET.witnesses"
        if "time" in reason_lower or "window" in reason_lower or "elapsed" in reason_lower:
            return "The review window has not elapsed. Wait the required time or set skip_wait_window=True for testing"
        return "Add more witnesses or allow more time before resubmitting"
    return f"Address the {gate} gate failure: {reason}"


def main() -> None:
    """Entry point for the MCP server. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
