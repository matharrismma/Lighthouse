"""render_tts.py — Render Spurgeon + Edwards text to audio via Piper TTS.

Free, local, no API costs. Piper is a C++ neural TTS that runs on CPU and
produces broadcast-quality narration (16kHz/22kHz mono WAV). For the channel,
we then mux the WAV to MP3 / MP4 for playback compatibility.

Input texts come from CCEL or Project Gutenberg (PD). For each work we have
a fetch function that pulls the canonical chapters, splits into devotional
chunks (one chapter per file for sermons; one morning/evening reading for
Spurgeon's M&E), and feeds each chunk through Piper.

Output paths match what the channel manifest already expects:
  spurgeon_morning_evening → D:/library_files/spurgeon_morning_evening/morningevening_<N>.mp3
  spurgeon_all_of_grace    → D:/library_files/spurgeon_all_of_grace/allofgrace_<N>.mp3
  edwards_select_sermons   → D:/library_files/edwards_select_sermons/edwards_sermon_<N>.mp3
  edwards_religious_affections → D:/library_files/edwards_religious_affections/affections_<N>.mp3

Piper setup (one time, free):
  1. Download Piper: https://github.com/rhasspy/piper/releases
     Extract to C:\\Concordance\\piper\\
  2. Download a voice model (Lessac is clear US English baritone — good for sermons):
     https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium
     Save en_US-lessac-medium.onnx + .json to C:\\Concordance\\piper\\voices\\

Run:
  python tools/render_tts.py --probe              # check Piper install + voice models
  python tools/render_tts.py --source spurgeon_morning_evening --limit 3 --dry-run
  python tools/render_tts.py --source spurgeon_morning_evening --apply
  python tools/render_tts.py --source edwards_select_sermons --apply

After rendering, run:
  python tools/duration_cache.py --warm     # registers new files for the scheduler
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
PIPER_DIR = Path("C:/Concordance/piper")
PIPER_BIN = PIPER_DIR / "piper.exe"
PIPER_VOICES = PIPER_DIR / "voices"
DEFAULT_VOICE = "en_US-lessac-medium"

# Output destinations (match channel manifest expectations)
OUTPUT_BASE = Path("D:/library_files")

# Source URL fetch — public-domain text sources
SOURCE_URLS = {
    "spurgeon_morning_evening": {
        "url": "https://www.ccel.org/ccel/spurgeon/morneve.txt",
        "fallback": "https://www.gutenberg.org/cache/epub/9398/pg9398.txt",
    },
    "spurgeon_all_of_grace": {
        "url": "https://www.gutenberg.org/cache/epub/636/pg636.txt",
    },
    "edwards_select_sermons": {
        "url": "https://www.ccel.org/ccel/edwards/sermons.txt",
        "fallback": "https://www.gutenberg.org/cache/epub/16934/pg16934.txt",  # Sinners in the Hands placeholder
    },
    "edwards_religious_affections": {
        "url": "https://www.ccel.org/ccel/edwards/affections.txt",
    },
}


def probe_piper() -> dict:
    """Check Piper installation and voice availability. Returns a status dict."""
    status = {
        "piper_bin": str(PIPER_BIN),
        "piper_installed": PIPER_BIN.exists(),
        "voices_dir": str(PIPER_VOICES),
        "voices_available": [],
        "default_voice": DEFAULT_VOICE,
        "default_voice_ready": False,
    }
    if PIPER_VOICES.exists():
        for f in PIPER_VOICES.glob("*.onnx"):
            status["voices_available"].append(f.stem)
        cfg = PIPER_VOICES / f"{DEFAULT_VOICE}.onnx.json"
        onnx = PIPER_VOICES / f"{DEFAULT_VOICE}.onnx"
        status["default_voice_ready"] = cfg.exists() and onnx.exists()
    return status


def fetch_source_text(source_key: str) -> str:
    """Download the public-domain text. Try CCEL first, fall back to PG."""
    urls = SOURCE_URLS.get(source_key, {})
    for url_key in ("url", "fallback"):
        url = urls.get(url_key)
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "NarrowHighway/1.0 (curated Christian family channel)"
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [{url_key}] {url} failed: {e}", flush=True)
            continue
    raise RuntimeError(f"could not fetch source for {source_key}")


def split_spurgeon_morning_evening(text: str) -> list[tuple[str, str]]:
    """Split into 730 entries (morning + evening for 365 days).
    Returns [(label, text), ...]."""
    # Spurgeon M&E uses "MORNING.—" and "EVENING.—" headers (em-dash variants vary)
    pattern = re.compile(r"(MORNING|EVENING)[.,]?\s*[—\-–]\s*\"?([^\n]*)\n", re.IGNORECASE)
    chunks = []
    parts = pattern.split(text)
    # parts = ['preamble', 'MORNING', 'verse...', 'next content', 'EVENING', 'verse...', ...]
    for i in range(1, len(parts), 3):
        if i + 1 >= len(parts):
            break
        period = parts[i].strip()
        verse = parts[i + 1].strip().strip('"').strip()
        body = parts[i + 2] if i + 2 < len(parts) else ""
        # Trim body at the next MORNING/EVENING header
        body = re.split(r"(MORNING|EVENING)[.,]?\s*[—\-–]", body, maxsplit=1)[0].strip()
        if not body or len(body) < 50:
            continue
        label = f"{period.title()} — {verse[:50]}"
        full_text = f"{period}. {verse}. {body}"
        chunks.append((label, full_text))
    return chunks


def split_by_chapter(text: str) -> list[tuple[str, str]]:
    """Generic chapter splitter: looks for 'Chapter N' or 'Sermon N' markers."""
    pattern = re.compile(r"^\s*(?:Chapter|Sermon|SERMON|Section)\s+([IVXLCM\d]+)\.?\s*$",
                         re.MULTILINE | re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        # Fallback: split on long blank-line runs into roughly chapter-sized chunks
        rough = re.split(r"\n\s*\n\s*\n\s*\n", text)
        return [(f"Section {i+1}", t.strip()) for i, t in enumerate(rough) if len(t.strip()) > 500]
    chunks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = f"Chapter {m.group(1)}"
        body = text[start:end].strip()
        if len(body) > 200:
            chunks.append((label, body))
    return chunks


def render_chunk_to_wav(text: str, output_wav: Path, voice: str = DEFAULT_VOICE) -> bool:
    """Pipe text into piper.exe, capture WAV to output_wav."""
    voice_onnx = PIPER_VOICES / f"{voice}.onnx"
    if not voice_onnx.exists():
        print(f"  voice model not found: {voice_onnx}", flush=True)
        return False
    if not PIPER_BIN.exists():
        print(f"  Piper binary not found: {PIPER_BIN}", flush=True)
        return False
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(PIPER_BIN), "--model", str(voice_onnx), "--output_file", str(output_wav)],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=600,
    )
    return proc.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 1000


def wav_to_mp3(wav: Path, mp3: Path) -> bool:
    """Use ffmpeg to convert WAV → MP3 (smaller, broadcast-compatible)."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3)],
        capture_output=True,
        timeout=300,
    )
    if proc.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
        wav.unlink(missing_ok=True)
        return True
    return False


