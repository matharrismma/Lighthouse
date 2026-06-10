#!/usr/bin/env python3
"""run_benchmark.py — measure how the mechanism compares to unfiltered generation.

For every prompt in the eval set, run TWO modes:
  - baseline: direct call to the base LLM (no gates, no verifiers)
  - gated:    full pipeline (RED -> LLM -> verifiers -> FLOOR -> BROTHERS -> GOD)

Score both against per-prompt expectations (healthy markers, concerning patterns,
expected RED-rejection, citation minimums). Aggregate metrics across the set:
  - Hallucination proxy: model produced concerning patterns in adversarial prompts
  - Citation accuracy: prompts requiring scripture got valid citations
  - Doctrinal alignment: expected_healthy markers actually present
  - Adversarial reject rate: RED gate caught what it should have
  - Latency overhead: gated_latency - baseline_latency
  - Cost overhead: gated_cost - baseline_cost

Output: data/benchmark/runs/<stamp>/ containing
  - results.jsonl           — one line per prompt with both modes' responses
  - aggregate.json          — summary stats
  - run_manifest.json       — provenance (model, mechanism version, eval set)

Usage:
    python tools/run_benchmark.py                          # full run
    python tools/run_benchmark.py --limit 5                # smoke test 5 prompts
    python tools/run_benchmark.py --category adversarial   # one category
    python tools/run_benchmark.py --base echo              # no API calls
    python tools/run_benchmark.py --dry-run                # don't write
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
EVAL_PATH = REPO_ROOT / "data" / "eval" / "prompts_v1.jsonl"
RUNS_DIR = REPO_ROOT / "data" / "benchmark" / "runs"
LOG_DIR = REPO_ROOT / "logs"

sys.path.insert(0, str(REPO_ROOT))

# Load .env directly — python-dotenv chokes on the operator's .env (which has
# embedded PowerShell snippets). This loader only treats lines matching
# KEY=value with a clean KEY pattern, ignoring everything else.
def _load_env_robust(env_path: Path) -> int:
    if not env_path.exists():
        return 0
    loaded = 0
    import re as _re
    key_re = _re.compile(r"^[A-Z][A-Z0-9_]*$")
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not key_re.match(k):
            continue
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or \
           (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        # Don't override real (non-empty) env vars, but DO fill in
        # ones that are present-but-empty (Windows shell often does this)
        if not os.environ.get(k):
            os.environ[k] = v
            loaded += 1
    return loaded


_load_env_robust(REPO_ROOT / ".env")


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.benchmark")
    logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "benchmark.log",
        maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(sh)
    return logger


log = _setup_logging()


def load_prompts(category: str | None = None, limit: int | None = None) -> list[dict]:
    if not EVAL_PATH.exists():
        raise FileNotFoundError(f"eval set missing: {EVAL_PATH}")
    out: list[dict] = []
    with EVAL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if category and row.get("category") != category:
                continue
            out.append(row)
    if limit:
        out = out[:limit]
    return out


def _make_adapter(base_name: str):
    """Resolve the base-model adapter from a CLI string.

    Supported:
      anthropic              - Anthropic Claude (DEFAULT_ANTHROPIC_MODEL)
      echo                   - echo adapter (no API)
      local                  - most recently registered local model
      local:<model_id>       - specific local model from data/models/registry.json
    """
    from api.generate_gated import (
        AnthropicAdapter, EchoAdapter, LocalModelAdapter,
    )
    name = base_name.strip()
    low = name.lower()
    if low == "echo":
        return EchoAdapter()
    if low == "anthropic":
        return AnthropicAdapter()
    if low.startswith("local"):
        model_id = name.split(":", 1)[1].strip() if ":" in name else ""
        registry_path = REPO_ROOT / "data" / "models" / "registry.json"
        if not registry_path.exists():
            raise RuntimeError("no model registry yet — train + register a model first")
        reg = json.loads(registry_path.read_text(encoding="utf-8"))
        models = reg.get("models", [])
        if not models:
            raise RuntimeError("registry is empty")
        chosen = None
        if model_id:
            for m in models:
                if m.get("id") == model_id or m.get("training_run") == model_id:
                    chosen = m
                    break
            if not chosen:
                known = [f"{m.get('id')} (run={m.get('training_run')})" for m in models]
                raise RuntimeError(
                    f"local model not found: {model_id}\n"
                    f"  known models: {known}"
                )
        else:
            chosen = sorted(models, key=lambda m: m.get("registered_at", ""), reverse=True)[0]
        adapter_path = (REPO_ROOT / chosen.get("adapter_path", "")) if chosen.get("adapter_path") else None
        log.info("using local model %s (%s)", chosen["id"], chosen["base_model"])
        return LocalModelAdapter(
            model_id=chosen["base_model"],
            adapter_path=str(adapter_path) if adapter_path else None,
            backend=chosen.get("backend", "hf"),
        )
    raise RuntimeError(f"unknown base name: {name}")


def run_baseline(prompt: str, base_name: str = "anthropic"):
    """Call the base LLM directly — no gates, no verifiers. Mirrors what an
    unfiltered LLM call returns."""
    adapter = _make_adapter(base_name)
    gen = adapter.generate(prompt)
    return {
        "mode": "baseline",
        "model": gen.model,
        "text": gen.text,
        "tokens_in": gen.tokens_in,
        "tokens_out": gen.tokens_out,
        "latency_ms": gen.latency_ms,
        "cost_usd": gen.cost_usd,
    }


def run_gated_mode(prompt: str, base_name: str = "anthropic"):
    """Call the full mechanism — RED -> LLM -> verifiers -> FLOOR -> BROTHERS -> GOD."""
    from api.generate_gated import run_gated
    adapter = _make_adapter(base_name)
    resp = run_gated(prompt, base=adapter)
    return {"mode": "gated", "response": resp}


def score_pair(prompt_row: dict, baseline: dict, gated: dict) -> dict:
    """Per-prompt scoring against the prompt's expected markers."""
    cat = prompt_row.get("category", "")
    expected_healthy = set(prompt_row.get("expected_healthy") or [])
    expected_concerning = set(prompt_row.get("expected_concerning") or [])
    expected_cite_min = int(prompt_row.get("expected_citations_min") or 0)
    expected_red_reject = bool(prompt_row.get("expected_red_reject"))

    gated_resp = gated.get("response") or {}
    gen = (gated_resp.get("generation") or {})
    gated_text = gen.get("text", "")
    baseline_text = baseline.get("text", "")

    verifier_results = gated_resp.get("verifier_results") or []
    scripture_v = next(
        (v for v in verifier_results if v.get("verifier") == "scripture_anchors"),
        {},
    )
    doctrine_v = next(
        (v for v in verifier_results if v.get("verifier") == "theology_doctrine"),
        {},
    )

    # Count citations in BOTH responses (run our extractor over them)
    from api.generate_gated import extract_citations, scan_doctrine_keywords
    baseline_cites = extract_citations(baseline_text)
    gated_cites = scripture_v.get("details") or extract_citations(gated_text)

    baseline_doctrine = scan_doctrine_keywords(baseline_text)
    gated_doctrine = doctrine_v.get("details") or scan_doctrine_keywords(gated_text)

    def has_tag(hits, tag):
        return any(h.get("tag") == tag for h in (hits or []))

    # Score each axis
    score = {
        # 1. RED-rejection correctness (adversarial only)
        "red_rejection_correct": None,
        # 2. Citation accuracy
        "baseline_citations": len(baseline_cites),
        "gated_citations": len(gated_cites),
        "citations_meet_min_baseline": len(baseline_cites) >= expected_cite_min,
        "citations_meet_min_gated": len(gated_cites) >= expected_cite_min,
        # 3. Healthy marker presence
        "baseline_healthy_present": sorted([t for t in expected_healthy if has_tag(baseline_doctrine, t)]),
        "gated_healthy_present": sorted([t for t in expected_healthy if has_tag(gated_doctrine, t)]),
        "baseline_healthy_missed": sorted([t for t in expected_healthy if not has_tag(baseline_doctrine, t)]),
        "gated_healthy_missed": sorted([t for t in expected_healthy if not has_tag(gated_doctrine, t)]),
        # 4. Concerning pattern detection (we WANT the engine to surface these)
        "baseline_concerning_surfaced": sorted([t for t in expected_concerning if has_tag(baseline_doctrine, t)]),
        "gated_concerning_surfaced": sorted([t for t in expected_concerning if has_tag(gated_doctrine, t)]),
        "baseline_concerning_missed": sorted([t for t in expected_concerning if not has_tag(baseline_doctrine, t)]),
        "gated_concerning_missed": sorted([t for t in expected_concerning if not has_tag(gated_doctrine, t)]),
        # 5. Audit completeness
        "gated_has_trail": bool(gated_resp.get("trail")),
        "gated_has_hash": bool(gated_resp.get("content_hash")),
        "gated_final_decision": gated_resp.get("final_decision"),
        # 6. Latency / cost
        "baseline_latency_ms": round(baseline.get("latency_ms", 0), 1),
        "gated_total_latency_ms": round(gated_resp.get("metrics", {}).get("total_latency_ms", 0), 1),
        "gated_overhead_ms": round(
            gated_resp.get("metrics", {}).get("total_latency_ms", 0)
            - baseline.get("latency_ms", 0), 1
        ),
        "baseline_cost_usd": round(baseline.get("cost_usd", 0), 4),
        "gated_cost_usd": round(gated_resp.get("metrics", {}).get("total_cost_usd", 0), 4),
    }

    # RED-rejection: for adversarial prompts marked expected_red_reject
    if cat == "adversarial":
        gate_results = gated_resp.get("gate_results") or []
        red = next((g for g in gate_results if g.get("gate") == "RED"), None)
        red_rejected = red and red.get("decision") == "reject"
        if expected_red_reject:
            score["red_rejection_correct"] = bool(red_rejected)
        else:
            score["red_rejection_correct"] = not red_rejected  # should NOT reject

    return score


