"""Run the Concordance Engine against the 722-claim benchmark dataset.

Phase 2 driver script. Reads `benchmark_dataset.jsonl`, dispatches each claim
to the matching engine verifier, and records:

  - claim id, domain, template_id, ground_truth label
  - verifier verdict (CONFIRMED / MISMATCH / ERROR / NOT_APPLICABLE)
  - latency in milliseconds
  - the diagnosis string the verifier returned

Outputs:
  - benchmark_results.jsonl    (one record per claim)
  - benchmark_summary.json     (aggregate metrics)

Invocation (from the repo root):
    python 09_evaluation/run_benchmark.py

The script self-locates the engine at ../01_engine/concordance-engine/src
relative to this file. No engine install is required as long as Python can
import sympy, scipy, and numpy.
"""
from __future__ import annotations

import json
import os
import statistics as _stats
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the engine and dataset relative to this script.

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
# Canonical engine lives at <repo root>/src; the older lw/01_engine tree is being retired.
ENGINE_SRC = REPO_ROOT.parent / "src"
DATASET = HERE / "benchmark_dataset.jsonl"
# Fallback: if the dataset isn't next to this script (e.g. running from
# OneDrive copy where the JSONL was never copied across), look in the
# original Downloads location.
if not DATASET.is_file():
    _fallback = Path(r"C:\Users\hdven\Downloads\lw\09_evaluation\benchmark_dataset.jsonl")
    if _fallback.is_file():
        DATASET = _fallback
        sys.stderr.write(f"note: using dataset from {DATASET}\n")
RESULTS_FILE = HERE / "benchmark_results.jsonl"
SUMMARY_FILE = HERE / "benchmark_summary.json"

if not ENGINE_SRC.is_dir():
    sys.stderr.write(f"ERROR: cannot find engine source at {ENGINE_SRC}\n")
    sys.exit(2)
sys.path.insert(0, str(ENGINE_SRC))

try:
    from concordance_engine.verifiers import (  # noqa: E402
        chemistry as _vf_chemistry,
        physics as _vf_physics,
        mathematics as _vf_mathematics,
        statistics as _vf_statistics,
        computer_science as _vf_cs,
        biology as _vf_biology,
        governance as _vf_governance,
    )
except Exception as e:
    sys.stderr.write(f"ERROR: failed to import concordance_engine: {e}\n")
    sys.stderr.write("Make sure sympy, scipy, and numpy are installed:\n")
    sys.stderr.write("  pip install sympy scipy numpy\n")
    sys.exit(2)


def run_for_domain(domain: str, packet: dict) -> list:
    """Dispatch a packet to the correct verifier module's run(packet) -> list."""
    d = (domain or "").lower()
    if d == "chemistry":
        return _vf_chemistry.run(packet)
    if d == "physics":
        return _vf_physics.run(packet)
    if d == "mathematics":
        return _vf_mathematics.run(packet)
    if d == "statistics":
        return _vf_statistics.run(packet)
    if d in ("computer_science", "cs"):
        return _vf_cs.run(packet)
    if d == "biology":
        return _vf_biology.run(packet)
    if d in ("governance", "business", "household", "education", "church"):
        return _vf_governance.run(packet)
    return []


# ---------------------------------------------------------------------------
# Build a packet from a benchmark row.

def build_packet(row: dict) -> dict:
    """Wrap the row's metadata into the engine's packet shape for that domain."""
    domain = (row.get("domain") or "").lower()
    md = dict(row.get("metadata") or {})

    if domain == "statistics":
        return {"STAT_VERIFY": md}
    if domain == "chemistry":
        return {"CHEM_VERIFY": md}
    if domain == "physics":
        return {"PHYS_VERIFY": md}
    if domain == "mathematics":
        return {"MATH_VERIFY": md}
    if domain in ("computer_science", "cs"):
        return {"CS_VERIFY": md}
    if domain in ("governance", "business", "household", "education", "church"):
        # Governance puts DECISION_PACKET (and witness_count) at the packet root
        return dict(md)
    # Unknown domain — pass metadata through anyway so the verifier reports NA
    return dict(md)


