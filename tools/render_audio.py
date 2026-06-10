"""Piper TTS audio renderer — generate MP3s from text substrate.

Piper is a fast, local, neural TTS engine (https://github.com/rhasspy/piper).
Zero per-character cost. Replaces ElevenLabs for bulk work per the storage-
discipline rule.

Inputs:
  - hymns.json (already-written PD hymns)
  - data/library_inventory/acquired/*.json (any text-bearing substrate)
  - explicit --text-file <path> or --slug <slug>

Output:
  D:/library_files/<slug>/<part>.mp3   (mirrors video acquisition shape)
  data/library_inventory/acquired/<slug>.json  manifest gains audio_renders[]

Strict-PD rule: only render text we already verified PD. The strict-PD-only
gate (Gate 1) sits upstream.

Pre-req:
  1. Install Piper from https://github.com/rhasspy/piper/releases
     (Windows: download piper_windows_amd64.zip, extract somewhere on PATH)
  2. Download a voice model:
       piper --download-voice en_US-lessac-medium
     (other voices: en_GB-alan-medium, en_US-amy-medium, etc.)
  3. Verify: echo "Hello world" | piper -m en_US-lessac-medium -f hello.wav

Usage:
  python tools/render_audio.py --slug hymn:amazing-grace
  python tools/render_audio.py --all-hymns
  python tools/render_audio.py --voice en_US-lessac-medium --bulk codex
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HYMNS_JSON = REPO / "site" / "hymns.json"
STORAGE_ROOT = Path("D:/library_files")  # matches the downloader's storage tier 1
DEFAULT_VOICE = "en_US-lessac-medium"
DEFAULT_VOICE_ALT = "en_GB-alan-medium"  # for KJV / older texts

# Default install paths (override via env vars NH_PIPER_EXE, NH_PIPER_VOICE_DIR)
import os as _os
PIPER_EXE = _os.environ.get("NH_PIPER_EXE", r"C:\Tools\piper\piper.exe")
PIPER_VOICE_DIR = _os.environ.get("NH_PIPER_VOICE_DIR", r"C:\Tools\piper\voices")


def piper_available() -> bool:
    return Path(PIPER_EXE).exists() or shutil.which("piper") is not None


def piper_cmd() -> str:
    """Return the piper executable path (env override > known path > PATH lookup)."""
    if Path(PIPER_EXE).exists():
        return PIPER_EXE
    return shutil.which("piper") or "piper"


def voice_model_path(voice_name: str) -> str | None:
    p = Path(PIPER_VOICE_DIR) / f"{voice_name}.onnx"
    return str(p) if p.exists() else None


def ffmpeg_cmd() -> str | None:
    """Return ffmpeg path: imageio-ffmpeg first, then PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg")


def render_text_to_mp3(text: str, out_path: Path, voice: str = DEFAULT_VOICE) -> bool:
    """Pipe text into piper, output WAV, convert to MP3 via ffmpeg.

    Returns True on success. Skips with warning if piper or ffmpeg missing.
    """
    if not piper_available():
        print(f"[skip] Piper not found at {PIPER_EXE} or on PATH")
        return False
    ff = ffmpeg_cmd()
    if not ff:
        print(f"[skip] ffmpeg not available (pip install imageio-ffmpeg)")
        return False
    model = voice_model_path(voice)
    if not model:
        print(f"[skip] voice model {voice} not at {PIPER_VOICE_DIR}/{voice}.onnx")
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wav_tmp = out_path.with_suffix(".wav")
    try:
        # 1) Piper: text → WAV
        proc = subprocess.run(
            [piper_cmd(), "-m", model, "-f", str(wav_tmp)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=1800,
        )
        if proc.returncode != 0 or not wav_tmp.exists():
            print(f"[piper error] returncode={proc.returncode}")
            print(proc.stderr.decode("utf-8", errors="replace")[:400])
            return False
        # 2) ffmpeg: WAV → MP3
        proc = subprocess.run(
            [ff, "-y", "-i", str(wav_tmp), "-codec:a", "libmp3lame", "-qscale:a", "5", str(out_path)],
            capture_output=True,
            timeout=600,
        )
        wav_tmp.unlink(missing_ok=True)
        if proc.returncode != 0:
            print(f"[ffmpeg error] {proc.stderr.decode('utf-8', errors='replace')[-400:]}")
            return False
        return True
    except Exception as e:
        print(f"[render error] {e}")
        return False


def render_hymns(voice: str, slug_filter: str | None = None) -> int:
    if not HYMNS_JSON.exists():
        print(f"[err] {HYMNS_JSON} not found. Run tools/hymnary_scrape.py first.")
        return 1
    blob = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    # Write to site/audio/hymns/ so the podcast feed and players can serve them.
    out_dir_root = REPO / "site" / "audio" / "hymns"
    out_dir_root.mkdir(parents=True, exist_ok=True)
    n = 0
    for h in blob.get("hymns", []):
        slug = h.get("slug")
        if slug_filter and slug != slug_filter:
            continue
        text = h.get("text")
        if not text:
            continue
        out = out_dir_root / f"{slug}.mp3"
        if out.exists():
            print(f"[skip exists] {slug}")
            continue
        # Add a short narrator preamble so the file plays well as podcast episode
        narration = f"{h.get('title')}, by {h.get('author','Anonymous')}.\n\n{text}"
        print(f"[render] {slug} -> {out}")
        if render_text_to_mp3(narration, out, voice=voice):
            n += 1
    print(f"Done. {n} hymn(s) rendered. Output: {out_dir_root}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--all-hymns", action="store_true")
    ap.add_argument("--slug", help="Single hymn slug to render (matches hymns.json slug)")
    ap.add_argument("--text-file", help="Render an arbitrary text file")
    ap.add_argument("--out", help="Output path for --text-file")
    ap.add_argument("--check", action="store_true", help="Just check whether Piper + ffmpeg are installed")
    args = ap.parse_args()

    if args.check:
        piper = f"[OK] {piper_cmd()}" if piper_available() else "[--] NOT FOUND"
        ff = ffmpeg_cmd()
        ffmpeg = f"[OK] {ff}" if ff else "[--] NOT INSTALLED"
        vm = voice_model_path(args.voice)
        voice = f"[OK] {vm}" if vm else f"[--] NOT FOUND at {PIPER_VOICE_DIR}/{args.voice}.onnx"
        print(f"Piper:   {piper}")
        print(f"ffmpeg:  {ffmpeg}")
        print(f"Voice:   {voice}")
        return 0

    if args.all_hymns:
        return render_hymns(voice=args.voice)
    if args.slug:
        return render_hymns(voice=args.voice, slug_filter=args.slug)
    if args.text_file:
        if not args.out:
            print("--out is required with --text-file")
            return 2
        text = Path(args.text_file).read_text(encoding="utf-8")
        ok = render_text_to_mp3(text, Path(args.out), voice=args.voice)
        return 0 if ok else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
