"""Adapt + produce Dade Season 1 episodes 2-13 in one chained pass.

For each episode:
  1. If no 00N.radio.json exists, adapt via Claude (radio_adapter)
  2. If no 00N.mp3 exists, produce via ElevenLabs (multi_voice)

Skips episodes already done. Resumable. Prints progress per episode.

Usage:
    python scripts/batch_dade_s1.py [--from N] [--to M] [--dry-run]
                                    [--skip-adapt] [--skip-produce]
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Load .env with empty-value override (Windows cmd shells set blank env vars)
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

from api import fountain, multi_voice, radio_adapter  # noqa: E402

SLUG = "dade"
EP_DIR = REPO / "data" / "serials" / SLUG / "episodes"
WORLD_PATH = REPO / "data" / "serials" / SLUG / "world.json"

start_ep = 2
end_ep = 13
dry = False
skip_adapt = False
skip_produce = False

args = list(sys.argv[1:])
i = 0
while i < len(args):
    a = args[i]
    if a == "--dry-run":
        dry = True
    elif a == "--skip-adapt":
        skip_adapt = True
    elif a == "--skip-produce":
        skip_produce = True
    elif a == "--from" and i + 1 < len(args):
        start_ep = int(args[i + 1]); i += 1
    elif a == "--to" and i + 1 < len(args):
        end_ep = int(args[i + 1]); i += 1
    i += 1

world = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
voice_cast = world.get("voice_cast") or {}
narrator = (voice_cast.get("_narrator") or {}).get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")
speaker_voices = {
    name: info["voice_id"]
    for name, info in voice_cast.items()
    if not name.startswith("_") and isinstance(info, dict) and info.get("voice_id")
}

print(f"=== Dade S1 batch: episodes {start_ep}-{end_ep} ===")
print(f"Narrator: {narrator}")
print(f"Speakers: {len(speaker_voices)}")
print(f"Dry run: {dry}")
print(f"Skip adapt: {skip_adapt}  Skip produce: {skip_produce}")
print()

t_total = time.time()

for ep_num in range(start_ep, end_ep + 1):
    print(f"--- Episode {ep_num:02d} ---", flush=True)
    tv_path    = EP_DIR / f"{ep_num:03d}.json"
    radio_path = EP_DIR / f"{ep_num:03d}.radio.json"
    mp3_path   = EP_DIR / f"{ep_num:03d}.mp3"

    if not tv_path.exists():
        print(f"  no TV master at {tv_path.name}, skip", flush=True)
        continue

    # ── 1. Radio adaptation ──
    if radio_path.exists():
        print(f"  radio.json exists, skip adaptation", flush=True)
    elif skip_adapt:
        print(f"  --skip-adapt set, skip adaptation", flush=True)
    elif dry:
        print(f"  [dry-run] would adapt TV to radio", flush=True)
    else:
        t0 = time.time()
        rec = json.loads(tv_path.read_text(encoding="utf-8"))
        segments = rec.get("segments") or []
        scene_count = sum(1 for s in segments if s.get("kind") == "scene_heading")
        print(f"  adapting {len(segments)} segments / ~{scene_count} scenes...", flush=True)

        def progress(i, total, result):
            if i % 5 == 0 or i == total:
                print(f"    scene {i}/{total} -> {len(result)} radio segments  ({(time.time()-t0):.0f}s)", flush=True)

        try:
            result = radio_adapter.adapt_episode(segments, on_progress=progress)
        except Exception as e:
            print(f"  ADAPT FAILED: {e}", flush=True)
            continue

        adapted_rec = dict(rec)
        adapted_rec["segments"] = result["adapted_segments"]
        adapted_rec["adapted_from_tv"] = True
        adapted_rec["adapter_model"]   = result["model"]
        adapted_rec["adapter_stats"]   = result["stats"]
        radio_path.write_text(json.dumps(adapted_rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  adapted in {(time.time()-t0)/60:.1f} min", flush=True)

    # ── 2. Audio production ──
    if mp3_path.exists():
        print(f"  {mp3_path.name} already exists ({mp3_path.stat().st_size:,} bytes), skip produce", flush=True)
        continue
    if skip_produce:
        print(f"  --skip-produce set, skip", flush=True)
        continue
    if dry:
        print(f"  [dry-run] would produce {mp3_path.name}", flush=True)
        continue

    src = radio_path if radio_path.exists() else tv_path
    using_radio = src == radio_path
    rec = json.loads(src.read_text(encoding="utf-8"))
    segments = rec.get("segments") or []

    plan = fountain.segments_to_audio_plan(
        segments=segments,
        voice_cast=speaker_voices,
        narrator_voice_id=narrator,
        include_scene_headings=True,
    )
    plan = [p for p in plan if p.get("voice_id") and (p.get("text") or "").strip()]
    total_chars = sum(len(p.get("text", "")) for p in plan)
    print(f"  producing {len(plan)} TTS calls / {total_chars:,} chars ({'radio' if using_radio else 'tv'})", flush=True)

    t0 = time.time()
    last_log = [0]
    def on_progress(i, total, segment, error=None):
        if error:
            print(f"    [{i}/{total}] ERROR: {error}", flush=True)
        elif i - last_log[0] >= 50 or i == total:
            last_log[0] = i
            elapsed = time.time() - t0
            print(f"    [{i:3d}/{total}] {(segment.get('speaker') or segment.get('kind') or ''):20} | {elapsed:5.0f}s", flush=True)

    try:
        result = multi_voice.produce(plan=plan, output_path=mp3_path, on_progress=on_progress)
    except Exception as e:
        print(f"  PRODUCE FAILED: {e}", flush=True)
        continue

    print(f"  produced {mp3_path.name} -- {result['bytes_written']/1024/1024:.1f} MB in {(time.time()-t0)/60:.1f} min", flush=True)

    # Update both files with audio metadata
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for p in [src, tv_path]:
        if not p.exists(): continue
        r = json.loads(p.read_text(encoding="utf-8"))
        r["produced"] = True
        r["produced_at_iso"] = iso
        r["audio_bytes"] = result["bytes_written"]
        r["audio_url"]   = f"/serial/{SLUG}/audio/{ep_num}"
        r["voices_used"] = result.get("voices_used")
        r["produced_from"] = "radio_adapted" if using_radio else "tv_master"
        r["produced_v1_no_sfx"] = True
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print()

elapsed = (time.time() - t_total) / 60
print(f"=== Batch done in {elapsed:.1f} min ===")
print()
print("Verify:")
print(f"  https://narrowhighway.com/dade.html")
print(f"  https://narrowhighway.com/serial/dade")
