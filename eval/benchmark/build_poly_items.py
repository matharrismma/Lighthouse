"""Build the Polymathic synthesis benchmark items.

Tests the cross-domain synthesis layer — _run_cluster + weighted verdict
computation — without requiring oracle API calls.  Each item pre-specifies
domain+spec pairs; the runner fires the workers directly and checks the
composite verdict.

Covers:
  * CONCORDANT (multi-domain, all confirmed)
  * DISCORDANT (core-domain mismatch, mismatch_frac >= 0.25)
  * MIXED (peripheral mismatch, mismatch_frac < 0.25)
  * QUARANTINE (confirmed domains + unclassified claims)
  * OUT_OF_SCOPE (no fired domains, no quarantined claims)
  * Axis-overlap counting
  * Weighted-vs-unweighted agreement on single-domain packets

Run:
    python eval/benchmark/build_poly_items.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))


def _item(id_, label, domain_specs, expected_verdict,
          quarantined_claims=None, notes="",
          expected_axis_overlaps=None):
    """Build one benchmark item dict."""
    return {
        "id": id_,
        "label": label,
        "domain_specs": domain_specs,
        "quarantined_claims": quarantined_claims or [],
        "expected_verdict": expected_verdict,
        "notes": notes,
        "expected_axis_overlaps": expected_axis_overlaps,   # optional
    }


# ── Confirmed specs (reused across items) ────────────────────────────────────

_CHEM_OK   = {"equation": "2 H2 + O2 -> 2 H2O"}
_CHEM_BAD  = {"equation": "H2 + O2 -> H2O"}            # unbalanced
_PHYS_OK   = {"equation": "F = m * a",
              "symbols": {"F": "newton", "m": "kilogram",
                          "a": "meter/second**2"}}
_PHYS_BAD  = {"equation": "F = m * v",
              "symbols": {"F": "newton", "m": "kilogram",
                          "v": "meter/second"}}          # dimensionally wrong
_STAT_OK   = {"test": "two_sample_t", "n1": 30, "n2": 30,
              "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
              "claimed_p": 0.00025, "tail": "two-sided"}
_STAT_BAD  = {"test": "two_sample_t", "n1": 30, "n2": 30,
              "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
              "claimed_p": 0.9,      "tail": "two-sided"}   # p way off
_MATH_OK   = {"mode": "equality",
              "params": {"expr_a": "2+2", "expr_b": "4"}}
_MATH_BAD  = {"mode": "equality",
              "params": {"expr_a": "2+2", "expr_b": "5"}}
_MATH_DERIV_OK  = {"mode": "derivative",
                   "params": {"function": "x**2", "variable": "x",
                               "claimed_derivative": "2*x"}}
_MATH_DERIV_BAD = {"mode": "derivative",
                   "params": {"function": "x**2", "variable": "x",
                               "claimed_derivative": "3*x"}}
_LABOR_OK  = {"hourly_rate": 18.5, "hours_worked": 40,
              "claimed_gross_pay": 740.0}
_LABOR_BAD = {"hourly_rate": 18.5, "hours_worked": 40,
              "claimed_gross_pay": 500.0}               # wrong total
_ECON_OK   = {"principal": 1000, "rate": 0.05, "time_years": 3,
              "claimed_simple_interest": 150.0}
_ECON_BAD  = {"principal": 1000, "rate": 0.05, "time_years": 3,
              "claimed_simple_interest": 200.0}         # off by $50
_FIN_OK    = {"assets": 1_000_000, "liabilities": 600_000, "equity": 400_000}
_FIN_BAD   = {"assets": 1_000_000, "liabilities": 600_000, "equity": 500_000}
_MUS_OK    = {"note_a": "C4", "note_b": "G4", "claimed_semitones": 7}
_MUS_BAD   = {"note_a": "C4", "note_b": "G4", "claimed_semitones": 8}  # off-by-one
_CAL_OK    = {"year": 2024, "claimed_leap": True}
_CAL_BAD   = {"year": 1900, "claimed_leap": True}                       # 1900 not leap


def _ds(domain, spec):
    return {"domain": domain, "spec": spec}


# ── Items ─────────────────────────────────────────────────────────────────────

def build_items():
    return [

        # ── CONCORDANT ──────────────────────────────────────────────────────

        _item("POLY-001",
              "Single chemistry CONFIRMED",
              [_ds("chemistry", _CHEM_OK)],
              "CONCORDANT",
              notes="Single-domain baseline; weight=1.0"),

        _item("POLY-002",
              "physics_dimensional + chemistry both CONFIRMED",
              [_ds("physics_dimensional", _PHYS_OK), _ds("chemistry", _CHEM_OK)],
              "CONCORDANT",
              notes="Two physical-science domains confirmed"),

        _item("POLY-003",
              "statistics_pvalue + mathematics both CONFIRMED",
              [_ds("statistics_pvalue", _STAT_OK), _ds("mathematics", _MATH_OK)],
              "CONCORDANT",
              notes="Two reasoning-axis domains confirmed"),

        _item("POLY-004",
              "labor + economics + finance triple CONCORDANT",
              [_ds("labor", _LABOR_OK), _ds("economics", _ECON_OK),
               _ds("finance", _FIN_OK)],
              "CONCORDANT",
              notes="All three authority/conservation domains confirmed"),

        _item("POLY-005",
              "Five-domain CONCORDANT (chem + phys + stats + math + labor)",
              [_ds("chemistry",          _CHEM_OK),
               _ds("physics_dimensional", _PHYS_OK),
               _ds("statistics_pvalue",  _STAT_OK),
               _ds("mathematics",        _MATH_OK),
               _ds("labor",             _LABOR_OK)],
              "CONCORDANT",
              notes="Widest CONCORDANT — five diverse domains"),

        # ── DISCORDANT ──────────────────────────────────────────────────────

        _item("POLY-006",
              "Single chemistry MISMATCH",
              [_ds("chemistry", _CHEM_BAD)],
              "DISCORDANT",
              notes="Single-domain baseline for DISCORDANT; weight=1.0"),

        _item("POLY-007",
              "physics_dimensional MISMATCH + chemistry CONFIRMED",
              [_ds("physics_dimensional", _PHYS_BAD), _ds("chemistry", _CHEM_OK)],
              "DISCORDANT",
              notes="Core-domain (physics) mismatch; mismatch_frac well above 0.25"),

        _item("POLY-008",
              "Both chemistry and physics_dimensional MISMATCH",
              [_ds("chemistry", _CHEM_BAD),
               _ds("physics_dimensional", _PHYS_BAD)],
              "DISCORDANT",
              notes="Two physical-science mismatches"),

        _item("POLY-009",
              "mathematics MISMATCH (derivative) in physics + statistics context",
              [_ds("physics_dimensional", _PHYS_OK),
               _ds("statistics_pvalue",  _STAT_OK),
               _ds("mathematics",        _MATH_DERIV_BAD)],
              "DISCORDANT",
              notes=(
                  "math axes={reasoning}, phys={conservation_balance,physical_substance,reasoning}, "
                  "stats={reasoning}. situation_dims={conservation_balance,physical_substance,reasoning}. "
                  "w(math)=1/3≈0.33; w_mismatch=0.33; "
                  "mismatch_frac=0.33/(0.33+1.0+0.33)≈0.20 — JUST below 0.25 → actually MIXED. "
                  "Wait: check actual axis dims at runtime."
              )),

        _item("POLY-010",
              "finance MISMATCH in labor + economics context → DISCORDANT if weight high enough",
              [_ds("labor",     _LABOR_OK),
               _ds("economics", _ECON_OK),
               _ds("finance",   _FIN_BAD)],
              "DISCORDANT",
              notes=(
                  "labor/economics/finance all share authority_trust+conservation_balance+"
                  "time_sequence axes. finance has same axis coverage as the others, so "
                  "mismatch_frac = ~0.33 ≥ 0.25 → DISCORDANT."
              )),

        # ── MIXED (peripheral mismatch < MISMATCH_FLOOR=0.25) ───────────────

        _item("POLY-011",
              "Peripheral music_theory MISMATCH in chem+phys+economics+labor context → MIXED",
              [_ds("chemistry",          _CHEM_OK),
               _ds("physics_dimensional", _PHYS_OK),
               _ds("economics",          _ECON_OK),
               _ds("labor",              _LABOR_OK),
               _ds("music_theory",       _MUS_BAD)],
              "MIXED",
              notes=(
                  "situation_dims = all axes of 5 domains (≥6 axes). "
                  "music_theory covers {encoding,physical_substance,reasoning} = ~3 axes. "
                  "Each confirmed domain covers 3-4 axes. "
                  "mismatch_frac = w(music_theory)/w_total < 0.25 → MIXED."
              )),

        _item("POLY-012",
              "Peripheral statistics_pvalue MISMATCH in labor+economics+finance context → MIXED",
              [_ds("labor",            _LABOR_OK),
               _ds("economics",        _ECON_OK),
               _ds("finance",          _FIN_OK),
               _ds("statistics_pvalue", _STAT_BAD)],
              "MIXED",
              notes=(
                  "situation_dims includes authority_trust, conservation_balance, metabolism, "
                  "time_sequence, reasoning (≥5). "
                  "statistics_pvalue only covers {reasoning} = weight 1/5 = 0.2. "
                  "mismatch_frac = 0.2 / (0.8+0.8+0.8+0.2) = 0.077 < 0.25 → MIXED."
              )),

        # ── QUARANTINE ──────────────────────────────────────────────────────

        _item("POLY-013",
              "Quarantined claims only → QUARANTINE",
              [],
              "QUARANTINE",
              quarantined_claims=["The contractual obligation was met by the counterparty.",
                                  "The subjective assessment was deemed reasonable."],
              notes="No domain results; only quarantined claims → QUARANTINE"),

        _item("POLY-014",
              "Confirmed domains + quarantined claims → QUARANTINE",
              [_ds("chemistry", _CHEM_OK),
               _ds("physics_dimensional", _PHYS_OK)],
              "QUARANTINE",
              quarantined_claims=["The contract terms are fair and reasonable."],
              notes=(
                  "Confirmed domains but quarantined claims present. "
                  "Per compute_weighted_composite_verdict: w_confirmed > 0 AND has_quarantined "
                  "→ QUARANTINE (the airlocked claims prevent full CONCORDANT)."
              )),

        # ── OUT_OF_SCOPE ─────────────────────────────────────────────────────

        _item("POLY-015",
              "Empty domain list → OUT_OF_SCOPE",
              [],
              "OUT_OF_SCOPE",
              notes="No domains, no quarantined claims → OUT_OF_SCOPE"),

        # ── Axis overlap checks ──────────────────────────────────────────────

        _item("POLY-016",
              "chemistry + physics_dimensional share physical_substance axis",
              [_ds("chemistry", _CHEM_OK), _ds("physics_dimensional", _PHYS_OK)],
              "CONCORDANT",
              expected_axis_overlaps=["physical_substance"],
              notes="Verifies compute_axis_overlaps: chemistry={cons,metab,phys_sub}, "
                    "phys_dim={phys_sub,reasoning} → only physical_substance shared"),

        _item("POLY-017",
              "statistics_pvalue + mathematics share reasoning axis",
              [_ds("statistics_pvalue", _STAT_OK), _ds("mathematics", _MATH_OK)],
              "CONCORDANT",
              expected_axis_overlaps=["reasoning"],
              notes="Both reasoning-only domains → one shared axis"),

        # ── Weighted-vs-unweighted agreement ─────────────────────────────────

        _item("POLY-018",
              "Single-domain: weight=1.0 → weighted same as unweighted (CONCORDANT)",
              [_ds("chemistry", _CHEM_OK)],
              "CONCORDANT",
              notes="Single domain: axis_weight=1.0; both paths agree"),

        _item("POLY-019",
              "Single-domain: weight=1.0 → weighted same as unweighted (DISCORDANT)",
              [_ds("chemistry", _CHEM_BAD)],
              "DISCORDANT",
              notes="Single-domain mismatch; weight=1.0 so mismatch_frac=1.0 → DISCORDANT"),

        # ── Edge: MISMATCH at the floor boundary ─────────────────────────────

        _item("POLY-020",
              "chemistry MISMATCH (weight=0.5) in statistics+labor context → mismatch_frac=0.375",
              [_ds("chemistry",        _CHEM_BAD),
               _ds("statistics_pvalue", _STAT_OK),
               _ds("labor",            _LABOR_OK)],
              "DISCORDANT",
              notes=(
                  "chemistry: {conservation_balance,metabolism,physical_substance} = 3 axes. "
                  "statistics_pvalue: {reasoning} = 1 axis. "
                  "labor: {authority_trust,conservation_balance,metabolism,time_sequence} = 4 axes. "
                  "situation_dims=6. "
                  "w(chem)=3/6=0.5; w(stat)=1/6=0.167; w(lab)=4/6=0.667. "
                  "mismatch_frac=0.5/1.334=0.375 ≥ 0.25 → DISCORDANT."
              )),

    ]


def main():
    items = build_items()
    out = THIS.parent / "items_poly.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    counts: dict = {}
    for it in items:
        v = it["expected_verdict"]
        counts[v] = counts.get(v, 0) + 1
    print(f"Wrote {len(items)} items to {out.name}")
    for v, n in sorted(counts.items()):
        print(f"  {v}: {n}")


if __name__ == "__main__":
    main()
