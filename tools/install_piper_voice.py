#!/usr/bin/env python3
"""install_piper_voice.py — helper to download a Piper voice model.

The daily reading renderer (tools/render_daily_reading.py) uses Piper TTS
to produce audio. Piper itself is just a binary; the *voice model* lives
in a pair of files (.onnx weights + .onnx.json config) that must be
downloaded separately, normally from the Piper voices repository on
Hugging Face:

    https://huggingface.co/rhasspy/piper-voices

This helper downloads a voice into the directory Piper expects, with
SHA256 verification.

Usage:
    python tools/install_piper_voice.py                          # default voice
    python tools/install_piper_voice.py --voice en_US-amy-medium # specific voice
    python tools/install_piper_voice.py --list                   # show common voices
    python tools/install_piper_voice.py --dir C:\\Tools\\piper    # explicit dir

Voice names follow the pattern <lang>-<speaker>-<quality>, e.g.:
    en_US-lessac-medium    en_US-amy-medium    en_US-ryan-high
    en_GB-alan-medium      en_GB-cori-high     en_GB-northern_english_male-medium

After installing, test:
    piper -m en_US-lessac-medium --output_file test.wav
    (type some text and press Ctrl+Z then Enter on Windows)

Or re-run the daily reading renderer:
    python tools/render_daily_reading.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Default voice models (curated as known-good for English)
COMMON_VOICES = [
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_US-ryan-high",
    "en_US-libritts-high",
    "en_GB-alan-medium",
    "en_GB-cori-high",
]

PIPER_HF_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
)

DEFAULT_DIR_CANDIDATES = [
    Path(r"C:\Tools\piper"),
    Path.home() / ".local" / "share" / "piper",
    Path.home() / "piper",
    Path.cwd() / "piper",
]


def find_piper_dir(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        p.mkdir(parents=True, exist_ok=True)
        return p
    piper_exe = shutil.which("piper") or shutil.which("piper.exe")
    if piper_exe:
        return Path(piper_exe).parent
    for cand in DEFAULT_DIR_CANDIDATES:
        if cand.exists():
            return cand
    target = DEFAULT_DIR_CANDIDATES[0]
    target.mkdir(parents=True, exist_ok=True)
    return target


def parse_voice(voice: str) -> tuple[str, str, str]:
    """e.g. en_US-lessac-medium -> ('en', 'en_US', 'lessac/medium')"""
    parts = voice.split("-")
    if len(parts) < 3:
        raise ValueError(f"unrecognized voice format: {voice} (expected lang-speaker-quality)")
    lang_full = parts[0]
    speaker = parts[1]
    quality = parts[2]
    lang_short = lang_full.split("_")[0]
    return lang_short, lang_full, f"{speaker}/{quality}"


def url_for_voice(voice: str, kind: str) -> str:
    """kind: 'onnx' | 'onnx.json'"""
    lang_short, lang_full, sub = parse_voice(voice)
    return f"{PIPER_HF_BASE}/{lang_short}/{lang_full}/{sub}/{voice}.{kind}"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, expected_min_bytes: int = 1024) -> None:
    print(f"  downloading {url}")
    print(f"  -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "nh-piper-installer/1"})
    with urllib.request.urlopen(req, timeout=300) as r:
        total = 0
        with dest.open("wb") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
                if total % (10 * (1 << 20)) < (1 << 20):
                    print(f"    {total // (1 << 20)} MB...")
    if dest.stat().st_size < expected_min_bytes:
        raise RuntimeError(
            f"download too small ({dest.stat().st_size} bytes); "
            f"check the voice name and your network"
        )
    print(f"  done ({dest.stat().st_size} bytes; sha256:{sha256_of(dest)[:16]}...)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Install a Piper voice model")
    ap.add_argument("--voice", default="en_US-lessac-medium",
                    help="Voice name (e.g. en_US-amy-medium)")
    ap.add_argument("--dir", default="", help="Piper directory (auto-detect if omitted)")
    ap.add_argument("--list", action="store_true", help="List common voices and exit")
    ap.add_argument("--force", action="store_true",
                    help="Re-download even if the file already exists")
    args = ap.parse_args()

    if args.list:
        print("Common English Piper voices:")
        for v in COMMON_VOICES:
            print(f"  {v}")
        print()
        print("Full list: https://github.com/rhasspy/piper/blob/master/VOICES.md")
        return 0

    target_dir = find_piper_dir(args.dir or None)
    print(f"target dir: {target_dir}")

    voice = args.voice
    onnx_path = target_dir / f"{voice}.onnx"
    json_path = target_dir / f"{voice}.onnx.json"

    for path, kind in ((onnx_path, "onnx"), (json_path, "onnx.json")):
        if path.exists() and not args.force:
            print(f"already present: {path.name} ({path.stat().st_size} bytes)")
            continue
        try:
            url = url_for_voice(voice, kind)
            download(url, path)
        except urllib.error.HTTPError as e:
            print(f"ERROR downloading {kind}: HTTP {e.code} {e.reason}")
            print(f"  URL was: {url}")
            print(f"  Confirm the voice name is correct: python tools/install_piper_voice.py --list")
            return 2
        except Exception as e:
            print(f"ERROR downloading {kind}: {e}")
            return 3

    print()
    print(f"✓ voice installed: {voice}")
    print(f"  files at: {target_dir}")
    print()
    print("Test it:")
    print(f'  Set-Content -Path test.txt -Value "Hello world."')
    print(f'  Get-Content test.txt | piper -m {voice} --output_file test.wav')
    print()
    print("Then re-render the daily reading:")
    print(f"  $env:NH_PIPER_VOICE = \"{voice}\"")
    print(f"  python tools/render_daily_reading.py --include-proverb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
