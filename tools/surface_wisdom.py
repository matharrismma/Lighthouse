"""surface_wisdom.py — Wisdom literature as cards (LOOP 41).

Surfaces a configurable set of public-domain wisdom and devotional substrates
that are already on disk in JSONL form. Each gets its own shelf+box so the
library stays browsable.

Sources covered:
  - Augustine's Confessions (data/augustine_confessions/sections.jsonl)
  - Marcus Aurelius, Meditations (data/aurelius/sayings.jsonl)
  - Boethius, Consolation of Philosophy (data/boethius_consolation/sections.jsonl)
  - Thomas à Kempis, Imitation of Christ (data/imitation_christ/chapters.jsonl)
  - Pirkei Avot — Ethics of the Fathers (data/pirkei_avot/sayings.jsonl)
  - Sermon on the Mount, structured (data/sermon_on_mount/units.jsonl)
  - La Rochefoucauld, Maxims (data/larochefoucauld/maxims.jsonl)

Authority tier assignment:
  - Augustine, Boethius, à Kempis → father (Christian wisdom tradition)
  - Aurelius, La Rochefoucauld → external_aligned (pre-Christian / post-Christian secular wisdom; useful but not authoritative)
  - Pirkei Avot → external_aligned (Jewish wisdom; respected, non-Christian canon)
  - Sermon on the Mount → words_in_red (Christ's recorded teaching)

Usage:
  python tools/surface_wisdom.py               # surface all
  python tools/surface_wisdom.py --source augustine
  python tools/surface_wisdom.py --min-chars 300
"""
from __future__ import annotations
import argparse
import json
import re
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


def _smart_title(text: str, prefix: str, n: int | str) -> str:
    t = re.sub(r"^\d+[\.\:]\s*", "", text).strip()
    sentence = re.split(r"(?<=[.!?])\s+", t, maxsplit=1)[0]
    if len(sentence) > 80:
        sentence = sentence[:77] + "..."
    return f"{prefix} §{n}: {sentence}"


SOURCES = {
    "augustine": {
        "path": "data/augustine_confessions/sections.jsonl",
        "shelf": "classics",
        "box": "augustine_confessions",
        "title_prefix": "Augustine, Confessions",
        "source_label": "Augustine, Confessions (c. AD 400)",
        "authority_tier": "father",
        "bands": ["augustine", "confessions", "father"],
        "text_field": "text",
    },
    "aurelius": {
        "path": "data/aurelius/sayings.jsonl",
        "shelf": "classics",
        "box": "aurelius_meditations",
        "title_prefix": "Aurelius, Meditations",
        "source_label": "Marcus Aurelius, Meditations (c. AD 170)",
        "authority_tier": "external_aligned",
        "bands": ["aurelius", "meditations", "stoic", "pre_christian"],
        "text_field": "text",
    },
    "boethius": {
        "path": "data/boethius_consolation/sections.jsonl",
        "shelf": "classics",
        "box": "boethius_consolation",
        "title_prefix": "Boethius, Consolation",
        "source_label": "Boethius, Consolation of Philosophy (c. AD 524)",
        "authority_tier": "father",
        "bands": ["boethius", "consolation", "philosophy"],
        "text_field": "text",
    },
    "imitation": {
        "path": "data/imitation_christ/chapters.jsonl",
        "shelf": "classics",
        "box": "imitation_of_christ",
        "title_prefix": "Imitation of Christ",
        "source_label": "Thomas à Kempis, The Imitation of Christ (c. 1418-1427)",
        "authority_tier": "father",
        "bands": ["imitation_christ", "a_kempis", "devotional"],
        "text_field": "text",
    },
    "pirkei_avot": {
        "path": "data/pirkei_avot/sayings.jsonl",
        "shelf": "classics",
        "box": "pirkei_avot",
        "title_prefix": "Pirkei Avot",
        "source_label": "Pirkei Avot — Ethics of the Fathers (Mishnah, c. AD 200)",
        "authority_tier": "external_aligned",
        "bands": ["pirkei_avot", "ethics_of_the_fathers", "jewish_wisdom"],
        "text_field": "text",
    },
    "sermon": {
        "path": "data/sermon_on_mount/units.jsonl",
        "shelf": "codex",
        "box": "sermon_on_mount",
        "title_prefix": "Sermon on the Mount",
        "source_label": "The Sermon on the Mount (Matthew 5-7)",
        "authority_tier": "words_in_red",
        "bands": ["sermon_on_mount", "words_in_red", "matt_5", "matt_6", "matt_7"],
        "text_field": "text",
    },
    "larochefoucauld": {
        "path": "data/larochefoucauld/maxims.jsonl",
        "shelf": "classics",
        "box": "larochefoucauld_maxims",
        "title_prefix": "La Rochefoucauld",
        "source_label": "François de La Rochefoucauld, Maxims (1665)",
        "authority_tier": "external_aligned",
        "bands": ["larochefoucauld", "maxims", "moralist", "post_christian"],
        "text_field": "text",
    },
}


def surface_source(key: str, min_chars: int, max_entries: int | None) -> dict:
    cfg = SOURCES[key]
    p = REPO / cfg["path"]
    if not p.exists():
        return {"error": f"missing {p}"}

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    counts = {"surfaced": 0, "skipped_short": 0, "skipped_exists": 0}
    surfaced = 0
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_entries and surfaced >= max_entries:
                break
            try:
                e = json.loads(line)
            except Exception:
                continue
            text = e.get(cfg["text_field"], "") or e.get("saying", "") or e.get("body", "")
            if len(text) < min_chars:
                counts["skipped_short"] += 1
                continue
            n = e.get("id") or e.get("section") or e.get("chapter") or e.get("saying_id") or (i + 1)
            seed = f"{key}::{n}"
            cid = _make_card_id("note", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            card = {
                "id": cid,
                "kind": "note",
                "title": _smart_title(text, cfg["title_prefix"], n),
                "body": text[:3800] + ("…" if len(text) > 3800 else ""),
                "source": {
                    "label": cfg["source_label"],
                    "url": f"/canon.html?ref={key}_{n}",
                    "ref": str(n),
                    "authority_tier": cfg["authority_tier"],
                },
                "shelf": cfg["shelf"],
                "box": cfg["box"],
                "bands": cfg["bands"],
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
            cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
            counts["surfaced"] += 1
            surfaced += 1
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=list(SOURCES.keys()) + ["all"], default="all")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--max-entries", type=int, default=None)
    args = parser.parse_args()

    sources = [args.source] if args.source != "all" else list(SOURCES.keys())
    print(f"=== Wisdom literature surfacing ===")
    for src in sources:
        print(f"\n[{src}]")
        r = surface_source(src, args.min_chars, args.max_entries)
        for k, v in r.items():
            if v:
                print(f"  {k}: {v}")

    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
