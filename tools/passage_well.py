#!/usr/bin/env python3
"""passage_well.py — draw original leveled reading passages into the Well.

The Well is not a feed. It is a well of knowledge we draw from — and it helps
the reader become a spring of ideas. This tool fills the well with ORIGINAL,
family-safe reading passages that use public-domain characters (Aesop, folk
tales, pre-1930 classics) to add interest. We never reproduce a copyrighted
text or a post-1930 studio's design; the words are our own.

Sources:
  - data/characters/public_domain.jsonl   (the PD character roster)
  - data/well/passages.jsonl              (where drawn passages are stored)

Spend discipline: every generation goes through tools/spend_guard.py. Default
is --dry-run (shows the prompt + estimated cost, spends nothing). Pass --apply
to actually call the model (cheap Haiku) and append the result.

Usage:
    python tools/passage_well.py --list-characters
    python tools/passage_well.py --character tortoise_hare --level early_reader      # dry-run
    python tools/passage_well.py --character lion_mouse --level emergent --apply
    python tools/passage_well.py --all --level early_reader --apply                  # one per character
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
sys.path.insert(0, str(REPO_ROOT / "tools"))

CHARACTERS = REPO_ROOT / "data" / "characters" / "public_domain.jsonl"
WELL = REPO_ROOT / "data" / "well" / "passages.jsonl"
MODEL = os.environ.get("NH_HAIKU_MODEL", "claude-haiku-4-5-20251001")
EST_PER_PASSAGE = 0.012  # generous Haiku estimate, USD

LEVELS = {
    "emergent":     {"words": "40 to 70",  "style": "very simple sentences, mostly short common words a 5-7 year old can decode, present or simple past tense"},
    "early_reader": {"words": "70 to 120", "style": "simple sentences with a clear beginning, middle, and end, for a 6-9 year old"},
    "fluent":       {"words": "120 to 200", "style": "two to four short paragraphs with some richer vocabulary, for a 9-12 year old"},
}

_SYSTEM = (
    "You write original, wholesome, family-safe reading passages for a Christian "
    "homeschool. ABSOLUTE RULES: (1) Use ONLY your own original wording — never "
    "copy, quote, or closely paraphrase any specific published text or translation. "
    "(2) The character is a public-domain figure used only as inspiration; do NOT "
    "imitate any post-1930 studio's design, names, or dialogue (e.g. Disney). "
    "(3) Keep it gentle and true — no violence beyond the gentlest fairy-tale level, "
    "nothing frightening, nothing that contradicts Scripture. Output ONLY a JSON "
    'object: {"title": "...", "text": "...", "lesson": "one short sentence"}.'
)


def _read_jsonl(p: Path) -> list:
    out = []
    if not p.exists():
        return out
    for ln in p.read_text("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _load_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if k:
        return k
    for d in [REPO_ROOT, Path(__file__).parent]:
        env_file = d / ".env"
        if env_file.exists():
            for line in env_file.read_text("utf-8", errors="replace").splitlines():
                m = re.match(r"ANTHROPIC_API_KEY=(.+)", line.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'").lstrip("<").rstrip(">")
    return ""


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:48]


def _prompt_for(ch: dict, level: str) -> str:
    spec = LEVELS[level]
    return (
        f"Write an original {level.replace('_', ' ')} reading passage of {spec['words']} words, "
        f"in {spec['style']}.\n\n"
        f"Feature the public-domain character/tale: {ch.get('name')} "
        f"(inspired by {ch.get('source_work')}). Teach the virtue of "
        f"{ch.get('virtue', 'goodness')}. Use your own original wording entirely. "
        f"End with one short lesson sentence."
    )


def generate(ch: dict, level: str, apply: bool) -> dict | None:
    prompt = _prompt_for(ch, level)
    if not apply:
        print(f"\n— DRY RUN — would generate [{level}] for {ch['id']} (~${EST_PER_PASSAGE})")
        print(f"  prompt: {prompt[:160]}…")
        return None

    try:
        import spend_guard
    except Exception:
        print("[well] spend_guard unavailable — refusing to spend.", file=sys.stderr)
        return None
    if not spend_guard.can_spend(EST_PER_PASSAGE):
        print(f"[well] OVER BUDGET — remaining ${spend_guard.remaining()}. Skipping.", file=sys.stderr)
        return None

    key = _load_key()
    if not key:
        print("[well] no ANTHROPIC_API_KEY — cannot generate.", file=sys.stderr)
        return None

    try:
        import anthropic
    except ImportError:
        print("[well] pip install anthropic", file=sys.stderr)
        return None

    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=MODEL, max_tokens=700, system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}])
    raw = "".join(getattr(b, "text", "") for b in resp.content).strip()

    # record actual-ish spend (Haiku pricing is tiny; use the estimate)
    try:
        spend_guard.record("bg_well_passage", EST_PER_PASSAGE)
    except Exception:
        pass

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        print(f"[well] model did not return JSON for {ch['id']}", file=sys.stderr)
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        print(f"[well] bad JSON for {ch['id']}", file=sys.stderr)
        return None

    text = (obj.get("text") or "").strip()
    rec = {
        "schema": "narrowhighway.well_passage/1",
        "id": f"well_{ch['id']}_{level}_{_slug(obj.get('title', ''))}"[:80],
        "title": (obj.get("title") or ch["name"]).strip(),
        "character_ids": [ch["id"]],
        "level": level,
        "word_count": len(text.split()),
        "text": text,
        "lesson": (obj.get("lesson") or "").strip(),
        "source_inspiration": f"{ch.get('source_work')} (public domain)",
        "ties_to": ["track:reading", f"virtue:{_slug(ch.get('virtue', ''))}"],
        "origin": "haiku",
        "added_at": datetime.now(timezone.utc).date().isoformat(),
    }
    WELL.parent.mkdir(parents=True, exist_ok=True)
    with WELL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[well] drew '{rec['title']}' ({rec['word_count']}w, {level}) -> {ch['id']}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="Draw original passages into the Well")
    ap.add_argument("--character", help="character id from the PD roster")
    ap.add_argument("--all", action="store_true", help="one passage per character")
    ap.add_argument("--level", choices=list(LEVELS), default="early_reader")
    ap.add_argument("--apply", action="store_true", help="actually spend + generate (default: dry-run)")
    ap.add_argument("--list-characters", action="store_true")
    args = ap.parse_args()

    roster = _read_jsonl(CHARACTERS)
    by_id = {c["id"]: c for c in roster}

    if args.list_characters:
        for c in roster:
            print(f"  {c['glyph']} {c['id']:22} {c['name']}  ({c.get('virtue', '')})")
        return 0

    if args.all:
        targets = roster
    elif args.character:
        if args.character not in by_id:
            print(f"unknown character {args.character!r}", file=sys.stderr)
            return 2
        targets = [by_id[args.character]]
    else:
        print("specify --character <id>, --all, or --list-characters", file=sys.stderr)
        return 2

    for ch in targets:
        generate(ch, args.level, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