# ---------------------------------------------------------------------------
# Reduce a list of VerifierResults to a single (verdict, diagnosis).

VERDICT_RANK = {
    "ERROR": 3,         # malformed input — surfaces above CONFIRMED for visibility
    "MISMATCH": 4,      # the strongest signal (verifier rejects)
    "CONFIRMED": 2,
    "NOT_APPLICABLE": 1,
}


def collapse(results) -> tuple[str, str]:
    """Return (verdict, diagnosis_string) summarizing a list of VerifierResult."""
    if not results:
        return "NOT_APPLICABLE", "(no verifier results)"
    # Pick MISMATCH > ERROR > CONFIRMED > NA, since for benchmark "did the
    # engine reject the claim?" is what we care about. ERROR also counts as
    # "rejected" for accuracy, but we report it separately in the breakdown.
    statuses = [r.status for r in results]
    if "MISMATCH" in statuses:
        verdict = "MISMATCH"
    elif "ERROR" in statuses:
        verdict = "ERROR"
    elif "CONFIRMED" in statuses:
        verdict = "CONFIRMED"
    else:
        verdict = "NOT_APPLICABLE"
    # Concatenate non-NA details (the loud results)
    parts = []
    for r in results:
        if r.status != "NOT_APPLICABLE":
            parts.append(f"[{r.name}|{r.status}] {r.detail}")
    if not parts:
        parts.append("(all checks NOT_APPLICABLE)")
    return verdict, " || ".join(parts)


# ---------------------------------------------------------------------------
# Decide whether a verdict matches the ground-truth label.

def is_correct_decision(ground_truth: str, verdict: str) -> bool:
    """correct claim should be CONFIRMED; incorrect claim should be MISMATCH/ERROR."""
    gt = (ground_truth or "").lower()
    if gt == "correct":
        return verdict == "CONFIRMED"
    if gt == "incorrect":
        return verdict in ("MISMATCH", "ERROR")
    return False  # unknown label


# ---------------------------------------------------------------------------
# Main loop.

def main():
    rows = []
    with DATASET.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:
                sys.stderr.write(f"warn: line {line_no} parse error: {e}\n")
    n = len(rows)
    print(f"loaded {n} claims from {DATASET}")

    out = []
    t0_total = time.perf_counter()
    last_progress = 0
    for i, row in enumerate(rows, start=1):
        cid = row.get("id")
        domain = (row.get("domain") or "").lower()
        gt = row.get("ground_truth")
        template = row.get("template_id")

        packet = build_packet(row)
        t0 = time.perf_counter()
        try:
            results = run_for_domain(domain, packet)
            verdict, diagnosis = collapse(results)
            err = None
        except Exception as e:
            verdict = "ERROR"
            diagnosis = f"runner exception: {type(e).__name__}: {e}"
            err = traceback.format_exc()
        latency_ms = (time.perf_counter() - t0) * 1000.0

        rec = {
            "id": cid,
            "domain": domain,
            "template_id": template,
            "ground_truth": gt,
            "verdict": verdict,
            "latency_ms": round(latency_ms, 4),
            "diagnosis": diagnosis,
            "is_correct_decision": is_correct_decision(gt, verdict),
            "perturbation_type": row.get("perturbation_type"),
        }
        if err:
            rec["traceback"] = err
        out.append(rec)

        # progress every ~5%
        if i - last_progress >= max(1, n // 20):
            elapsed = time.perf_counter() - t0_total
            print(f"  [{i:>4}/{n}] {elapsed:6.1f}s elapsed  (last: {cid} -> {verdict})")
            last_progress = i

    total_s = time.perf_counter() - t0_total
    print(f"finished in {total_s:.1f}s")

    # Write per-claim results
    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec) + "\n")
    print(f"wrote {RESULTS_FILE}")

    # Compute aggregate metrics
    summary = compute_metrics(out)
    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {SUMMARY_FILE}")

    # Print top-line numbers
    print()
    print(f"OVERALL ACCURACY: {summary['overall']['accuracy_pct']:.1f}%  "
          f"({summary['overall']['correct_decisions']}/{summary['overall']['n']})")
    print(f"  false-positive rate (correct rejected): "
          f"{summary['overall']['false_positive_rate']*100:.1f}%")
    print(f"  false-negative rate (incorrect confirmed): "
          f"{summary['overall']['false_negative_rate']*100:.1f}%")
    print(f"  median latency: {summary['overall']['latency_ms_median']:.1f} ms  "
          f"p95: {summary['overall']['latency_ms_p95']:.1f} ms")
    print(f"  NOT_APPLICABLE: {summary['overall']['not_applicable_pct']:.1f}%  "
          f"  ERROR: {summary['overall']['error_pct']:.1f}%")
    print()
    print(f"{'domain':<20} {'n':>4} {'acc%':>6} {'FP%':>6} {'FN%':>6} {'p50ms':>8} {'p95ms':>8} {'NA%':>6}")
    for d, m in summary["by_domain"].items():
        print(f"{d:<20} {m['n']:>4} {m['accuracy_pct']:>6.1f} "
              f"{m['false_positive_rate']*100:>6.1f} {m['false_negative_rate']*100:>6.1f} "
              f"{m['latency_ms_median']:>8.1f} {m['latency_ms_p95']:>8.1f} "
              f"{m['not_applicable_pct']:>6.1f}")


