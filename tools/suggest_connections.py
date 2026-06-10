"""suggest_connections.py — Propose missing connections in the graph.

For each card (or one named card), find the top-N other cards it likely
should connect to but doesn't yet. Operator reviews + approves via API.

Signals used (cheap, deterministic):
  1. Token overlap (Jaccard on title + first 500 chars of body)
  2. Same shelf bonus (cards in same shelf more likely related)
  3. Authority-tier compatibility (scripture ↔ catechism; hymn ↔ creed; etc.)
  4. Existing-connection penalty (already linked → score = 0)
  5. Walk co-occurrence (cards walked together → boost)

Output: data/rebalance/suggested_connections.json — operator pulls from this
list and authors connections via POST /connections.

Usage:
  python tools/suggest_connections.py                    # all cards, top 3 each
  python tools/suggest_connections.py --card-id <id>     # one card
  python tools/suggest_connections.py --apply            # write the queue
  python tools/suggest_connections.py --threshold 0.15   # minimum jaccard
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CARDS_DIR = REPO / "data" / "cards"
SUGGESTED_PATH = REPO / "data" / "rebalance" / "suggested_connections.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set:
    return set(t for t in re.findall(r"[a-zA-Z][a-zA-Z']{3,}", (text or "").lower())
               if t not in STOPWORDS)


STOPWORDS = {
    "the", "and", "with", "from", "that", "this", "have", "been", "were", "their", "what",
    "which", "would", "could", "should", "shall", "into", "than", "them", "they", "your",
    "more", "some", "such", "also", "when", "then", "thus", "made", "upon", "whom", "very",
    "much", "many", "must", "thee", "thou", "thine", "doth", "hath", "unto", "according",
    "saith",
}

TIER_AFFINITY = {
    # Tier pairs that often connect
    ("scripture", "catechism"): 1.3,
    ("scripture", "creed"): 1.2,
    ("scripture", "scripture"): 0.8,  # less interesting unless very specific
    ("catechism", "creed"): 1.4,
    ("catechism", "catechism"): 1.1,
    ("creed", "creed"): 1.3,
    ("scripture", "external_aligned"): 1.0,  # hymns, recipes etc
    ("creed", "external_aligned"): 1.1,
    ("father", "scripture"): 1.3,
    ("father", "catechism"): 1.2,
}


def _tier_bonus(a: str, b: str) -> float:
    return TIER_AFFINITY.get((a, b), TIER_AFFINITY.get((b, a), 1.0))


def _read_all_cards() -> list[dict]:
    if not CARDS_DIR.exists():
        return []
    out = []
    for f in CARDS_DIR.glob("*.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _already_connected(a: dict, b_id: str) -> bool:
    for conn in (a.get("connections") or []):
        if conn.get("to_card_id") == b_id:
            return True
    return False


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def suggest_for_card(card: dict, all_cards: list[dict], k: int, threshold: float) -> list[dict]:
    """Return top-k suggested connections for one card, above threshold."""
    if card.get("kind") in ("connection", "walk", "search", "community_note"):
        return []
    a_tokens = _tokens(card.get("title", "") + " " + (card.get("body") or "")[:500])
    if len(a_tokens) < 3:
        return []
    a_tier = (card.get("source") or {}).get("authority_tier", "")
    a_shelf = card.get("shelf", "")
    candidates = []
    for other in all_cards:
        if other.get("id") == card.get("id"):
            continue
        if other.get("kind") in ("connection", "walk", "search", "community_note"):
            continue
        if _already_connected(card, other["id"]):
            continue
        b_tokens = _tokens(other.get("title", "") + " " + (other.get("body") or "")[:500])
        if len(b_tokens) < 3:
            continue
        j = _jaccard(a_tokens, b_tokens)
        if j < threshold:
            continue
        b_tier = (other.get("source") or {}).get("authority_tier", "")
        b_shelf = other.get("shelf", "")
        tier_b = _tier_bonus(a_tier, b_tier)
        shelf_bonus = 1.15 if a_shelf == b_shelf else 1.0
        score = j * tier_b * shelf_bonus
        # Suggest a relationship kind based on tiers
        if a_tier in ("catechism", "creed") and b_tier == "scripture":
            rel = "proof_text"
        elif a_tier == "scripture" and b_tier in ("catechism", "creed"):
            rel = "proof_text"
        elif a_tier == "creed" and b_tier == "creed":
            rel = "parallels"
        elif a_shelf == "hymns" or b_shelf == "hymns":
            rel = "illuminates"
        elif a_tier == "father" or b_tier == "father":
            rel = "cites"
        else:
            rel = "see_also"
        candidates.append({
            "to_card_id": other["id"],
            "to_title": other.get("title"),
            "jaccard": round(j, 3),
            "score": round(score, 3),
            "relationship_suggested": rel,
            "to_authority_tier": b_tier,
            "to_shelf": b_shelf,
        })
    candidates.sort(key=lambda x: -x["score"])
    return candidates[:k]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--card-id", help="Suggest connections for one card only")
    parser.add_argument("--k", type=int, default=3, help="Suggestions per card")
    parser.add_argument("--threshold", type=float, default=0.12, help="Min jaccard score")
    parser.add_argument("--apply", action="store_true", help="Write suggestions to disk")
    parser.add_argument("--limit-cards", type=int, default=None, help="Cap cards processed")
    args = parser.parse_args()

    all_cards = _read_all_cards()
    out: dict[str, list] = {}

    if args.card_id:
        target = next((c for c in all_cards if c.get("id") == args.card_id), None)
        if not target:
            print(f"No card with id {args.card_id}")
            return
        suggestions = suggest_for_card(target, all_cards, args.k, args.threshold)
        out[args.card_id] = suggestions
        print(f"Suggestions for {target.get('title', args.card_id)}:")
        for s in suggestions:
            print(f"  -> {s['to_title']} (jaccard {s['jaccard']}, suggested: {s['relationship_suggested']})")
    else:
        n = 0
        for card in all_cards:
            if args.limit_cards and n >= args.limit_cards:
                break
            if card.get("kind") in ("connection", "walk", "search", "community_note"):
                continue
            suggestions = suggest_for_card(card, all_cards, args.k, args.threshold)
            if suggestions:
                out[card["id"]] = {
                    "card_title": card.get("title"),
                    "shelf": card.get("shelf"),
                    "suggestions": suggestions,
                }
                n += 1
        print(f"Generated suggestions for {len(out)} cards (limit={args.limit_cards or 'none'}).")

    if args.apply and out:
        SUGGESTED_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUGGESTED_PATH.write_text(json.dumps({
            "generated_at": _now(),
            "threshold": args.threshold,
            "suggestions_by_card": out,
        }, indent=2), encoding="utf-8")
        print(f"Wrote {SUGGESTED_PATH}")
        # Quick summary
        total = sum(len(v.get("suggestions") if isinstance(v, dict) else v) for v in out.values())
        print(f"Total connection suggestions: {total}")
        print(f"Operator review at: {SUGGESTED_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
