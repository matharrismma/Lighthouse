"""Zero-false-positive guarantee, EXTENDED: subtle near-misses and untested sub-modes.

test_no_false_positives_multidomain.py proves the guarantee with one case per domain.
This file presses harder -- the false specs here are deliberate *near-misses* (the
(x+1)**2 = x**2+1 freshman error; a wrong antiderivative whose derivative is off by a
constant; an unbalanced equation that looks balanced; BB84 insecure-but-claimed-secure)
plus sub-modes the first file never exercised (integral, limit, solve, equality, gcd,
factorial, permutations, circle area, shell capacity, critical angle, compound interest,
Grover). A loose verifier passes the one-case test and fails here.

All offline through api.derivation.verify_step. Shapes copied from _BRIDGE_SYS.

Run: PYTHONPATH=src python -m pytest tests/test_no_false_positives_extended.py
     PYTHONPATH=src python tests/test_no_false_positives_extended.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import derivation as D  # noqa: E402

# (label, domain, TRUE spec, deliberately-FALSE near-miss spec)
CASES = [
    ("math_integral", "mathematics",
     {"mode": "integral", "params": {"integrand": "2*x", "variable": "x", "claimed_antiderivative": "x**2"}},
     {"mode": "integral", "params": {"integrand": "2*x", "variable": "x", "claimed_antiderivative": "x**2 + x"}}),
    ("math_limit", "mathematics",
     {"mode": "limit", "params": {"function": "sin(x)/x", "variable": "x", "point": 0, "claimed_limit": "1"}},
     {"mode": "limit", "params": {"function": "sin(x)/x", "variable": "x", "point": 0, "claimed_limit": "0"}}),
    ("math_solve", "mathematics",
     {"mode": "solve", "params": {"equation": "2*x - 6", "variable": "x", "claimed_solutions": [3]}},
     {"mode": "solve", "params": {"equation": "2*x - 6", "variable": "x", "claimed_solutions": [2]}}),
    ("math_equality_freshman", "mathematics",  # the classic (x+1)^2 = x^2+1 trap
     {"mode": "equality", "params": {"expr_a": "(x+1)**2", "expr_b": "x**2+2*x+1", "variables": ["x"]}},
     {"mode": "equality", "params": {"expr_a": "(x+1)**2", "expr_b": "x**2+1", "variables": ["x"]}}),
    ("nt_factorial", "number_theory",
     {"factorial_n": 5, "claimed_factorial": 120},
     {"factorial_n": 5, "claimed_factorial": 100}),
    ("nt_gcd", "number_theory",
     {"gcd_a": 12, "gcd_b": 18, "claimed_gcd": 6},
     {"gcd_a": 12, "gcd_b": 18, "claimed_gcd": 4}),
    ("comb_permutations", "combinatorics",
     {"perm_n": 5, "perm_k": 2, "claimed_permutations": 20},
     {"perm_n": 5, "perm_k": 2, "claimed_permutations": 10}),
    ("geo_circle_area", "geometry",
     {"circle_radius": 5, "claimed_circle_area": 78.5398},
     {"circle_radius": 5, "claimed_circle_area": 75.0}),
    ("geo_valid_triangle", "geometry",  # 1,2,10 violates the triangle inequality
     {"tri_a": 3, "tri_b": 4, "tri_c": 5, "claimed_valid_triangle": True},
     {"tri_a": 1, "tri_b": 2, "tri_c": 10, "claimed_valid_triangle": True}),
    ("optics_photon_energy", "optics",  # E = hc/lambda with SI-2019 constants -> 3.056e-19 J
     {"wavelength_m": 6.5e-7, "claimed_photon_energy_j": 3.056e-19},
     {"wavelength_m": 6.5e-7, "claimed_photon_energy_j": 5.0e-19}),
    ("optics_critical_angle", "optics",
     {"n_core": 1.5, "n_cladding": 1.0, "claimed_critical_angle_deg": 41.81},
     {"n_core": 1.5, "n_cladding": 1.0, "claimed_critical_angle_deg": 30.0}),
    ("atomic_shell_capacity", "atomic",
     {"shell_n": 3, "claimed_shell_capacity": 18},
     {"shell_n": 3, "claimed_shell_capacity": 9}),
    ("physics_emc2", "physics_dimensional",
     {"equation": "E = m*c**2", "symbols": {"E": "joule", "m": "kilogram", "c": "meter/second"}},
     {"equation": "E = m*c**2", "symbols": {"E": "newton", "m": "kilogram", "c": "meter/second"}}),
    ("chem_unbalanced", "chemistry",
     {"equation": "CH4 + 2 O2 -> CO2 + 2 H2O"},
     {"equation": "CH4 + O2 -> CO2 + H2O"}),
    ("music_midi", "music_theory",
     {"midi_note": 60, "claimed_frequency_hz": 261.63},
     {"midi_note": 60, "claimed_frequency_hz": 440.0}),
    ("econ_compound", "economics",
     {"principal": 1000, "rate": 0.05, "time_years": 3, "compounding_periods": 12, "claimed_compound_amount": 1161.62},
     {"principal": 1000, "rate": 0.05, "time_years": 3, "compounding_periods": 12, "claimed_compound_amount": 1200.0}),
    ("qc_grover", "quantum_computing",
     {"n_items": 64, "claimed_grover_iterations": 6},
     {"n_items": 64, "claimed_grover_iterations": 10}),
    ("qc_bb84", "quantum_computing",  # secure iff QBER < 0.11
     {"qber": 0.09, "claimed_secure": True},
     {"qber": 0.20, "claimed_secure": True}),
]


def test_true_claims_confirm():
    """Every known-true near-miss control must CONFIRM (no false negatives)."""
    for label, domain, true_spec, _false in CASES:
        st = D.verify_step(domain, true_spec)["status"]
        assert st == "CONFIRMED", f"{label} ({domain}): true claim returned {st}, expected CONFIRMED"


def test_false_near_misses_never_confirm():
    """THE CARDINAL GUARANTEE under pressure: no subtle near-miss is ever confirmed."""
    for label, domain, _true, false_spec in CASES:
        st = D.verify_step(domain, false_spec)["status"]
        assert st != "CONFIRMED", f"{label} ({domain}): a FALSE near-miss was CONFIRMED -- a false positive!"


def test_false_step_never_holds_in_a_chain():
    """At the chain level: any near-miss step keeps the derivation from HOLDING."""
    for label, domain, _true, false_spec in CASES:
        r = D.verify_derivation([{"id": "s0", "domain": domain, "spec": false_spec}])
        assert r["verdict"] != "HOLDS", f"{label} ({domain}): chain with a false step HELD -- a false positive!"


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
    print(f"\n{len(fns) - failed}/{len(fns)} passed | {len(CASES)} adversarial cases")
    sys.exit(1 if failed else 0)
