"""probe_arrangement.py — make the gaps DO the search (honestly).

The supersymmetry placeholder (api/placeholders.py) proposes that the map's
dimensions pair across a symmetry, and it carries its OWN disconfirmers:
  falsifiers:
    F1  a fundamental domain that fits NO dual (an unpaired axis the symmetry
        cannot place);
    F2  a predicted partner (e.g. continuity) that corresponds to no real
        domain (the pairing predicts ghosts);
    F3  a non-symmetric arrangement that explains the structure just as well —
        i.e. the proposed duals are no more complementary than random pairs.
  unlikely_tests:
    U1  hunt the domains that BREAK the pairing;
    U2  test the WEAKEST predicted partner first;
    U3  measure whether the symmetry actually carries explanatory weight.

A placeholder ADVANCES ONLY BY SURVIVING these — never by confirmations. This
tool runs them against the LIVE grid and reports survived / weakened / untestable,
plainly. It is the exploration term of the search made real: spend on refutation,
not self-reinforcement. Re-runnable, pure-compute, no network. Map never launders
— an inconvenient result is reported as found.

    python tools/probe_arrangement.py            # full report
    PYTHONPATH=src python tools/probe_arrangement.py
"""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Tuple

from concordance_engine import grid as _grid

# The arrangement under test (mirrors _AXIS_DUALS / the SUSY placeholder).
DUALS: List[Tuple[str, str]] = [
    ("order", "uncertainty"),
    ("conservation_balance", "metabolism"),
    ("reasoning", "authority_trust"),
]
PREDICTED = {"discreteness": "continuity", "physical_substance": "abstract/spirit"}
UNPAIRED = ["encoding", "time_sequence", "symmetry"]  # no dual proposed


def _canonical() -> Dict[str, frozenset]:
    return {d: _grid.AXIS_DIMENSIONS[d]
            for d in _grid.AXIS_DIMENSIONS if not _grid.is_alias(d)}


def _phi(domains: Dict[str, frozenset], a: str, b: str) -> Dict[str, float]:
    """2x2 co-occurrence of two dimensions across domains + the phi coefficient.
    phi<0 = complementary (tend to NOT co-occur, as true opposites would);
    phi>0 = co-occur more than chance; phi~0 = independent."""
    n11 = n10 = n01 = n00 = 0
    for dims in domains.values():
        ha, hb = a in dims, b in dims
        if ha and hb: n11 += 1
        elif ha and not hb: n10 += 1
        elif hb and not ha: n01 += 1
        else: n00 += 1
    N = n11 + n10 + n01 + n00
    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    phi = ((n11 * n00 - n10 * n01) / denom) if denom else 0.0
    exp_both = ((n11 + n10) * (n11 + n01) / N) if N else 0.0
    return {"both": n11, "a_only": n10, "b_only": n01, "neither": n00,
            "phi": phi, "expected_both": exp_both, "n": N}


