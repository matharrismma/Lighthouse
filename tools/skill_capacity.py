#!/usr/bin/env python3
"""skill_capacity.py — "build capacity based on need."

Reads the demand signals (captured seeds/queries) and the supply
(existing skill maps' trigger keywords). Finds query clusters that NO
existing skill covers, and proposes them as candidate skills to build.

Deterministic + free (no API). Designed to run in the daily gather cycle.
Output is a review queue the operator pulls from — nothing auto-builds.

Demand sources (best-effort, whichever exist):
    data/seeds/seeds.jsonl        — captured queries (/capture writes here)
    data/discernments/*.json      — gated-generation prompts (slugs)
    data/walks/*.jsonl            — walk queries

Supply:
    data/skills/*.json            — each map's triggers.keywords + title tokens

Output:
    data/skills/_capacity_proposals.json
        {"generated": "...", "covered_skills": N, "uncovered_clusters": [
            {"theme": "...", "sample_queries": [...], "size": N,
             "suggested_skill_title": "...", "domains": [...]}
        ]}

Usage:
    python tools/skill_capacity.py            # analyze + write proposals
    python tools/skill_capacity.py --dry-run  # print, don't write
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent)
)).resolve()
SKILLS_DIR = REPO_ROOT / "data" / "skills"
SEEDS = REPO_ROOT / "data" / "seeds" / "seeds.jsonl"
DISCERN_DIR = REPO_ROOT / "data" / "discernments"
PROPOSALS = SKILLS_DIR / "_capacity_proposals.json"

STOP = set("the a an of to and or in on for is are be with how what why when "
           "do does can i we you it that this from as at by my your our".split())


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in STOP}


def load_supply() -> tuple[set, int]:
    """Return (covered keyword set, skill count)."""
    covered, n = set(), 0
    if not SKILLS_DIR.exists():
        return covered, 0
    for p in SKILLS_DIR.glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        n += 1
        covered |= {k.lower() for k in m.get("triggers", {}).get("keywords", [])}
        covered |= _tokens(m.get("title", ""))
        for pr in m.get("protocols", []):
            covered |= _tokens(pr.get("title", ""))
    return covered, n


def load_demand() -> list:
    """Return list of {query, domains} from captured signals."""
    out = []
    if SEEDS.exists():
        for line in SEEDS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            q = o.get("query") or o.get("title") or ""
            if q:
                out.append({"query": q, "domains": o.get("domains", [])})
    if DISCERN_DIR.exists():
        for p in list(DISCERN_DIR.glob("*.json"))[:2000]:
            try:
                o = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            q = (o.get("prompt", {}) or {}).get("text") if isinstance(o.get("prompt"), dict) else o.get("prompt")
            if q:
                out.append({"query": q, "domains": o.get("domains", [])})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Propose skills to build, based on demand")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-cluster", type=int, default=2,
                    help="Minimum uncovered queries sharing a theme to propose")
    args = ap.parse_args()

    covered, n_skills = load_supply()
    demand = load_demand()

    # Find uncovered queries: those whose tokens barely overlap covered keywords
    uncovered = []
    for d in demand:
        toks = _tokens(d["query"])
        if not toks:
            continue
        overlap = len(toks & covered) / max(1, len(toks))
        if overlap < 0.34:   # <34% of the query's words are covered by any skill
            uncovered.append({**d, "tokens": toks})

    # Cluster uncovered queries by their most distinctive shared token
    theme_buckets = defaultdict(list)
    global_tok_freq = Counter()
    for u in uncovered:
        global_tok_freq.update(u["tokens"])
    for u in uncovered:
        # pick the rarest meaningful token as the theme anchor
        anchor = min(u["tokens"], key=lambda t: global_tok_freq[t]) if u["tokens"] else None
        if anchor:
            theme_buckets[anchor].append(u)

    clusters = []
    for theme, items in sorted(theme_buckets.items(), key=lambda kv: -len(kv[1])):
        if len(items) < args.min_cluster:
            continue
        domains = Counter()
        for it in items:
            domains.update(it.get("domains", []))
        clusters.append({
            "theme": theme,
            "size": len(items),
            "sample_queries": [it["query"] for it in items[:5]],
            "domains": [d for d, _ in domains.most_common(4)],
            "suggested_skill_title": f"{theme.title()} — capability map",
        })

    result = {
        "schema": "narrowhighway.capacity_proposals/1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "covered_skills": n_skills,
        "demand_queries_seen": len(demand),
        "uncovered_queries": len(uncovered),
        "uncovered_clusters": clusters,
        "note": "Operator reviews. Each cluster is a candidate skill to build "
                "where queries cluster and no current skill covers them.",
    }

    print(f"[capacity] skills={n_skills} demand={len(demand)} "
          f"uncovered={len(uncovered)} clusters={len(clusters)}")
    for c in clusters[:8]:
        print(f"   - '{c['theme']}' x{c['size']}: {c['sample_queries'][:2]}")

    if not args.dry_run:
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        PROPOSALS.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[capacity] wrote {PROPOSALS.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
