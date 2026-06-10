"""Engine-generated devotional — Anthropic API metered.

Pulls from existing substrate (mind/body/spirit + scripture + Almanac) and asks
Claude to compose a single short devotion for a target date. Output is alignment-
gate-checked before write.

Standing rule: per the storage-discipline memo, paid API calls are reserved for
high-engagement / high-substrate content. A daily devotion qualifies (everyone
who lands on the front page sees it).

Pre-req:
  - ANTHROPIC_API_KEY env var set
  - The anthropic SDK: pip install anthropic

Usage:
  python tools/generate_devotional.py                 # today's devotion
  python tools/generate_devotional.py --date 2026-05-20
  python tools/generate_devotional.py --week           # 7 days starting today
  python tools/generate_devotional.py --dry-run        # print, don't write

Output:
  data/devotionals/<YYYY-MM-DD>.json
  site/devotionals/<YYYY-MM-DD>.json (mirror for the front of site)

Standing principle: every devotion passes through the alignment gate. We don't
ship anything we wouldn't be proud to read aloud to a 5-year-old, an 80-year-
old, and the Lord on the same morning.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "data" / "devotionals"
SITE_OUT = REPO / "site" / "devotionals"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SITE_OUT.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are the devotional voice of Narrow Highway — a curated, family-safe
Christian internet portal. You compose one short morning devotion per day.

Each devotion must:
- Anchor in ONE Scripture passage (cite chapter & verse)
- Be 120-180 words exactly
- Open with a quoted Scripture excerpt
- Develop a SINGLE pastoral observation — not a sermon, not a treatise
- Close with one short prayer line OR one simple call-to-practice (15 words max)
- Use plain modern English; KJV-style only when quoting Scripture itself
- Avoid trite Christianese (no "blessed", "let go and let God", "season")
- Avoid politics, current-events references, denomination polemics
- Stay anchored in the Words-in-Red authority spine when possible

Output STRICT JSON:
{
  "date": "<YYYY-MM-DD>",
  "scripture_ref": "Book Chapter:Verse",
  "scripture_text": "<KJV or ESV-style quoted excerpt>",
  "title": "<short title, max 60 chars>",
  "body": "<the 120-180 word devotion>",
  "practice": "<short call-to-practice or prayer, max 15 words>",
  "axes": ["<one or two of: physical_substance, metabolism, conservation_balance, authority_trust, time_sequence, information_encoding, reasoning>"]
}

Do not output any prose outside the JSON."""

USER_PROMPT_TEMPLATE = """Compose today's devotion.

Today: {date} ({weekday})
Recent themes (avoid repeating): {recent_themes}

Anchor it in a Scripture passage that fits the day's reflection.
Family-safe. Concise. Anchored. Specific. Avoid platitudes."""


def load_recent_themes() -> list[str]:
    """Look at the past 14 days of devotionals to avoid repetition."""
    themes = []
    for p in sorted(OUT_DIR.glob("*.json"), reverse=True)[:14]:
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
            t = blob.get("title")
            if t:
                themes.append(t)
        except Exception:
            continue
    return themes


def call_claude(date_str: str, weekday: str, recent_themes: list[str]) -> dict | None:
    try:
        import anthropic
    except ImportError:
        print("[skip] anthropic SDK not installed. Run: pip install anthropic")
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[skip] ANTHROPIC_API_KEY env var not set.")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user = USER_PROMPT_TEMPLATE.format(
        date=date_str,
        weekday=weekday,
        recent_themes=", ".join(recent_themes[:10]) if recent_themes else "(none yet)",
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        # Strip code-fence if present
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
        text = re.sub(r"\s*```\s*$", "", text.strip())
        blob = json.loads(text)
        return blob
    except json.JSONDecodeError as e:
        print(f"[err] JSON parse failed: {e}\n--- raw ---\n{text[:1000]}")
        return None
    except Exception as e:
        print(f"[err] Claude call failed: {e}")
        return None


def alignment_check(blob: dict) -> tuple[bool, str]:
    """Light client-side alignment check. Server-side polymathic gate is the real one."""
    body = (blob.get("body") or "").lower()
    bad = ["politics", "election", "republican", "democrat", "vaccine", "covid", "trump", "biden", "abortion"]
    for kw in bad:
        if kw in body:
            return False, f"contains keyword '{kw}' — likely fails per-channel alignment"
    if len((blob.get("body") or "").split()) < 80:
        return False, "body is too short (under 80 words)"
    if len((blob.get("body") or "").split()) > 220:
        return False, "body is too long (over 220 words)"
    if not blob.get("scripture_ref"):
        return False, "no scripture_ref"
    return True, "passed"


def write_devotion(date_str: str, blob: dict, dry_run: bool = False):
    blob["generated_at"] = datetime.now(timezone.utc).isoformat()
    blob["date"] = date_str
    if dry_run:
        print(json.dumps(blob, indent=2))
        return
    out = OUT_DIR / f"{date_str}.json"
    out.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    mirror = SITE_OUT / f"{date_str}.json"
    mirror.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"[wrote] {out.relative_to(REPO)} (and site mirror)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--week", action="store_true", help="Generate 7 days starting from --date")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.date:
        d0 = datetime.fromisoformat(args.date)
    else:
        d0 = datetime.now()

    days = 7 if args.week else 1
    for i in range(days):
        d = d0 + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        weekday = d.strftime("%A")
        target = OUT_DIR / f"{date_str}.json"
        if target.exists() and not args.dry_run:
            print(f"[skip exists] {date_str}")
            continue
        recent = load_recent_themes()
        blob = call_claude(date_str, weekday, recent)
        if not blob:
            return 1
        ok, msg = alignment_check(blob)
        if not ok:
            print(f"[alignment FAIL] {date_str}: {msg}")
            continue
        write_devotion(date_str, blob, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