def run() -> Dict:
    domains = _canonical()
    dims = [d for d in _grid.DIMENSIONS]
    report: Dict = {"n_domains": len(domains), "n_dimensions": len(dims)}

    # ── U1 / F1: domains that break the pairing ──────────────────────────
    paired = set()
    for a, b in DUALS:
        paired.add(a); paired.add(b)
    paired |= set(PREDICTED.keys())  # the present half of a predicted pair counts as placed
    breakers = sorted(d for d, ds in domains.items() if ds and not (set(ds) & paired))
    report["F1_breakers"] = breakers

    # ── F3 / U3: are the proposed duals more COMPLEMENTARY than random pairs? ──
    # Rank every dimension pair by phi (most complementary = most negative).
    all_pairs = []
    for a, b in itertools.combinations(dims, 2):
        st = _phi(domains, a, b)
        all_pairs.append((a, b, st["phi"], st["both"], st["expected_both"]))
    all_pairs.sort(key=lambda t: t[2])  # most negative (complementary) first
    rank_of = {frozenset((a, b)): i for i, (a, b, *_ ) in enumerate(all_pairs)}
    n_pairs = len(all_pairs)

    dual_results = []
    for a, b in DUALS:
        st = _phi(domains, a, b)
        r = rank_of.get(frozenset((a, b)))
        dual_results.append({
            "pair": f"{a} <-> {b}", "phi": round(st["phi"], 3),
            "both": st["both"], "expected_both": round(st["expected_both"], 2),
            "complementary": st["phi"] < -0.05,
            "rank_by_complementarity": r, "of": n_pairs,
            "percentile": round(100 * (1 - r / max(1, n_pairs - 1)), 0) if r is not None else None,
        })
    report["duals"] = dual_results

    # median phi of all pairs, to judge whether duals are special
    phis = sorted(p[2] for p in all_pairs)
    report["all_pairs_phi_median"] = round(phis[len(phis) // 2], 3)
    report["all_pairs_phi_min"] = round(phis[0], 3)
    report["most_complementary_overall"] = [
        {"pair": f"{a} <-> {b}", "phi": round(ph, 3)} for a, b, ph, *_ in all_pairs[:5]
    ]

    # ── F2 / U2: the predicted-missing partners ──────────────────────────
    # The grid has no 'continuity' or 'abstract' dimension, so we CANNOT confirm a
    # real family carries them — honestly untestable from current data. Report the
    # present half's weight (the weakest predicted partner = test first).
    pred = []
    for present, missing in PREDICTED.items():
        carriers = sorted(d for d, ds in domains.items() if present in ds)
        pred.append({"present_axis": present, "predicted_partner": missing,
                     "present_carriers": len(carriers),
                     "testable_now": False,
                     "note": (f"no '{missing}' dimension exists in the grid; whether a real "
                              f"family of domains carries it is an OPEN prediction, not "
                              f"confirmable from current data. To test: add a candidate "
                              f"'{missing}' axis and see if domains cluster there naturally.")})
    pred.sort(key=lambda p: p["present_carriers"])  # weakest first (U2)
    report["F2_predicted_partners"] = pred

    # ── Verdicts ─────────────────────────────────────────────────────────
    n_complementary = sum(1 for d in dual_results if d["complementary"])
    verdicts = {
        "F1_no_unplaceable_domain": "SURVIVED (weak)" if not breakers
            else f"WEAKENED — {len(breakers)} domain(s) sit only on unpaired axes",
        "F1_note": ("nearly every domain touches reasoning or physical_substance, both "
                    "paired — so 'placed by the symmetry' is close to trivial; treat as weak."),
        "F3_duals_are_complementary":
            f"{n_complementary}/{len(DUALS)} proposed duals are complementary (phi<-0.05)",
        "F3_note": ("if the duals are NOT more complementary than typical pairs, the symmetry "
                    "is decoration, not structure (F3 fires)."),
        "F2_predicted_partners": "UNTESTABLE from current grid (no such dimension) — honest gap.",
    }
    report["verdicts"] = verdicts
    return report


def _fmt(report: Dict) -> str:
    L = []
    L.append("=" * 64)
    L.append("ARRANGEMENT PROBE — running the SUSY placeholder's own disconfirmers")
    L.append(f"{report['n_domains']} canonical domains x {report['n_dimensions']} dimensions")
    L.append("=" * 64)

    L.append("\nU1/F1 — domains that BREAK the pairing (sit only on unpaired axes):")
    if report["F1_breakers"]:
        for d in report["F1_breakers"]:
            L.append(f"   ! {d}")
    else:
        L.append("   none — every domain touches at least one paired axis.")
    L.append(f"   {report['verdicts']['F1_no_unplaceable_domain']}")
    L.append(f"   ({report['verdicts']['F1_note']})")

    L.append("\nF3/U3 — are the proposed duals COMPLEMENTARY (phi<0 = tend not to co-occur)?")
    L.append(f"   median phi over all pairs: {report['all_pairs_phi_median']}  "
             f"(most complementary overall: {report['all_pairs_phi_min']})")
    for d in report["duals"]:
        tag = "complementary" if d["complementary"] else "NOT complementary"
        L.append(f"   {d['pair']:42}  phi={d['phi']:+.3f}  both={d['both']} "
                 f"(exp {d['expected_both']})  rank {d['rank_by_complementarity']}/{d['of']}  [{tag}]")
    L.append("   most complementary pairs in the whole grid:")
    for p in report["most_complementary_overall"]:
        L.append(f"      {p['pair']:42} phi={p['phi']:+.3f}")
    L.append(f"   {report['verdicts']['F3_duals_are_complementary']}")
    L.append(f"   ({report['verdicts']['F3_note']})")

    L.append("\nF2/U2 — predicted-missing partners (weakest first):")
    for p in report["F2_predicted_partners"]:
        L.append(f"   {p['present_axis']} -> {p['predicted_partner']} "
                 f"(present axis carried by {p['present_carriers']} domains)")
        L.append(f"      {p['note']}")
    L.append(f"   {report['verdicts']['F2_predicted_partners']}")

    L.append("\n" + "-" * 64)
    L.append("A placeholder advances only by SURVIVING these. This is evidence to")
    L.append("weigh, never a self-declared confirmation (the apex stays reserved).")
    return "\n".join(L)


if __name__ == "__main__":
    print(_fmt(run()))
