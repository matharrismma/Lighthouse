"""Measure the 'find more from what we have' yield.

Premise: 782 of 886 almanac entries (already four-gate-verified, STRUCTURED
claims) have ZERO confirmed domains, and 23 have exactly one. Only 81 reached the
2+ that makes a verified cross-domain connection. If we re-run the unconfirmed
structured claims through the existing deterministic verifier stack, how many
newly confirm domains -- and how many reach 2+ (a NEW verified connection)?

This is the empirical test of the discovery thesis. It is FAITHFUL: deterministic
verifiers on already-structured claims (NOT the free-text grid prose, which the
2026-06-06 Phase-2 pilot already found yields ~0%). It GENERATES nothing -- it
only runs checks we already have and counts what survives.

Read-only on the substrate; runs the verifier dispatch in-process (no writes).
Bounded by --n. Reports yield + any oracle cost so the measurement is honest.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRIES = REPO / "data" / "almanac" / "entries.jsonl"


def _confirmed_domains(entry: dict) -> list:
    dr = (entry.get("pre_run") or {}).get("domain_results") or []
    return sorted({d["domain"] for d in dr
                   if d.get("verdict") == "CONFIRMED" and d.get("domain")})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="sample size of unconfirmed claims")
    ap.add_argument("--min-confirmed", type=int, default=0,
                    help="only probe claims currently confirmed by <= this many domains")
    args = ap.parse_args()

    try:
        from concordance_engine.agent.poly_agent import run_polymathic
    except Exception as exc:
        print(f"[FATAL] polymathic agent unavailable: {exc}")
        return 1

    # Pick claims currently confirmed by <= min_confirmed domains (the opportunity).
    sample = []
    with ENTRIES.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            sit = (e.get("situation") or "").strip()
            if not sit:
                continue
            if len(_confirmed_domains(e)) <= args.min_confirmed:
                sample.append(e)
            if len(sample) >= args.n:
                break

    print(f"probing {len(sample)} structured claims currently confirmed by "
          f"<= {args.min_confirmed} domain(s)\n")

    newly_2plus = 0
    newly_any = 0
    rows = []
    for e in sample:
        sit = (e.get("situation") or "").strip()
        before = _confirmed_domains(e)
        try:
            rec = run_polymathic(situation=sit, model=None)
        except Exception as exc:
            rows.append((e.get("id"), "ERROR", str(exc)[:60], before, []))
            continue
        # Normalize a PolymathicRecord (dataclass or dict). The composite field is
        # `composite_verdict`; domain_results is a list of {domain, verdict, ...}.
        def _get(o, k):
            return o.get(k) if isinstance(o, dict) else getattr(o, k, None)
        results = _get(rec, "domain_results") or _get(rec, "results") or []
        confirmed = []
        for d in results:
            dom = _get(d, "domain")
            vd = _get(d, "verdict")
            if dom and vd == "CONFIRMED":
                confirmed.append(dom)
        confirmed = sorted(set(confirmed))
        verdict = _get(rec, "composite_verdict") or _get(rec, "verdict") or "?"
        if len(confirmed) >= 1:
            newly_any += 1
        if len(confirmed) >= 2:
            newly_2plus += 1
        rows.append((e.get("id"), verdict, "", before, confirmed))

    print(f"{'id':<22} {'verdict':<13} {'before':<8} after")
    for cid, verdict, err, before, after in rows:
        tag = err or (",".join(after) if after else "(none)")
        print(f"{str(cid)[:22]:<22} {verdict:<13} {len(before):<8} {tag[:60]}")

    n = len(sample) or 1
    print(f"\n=== YIELD (re-running prose situations through /polymathic) ===")
    print(f"confirm >=1 domain on re-run : {newly_any}/{len(sample)}  ({100*newly_any/n:.0f}%)")
    print(f"reach   >=2 (a verified cross-domain connection): {newly_2plus}/{len(sample)}  ({100*newly_2plus/n:.0f}%)")
    print("Note: OUT_OF_SCOPE = the NL->structured-spec extraction failed; the verifier "
          "never ran. The bottleneck this measures is claim STRUCTURING, not verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
