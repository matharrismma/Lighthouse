"""
benchmark_v2_generate.py — build the v2 benchmark dataset.

Self-validating: each item runs the actual verifier before recording.
  - correct spec  → verifier must return CONFIRMED
  - incorrect spec → verifier must return MISMATCH or ERROR

Outputs: benchmark_v2_dataset.jsonl  (one JSON object per line)

Run from repo root:
    python lw/09_evaluation/benchmark_v2_generate.py
"""
from __future__ import annotations
import hashlib, json, math, sys, time, itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from concordance_engine.mcp_server.tools import ALL_TOOLS

HERE = Path(__file__).resolve().parent
OUT  = HERE / "benchmark_v2_dataset.jsonl"

# ── helpers ───────────────────────────────────────────────────────────────────

_counter = itertools.count(1)

def _summary(result) -> str:
    if isinstance(result, dict):
        s = result.get("status")
        if s:
            return s
        statuses = []
        for v in result.values():
            if isinstance(v, dict) and "status" in v:
                statuses.append(v["status"])
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "status" in item:
                        statuses.append(item["status"])
        if "MISMATCH" in statuses:
            return "MISMATCH"
        if "ERROR" in statuses:
            return "ERROR"
        if "CONFIRMED" in statuses:
            return "CONFIRMED"
        if statuses:
            return statuses[0]
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "status" in item:
                return item["status"]
    return "UNKNOWN"


def _item(domain, template_id, claim_text, ground_truth, spec_snapshot, perturbation=None):
    uid = hashlib.md5(f"{domain}:{template_id}:{ground_truth}:{claim_text}".encode()).hexdigest()[:12]
    row = {
        "id": uid,
        "seq": next(_counter),
        "domain": domain,
        "template_id": template_id,
        "claim_text": claim_text,
        "ground_truth": ground_truth,
        "spec_snapshot": spec_snapshot,
    }
    if perturbation:
        row["perturbation"] = perturbation
    return row


def _pair(domain, template_id, correct_fn, wrong_fn, correct_claim, wrong_claim, correct_snap, wrong_snap, wrong_perturbation="value_perturbed"):
    """Run both specs. Emit items only when verifier agrees with expected label."""
    items = []
    try:
        rc = _summary(correct_fn())
        if rc == "CONFIRMED":
            items.append(_item(domain, template_id, correct_claim, "correct", correct_snap))
        else:
            print(f"  WARN {domain}/{template_id} correct->{rc} (expected CONFIRMED)")
    except Exception as e:
        print(f"  ERR  {domain}/{template_id} correct: {e!r}")

    try:
        wc = _summary(wrong_fn())
        if wc in ("MISMATCH", "ERROR"):
            items.append(_item(domain, template_id, wrong_claim, "incorrect", wrong_snap, wrong_perturbation))
        else:
            print(f"  WARN {domain}/{template_id} wrong->{wc} (expected MISMATCH)")
    except Exception as e:
        print(f"  ERR  {domain}/{template_id} wrong: {e!r}")

    return items


# ── domain-specific callers ───────────────────────────────────────────────────

_math  = ALL_TOOLS["verify_mathematics"]
_chem  = ALL_TOOLS["verify_chemistry"]
_phys_c = ALL_TOOLS["verify_physics_conservation"]
_phys_d = ALL_TOOLS["verify_physics_dimensional"]
_stat_ci  = ALL_TOOLS["verify_statistics_confidence_interval"]
_stat_mc  = ALL_TOOLS["verify_statistics_multiple_comparisons"]
_stat_pv  = ALL_TOOLS["verify_statistics_pvalue"]
_cs    = ALL_TOOLS["verify_computer_science"]
_logic = ALL_TOOLS["verify_formal_logic"]
_gov   = ALL_TOOLS["verify_governance_decision_packet"]
_number = ALL_TOOLS["verify_number_theory"]


def _math_eq(a, b):
    return _math("equality", {"expr_a": a, "expr_b": b})

def _math_deriv(fn_expr, var, claimed):
    return _math("derivative", {"function": fn_expr, "variable": var, "claimed_derivative": claimed})

def _math_solve(eq, var, claimed_sols):
    return _math("solve", {"equation": eq, "variable": var, "claimed_solutions": claimed_sols})

def _logic_sat(formula, claimed):
    return _logic({"formula": formula, "claimed_satisfiable": claimed})

def _logic_taut(formula, claimed):
    return _logic({"formula": formula, "claimed_tautology": claimed})

def _logic_equiv(fa, fb, claimed):
    return _logic({"formula_a": fa, "formula_b": fb, "claimed_equivalent": claimed})

def _stat_mc_claimed(p_values, method, alpha, claimed_rejected_indices):
    return _stat_mc(p_values, method, alpha, claimed_rejected_indices)


