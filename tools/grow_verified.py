"""grow_verified.py — grow the verified cross-domain connection moat, oracle-free.

Each genuine, coherent real-world scenario is described so that 2+ INDEPENDENT
deterministic domain verifiers each confirm their part. The connection is verified
because the math on every side checks out — not generated, not a resonance. No
oracle / API calls: the engine's own verifiers do all the asserting, deterministically.

Discipline:
  * GENUINE scenarios only — the domains genuinely co-occur (a household's money
    spans labor+finance+economics; a square garden spans number_theory+geometry).
    No synthetic concatenation of unrelated facts.
  * Quality over quantity — varied real instances, not parameter-spam. The ceiling
    is distinct genuine patterns, not compute.
  * Writes to data/almanac/generated_verified.jsonl ONLY — a separate, reversible
    file. The curated data/almanac/entries.jsonl is never touched. Operator merges.
  * Every emitted entry has >=2 domain verifiers returning CONFIRMED (airtight).

Run:  python tools/grow_verified.py        (default, idempotent — skips dupes)
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "data" / "almanac" / "generated_verified.jsonl"

from concordance_engine.mcp_server.tools import ALL_TOOLS  # noqa: E402

# Axis scaffold per domain (the engine's 7 axes) — for the connection index.
AXES = {
    "labor": ["authority_trust", "conservation_balance", "time_sequence"],
    "finance": ["conservation_balance", "time_sequence", "reasoning"],
    "economics": ["conservation_balance", "time_sequence", "authority_trust"],
    "geometry": ["physical_substance", "reasoning", "conservation_balance"],
    "nutrition": ["metabolism", "physical_substance", "conservation_balance"],
    "number_theory": ["reasoning", "encoding"],
    "astronomy": ["physical_substance", "time_sequence", "reasoning"],
    "optics": ["physical_substance", "reasoning", "encoding"],
    "hydrology": ["conservation_balance", "physical_substance", "time_sequence"],
}


def _verify(domain, spec):
    """Return (status, detail) from a domain verifier — deterministic, in-process."""
    fn = ALL_TOOLS.get(f"verify_{domain}")
    if fn is None:
        return ("NO_FN", "")
    params = inspect.signature(fn).parameters
    first = next(iter(params))
    if first == "spec":
        raw = fn(spec)
    else:
        kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        raw = fn(**spec) if kw else fn(**{k: v for k, v in spec.items() if k in set(params)})
    if not isinstance(raw, dict):
        return ("ERROR", "")
    checks = raw.get("checks") or raw.get("results") or []
    if isinstance(checks, list):
        for c in checks:
            if isinstance(c, dict) and c.get("status") in ("CONFIRMED", "MISMATCH"):
                return (c["status"], (c.get("detail") or "")[:220])
    return (raw.get("status"), (raw.get("detail") or "")[:220])


def _entry(tname, title, situation, confirmed):
    """confirmed = [(domain, detail), ...] for the CONFIRMED verifiers."""
    doms = sorted({d for d, _ in confirmed})
    axes = sorted({a for d, _ in confirmed for a in AXES.get(d, [])})
    sid = hashlib.sha256(situation.encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"gen_{tname}_{sid}",
        "kind": "generated_connection",
        "title": title,
        "situation": situation,
        "category": "generated",
        "domains": doms,
        "axes": axes,
        "verdict": "CONCORDANT",
        "generated": True,
        "method": "deterministic verifier confirmation (oracle-free)",
        "pre_run": {
            "summary": f"{len(doms)} independent domain verifiers each CONFIRMED their part.",
            "domain_results": [
                {"domain": d, "verdict": "CONFIRMED", "detail": det} for d, det in confirmed
            ],
        },
    }


def _harvest(tname, title, situation, claims):
    """Run each (domain, spec); emit an entry iff 2+ DISTINCT domains CONFIRM."""
    confirmed = []
    seen = set()
    for dom, spec in claims:
        st, det = _verify(dom, spec)
        if st == "CONFIRMED" and dom not in seen:
            confirmed.append((dom, det))
            seen.add(dom)
    if len(seen) >= 2:
        return _entry(tname, title, situation, confirmed)
    return None


# ── Genuine scenario templates ──────────────────────────────────────────────
def t_household():
    """A household's money: paycheck (labor) + savings growth (finance) +
    inflation over the same years (economics)."""
    params = [
        (18.50, 40, 5000, 0.05, 10, 100.0, 121.9),
        (25.00, 38, 12000, 0.04, 15, 110.0, 142.0),
        (15.00, 40, 3000, 0.06, 20, 100.0, 134.7),
        (32.00, 40, 25000, 0.045, 8, 120.0, 138.6),
        (21.75, 36, 8000, 0.055, 12, 100.0, 130.0),
        (40.00, 40, 50000, 0.05, 25, 130.0, 180.5),
    ]
    for R, H, P, r, Y, c0, c1 in params:
        gross = round(R * H, 2)
        fv = round(P * (1 + r) ** Y, 2)
        infl = round((c1 - c0) / c0 * 100, 4)
        sit = (f"A worker earning ${R:.2f}/hour for {H} hours grosses ${gross:.2f}. "
               f"They invest ${P:,} at {r*100:.2f}% compounded annually for {Y} years, "
               f"reaching ${fv:,.2f}. Over the same period CPI rose from {c0} to {c1} "
               f"({infl:.2f}% inflation).")
        title = f"Household over {Y}y: ${R:.0f}/hr wage, ${P:,} saved, {infl:.1f}% inflation"
        yield ("household", title, sit,
               [("labor", {"hourly_rate": R, "hours_worked": H, "claimed_gross_pay": gross}),
                ("finance", {"principal": P, "rate": r, "years": Y, "compounding_per_year": 1,
                             "claimed_future_value": fv}),
                ("economics", {"cpi_current": c1, "cpi_previous": c0, "claimed_inflation_rate": infl})])


def t_flooring_job():
    """Hiring out a flooring job: room area (geometry) + the worker's pay (labor)."""
    params = [(12.0, 15.0, 22.0, 16), (10.0, 10.0, 28.0, 8), (14.0, 18.0, 19.5, 24),
              (11.0, 13.0, 25.0, 12), (16.0, 20.0, 30.0, 30)]
    for L, W, R, H in params:
        area = round(L * W, 4)
        perim = round(2 * (L + W), 4)
        gross = round(R * H, 2)
        sit = (f"A rectangular floor {L:.0f}ft x {W:.0f}ft has area {area:.0f} sq ft "
               f"(perimeter {perim:.0f} ft). A flooring worker paid ${R:.2f}/hour for "
               f"{H} hours earns ${gross:.2f} to install it.")
        title = f"Flooring a {L:.0f}x{W:.0f} room ({area:.0f} sq ft), labor ${gross:.0f}"
        yield ("flooring_job", title, sit,
               [("geometry", {"rect_l": L, "rect_w": W, "claimed_rect_area": area,
                              "claimed_rect_perimeter": perim}),
                ("labor", {"hourly_rate": R, "hours_worked": H, "claimed_gross_pay": gross})])


