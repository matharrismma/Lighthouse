"""Replace the 45 EPUB-derived chapters with the 12 canonical Apokalypsis
production scripts from the ElevenLabs zip (already extracted into
data/serials/_source/apokalypsis_audio_drop/).

These are the audio-ready scripts that match the Spotify episodes —
single-narrator (John of Patmos), one txt file per episode, named
ep01_the_exile.txt through ep12_the_face.txt.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO / "data" / "serials" / "_source" / "apokalypsis_audio_drop"
EPISODES_DIR = REPO / "data" / "serials" / "apokalypsis" / "episodes"

EP_RE = re.compile(r"^ep(\d+)_(.+)\.txt$", re.IGNORECASE)

# Make slug → human title
def _title_from_slug(slug: str) -> str:
    parts = slug.replace("_", " ").split()
    # Drop leading "the" we'll re-add naturally
    return " ".join(w.capitalize() for w in parts)

# Title overrides for the canonical 12
TITLES = {
    "ep01_the_exile.txt":     "The Exile",
    "ep02_the_fire.txt":      "The Fire",
    "ep03_the_throne.txt":    "The Throne",
    "ep04_the_horsemen.txt":  "The Horsemen",
    "ep05_the_silence.txt":   "The Silence",
    "ep06_the_trumpets.txt":  "The Trumpets",
    "ep07_the_witnesses.txt": "The Witnesses",
    "ep08_the_beasts.txt":    "The Beasts",
    "ep09_the_harvest.txt":   "The Harvest",
    "ep10_the_fall.txt":      "The Fall",
    "ep11_the_rider.txt":     "The Rider",
    "ep12_the_face.txt":      "The Face",
}

print(f"Clearing old Apokalypsis episodes…")
if EPISODES_DIR.exists():
    for f in EPISODES_DIR.glob("*"):
        f.unlink()
EPISODES_DIR.mkdir(parents=True, exist_ok=True)

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
count = 0
total_words = 0

for f in sorted(SOURCE_DIR.glob("ep*.txt")):
    m = EP_RE.match(f.name)
    if not m:
        continue
    ep_num = int(m.group(1))
    title = TITLES.get(f.name) or _title_from_slug(m.group(2))
    script = f.read_text(encoding="utf-8").strip()
    word_count = len(script.split())

    rec = {
        "serial":            "apokalypsis",
        "ep_num":            ep_num,
        "title":             title,
        "script":            script,
        "summary":           "",
        "continuity_note":   "",
        "word_count":        word_count,
        "drafted_at_iso":    now_iso,
        "ingested_from":     f.name,
        "source_kind":       "elevenlabs_production_script",
        "produced":          False,  # Will be true once the MP3 is on disk; for now, on Spotify
        "spotify_show_url":  "https://open.spotify.com/show/0zWxTwkyiBEUjNmQwEG63Z",
    }
    json_path = EPISODES_DIR / f"{ep_num:03d}.json"
    json_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    count += 1
    total_words += word_count
    print(f"  {f.name} -> ep {ep_num:02d} \"{title}\" ({word_count} words)")

print(f"\nWrote {count} episodes to {EPISODES_DIR}")
print(f"Total words: {total_words:,}")
print("\nThe Spotify show (0zWxTwkyiBEUjNmQwEG63Z) embedded on /apokalypsis.html provides the audio.")
