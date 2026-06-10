"""engine_daily.py — Single nightly entry point for the engine's content-generation pass.

The engine has several generators (devotional, almanac entry, hymn audio, lesson,
maker project pick, recipe pick). This script picks gaps in the substrate and
queues newly-generated items for OPERATOR REVIEW. No item ships live without
operator approval — same alignment gate as user submissions.

Queue: data/engine_queue/<id>.json
Each file: {
  id, kind, generated_at, status (quarantined|approved|rejected),
  body, source_generator, gap_filled, operator_notes
}

This script does the QUEUE step only. The actual generators (devotional_gen,
almanac_gen, etc.) are separate tools that this script invokes. For Phase 1
we ship a deterministic scaffold (no LLM call) — the substrate's existing
text-based generators produce daily candidates from PD substrate.

Run nightly:
  python tools/engine_daily.py

Or specific kind:
  python tools/engine_daily.py --kind devotional --count 3

This is safe to run anytime. It only WRITES to data/engine_queue/. It never
modifies the live substrate or the channel.
"""
from __future__ import annotations
import argparse
import json
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE_DIR = REPO / "data" / "engine_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(5)}"


def _save(item: dict):
    p = QUEUE_DIR / f"{item['id']}.json"
    p.write_text(json.dumps(item, indent=2), encoding="utf-8")
    return p


# ---------- Generators ----------

DEVOTIONAL_VERSES = [
    ("Psalm 23:1", "The LORD is my shepherd; I shall not want.",
     "Today, in the small thing you lack, ask whether you are wanting what you actually need or what would only feed a deeper hunger. The Shepherd has not forgotten you. He measures abundance differently than the world does."),
    ("Matthew 11:28", "Come unto me, all ye that labour and are heavy laden, and I will give you rest.",
     "If today's load feels heavier than the day, the invitation is not to push through but to come. To set the load at his feet. The rest he offers is not the absence of work; it is the presence of the One who carries it with you."),
    ("Philippians 4:6-7", "Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God.",
     "Today, name your worry to him before you name it to anyone else. Thanksgiving in the same breath. The peace that follows isn't the absence of the worry — it's a peace that keeps your heart even while the worry is still real."),
    ("Romans 12:2", "And be not conformed to this world: but be ye transformed by the renewing of your mind.",
     "Today, notice one place where the world's pattern is shaping yours by default. Question it for an hour. See what God's pattern would have you do instead."),
    ("1 John 1:9", "If we confess our sins, he is faithful and just to forgive us our sins, and to cleanse us from all unrighteousness.",
     "Today's confession does not earn forgiveness — Christ earned it. Confession is naming what he has already named, and accepting the cleansing he has already prepared."),
    ("Proverbs 3:5-6", "Trust in the LORD with all thine heart; and lean not unto thine own understanding.",
     "Today's decision: when you do not know, do not pretend to know. Lay the not-knowing before him. The path becomes visible from the next step, not from the summit."),
    ("John 14:27", "Peace I leave with you, my peace I give unto you: not as the world giveth, give I unto you.",
     "The world's peace depends on circumstances arranging themselves. Christ's peace persists when the circumstances refuse. Today, ask which peace you are seeking and which you have."),
]


def gen_devotional(count: int = 1) -> list:
    out = []
    pool = DEVOTIONAL_VERSES[:]
    random.shuffle(pool)
    for v in pool[:count]:
        ref, text, reflection = v
        item = {
            "id": _gen_id("dev"),
            "kind": "devotional",
            "status": "quarantined",
            "generated_at": _now(),
            "source_generator": "tools/engine_daily.py:gen_devotional",
            "scripture_ref": ref,
            "scripture_text": text,
            "reflection": reflection,
            "gap_filled": "today's daily devotional",
        }
        _save(item)
        out.append(item)
    return out