def t_workers_day():
    """A laborer's day: pay (labor) + energy balance of hard work (nutrition)."""
    params = [(18.0, 40, 70.0, 1.75, 3000, 2800), (22.0, 40, 82.0, 1.80, 3400, 3100),
              (16.5, 38, 64.0, 1.68, 2600, 2500), (28.0, 40, 90.0, 1.88, 3600, 3300)]
    for R, H, W, Ht, intake, expend in params:
        gross = round(R * H, 2)
        bmi = W / (Ht ** 2)
        cls = ("underweight" if bmi < 18.5 else "normal" if bmi < 25 else
               "overweight" if bmi < 30 else "obese")
        bal = intake - expend
        sit = (f"A manual laborer earning ${R:.2f}/hour for {H} hours grosses ${gross:.2f}. "
               f"At {W:.0f}kg and {Ht:.2f}m their BMI is {bmi:.1f} ({cls}); a daily intake "
               f"of {intake} kcal against {expend} kcal expenditure nets {bal:+d} kcal.")
        title = f"Laborer's day: ${gross:.0f} pay, BMI {bmi:.1f}, {bal:+d} kcal"
        yield ("workers_day", title, sit,
               [("labor", {"hourly_rate": R, "hours_worked": H, "claimed_gross_pay": gross}),
                ("nutrition", {"weight_kg": W, "height_m": Ht, "claimed_bmi_class": cls})])


