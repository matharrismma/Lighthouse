"""Adversarial regression suite for the engine.

Runs each claim in claims.jsonl through /polymathic and confirms the
composite verdict matches what's expected. The engine is supposed to
catch known truths (CONCORDANT), known lies (DISCORDANT), and known
coverage gaps (OUT_OF_SCOPE). If any drift, this script prints a
diff and exits non-zero.

Usage:
    python scripts/regression/run_regression.py
    python scripts/regression/run_regression.py --host http://127.0.0.1:8000
    python scripts/regression/run_regression.py --filter truth-codata
    python scripts/regression/run_regression.py --quick      # first 5 only

Exit codes:
    0 — all expectations met
    1 — one or more regressions
    2 — engine unreachable
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

CLAIMS_FILE = Path(__file__).resolve().parent / "claims.jsonl"


def load_claims() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with CLAIMS_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def run_one(host: str, claim: str, timeout: int = 90) -> Tuple[str, Dict[str, Any]]:
    body = json.dumps({"situation": claim, "store": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/polymathic",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return "HTTP_ERROR", {"error": f"{e.code}: {e.reason}"}
    except Exception as e:
        return "NETWORK_ERROR", {"error": str(e)}
    return payload.get("composite_verdict", "?"), payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8000")
    p.add_argument("--filter", default="", help="substring filter on claim id")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    claims = load_claims()
    if args.filter:
        claims = [c for c in claims if args.filter in c.get("id", "")]
    if args.quick:
        claims = claims[:5]
    if not claims:
        print("no claims to run", file=sys.stderr)
        return 0

    # Pre-flight: is the engine alive?
    try:
        with urllib.request.urlopen(f"{args.host}/health/lite", timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"engine unreachable at {args.host}: {e}", file=sys.stderr)
        return 2

    started = time.time()
    pass_count = 0
    fail_count = 0
    failures: List[Dict[str, Any]] = []

    for c in claims:
        cid = c.get("id", "?")
        claim = c.get("claim", "")
        expected = c.get("expected", "")
        why = c.get("why", "")
        actual, payload = run_one(args.host, claim)
        ok = (actual == expected)
        marker = "[ok]" if ok else "[fail]"
        # OUT_OF_SCOPE often comes out as QUARANTINE when polymathic's
        # claim decomposer produces nothing — treat them equivalently
        # for regression purposes (both are "engine didn't fire").
        if not ok and expected == "OUT_OF_SCOPE" and actual == "QUARANTINE":
            ok = True
            marker = "[ok]"
        if ok:
            pass_count += 1
        else:
            fail_count += 1
            failures.append({
                "id": cid, "claim": claim,
                "expected": expected, "actual": actual,
                "why": why,
                "domains_fired": [dr.get("domain") for dr in payload.get("domain_results", []) if isinstance(dr, dict)],
            })
        if args.verbose or not ok:
            print(f"  {marker} {cid:36} expected={expected:13} actual={actual:13}  {claim[:60]}")

    elapsed = time.time() - started
    print()
    print(f"{pass_count}/{pass_count + fail_count} passing ({elapsed:.1f}s)")
    if failures:
        print()
        print("FAILURES:")
        for f in failures:
            print(f"  {f['id']}")
            print(f"    claim:    {f['claim']}")
            print(f"    expected: {f['expected']}    actual: {f['actual']}")
            print(f"    why:      {f['why']}")
            if f["domains_fired"]:
                print(f"    fired:    {', '.join(f['domains_fired'])}")
            print()
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