def aggregate(scored_rows: list[dict]) -> dict:
    """Compute aggregate metrics across the run."""
    n = len(scored_rows)
    if not n:
        return {"n": 0}

    by_category: dict[str, list[dict]] = {}
    for r in scored_rows:
        by_category.setdefault(r.get("category", "unknown"), []).append(r)

    # Aggregate functions
    def avg(rows, key):
        vals = [r["score"].get(key, 0) or 0 for r in rows]
        return round(sum(vals) / max(len(vals), 1), 2)

    def pct(rows, key):
        vals = [bool(r["score"].get(key)) for r in rows]
        return round(100 * sum(vals) / max(len(vals), 1), 1)

    out = {
        "n": n,
        "by_category": {k: len(v) for k, v in by_category.items()},
        "overall": {
            "avg_baseline_latency_ms": avg(scored_rows, "baseline_latency_ms"),
            "avg_gated_latency_ms": avg(scored_rows, "gated_total_latency_ms"),
            "avg_overhead_ms": avg(scored_rows, "gated_overhead_ms"),
            "total_baseline_cost_usd": round(
                sum(r["score"]["baseline_cost_usd"] for r in scored_rows), 4
            ),
            "total_gated_cost_usd": round(
                sum(r["score"]["gated_cost_usd"] for r in scored_rows), 4
            ),
            "pct_with_audit_trail": pct(scored_rows, "gated_has_trail"),
            "pct_with_content_hash": pct(scored_rows, "gated_has_hash"),
        },
        "doctrinal": {},
        "factual": {},
        "adversarial": {},
    }

    # Per-category metrics
    for cat in ("doctrinal", "factual", "adversarial"):
        rows = by_category.get(cat, [])
        if not rows:
            continue
        out[cat]["n"] = len(rows)
        out[cat]["pct_citations_meet_min_baseline"] = pct(rows, "citations_meet_min_baseline")
        out[cat]["pct_citations_meet_min_gated"] = pct(rows, "citations_meet_min_gated")
        out[cat]["healthy_markers_caught_baseline"] = sum(
            len(r["score"].get("baseline_healthy_present") or []) for r in rows
        )
        out[cat]["healthy_markers_caught_gated"] = sum(
            len(r["score"].get("gated_healthy_present") or []) for r in rows
        )
        out[cat]["concerning_patterns_surfaced_baseline"] = sum(
            len(r["score"].get("baseline_concerning_surfaced") or []) for r in rows
        )
        out[cat]["concerning_patterns_surfaced_gated"] = sum(
            len(r["score"].get("gated_concerning_surfaced") or []) for r in rows
        )
        if cat == "adversarial":
            red_correct = [r for r in rows if r["score"].get("red_rejection_correct") is True]
            red_attempted = [r for r in rows if r["score"].get("red_rejection_correct") is not None]
            out[cat]["red_rejection_correct_pct"] = round(
                100 * len(red_correct) / max(len(red_attempted), 1), 1
            )

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the mechanism benchmark")
    ap.add_argument("--limit", type=int, default=0,
                    help="Limit number of prompts (0 = all)")
    ap.add_argument("--category", default="",
                    help="Filter: doctrinal | factual | adversarial")
    ap.add_argument("--base", default="anthropic",
                    help="Base model adapter: anthropic | echo (no API)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't write results")
    args = ap.parse_args()

    cat = args.category or None
    limit = args.limit or None
    prompts = load_prompts(category=cat, limit=limit)
    log.info(
        "benchmark start | n=%d | base=%s | category=%s",
        len(prompts), args.base, cat or "(all)",
    )
    if not prompts:
        log.error("no prompts loaded — check %s", EVAL_PATH)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / stamp
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
        results_path = run_dir / "results.jsonl"
        results_fh = results_path.open("w", encoding="utf-8")
    else:
        results_fh = None

    started = time.time()
    scored_rows: list[dict] = []
    try:
        for i, row in enumerate(prompts, 1):
            pid = row.get("id", f"p-{i}")
            prompt = row.get("prompt", "")
            log.info("[%d/%d] %s · %s", i, len(prompts), pid, prompt[:60])

            try:
                base = run_baseline(prompt, base_name=args.base)
            except Exception as e:
                log.warning("baseline failed for %s: %s", pid, e)
                base = {"mode": "baseline", "error": str(e)[:300]}

            try:
                gated = run_gated_mode(prompt, base_name=args.base)
            except Exception as e:
                log.warning("gated failed for %s: %s", pid, e)
                gated = {"mode": "gated", "error": str(e)[:300]}

            score = score_pair(row, base, gated)

            row_out = {
                "id": pid,
                "category": row.get("category"),
                "prompt": prompt,
                "expected": {
                    "healthy": row.get("expected_healthy"),
                    "concerning": row.get("expected_concerning"),
                    "citations_min": row.get("expected_citations_min"),
                    "red_reject": row.get("expected_red_reject"),
                },
                "baseline": base,
                "gated": gated,
                "score": score,
            }
            scored_rows.append(row_out)
            if results_fh:
                results_fh.write(json.dumps(row_out, ensure_ascii=False) + "\n")
                results_fh.flush()
    finally:
        if results_fh:
            results_fh.close()

    agg = aggregate(scored_rows)
    elapsed = round(time.time() - started, 1)
    agg["wall_seconds"] = elapsed
    agg["stamp"] = stamp
    agg["base"] = args.base
    agg["eval_set"] = str(EVAL_PATH.name)

    if not args.dry_run:
        (run_dir / "aggregate.json").write_text(
            json.dumps(agg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        manifest = {
            "schema": "narrowhighway.benchmark_run/1",
            "stamp": stamp,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_model": args.base,
            "category_filter": cat or "(all)",
            "limit": limit,
            "wall_seconds": elapsed,
            "eval_set": str(EVAL_PATH.name),
            "files": ["results.jsonl", "aggregate.json"],
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Also publish the latest to site/benchmark/latest/ so /benchmark.html
        # can fetch the results as static files (no engine endpoint required).
        latest_dir = REPO_ROOT / "site" / "benchmark" / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / "aggregate.json").write_text(
            json.dumps(agg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (latest_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Public results — trim to the fields the page renders + cap text to keep file small
        public_results = [
            {
                "id": r["id"],
                "category": r["category"],
                "prompt": r["prompt"],
                "expected": r["expected"],
                "baseline_text": (r["baseline"].get("text") or "")[:1200],
                "baseline_model": r["baseline"].get("model", ""),
                "gated_text": (
                    ((r["gated"].get("response") or {}).get("generation") or {})
                    .get("text") or ""
                )[:1200],
                "gated_final_decision": (r["gated"].get("response") or {}).get("final_decision"),
                "gated_gate_results": (r["gated"].get("response") or {}).get("gate_results") or [],
                "gated_verifier_results": (r["gated"].get("response") or {}).get("verifier_results") or [],
                "score": r["score"],
            }
            for r in scored_rows
        ]
        with (latest_dir / "results.jsonl").open("w", encoding="utf-8") as f:
            for r in public_results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log.info("published latest results to site/benchmark/latest/")

    log.info("=" * 60)
    log.info("BENCHMARK COMPLETE | n=%d | wall=%.1fs", len(scored_rows), elapsed)
    log.info("overall: %s", json.dumps(agg["overall"], indent=2))
    for cat_name in ("doctrinal", "factual", "adversarial"):
        if cat_name in agg and agg[cat_name]:
            log.info("%s: %s", cat_name, json.dumps(agg[cat_name], indent=2))
    if not args.dry_run:
        log.info("wrote: %s", run_dir)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("benchmark interrupted")
        sys.exit(130)
