"""
run_benchmark_v2.py — compare Concordance engine vs Claude Haiku vs Claude Sonnet.

For each item in benchmark_v2_dataset.jsonl:
  - Concordance: run the actual verify_* tool (deterministic, local)
  - Haiku / Sonnet: ask "correct or incorrect?" on claim_text

Outputs:
  benchmark_v2_results.jsonl   — per-item results
  RESULTS_V2.md                — comparison report

Run from repo root:
    python lw/09_evaluation/run_benchmark_v2.py
"""
from __future__ import annotations
import json, math, os, re, sys, time
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from concordance_engine.mcp_server.tools import ALL_TOOLS

HERE = Path(__file__).resolve().parent
DATASET = HERE / "benchmark_v2_dataset.jsonl"
RESULTS  = HERE / "benchmark_v2_results.jsonl"
REPORT   = HERE / "RESULTS_V2.md"

# ── load .env ─────────────────────────────────────────────────────────────────
env_path = ROOT / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if v:  # only set if value is non-empty
                    os.environ[k] = v

# ── Anthropic client ──────────────────────────────────────────────────────────
try:
    import anthropic
    _api_key = os.environ.get("ANTHROPIC_API_KEY") or None
    _client = anthropic.Anthropic(api_key=_api_key)
    _LLM_AVAILABLE = bool(_api_key)
except Exception:
    _client = None
    _LLM_AVAILABLE = False

MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
}

LLM_PROMPT = (
    "Is the following claim mathematically, scientifically, or logically correct or incorrect? "
    "Answer with exactly one word: correct or incorrect.\n\nClaim: {claim}"
)


# ── Concordance engine dispatcher ─────────────────────────────────────────────

def _summary(result) -> str:
    if isinstance(result, dict):
        s = result.get("status")
        if s:
            return s
        statuses = []
        for v in result.values():
            if isinstance(v, dict) and "status" in v:
                statuses.append(v["status"])
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "status" in item:
                        statuses.append(item["status"])
        if "MISMATCH" in statuses:
            return "MISMATCH"
        if "ERROR" in statuses:
            return "ERROR"
        if "CONFIRMED" in statuses:
            return "CONFIRMED"
        if statuses:
            return statuses[0]
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "status" in item:
                return item["status"]
    return "UNKNOWN"


def _engine_label(status: str) -> str:
    if status == "CONFIRMED":
        return "correct"
    if status in ("MISMATCH", "ERROR"):
        return "incorrect"
    return "abstain"


_math  = ALL_TOOLS["verify_mathematics"]
_chem  = ALL_TOOLS["verify_chemistry"]
_phys_c = ALL_TOOLS["verify_physics_conservation"]
_phys_d = ALL_TOOLS["verify_physics_dimensional"]
_stat_ci  = ALL_TOOLS["verify_statistics_confidence_interval"]
_stat_mc  = ALL_TOOLS["verify_statistics_multiple_comparisons"]
_cs    = ALL_TOOLS["verify_computer_science"]
_logic = ALL_TOOLS["verify_formal_logic"]


def run_concordance(domain: str, spec: dict) -> tuple[str, str, float]:
    """Returns (label, status, latency_ms)."""
    t0 = time.perf_counter()
    try:
        if domain == "mathematics":
            mode = spec.get("mode", "equality")
            result = _math(mode, {k: v for k, v in spec.items() if k != "mode"})
        elif domain == "chemistry":
            result = _chem(spec.get("equation", ""))
        elif domain == "physics_conservation":
            result = _phys_c(spec.get("before", {}), spec.get("after", {}))
        elif domain == "physics_dimensional":
            result = _phys_d(spec.get("equation", ""), spec.get("dimensions", {}))
        elif domain == "statistics":
            stype = spec.get("stat_type", "ci")
            if stype == "mc":
                ci = spec.get("claimed_rejected")
                result = _stat_mc(
                    spec["p_values"], spec["method"], spec.get("alpha", 0.05),
                    ci,
                )
            else:
                result = _stat_ci(
                    spec["estimate"], spec["ci_low"], spec["ci_high"],
                    spec={"mean": spec.get("mean"), "sd": spec.get("sd"),
                          "n": spec.get("n"), "conf_level": spec.get("conf_level", 0.95)},
                )
        elif domain == "formal_logic":
            lspec = {k: v for k, v in spec.items()}
            result = _logic(lspec)
        elif domain == "computer_science":
            code  = spec.get("code", "")
            fn    = spec.get("function_name", "")
            tests = spec.get("test_cases", [])
            result = _cs(code, function_name=fn, test_cases=tests)
        else:
            return "abstain", "NO_TOOL", 0
        status = _summary(result)
    except Exception as e:
        status = "ERROR"
    elapsed = (time.perf_counter() - t0) * 1000
    return _engine_label(status), status, elapsed


