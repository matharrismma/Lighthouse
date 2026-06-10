"""Engagement scorer + content lifecycle stage assigner.

Combines:
  - acquisition manifests (data/library_inventory/acquired/*.json)
  - server-side feedback log if present (data/feedback/*.jsonl)
  - localStorage-exported feedback dumps if present (data/feedback/exports/*.json)
  - play counts if present (data/feedback/plays.jsonl)

Computes per-slug engagement_score and assigns lifecycle state:
    ACQUIRED → BROADCASTING → STEADY → FADING → ARCHIVE-CANDIDATE → DELETED

Writes:
  - data/library_inventory/engagement_scores.json
  - per-slug `lifecycle_state` + `engagement_score` updates injected into each
    manifest at data/library_inventory/acquired/<slug>.json

Standing rule: NOTHING IS AUTO-DELETED. Operator (Matt) reviews ARCHIVE candidates
in /inbox.html or via manual sweep. This script only scores + suggests.

Usage:
    python tools/score_engagement.py [--dry-run]
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
ACQ = REPO / "data" / "library_inventory" / "acquired"
FEEDBACK_DIR = REPO / "data" / "feedback"
SCORES_OUT = REPO / "data" / "library_inventory" / "engagement_scores.json"


def load_feedback() -> dict[str, dict]:
    """Aggregate all available feedback signals per slug.

    Returns: { slug: { up: int, down: int, flags: list[dict], plays: int, last_play_ts: int } }
    """
    by_slug: dict[str, dict] = {}

    def bucket(slug: str) -> dict:
        return by_slug.setdefault(slug, {"up": 0, "down": 0, "flags": [], "plays": 0, "last_play_ts": 0})

    # Server-side feedback log (jsonl)
    if FEEDBACK_DIR.exists():
        for fp in FEEDBACK_DIR.glob("*.jsonl"):
            with fp.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        slug = ev.get("slug")
                        if not slug:
                            continue
                        b = bucket(slug)
                        if ev.get("vote") == "up":
                            b["up"] += 1
                        elif ev.get("vote") == "down":
                            b["down"] += 1
                            b["flags"].append({
                                "visitor_id": ev.get("visitor_id"),
                                "reason": ev.get("reason"),
                                "ts": ev.get("ts"),
                                "resolved": ev.get("resolved", False),
                            })
                        if ev.get("event") == "play":
                            b["plays"] += 1
                            b["last_play_ts"] = max(b["last_play_ts"], int(ev.get("ts", 0)))
                    except Exception:
                        continue

    # localStorage exports (operator dumps from /inbox.html)
    exports_dir = FEEDBACK_DIR / "exports"
    if exports_dir.exists():
        for fp in sorted(exports_dir.glob("nh-inbox-*.json")):
            try:
                blob = json.loads(fp.read_text(encoding="utf-8"))
                # thumbs
                thumbs = blob.get("thumbs", {})
                for slug, v in thumbs.items():
                    # Strip frontend prefix (sched:, tv:, radio:, kids:) so we score by base slug
                    base = slug.split(":", 1)[1] if ":" in slug else slug
                    b = bucket(base)
                    vote = v.get("vote")
                    if vote == "up": b["up"] += 1
                    elif vote == "down": b["down"] += 1
                # flags
                for f in blob.get("flags", []):
                    slug = (f.get("slug") or "").split(":", 1)[-1]
                    if not slug: continue
                    b = bucket(slug)
                    b["flags"].append({
                        "visitor_id": f.get("visitor_id"),
                        "reason": f.get("reason"),
                        "ts": f.get("ts"),
                        "resolved": f.get("resolved", False),
                        "resolution": f.get("resolution"),
                    })
            except Exception as e:
                print(f"[warn] could not parse {fp.name}: {e}")

    return by_slug


def score(stats: dict, manifest: dict, now_ts: int) -> float:
    """engagement_score per the formula in storage-discipline memo."""
    plays = stats.get("plays", 0)
    up = stats.get("up", 0)
    down = sum(1 for f in stats.get("flags", []) if not f.get("resolution") == "ABUSE")
    last_play = stats.get("last_play_ts", 0)
    # If no play data at all, use acquisition timestamp as a fallback
    if not last_play:
        try:
            last_play = int(datetime.fromisoformat(manifest.get("acquired_at_iso", "").replace("Z","+00:00")).timestamp())
        except Exception:
            last_play = now_ts  # treat as fresh

    days_since = max(0, (now_ts - last_play) / 86400)
    recency_decay = max(0.0, 1.0 - days_since / 90.0)
    flag_review_bonus = sum(1 for f in stats.get("flags", []) if f.get("resolution") == "OK")

    score = (plays * 0.5) + (up * 3.0) - (down * 1.5) + (recency_decay * 5.0) + (flag_review_bonus * 0.5)
    return round(score, 2)


def lifecycle_state(score_val: float, plays: int, age_days: float) -> str:
    if plays == 0 and age_days < 7:
        return "ACQUIRED"
    if age_days < 14:
        return "BROADCASTING"
    if score_val >= 20:
        return "STEADY"
    if score_val >= 5:
        return "FADING"
    if age_days >= 60 and score_val < 5:
        return "ARCHIVE-CANDIDATE"
    return "FADING"


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if not ACQ.exists():
        print(f"No manifests at {ACQ}")
        return 1
    feedback = load_feedback()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    rows = []
    updated = 0

    for mfp in sorted(ACQ.glob("*.json")):
        try:
            manifest = json.loads(mfp.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = manifest.get("slug")
        if not slug:
            continue
        stats = feedback.get(slug, {})
        sc = score(stats, manifest, now_ts)

        try:
            acquired_at = datetime.fromisoformat(manifest.get("acquired_at_iso", "").replace("Z","+00:00")).timestamp()
        except Exception:
            acquired_at = now_ts
        age_days = (now_ts - acquired_at) / 86400

        state = lifecycle_state(sc, stats.get("plays", 0), age_days)

        manifest["engagement_score"] = sc
        manifest["lifecycle_state"] = state
        manifest["lifecycle_updated_at"] = datetime.now(timezone.utc).isoformat()
        manifest["engagement_stats"] = {
            "plays": stats.get("plays", 0),
            "up": stats.get("up", 0),
            "down_open": sum(1 for f in stats.get("flags", []) if not f.get("resolved")),
            "down_resolved": sum(1 for f in stats.get("flags", []) if f.get("resolved")),
            "age_days": round(age_days, 1),
        }
        rows.append({
            "slug": slug, "score": sc, "state": state, "category": manifest.get("category"),
            "age_days": round(age_days, 1), **manifest["engagement_stats"],
        })
        if not dry_run:
            mfp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            updated += 1

    rows.sort(key=lambda r: r["score"], reverse=True)

    # Summary
    by_state: dict[str, int] = {}
    for r in rows:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(rows),
        "by_state": by_state,
        "top_10": rows[:10],
        "archive_candidates": [r for r in rows if r["state"] == "ARCHIVE-CANDIDATE"],
        "all": rows,
    }
    if not dry_run:
        SCORES_OUT.parent.mkdir(parents=True, exist_ok=True)
        SCORES_OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
        # Mirror to site/ so the operator inbox can fetch it via /engagement_scores.json
        site_copy = REPO / "site" / "engagement_scores.json"
        site_copy.parent.mkdir(parents=True, exist_ok=True)
        site_copy.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Scored {len(rows)} items{' (dry-run, not written)' if dry_run else ''}")
    print(f"  By state: {by_state}")
    print(f"  Archive candidates: {len(out['archive_candidates'])}")
    if out["archive_candidates"]:
        print(f"  Top archive candidates:")
        for r in out["archive_candidates"][:5]:
            print(f"    {r['slug']:50} score={r['score']} age={r['age_days']}d")
    if not dry_run:
        print(f"  Manifests updated: {updated}")
        print(f"  Summary written: {SCORES_OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
