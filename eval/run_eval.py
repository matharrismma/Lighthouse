"""Eval runner for the Four-Gates conversational dataset.

Two modes:
  --mode=score    Score a JSONL of {id, predicted_halt_gate} against the dataset.
  --mode=heuristic  Run a deterministic baseline that extracts the halt gate
                    directly from the assistant turn already in the dataset
                    (i.e. measures the dataset's internal consistency).

Usage:
    PYTHONPATH=src python eval/run_eval.py --mode=heuristic
    PYTHONPATH=src python eval/run_eval.py --mode=score --predictions preds.jsonl

The dataset stores expected halt gates as one of: RED, FLOOR, WAY, EXECUTION, PASS.
We compare predicted halt gate to the expected halt gate per item and report
overall accuracy plus per-domain breakdown.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

EVAL_PATH = Path(__file__).resolve().parent / "eval_chat.jsonl"


_GATE_RE = re.compile(
    r"\b(?P<gate>RED|FLOOR|WAY|EXECUTION)\s+GATE\s*[:\-]\s*(?P<verdict>FAIL|PASS|CAUTION)\b",
    re.IGNORECASE,
)


def extract_halt_gate_from_assistant(text: str) -> str:
    """Heuristic: walk gate verdicts in order, return the first FAIL gate.

    If no gate fails, return the last gate mentioned (PASS or EXECUTION).
    """
    matches = list(_GATE_RE.finditer(text))
    for m in matches:
        gate = m.group("gate").upper()
        verdict = m.group("verdict").upper()
        if verdict == "FAIL":
            return gate
    if matches:
        return matches[-1].group("gate").upper()
    return "UNKNOWN"


def load_dataset(path: Path):
    items = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def cmd_heuristic():
    items = load_dataset(EVAL_PATH)
    correct = 0
    by_domain = defaultdict(lambda: [0, 0])  # [correct, total]
    confusion = Counter()
    for it in items:
        expected = (it.get("halt_gate_expected") or "").upper()
        # Find the assistant turn
        assistant_text = ""
        for m in it.get("messages", []):
            if m.get("role") == "assistant":
                assistant_text = m.get("content", "")
                break
        predicted = extract_halt_gate_from_assistant(assistant_text)
        ok = (predicted == expected)
        if ok:
            correct += 1
        domain = it.get("domain", "unknown")
        by_domain[domain][1] += 1
        if ok:
            by_domain[domain][0] += 1
        confusion[(expected, predicted)] += 1
    n = len(items)
    print(f"Heuristic baseline (extract halt gate from existing assistant turn)")
    print(f"  Overall: {correct}/{n} = {correct / n:.1%}")
    print()
    print(f"  Per domain:")
    for d in sorted(by_domain):
        c, t = by_domain[d]
        print(f"    {d:14s} {c:3d}/{t:3d} = {c/t:.0%}")
    print()
    print(f"  Confusion (expected -> predicted, count):")
    for (e, p), c in sorted(confusion.items(), key=lambda kv: -kv[1])[:10]:
        if e != p:
            print(f"    {e:10s} -> {p:10s}  {c}")
    return 0 if correct == n else 1


def cmd_score(predictions_path: Path):
    items = {it["id"]: it for it in load_dataset(EVAL_PATH)}
    preds = []
    with predictions_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                preds.append(json.loads(line))
    correct = 0
    n = len(preds)
    missing = []
    confusion = Counter()
    for p in preds:
        pid = p["id"]
        item = items.get(pid)
        if item is None:
            missing.append(pid)
            continue
        expected = (item.get("halt_gate_expected") or "").upper()
        predicted = (p.get("predicted_halt_gate") or "").upper()
        if predicted == expected:
            correct += 1
        confusion[(expected, predicted)] += 1
    print(f"Scoring {predictions_path}: {correct}/{n} correct = {correct/n:.1%}")
    if missing:
        print(f"  {len(missing)} prediction id(s) not found in dataset")
    print(f"  Confusion (expected -> predicted, count):")
    for (e, pr), c in sorted(confusion.items(), key=lambda kv: -kv[1])[:10]:
        if e != pr:
            print(f"    {e:10s} -> {pr:10s}  {c}")
    return 0 if correct == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["heuristic", "score"], default="heuristic")
    ap.add_argument("--predictions", type=Path, default=None,
                    help="JSONL of {id, predicted_halt_gate} for --mode=score")
    args = ap.parse_args()
    if args.mode == "heuristic":
        sys.exit(cmd_heuristic())
    if args.mode == "score":
        if not args.predictions:
            ap.error("--predictions required for --mode=score")
        sys.exit(cmd_score(args.predictions))


if __name__ == "__main__":
    main()