# ── item builders ─────────────────────────────────────────────────────────────

def build_mathematics_equality():
    items = []
    cases = [
        # (expr_a, expr_b_correct, claim_correct, expr_b_wrong, claim_wrong)
        ("2**10",   "1024",          "2 to the power of 10 equals 1024",
                    "512",           "2 to the power of 10 equals 512"),
        ("sin(pi/2)", "1",           "sin(π/2) equals 1",
                    "0",             "sin(π/2) equals 0"),
        ("cos(pi)", "-1",            "cos(π) equals -1",
                    "1",             "cos(π) equals 1"),
        ("log(E)",  "1",             "ln(e) equals 1",
                    "0",             "ln(e) equals 0"),
        ("2**8",    "256",           "2^8 equals 256",
                    "128",           "2^8 equals 128"),
        ("factorial(5)", "120",      "5! equals 120",
                    "60",            "5! equals 60"),
        ("pi**2",   "pi**2",         "π² equals π²",
                    "9",             "π² equals 9"),
        ("sqrt(144)", "12",          "√144 equals 12",
                    "14",            "√144 equals 14"),
        ("E**2",    "E**2",          "e² equals e²",
                    "4",             "e² equals 4"),
        ("sin(0)", "0",              "sin(0) equals 0",
                   "1",              "sin(0) equals 1"),
        ("cos(0)", "1",              "cos(0) equals 1",
                   "0",              "cos(0) equals 0"),
        ("tan(pi/4)", "1",           "tan(π/4) equals 1",
                    "0",             "tan(π/4) equals 0"),
        ("2**0",    "1",             "2^0 equals 1",
                    "2",             "2^0 equals 2"),
        ("7**2",    "49",            "7² equals 49",
                    "42",            "7² equals 42"),
        ("Abs(-5)", "5",             "|-5| equals 5",
                    "−5",            "|-5| equals -5"),
    ]
    for a, b_c, cl_c, b_w, cl_w in cases:
        items += _pair(
            "mathematics", f"eq_{a}",
            lambda a=a, b=b_c: _math_eq(a, b),
            lambda a=a, b=b_w: _math_eq(a, b),
            cl_c, cl_w,
            {"mode": "equality", "expr_a": a, "expr_b": b_c},
            {"mode": "equality", "expr_a": a, "expr_b": b_w},
        )
    return items


def build_mathematics_derivative():
    items = []
    cases = [
        # (function, var, correct_deriv, wrong_deriv, correct_claim, wrong_claim)
        ("x**2", "x", "2*x", "x",
         "The derivative of x² with respect to x is 2x",
         "The derivative of x² with respect to x is x"),
        ("x**3", "x", "3*x**2", "2*x**2",
         "The derivative of x³ with respect to x is 3x²",
         "The derivative of x³ with respect to x is 2x²"),
        ("sin(x)", "x", "cos(x)", "sin(x)",
         "The derivative of sin(x) is cos(x)",
         "The derivative of sin(x) is sin(x)"),
        ("cos(x)", "x", "-sin(x)", "sin(x)",
         "The derivative of cos(x) is -sin(x)",
         "The derivative of cos(x) is sin(x)"),
        ("E**x", "x", "exp(x)", "E**x/x",
         "The derivative of e^x is e^x",
         "The derivative of e^x is e^x/x"),
        ("log(x)", "x", "1/x", "x",
         "The derivative of ln(x) is 1/x",
         "The derivative of ln(x) is x"),
        ("x**4", "x", "4*x**3", "3*x**2",
         "The derivative of x⁴ is 4x³",
         "The derivative of x⁴ is 3x²"),
        ("x**(-1)", "x", "-x**(-2)", "x**(-2)",
         "The derivative of 1/x is -1/x²",
         "The derivative of 1/x is 1/x²"),
        ("x**2 + 3*x + 1", "x", "2*x + 3", "2*x",
         "The derivative of x²+3x+1 is 2x+3",
         "The derivative of x²+3x+1 is 2x"),
        ("tan(x)", "x", "1/cos(x)**2", "cos(x)**2",
         "The derivative of tan(x) is sec²(x)",
         "The derivative of tan(x) is cos²(x)"),
    ]
    for fn_e, v, cd, wd, cl_c, cl_w in cases:
        items += _pair(
            "mathematics", f"deriv_{fn_e[:12]}",
            lambda fe=fn_e, vv=v, d=cd: _math_deriv(fe, vv, d),
            lambda fe=fn_e, vv=v, d=wd: _math_deriv(fe, vv, d),
            cl_c, cl_w,
            {"mode": "derivative", "function": fn_e, "variable": v, "claimed_derivative": cd},
            {"mode": "derivative", "function": fn_e, "variable": v, "claimed_derivative": wd},
        )
    return items


