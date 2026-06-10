"""Produce one Dade episode end-to-end.

Reads the radio-adapted segments (001.radio.json) if present, else falls
back to the TV master. Builds a multi-voice plan against world.json's
voice_cast. Calls ElevenLabs once per voice segment. Stitches the MP3
streams into a single file at data/serials/dade/episodes/<n>.mp3.

SFX segments are recognized but skipped in v1 — we want a listenable
version of the episode first; sound design comes in pass 2 via the
ElevenLabs Sound Effects API.

Usage:
    python scripts/produce_dade_episode.py [ep_num] [--dry-run]
"""
import json
import os
import sys
import time
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Load .env, overwriting empty shell values
env_path = REPO / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not os.environ.get(k):
            os.environ[k] = v

from api import fountain, multi_voice  # noqa: E402

SLUG = "dade"
EP_DIR = REPO / "data" / "serials" / SLUG / "episodes"
WORLD_PATH = REPO / "data" / "serials" / SLUG / "world.json"

ep_num = 1
dry = False
for a in sys.argv[1:]:
    if a == "--dry-run":
        dry = True
    elif a.isdigit():
        ep_num = int(a)

# Pick source: radio.json preferred, else .json
radio_path = EP_DIR / f"{ep_num:03d}.radio.json"
tv_path    = EP_DIR / f"{ep_num:03d}.json"
src = radio_path if radio_path.exists() else tv_path
if not src.exists():
    print(f"ERROR: no episode source at {src}", file=sys.stderr)
    sys.exit(1)
using_radio = src == radio_path
print(f"Source: {src.name}  ({'RADIO-ADAPTED' if using_radio else 'TV master'})")

rec = json.loads(src.read_text(encoding="utf-8"))
segments = rec.get("segments") or []
world = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
voice_cast = world.get("voice_cast") or {}

narrator = (voice_cast.get("_narrator") or {}).get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")
if not narrator:
    print("ERROR: no narrator voice_id", file=sys.stderr); sys.exit(1)

speaker_voices = {
    name: info["voice_id"]
    for name, info in voice_cast.items()
    if not name.startswith("_") and isinstance(info, dict) and info.get("voice_id")
}

print(f"Episode: ep{ep_num:02d} '{rec.get('title')}' — {len(segments)} segments")
print(f"Voice cast loaded: {len(speaker_voices)} speakers; narrator {narrator}")

# Build the plan
plan = fountain.segments_to_audio_plan(
    segments=segments,
    voice_cast=speaker_voices,
    narrator_voice_id=narrator,
    include_scene_headings=True,
)

# v1: drop SFX (they have voice_id=None / skip=True) and any zero-length
plan = [p for p in plan if p.get("voice_id") and (p.get("text") or "").strip()]

# Stats
kind_counts = Counter(p.get("kind") for p in plan)
voice_counts = Counter(p.get("voice_id") for p in plan)
total_chars = sum(len((p.get("text") or "")) for p in plan)
est_cost = round(total_chars / 1000.0 * 0.30, 2)

print()
print("Plan built:")
print(f"  Total TTS segments: {len(plan)}")
for k, c in kind_counts.most_common():
    print(f"    {k}: {c}")
print(f"  Unique voices: {len(voice_counts)}")
print(f"  Total characters: {total_chars:,}")
print(f"  Est. chars on Pro quota: ~{total_chars:,} / 628,141 available")
print(f"  Equivalent USD if metered (~$0.30/1k): ${est_cost}")

# Unknown speakers (falling back to narrator)
unknown = set()
for s in segments:
    if s.get("kind") == "dialogue":
        sp = s.get("speaker", "")
        if sp and sp not in speaker_voices:
            unknown.add(sp)
if unknown:
    print(f"  Falling back to narrator for: {sorted(unknown)}")

if dry:
    print()
    print("--dry-run: no ElevenLabs calls.")
    sys.exit(0)

# Sanity: confirm ElevenLabs key
if not os.environ.get("ELEVENLABS_API_KEY"):
    print("ERROR: ELEVENLABS_API_KEY not configured", file=sys.stderr); sys.exit(1)

out_mp3 = EP_DIR / f"{ep_num:03d}.mp3"
print()
print(f"Producing -> {out_mp3}")
print("This will take ~5-15 minutes for the full episode.")
print()

t0 = time.time()
n_done = [0]
def on_progress(i, total, segment, error=None):
    n_done[0] = i
    if error:
        print(f"  [{i}/{total}] ERROR: {error}", flush=True)
    elif i % 25 == 0 or i == total:
        speaker = segment.get("speaker") or segment.get("kind")
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0
        eta_sec = (total - i) / rate if rate > 0 else 0
        print(f"  [{i:3d}/{total}] {speaker:20} | {elapsed:5.0f}s elapsed | ~{eta_sec:4.0f}s remaining", flush=True)

try:
    result = multi_voice.produce(plan=plan, output_path=out_mp3, on_progress=on_progress)
except Exception as e:
    print(f"\nFAILED at segment {n_done[0]}: {e}", file=sys.stderr)
    sys.exit(2)

elapsed = time.time() - t0
print()
print(f"DONE in {elapsed/60:.1f} min")
print(f"  Output: {out_mp3}")
print(f"  Size:   {result['bytes_written']:,} bytes ({result['bytes_written']/1024/1024:.1f} MB)")
print(f"  Voices used: {len(result.get('voices_used',[]))}")

# Update the episode record with audio metadata
rec["produced"] = True
rec["produced_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
rec["audio_bytes"] = result["bytes_written"]
rec["audio_url"]   = f"/serial/{SLUG}/audio/{ep_num}"
rec["voices_used"] = result.get("voices_used")
rec["produced_from"] = "radio_adapted" if using_radio else "tv_master"
rec["produced_v1_no_sfx"] = True
src.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

# Also update the canonical 001.json with audio_url so /dade.html picks it up
canonical = EP_DIR / f"{ep_num:03d}.json"
if canonical.exists() and canonical != src:
    canon_rec = json.loads(canonical.read_text(encoding="utf-8"))
    canon_rec["produced"] = True
    canon_rec["produced_at_iso"] = rec["produced_at_iso"]
    canon_rec["audio_bytes"] = rec["audio_bytes"]
    canon_rec["audio_url"]   = rec["audio_url"]
    canon_rec["voices_used"] = rec["voices_used"]
    canon_rec["produced_from"] = rec["produced_from"]
    canon_rec["produced_v1_no_sfx"] = True
    canonical.write_text(json.dumps(canon_rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Updated canonical: {canonical.name}")

print()
print(f"Listen: https://narrowhighway.com/serial/{SLUG}/audio/{ep_num}")
print(f"        https://narrowhighway.com/dade.html  (after page wires player)")