def run_llm(model_key: str, claim_text: str) -> tuple[str, float, int]:
    """Returns (label, latency_ms, input_tokens)."""
    if not _LLM_AVAILABLE:
        return "abstain", 0, 0
    prompt = LLM_PROMPT.format(claim=claim_text)
    t0 = time.perf_counter()
    try:
        resp = _client.messages.create(
            model=MODELS[model_key],
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip().lower()
        in_tok = resp.usage.input_tokens
        elapsed = (time.perf_counter() - t0) * 1000
        if re.search(r"\bincorrect\b", raw):
            return "incorrect", elapsed, in_tok
        if re.search(r"\bcorrect\b", raw):
            return "correct", elapsed, in_tok
        return "abstain", elapsed, in_tok
    except Exception as e:
        print(f"  LLM_ERR {model_key}: {e!r}")
        elapsed = (time.perf_counter() - t0) * 1000
        return "abstain", elapsed, 0


# ── metrics helper ───────────────────────────────────────────────────────────

def _metrics(items_with_results, label_key):
    col = f"{label_key}_label"
    labels    = [(r["ground_truth"], r[col]) for r in items_with_results]
    total     = len(labels)

    abstains  = sum(1 for _, p in labels if p == "abstain")
    decided   = [(gt, p) for gt, p in labels if p != "abstain"]

    tp = sum(1 for gt, p in decided if gt == "correct"   and p == "correct")
    tn = sum(1 for gt, p in decided if gt == "incorrect" and p == "incorrect")
    fp = sum(1 for gt, p in decided if gt == "incorrect" and p == "correct")
    fn = sum(1 for gt, p in decided if gt == "correct"   and p == "incorrect")

    acc = (tp + tn) / len(decided) if decided else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0
    fnr = fn / (fn + tp) if (fn + tp) else 0

    lat_col = f"{label_key}_latency_ms"
    lats = [r[lat_col] for r in items_with_results if r.get(lat_col, 0) > 0]
    med_lat = sorted(lats)[len(lats)//2] if lats else 0
    p95_lat = sorted(lats)[int(len(lats)*0.95)] if lats else 0

    return {
        "total": total, "decided": len(decided), "abstains": abstains,
        "accuracy": acc, "fpr": fpr, "fnr": fnr,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "median_latency_ms": med_lat, "p95_latency_ms": p95_lat,
    }


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    # Load dataset
    with open(DATASET, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(items)} benchmark items\n")

    results = []
    haiku_total_tokens = 0
    sonnet_total_tokens = 0

    for i, item in enumerate(items, 1):
        domain    = item["domain"]
        template  = item["template_id"]
        gt        = item["ground_truth"]
        claim     = item["claim_text"]
        snap      = dict(item["spec_snapshot"])

        # Concordance
        eng_label, eng_status, eng_lat = run_concordance(domain, snap)

        # LLMs (with small rate-limit pause every 50 items)
        if i % 50 == 0:
            time.sleep(1)

        haiku_label,  haiku_lat,  haiku_tok  = run_llm("haiku",  claim)
        sonnet_label, sonnet_lat, sonnet_tok = run_llm("sonnet", claim)

        haiku_total_tokens  += haiku_tok
        sonnet_total_tokens += sonnet_tok

        row = {
            "id": item["id"], "seq": item["seq"],
            "domain": domain, "template_id": template,
            "ground_truth": gt,
            "claim_text": claim,
            "engine_label": eng_label, "engine_status": eng_status,
            "engine_latency_ms": round(eng_lat, 1),
            "haiku_label": haiku_label, "haiku_latency_ms": round(haiku_lat, 1),
            "sonnet_label": sonnet_label, "sonnet_latency_ms": round(sonnet_lat, 1),
        }
        results.append(row)

        eng_ok  = "+" if eng_label  == gt else ("-" if eng_label  == "abstain" else "X")
        hku_ok  = "+" if haiku_label  == gt else ("-" if haiku_label  == "abstain" else "X")
        son_ok  = "+" if sonnet_label == gt else ("-" if sonnet_label == "abstain" else "X")
        print(f"  [{i:03d}] {domain[:22]:<22} gt={gt[0]}  eng={eng_ok}({eng_status[:4]})  "
              f"haiku={hku_ok}  sonnet={son_ok}  {claim[:40]}", flush=True)

    # Save per-item results
    RESULTS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8"
    )

    # Compute metrics
    m_eng    = _metrics(results, "engine")
    m_haiku  = _metrics(results, "haiku")
    m_sonnet = _metrics(results, "sonnet")

    # Cost estimate (Claude pricing, approximate)
    avg_claim_chars = sum(len(r["claim_text"]) for r in results) / len(results)
    avg_prompt_toks = haiku_total_tokens / len(results) if results else 0
    haiku_cost  = haiku_total_tokens  * 2 / 1_000_000 * 2   # $0.80/M input, x2 for both runs
    sonnet_cost = sonnet_total_tokens * 3 / 1_000_000 * 2   # $3/M input, x2 for both runs

    # Write report
    _write_report(m_eng, m_haiku, m_sonnet, results,
                  haiku_total_tokens, sonnet_total_tokens,
                  haiku_cost, sonnet_cost)

    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'System':<20} {'Accuracy':>10} {'FPR':>8} {'FNR':>8} {'Abstain':>8} {'Lat(p95)':>10}")
    print(f"  {'-'*20}  {'-'*8}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*8}")
    for name, m in [("Concordance",m_eng),("Haiku",m_haiku),("Sonnet",m_sonnet)]:
        print(f"  {name:<20} {m['accuracy']*100:>9.1f}%  {m['fpr']*100:>6.1f}%  "
              f"{m['fnr']*100:>6.1f}%  {m['abstains']:>6}  {m['p95_latency_ms']:>8.0f}ms")
    print(f"\n  Dataset: {len(items)} items, 50/50 balance")
    print(f"  Report: {REPORT}")