def build_mathematics_solve():
    items = []
    cases = [
        ("x**2 - 4", "x", ["2", "-2"], ["2"],
         "The equation x²-4=0 has solutions x=2 and x=-2",
         "The equation x²-4=0 has only one solution x=2"),
        ("x**2 - 9", "x", ["3", "-3"], ["3"],
         "x²=9 has solutions x=3 and x=-3",
         "x²=9 has only the solution x=3"),
        ("2*x - 6", "x", ["3"], ["6"],
         "2x-6=0 has the solution x=3",
         "2x-6=0 has the solution x=6"),
        ("x**2 - 5*x + 6", "x", ["2", "3"], ["2", "4"],
         "x²-5x+6=0 has solutions x=2 and x=3",
         "x²-5x+6=0 has solutions x=2 and x=4"),
        ("x - 7", "x", ["7"], ["3"],
         "x-7=0 has the solution x=7",
         "x-7=0 has the solution x=3"),
    ]
    for eq, v, cs, ws, cl_c, cl_w in cases:
        items += _pair(
            "mathematics", f"solve_{eq[:15]}",
            lambda e=eq, vv=v, s=cs: _math_solve(e, vv, s),
            lambda e=eq, vv=v, s=ws: _math_solve(e, vv, s),
            cl_c, cl_w,
            {"mode": "solve", "equation": eq, "variable": v, "claimed_solutions": cs},
            {"mode": "solve", "equation": eq, "variable": v, "claimed_solutions": ws},
        )
    return items


def build_chemistry():
    items = []
    cases = [
        # (balanced_eq, unbalanced_eq, correct_claim, wrong_claim)
        ("2H2 + O2 -> 2H2O",   "H2 + O2 -> H2O",
         "The chemical equation 2H₂ + O₂ → 2H₂O is balanced",
         "The chemical equation H₂ + O₂ → H₂O is balanced"),
        ("CH4 + 2O2 -> CO2 + 2H2O", "CH4 + O2 -> CO2 + H2O",
         "CH₄ + 2O₂ → CO₂ + 2H₂O is a balanced combustion equation",
         "CH₄ + O₂ → CO₂ + H₂O is a balanced combustion equation"),
        ("2NaOH + H2SO4 -> Na2SO4 + 2H2O", "NaOH + H2SO4 -> Na2SO4 + H2O",
         "2NaOH + H₂SO₄ → Na₂SO₄ + 2H₂O is balanced",
         "NaOH + H₂SO₄ → Na₂SO₄ + H₂O is balanced"),
        ("N2 + 3H2 -> 2NH3", "N2 + H2 -> NH3",
         "N₂ + 3H₂ → 2NH₃ (Haber process) is balanced",
         "N₂ + H₂ → NH₃ is balanced"),
        ("2CO + O2 -> 2CO2", "CO + O2 -> CO2",
         "2CO + O₂ → 2CO₂ is balanced",
         "CO + O₂ → CO₂ is balanced"),
        ("C6H12O6 + 6O2 -> 6CO2 + 6H2O", "C6H12O6 + O2 -> CO2 + H2O",
         "C₆H₁₂O₆ + 6O₂ → 6CO₂ + 6H₂O (aerobic respiration) is balanced",
         "C₆H₁₂O₆ + O₂ → CO₂ + H₂O is balanced"),
        ("4Fe + 3O2 -> 2Fe2O3", "Fe + O2 -> Fe2O3",
         "4Fe + 3O₂ → 2Fe₂O₃ (rust formation) is balanced",
         "Fe + O₂ → Fe₂O₃ is balanced"),
        ("2H2O2 -> 2H2O + O2", "H2O2 -> H2O + O2",
         "2H₂O₂ → 2H₂O + O₂ (hydrogen peroxide decomposition) is balanced",
         "H₂O₂ → H₂O + O₂ is balanced"),
        ("2Na + 2H2O -> 2NaOH + H2", "Na + H2O -> NaOH + H2",
         "2Na + 2H₂O → 2NaOH + H₂ is balanced",
         "Na + H₂O → NaOH + H₂ is balanced"),
        ("Ca + 2HCl -> CaCl2 + H2", "Ca + HCl -> CaCl2 + H2",
         "Ca + 2HCl → CaCl₂ + H₂ is balanced",
         "Ca + HCl → CaCl₂ + H₂ is balanced"),
        ("3H2 + N2 -> 2NH3", "H2 + N2 -> NH3",
         "3H₂ + N₂ → 2NH₃ is balanced",
         "H₂ + N₂ → NH₃ is balanced"),
        ("2Al + 3Cl2 -> 2AlCl3", "Al + Cl2 -> AlCl3",
         "2Al + 3Cl₂ → 2AlCl₃ is balanced",
         "Al + Cl₂ → AlCl₃ is balanced"),
        ("2KClO3 -> 2KCl + 3O2", "KClO3 -> KCl + O2",
         "2KClO₃ → 2KCl + 3O₂ is balanced",
         "KClO₃ → KCl + O₂ is balanced"),
        ("Zn + 2HCl -> ZnCl2 + H2", "Zn + HCl -> ZnCl2 + H2",
         "Zn + 2HCl → ZnCl₂ + H₂ is balanced",
         "Zn + HCl → ZnCl₂ + H₂ is balanced"),
        ("2Mg + O2 -> 2MgO", "Mg + O2 -> MgO",
         "2Mg + O₂ → 2MgO is balanced",
         "Mg + O₂ → MgO is balanced"),
    ]
    for bal, unbal, cl_c, cl_w in cases:
        def _run(eq):
            r = _chem(eq)
            return r.get("equation", {}).get("status", "UNKNOWN")
        items += _pair(
            "chemistry", f"chem_{bal[:15]}",
            lambda e=bal: _chem(e),
            lambda e=unbal: _chem(e),
            cl_c, cl_w,
            {"equation": bal},
            {"equation": unbal},
        )
    return items


