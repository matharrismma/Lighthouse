"""Trust Floor — adversarial-precision benchmark.

The original benchmark measured tool-use accuracy and saturated at 100%
(171/171). That's no longer a useful number — it doesn't tell us where
the engine is actually weak.

Trust Floor measures what an honesty-first engine actually needs to
defend: the **false positive rate**. How often does the engine return
CONCORDANT for a claim that's actually wrong? Every false positive is
the engine lying to the user. A trustworthy engine should approach
FPR=0; an over-confident one drifts upward.

The benchmark slices claims into four buckets:

  truth     — true claims; engine should CONCORDANT
  lie       — adversarial; engine should DISCORDANT (never CONCORDANT)
  boundary  — at the tolerance edge; engine should CONCORDANT
              (within tolerance) consistently across runs
  gap       — known coverage gaps; engine should OUT_OF_SCOPE
              (never CONCORDANT, since the math chain doesn't exist)

Headline metrics:

  FPR    — false positive rate = (lies + gaps marked CONCORDANT) / total
           non-truths. THE TRUST-FLOOR NUMBER. Target: 0.
  Recall — fraction of truths correctly CONCORDANT.
  Cover  — fraction of all claims where at least one verifier fired.

Usage:
    python scripts/regression/run_trust_floor.py
    python scripts/regression/run_trust_floor.py --slice lie
    python scripts/regression/run_trust_floor.py --domain physics
    python scripts/regression/run_trust_floor.py --report json > tf.json

Each commit that changes verifier behavior should re-run this. The
benchmark is a growing substrate: when a new verifier ships, add 3-5
claims here (1-2 truths, 1-2 lies, ideally a boundary case). The
build queue's growth feeds this directly — every promoted gap should
also seed a claim or two.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLAIMS_FILE = Path(__file__).resolve().parent / "trust_floor.jsonl"


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


def _verdict_matches(expected: str, actual: str) -> bool:
    """OUT_OF_SCOPE and QUARANTINE are equivalent for benchmarking — both
    mean 'engine did not fire / could not classify'. CONCORDANT must
    match exactly. Everything else uses the verdict label."""
    if expected == actual:
        return True
    if expected == "OUT_OF_SCOPE" and actual in ("QUARANTINE", "OUT_OF_SCOPE"):
        return True
    return False


def classify_outcome(expected: str, actual: str) -> str:
    """Map (expected, actual) to a result category for reporting."""
    if expected == "CONCORDANT":
        if actual == "CONCORDANT":
            return "true_positive"  # truth confirmed
        return "false_negative"      # truth missed
    if expected == "DISCORDANT":
        if actual == "DISCORDANT":
            return "true_negative"   # lie caught
        if actual == "CONCORDANT":
            return "false_positive"  # ENGINE LIED — trust-floor violation
        return "missed_lie"          # lie not confirmed but not caught either
    if expected == "OUT_OF_SCOPE":
        if actual in ("OUT_OF_SCOPE", "QUARANTINE"):
            return "correct_gap"
        if actual == "CONCORDANT":
            return "false_positive_gap"  # engine confirmed something it shouldn't
        return "misrouted_gap"
    return "unknown"


def main() -> int:
    p = argparse.ArgumentParser(description="Trust Floor — adversarial-precision benchmark.")
    p.add_argument("--host", default="http://127.0.0.1:8000")
    p.add_argument("--slice", default="", help="filter by slice: truth|lie|boundary|gap")
    p.add_argument("--domain", default="", help="filter by domain")
    p.add_argument("--filter", default="", help="substring filter on claim id")
    p.add_argument("--limit", type=int, default=0, help="cap claims run (0 = no cap)")
    p.add_argument("--pace", type=float, default=0.5, help="seconds between claims (rate-limit pacing)")
    p.add_argument("--report", choices=["text", "json", "both"], default="text")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    claims = load_claims()
    if args.slice:
        claims = [c for c in claims if c.get("slice") == args.slice]
    if args.domain:
        claims = [c for c in claims if c.get("domain") == args.domain]
    if args.filter:
        claims = [c for c in claims if args.filter in c.get("id", "")]
    if args.limit:
        claims = claims[: args.limit]
    if not claims:
        print("no claims to run", file=sys.stderr)
        return 0

    try:
        with urllib.request.urlopen(f"{args.host}/health/lite", timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"engine unreachable at {args.host}: {e}", file=sys.stderr)
        return 2

    started = time.time()
    outcomes: List[Dict[str, Any]] = []
    by_slice: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_domain: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    fired_count = 0

    for i, c in enumerate(claims):
        if i > 0 and args.pace > 0:
            time.sleep(args.pace)
        cid = c.get("id", "?")
        claim_text = c.get("claim", "")
        slice_ = c.get("slice", "?")
        domain = c.get("domain", "?")
        expected = c.get("expected", "")
        actual, payload = run_one(args.host, claim_text)
        outcome = classify_outcome(expected, actual)
        ok = outcome in ("true_positive", "true_negative", "correct_gap")
        domain_results = payload.get("domain_results", []) if isinstance(payload, dict) else []
        any_fired = bool(domain_results)
        if any_fired:
            fired_count += 1
        outcomes.append({
            "id": cid, "slice": slice_, "domain": domain,
            "claim": claim_text, "expected": expected, "actual": actual,
            "outcome": outcome, "ok": ok, "fired": any_fired,
            "why": c.get("why", ""),
            "fired_domains": [dr.get("domain") for dr in domain_results if isinstance(dr, dict)],
        })
        by_slice[slice_][outcome] += 1
        by_slice[slice_]["_total"] += 1
        by_domain[domain][outcome] += 1
        by_domain[domain]["_total"] += 1
        if args.verbose or not ok:
            marker = "[ok]" if ok else "[fail]"
            print(f"  {marker} {cid:36} {slice_:9} {domain:22} expected={expected:13} actual={actual}")

    elapsed = time.time() - started

    # Aggregate metrics
    total = len(outcomes)
    true_positive = sum(1 for o in outcomes if o["outcome"] == "true_positive")
    true_negative = sum(1 for o in outcomes if o["outcome"] == "true_negative")
    correct_gap = sum(1 for o in outcomes if o["outcome"] == "correct_gap")
    false_positive = sum(1 for o in outcomes if o["outcome"] == "false_positive")
    false_positive_gap = sum(1 for o in outcomes if o["outcome"] == "false_positive_gap")
    false_negative = sum(1 for o in outcomes if o["outcome"] == "false_negative")
    missed_lie = sum(1 for o in outcomes if o["outcome"] == "missed_lie")
    misrouted_gap = sum(1 for o in outcomes if o["outcome"] == "misrouted_gap")

    n_truths = sum(1 for o in outcomes if o["expected"] == "CONCORDANT")
    n_lies = sum(1 for o in outcomes if o["expected"] == "DISCORDANT")
    n_gaps = sum(1 for o in outcomes if o["expected"] == "OUT_OF_SCOPE")
    n_non_truths = n_lies + n_gaps

    # FPR: any time a non-truth came back CONCORDANT. The trust-floor number.
    fpr = (false_positive + false_positive_gap) / n_non_truths if n_non_truths else 0
    recall = true_positive / n_truths if n_truths else 0
    coverage = fired_count / total if total else 0

    report = {
        "total": total,
        "elapsed_s": round(elapsed, 1),
        "metrics": {
            "false_positive_rate": round(fpr, 4),
            "false_positives": false_positive + false_positive_gap,
            "non_truths_evaluated": n_non_truths,
            "recall": round(recall, 4),
            "truths_evaluated": n_truths,
            "coverage": round(coverage, 4),
        },
        "outcomes": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "correct_gap": correct_gap,
            "false_positive": false_positive,
            "false_positive_gap": false_positive_gap,
            "false_negative": false_negative,
            "missed_lie": missed_lie,
            "misrouted_gap": misrouted_gap,
        },
        "by_slice": {k: dict(v) for k, v in by_slice.items()},
        "by_domain": {k: dict(v) for k, v in by_domain.items()},
        "failures": [o for o in outcomes if not o["ok"]],
    }

    if args.report in ("json", "both"):
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.report in ("text", "both"):
        print()
        print(f"TRUST FLOOR — {total} claims, {elapsed:.1f}s")
        print()
        print(f"  False Positive Rate:  {fpr*100:.2f}%   ({false_positive + false_positive_gap} of {n_non_truths} non-truths confirmed)")
        print(f"  Recall (truths):      {recall*100:.2f}%   ({true_positive} of {n_truths} truths confirmed)")
        print(f"  Coverage:             {coverage*100:.2f}%   ({fired_count} of {total} claims had a verifier fire)")
        print()
        print("  By slice:")
        for s, counts in sorted(by_slice.items()):
            t = counts.get("_total", 0)
            ok = sum(v for k, v in counts.items() if k in ("true_positive", "true_negative", "correct_gap"))
            print(f"    {s:10} {ok:3} / {t:3}")
        # Per-domain only when failures exist there
        problem_domains = [d for d, c in by_domain.items()
                           if c.get("false_positive", 0) > 0
                           or c.get("false_positive_gap", 0) > 0
                           or c.get("false_negative", 0) > 0
                           or c.get("missed_lie", 0) > 0]
        if problem_domains:
            print()
            print("  Domains with failures:")
            for d in sorted(problem_domains):
                c = by_domain[d]
                t = c.get("_total", 0)
                bad = c.get("false_positive", 0) + c.get("false_positive_gap", 0) + c.get("false_negative", 0) + c.get("missed_lie", 0)
                print(f"    {d:22} {bad:3} bad / {t:3} total")

        if false_positive + false_positive_gap > 0:
            print()
            print("  *** TRUST-FLOOR VIOLATIONS — engine confirmed false claims ***")
            for o in outcomes:
                if o["outcome"] in ("false_positive", "false_positive_gap"):
                    print(f"    {o['id']}  {o['claim'][:80]}")

    # Exit 0 only if FPR is exactly 0. The trust-floor violation is a
    # hard failure regardless of other slice scores.
    if fpr > 0:
        return 1
    if false_negative + missed_lie + misrouted_gap > total * 0.30:
        return 1  # > 30% other failures is also a fail
    return 0


if __name__ == "__main__":
    sys.exit(main())
