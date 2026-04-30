"""Generate the benchmark items file (eval/benchmark/items.jsonl).

Each item has:
  id            unique string
  domain        chemistry | statistics | physics
  task          short task type tag
  prompt        the natural-language question to ask the model
  ground_truth  the correct answer (parser-readable)
  answer_kind   'classification' | 'numeric' | 'string' — how to score
  tolerance     for numeric, the allowed |error|

All items are deterministic and reproducible: the ground truth is computed at
build time, not curated. Re-running this script produces identical items.

Run:  python eval/benchmark/build_items.py
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

# Use the verifier code itself to compute ground truth where applicable.
from concordance_engine.verifiers import chemistry as chem  # noqa: E402
from scipy import stats as scistats  # noqa: E402


# ---------------------------------------------------------------------
# Chemistry: balanced-equation classification + balancing coefficients
# ---------------------------------------------------------------------

CHEM_EQUATIONS = [
    "2 H2 + O2 -> 2 H2O",
    "H2 + O2 -> H2O",
    "C3H8 + 5 O2 -> 3 CO2 + 4 H2O",
    "C2H6 + O2 -> CO2 + H2O",
    "C8H18 + 25 O2 -> 16 CO2 + 18 H2O",
    "2 C8H18 + 25 O2 -> 16 CO2 + 18 H2O",
    "Fe + O2 -> Fe2O3",
    "Al + Cl2 -> AlCl3",
    "KClO3 -> KCl + O2",
    "2 KClO3 -> 2 KCl + 3 O2",
    "N2 + 3 H2 -> 2 NH3",
    "Cu + 2 AgNO3 -> Cu(NO3)2 + 2 Ag",
    "CaCO3 -> CaO + CO2",
    "Na + H2O -> NaOH + H2",
    "Mg + HCl -> MgCl2 + H2",
    "P4 + O2 -> P2O5",
    "2 H2O2 -> 2 H2O + O2",
]


def build_chemistry():
    """Engine is the ground truth: every label comes from chem.verify_equation."""
    items = []
    for i, eq in enumerate(CHEM_EQUATIONS, start=1):
        engine_result = chem.verify_equation(eq, balance_if_unbalanced=False)
        balanced = engine_result.status == "CONFIRMED"
        items.append({
            "id": f"CHEM-{i:03d}",
            "domain": "chemistry",
            "task": "is_balanced",
            "prompt": (
                f"Is the chemical equation `{eq}` balanced? "
                f"Answer with exactly one word: yes or no."
            ),
            "ground_truth": "yes" if balanced else "no",
            "answer_kind": "classification",
        })
    return items


# ---------------------------------------------------------------------
# Statistics: recompute p-values
# ---------------------------------------------------------------------

def two_sample_t_p(n1, n2, m1, m2, s1, s2):
    se = math.sqrt(s1 ** 2 / n1 + s2 ** 2 / n2)
    t = (m1 - m2) / se
    df = (s1 ** 2 / n1 + s2 ** 2 / n2) ** 2 / (
        (s1 ** 2 / n1) ** 2 / (n1 - 1) + (s2 ** 2 / n2) ** 2 / (n2 - 1)
    )
    return 2 * scistats.t.sf(abs(t), df)


def paired_t_p(n, mean_diff, sd_diff):
    t = mean_diff / (sd_diff / math.sqrt(n))
    return 2 * scistats.t.sf(abs(t), n - 1)


def one_proportion_z_p(n, x, p0):
    phat = x / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (phat - p0) / se
    return 2 * scistats.norm.sf(abs(z))


def fisher_p(table):
    res = scistats.fisher_exact(table, alternative="two-sided")
    return float(res.pvalue) if hasattr(res, "pvalue") else float(res[1])


STAT_SCENARIOS = [
    ("two_sample_t", "n1=30, n2=30, mean1=5.0, mean2=4.0, sd1=1.0, sd2=1.0",
     two_sample_t_p, (30, 30, 5.0, 4.0, 1.0, 1.0)),
    ("two_sample_t", "n1=50, n2=50, mean1=10.0, mean2=10.5, sd1=2.0, sd2=2.0",
     two_sample_t_p, (50, 50, 10.0, 10.5, 2.0, 2.0)),
    ("two_sample_t", "n1=20, n2=20, mean1=100, mean2=98, sd1=5, sd2=5",
     two_sample_t_p, (20, 20, 100, 98, 5, 5)),
    ("paired_t", "n=20 paired observations, mean_diff=0.5, sd_diff=1.0",
     paired_t_p, (20, 0.5, 1.0)),
    ("paired_t", "n=40 paired observations, mean_diff=0.2, sd_diff=1.0",
     paired_t_p, (40, 0.2, 1.0)),
    ("paired_t", "n=15 paired observations, mean_diff=2.0, sd_diff=3.0",
     paired_t_p, (15, 2.0, 3.0)),
    ("one_proportion_z", "n=200 trials, 110 successes, null p0=0.5",
     one_proportion_z_p, (200, 110, 0.5)),
    ("one_proportion_z", "n=500 trials, 280 successes, null p0=0.5",
     one_proportion_z_p, (500, 280, 0.5)),
    ("fisher_exact", "2x2 contingency table [[8,2],[1,5]]",
     fisher_p, ([[8, 2], [1, 5]],)),
    ("fisher_exact", "2x2 contingency table [[12,7],[6,15]]",
     fisher_p, ([[12, 7], [6, 15]],)),
]


def build_statistics():
    items = []
    for i, (test_kind, scenario_text, fn, args) in enumerate(STAT_SCENARIOS, start=1):
        p = float(fn(*args))
        items.append({
            "id": f"STAT-{i:03d}",
            "domain": "statistics",
            "task": "two_tailed_pvalue",
            "test_kind": test_kind,
            "prompt": (
                f"Compute the two-tailed p-value for a {test_kind.replace('_', ' ')} "
                f"with the following inputs: {scenario_text}. "
                f"Reply with only the p-value as a decimal number (e.g. 0.0123). "
                f"Round to four significant figures."
            ),
            "ground_truth": p,
            "answer_kind": "numeric",
            # Allow 5% relative tolerance; LLMs round differently than scipy.
            "tolerance": 0.05,
        })
    return items


# ---------------------------------------------------------------------
# Physics: dimensional consistency yes/no
# ---------------------------------------------------------------------

PHYS_ITEMS_RAW = [
    # (equation, symbols-with-units, dimensionally-consistent?)
    ("F = m * a", {"F": "newton", "m": "kilogram", "a": "meter/second**2"}, True),
    ("F = m * v", {"F": "newton", "m": "kilogram", "v": "meter/second"}, False),
    ("E = m * c**2", {"E": "joule", "m": "kilogram", "c": "meter/second"}, True),
    ("KE = 0.5 * m * v**2", {"KE": "joule", "m": "kilogram", "v": "meter/second"}, True),
    ("p = m * v", {"p": "kilogram*meter/second", "m": "kilogram", "v": "meter/second"}, True),
    ("V = I * R", {"V": "volt", "I": "ampere", "R": "ohm"}, True),
    ("v = u + a * t", {"v": "meter/second", "u": "meter/second", "a": "meter/second**2", "t": "second"}, True),
    ("s = u * t**2", {"s": "meter", "u": "meter/second", "t": "second"}, False),
    ("P = F * v", {"P": "watt", "F": "newton", "v": "meter/second"}, True),
    ("F = q * E", {"F": "newton", "q": "coulomb", "E": "volt/meter"}, True),
]


def build_physics():
    items = []
    for i, (eq, symbols, ok) in enumerate(PHYS_ITEMS_RAW, start=1):
        # Render the symbols dict into prompt text
        sym_text = ", ".join(f"{k} in {v.replace('**', '^').replace('*', '·')}"
                              for k, v in symbols.items())
        items.append({
            "id": f"PHYS-{i:03d}",
            "domain": "physics",
            "task": "dimensional_consistency",
            "prompt": (
                f"Is the equation `{eq}` dimensionally consistent in SI units, given "
                f"{sym_text}? Answer with exactly one word: yes or no."
            ),
            "ground_truth": "yes" if ok else "no",
            "answer_kind": "classification",
            # Stash the structured form for the with-tools mode
            "structured_args": {"equation": eq, "symbols": symbols},
        })
    return items


def main():
    items = build_chemistry() + build_statistics() + build_physics()
    out = THIS.parent / "items.jsonl"
    with out.open("w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    counts = {}
    for it in items:
        counts[it["domain"]] = counts.get(it["domain"], 0) + 1
    print(f"Wrote {len(items)} items to {out}")
    for d, n in sorted(counts.items()):
        print(f"  {d}: {n}")


if __name__ == "__main__":
    main()