def build_physics_conservation():
    items = []
    cases = [
        # (quantity, val_before, val_after_correct, val_after_wrong, claim_c, claim_w)
        ("momentum_kg_m_s", 10.0, 10.0, 9.0,
         "A closed system with initial momentum 10 kg·m/s still has momentum 10 kg·m/s after the interaction (conserved)",
         "A closed system loses momentum: 10 kg·m/s before but only 9 kg·m/s after (still 'conserved')"),
        ("kinetic_energy_J", 500.0, 500.0, 400.0,
         "In an elastic collision, kinetic energy before (500 J) equals kinetic energy after (500 J)",
         "In an elastic collision, kinetic energy drops from 500 J to 400 J (elastic)"),
        ("total_energy_J", 1000.0, 1000.0, 850.0,
         "Total mechanical energy is conserved at 1000 J before and after",
         "Total mechanical energy decreases from 1000 J to 850 J but is claimed conserved"),
        ("charge_C", 2.5, 2.5, 2.0,
         "Electric charge is conserved: 2.5 C before and 2.5 C after the reaction",
         "Electric charge drops from 2.5 C to 2.0 C but is claimed conserved"),
        ("mass_kg", 5.0, 5.0, 4.5,
         "In a chemical reaction at standard conditions, mass is conserved: 5 kg in, 5 kg out",
         "Mass decreases from 5 kg to 4.5 kg in a reaction (claimed conserved)"),
        ("angular_momentum_kg_m2_s", 8.0, 8.0, 6.0,
         "Angular momentum is conserved at 8 kg·m²/s in this isolated system",
         "Angular momentum changes from 8 to 6 kg·m²/s yet is claimed conserved"),
        ("baryon_number", 3.0, 3.0, 2.0,
         "Baryon number is conserved: 3 baryons in, 3 baryons out",
         "Baryon number changes from 3 to 2 but is claimed conserved"),
        ("lepton_number", 2.0, 2.0, 1.0,
         "Lepton number is conserved at 2 in this decay",
         "Lepton number drops from 2 to 1 but is claimed conserved"),
    ]
    for qty, bef, aft_c, aft_w, cl_c, cl_w in cases:
        items += _pair(
            "physics_conservation", f"phys_cons_{qty[:15]}",
            lambda q=qty, b=bef, a=aft_c: _phys_c({q: b}, {q: a}),
            lambda q=qty, b=bef, a=aft_w: _phys_c({q: b}, {q: a}),
            cl_c, cl_w,
            {"before": {qty: bef}, "after": {qty: aft_c}},
            {"before": {qty: bef}, "after": {qty: aft_w}},
        )
    return items


