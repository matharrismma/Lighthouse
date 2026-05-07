"""Comparative analysis: Polymathic engine vs Claude alone on synthesis.

Three modes are scored against the same 20 poly items:

  engine   — deterministic synthesis (_run_cluster + weighted verdict)
             This is the ground truth: 20/20 by construction.

  alone    — Claude asked to synthesise a verdict from a natural-language
             description of the situation; no verifier tools available.

  poly     — run_polymathic() with the full oracle pipeline (decompose →
             classify → verify → synthesise). Costs N oracle API calls per
             item; gated by --poly flag so it's opt-in.

Scoring
-------
Ground truth is items_poly.jsonl expected_verdict.  Each run is scored
independently.  A delta table shows which items changed between modes.

Usage:
    # Engine + alone only (no API calls needed beyond alone run):
    python eval/benchmark/run_poly_comparative.py

    # Include full oracle pipeline (costs ~100 API calls):
    python eval/benchmark/run_poly_comparative.py --poly

    # Use Sonnet for the alone run:
    python eval/benchmark/run_poly_comparative.py --model claude-sonnet-4-6

    # Skip alone run (engine only, deterministic, no API needed):
    python eval/benchmark/run_poly_comparative.py --engine-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

ITEMS_PATH = THIS.parent / "items_poly.jsonl"

# Load env
_env = REPO / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8", errors="replace").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            k, v = _line.split("=", 1)
            _k, _v = k.strip(), v.strip()
            if _k not in os.environ or not os.environ[_k]:
                os.environ[_k] = _v


# ── Natural-language situation generation ─────────────────────────────────────

def _spec_to_sentence(domain: str, spec: dict) -> str:
    """Convert one domain+spec to a human-readable factual claim."""
    if domain == "chemistry":
        eq = spec.get("equation", "?")
        return f"The chemical equation {eq} is balanced."

    if domain == "physics_dimensional":
        eq = spec.get("equation", "?")
        syms = spec.get("symbols", {})
        sym_str = ", ".join(f"{k} in {v}" for k, v in syms.items())
        return f"The equation {eq} is dimensionally consistent ({sym_str})."

    if domain == "physics_conservation":
        before = spec.get("before", {})
        after = spec.get("after", {})
        return f"Conservation holds between {before} and {after}."

    if domain == "statistics_pvalue":
        test = spec.get("test", "t-test")
        n1, n2 = spec.get("n1"), spec.get("n2")
        m1, m2 = spec.get("mean1"), spec.get("mean2")
        s1, s2 = spec.get("sd1"), spec.get("sd2")
        p = spec.get("claimed_p")
        return (f"A {test.replace('_',' ')} with n₁={n1}, n₂={n2}, "
                f"mean₁={m1}, mean₂={m2}, sd₁={s1}, sd₂={s2} "
                f"gives a two-tailed p-value of {p}.")

    if domain == "mathematics":
        mode = spec.get("mode", "")
        params = spec.get("params", {})
        if mode == "equality":
            return (f"The mathematical statement "
                    f"{params.get('expr_a')} = {params.get('expr_b')} is true.")
        if mode == "derivative":
            fn = params.get("function", "f(x)")
            cd = params.get("claimed_derivative", "?")
            var = params.get("variable", "x")
            return f"The derivative of {fn} with respect to {var} is {cd}."
        if mode == "integral":
            return f"The antiderivative of {params.get('integrand')} is {params.get('claimed_antiderivative')}."
        return f"The mathematical claim ({mode}: {params}) is correct."

    if domain == "labor":
        rate = spec.get("hourly_rate")
        hours = spec.get("hours_worked")
        regular = spec.get("regular_hours")
        ot = spec.get("overtime_hours")
        claimed_gross = spec.get("claimed_gross_pay")
        claimed_ot = spec.get("claimed_overtime_pay")
        claimed_hourly = spec.get("claimed_hourly_equivalent")
        annual = spec.get("annual_salary")
        if claimed_gross is not None and hours is not None:
            return (f"An employee earning ${rate}/hour who works {hours} hours "
                    f"has gross pay of ${claimed_gross}.")
        if claimed_ot is not None:
            return (f"An employee earning ${rate}/hour works {regular} regular "
                    f"hours plus {ot} overtime hours (1.5× rate). "
                    f"Their overtime pay is ${claimed_ot}.")
        if annual is not None and claimed_hourly is not None:
            return (f"A ${annual:,}/year salary equals ${claimed_hourly}/hour "
                    f"(based on standard annual hours).")
        return f"Labor claim: {spec}"

    if domain == "economics":
        p = spec.get("principal")
        r = spec.get("rate")
        t = spec.get("time_years")
        ci = spec.get("claimed_simple_interest")
        ry = spec.get("claimed_doubling_years")
        rp = spec.get("rate_percent")
        gdp = spec.get("gdp")
        pop = spec.get("population")
        cap = spec.get("claimed_gdp_per_capita")
        if ci is not None:
            return (f"Simple interest on ${p:,} at {r*100:.0f}% for {t} years "
                    f"is ${ci:.2f}.")
        if ry is not None:
            return (f"At {rp}% annual growth, an investment doubles "
                    f"in approximately {ry} years (Rule of 72).")
        if cap is not None:
            return (f"A country with GDP ${gdp:,} and population {pop:,} "
                    f"has GDP per capita of ${cap:,}.")
        return f"Economics claim: {spec}"

    if domain == "finance":
        a = spec.get("assets")
        l = spec.get("liabilities")
        e = spec.get("equity")
        pv = spec.get("claimed_present_value")
        fv = spec.get("claimed_future_value")
        p  = spec.get("principal")
        r  = spec.get("rate")
        y  = spec.get("years")
        if e is not None and a is not None:
            return (f"A company has assets ${a:,}, liabilities ${l:,}, "
                    f"and equity ${e:,}. (Accounting identity A = L + E)")
        if fv is not None:
            return (f"${p:,} invested at {r*100:.0f}% compounded annually "
                    f"for {y} years grows to ${fv:.2f}.")
        if pv is not None:
            return f"The present value of future cash flow is ${pv:.2f}."
        return f"Finance claim: {spec}"

    if domain == "music_theory":
        na, nb = spec.get("note_a"), spec.get("note_b")
        s = spec.get("claimed_semitones")
        f = spec.get("claimed_freq_hz")
        if s is not None:
            return f"The interval from {na} to {nb} is {s} semitones."
        if f is not None:
            return (f"Starting from {spec.get('base_freq_hz')} Hz at {na}, "
                    f"{spec.get('semitones_up')} semitones up gives {f} Hz.")
        return f"Music theory claim: {spec}"

    if domain == "calendar_time":
        y = spec.get("year")
        leap = spec.get("claimed_leap")
        dow = spec.get("claimed_weekday")
        date = spec.get("date")
        if leap is not None:
            return f"The year {y} {'is' if leap else 'is not'} a leap year."
        if dow is not None:
            return f"{date} falls on a {dow}."
        return f"Calendar claim: {spec}"

    if domain == "cryptography":
        algo = spec.get("algo") or spec.get("algorithm", "")
        msg  = spec.get("message_hex") or spec.get("message", "")
        dig  = spec.get("claimed_digest", "?")
        return f"The {algo} hash of {msg!r} is {dig}."

    if domain == "geometry":
        return f"Geometry claim: {spec}"

    if domain == "real_estate":
        ltv = spec.get("claimed_ltv")
        cap = spec.get("claimed_cap_rate")
        grm = spec.get("claimed_grm")
        lv  = spec.get("loan_amount")
        av  = spec.get("appraised_value")
        noi = spec.get("net_operating_income")
        pv  = spec.get("property_value")
        pp  = spec.get("property_price")
        agr = spec.get("annual_gross_rent")
        if ltv is not None:
            return (f"A ${lv:,} loan on a ${av:,} property has "
                    f"LTV ratio {ltv:.0%}.")
        if cap is not None:
            return (f"A property with NOI ${noi:,} valued at ${pv:,} "
                    f"has cap rate {cap:.0%}.")
        if grm is not None:
            return (f"A ${pp:,} property with ${agr:,} annual gross rent "
                    f"has GRM {grm}.")
        return f"Real estate claim: {spec}"

    return f"[{domain}: {spec}]"


def item_to_situation(item: dict) -> str:
    """Build a human-readable paragraph from domain_specs + quarantined."""
    sentences = []
    for ds in item.get("domain_specs", []):
        s = _spec_to_sentence(ds["domain"], ds.get("spec", {}))
        if s:
            sentences.append(s)
    for c in item.get("quarantined_claims", []):
        sentences.append(c)
    return " ".join(sentences) if sentences else "(no claims)"


# ── Verdict vocabulary ────────────────────────────────────────────────────────

_VERDICTS = ["CONCORDANT", "DISCORDANT", "MIXED", "QUARANTINE", "OUT_OF_SCOPE"]

_ALONE_SYSTEM = """\
You are a multi-domain fact-checking system. For each situation presented, \
you must classify it using exactly one of five verdicts:

CONCORDANT   — every factual claim in the situation is verifiably correct.
DISCORDANT   — at least one factual claim is clearly incorrect or contradicted \
by established science/math/law.
MIXED        — the majority of claims are correct, but one peripheral or \
minor claim is slightly wrong (not a core error).
QUARANTINE   — the situation contains claims that cannot be verified with \
objective facts alone (subjective, legal interpretation, or opinion-based).
OUT_OF_SCOPE — there are no specific factual claims to verify.

Rules:
- Consider ALL claims in the situation together.
- DISCORDANT requires a clear factual error (wrong formula, wrong number, wrong law).
- MIXED is for situations where one minor/peripheral claim is off but the main \
substance is sound.
- Reply with ONLY the verdict word. No explanation."""

_ALONE_PROMPT = """\
Situation:
{situation}

Verdict (CONCORDANT / DISCORDANT / MIXED / QUARANTINE / OUT_OF_SCOPE):"""


# ── Engine run ────────────────────────────────────────────────────────────────

def run_engine_mode(items: List[dict]) -> List[dict]:
    """Run deterministic synthesis for each item."""
    from concordance_engine.agent.poly_agent import _run_cluster
    from concordance_engine.poly_record import (
        compute_axis_overlaps, compute_axis_weights,
        compute_weighted_composite_verdict,
    )
    from concordance_engine.mcp_server.tools import ALL_TOOLS

    results = []
    for item in items:
        t0 = time.monotonic()
        domain_results = _run_cluster(item.get("domain_specs", []), ALL_TOOLS)
        ws = compute_axis_weights(domain_results)
        verdict = compute_weighted_composite_verdict(
            domain_results, weights=ws,
            quarantined_claims=item.get("quarantined_claims") or None,
        )
        elapsed = time.monotonic() - t0
        results.append({
            "id": item["id"],
            "expected": item["expected_verdict"],
            "verdict": verdict,
            "correct": verdict == item["expected_verdict"],
            "elapsed_s": elapsed,
            "domain_results": [
                {"domain": r.domain, "verdict": r.verdict,
                 "weight": ws.get(r.domain, 0)}
                for r in domain_results
            ],
        })
    return results


# ── Alone run ─────────────────────────────────────────────────────────────────

def run_alone_mode(items: List[dict], model: str, delay: float = 0.2) -> List[dict]:
    """Ask Claude (no tools) to classify each situation."""
    import anthropic
    client = anthropic.Anthropic()

    results = []
    for item in items:
        situation = item_to_situation(item)
        prompt = _ALONE_PROMPT.format(situation=situation)

        t0 = time.monotonic()
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=16,
                system=_ALONE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip().upper()
            # Extract first matching verdict word
            verdict = next((v for v in _VERDICTS if v in raw), raw.split()[0] if raw else "UNKNOWN")
        except Exception as e:
            verdict = f"[ERROR: {e}]"
        elapsed = time.monotonic() - t0

        results.append({
            "id": item["id"],
            "expected": item["expected_verdict"],
            "verdict": verdict,
            "correct": verdict == item["expected_verdict"],
            "elapsed_s": elapsed,
            "situation": situation[:120],
        })
        if delay:
            time.sleep(delay)
    return results


# ── Poly oracle run ───────────────────────────────────────────────────────────

def run_poly_mode(items: List[dict], model: str, delay: float = 0.5) -> List[dict]:
    """Run the full oracle pipeline (decompose → classify → verify → synthesise)."""
    from concordance_engine.agent.poly_agent import run_polymathic

    results = []
    for item in items:
        situation = item_to_situation(item)

        t0 = time.monotonic()
        try:
            record = run_polymathic(situation, model=model, decompose=True)
            verdict = record.composite_verdict
        except Exception as e:
            verdict = f"[ERROR: {e}]"
        elapsed = time.monotonic() - t0

        results.append({
            "id": item["id"],
            "expected": item["expected_verdict"],
            "verdict": verdict,
            "correct": verdict == item["expected_verdict"],
            "elapsed_s": elapsed,
            "situation": situation[:120],
        })
        if delay:
            time.sleep(delay)
    return results


# ── Reporting ─────────────────────────────────────────────────────────────────

def score(results: List[dict]) -> tuple[int, int]:
    c = sum(1 for r in results if r["correct"])
    return c, len(results)


def print_run(label: str, results: List[dict], width: int = 60) -> None:
    c, n = score(results)
    t = sum(r["elapsed_s"] for r in results)
    print(f"\n{'='*width}")
    print(f"  {label}")
    print(f"  Total:   {c}/{n} = {c/n:.1%}")
    print(f"  Elapsed: {t:.2f}s  ({t/n:.2f}s avg)")
    print(f"{'─'*width}")
    by_verdict: Dict[str, list] = {}
    for r in results:
        by_verdict.setdefault(r["expected"], []).append(r)
    for v in sorted(by_verdict):
        rs = by_verdict[v]
        ok = sum(r["correct"] for r in rs)
        marker = "+" if ok == len(rs) else ("x" if ok == 0 else "~")
        print(f"  {marker} {v:13s}: {ok}/{len(rs)}")
    print(f"{'='*width}")


def delta_table(label_a: str, res_a: List[dict],
                label_b: str, res_b: List[dict]) -> None:
    a_map = {r["id"]: r for r in res_a}
    b_map = {r["id"]: r for r in res_b}
    fixed  = [r for r in res_b if r["correct"] and not a_map.get(r["id"], r)["correct"]]
    broken = [r for r in res_b if not r["correct"] and a_map.get(r["id"], r)["correct"]]
    gained = [r for r in res_a if not r["correct"] and b_map.get(r["id"], r)["correct"]]

    print(f"\n  Delta: {label_b} vs {label_a}")
    if fixed:
        print(f"  Items {label_b} FIXED vs {label_a} ({len(fixed)}):")
        for r in fixed:
            print(f"    + {r['id']:10s}  exp={r['expected']:12s}  {label_b}={r['verdict']}")
    else:
        print(f"  (no items fixed by {label_b})")
    if broken:
        print(f"  Items {label_b} BROKE vs {label_a} ({len(broken)}):")
        for r in broken:
            print(f"    - {r['id']:10s}  exp={r['expected']:12s}  {label_b}={r['verdict']}")
    if not fixed and not broken:
        print("  (identical results)")


def full_table(runs: Dict[str, List[dict]], items: List[dict]) -> None:
    """Print a per-item comparison table across all runs."""
    headers = list(runs.keys())
    col_w = 14
    id_w = 10
    exp_w = 14

    print(f"\n{'─'*70}")
    header = f"  {'ID':{id_w}}  {'Expected':{exp_w}}" + "".join(
        f"  {h:{col_w}}" for h in headers)
    print(header)
    print(f"{'─'*70}")

    for item in items:
        iid = item["id"]
        exp = item["expected_verdict"]
        row = f"  {iid:{id_w}}  {exp:{exp_w}}"
        for h, res in runs.items():
            by_id = {r["id"]: r for r in res}
            r = by_id.get(iid)
            if r:
                mark = "✓" if r["correct"] else "✗"
                v = r["verdict"][:col_w-2]
                row += f"  {mark} {v:{col_w-2}}"
            else:
                row += f"  {'N/A':{col_w}}"
        print(row)
    print(f"{'─'*70}")

    # Summary row
    summary = f"  {'SCORE':{id_w}}  {'':{exp_w}}"
    for h, res in runs.items():
        c, n = score(res)
        s = f"{c}/{n}={c/n:.0%}"
        summary += f"  {s:{col_w}}"
    print(summary)
    print(f"{'─'*70}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        help="Model for alone + poly runs")
    parser.add_argument("--engine-only", action="store_true",
                        help="Skip alone and poly runs (no API calls)")
    parser.add_argument("--poly", action="store_true",
                        help="Also run the full oracle pipeline (expensive)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Seconds between API calls")
    parser.add_argument("--build", action="store_true",
                        help="Regenerate items_poly.jsonl first")
    args = parser.parse_args()

    if args.build:
        import subprocess
        subprocess.run([sys.executable,
                        str(THIS.parent / "build_poly_items.py")], check=True)

    if not ITEMS_PATH.exists():
        print("items_poly.jsonl not found — run with --build.", file=sys.stderr)
        sys.exit(1)

    items = [json.loads(l) for l in ITEMS_PATH.read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    print(f"Loaded {len(items)} items")
    print(f"Model: {args.model}")

    runs: Dict[str, List[dict]] = {}

    # ── Engine (always) ───────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  ENGINE (deterministic synthesis)...")
    engine_results = run_engine_mode(items)
    runs["engine"] = engine_results
    print_run(f"Engine ({args.model})", engine_results)

    if args.engine_only:
        full_table(runs, items)
        return

    # ── Alone ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  ALONE — {args.model} (no tools)...")
    alone_results = run_alone_mode(items, args.model, delay=args.delay)
    runs["alone"] = alone_results
    print_run(f"Alone ({args.model})", alone_results)

    delta_table("alone", alone_results, "engine", engine_results)

    # ── Poly oracle (opt-in) ───────────────────────────────────────────────
    if args.poly:
        print(f"\n{'─'*60}")
        print(f"  POLY ORACLE — {args.model} (full pipeline)...")
        poly_results = run_poly_mode(items, args.model, delay=args.delay)
        runs["poly-oracle"] = poly_results
        print_run(f"Poly Oracle ({args.model})", poly_results)
        delta_table("alone", alone_results, "poly-oracle", poly_results)
        delta_table("engine", engine_results, "poly-oracle", poly_results)

    # ── Full comparison table ─────────────────────────────────────────────
    full_table(runs, items)

    # Save results
    out = THIS.parent / f"results_poly_compare_{args.model.replace('-','_')}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for mode, res in runs.items():
            for r in res:
                f.write(json.dumps({"mode": mode, **r}, ensure_ascii=False) + "\n")
    print(f"\nResults written to {out.name}")


if __name__ == "__main__":
    main()