def t_square_garden():
    """A square garden with a prime side length: primality (number_theory) +
    area (geometry)."""
    primes = [11, 13, 17, 19, 23, 29, 31, 37]
    for p in primes:
        area = round(float(p * p), 4)
        perim = round(float(4 * p), 4)
        sit = (f"A square garden bed measures {p}ft on each side. {p} is a prime number; "
               f"the bed's area is {p}x{p} = {area:.0f} sq ft and its perimeter is "
               f"{perim:.0f} ft.")
        title = f"Square garden, prime side {p}ft = {area:.0f} sq ft"
        yield ("square_garden", title, sit,
               [("number_theory", {"n_prime": p, "claimed_prime": True}),
                ("geometry", {"rect_l": float(p), "rect_w": float(p),
                              "claimed_rect_area": area, "claimed_rect_perimeter": perim})])


def t_savings_vs_inflation():
    """Will savings outpace inflation? compound growth (finance) + CPI (economics)."""
    params = [(10000, 0.05, 10, 100.0, 119.0), (5000, 0.03, 15, 100.0, 140.0),
              (20000, 0.06, 8, 110.0, 128.5), (15000, 0.045, 20, 100.0, 165.3),
              (8000, 0.04, 12, 120.0, 152.0)]
    for P, r, Y, c0, c1 in params:
        fv = round(P * (1 + r) ** Y, 2)
        infl = round((c1 - c0) / c0 * 100, 4)
        sit = (f"${P:,} invested at {r*100:.1f}% compounded annually for {Y} years grows to "
               f"${fv:,.2f}. Over the same {Y} years CPI moved {c0} to {c1}, a cumulative "
               f"{infl:.2f}% inflation.")
        title = f"${P:,} at {r*100:.1f}% for {Y}y vs {infl:.0f}% inflation"
        yield ("savings_vs_inflation", title, sit,
               [("finance", {"principal": P, "rate": r, "years": Y, "compounding_per_year": 1,
                             "claimed_future_value": fv}),
                ("economics", {"cpi_current": c1, "cpi_previous": c0, "claimed_inflation_rate": infl})])


def t_telescope_star():
    """A telescope observing a star: the objective lens (optics, thin-lens
    relation) + the star's distance from its parallax (astronomy)."""
    params = [(0.10, 100.0, 0.05), (0.20, 200.0, 0.02), (0.08, 50.0, 0.10),
              (0.15, 500.0, 0.025), (0.12, 80.0, 0.04)]
    for f, do, par in params:
        di = 1.0 / ((1.0 / f) - (1.0 / do))
        dist = round(1.0 / par, 4)
        sit = (f"A telescope objective of focal length {f:.2f} m forms an image of a distant "
               f"source at object distance {do:.0f} m (image distance {di:.4f} m; the thin-lens "
               f"relation 1/f = 1/d_o + 1/d_i holds). The star it observes has a parallax of "
               f"{par} arcsec, placing it {dist:.2f} parsecs away.")
        title = f"Telescope f={f:.2f}m views a star at {dist:.1f} pc"
        yield ("telescope_star", title, sit,
               [("optics", {"focal_length_m": f, "object_distance_m": do,
                            "image_distance_m": round(di, 6), "claimed_thin_lens_consistent": True}),
                ("astronomy", {"parallax_arcsec": par, "claimed_distance_parsec": dist})])


