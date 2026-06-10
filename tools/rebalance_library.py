"""rebalance_library.py — The Rebalancer (LOOP 19).

Nightly job. Watches the library and PROPOSES optimizations the operator
can approve. Never silently applies the consequential ones.

What it watches (signals):
  - Cohesion within a box (cards in same box connect to each other > to outside)
  - Loose coupling between boxes (boxes are distinct, not sprawled)
  - Orphan cards (no in/out connections after 30 days)
  - Duplicate cards (high text similarity + overlapping connections)
  - Box overgrowth (boxes > N cards with internal sub-cluster structure)
  - Walks not captured by any Atlas path (canonize candidates)
  - Community notes that contradict their card's claim (surface for review)

What it does QUIETLY (auto):
  - Recompute trust-weighted scores
  - Update cite_count counters
  - Refresh per-card metric snapshots

What it does LOUDLY (queues for operator):
  - Suggest merge of two near-duplicate cards
  - Suggest move of a card to a better-fitting box
  - Suggest split of a box that has internal sub-clusters
  - Suggest canonize-as-Atlas-path
  - Suggest archive of orphan cards

Hard rules:
  - Never delete a card.
  - Never edit card content.
  - Never auto-merge.
  - Never propose > 10 consequential changes per run.

Storage:
  data/rebalance/<date>.json   per-run report
  data/rebalance_queue.json    operator-facing pending suggestions

Usage:
  python tools/rebalance_library.py             # dry run, no writes
  python tools/rebalance_library.py --apply     # write the queue + quiet updates
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
REBALANCE_DIR = REPO / "data" / "rebalance"
REBALANCE_QUEUE = REPO / "data" / "rebalance_queue.json"

MAX_SUGGESTIONS_PER_RUN = 10
ORPHAN_AGE_DAYS = 30
BOX_OVERGROWTH_THRESHOLD = 500  # raised from 50 — split candidate
DUPLICATE_JACCARD_THRESHOLD = 0.85
# Box-name prefixes that are navigation glue, not browseable content.
# Box-overgrowth proposals never fire for these.
GLUE_BOX_PREFIXES = ("sequence_",)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _tokens(text: str) -> set:
    return set(t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z']{2,}", text or ""))


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _age_days(ts: str) -> float:
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - d).total_seconds() / 86400.0
    except Exception:
        return 0.0


def _load_queue() -> list:
    if not REBALANCE_QUEUE.exists():
        return []
    try:
        return json.loads(REBALANCE_QUEUE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(q: list):
    REBALANCE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    REBALANCE_QUEUE.write_text(json.dumps(q, indent=2), encoding="utf-8")


def _dedupe_proposal(q: list, kind: str, card_ids: list) -> bool:
    """Returns True if a similar proposal already pending."""
    target = sorted(card_ids)
    for item in q:
        if item.get("status") != "pending":
            continue
        if item.get("kind") != kind:
            continue
        if sorted(item.get("card_ids", [])) == target:
            return True
    return False


def analyze(apply: bool = False) -> dict:
    cards = _read_all_cards()
    n = len(cards)
    report = {
        "ran_at": _now(),
        "apply": apply,
        "total_cards": n,
        "auto_updates": {"trust_scores_refreshed": 0, "cite_counts_refreshed": 0},
        "suggestions": [],  # the consequential ones for operator
        "metrics_summary": {},
    }

    by_id = {c["id"]: c for c in cards if c.get("id")}
    by_box: dict[str, list] = defaultdict(list)
    by_shelf: dict[str, list] = defaultdict(list)

    # First pass: bucket + compute citation counts
    citation_count = Counter()
    for c in cards:
        if c.get("box"):
            by_box[c["box"]].append(c)
        if c.get("shelf"):
            by_shelf[c["shelf"]].append(c)
        for conn in (c.get("connections") or []):
            tid = conn.get("to_card_id")
            if tid:
                citation_count[tid] += 1

    # Auto-update: refresh cite_count if drifted
    if apply:
        for cid, true_count in citation_count.items():
            card = by_id.get(cid)
            if not card:
                continue
            m = card.get("metrics") or {}
            if m.get("cite_count") != true_count:
                m["cite_count"] = true_count
                card["metrics"] = m
                card["updated_at"] = _now()
                (CARDS_DIR / f"{cid}.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
                report["auto_updates"]["cite_counts_refreshed"] += 1

    # Auto-update: refresh trust_weighted_score
    if apply:
        try:
            from api.promotion import _trust_weighted_score  # type: ignore
            for c in cards:
                m = c.get("metrics") or {}
                m["trust_weighted_score"] = _trust_weighted_score(m)
                c["metrics"] = m
                (CARDS_DIR / f"{c['id']}.json").write_text(json.dumps(c, indent=2), encoding="utf-8")
                report["auto_updates"]["trust_scores_refreshed"] += 1
        except Exception:
            pass

    # --- Consequential suggestions (queued for operator) ---
    suggestions = []
    queue = _load_queue() if apply else []

    # 1. ORPHANS: no inbound, no outbound, > 30 days old
    for c in cards:
        if c.get("kind") in ("connection", "walk", "search", "community_note"):
            continue  # these have different orphan semantics
        out_count = len(c.get("connections") or [])
        in_count = citation_count.get(c["id"], 0)
        age = _age_days(c.get("created_at") or "")
        if out_count == 0 and in_count == 0 and age >= ORPHAN_AGE_DAYS:
            kind = "archive_orphan"
            if not _dedupe_proposal(queue, kind, [c["id"]]):
                suggestions.append({
                    "kind": kind,
                    "card_ids": [c["id"]],
                    "reason": f"No inbound/outbound connections after {age:.0f} days. Consider archiving or connecting.",
                    "card_titles": [c.get("title", "?")],
                })
            if len(suggestions) >= MAX_SUGGESTIONS_PER_RUN:
                break

    # Pre-build a set of (a_id, b_id) pairs already connected — those are
    # NOT duplicates; the operator has declared the relationship.
    already_connected = set()
    for c in cards:
        if c.get("kind") != "connection":
            continue
        ex = c.get("extra") or {}
        L, R = ex.get("left_card_id"), ex.get("right_card_id")
        if L and R:
            already_connected.add((L, R)); already_connected.add((R, L))

    # 2. NEAR-DUPLICATES within the same shelf (jaccard on title+body tokens)
    if len(suggestions) < MAX_SUGGESTIONS_PER_RUN:
        for shelf, shelf_cards in by_shelf.items():
            if len(shelf_cards) < 2:
                continue
            for i, a in enumerate(shelf_cards):
                if len(suggestions) >= MAX_SUGGESTIONS_PER_RUN:
                    break
                if a.get("kind") in ("connection", "walk", "community_note"):
                    continue
                a_tokens = _tokens((a.get("title", "") + " " + (a.get("body") or "")[:500]))
                if len(a_tokens) < 4:
                    continue
                for b in shelf_cards[i+1:]:
                    if b.get("kind") in ("connection", "walk", "community_note"):
                        continue
                    if a["id"] == b["id"]:
                        continue
                    # Skip if operator has already declared a relationship
                    if (a["id"], b["id"]) in already_connected:
                        continue
                    b_tokens = _tokens((b.get("title", "") + " " + (b.get("body") or "")[:500]))
                    if len(b_tokens) < 4:
                        continue
                    score = _jaccard(a_tokens, b_tokens)
                    if score >= DUPLICATE_JACCARD_THRESHOLD:
                        kind = "merge_duplicate"
                        if not _dedupe_proposal(queue, kind, [a["id"], b["id"]]):
                            suggestions.append({
                                "kind": kind,
                                "card_ids": [a["id"], b["id"]],
                                "reason": f"Near-duplicate (Jaccard {score:.2f}) within '{shelf}'. Operator review.",
                                "card_titles": [a.get("title", "?"), b.get("title", "?")],
                                "similarity": round(score, 3),
                            })

    # 3. BOX OVERGROWTH (skips navigation-glue boxes like sequence_*)
    if len(suggestions) < MAX_SUGGESTIONS_PER_RUN:
        for box, box_cards in by_box.items():
            if any(box.startswith(p) for p in GLUE_BOX_PREFIXES):
                continue  # sequence_* is navigation glue, not content
            if len(box_cards) >= BOX_OVERGROWTH_THRESHOLD:
                kind = "split_box"
                if not _dedupe_proposal(queue, kind, [box]):
                    suggestions.append({
                        "kind": kind,
                        "card_ids": [],
                        "reason": f"Box '{box}' has {len(box_cards)} cards. Consider splitting into sub-boxes.",
                        "box": box,
                    })
            if len(suggestions) >= MAX_SUGGESTIONS_PER_RUN:
                break

    # 4. FREQUENT WALKS that don't have an Atlas path yet (canonize candidates)
    if len(suggestions) < MAX_SUGGESTIONS_PER_RUN:
        try:
            from api.walks_cache import _read_replay  # type: ignore
            replays = _read_replay(limit=500)
            # Count walk-fingerprints
            fp_counts = Counter()
            fp_to_walk_cards = {}
            for r in replays:
                fp = r.get("fingerprint")
                if fp:
                    fp_counts[fp] += 1
                    if r.get("walk_card_id"):
                        fp_to_walk_cards[fp] = r["walk_card_id"]
            # Check which walks haven't been canonized to public Atlas paths
            atlas_public_walks = set(c["id"] for c in cards if c.get("kind") == "walk" and c.get("lifecycle_stage") in ("public", "featured"))
            for fp, count in fp_counts.most_common(5):
                if count < 3:
                    break
                walk_id = fp_to_walk_cards.get(fp)
                if walk_id and walk_id not in atlas_public_walks:
                    kind = "canonize_walk"
                    if not _dedupe_proposal(queue, kind, [walk_id]):
                        suggestions.append({
                            "kind": kind,
                            "card_ids": [walk_id],
                            "reason": f"Walk asked {count} times; not yet on the Atlas. Consider canonizing.",
                        })
                if len(suggestions) >= MAX_SUGGESTIONS_PER_RUN:
                    break
        except Exception:
            pass

    # Cap at hard limit
    suggestions = suggestions[:MAX_SUGGESTIONS_PER_RUN]
    report["suggestions"] = suggestions
    report["metrics_summary"] = {
        "total_cards": n,
        "by_kind": dict(Counter(c.get("kind", "?") for c in cards)),
        "by_shelf": {k: len(v) for k, v in by_shelf.items()},
        "by_lifecycle": dict(Counter(c.get("lifecycle_stage", "?") for c in cards)),
        "orphans_total": sum(1 for c in cards if c.get("kind") not in ("connection", "walk") and not (c.get("connections") or []) and citation_count.get(c["id"], 0) == 0),
    }

    # Write report
    if apply:
        REBALANCE_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REBALANCE_DIR / f"{_now()[:10]}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        # Append new suggestions to queue (with status=pending)
        for s in suggestions:
            queue.append({**s, "status": "pending", "created_at": _now()})
        _save_queue(queue)

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    r = analyze(apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"=== Rebalancer {mode} at {r['ran_at']} ===")
    print(f"Total cards: {r['total_cards']}")
    print(f"Auto updates: {r['auto_updates']}")
    print(f"\nMetrics summary:")
    for k, v in r['metrics_summary'].items():
        print(f"  {k}: {v}")
    print(f"\nConsequential suggestions for operator: {len(r['suggestions'])}")
    for i, s in enumerate(r['suggestions'][:MAX_SUGGESTIONS_PER_RUN], 1):
        print(f"  {i}. [{s['kind']}] {s['reason']}")
        if s.get("card_titles"):
            for t in s["card_titles"]:
                print(f"     - {t}")
    if not args.apply:
        print("\n[DRY RUN] re-run with --apply to write queue + auto-update metrics.")


if __name__ == "__main__":
    main()
