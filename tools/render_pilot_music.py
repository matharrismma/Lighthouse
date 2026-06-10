"""Render original music + foley for the two pilot series via ElevenLabs Music + Sound APIs.

Music palette per series (used across all episodes of that series):
  - sci_fi_theme_main      — 45-sec opener, plays under intro VO
  - sci_fi_theme_closing   — 30-sec elegiac close, plays under pastoral closing line
  - hundred_acre_theme_main — 45-sec gentle English-folk opener
  - hundred_acre_theme_closing — 30-sec resolution close

Foley for Soft Rains pilot (sound design layer over the broadcast body):
  - wind_storm_loud (Scene 13)
  - tree_falling_crack (Scene 14)
  - fire_crackle_intense (Scenes 18-20)
  - rain_aftermath_gentle (Scene 21)

Output: D:/library_files/_pilot_music/<name>.mp3
        D:/library_files/_pilot_foley/<name>.mp3
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import urllib.request
import urllib.error
import json
import time

KEY = os.environ["ELEVENLABS_API_KEY"]

MUSIC_OUT = Path("D:/library_files/_pilot_music")
FOLEY_OUT = Path("D:/library_files/_pilot_foley")
MUSIC_OUT.mkdir(parents=True, exist_ok=True)
FOLEY_OUT.mkdir(parents=True, exist_ok=True)

MUSIC_PIECES = [
    {
        "name": "scifi_theme_main",
        "prompt": (
            "Vintage 1950s atomic-age science-fiction television theme. "
            "Theremin lead with melancholy, sustained woodwind chords, "
            "subtle bass throb, occasional vibraphone. Slightly eerie but reassuring. "
            "Opens with a slow ascending phrase, develops into a memorable melodic hook, "
            "ends with a slight unresolved tension. Like the Twilight Zone, like Dimension X, "
            "like the dawn of the atomic age. No vocals."
        ),
        "duration_ms": 45000,
    },
    {
        "name": "scifi_theme_closing",
        "prompt": (
            "Quiet elegiac instrumental coda, 1950s style. Single muted trumpet over "
            "sustained strings, gentle brushed snare. Mood of acceptance and quiet sorrow. "
            "Like the end credits of a Twilight Zone episode. Slow tempo, "
            "ends on a soft major chord. No vocals."
        ),
        "duration_ms": 30000,
    },
    {
        "name": "hundred_acre_theme_main",
        "prompt": (
            "Gentle pastoral English folk instrumental theme. Recorder, oboe, light strings, "
            "soft brushed cymbal, fingerpicked guitar. Pastoral, warm, slightly nostalgic. "
            "Memorable melodic hook, like a children's book come to life. "
            "Think Vaughan Williams 'The Lark Ascending' or 'Greensleeves' arranged for picture book. "
            "Major key, ends on a gentle resolution. No vocals."
        ),
        "duration_ms": 45000,
    },
    {
        "name": "hundred_acre_theme_closing",
        "prompt": (
            "Soft gentle English folk closing instrumental, very short. Single oboe melody over "
            "warm strings. Bedtime-story conclusion. Slow tempo, major key, resolves on a "
            "peaceful note. Like a parent closing a storybook. No vocals."
        ),
        "duration_ms": 30000,
    },
]

FOLEY = [
    {
        "name": "wind_storm_loud",
        "text": "Howling storm wind through trees, shutters banging, dramatic and threatening, 12 seconds",
        "duration_sec": 12,
    },
    {
        "name": "tree_falling_crack",
        "text": "Massive oak tree cracking, splintering wood, then a deep impactful crash into earth and debris, 8 seconds",
        "duration_sec": 8,
    },
    {
        "name": "fire_crackle_intense",
        "text": "Large house fire crackling intensely, wood beams collapsing, glass breaking from heat, 15 seconds",
        "duration_sec": 15,
    },
    {
        "name": "rain_aftermath_gentle",
        "text": "Gentle rain falling on ashes and ruined wood, distant birdsong, peaceful aftermath, 15 seconds",
        "duration_sec": 15,
    },
]


def post_music(payload, headers, out_path: Path) -> tuple[int, bytes]:
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/music",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        return r.status, r.read()


def post_sound(payload, headers, out_path: Path) -> tuple[int, bytes]:
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/sound-generation",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.status, r.read()


def render_music():
    print("=== Music ===")
    headers = {"xi-api-key": KEY, "Content-Type": "application/json", "accept": "audio/mpeg"}
    for piece in MUSIC_PIECES:
        out = MUSIC_OUT / f"{piece['name']}.mp3"
        if out.exists() and out.stat().st_size > 5000:
            print(f"  [SKIP] {out.name}")
            continue
        payload = {"prompt": piece["prompt"], "music_length_ms": piece["duration_ms"]}
        try:
            status, audio = post_music(payload, headers, out)
            out.write_bytes(audio)
            print(f"  [OK]   {out.name}  {len(audio)//1024} KB  ({piece['duration_ms']/1000}s)")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"  [FAIL] {out.name}  HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL] {out.name}  {type(e).__name__}: {e}")


def render_foley():
    print("=== Foley ===")
    headers = {"xi-api-key": KEY, "Content-Type": "application/json", "accept": "audio/mpeg"}
    for f in FOLEY:
        out = FOLEY_OUT / f"{f['name']}.mp3"
        if out.exists() and out.stat().st_size > 5000:
            print(f"  [SKIP] {out.name}")
            continue
        payload = {"text": f["text"], "duration_seconds": f["duration_sec"]}
        try:
            status, audio = post_sound(payload, headers, out)
            out.write_bytes(audio)
            print(f"  [OK]   {out.name}  {len(audio)//1024} KB  ({f['duration_sec']}s)")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"  [FAIL] {out.name}  HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL] {out.name}  {type(e).__name__}: {e}")


def usage_check():
    req = urllib.request.Request("https://api.elevenlabs.io/v1/user",
                                  headers={"xi-api-key": KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    sub = data.get("subscription", {})
    print(f"ElevenLabs tier: {sub.get('tier')}  used: {sub.get('character_count')}/{sub.get('character_limit')}")


if __name__ == "__main__":
    usage_check()
    print()
    render_music()
    print()
    render_foley()
    print()
    usage_check()
