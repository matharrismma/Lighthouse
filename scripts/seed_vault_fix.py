"""
Fix batch: 21 interactions that errored/skipped in seed_vault_100.py,
now routed to correct tool names and signatures.
"""
from __future__ import annotations
import sys, time
from pathlib import Path

repo = Path(__file__).parent.parent
sys.path.insert(0, str(repo / "src"))
sys.path.insert(0, str(repo))

from concordance_engine.mcp_server.tools import ALL_TOOLS
from api.packet_store import get_packet_store
from api.trust_index import record_confirmation

try:
    from concordance_engine.instance_identity import get_instance_id
    INSTANCE_ID = get_instance_id() or "seed-script"
except Exception:
    INSTANCE_ID = "seed-script"

store = get_packet_store()

# ── Fixed interactions ─────────────────────────────────────────────────────────
# verify_mathematics: (mode, params)  — modes: equality, derivative, integral, solve, matrix
# verify_physics_conservation: (before, after, law=)
# verify_physics_dimensional: (expression, expected_dimensions)
# verify_statistics_pvalue: (spec)
# verify_statistics_confidence_interval: (spec)
# verify_statistics_multiple_comparisons: (spec)
# verify_governance_decision_packet: (decision_packet, witness_count, domain)
# verify_computer_science: (code, function_name, test_cases, claimed_class)

INTERACTIONS = [
    # MATHEMATICS (correct signature: fn(mode, params))
    ("mathematics", "equality", {"lhs": "2**10", "rhs": "1024"}),
    ("mathematics", "equality", {"lhs": "sin(pi/2)", "rhs": "1"}),
    ("mathematics", "equality", {"lhs": "log(e)", "rhs": "1"}),
    ("mathematics", "solve", {"equation": "x**2 - 5*x + 6", "variable": "x"}),
    ("mathematics", "inequality", {"lhs": "x", "rhs": "0", "op": ">", "domain": "positive"}),

    # PHYSICS — conservation law
    ("physics_conservation", {"kinetic_energy": 1000, "potential_energy": 500}, {"kinetic_energy": 900, "potential_energy": 600}),
    ("physics_conservation", {"momentum_x": 10, "momentum_y": 0}, {"momentum_x": 10, "momentum_y": 0}),

    # PHYSICS — dimensional analysis
    ("physics_dimensional", "F = m * a", "kg * m / s**2"),
    ("physics_dimensional", "E = m * c**2", "kg * m**2 / s**2"),
    ("physics_dimensional", "v = d / t", "m / s"),

    # STATISTICS (correct tool names)
    ("statistics_pvalue", {"observed": [15, 25, 20, 30, 10], "expected": [20, 20, 20, 20, 20], "test": "chi_square"}),
    ("statistics_pvalue", {"group_a": [5.1, 5.4, 5.0, 5.3], "group_b": [4.8, 4.7, 5.1, 4.9], "test": "t_test"}),
    ("statistics_confidence_interval", {"sample_mean": 50, "sample_std": 10, "n": 100, "confidence": 0.95}),
    ("statistics_multiple_comparisons", {"p_values": [0.04, 0.03, 0.02, 0.05], "method": "bonferroni", "alpha": 0.05}),

    # GOVERNANCE
    ("governance_decision_packet", {"decision": "Adopt the open-source license", "rationale": "Maximizes reach", "alternatives_considered": ["proprietary", "CC-BY"]}, 5),

    # COMPUTER SCIENCE (correct signature: fn(code, function_name, test_cases, claimed_class))
    ("computer_science",
     "def binary_search(arr, target):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        mid = (lo+hi)//2\n        if arr[mid]==target: return mid\n        elif arr[mid]<target: lo=mid+1\n        else: hi=mid-1\n    return -1",
     "binary_search", [{"input": [[1,3,5,7,9], 5], "output": 2}], "O(log n)"),

    # NUMBER THEORY (separate tool)
    ("number_theory", {"n": 28, "check": "perfect"}),
    ("number_theory", {"n": 496, "check": "perfect"}),
    ("number_theory", {"a": 12, "b": 18, "operation": "gcd"}),
    ("number_theory", {"n": 17, "check": "prime"}),
    ("number_theory", {"base": 2, "exp": 10, "modulus": 1000}),
]


