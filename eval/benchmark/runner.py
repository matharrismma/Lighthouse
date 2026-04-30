"""Benchmark runner: score a completion-fn against eval/benchmark/items.jsonl.

A completion fn maps a list of chat messages to an assistant string. The runner
calls it once per item, parses the answer, and scores against ground truth.

Two scoring modes are baked in:
  - 'classification': normalize to lowercase, take the first word, compare.
  - 'numeric':        extract the first decimal number, compare with relative
                      tolerance from the item.

Usage:
    from eval.benchmark.runner import run, BenchResult
    result = run(my_completion_fn, label="claude_alone")
    print(result.summary())

Or as a script (smoke-tests with a stub fn that returns "yes" / 0.05):
    python eval/benchmark/runner.py
"""
from __future__ import annotations
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Tuple

THIS = Path(__file__).resolve()
ITEMS_PATH = THIS.parent / "items.jsonl"


CompletionFn = Callable[[List[Dict[str, str]]], str]


_NUM_RE = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def parse_classification(reply: str) -> str:
    """First word, lowercased, stripped of punctuation."""
    if not reply:
        return ""
    word = reply.strip().split()[0] if reply.strip() else ""
    return re.sub(r"[^a-z]", "", word.lower())


def parse_numeric(reply: str) -> float | None:
    """First decimal number in the reply, or None."""
    if not reply:
        return None
    m = _NUM_RE.search(reply)
    if m is None:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def score_item(item: dict, reply: str) -> Tuple[bool, str]:
    kind = item["answer_kind"]
    if kind == "classification":
        got = parse_classification(reply)
        want = str(item["ground_truth"]).lower()
        return got == want, f"got={got!r} want={want!r}"
    if kind == "numeric":
        got = parse_numeric(reply)
        want = float(item["ground_truth"])
        tol = float(item.get("tolerance", 0.05))
        if got is None:
            return False, f"no number found in reply (want={want:.4g})"
        if want == 0:
            ok = abs(got) <= tol
        else:
            ok = abs(got - want) / abs(want) <= tol
        return ok, f"got={got:.4g} want={want:.4g} rel_err={abs(got-want)/(abs(want) or 1):.2%}"
    return False, f"unknown answer_kind {kind!r}"


@dataclass
class ItemResult:
    id: str
    domain: str
    task: str
    correct: bool
    reply: str
    detail: str


@dataclass
class BenchResult:
    label: str
    items: List[ItemResult] = field(default_factory=list)

    def summary(self) -> str:
        n = len(self.items)
        c = sum(1 for r in self.items if r.correct)
        out = [f"=== {self.label}: {c}/{n} = {c/n:.1%} ==="]
        # per-domain
        by_domain: Dict[str, List[ItemResult]] = {}
        for r in self.items:
            by_domain.setdefault(r.domain, []).append(r)
        for d in sorted(by_domain):
            rs = by_domain[d]
            cd = sum(1 for r in rs if r.correct)
            out.append(f"  {d:12s}  {cd:3d}/{len(rs):3d} = {cd/len(rs):.1%}")
        return "\n".join(out)

    def to_jsonl(self, path: Path) -> None:
        with path.open("w") as f:
            for r in self.items:
                f.write(json.dumps({
                    "id": r.id, "domain": r.domain, "task": r.task,
                    "correct": r.correct, "reply": r.reply, "detail": r.detail,
                }) + "\n")


def load_items(path: Path = ITEMS_PATH):
    items = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def run(completion_fn: CompletionFn, label: str = "completion",
        items_path: Path = ITEMS_PATH,
        system_prompt: str | None = None,
        verbose: bool = False) -> BenchResult:
    """Run the completion fn over every benchmark item and score."""
    items = load_items(items_path)
    result = BenchResult(label=label)
    sys_msg = system_prompt or (
        "You are answering benchmark questions. Follow the format requested in "
        "each prompt exactly: a single word for yes/no questions, or a single "
        "decimal number for numeric questions. Do not add explanation."
    )
    for it in items:
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": it["prompt"]},
        ]
        try:
            reply = completion_fn(messages)
        except Exception as e:
            reply = f"[completion error: {e}]"
        ok, detail = score_item(it, reply)
        result.items.append(ItemResult(
            id=it["id"], domain=it["domain"], task=it["task"],
            correct=ok, reply=reply, detail=detail,
        ))
        if verbose:
            mark = "OK" if ok else "FAIL"
            print(f"  [{mark}] {it['id']:10s} {detail}")
    return result


def stub_completion(messages):
    """Smoke-test stub: always answers 'yes' and 0.05.

    For yes/no items it gets ~half right by coin-flip.
    For numeric items it'll be way off — that's the point of a baseline.
    """
    user = next((m for m in messages if m["role"] == "user"), {}).get("content", "")
    if "yes or no" in user:
        return "yes"
    return "0.05"


def main():
    result = run(stub_completion, label="stub", verbose=True)
    print()
    print(result.summary())


if __name__ == "__main__":
    main()