def build_physics_dimensional():
    items = []
    cases = [
        # (equation, correct_dims, wrong_dims, claim_c, claim_w)
        ("F = m * a",
         {"F": "kg*m/s^2", "m": "kg", "a": "m/s^2"},
         {"F": "kg", "m": "kg", "a": "m/s^2"},
         "In Newton's second law F=ma, force has units kg·m/s² (Newtons)",
         "In Newton's second law F=ma, force has units kg"),
        ("E = m * c**2",
         {"E": "kg*m^2/s^2", "m": "kg", "c": "m/s"},
         {"E": "kg", "m": "kg", "c": "m/s"},
         "In E=mc², energy has units kg·m²/s² (Joules)",
         "In E=mc², energy has units kg"),
        ("v = d / t",
         {"v": "m/s", "d": "m", "t": "s"},
         {"v": "m/s^2", "d": "m", "t": "s"},
         "Velocity v=d/t has units m/s",
         "Velocity v=d/t has units m/s²"),
        ("p = m * v",
         {"p": "kg*m/s", "m": "kg", "v": "m/s"},
         {"p": "kg", "m": "kg", "v": "m/s"},
         "Momentum p=mv has units kg·m/s",
         "Momentum p=mv has units kg"),
        ("W = F * d",
         {"W": "kg*m^2/s^2", "F": "kg*m/s^2", "d": "m"},
         {"W": "kg*m/s^2", "F": "kg*m/s^2", "d": "m"},
         "Work W=Fd has units kg·m²/s² (Joules)",
         "Work W=Fd has units kg·m/s² (Newtons)"),
        ("P = W / t",
         {"P": "kg*m^2/s^3", "W": "kg*m^2/s^2", "t": "s"},
         {"P": "kg*m^2/s^2", "W": "kg*m^2/s^2", "t": "s"},
         "Power P=W/t has units kg·m²/s³ (Watts)",
         "Power P=W/t has units kg·m²/s² (Joules)"),
        ("rho = m / V",
         {"rho": "kg/m^3", "m": "kg", "V": "m^3"},
         {"rho": "kg/m^2", "m": "kg", "V": "m^3"},
         "Density ρ=m/V has units kg/m³",
         "Density ρ=m/V has units kg/m²"),
    ]
    for eq, cdims, wdims, cl_c, cl_w in cases:
        items += _pair(
            "physics_dimensional", f"phys_dim_{eq[:12]}",
            lambda e=eq, d=cdims: _phys_d(e, d),
            lambda e=eq, d=wdims: _phys_d(e, d),
            cl_c, cl_w,
            {"equation": eq, "dimensions": cdims},
            {"equation": eq, "dimensions": wdims},
        )
    return items


def build_statistics_ci():
    import scipy.stats as scstats
    items = []
    # Generate CI cases from actual parameters
    cases = [
        # (mean, sd, n, conf_level, claim_template)
        (50.0,  10.0, 100, 0.95, "Sample mean=50, sd=10, n=100 → 95% CI is approximately [{lo:.1f}, {hi:.1f}]"),
        (70.0,  15.0, 50,  0.95, "Sample mean=70, sd=15, n=50 → 95% CI is approximately [{lo:.1f}, {hi:.1f}]"),
        (100.0, 20.0, 200, 0.99, "Sample mean=100, sd=20, n=200 → 99% CI is approximately [{lo:.1f}, {hi:.1f}]"),
        (25.0,  5.0,  30,  0.90, "Sample mean=25, sd=5, n=30 → 90% CI is approximately [{lo:.1f}, {hi:.1f}]"),
        (0.0,   1.0,  1000, 0.95, "Standardised sample mean=0, sd=1, n=1000 → 95% CI is approximately [{lo:.3f}, {hi:.3f}]"),
        (8.5,   2.0,  40,  0.95, "Sample mean=8.5, sd=2, n=40 → 95% CI is approximately [{lo:.2f}, {hi:.2f}]"),
        (500.0, 50.0, 80,  0.95, "Sample mean=500, sd=50, n=80 → 95% CI is approximately [{lo:.1f}, {hi:.1f}]"),
        (12.3,  3.1,  25,  0.90, "Sample mean=12.3, sd=3.1, n=25 → 90% CI is approximately [{lo:.2f}, {hi:.2f}]"),
    ]
    for mean, sd, n, conf, tmpl in cases:
        tcrit = scstats.t.ppf(0.5 + conf / 2, n - 1)
        margin = tcrit * sd / math.sqrt(n)
        lo, hi = mean - margin, mean + margin
        inflation = 1.4 + 0.1 * (conf == 0.99)  # wrong bounds: too wide
        lo_w, hi_w = mean - margin * inflation, mean + margin * inflation
        cl_c = tmpl.format(lo=lo, hi=hi)
        cl_w = f"The 95% CI for mean={mean}, sd={sd}, n={n} is [{lo_w:.1f}, {hi_w:.1f}] (incorrect bounds)"
        items += _pair(
            "statistics", f"stat_ci_{mean:.0f}_{n}",
            lambda m=mean, ll=lo, hh=hi, sd=sd, n=n, c=conf:
                _stat_ci(m, ll, hh, spec={"mean": m, "sd": sd, "n": n, "conf_level": c}),
            lambda m=mean, ll=lo_w, hh=hi_w, sd=sd, n=n, c=conf:
                _stat_ci(m, ll, hh, spec={"mean": m, "sd": sd, "n": n, "conf_level": c}),
            cl_c, cl_w,
            {"stat_type": "ci", "estimate": mean, "ci_low": lo, "ci_high": hi, "mean": mean, "sd": sd, "n": n, "conf_level": conf},
            {"stat_type": "ci", "estimate": mean, "ci_low": lo_w, "ci_high": hi_w, "mean": mean, "sd": sd, "n": n, "conf_level": conf},
        )
    return items


