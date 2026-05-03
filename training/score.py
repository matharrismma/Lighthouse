"""Score a model's predictions against the held-out eval set.

Wraps `eval/run_eval.py --mode=score` with a cleaner CLI and adds a
training-friendly summary:
    - overall accuracy
    - per-domain accuracy
    - confusion matrix (top mismatches)
    - per-difficulty accuracy
    - flag if accuracy <= heuristic baseline (suggests undertraining)

Usage:
    python training/score.py --predictions preds.jsonl
    python training/score.py --predictions preds.jsonl --eval eval/eval_chat.jsonl

Predictions JSONL shape (one per line):
    {"id": "EVAL-0001", "predicted_halt_gate": "RED"}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

# Heuristic baseline reported in CHANGELOG v1.0.5: ~76%.
# Anything trained should beat this, otherwise it's undertraining.
HEURISTIC_BASELINE = 0.76


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True, type=Path,
                    help="JSONL of {id, predicted_halt_gate}")
    ap.add_argument("--eval", default=Path("eval/eval_chat.jsonl"), type=Path,
                    help="JSONL of eval items (default: eval/eval_chat.jsonl)")
    ap.add_argument("--quiet", action="store_true",
                    help="Print only the overall accuracy as a number")
    args = ap.parse_args()

    if not args.eval.exists():
        print(f"eval set not found: {args.eval}", file=sys.stderr)
        sys.exit(1)
    if not args.predictions.exists():
        print(f"predictions not found: {args.predictions}", file=sys.stderr)
        sys.exit(1)

    eval_items = {it["id"]: it for it in load_jsonl(args.eval)}
    preds = load_jsonl(args.predictions)

    correct = 0
    total = 0
    by_domain = defaultdict(lambda: [0, 0])  # [correct, total]
    by_difficulty = defaultdict(lambda: [0, 0])
    confusion = Counter()
    missing = []

    for p in preds:
        pid = p.get("id")
        item = eval_items.get(pid)
        if item is None:
            missing.append(pid)
            continue
        expected = (item.get("halt_gate_expected") or "").upper()
        predicted = (p.get("predicted_halt_gate") or "").upper()
        ok = (expected == predicted)
        total += 1
        if ok:
            correct += 1
        domain = item.get("domain", "unknown")
        diff = item.get("difficulty", "unknown")
        by_domain[domain][1] += 1
        by_difficulty[diff][1] += 1
        if ok:
            by_domain[domain][0] += 1
            by_difficulty[diff][0] += 1
        confusion[(expected, predicted)] += 1

    if total == 0:
        print("No predictions matched any eval item.", file=sys.stderr)
        sys.exit(2)

    accuracy = correct / total
    if args.quiet:
        print(f"{accuracy:.4f}")
        return

    print(f"Scored {total} predictions against {args.eval}")
    print(f"  Overall accuracy: {correct}/{total} = {accuracy:.1%}")
    if missing:
        print(f"  Predictions missing from eval set: {len(missing)} (first: {missing[:3]})")

    print()
    print(f"  vs heuristic baseline ({HEURISTIC_BASELINE:.0%}):")
    if accuracy < HEURISTIC_BASELINE:
        print(f"    ⚠️  BELOW baseline — likely undertraining or contamination")
    elif accuracy < HEURISTIC_BASELINE + 0.05:
        print(f"    ~ at baseline — train for longer or audit data")
    else:
        print(f"    ✓  beating baseline")

    print()
    print("  Per domain:")
    for d in sorted(by_domain):
        c, t = by_domain[d]
        print(f"    {d:14s} {c:3d}/{t:3d} = {(c/t):.0%}")

    print()
    print("  Per difficulty:")
    for d in sorted(by_difficulty):
        c, t = by_difficulty[d]
        print(f"    {d:14s} {c:3d}/{t:3d} = {(c/t):.0%}")

    print()
    print("  Top confusions (expected -> predicted, count):")
    for (e, p), c in sorted(confusion.items(), key=lambda kv: -kv[1])[:8]:
        if e != p:
            print(f"    {e:10s} -> {p:10s}  {c}")

    sys.exit(0 if correct == total else 1)


if __name__ == "__main__":
    main()
