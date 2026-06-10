"""intake_train.py — Nightly job that learns from interviews.

Walks the interview-card archive and surfaces:
  - which clarifying questions accelerated convergence
  - which queries drop off (operator backlog signal — these are the things to
    build cards for next)
  - audience patterns (kids? sermons? family worship?)
  - tradition lens patterns (1689? WCF?)

Writes a weekly report to data/intake/training_report.md that the operator
reads to decide what to acquire/build.

This is the user experience continuously training the intake — but read-only:
the report surfaces signals; the operator decides what to act on. We never
silently rewrite the Interviewer's rules.

Usage:
    python tools/intake_train.py            # generate report from all interviews
    python tools/intake_train.py --days 7   # last week only
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INTERVIEWS_DIR = REPO / "data" / "quarantine" / "interviews"
REPORT_DIR = REPO / "data" / "intake"
REPORT_PATH = REPORT_DIR / "training_report.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_all(days: int | None):
    if not INTERVIEWS_DIR.exists():
        return
    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for f in INTERVIEWS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if cutoff:
            try:
                created = datetime.fromisoformat(c.get("created_at", "").replace("Z", "+00:00"))
                if created < cutoff:
                    continue
            except Exception:
                pass
        yield c


def analyze(days: int | None = None) -> dict:
    interviews = list(_load_all(days))
    total = len(interviews)
    outcomes = Counter()
    audiences = Counter()
    traditions = Counter()
    abandoned_queries = []
    converged_queries = []
    followups_for_converged = []
    ask_kinds_in_converged = Counter()
    ask_kinds_in_abandoned = Counter()

    for c in interviews:
        ex = c.get("extra", {})
        outcome = ex.get("outcome", "in_progress")
        outcomes[outcome] += 1
        audiences[ex.get("audience") or "unknown"] += 1
        traditions[ex.get("tradition") or "unspecified"] += 1
        q = ex.get("query", "")
        if outcome == "ready_to_walk":
            converged_queries.append(q)
            followups_for_converged.append(ex.get("followups_asked", 0))
            for t in ex.get("turns", []):
                if t.get("role") == "shepherd" and t.get("ask_kind"):
                    ask_kinds_in_converged[t["ask_kind"]] += 1
        elif outcome in ("abandoned", "in_progress"):
            abandoned_queries.append({
                "query": q,
                "outcome": outcome,
                "followups": ex.get("followups_asked", 0),
                "created_at": c.get("created_at", ""),
            })
            for t in ex.get("turns", []):
                if t.get("role") == "shepherd" and t.get("ask_kind"):
                    ask_kinds_in_abandoned[t["ask_kind"]] += 1

    avg_followups = round(sum(followups_for_converged) / len(followups_for_converged), 2) if followups_for_converged else 0
    convergence_rate = round(outcomes["ready_to_walk"] / total, 3) if total else None

    return {
        "ran_at": _now(),
        "days": days,
        "total_interviews": total,
        "outcomes": dict(outcomes),
        "convergence_rate": convergence_rate,
        "avg_followups_for_converged": avg_followups,
        "audiences": dict(audiences),
        "traditions": dict(traditions),
        "ask_kinds_in_converged": dict(ask_kinds_in_converged),
        "ask_kinds_in_abandoned": dict(ask_kinds_in_abandoned),
        "abandoned_queries": sorted(abandoned_queries, key=lambda x: x["created_at"], reverse=True)[:30],
    }


def render_report(a: dict) -> str:
    lines = []
    lines.append("# Intake training report")
    lines.append(f"\n_Generated {a['ran_at']}_ · Window: {('last ' + str(a['days']) + ' days') if a['days'] else 'all time'}\n")
    lines.append("## Summary")
    lines.append(f"- **Total interviews:** {a['total_interviews']}")
    if a["convergence_rate"] is not None:
        lines.append(f"- **Convergence rate:** {a['convergence_rate']*100:.1f}% (the fraction that reached `ready_to_walk`)")
    lines.append(f"- **Avg follow-ups before walk:** {a['avg_followups_for_converged']}")
    lines.append("\n### Outcomes")
    for o, n in sorted(a["outcomes"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{o}`: {n}")

    lines.append("\n### Audiences our users bring")
    for k, v in sorted(a["audiences"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")

    lines.append("\n### Tradition lens distribution")
    for k, v in sorted(a["traditions"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")

    lines.append("\n## What Shepherd asked")
    lines.append("\n### In conversations that converged to a walk")
    for k, v in sorted(a["ask_kinds_in_converged"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")
    lines.append("\n### In conversations that dropped off")
    for k, v in sorted(a["ask_kinds_in_abandoned"].items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")

    lines.append("\n## Operator backlog — queries that didn't converge")
    lines.append("\nThese are the things the library is missing. Each one is a hint about what to acquire or build next.\n")
    if not a["abandoned_queries"]:
        lines.append("_No abandoned queries this window. The library is keeping up._")
    else:
        for q in a["abandoned_queries"]:
            lines.append(f"- `{q['outcome']}` after {q['followups']} follow-up(s) — \"{q['query']}\" ({q['created_at'][:10]})")

    lines.append("\n## Standing principle")
    lines.append("\nThe operator reads this report and decides what to build next. The Interviewer's rules are not auto-mutated. This report is signal; the human is the steering.\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None, help="Only consider interviews from the last N days")
    parser.add_argument("--print-only", action="store_true", help="Print report; don't write")
    args = parser.parse_args()
    a = analyze(args.days)
    report = render_report(a)
    if args.print_only:
        print(report)
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"=== Intake training report written ===")
    print(f"Path: {REPORT_PATH}")
    print(f"Total interviews analyzed: {a['total_interviews']}")
    print(f"Convergence rate: {a['convergence_rate']*100 if a['convergence_rate'] else 0:.1f}%")
    print(f"Operator backlog items: {len(a['abandoned_queries'])}")


if __name__ == "__main__":
    main()
