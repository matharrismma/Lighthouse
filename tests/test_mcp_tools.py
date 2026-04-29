"""Tests for the MCP tool functions (no MCP SDK required).

Run: PYTHONPATH=src python tests/test_mcp_tools.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from concordance_engine.mcp_server.tools import (  # noqa: E402
    validate_packet,
    verify_chemistry,
    verify_physics_dimensional,
    verify_physics_conservation,
    verify_mathematics,
    verify_statistics_pvalue,
    verify_statistics_multiple_comparisons,
    verify_statistics_confidence_interval,
    verify_computer_science,
    verify_biology,
    verify_governance_decision_packet,
    attest_red,
    attest_floor,
    get_example_packet,
    ALL_TOOLS,
    TOOLS,
    TOOL_BY_NAME,
    call_tool,
)


PASS = 0
FAIL = 0


def expect(name, condition, detail=""):
    global PASS, FAIL
    icon = "OK" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{icon}] {name}{(': ' + detail) if detail else ''}")


print("Tool registry:")
for name in [
    "validate_packet", "verify_chemistry",
    "verify_physics_dimensional", "verify_physics_conservation",
    "verify_mathematics",
    "verify_statistics_pvalue", "verify_statistics_multiple_comparisons",
    "verify_statistics_confidence_interval",
    "verify_computer_science", "verify_biology",
    "verify_governance_decision_packet",
    "attest_red", "attest_floor",
    "get_example_packet",
]:
    expect(f"{name} in ALL_TOOLS", name in ALL_TOOLS and callable(ALL_TOOLS[name]))

descriptor_names = {t["name"] for t in TOOLS}
expect("TOOLS descriptor list matches TOOL_BY_NAME",
       descriptor_names == set(TOOL_BY_NAME.keys()))

print("\nChemistry:")
r = verify_chemistry("2 H2 + O2 -> 2 H2O", temperature_K=298.15)
expect("balanced + positive T",
       r["equation"]["status"] == "CONFIRMED" and r["temperature"]["status"] == "CONFIRMED")
r = verify_chemistry("H2 + O2 -> H2O")
expect("unbalanced rejects", r["equation"]["status"] == "MISMATCH")
expect("rebalance suggestion present", "balanced_form" in r)
r = verify_chemistry("2 H2 + O2 -> 2 H2O", temperature_K=-5)
expect("negative T rejects", r["temperature"]["status"] == "MISMATCH")

print("\nPhysics:")
r = verify_physics_dimensional("F = m * a",
    {"F": "newton", "m": "kilogram", "a": "meter/second**2"})
expect("F=ma confirms", r["status"] == "CONFIRMED")
r = verify_physics_dimensional("F = m * v",
    {"F": "newton", "m": "kilogram", "v": "meter/second"})
expect("F=mv mismatches", r["status"] == "MISMATCH")
r = verify_physics_conservation({"p": 12.5}, {"p": 12.5})
expect("identical conservation", r["status"] == "CONFIRMED")
r = verify_physics_conservation({"p": 12.5}, {"p": 11.0})
expect("drift rejects", r["status"] == "MISMATCH")
r = verify_physics_conservation({"KE": 5.0, "PE": 10.0}, {"KE": 8.0, "PE": 7.0}, law="energy")
expect("energy total conservation (law=energy)", r["status"] == "CONFIRMED")
r = verify_physics_conservation({"wrongkey": 1.0}, {"wrongkey": 1.0}, law="energy")
expect("wrong key rejected by named law", r["status"] == "MISMATCH")

print("\nMathematics:")
r = verify_mathematics("equality",
    {"expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1", "variables": ["x"]})
expect("polynomial equality", r["status"] == "CONFIRMED")
r = verify_mathematics("derivative",
    {"function": "sin(x)", "variable": "x", "claimed_derivative": "cos(x)"})
expect("d/dx sin = cos", r["status"] == "CONFIRMED")
r = verify_mathematics("solve",
    {"equation": "x**2 = 4", "variable": "x", "claimed_solutions": [-2, 2]})
expect("x^2=4 solutions", r["status"] == "CONFIRMED")
r = verify_mathematics("matrix",
    {"matrix": [[1, 2], [3, 4]], "claim_type": "determinant", "claimed_value": -2})
expect("matrix determinant", r["status"] == "CONFIRMED")
r = verify_mathematics("inequality", {"lhs": "x**2", "rhs": "0", "op": ">="})
expect("inequality x^2 >= 0", r["status"] == "CONFIRMED")
r = verify_mathematics("series",
    {"term": "1/2**k", "start": 0, "end": "oo", "claimed_sum": 2})
expect("geometric series sum", r["status"] == "CONFIRMED")
r = verify_mathematics("ode",
    {"ode": "Derivative(y(x),x) - y(x)", "claimed_solution": "exp(x)"})
expect("ode dy/dx = y", r["status"] == "CONFIRMED")
r = verify_mathematics("unknown_mode", {})
expect("unknown mode errors", r["status"] == "ERROR")

print("\nStatistics:")
r = verify_statistics_pvalue({
    "test": "two_sample_t", "n1": 30, "n2": 30,
    "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
    "claimed_p": 0.0003,
})
expect("t-test recompute", r["status"] == "CONFIRMED")
r = verify_statistics_pvalue({
    "test": "paired_t", "n": 20, "mean_diff": 0.5, "sd_diff": 1.0,
    "tail": "two", "claimed_p": 0.0375, "tolerance": 1e-2,
})
expect("paired t-test recompute", r["status"] == "CONFIRMED")
r = verify_statistics_pvalue({
    "test": "one_proportion_z", "n": 200, "successes": 110, "p0": 0.5,
    "tail": "two", "claimed_p": 0.158, "tolerance": 1e-2,
})
expect("one-proportion z recompute", r["status"] == "CONFIRMED")
r = verify_statistics_pvalue({
    "test": "fisher_exact", "table": [[8, 2], [1, 5]],
    "tail": "two", "claimed_p": 0.0350, "tolerance": 1e-2,
})
expect("Fisher exact recompute", r["status"] == "CONFIRMED")
r = verify_statistics_multiple_comparisons(
    [0.001, 0.008, 0.04, 0.05, 0.5], "bonferroni", 0.05, [0, 1])
expect("Bonferroni correct claim", r["status"] == "CONFIRMED")
r = verify_statistics_confidence_interval(5.0, 4.5, 5.5)
expect("CI ok", r["status"] == "CONFIRMED")
r = verify_statistics_confidence_interval(
    100, 95.872, 104.128, spec={"mean": 100, "sd": 10, "n": 25, "conf_level": 0.95, "tolerance": 0.01})
expect("CI bound recompute", r["status"] == "CONFIRMED")

print("\nComputer Science:")
r = verify_computer_science(
    code="def lsum(a):\n    s = 0\n    for x in a: s += x\n    return s",
    function_name="lsum",
    test_cases=[{"args": [[1,2,3]], "expected": 6}, {"args": [[]], "expected": 0}])
expect("static + correctness pass",
       r["static_termination"]["status"] in ("CONFIRMED", "NOT_APPLICABLE")
       and r["functional_correctness"]["status"] == "CONFIRMED")
r = verify_computer_science(
    code="def loop():\n    while True:\n        x = 1",
    function_name="loop")
expect("while True flagged", r["static_termination"]["status"] == "MISMATCH")
r = verify_computer_science(
    code="def f(x): return x*2",
    function_name="f",
    test_cases=[{"args":[3],"expected":6}],
    determinism_trials=3)
expect("determinism check confirms",
       r.get("determinism", {}).get("status") == "CONFIRMED")

print("\nBiology:")
r = verify_biology(n_replicates=4)
expect("4 replicates", any(c["status"] == "CONFIRMED" for c in r["checks"]))
r = verify_biology(n_replicates=2)
expect("2 replicates rejects", any(c["status"] == "MISMATCH" for c in r["checks"]))
r = verify_biology(hardy_weinberg={"counts": [490, 420, 90]})
expect("Hardy-Weinberg consistent", r["checks"][0]["status"] == "CONFIRMED")
r = verify_biology(molarity={"mass_g": 4.0, "mw_g_per_mol": 40.0, "volume_L": 0.1, "claimed_molarity": 1.0})
expect("Molarity arithmetic", r["checks"][0]["status"] == "CONFIRMED")
r = verify_biology(mendelian={"observed": [315, 108, 101, 32], "expected_ratio": [9, 3, 3, 1]})
expect("Mendelian 9:3:3:1", r["checks"][0]["status"] == "CONFIRMED")

print("\nGovernance:")
complete_dp = {
    "title": "Approve grant disbursement",
    "scope": "mesh",
    "red_items": ["no exploitation"],
    "floor_items": ["budget within tolerance"],
    "way_path": "Disburse against milestone reports per the agreement.",
    "execution_steps": ["Verify milestones", "Sign disbursement"],
    "witnesses": ["Board Chair", "Treasurer"],
}
r = verify_governance_decision_packet(complete_dp, witness_count=2)
expect("complete packet confirms",
       r["shape"]["status"] == "CONFIRMED"
       and r.get("witness_consistency", {}).get("status") == "CONFIRMED")
r = verify_governance_decision_packet(complete_dp, witness_count=2, domain="business")
expect("business profile flags missing required",
       r.get("domain_profile", {}).get("status") == "MISMATCH")
business_dp = dict(complete_dp)
business_dp["officers"] = ["CEO"]
business_dp["fiduciary_basis"] = "approved budget"
business_dp["dollar_amount"] = 50000
business_dp["risk_assessment"] = "low"
r = verify_governance_decision_packet(business_dp, witness_count=2, domain="business")
expect("business profile passes when fields present",
       r["domain_profile"]["status"] == "CONFIRMED")

print("\nAttestation:")
r = attest_red({"domain": "chemistry"})
expect("attest_red runs on bare chemistry packet",
       isinstance(r, dict) and "results" in r)
r = attest_floor({"domain": "physics", "units": "SI"})
expect("attest_floor on physics with units",
       isinstance(r, dict) and "results" in r)
r = attest_red({"domain": "nope"})
expect("unknown domain returns ERROR", r.get("status") == "ERROR")

print("\nFull engine pipeline:")
ex_path = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "sample_packet_jda_phase1_fund.json")
with open(ex_path) as f:
    packet = json.load(f)
r = validate_packet(packet, now_epoch=9999999999)
expect("JDA Phase 1 packet PASSes", r["overall"] == "PASS")
corrupted = json.loads(json.dumps(packet))
corrupted["DECISION_PACKET"]["red_items"] = []
r = validate_packet(corrupted, now_epoch=9999999999)
expect("corrupted packet REJECTs", r["overall"] == "REJECT")

print("\nExample packets:")
r = get_example_packet("chemistry_verify")
expect("chemistry_verify example loads",
       "packet" in r and r["packet"].get("domain") == "chemistry")
r = get_example_packet("definitely_not_real")
expect("missing example errors with availability list",
       "error" in r and "available" in r)

print("\ncall_tool dispatch:")
r = call_tool("verify_chemistry", {"equation": "2 H2 + O2 -> 2 H2O"})
expect("call_tool verify_chemistry",
       r.get("equation", {}).get("status") == "CONFIRMED")
r = call_tool("does_not_exist", {})
expect("call_tool unknown returns error", "error" in r)

print("\nError safety:")
r = verify_chemistry("not an equation at all")
expect("nonsense input returns ERROR or MISMATCH",
       r["equation"]["status"] in ("ERROR", "MISMATCH"))
r = verify_mathematics("equality", {"expr_a": "@@bad@@", "variables": ["x"]})
expect("missing field handled",
       r["status"] in ("NOT_APPLICABLE", "ERROR", "MISMATCH"))

print("\n" + "=" * 60)
if FAIL:
    print(f"FAIL: {PASS} passed, {FAIL} failed.")
    raise SystemExit(1)
print(f"All {PASS} MCP tool tests passed.")
print("=" * 60)
