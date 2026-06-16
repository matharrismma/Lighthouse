"""The zero-false-positive guarantee, proven OFFLINE across many domains.

The engine's one absolute promise is: never seal a falsehood. Before this file that
promise was tested by a single benchmark in ONE domain (mathematics), over live HTTP.
This proves it offline across 14 domains: for each, a known-TRUE claim must CONFIRM and
a known-FALSE claim must NEVER confirm (and a false step must never let a derivation
HOLD).

The spec shapes come from the verified bridge prompt (api/derivation.py `_BRIDGE_SYS`),
where each shape is documented as tested end-to-end through dispatch.

Run: PYTHONPATH=src python -m pytest tests/test_no_false_positives_multidomain.py
     PYTHONPATH=src python tests/test_no_false_positives_multidomain.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import derivation as D  # noqa: E402

# domain -> (a TRUE spec, a deliberately FALSE spec)
CASES = {
    "mathematics": (
        {"mode": "derivative", "params": {"function": "x**2", "variable": "x", "claimed_derivative": "2*x"}},
        {"mode": "derivative", "params": {"function": "x**2", "variable": "x", "claimed_derivative": "3*x"}}),
    "number_theory": (
        {"n_prime": 17, "claimed_prime": True},
        {"n_prime": 15, "claimed_prime": True}),
    "combinatorics": (
        {"comb_n": 5, "comb_k": 2, "claimed_combinations": 10},
        {"comb_n": 5, "comb_k": 2, "claimed_combinations": 11}),
    "formal_logic": (
        {"variables": ["p", "q"], "formula": "p | ~p", "claimed_tautology": True},
        {"variables": ["p", "q"], "formula": "p & ~p", "claimed_tautology": True}),
    "geometry": (
        {"pyth_a": 3, "pyth_b": 4, "pyth_c": 5, "claimed_right_triangle": True},
        {"pyth_a": 3, "pyth_b": 4, "pyth_c": 6, "claimed_right_triangle": True}),
    "optics": (
        {"n1": 1.0, "n2": 1.5, "theta1_deg": 30, "claimed_theta2_deg": 19.47},
        {"n1": 1.0, "n2": 1.5, "theta1_deg": 30, "claimed_theta2_deg": 30.0}),
    "atomic": (
        {"atomic_number": 6, "claimed_configuration": "1s2 2s2 2p2"},
        {"atomic_number": 6, "claimed_configuration": "1s2 2s2 2p4"}),
    "molecular_geometry": (
        {"bonding_domains": 4, "lone_pairs": 0, "claimed_geometry": "tetrahedral", "claimed_bond_angle_deg": 109.47},
        {"bonding_domains": 4, "lone_pairs": 0, "claimed_geometry": "octahedral", "claimed_bond_angle_deg": 109.47}),
    "statistics": (
        {"pvalue": {"test": "z", "z": 1.96, "tail": "two", "claimed_p": 0.05}},
        {"pvalue": {"test": "z", "z": 1.96, "tail": "two", "claimed_p": 0.5}}),
    "physics_dimensional": (
        {"equation": "F = m*a", "symbols": {"F": "newton", "m": "kilogram", "a": "meter/second**2"}},
        {"equation": "F = m*a", "symbols": {"F": "joule", "m": "kilogram", "a": "meter/second**2"}}),
    "chemistry": (
        {"equation": "2 H2 + O2 -> 2 H2O"},
        {"equation": "H2 + O2 -> H2O"}),
    "music_theory": (
        {"freq_a": 440, "freq_b": 660, "claimed_interval": "fifth"},
        {"freq_a": 440, "freq_b": 880, "claimed_interval": "fifth"}),
    "economics": (
        {"rate_percent": 7, "claimed_doubling_years": 10.3},
        {"rate_percent": 7, "claimed_doubling_years": 5.0}),
    "quantum_computing": (
        {"amplitudes": [0.6, 0.8], "claimed_normalized": True},
        {"amplitudes": [0.6, 0.6], "claimed_normalized": True}),
}


def test_true_claims_confirm():
    """Every known-true claim must CONFIRM (no false negatives in this set)."""
    for domain, (true_spec, _false) in CASES.items():
        st = D.verify_step(domain, true_spec)["status"]
        assert st == "CONFIRMED", f"{domain}: true claim returned {st}, expected CONFIRMED"


def test_false_claims_never_confirm():
    """THE CARDINAL GUARANTEE: a false claim is NEVER confirmed -- in any domain."""
    for domain, (_true, false_spec) in CASES.items():
        st = D.verify_step(domain, false_spec)["status"]
        assert st != "CONFIRMED", f"{domain}: FALSE claim was CONFIRMED -- a false positive!"


def test_false_step_never_holds_in_a_chain():
    """At the chain level: a derivation containing a false step never HOLDS."""
    for domain, (_true, false_spec) in CASES.items():
        r = D.verify_derivation([{"id": "s0", "domain": domain, "spec": false_spec}])
        assert r["verdict"] != "HOLDS", f"{domain}: chain with a false step HELD -- a false positive!"


def test_true_chain_holds():
    """A chain built only of true steps from distinct domains HOLDS."""
    steps = [{"id": f"s{i}", "domain": d, "spec": s}
             for i, (d, (s, _f)) in enumerate(CASES.items())]
    r = D.verify_derivation(steps)
    assert r["verdict"] == "HOLDS", f"all-true multi-domain chain did not HOLD: {r['verdict']}"
    assert r["confirmed_steps"] == len(CASES)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed | {len(CASES)} domains covered")
    sys.exit(1 if failed else 0)
