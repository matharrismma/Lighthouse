"""Run the Polymathic synthesis benchmark.

Tests cross-domain synthesis: _run_cluster + axis-weight computation +
weighted composite verdict.  No oracle API calls — domain specs are
pre-classified in items_poly.jsonl.

Usage:
    python eval/benchmark/run_poly.py
    python eval/benchmark/run_poly.py --diagnose
    python eval/benchmark/run_poly.py --build    # regenerate items first
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

ITEMS_PATH = THIS.parent / "items_poly.jsonl"


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class PolyItemResult:
    id: str
    label: str
    expected: str
    actual: str
    correct: bool
    elapsed_s: float
    domain_results: List[Dict[str, Any]] = field(default_factory=list)
    axis_overlaps: List[str] = field(default_factory=list)
    axis_weights: Dict[str, float] = field(default_factory=dict)
    overlap_check: Optional[bool] = None   # None = not checked
    detail: str = ""


@dataclass
class PolyBenchResult:
    items: List[PolyItemResult] = field(default_factory=list)

    def summary(self) -> str:
        total = len(self.items)
        if total == 0:
            return "No items."
        correct = sum(r.correct for r in self.items)
        elapsed = sum(r.elapsed_s for r in self.items)
        lines = [
            f"\n{'='*60}",
            f"  Polymathic Synthesis Benchmark",
            f"  Total:   {correct}/{total} = {correct/total:.1%}",
            f"  Elapsed: {elapsed:.2f}s",
            f"{'─'*60}",
        ]
        # by expected verdict
        by_verdict: Dict[str, list] = {}
        for r in self.items:
            by_verdict.setdefault(r.expected, []).append(r)
        for v in sorted(by_verdict):
            rs = by_verdict[v]
            ok = sum(r.correct for r in rs)
            marker = "+" if ok == len(rs) else ("x" if ok == 0 else "~")
            lines.append(f"  {marker} {v:12s}: {ok}/{len(rs)}")
        # overlap checks
        overlap_checked = [r for r in self.items if r.overlap_check is not None]
        if overlap_checked:
            ok2 = sum(r.overlap_check for r in overlap_checked)
            lines.append(f"  Axis-overlap checks: {ok2}/{len(overlap_checked)}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)

    def diagnose(self) -> str:
        failures = [r for r in self.items if not r.correct]
        if not failures:
            return "  All items correct.\n"
        lines = [f"\n  FAILURES ({len(failures)}):", "─" * 60]
        for r in failures:
            lines.append(f"  [{r.id}] {r.label}")
            lines.append(f"    expected : {r.expected!r}")
            lines.append(f"    actual   : {r.actual!r}")
            if r.axis_weights:
                lines.append(f"    weights  : {r.axis_weights}")
            for dr in r.domain_results:
                lines.append(f"    worker   : {dr['domain']:22s} → {dr['verdict']:15s} {dr['detail'][:55]}")
            if r.detail:
                lines.append(f"    note     : {r.detail}")
            lines.append("")
        return "\n".join(lines)

    def to_jsonl(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            for r in self.items:
                f.write(json.dumps({
                    "id": r.id, "label": r.label,
                    "expected": r.expected, "actual": r.actual,
                    "correct": r.correct, "elapsed_s": round(r.elapsed_s, 3),
                    "axis_weights": r.axis_weights,
                    "axis_overlaps": r.axis_overlaps,
                    "overlap_check": r.overlap_check,
                    "domain_results": [
                        {"domain": d["domain"], "verdict": d["verdict"],
                         "detail": d["detail"][:100]}
                        for d in r.domain_results
                    ],
                }, ensure_ascii=False) + "\n")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_item(item: dict) -> PolyItemResult:
    """Run one synthesis item. No oracle; uses pre-classified domain specs."""
    from concordance_engine.agent.poly_agent import _run_cluster, _extract_verdict
    from concordance_engine.poly_record import (
        compute_axis_overlaps,
        compute_axis_weights,
        compute_weighted_composite_verdict,
    )
    from concordance_engine.mcp_server.tools import ALL_TOOLS

    t0 = time.monotonic()

    domain_specs: List[dict] = item.get("domain_specs", [])
    quarantined:  List[str]  = item.get("quarantined_claims", [])
    expected:     str        = item["expected_verdict"]

    # Fire workers
    results = _run_cluster(domain_specs, ALL_TOOLS)

    # Compute overlaps + weighted verdict
    axis_overlaps = compute_axis_overlaps(results)
    axis_weights  = compute_axis_weights(results)
    actual        = compute_weighted_composite_verdict(
        results,
        weights=axis_weights,
        quarantined_claims=quarantined or None,
    )

    elapsed = time.monotonic() - t0

    # Optional axis-overlap check
    expected_dims = item.get("expected_axis_overlaps")
    overlap_ok: Optional[bool] = None
    if expected_dims is not None:
        actual_dims = {ao.dimension for ao in axis_overlaps}
        overlap_ok = all(d in actual_dims for d in expected_dims)

    # Domain result summaries for reporting
    dr_summary = [
        {"domain": r.domain, "verdict": r.verdict,
         "detail": r.detail, "weight": axis_weights.get(r.domain, 0)}
        for r in results
    ]

    return PolyItemResult(
        id=item["id"],
        label=item["label"],
        expected=expected,
        actual=actual,
        correct=(actual == expected),
        elapsed_s=elapsed,
        domain_results=dr_summary,
        axis_overlaps=[ao.dimension for ao in axis_overlaps],
        axis_weights=axis_weights,
        overlap_check=overlap_ok,
        detail=item.get("notes", ""),
    )


def run_benchmark(items: List[dict]) -> PolyBenchResult:
    result = PolyBenchResult()
    total = len(items)
    for i, item in enumerate(items, 1):
        r = run_item(item)
        result.items.append(r)
        marker = "+" if r.correct else "x"
        overlap_flag = ""
        if r.overlap_check is not None:
            overlap_flag = " [overlap✓]" if r.overlap_check else " [overlap✗]"
        workers = ",".join(f"{d['domain']}:{d['verdict'][:2]}"
                           for d in r.domain_results) or "(none)"
        print(f"  [{i:2d}/{total}] {marker} {item['id']:10s}  "
              f"exp={r.expected:13s} got={r.actual:13s}  "
              f"{r.elapsed_s:.2f}s{overlap_flag}")
        if not r.correct or r.domain_results:
            print(f"          workers: {workers}")
    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build",   action="store_true",
                        help="(re)generate items_poly.jsonl first")
    parser.add_argument("--diagnose", action="store_true",
                        help="print failure details after run")
    parser.add_argument("--out", default=None,
                        help="write results JSONL to this path")
    args = parser.parse_args()

    if args.build:
        import subprocess
        subprocess.run([sys.executable,
                        str(THIS.parent / "build_poly_items.py")], check=True)

    if not ITEMS_PATH.exists():
        print("items_poly.jsonl not found — run with --build first.",
              file=sys.stderr)
        sys.exit(1)

    items = [json.loads(l) for l in ITEMS_PATH.read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    print(f"Loaded {len(items)} items from {ITEMS_PATH.name}")
    print(f"{'='*60}")

    bench = run_benchmark(items)

    print(bench.summary())

    if args.diagnose:
        print(bench.diagnose())

    out_path = Path(args.out) if args.out else (THIS.parent / "results_poly.jsonl")
    bench.to_jsonl(out_path)
    print(f"Results written to {out_path.name}")


if __name__ == "__main__":
    main()
