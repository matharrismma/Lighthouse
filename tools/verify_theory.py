"""verify_theory — LOCATE a theory/paper's claims, then VERIFY each.

Matt 2026-06-10: "We need to locate papers, theories, and frameworks and verify.
We can rough out a lot by using others' theories." This is the verify side: feed
a located source's quantitative claims (prose) through the bridge (/derivation/
solve); each is machine-verified by the deterministic verifiers. The engine never
generates truth — it CHECKS the located claims, and a wrong one BREAKS.

Usage:
  python tools/verify_theory.py --title "Title" --source "url" -- "claim1" "claim2" ...

Each claim is a plain-language statement of one quantitative claim from the source.
Prints a verified / broken / incomplete breakdown.
"""
from __future__ import annotations

import argparse
import json
import urllib.request

PROD = "https://narrowhighway.com"


def verify(claim: str, base: str = PROD) -> dict:
    req = urllib.request.Request(
        base + "/derivation/solve",
        data=json.dumps({"problem": claim}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=75) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"request error: {e}"}


def run(title: str, source: str, claims: list, base: str = PROD) -> list:
    rows = []
    for c in claims:
        d = verify(c, base)
        verdict = d.get("verdict") if d.get("ok") else "INCOMPLETE"
        doms = sorted({s.get("domain") for s in (d.get("structured_steps") or []) if s.get("domain")})
        broke_at = d.get("broken_at")
        rows.append({"claim": c, "verdict": verdict, "domains": doms, "broken_at": broke_at})
        tag = {"HOLDS": "VERIFIED  ", "BROKEN": "BROKEN    ", "INCOMPLETE": "INCOMPLETE"}.get(verdict, verdict)
        print(f"[{tag}] {c[:66]}  ({', '.join(doms) or '-'})")
    held = sum(1 for r in rows if r["verdict"] == "HOLDS")
    broke = sum(1 for r in rows if r["verdict"] == "BROKEN")
    inc = len(rows) - held - broke
    print(f"\n{title}")
    print(f"  source: {source}")
    print(f"  {held} VERIFIED · {broke} BROKEN · {inc} INCOMPLETE  (of {len(rows)} located claims)")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--base", default=PROD)
    ap.add_argument("claims", nargs="+")
    a = ap.parse_args(argv)
    run(a.title, a.source, a.claims, a.base)


if __name__ == "__main__":
    main()
