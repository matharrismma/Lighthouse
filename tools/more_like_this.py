"""More-like-this — feedback signal → production queue.

Reads:
  - engagement_scores.json (engagement per slug)
  - localStorage-exported feedback JSON (thumbs-up + thumbs-down per slug)

Analyzes high-thumbs-up content to extract:
  - dominant category (radio, hymns, vegas, etc.)
  - dominant theme / topic / scripture-anchor (via Claude)
  - voice/style suggestion

Outputs production tasks to data/production_queue/<date>.json. Operator (Matt)
reviews these in /inbox.html "Production Queue" tab before any paid call.

Three production task types:
  1. ACQUIRE — propose a new IA collection or text to grab (similar PD substrate)
  2. NARRATE — propose an ElevenLabs marquee narration of a related text
  3. GENERATE — propose a Claude-composed devotion/almanac/script on the theme

Pre-req:
  - ANTHROPIC_API_KEY (for theme analysis)
  - feedback export at site/feedback_export.json or operator-exported via /inbox.html

Usage:
  python tools/more_like_this.py --dry-run
  python tools/more_like_this.py --top 5    # propose for top 5 slugs
  python tools/more_like_this.py --slug tv:tv_andy_griffith_discovers_america
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

REPO = Path(__file__).resolve().parent.parent
SCORES_PATH = REPO / "site" / "engagement_scores.json"
FEEDBACK_EXPORT = REPO / "site" / "feedback_export.json"
QUEUE_DIR = REPO / "data" / "production_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def load_signals() -> dict:
    """Returns: { slug: { up: int, down: int, plays: int, score: float, category: str } }"""
    out = defaultdict(lambda: {"up": 0, "down": 0, "plays": 0, "score": 0.0, "category": None, "title": None})

    # Engagement scores
    if SCORES_PATH.exists():
        blob = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
        for row in blob.get("all", []):
            slug = row.get("slug")
            if not slug: continue
            out[slug]["score"] = row.get("score", 0.0)
            out[slug]["plays"] = row.get("plays", 0)
            out[slug]["up"] = row.get("up", 0)
            out[slug]["category"] = row.get("category")

    # Feedback export (operator-exported from /inbox.html)
    if FEEDBACK_EXPORT.exists():
        try:
            blob = json.loads(FEEDBACK_EXPORT.read_text(encoding="utf-8"))
            thumbs = blob.get("thumbs", {})
            for k, v in thumbs.items():
                base = k.split(":", 1)[1] if ":" in k else k
                if v.get("vote") == "up":
                    out[base]["up"] += 1
                elif v.get("vote") == "down":
                    out[base]["down"] += 1
        except Exception as e:
            print(f"[warn] couldn't parse feedback export: {e}")

    return dict(out)


def rank_top(signals: dict, n: int = 5) -> list[tuple[str, dict]]:
    items = list(signals.items())
    # Sort by (up * 3 + plays - down)
    items.sort(key=lambda x: x[1]["up"] * 3 + x[1]["plays"] - x[1]["down"], reverse=True)
    return items[:n]


def analyze_with_claude(slug: str, signal: dict, manifest_lookup: dict) -> dict | None:
    """Asks Claude to extract themes + propose 3 production tasks."""
    try:
        import anthropic
    except ImportError:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    client = anthropic.Anthropic(api_key=key)

    manifest = manifest_lookup.get(slug, {})
    title = manifest.get("title") or signal.get("title") or slug
    category = signal.get("category") or manifest.get("category") or "unknown"
    notes = manifest.get("notes") or ""

    system = """You are the production-curator for Narrow Highway — a curated Christian-family
internet portal. The audience just thumbs-upped a piece. Your job is to propose
three production tasks that give them MORE LIKE THIS.

Output STRICT JSON:
{
  "themes": ["<one to three theme keywords>"],
  "voice_suggestion": "<one of: steady_pastor, storyteller, codex_reader, lighthouse_kids, newscaster, hymnal>",
  "tasks": [
    {
      "type": "ACQUIRE",
      "what": "<specific IA collection or PD text>",
      "rationale": "<one line why this fits the theme>",
      "estimated_cost": "$0 (free)",
      "priority": "<high|med|low>"
    },
    {
      "type": "NARRATE",
      "what": "<specific PD text we already own + voice>",
      "rationale": "<one line>",
      "estimated_cost": "<$X via ElevenLabs based on char count>",
      "priority": "<high|med|low>"
    },
    {
      "type": "GENERATE",
      "what": "<devotion or almanac entry, on what specific theme>",
      "rationale": "<one line>",
      "estimated_cost": "<$0.01-0.03 via Claude API>",
      "priority": "<high|med|low>"
    }
  ]
}

No prose outside the JSON. Keep tasks concrete and actionable. Prefer high-priority
items that the engine already has substrate for."""

    user = f"""Audience just thumbs-upped:

  TITLE:      {title}
  CATEGORY:   {category}
  SCORE:      {signal['score']}
  PLAYS:      {signal['plays']}
  THUMBS-UP:  {signal['up']}
  NOTES:      {notes}

What three production tasks would you queue?"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
        text = re.sub(r"\s*```\s*$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        print(f"[err] Claude call: {e}")
        return None


def load_manifests() -> dict:
    """slug → manifest dict for lookup."""
    out = {}
    acq = REPO / "data" / "library_inventory" / "acquired"
    if not acq.exists(): return out
    for p in acq.glob("*.json"):
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
            out[blob.get("slug")] = blob
        except Exception:
            continue
    return out


def write_queue(tasks: list[dict], dry_run: bool = False):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = QUEUE_DIR / f"{date_str}.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(tasks),
        "tasks": tasks,
    }
    if dry_run:
        print(json.dumps(payload, indent=2))
        return
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Mirror to site/ so /inbox.html can fetch
    mirror = REPO / "site" / "production_queue.json"
    mirror.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[wrote] {out.relative_to(REPO)} (and site mirror) — {len(tasks)} tasks proposed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="Top N high-engagement slugs to propose tasks for")
    ap.add_argument("--slug", help="Specific slug to analyze")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    signals = load_signals()
    if not signals:
        print("[skip] no signals (engagement_scores.json + feedback_export.json both empty)")
        return 0
    manifests = load_manifests()

    targets = []
    if args.slug:
        if args.slug in signals:
            targets.append((args.slug, signals[args.slug]))
    else:
        targets = rank_top(signals, n=args.top)

    if not targets:
        print("[skip] no targets met threshold")
        return 0

    all_tasks = []
    for slug, sig in targets:
        print(f"\nAnalyzing {slug} (up={sig['up']}, plays={sig['plays']}, score={sig['score']})…")
        analysis = analyze_with_claude(slug, sig, manifests)
        if not analysis:
            print(f"  [skip — Claude unavailable; ANTHROPIC_API_KEY?]")
            continue
        for task in analysis.get("tasks", []):
            task["seed_slug"] = slug
            task["themes"] = analysis.get("themes", [])
            task["voice_suggestion"] = analysis.get("voice_suggestion")
            task["status"] = "PROPOSED"
            all_tasks.append(task)
        for t in analysis.get("tasks", []):
            print(f"  → {t.get('type')}: {t.get('what')[:80]} ({t.get('estimated_cost')})")

    if all_tasks:
        write_queue(all_tasks, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
