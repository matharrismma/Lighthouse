"""surface_sermons_devotionals.py — Operator-authored sermons + devotionals (LOOP 44).

Surfaces:
  - data/sermons/sermons.jsonl    (operator-authored sermon outlines)
  - data/devotionals/reflections.jsonl (daily devotional reflections)

Both go to shelf=codex (close-to-canonical) with appropriate authority tiers.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CARDS_DIR = REPO / "data" / "cards"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    from api.cards import _make_card_id, _compute_source_hash  # type: ignore
    counts = {"sermons_surfaced": 0, "devotionals_surfaced": 0, "skipped_exists": 0}

    # Sermons
    sp = REPO / "data" / "sermons" / "sermons.jsonl"
    if sp.exists():
        for line in sp.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            title = e.get("title", "Untitled sermon")
            body = e.get("body", "")
            if len(body) < 80:
                continue
            sid = e.get("id") or f"sermon_{counts['sermons_surfaced']}"
            cid = _make_card_id("note", f"sermon::{sid}")
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            card = {
                "id": cid,
                "kind": "note",
                "title": f"Sermon: {title}",
                "body": body[:3800] + ("…" if len(body) > 3800 else ""),
                "source": {
                    "label": "Operator-authored sermon",
                    "url": "/sermons.html",
                    "ref": title,
                    "authority_tier": "matt",
                },
                "shelf": "codex",
                "box": "sermons",
                "bands": ["sermon", e.get("format", "outline")],
                "connections": [],
                "author": "matt",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            }
            card["source_hash"] = _compute_source_hash(card)
            cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
            counts["sermons_surfaced"] += 1

    # Devotionals
    dp = REPO / "data" / "devotionals" / "reflections.jsonl"
    if dp.exists():
        for line in dp.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            title = e.get("title") or (e.get("scripture_ref") or "Devotional")
            body = e.get("reflection") or e.get("body") or ""
            if len(body) < 80:
                continue
            did = e.get("id") or f"dev_{counts['devotionals_surfaced']}"
            cid = _make_card_id("note", f"devotional::{did}")
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            card = {
                "id": cid,
                "kind": "note",
                "title": f"Devotional: {title}",
                "body": body[:3800] + ("…" if len(body) > 3800 else ""),
                "source": {
                    "label": "Operator-authored devotional",
                    "url": "/daily.html?id=" + did,
                    "ref": e.get("scripture_ref", "") or title,
                    "authority_tier": "matt",
                },
                "shelf": "codex",
                "box": "devotionals",
                "bands": ["devotional", "reflection"] + ([e.get("scripture_ref")] if e.get("scripture_ref") else []),
                "connections": [],
                "author": "matt",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            }
            card["source_hash"] = _compute_source_hash(card)
            cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
            counts["devotionals_surfaced"] += 1

    print(f"=== Sermons & devotionals surfacing ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
