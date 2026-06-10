"""Audience demand breakdown — who reaches for what.

Matt's product north star: don't make people like what we like — build what AI
agents, bots, AND people actually want and use most. The access log already records
path + ua_class per request, so we can ask, per audience category: what are they
reaching for? Which tool is the demand magnet? Which tools are starved? Then we
improve the magnet and lift the starved ones toward it.

Read-only. Runs on the box over data/visits/access-*.jsonl. No writes.

Usage:
  python tools/audience_breakdown.py [--days N] [--top K]
"""
from __future__ import annotations
import argparse
import collections
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

_VISITS = Path(__file__).resolve().parent.parent / "data" / "visits"


def _norm(path: str) -> str:
    """Collapse a request path to a 'tool': strip the query, keep the first two
    segments, fold the deep/variable tail to /* so per-card / per-ref URLs group."""
    p = (path or "/").split("?", 1)[0].split("#", 1)[0]
    if p in ("", "/"):
        return "/"
    segs = [s for s in p.split("/") if s]
    if len(segs) <= 2:
        return "/" + "/".join(segs)
    return "/" + "/".join(segs[:2]) + "/*"


def _load(days: int | None):
    files = sorted(_VISITS.glob("access-*.jsonl"))
    if days:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days - 1))
        keep = []
        for f in files:
            stem = f.stem.replace("access-", "")
            try:
                d = datetime.strptime(stem, "%Y%m%d").date()
            except ValueError:
                continue
            if d >= cutoff:
                keep.append(f)
        files = keep
    rows = []
    for f in files:
        for ln in f.read_text("utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="limit to last N days (0 = all)")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    rows = _load(args.days or None)
    if not rows:
        print("no visit data")
        return 1

    window = f"last {args.days} days" if args.days else "all-time"
    by_class = collections.Counter(r.get("ua_class") or "other" for r in rows)
    print(f"=== AUDIENCE COMPOSITION ({window}, {len(rows):,} requests) ===")
    for cls, n in by_class.most_common():
        print(f"  {cls:16} {n:>8,}  ({100*n/len(rows):4.1f}%)")

    print(f"\n=== WHAT EACH CATEGORY REACHES FOR (top {args.top} tools) ===")
    for cls, _ in by_class.most_common():
        sub = [r for r in rows if (r.get("ua_class") or "other") == cls]
        tools = collections.Counter(_norm(r.get("path", "")) for r in sub)
        print(f"\n-- {cls}  ({len(sub):,} requests) --")
        for tool, n in tools.most_common(args.top):
            print(f"   {n:>7,}  {tool}")

    print(f"\n=== TOP TOOLS OVERALL + who reaches for each ===")
    tools_all = collections.Counter(_norm(r.get("path", "")) for r in rows)
    for tool, n in tools_all.most_common(args.top + 6):
        mix = collections.Counter((r.get("ua_class") or "other")
                                  for r in rows if _norm(r.get("path", "")) == tool)
        mixs = ", ".join(f"{c}:{m}" for c, m in mix.most_common(4))
        print(f"  {n:>7,}  {tool:28} [{mixs}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