def build_statistics_mc():
    items = []
    # Use claimed_rejected_indices to get CONFIRMED vs MISMATCH
    # Bonferroni: p_adj = p * k; index rejected if p_adj < alpha
    cases = [
        # (p_values, method, alpha, correct_rejected_idx, wrong_rejected_idx, claim_c, claim_w)
        ([0.01, 0.04, 0.02], "bonferroni", 0.05, [0], [0, 1, 2],
         "Bonferroni correction (3 tests, α=0.05): only index 0 (p=0.01) is rejected",
         "Bonferroni correction (3 tests, α=0.05): all three indices are rejected"),
        ([0.001, 0.002, 0.003], "bonferroni", 0.05, [0, 1, 2], [],
         "Bonferroni correction (3 tests, α=0.05): all three p-values are rejected",
         "Bonferroni correction (3 tests, α=0.05): none are rejected"),
        ([0.06, 0.08, 0.10], "bonferroni", 0.05, [], [0, 1, 2],
         "Bonferroni correction (3 tests, α=0.05): none are rejected (all adjusted p > 0.05)",
         "Bonferroni correction (3 tests, α=0.05): all three are rejected"),
        ([0.049, 0.049], "bonferroni", 0.05, [], [0, 1],
         "Bonferroni correction (2 tests, α=0.05): neither p=0.049 is rejected (0.049*2=0.098 > 0.05)",
         "Bonferroni correction (2 tests, α=0.05): both p=0.049 are rejected"),
        ([0.01, 0.20, 0.30, 0.005], "bonferroni", 0.05, [0, 3], [1, 2],
         "Bonferroni correction (4 tests, α=0.05): indices 0 and 3 are rejected",
         "Bonferroni correction (4 tests, α=0.05): indices 1 and 2 are rejected"),
        ([0.005, 0.010, 0.040], "bonferroni", 0.01, [], [0, 1, 2],
         "Bonferroni correction (3 tests, α=0.01): none are rejected (smallest adj_p=0.015 > 0.01)",
         "Bonferroni correction (3 tests, α=0.01): all three are rejected"),
    ]
    for ps, meth, alpha, ci, wi, cl_c, cl_w in cases:
        k = len(ps)
        items += _pair(
            "statistics", f"stat_mc_k{k}_{meth}_a{alpha}",
            lambda p=ps, m=meth, a=alpha, c=ci: _stat_mc(p, m, a, c),
            lambda p=ps, m=meth, a=alpha, c=wi: _stat_mc(p, m, a, c),
            cl_c, cl_w,
            {"stat_type": "mc", "p_values": ps, "method": meth, "alpha": alpha, "claimed_rejected": ci},
            {"stat_type": "mc", "p_values": ps, "method": meth, "alpha": alpha, "claimed_rejected": wi},
            "claimed_rejected_wrong",
        )
    return items