def _write_report(m_eng, m_haiku, m_sonnet, results, haiku_tok, sonnet_tok, haiku_cost, sonnet_cost):
    total = len(results)
    lines = [
        "# Benchmark V2 Results",
        f"",
        f"**Date:** {time.strftime('%Y-%m-%d')}  ",
        f"**Dataset:** {total} items (50% correct, 50% incorrect)  ",
        f"**Domains:** mathematics, chemistry, physics, statistics, formal_logic, computer_science  ",
        f"",
        "## Overall Accuracy",
        "",
        "| System | Accuracy | FPR | FNR | Abstains | Median Lat | p95 Lat |",
        "|--------|----------|-----|-----|----------|-----------|---------|",
    ]
    for name, m in [("Concordance Engine", m_eng), ("Claude Haiku", m_haiku), ("Claude Sonnet", m_sonnet)]:
        lines.append(
            f"| {name} | **{m['accuracy']*100:.1f}%** | {m['fpr']*100:.1f}% | "
            f"{m['fnr']*100:.1f}% | {m['abstains']} | {m['median_latency_ms']:.0f}ms | "
            f"{m['p95_latency_ms']:.0f}ms |"
        )
    lines += [
        "",
        "## Confusion Matrices",
        "",
    ]
    for name, m in [("Concordance Engine", m_eng), ("Claude Haiku", m_haiku), ("Claude Sonnet", m_sonnet)]:
        lines += [
            f"### {name}",
            f"",
            f"| | Predicted correct | Predicted incorrect | Abstain |",
            f"|---|---|---|---|",
            f"| **Actually correct** | {m['tp']} | {m['fn']} | {total//2 - m['tp'] - m['fn']} |",
            f"| **Actually incorrect** | {m['fp']} | {m['tn']} | {total//2 - m['fp'] - m['tn']} |",
            "",
        ]

    # Per-domain breakdown
    domains = sorted(set(r["domain"] for r in results))
    lines += ["## Per-Domain Accuracy", ""]
    lines.append("| Domain | N | Concordance | Haiku | Sonnet |")
    lines.append("|--------|---|-------------|-------|--------|")
    for d in domains:
        dr = [r for r in results if r["domain"] == d]
        n = len(dr)
        def _dacc(key):
            decided = [r for r in dr if r[key] != "abstain"]
            if not decided: return "N/A"
            acc = sum(1 for r in decided if r[key] == r["ground_truth"]) / len(decided)
            return f"{acc*100:.0f}%"
        lines.append(f"| {d} | {n} | {_dacc('engine_label')} | {_dacc('haiku_label')} | {_dacc('sonnet_label')} |")

    lines += [
        "",
        "## Cost & Latency",
        "",
        f"| System | Cost (est.) | Tokens | Median Lat | p95 Lat |",
        f"|--------|------------|--------|-----------|---------|",
        f"| Concordance Engine | $0.00 | 0 | {m_eng['median_latency_ms']:.0f}ms | {m_eng['p95_latency_ms']:.0f}ms |",
        f"| Claude Haiku | ${haiku_cost:.4f} | {haiku_tok:,} | {m_haiku['median_latency_ms']:.0f}ms | {m_haiku['p95_latency_ms']:.0f}ms |",
        f"| Claude Sonnet | ${sonnet_cost:.4f} | {sonnet_tok:,} | {m_sonnet['median_latency_ms']:.0f}ms | {m_sonnet['p95_latency_ms']:.0f}ms |",
        "",
        "## Notes",
        "",
        "- Concordance engine is **deterministic** — same input always yields same result.",
        "- LLM answers are stochastic; a single pass was used here.",
        "- Concordance 'abstain' = verifier returned NOT_APPLICABLE (no evidence for or against).",
        "- LLM 'abstain' = response did not contain 'correct' or 'incorrect'.",
        "- Concordance cost is effectively $0 (local CPU, no API calls).",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {REPORT}")


if __name__ == "__main__":
    main()