def run_one(idx, *args):
    tool_key = args[0]
    rest = args[1:]

    if tool_key == "mathematics":
        mode, params = rest[0], rest[1]
        fn = ALL_TOOLS.get("verify_mathematics")
        domain = "mathematics"
        spec = {"mode": mode, "params": params}
        try:
            result = fn(mode, params)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "physics_conservation":
        before, after = rest[0], rest[1]
        fn = ALL_TOOLS.get("verify_physics_conservation")
        domain = "physics_conservation"
        spec = {"before": before, "after": after}
        try:
            result = fn(before, after)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "physics_dimensional":
        expression, expected = rest[0], rest[1]
        fn = ALL_TOOLS.get("verify_physics_dimensional")
        domain = "physics_dimensional"
        spec = {"expression": expression, "expected": expected}
        try:
            result = fn(expression, expected)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "statistics_pvalue":
        fn = ALL_TOOLS.get("verify_statistics_pvalue")
        domain = "statistics_pvalue"
        spec = rest[0]
        try:
            result = fn(spec)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "statistics_confidence_interval":
        fn = ALL_TOOLS.get("verify_statistics_confidence_interval")
        domain = "statistics_confidence_interval"
        spec = rest[0]
        try:
            result = fn(spec)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "statistics_multiple_comparisons":
        fn = ALL_TOOLS.get("verify_statistics_multiple_comparisons")
        domain = "statistics_multiple_comparisons"
        spec = rest[0]
        try:
            result = fn(spec)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "governance_decision_packet":
        packet, witness_count = rest[0], rest[1]
        fn = ALL_TOOLS.get("verify_governance_decision_packet")
        domain = "governance_decision_packet"
        spec = {"packet": packet, "witness_count": witness_count}
        try:
            result = fn(packet, witness_count=witness_count)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "computer_science":
        code, fn_name, test_cases, claimed_class = rest[0], rest[1], rest[2], rest[3]
        fn = ALL_TOOLS.get("verify_computer_science")
        domain = "computer_science"
        spec = {"code": code[:50] + "...", "claimed_class": claimed_class}
        try:
            result = fn(code, function_name=fn_name, test_cases=test_cases, claimed_class=claimed_class)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}

    elif tool_key == "number_theory":
        fn = ALL_TOOLS.get("verify_number_theory")
        domain = "number_theory"
        spec = rest[0]
        try:
            result = fn(spec)
        except Exception as exc:
            return {"status": "error", "domain": domain, "error": str(exc)}
    else:
        return {"status": "skip", "reason": f"unknown: {tool_key}"}

    entry = store.append(domain, spec, result)
    summary = entry.get("summary", "UNKNOWN")
    record_confirmation(domain, spec, INSTANCE_ID, summary=summary, entry_id=entry.get("id"))
    return {"status": "ok", "domain": domain, "summary": summary, "entry_id": entry.get("id")}


def main():
    print(f"Fix batch: {len(INTERACTIONS)} interactions\n")
    results = {"ok": 0, "skip": 0, "error": 0}
    t0 = time.time()
    for idx, args in enumerate(INTERACTIONS, 1):
        r = run_one(idx, *args)
        status = r["status"]
        results[status] = results.get(status, 0) + 1
        marker = "+" if status == "ok" else ("~" if status == "skip" else "!")
        domain = r.get("domain", args[0])
        print(f"  [{idx:03d}] {marker} {domain:<32} {r.get('summary', r.get('reason', r.get('error', '')))[:60]}")
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s — OK:{results.get('ok',0)} Skip:{results.get('skip',0)} Error:{results.get('error',0)}")


if __name__ == "__main__":
    main()