CONFIG_BY_SOURCE = {
    "spurgeon_morning_evening": {
        "splitter": split_spurgeon_morning_evening,
        "out_dir": OUTPUT_BASE / "spurgeon_morning_evening",
        "filename_pattern": "morningevening_{i:03d}.mp3",
    },
    "spurgeon_all_of_grace": {
        "splitter": split_by_chapter,
        "out_dir": OUTPUT_BASE / "spurgeon_all_of_grace",
        "filename_pattern": "allofgrace_{i:02d}.mp3",
    },
    "edwards_select_sermons": {
        "splitter": split_by_chapter,
        "out_dir": OUTPUT_BASE / "edwards_select_sermons",
        "filename_pattern": "edwards_sermon_{i:02d}.mp3",
    },
    "edwards_religious_affections": {
        "splitter": split_by_chapter,
        "out_dir": OUTPUT_BASE / "edwards_religious_affections",
        "filename_pattern": "affections_{i:02d}.mp3",
    },
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=list(CONFIG_BY_SOURCE.keys()), help="Which work to render")
    p.add_argument("--limit", type=int, default=0, help="Cap rendered chunks (0=no cap)")
    p.add_argument("--apply", action="store_true", help="Actually render")
    p.add_argument("--dry-run", action="store_true", help="Report only")
    p.add_argument("--probe", action="store_true", help="Show Piper install status and exit")
    p.add_argument("--voice", default=DEFAULT_VOICE)
    args = p.parse_args()

    if args.probe:
        s = probe_piper()
        print(json.dumps(s, indent=2))
        if not s["piper_installed"]:
            print()
            print("Piper not installed. Install steps:")
            print("  1. Download: https://github.com/rhasspy/piper/releases/latest")
            print(f"     Extract to: {PIPER_DIR}")
            print(f"  2. Download voice: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium")
            print(f"     Save .onnx + .onnx.json to: {PIPER_VOICES}")
        return

    if not args.source:
        p.print_help()
        return
    if not (args.apply or args.dry_run):
        args.dry_run = True

    s = probe_piper()
    if not s["default_voice_ready"]:
        print("Piper voice not ready. Run with --probe for setup instructions.")
        return

    cfg = CONFIG_BY_SOURCE[args.source]
    print(f"fetching source for {args.source}...")
    try:
        text = fetch_source_text(args.source)
    except Exception as e:
        print(f"fetch failed: {e}")
        return
    print(f"  source length: {len(text)} chars")
    chunks = cfg["splitter"](text)
    print(f"  chunks: {len(chunks)}")

    if args.limit:
        chunks = chunks[: args.limit]
        print(f"  (capped to {args.limit})")

    out_dir = cfg["out_dir"]
    if args.dry_run:
        print()
        for i, (label, body) in enumerate(chunks[:5]):
            print(f"  [{i+1}/{len(chunks)}] {label}  ({len(body)} chars)")
        print()
        print("DRY-RUN — re-run with --apply to render.")
        return

    print(f"  rendering to {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    fail = 0
    t0 = time.time()
    for i, (label, body) in enumerate(chunks):
        mp3 = out_dir / cfg["filename_pattern"].format(i=i + 1)
        if mp3.exists() and mp3.stat().st_size > 1000:
            print(f"  [{i+1}/{len(chunks)}] EXISTS  {mp3.name}")
            ok += 1
            continue
        wav = mp3.with_suffix(".wav")
        # Limit each render to ~2000 chars to keep render time manageable
        body_capped = body[:8000]
        if not render_chunk_to_wav(body_capped, wav, args.voice):
            fail += 1
            print(f"  [{i+1}/{len(chunks)}] FAIL    {mp3.name}")
            continue
        if not wav_to_mp3(wav, mp3):
            fail += 1
            print(f"  [{i+1}/{len(chunks)}] FAIL    {mp3.name} (mp3 mux)")
            continue
        ok += 1
        print(f"  [{i+1}/{len(chunks)}] OK      {mp3.name}  ({mp3.stat().st_size // 1024} KB, t+{time.time()-t0:.0f}s)",
              flush=True)

    print()
    print(f"done: {ok} ok / {fail} fail in {time.time()-t0:.0f}s")
    print()
    print("Next: python tools/duration_cache.py --warm   # registers new files")


if __name__ == "__main__":
    main()
