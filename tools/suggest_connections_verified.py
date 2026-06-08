"""suggest_connections_verified.py — VERIFIED connection discovery.

Unlike suggest_connections.py (heuristic Jaccard token overlap), this proposes a
connection ONLY where two cards demonstrably cite the SAME scripture reference
(book chapter:verse). That is a verifiable link, not a guess — it preserves the
trust moat (verified, not generated connections) and is high enough confidence to
approve in bulk.

Writes data/rebalance/verified_connections.json in the same `suggestions_by_card`
shape as the heuristic queue, plus method='shared_scripture_ref' and evidence (the
shared verses). The review surface (GET /connections/suggested, cards-dev.html)
reads both queues and tags each by method.

Usage:
  python tools/suggest_connections_verified.py             # dry-run summary
  python tools/suggest_connections_verified.py --apply     # write the queue
  python tools/suggest_connections_verified.py --k 3 --max-per-verse 25
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

CARDS_DIR = REPO / "data" / "cards"
OUT = REPO / "data" / "rebalance" / "verified_connections.json"
CONTENT_KINDS = {"note", "walk"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_ref(ref: str):
    """Canonicalize a scripture ref to a verse-level dedup key: <num><book3> c:v.
    'Romans 8:28' and 'Rom 8:28' both -> 'rom 8:28'. Chapter-only refs are dropped
    (too coarse to be a precise verified link)."""
    m = re.match(r'\s*([1-3])?\s*([A-Za-z]+)\s*(\d+:\d+(?:-\d+)?)\s*$', ref.strip())
    if not m:
        return None
    num = m.group(1) or ""
    book = m.group(2).lower()[:3]
    return f"{num}{book} {m.group(3)}"


def _connection_graph():
    """Map card_id -> set(neighbor ids) from existing kind=connection cards, so we
    never re-propose an edge that already exists."""
    graph = defaultdict(set)
    for f in CARDS_DIR.glob("card_c_*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        ex = c.get("extra") or {}
        l, r = ex.get("left_card_id"), ex.get("right_card_id")
        if l and r:
            graph[l].add(r)
            graph[r].add(l)
    return graph


def main() -> int:
    ap = argparse.ArgumentParser(description="Verified shared-scripture connection discovery")
    ap.add_argument("--k", type=int, default=3, help="max suggestions per card")
    ap.add_argument("--max-per-verse", type=int, default=25,
                    help="ignore verses cited by more than this many cards (too common to be a precise link)")
    ap.add_argument("--apply", action="store_true", help="write the queue")
    args = ap.parse_args()

    from concordance_engine.scripture_retrieval import _REF_PATTERN

    card_refs = {}      # cid -> set(verse keys)
    title = {}          # cid -> title
    shelf = {}          # cid -> shelf
    verse_cards = defaultdict(set)   # verse key -> set(cids)

    for f in CARDS_DIR.glob("card_n_*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("kind") not in CONTENT_KINDS:
            continue
        cid = c.get("id")
        text = (c.get("title") or "") + " " + (c.get("body") or "")
        refs = set()
        for m in _REF_PATTERN.finditer(text):
            k = _norm_ref(m.group(0))
            if k:
                refs.add(k)
        if not refs:
            continue
        card_refs[cid] = refs
        title[cid] = (c.get("title") or "")[:90]
        shelf[cid] = c.get("shelf") or "?"
        for k in refs:
            verse_cards[k].add(cid)

    # drop over-common verses (John 3:16 everywhere -> not a precise pairwise link)
    common = {v for v, cids in verse_cards.items() if len(cids) > args.max_per_verse}
    graph = _connection_graph()

    # for each card, score neighbors by # shared (non-common) verses
    suggestions_by_card = {}
    total_pairs = 0
    for cid, refs in card_refs.items():
        neigh_score = defaultdict(int)
        neigh_evidence = defaultdict(list)
        for v in refs:
            if v in common:
                continue
            for other in verse_cards.get(v, ()):
                if other == cid or other in graph.get(cid, set()):
                    continue
                neigh_score[other] += 1
                if len(neigh_evidence[other]) < 4:
                    neigh_evidence[other].append(v)
        if not neigh_score:
            continue
        ranked = sorted(neigh_score.items(), key=lambda kv: -kv[1])[:args.k]
        sugg = []
        for other, score in ranked:
            sugg.append({
                "to_card_id": other,
                "to_title": title.get(other, ""),
                "to_shelf": shelf.get(other, "?"),
                "relationship_suggested": "parallels",
                "method": "shared_scripture_ref",
                "evidence": neigh_evidence[other],
                "shared_count": score,
                "score": round(min(1.0, 0.5 + 0.25 * score), 3),
            })
        if sugg:
            suggestions_by_card[cid] = {"card_title": title.get(cid, ""), "shelf": shelf.get(cid, "?"),
                                        "suggestions": sugg}
            total_pairs += len(sugg)

    payload = {"generated_at": _now(), "method": "shared_scripture_ref",
               "max_per_verse": args.max_per_verse,
               "suggestions_by_card": suggestions_by_card}
    print(f"[verified] {len(card_refs)} cards carry verse refs; "
          f"{len(verse_cards)} distinct verses ({len(common)} too-common, ignored); "
          f"{len(suggestions_by_card)} cards get suggestions; {total_pairs} verified pairs.")
    if args.apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[verified] wrote {OUT}")
    else:
        print("[verified] DRY RUN — pass --apply to write the queue.")
        ex = next(iter(suggestions_by_card.items()), None)
        if ex:
            cid, info = ex
            s = info["suggestions"][0]
            print(f"  example: {info['card_title'][:40]} -> {s['to_title'][:40]} "
                  f"(shares {s['shared_count']}: {s['evidence']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