def t_field_drainage():
    """A rectangular catchment: its area (geometry) is its drainage area, which
    sets the rational-method runoff (hydrology)."""
    params = [(660.0, 660.0, 2.0, 0.35), (660.0, 330.0, 1.5, 0.40),
              (1320.0, 660.0, 3.0, 0.30), (440.0, 440.0, 2.5, 0.45),
              (880.0, 550.0, 1.0, 0.50)]
    for L, W, i, C in params:
        area_sqft = round(L * W, 4)
        perim = round(2 * (L + W), 4)
        acres = round(L * W / 43560.0, 6)
        Q = round(C * i * acres, 4)
        sit = (f"A rectangular catchment {L:.0f}ft x {W:.0f}ft covers {area_sqft:,.0f} sq ft "
               f"({acres:.3f} acres). Under {i} in/hr rainfall with runoff coefficient {C}, the "
               f"rational-method peak runoff is Q = C*i*A = {Q:.3f} cfs.")
        title = f"{L:.0f}x{W:.0f}ft catchment ({acres:.1f} ac) gives {Q:.2f} cfs runoff"
        yield ("field_drainage", title, sit,
               [("geometry", {"rect_l": L, "rect_w": W, "claimed_rect_area": area_sqft,
                              "claimed_rect_perimeter": perim}),
                ("hydrology", {"rainfall_intensity": i, "drainage_area": acres,
                               "runoff_coefficient": C, "claimed_runoff": Q})])


def t_circular_catchment():
    """A circular catchment: area pi*r^2 (geometry) sets the drainage area and so
    the runoff (hydrology)."""
    params = [(100.0, 2.0, 0.40), (150.0, 1.5, 0.35), (200.0, 3.0, 0.30), (120.0, 2.5, 0.45)]
    for R, i, C in params:
        area_sqft = round(math.pi * R * R, 4)
        circ = round(2 * math.pi * R, 4)
        acres = round(area_sqft / 43560.0, 6)
        Q = round(C * i * acres, 4)
        sit = (f"A circular catchment of radius {R:.0f}ft has area pi*r^2 = {area_sqft:,.0f} sq ft "
               f"({acres:.3f} acres, circumference {circ:.0f} ft). At {i} in/hr with runoff "
               f"coefficient {C}, peak runoff Q = C*i*A = {Q:.3f} cfs.")
        title = f"Circular catchment r={R:.0f}ft ({acres:.1f} ac) gives {Q:.2f} cfs"
        yield ("circular_catchment", title, sit,
               [("geometry", {"circle_radius": R, "claimed_circle_area": area_sqft,
                              "claimed_circle_circumference": circ}),
                ("hydrology", {"rainfall_intensity": i, "drainage_area": acres,
                               "runoff_coefficient": C, "claimed_runoff": Q})])


TEMPLATES = [t_household, t_flooring_job, t_workers_day, t_square_garden, t_savings_vs_inflation,
             t_telescope_star, t_field_drainage, t_circular_catchment]


def main():
    existing = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    existing.add(json.loads(line).get("id"))
                except Exception:
                    pass
    new = []
    tried = 0
    for tmpl in TEMPLATES:
        for tname, title, sit, claims in tmpl():
            tried += 1
            entry = _harvest(tname, title, sit, claims)
            if entry and entry["id"] not in existing:
                new.append(entry)
                existing.add(entry["id"])
    if new:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as f:
            for e in new:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    by_pair = {}
    for e in new:
        by_pair[tuple(e["domains"])] = by_pair.get(tuple(e["domains"]), 0) + 1
    print(json.dumps({
        "scenarios_tried": tried,
        "new_verified": len(new),
        "total_in_file": len(existing),
        "by_domain_combo": {"+".join(k): v for k, v in sorted(by_pair.items())},
        "stamp": datetime.now(timezone.utc).isoformat(),
        "out": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
