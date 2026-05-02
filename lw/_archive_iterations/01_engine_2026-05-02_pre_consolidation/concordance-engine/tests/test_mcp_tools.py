"""Tests for the MCP tool functions (no MCP SDK required).

Run: PYTHONPATH=src python tests/test_mcp_tools.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from concordance_engine.mcp_server.tools import (
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
    ALL_TOOLS,
)


PASS = 0
FAIL = 0


def expect(name, condition, detail=""):
    global PASS, FAIL
    icon = "✓" if condition else "✗"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {icon} {name}{(': ' + detail) if detail else ''}")


# Each tool must exist and be callable
print("Tool registry:")
for name in [
    "validate_packet", "verify_chemistry",
    "verify_physics_dimensional", "verify_physics_conservation",
    "verify_mathematics",
    "verify_statistics_pvalue", "verify_statistics_multiple_comparisons",
    "verify_statistics_confidence_interval",
    "verify_computer_science", "verify_biology",
    "verify_governance_decision_packet",
]:
    expect(f"{name} registered", name in ALL_TOOLS and callable(ALL_TOOLS[name]))

# ─── Chemistry ───
print("\nChemistry:")
r = verify_chemistry("2 H2 + O2 -> 2 H2O", temperature_K=298.15)
expect("balanced + positive T", r["results"][0]["status"] == "CONFIRMED"
       and r["results"][1]["status"] == "CONFIRMED")
r = verify_chemistry("H2 + O2 -> H2O")
expect("unbalanced rejects", r["results"][0]["status"] == "MISMATCH")
expect("rebalance suggestion present",
       "balances as" in r["results"][0]["detail"])
r = verify_chemistry("2 H2 + O2 -> 2 H2O", temperature_K=-5)
expect("negative T rejects", r["results"][1]["status"] == "MISMATCH")

# ─── Physics ───
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

# ─── Mathematics ───
print("\nMathematics:")
r = verify_mathematics("equality",
    {"expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1", "variables": ["x"]})
expect("polynomial equality", r["status"] == "CONFIRMED")
r = verify_mathematics("derivative",
    {"function": "sin(x)", "variable": "x", "claimed_derivative": "cos(x)"})
expect("d/dx sin = cos", r["status"] == "CONFIRMED")
r = verify_mathematics("derivative",
    {"function": "sin(x)", "variable": "x", "claimed_derivative": "-cos(x)"})
expect("d/dx sin != -cos", r["status"] == "MISMATCH")
r = verify_mathematics("integral",
    {"integrand": "1/(1+x**2)", "variable": "x", "claimed_antiderivative": "atan(x)"})
expect("integral atan", r["status"] == "CONFIRMED")
r = verify_mathematics("solve",
    {"equation": "x**2 = 4", "variable": "x", "claimed_solutions": [-2, 2]})
expect("x^2=4 solutions", r["status"] == "CONFIRMED")
r = verify_mathematics("unknown_mode", {})
expect("unknown mode errors", r["status"] == "ERROR")

# ─── Statistics ───
print("\nStatistics:")
r = verify_statistics_pvalue({
    "test": "two_sample_t", "n1": 30, "n2": 30,
    "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
    "claimed_p": 0.0003,
})
expect("t-test recompute", r["status"] == "CONFIRMED")
r = verify_statistics_multiple_comparisons(
    [0.001, 0.008, 0.04, 0.05, 0.5], "bonferroni", 0.05, [0, 1])
expect("Bonferroni correct claim", r["status"] == "CONFIRMED")
r = verify_statistics_multiple_comparisons(
    [0.001, 0.008, 0.04, 0.05, 0.5], "bonferroni", 0.05, [0])
expect("Bonferroni wrong claim", r["status"] == "MISMATCH")
r = verify_statistics_confidence_interval(5.0, 4.5, 5.5)
expect("CI ok", r["status"] == "CONFIRMED")
r = verify_statistics_confidence_interval(5.0, 5.5, 6.0)
expect("CI excludes estimate", r["status"] == "MISMATCH")

# ─── Computer Science ───
print("\nComputer Science:")
r = verify_computer_science(
    code="def lsum(a):\n    s = 0\n    for x in a: s += x\n    return s",
    function_name="lsum",
    test_cases=[{"args": [[1,2,3]], "expected": 6},
                {"args": [[]], "expected": 0}])
results = {x["status"] for x in r["results"]}
expect("static + correctness pass", "MISMATCH" not in results
       and "ERROR" not in results)

r = verify_computer_science(
    code="def loop():\n    while True:\n        x = 1",
    function_name="loop")
expect("while True flagged",
       any(x["status"] == "MISMATCH" for x in r["results"]))

r = verify_computer_science(
    code="def add(a,b):\n    return a - b",
    function_name="add",
    test_cases=[{"args": [2,3], "expected": 5}])
expect("wrong impl flagged",
       any(x["status"] == "MISMATCH" for x in r["results"]))

# ─── Biology ───
print("\nBiology:")
r = verify_biology(n_replicates=4)
expect("4 replicates", r["results"][0]["status"] == "CONFIRMED")
r = verify_biology(n_replicates=2)
expect("2 replicates rejects", r["results"][0]["status"] == "MISMATCH")
r = verify_biology(
    n_replicates=3,
    assay_classes=["qPCR", "western"],
    dose_response={"doses": [0,1,5,25],
                   "responses": [0.1,0.3,0.2,0.8],
                   "expected_direction": "increasing"})
expect("non-monotonic rejects",
       any(x["status"] == "MISMATCH" for x in r["results"]))

r = verify_biology()  # nothing supplied
expect("empty inputs NOT_APPLICABLE",
       r["results"][0]["status"] == "NOT_APPLICABLE")

# ─── Governance ───
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
       all(x["status"] == "CONFIRMED" for x in r["results"]))

r = verify_governance_decision_packet(
    {"title": "x", "scope": "weird", "red_items": [],
     "floor_items": [], "way_path": "go", "execution_steps": [],
     "witnesses": []})
expect("empty packet rejects",
       r["results"][0]["status"] == "MISMATCH")

r = verify_governance_decision_packet(complete_dp, witness_count=5)
expect("witness count mismatch detected",
       any(x["status"] == "MISMATCH" for x in r["results"]))

# ─── Top-level engine ───
print("\nFull engine pipeline:")
ex_path = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "sample_packet_jda_phase1_fund.json")
with open(ex_path) as f:
    packet = json.load(f)
r = validate_packet(packet, now_epoch=9999999999)
expect("JDA Phase 1 packet PASSes", r["overall"] == "PASS")

corrupted = dict(packet)
corrupted["DECISION_PACKET"] = dict(packet["DECISION_PACKET"])
corrupted["DECISION_PACKET"]["red_items"] = []  # empty red items
r = validate_packet(corrupted, now_epoch=9999999999)
expect("corrupted packet REJECTs", r["overall"] == "REJECT")

# ─── Error handling ───
print("\nError safety:")
r = verify_chemistry("not an equation at all")
expect("nonsense input returns ERROR not exception",
       r["results"][0]["status"] in ("ERROR", "MISMATCH"))

r = verify_mathematics("equality", {"expr_a": "@@bad@@", "variables": ["x"]})
# missing expr_b returns NOT_APPLICABLE actually since equality requires both
expect("missing field handled",
       r["status"] in ("NOT_APPLICABLE", "ERROR"))


print(f"\n{'='*60}")
if FAIL:
    print(f"FAIL: {PASS} passed, {FAIL} failed.")
    raise SystemExit(1)
print(f"All {PASS} MCP tool tests passed.")
print(f"{'='*60}")
