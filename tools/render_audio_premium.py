"""ElevenLabs marquee narration — paid quality for high-engagement content.

Pairs with render_audio.py (Piper, free, bulk). This tool is for MARQUEE:
- Spurgeon sermon excerpts → Steady Pastor voice
- Pilgrim's Progress chapters → Storyteller voice
- Augustine readings → Codex Reader voice
- Almanac entries that earned thumbs-up → Newscaster voice

Per the storage-discipline rule: this should only run on content that's earned
engagement OR on operator-curated marquee pieces. ~628k char/month budget.

Pre-req:
  - ELEVENLABS_API_KEY env var set
  - pip install elevenlabs (or use raw requests; this tool uses requests directly
    so the SDK is optional)

Usage:
  python tools/render_audio_premium.py --check
  python tools/render_audio_premium.py --text-file <path> --voice steady_pastor --out <mp3>
  python tools/render_audio_premium.py --substrate spurgeon --voice steady_pastor
  python tools/render_audio_premium.py --hymn amazing-grace --voice hymnal

Voice palette (configurable below):
  steady_pastor   — Spurgeon, Edwards
  storyteller     — Pilgrim's Progress, parables
  codex_reader    — Augustine, Boethius, Easton's
  lighthouse_kids — children's content
  newscaster      — almanac, "on this day"
  hymnal          — hymn read-throughs

Output:
  D:/library_files/<slug>/marquee.mp3  + manifest.audio_renders_premium[]

Standing rule: always include "more at narrowhighway.com" outro for distribution-
ready pieces. Use --no-outro for substrate-only renders.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import urllib.request as request
import urllib.error as urlerr

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

REPO = Path(__file__).resolve().parent.parent
STORAGE_ROOT = Path("D:/library_files")
ELEVEN_API = "https://api.elevenlabs.io/v1"

# Voice palette — operator-set voice_ids per category.
# These are placeholder IDs; Matt must fill in actual voice_ids from his
# ElevenLabs account (account.elevenlabs.io/voice-library).
VOICES = {
    "steady_pastor":   {"voice_id": "EXAMPLE_STEADY_PASTOR_ID",   "stability": 0.65, "similarity": 0.75, "style": 0.30},
    "storyteller":     {"voice_id": "EXAMPLE_STORYTELLER_ID",     "stability": 0.55, "similarity": 0.70, "style": 0.55},
    "codex_reader":    {"voice_id": "EXAMPLE_CODEX_READER_ID",    "stability": 0.70, "similarity": 0.80, "style": 0.20},
    "lighthouse_kids": {"voice_id": "EXAMPLE_LIGHTHOUSE_KIDS_ID", "stability": 0.50, "similarity": 0.65, "style": 0.60},
    "newscaster":      {"voice_id": "EXAMPLE_NEWSCASTER_ID",      "stability": 0.65, "similarity": 0.75, "style": 0.40},
    "hymnal":          {"voice_id": "EXAMPLE_HYMNAL_ID",          "stability": 0.75, "similarity": 0.80, "style": 0.25},
}

OUTRO_TEXT = (
    "Narrow Highway — a curated internet for Christian families. "
    "Find more at NarrowHighway dot com."
)


def api_key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY")


def voice_setup_ok(voice_key: str) -> bool:
    v = VOICES.get(voice_key)
    return v and not v["voice_id"].startswith("EXAMPLE_")


def estimate_chars(text: str) -> int:
    return len(text)


def quota_status() -> dict | None:
    key = api_key()
    if not key: return None
    req = request.Request(f"{ELEVEN_API}/user/subscription", headers={"xi-api-key": key})
    try:
        with request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def synthesize(text: str, voice_key: str, out_path: Path) -> bool:
    key = api_key()
    if not key:
        print(f"[skip] ELEVENLABS_API_KEY not set")
        return False
    if not voice_setup_ok(voice_key):
        print(f"[skip] Voice '{voice_key}' has placeholder voice_id; edit VOICES dict with actual IDs from your ElevenLabs account.")
        return False
    v = VOICES[voice_key]
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": v["stability"],
            "similarity_boost": v["similarity"],
            "style": v["style"],
            "use_speaker_boost": True,
        },
    }
    url = f"{ELEVEN_API}/text-to-speech/{v['voice_id']}"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with request.urlopen(req, timeout=300) as r:
            out_path.write_bytes(r.read())
        return True
    except urlerr.HTTPError as e:
        print(f"[err] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}")
        return False
    except Exception as e:
        print(f"[err] {e}")
        return False


def render_text(text: str, voice_key: str, out_path: Path, include_outro: bool = True) -> bool:
    if include_outro:
        text = text.rstrip() + "\n\n" + OUTRO_TEXT
    chars = estimate_chars(text)
    print(f"[render] {voice_key} · {chars} chars · → {out_path}")
    return synthesize(text, voice_key, out_path)


def render_hymn(slug: str, voice_key: str = "hymnal") -> bool:
    hymns_path = REPO / "site" / "hymns.json"
    if not hymns_path.exists():
        print(f"[err] {hymns_path} missing; run tools/hymnary_scrape.py first")
        return False
    blob = json.loads(hymns_path.read_text(encoding="utf-8"))
    h = next((x for x in blob.get("hymns", []) if x.get("slug") == slug), None)
    if not h:
        print(f"[err] hymn slug not found: {slug}")
        return False
    out = STORAGE_ROOT / "hymn_renders_premium" / f"{slug}.mp3"
    return render_text(h["text"], voice_key, out, include_outro=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quota", action="store_true")
    ap.add_argument("--voice", default="codex_reader", choices=list(VOICES.keys()))
    ap.add_argument("--text-file", help="Text file to narrate")
    ap.add_argument("--hymn", help="Hymn slug from hymns.json")
    ap.add_argument("--out", help="Output MP3 path (with --text-file)")
    ap.add_argument("--no-outro", action="store_true", help="Skip the 'narrowhighway.com' outro")
    args = ap.parse_args()

    if args.check:
        key = api_key()
        print(f"ELEVENLABS_API_KEY: {'✓ set' if key else '✗ NOT set'}")
        print(f"Voice slots configured: {sum(1 for k in VOICES if voice_setup_ok(k))}/{len(VOICES)}")
        print(f"  (edit the VOICES dict in {Path(__file__).name} with your actual voice_ids)")
        if not key:
            print(f"\nSet env var (PowerShell): $env:ELEVENLABS_API_KEY = 'sk_...'")
        for k, v in VOICES.items():
            status = "✓" if voice_setup_ok(k) else "✗ placeholder"
            print(f"  {k:18} {status:12}  {v['voice_id']}")
        return 0

    if args.quota:
        q = quota_status()
        if not q: print("Set ELEVENLABS_API_KEY first.")
        else: print(json.dumps(q, indent=2))
        return 0

    if args.hymn:
        return 0 if render_hymn(args.hymn, args.voice) else 1
    if args.text_file:
        if not args.out:
            print("--out required with --text-file"); return 2
        text = Path(args.text_file).read_text(encoding="utf-8")
        return 0 if render_text(text, args.voice, Path(args.out), include_outro=not args.no_outro) else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