def build_formal_logic():
    items = []

    # NOTE: use A, B, C — not P, Q, R (those conflict with SymPy builtins)
    # Satisfiability
    sat_cases = [
        ("A & ~A", False, "A AND NOT A is a contradiction — it is not satisfiable",
                          "A AND NOT A is satisfiable"),
        ("A | ~A", True,  "A OR NOT A is a tautology, hence satisfiable",
                          "A OR NOT A is not satisfiable"),
        ("(A >> B) & A & ~B", False,
         "The formula (A implies B) AND A AND NOT B is unsatisfiable",
         "(A implies B) AND A AND NOT B is satisfiable"),
        ("A | B | C", True, "A OR B OR C is satisfiable",
                            "A OR B OR C is not satisfiable"),
        ("~A & ~A", True,  "NOT A AND NOT A is satisfiable (when A is false)",
                           "NOT A AND NOT A is not satisfiable"),
        ("A & B & ~A", False, "A AND B AND NOT A is a contradiction — not satisfiable",
                              "A AND B AND NOT A is satisfiable"),
        ("A & B", True,   "A AND B is satisfiable (when both A and B are true)",
                          "A AND B is not satisfiable"),
    ]
    for formula, claimed, cl_c, cl_w in sat_cases:
        items += _pair(
            "formal_logic", f"logic_sat_{formula[:12]}",
            lambda f=formula, c=claimed: _logic_sat(f, c),
            lambda f=formula, c=not claimed: _logic_sat(f, c),
            cl_c, cl_w,
            {"formula": formula, "claimed_satisfiable": claimed},
            {"formula": formula, "claimed_satisfiable": not claimed},
            "satisfiability_flipped",
        )

    # Tautology
    taut_cases = [
        ("A | ~A", True,  "A OR NOT A is a tautology (Law of Excluded Middle)",
                          "A OR NOT A is not a tautology"),
        ("A & ~A", False, "A AND NOT A is not a tautology (it is always false)",
                          "A AND NOT A is a tautology"),
        ("A >> A", True,  "A implies A is a tautology",
                          "A implies A is not a tautology"),
        ("A >> B", False, "A implies B is not a tautology (false when A is true and B is false)",
                          "A implies B is a tautology"),
        ("(A & B) >> A", True,  "(A AND B) implies A is a tautology",
                                "(A AND B) implies A is not a tautology"),
        ("~(A & ~A)", True, "NOT(A AND NOT A) is a tautology",
                            "NOT(A AND NOT A) is not a tautology"),
        ("A | B", False,  "A OR B is not a tautology (false when both A and B are false)",
                          "A OR B is a tautology"),
    ]
    for formula, claimed, cl_c, cl_w in taut_cases:
        items += _pair(
            "formal_logic", f"logic_taut_{formula[:12]}",
            lambda f=formula, c=claimed: _logic_taut(f, c),
            lambda f=formula, c=not claimed: _logic_taut(f, c),
            cl_c, cl_w,
            {"formula": formula, "claimed_tautology": claimed},
            {"formula": formula, "claimed_tautology": not claimed},
            "tautology_flipped",
        )

    # Equivalence (use >> for implication)
    equiv_cases = [
        ("A >> B", "~A | B", True,
         "A implies B is logically equivalent to NOT A OR B (material implication)",
         "A implies B is NOT logically equivalent to NOT A OR B"),
        ("~(A & B)", "~A | ~B", True,
         "NOT(A AND B) is equivalent to NOT A OR NOT B (De Morgan's law)",
         "NOT(A AND B) is NOT equivalent to NOT A OR NOT B"),
        ("A & B", "B & A", True,
         "A AND B is equivalent to B AND A (commutativity)",
         "A AND B is NOT equivalent to B AND A"),
        ("A >> B", "B >> A", False,
         "A implies B is NOT equivalent to B implies A (converse is different)",
         "A implies B is equivalent to B implies A"),
        ("~(A | B)", "~A & ~B", True,
         "NOT(A OR B) is equivalent to NOT A AND NOT B (De Morgan's law)",
         "NOT(A OR B) is NOT equivalent to NOT A AND NOT B"),
    ]
    for fa, fb, claimed, cl_c, cl_w in equiv_cases:
        items += _pair(
            "formal_logic", f"logic_eq_{fa[:10]}_{fb[:10]}",
            lambda a=fa, b=fb, c=claimed: _logic_equiv(a, b, c),
            lambda a=fa, b=fb, c=not claimed: _logic_equiv(a, b, c),
            cl_c, cl_w,
            {"formula_a": fa, "formula_b": fb, "claimed_equivalent": claimed},
            {"formula_a": fa, "formula_b": fb, "claimed_equivalent": not claimed},
            "equivalence_flipped",
        )

    return items


