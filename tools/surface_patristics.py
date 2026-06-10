"""surface_patristics.py — Apostolic Fathers as first-class cards (LOOP 25).

The substrate already contains the Apostolic Fathers as JSONL chapters under
data/<work>/chapters.jsonl. This tool surfaces each chapter as a real card on
disk, with authority_tier=father, shelf=patristics, box=<work>.

Works covered:
  - 1 Clement (1 Clem)            — c. AD 96
  - Didache                       — c. AD 50-150
  - Ignatius of Antioch (7 epistles) — c. AD 110
  - Polycarp to the Philippians   — c. AD 110-140
  - Martyrdom of Polycarp         — c. AD 155
  - Epistle of Barnabas           — c. AD 70-135

All universally PD (translations >100 years old; Hitchcock & Brown 1884 et al.).

Usage:
  python tools/surface_patristics.py                # write cards
  python tools/surface_patristics.py --dry-run      # report only
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CARDS_DIR = REPO / "data" / "cards"
DATA = REPO / "data"

# Map data-dir name → (work_title_prefix, work_slug_for_box)
PATRISTIC_WORKS = {
    "clement1": ("1 Clement", "clement_first"),
    "didache": ("Didache", "didache"),
    "ignatius_eph": ("Ignatius to the Ephesians", "ignatius_ephesians"),
    "ignatius_mag": ("Ignatius to the Magnesians", "ignatius_magnesians"),
    "ignatius_phild": ("Ignatius to the Philadelphians", "ignatius_philadelphians"),
    "ignatius_polyc": ("Ignatius to Polycarp", "ignatius_to_polycarp"),
    "ignatius_rom": ("Ignatius to the Romans", "ignatius_romans"),
    "ignatius_smy": ("Ignatius to the Smyrnaeans", "ignatius_smyrnaeans"),
    "ignatius_tra": ("Ignatius to the Trallians", "ignatius_trallians"),
    "polycarp": ("Polycarp to the Philippians", "polycarp_philippians"),
    "martyrdom_polycarp": ("Martyrdom of Polycarp", "martyrdom_polycarp"),
    "barnabas": ("Epistle of Barnabas", "barnabas"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-chapters-per-work", type=int, default=None,
                        help="Cap chapters per work (e.g. 10 to test)")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    counts = {"created": 0, "skipped_exists": 0, "would_create": 0, "errors": 0}
    by_work = {}

    for work_dir, (work_title, work_slug) in PATRISTIC_WORKS.items():
        chapters_path = DATA / work_dir / "chapters.jsonl"
        if not chapters_path.exists():
            continue
        try:
            with chapters_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            counts["errors"] += 1
            continue
        work_count = 0
        for i, line in enumerate(lines):
            if args.max_chapters_per_work and i >= args.max_chapters_per_work:
                break
            try:
                ch = json.loads(line)
            except Exception:
                counts["errors"] += 1
                continue
            chapter = ch.get("chapter") or (i + 1)
            ch_roman = ch.get("chapter_roman") or str(chapter)
            text = ch.get("text") or ""
            if not text or len(text) < 30:
                continue
            ref = ch.get("reference") or f"{work_title} {chapter}"
            source_label = ch.get("source") or work_title
            themes = ch.get("themes") or []
            axes = ch.get("axes") or []

            # Build the card
            seed = f"patristic::{work_slug}::{chapter}"
            cid = _make_card_id("note", seed)
            p = CARDS_DIR / f"{cid}.json"
            if p.exists():
                counts["skipped_exists"] += 1
                continue
            card = {
                "id": cid,
                "kind": "note",
                "title": ref,
                "body": text[:3800] + ("…" if len(text) > 3800 else ""),
                "source": {
                    "label": source_label,
                    "url": f"/canon.html?ref={work_slug}_ch{chapter}",
                    "ref": f"{work_title} {ch_roman}",
                    "authority_tier": "father",
                },
                "shelf": "patristics",
                "box": work_slug,
                "bands": ([work_slug, "apostolic_fathers"] + list(themes)[:5] + list(axes)[:3])[:16],
                "connections": [],
                "author": "engine",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            }
            card["source_hash"] = _compute_source_hash(card)

            if args.dry_run:
                counts["would_create"] += 1
            else:
                CARDS_DIR.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(card, indent=2), encoding="utf-8")
                counts["created"] += 1
            work_count += 1
        by_work[work_title] = work_count

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Patristics surfacing — {mode} ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print()
    for work, n in by_work.items():
        print(f"  {work}: {n} chapters")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