ALMANAC_CLAIMS = [
    {"claim": "Local-honey desensitization to seasonal allergies has equivocal evidence; some small studies show benefit, larger trials don't replicate.",
     "domain": "medicine", "verdict": "MIXED", "sources": ["JACI 2002 small-trial", "JACI 2011 negative trial"]},
    {"claim": "Pressing fresh garlic and waiting 10 minutes before cooking preserves more allicin (the antimicrobial compound).",
     "domain": "nutrition", "verdict": "PASS", "sources": ["Cancer Prevention Research 2007"]},
    {"claim": "Reading aloud to children in utero measurably improves post-birth language preference for the same voice.",
     "domain": "developmental_psychology", "verdict": "PASS", "sources": ["DeCasper & Spence 1986"]},
    {"claim": "Bread made with poolish (pre-ferment) keeps fresh longer than straight-dough breads.",
     "domain": "food_science", "verdict": "PASS", "sources": ["Calvel, French bread science"]},
    {"claim": "The phrase 'thou shalt not steal' applies to wages withheld from a laborer as well as to chattels taken.",
     "domain": "theology", "verdict": "PASS", "sources": ["Deut 24:14-15", "James 5:4"]},
]


def gen_almanac(count: int = 1) -> list:
    out = []
    pool = ALMANAC_CLAIMS[:]
    random.shuffle(pool)
    for c in pool[:count]:
        item = {
            "id": _gen_id("alm"),
            "kind": "almanac_entry",
            "status": "quarantined",
            "generated_at": _now(),
            "source_generator": "tools/engine_daily.py:gen_almanac",
            **c,
            "gap_filled": "today's almanac entry",
        }
        _save(item)
        out.append(item)
    return out


def gen_recipe_pick(count: int = 1) -> list:
    """Pick a recipe-of-the-day from the existing catalog (just promotes one to spotlight)."""
    catalog_path = REPO / "content" / "recipes.json"
    if not catalog_path.exists():
        return []
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    recipes = catalog.get("recipes", [])
    out = []
    sample = random.sample(recipes, min(count, len(recipes)))
    for r in sample:
        item = {
            "id": _gen_id("rec"),
            "kind": "recipe_spotlight",
            "status": "quarantined",
            "generated_at": _now(),
            "source_generator": "tools/engine_daily.py:gen_recipe_pick",
            "recipe_slug": r.get("slug"),
            "recipe_title": r.get("title"),
            "recipe_source": r.get("source"),
            "gap_filled": "recipe of the day",
        }
        _save(item)
        out.append(item)
    return out


def gen_maker_pick(count: int = 1) -> list:
    """Pick a project-of-the-week from the maker catalog."""
    catalog_path = REPO / "content" / "projects.json"
    if not catalog_path.exists():
        return []
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    projects = catalog.get("projects", [])
    out = []
    sample = random.sample(projects, min(count, len(projects)))
    for p in sample:
        item = {
            "id": _gen_id("mak"),
            "kind": "maker_spotlight",
            "status": "quarantined",
            "generated_at": _now(),
            "source_generator": "tools/engine_daily.py:gen_maker_pick",
            "project_slug": p.get("slug"),
            "project_title": p.get("title"),
            "project_source": p.get("primary_source"),
            "gap_filled": "project of the week",
        }
        _save(item)
        out.append(item)
    return out


# ---------- Orchestrator ----------

GENERATORS = {
    "devotional": gen_devotional,
    "almanac": gen_almanac,
    "recipe": gen_recipe_pick,
    "maker": gen_maker_pick,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=list(GENERATORS.keys()) + ["all"], default="all")
    ap.add_argument("--count", type=int, default=1)
    args = ap.parse_args()

    print(f"engine_daily.py — running at {_now()}")
    print(f"  queue dir: {QUEUE_DIR}")
    kinds = [args.kind] if args.kind != "all" else list(GENERATORS.keys())
    grand_total = 0
    for k in kinds:
        try:
            items = GENERATORS[k](args.count)
            for it in items:
                print(f"  [QUEUED] {it['kind']:18}  id={it['id']}")
            grand_total += len(items)
        except Exception as e:
            print(f"  [ERROR] {k}: {e}")
    print(f"\nQueued {grand_total} items. Operator review at /engine-queue.html or "
          f"GET /engine/queue endpoint.")


if __name__ == "__main__":
    main()