def build_computer_science():
    items = []

    # CS items: use FUNCTIONAL CORRECTNESS — correct test cases vs wrong expected outputs
    code_bs = """def binary_search(arr, target):
    lo, hi = 0, len(arr)-1
    while lo <= hi:
        mid = (lo+hi)//2
        if arr[mid]==target: return mid
        elif arr[mid]<target: lo=mid+1
        else: hi=mid-1
    return -1"""

    code_factorial = """def factorial(n):
    if n <= 1: return 1
    return n * factorial(n-1)"""

    code_power = """def power(base, exp):
    result = 1
    for _ in range(exp): result *= base
    return result"""

    code_fib = """def fib(n):
    if n <= 1: return n
    a, b = 0, 1
    for _ in range(n-1): a, b = b, a+b
    return b"""

    code_is_prime = """def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0: return False
    return True"""

    code_gcd = """def gcd(a, b):
    while b: a, b = b, a % b
    return a"""

    code_reverse = """def reverse_string(s):
    return s[::-1]"""

    code_sum_list = """def sum_list(lst):
    total = 0
    for x in lst: total += x
    return total"""

    def _t(args_list, expected):
        return {"args": args_list, "expected": expected}

    cs_cases = [
        # (code, fn, correct_tests, wrong_tests, claim_c, claim_w)
        (code_bs, "binary_search",
         [_t([[1,3,5,7,9], 5], 2), _t([[1,3,5,7,9], 1], 0), _t([[2,4,6,8], 3], -1)],
         [_t([[1,3,5,7,9], 5], 3), _t([[1,3,5,7,9], 1], 1)],
         "Binary search correctly finds target index (returns 2 for target=5 in [1,3,5,7,9])",
         "Binary search returns index 3 for target=5 in [1,3,5,7,9] (incorrect, correct is 2)"),
        (code_factorial, "factorial",
         [_t([5], 120), _t([0], 1), _t([6], 720)],
         [_t([5], 60), _t([0], 0)],
         "factorial(5) equals 120 and factorial(0) equals 1",
         "factorial(5) equals 60 (incorrect, correct is 120)"),
        (code_power, "power",
         [_t([2, 10], 1024), _t([3, 3], 27), _t([5, 0], 1)],
         [_t([2, 10], 512), _t([3, 3], 9)],
         "power(2, 10) equals 1024 and power(3, 3) equals 27",
         "power(2, 10) equals 512 (incorrect, correct is 1024)"),
        (code_fib, "fib",
         [_t([0], 0), _t([1], 1), _t([10], 55)],
         [_t([10], 89), _t([0], 1)],
         "fib(10) equals 55 (the 10th Fibonacci number)",
         "fib(10) equals 89 (incorrect, that is fib(11))"),
        (code_is_prime, "is_prime",
         [_t([7], True), _t([4], False), _t([1], False)],
         [_t([7], False), _t([4], True)],
         "is_prime(7) is True and is_prime(4) is False",
         "is_prime(7) is False (incorrect, 7 is prime)"),
        (code_gcd, "gcd",
         [_t([48, 36], 12), _t([100, 25], 25), _t([17, 13], 1)],
         [_t([48, 36], 6), _t([100, 25], 5)],
         "gcd(48, 36) equals 12",
         "gcd(48, 36) equals 6 (incorrect, correct is 12)"),
        (code_reverse, "reverse_string",
         [_t(["hello"], "olleh"), _t(["abc"], "cba")],
         [_t(["hello"], "hello"), _t(["abc"], "abc")],
         "reverse_string('hello') equals 'olleh'",
         "reverse_string('hello') equals 'hello' (incorrect, string is unchanged)"),
        (code_sum_list, "sum_list",
         [_t([[1,2,3,4,5]], 15), _t([[10, -3, 7]], 14)],
         [_t([[1,2,3,4,5]], 14), _t([[10, -3, 7]], 17)],
         "sum_list([1,2,3,4,5]) equals 15",
         "sum_list([1,2,3,4,5]) equals 14 (incorrect, correct is 15)"),
    ]
    for code, fn, tests_c, tests_w, cl_c, cl_w in cs_cases:
        items += _pair(
            "computer_science", f"cs_{fn}",
            lambda c=code, f=fn, t=tests_c: _cs(c, function_name=f, test_cases=t),
            lambda c=code, f=fn, t=tests_w: _cs(c, function_name=f, test_cases=t),
            cl_c, cl_w,
            {"code": code, "function_name": fn, "test_cases": tests_c},
            {"code": code, "function_name": fn, "test_cases": tests_w},
            "wrong_expected_output",
        )
    return items


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    all_items: list[dict] = []

    builders = [
        ("mathematics/equality",      build_mathematics_equality),
        ("mathematics/derivative",     build_mathematics_derivative),
        ("mathematics/solve",          build_mathematics_solve),
        ("chemistry",                  build_chemistry),
        ("physics_conservation",       build_physics_conservation),
        ("physics_dimensional",        build_physics_dimensional),
        ("statistics/ci",              build_statistics_ci),
        ("statistics/multiple_comp",   build_statistics_mc),
        ("formal_logic",               build_formal_logic),
        ("computer_science",           build_computer_science),
    ]

    for label, builder in builders:
        before = len(all_items)
        try:
            items = builder()
            all_items.extend(items)
            n = len(all_items) - before
            n_c = sum(1 for x in items if x["ground_truth"] == "correct")
            n_w = len(items) - n_c
            print(f"  {label:<30} +{n:3d}  (correct={n_c}, incorrect={n_w})")
        except Exception as e:
            import traceback
            print(f"  {label:<30} ERROR: {e}")
            traceback.print_exc()

    # Renumber sequentially
    for i, item in enumerate(all_items, 1):
        item["seq"] = i

    total = len(all_items)
    n_correct = sum(1 for x in all_items if x["ground_truth"] == "correct")
    n_incorrect = total - n_correct

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_items) + "\n", encoding="utf-8")

    elapsed = time.time() - t0
    print(f"\nDataset written to: {OUT}")
    print(f"  Total items  : {total}")
    print(f"  Correct      : {n_correct}")
    print(f"  Incorrect    : {n_incorrect}")
    print(f"  Balance      : {n_correct/total*100:.1f}% correct")
    print(f"  Elapsed      : {elapsed:.1f}s")


if __name__ == "__main__":
    main()