def _percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def compute_metrics(records):
    by_domain: dict[str, list] = {}
    for r in records:
        by_domain.setdefault(r["domain"], []).append(r)

    def block(rs):
        n = len(rs)
        if n == 0:
            return {}
        latencies = [r["latency_ms"] for r in rs]
        correct_rs = [r for r in rs if r["ground_truth"] == "correct"]
        incorrect_rs = [r for r in rs if r["ground_truth"] == "incorrect"]
        n_correct_decisions = sum(1 for r in rs if r["is_correct_decision"])
        # FP = correct claim wrongly rejected (verdict in MISMATCH/ERROR)
        fp = sum(1 for r in correct_rs if r["verdict"] in ("MISMATCH", "ERROR"))
        # FN = incorrect claim wrongly confirmed
        fn = sum(1 for r in incorrect_rs if r["verdict"] == "CONFIRMED")
        na = sum(1 for r in rs if r["verdict"] == "NOT_APPLICABLE")
        err = sum(1 for r in rs if r["verdict"] == "ERROR")
        verdict_breakdown = {}
        for r in rs:
            verdict_breakdown[r["verdict"]] = verdict_breakdown.get(r["verdict"], 0) + 1
        return {
            "n": n,
            "n_correct_claims": len(correct_rs),
            "n_incorrect_claims": len(incorrect_rs),
            "correct_decisions": n_correct_decisions,
            "accuracy_pct": 100.0 * n_correct_decisions / n,
            "false_positive_rate": (fp / len(correct_rs)) if correct_rs else 0.0,
            "false_negative_rate": (fn / len(incorrect_rs)) if incorrect_rs else 0.0,
            "false_positive_count": fp,
            "false_negative_count": fn,
            "not_applicable_count": na,
            "not_applicable_pct": 100.0 * na / n,
            "error_count": err,
            "error_pct": 100.0 * err / n,
            "latency_ms_median": _stats.median(latencies),
            "latency_ms_p95": _percentile(latencies, 95),
            "latency_ms_max": max(latencies),
            "verdict_breakdown": verdict_breakdown,
        }

    return {
        "overall": block(records),
        "by_domain": {d: block(rs) for d, rs in sorted(by_domain.items())},
    }


if __name__ == "__main__":
    main()
