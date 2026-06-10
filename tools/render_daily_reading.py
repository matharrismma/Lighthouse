#!/usr/bin/env python3
"""render_daily_reading.py — produce today's psalm reading as audio + text.

Calendar-driven; same calculation as /assembly/today.html:
  psalm_of_the_day = ((day_of_year - 1) % 150) + 1

Pipeline (every organ replaceable; each does one thing):
  1. Compute today's psalm reference   (deterministic by date)
  2. Read the Scripture text           (data/bible_en/verses.jsonl)
  3. Render audio                       (Piper TTS — free, local, no API)
  4. Sign + manifest                    (SHA256 over canonical bytes)
  5. Publish                            (site/assembly/audio/today/)

Designed to be run nightly as a Windows Scheduled Task — produces a
fresh audio file per UTC date. The page at /assembly/listen.html plays
whatever is currently at site/assembly/audio/today/.

Piper is OPTIONAL. If it's not installed, the script still produces:
  - reading.txt        (the verses in plain text)
  - manifest.json      (references, hashes, "audio_status": "no_renderer")
The page reads the manifest and shows the text + an "audio coming soon"
state if no audio exists. Install Piper later, re-run, audio appears.

Why Piper, not ElevenLabs or another API:
  - Free; runs locally; no quota, no rate limit, no vendor lock
  - Deterministic given the same model + text (good for reproducibility)
  - Distributed: one of the architectural rules — no API dependency
    where a local tool will do (see /organic-design.html)

Install (when ready):
  https://github.com/rhasspy/piper · `pip install piper-tts`
  Or download a binary release; the script auto-detects either.

Usage:
  python tools/render_daily_reading.py                    # today's psalm
  python tools/render_daily_reading.py --date 2026-06-01   # specific date
  python tools/render_daily_reading.py --dry-run           # don't write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, date as date_cls
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
BIBLE_PATH = REPO_ROOT / "data" / "bible_en" / "verses.jsonl"
OUT_DIR = REPO_ROOT / "site" / "assembly" / "audio" / "today"
ARCHIVE_DIR = REPO_ROOT / "data" / "daily_readings"
LOG_DIR = REPO_ROOT / "logs"

# Piper-TTS configuration (set via env to override)
PIPER_VOICE = os.environ.get(
    "NH_PIPER_VOICE",
    "en_US-lessac-medium",  # popular default; install via `piper --model en_US-lessac-medium`
)
PIPER_BIN = os.environ.get("NH_PIPER_BIN", "")  # explicit path if not on PATH


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.daily_reading")
    logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "daily_reading.log",
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(sh)
    return logger


log = _setup_logging()


def day_of_year(d: date_cls) -> int:
    """1-indexed day of year."""
    start = date_cls(d.year, 1, 1)
    return (d - start).days + 1


def psalm_for_date(d: date_cls) -> int:
    """Same calculation as the JS in /assembly/today.html."""
    return ((day_of_year(d) - 1) % 150) + 1


def proverb_for_date(d: date_cls) -> int:
    """Same calculation as the JS in /assembly/today.html."""
    return ((d.day - 1) % 31) + 1


def read_chapter(book: str, chapter: int) -> list[dict]:
    """Read all verses of a book + chapter from the Bible JSONL."""
    if not BIBLE_PATH.exists():
        log.warning("bible source missing at %s", BIBLE_PATH)
        return []
    out: list[dict] = []
    book_lower = book.lower()
    with BIBLE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except Exception:
                continue
            if str(v.get("book", "")).lower() == book_lower and v.get("chapter") == chapter:
                out.append(v)
            elif out:
                # We've moved past the chapter — JSONL is sorted, can stop
                # (only safe if file is reliably sorted; defensive — break if true)
                break
    # If the file isn't perfectly sorted, do a full pass without the break
    if not out:
        with BIBLE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    v = json.loads(line)
                except Exception:
                    continue
                if str(v.get("book", "")).lower() == book_lower and v.get("chapter") == chapter:
                    out.append(v)
    # Sort by verse just in case
    out.sort(key=lambda v: int(v.get("verse") or 0))
    return out


def compose_reading_text(verses: list[dict], include_verse_numbers: bool = True) -> str:
    """Compose verses into a single text suitable for TTS reading."""
    if not verses:
        return ""
    lines = []
    for v in verses:
        text = (v.get("text") or "").strip()
        if not text:
            continue
        if include_verse_numbers:
            lines.append(f"Verse {v.get('verse')}. {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def find_piper() -> str | None:
    """Locate the Piper TTS binary or Python module. Returns:
      - 'binary:<path>' if a piper.exe / piper executable is on PATH
      - 'python' if `piper-tts` is importable as a Python module
      - None if not installed at all
    """
    if PIPER_BIN and Path(PIPER_BIN).exists():
        return f"binary:{PIPER_BIN}"
    located = shutil.which("piper") or shutil.which("piper.exe")
    if located:
        return f"binary:{located}"
    try:
        import piper  # noqa: F401
        return "python"
    except ImportError:
        return None


def render_audio_piper(text: str, out_wav: Path) -> bool:
    """Try to render text -> WAV via Piper. Return True on success."""
    piper = find_piper()
    if not piper:
        log.info("piper not installed; skipping audio render")
        return False
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        if piper.startswith("binary:"):
            bin_path = piper.split(":", 1)[1]
            # Piper CLI: stdin = text, --output_file = wav path, -m model
            cmd = [bin_path, "-m", PIPER_VOICE, "--output_file", str(out_wav)]
            log.info("invoking %s", " ".join(cmd))
            result = subprocess.run(
                cmd, input=text.encode("utf-8"),
                capture_output=True, timeout=600,
            )
            if result.returncode != 0:
                log.error("piper failed (rc=%s): %s",
                          result.returncode, result.stderr.decode("utf-8", "replace")[:500])
                return False
        else:
            # Python module path
            from piper import PiperVoice  # type: ignore
            voice = PiperVoice.load(PIPER_VOICE)
            with out_wav.open("wb") as f:
                voice.synthesize(text, f)
        log.info("rendered audio: %s (%d bytes)",
                 out_wav.name, out_wav.stat().st_size if out_wav.exists() else 0)
        return out_wav.exists() and out_wav.stat().st_size > 0
    except subprocess.TimeoutExpired:
        log.error("piper timed out after 600s")
        return False
    except Exception as e:
        log.exception("piper render failed: %s", e)
        return False


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Render today's daily reading")
    ap.add_argument("--date", default="", help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--include-proverb", action="store_true",
                    help="Also include today's proverb (longer reading)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write outputs")
    ap.add_argument("--archive", action="store_true",
                    help="Also write a dated copy under data/daily_readings/")
    args = ap.parse_args()

    if args.date:
        try:
            d = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            log.error("bad --date format (expected YYYY-MM-DD)")
            return 2
    else:
        d = datetime.now(timezone.utc).date()

    iso_date = d.isoformat()
    psalm_n = psalm_for_date(d)
    proverb_n = proverb_for_date(d) if args.include_proverb else None

    log.info("date=%s · psalm=%d · proverb=%s", iso_date, psalm_n,
             proverb_n if proverb_n else "(omitted)")

    # Read the verses
    psalm_verses = read_chapter("Psalms", psalm_n)
    proverb_verses = read_chapter("Proverbs", proverb_n) if proverb_n else []

    if not psalm_verses:
        log.error("no verses found for Psalms %d — Bible source missing or unreadable", psalm_n)
        return 3

    log.info("psalm %d: %d verses", psalm_n, len(psalm_verses))
    if proverb_verses:
        log.info("proverbs %d: %d verses", proverb_n, len(proverb_verses))

    # Compose reading text — short intro + psalm + (optional) proverb
    parts = []
    parts.append(
        f"The reading for {d.strftime('%A, %B %d, %Y')}. "
        f"From the book of Psalms, chapter {psalm_n}."
    )
    parts.append(compose_reading_text(psalm_verses))
    if proverb_verses:
        parts.append(
            f"And from the book of Proverbs, chapter {proverb_n}."
        )
        parts.append(compose_reading_text(proverb_verses))
    parts.append("Here ends the reading.")
    reading_text = "\n\n".join(parts)
    reading_bytes = reading_text.encode("utf-8")
    text_hash = hashlib.sha256(reading_bytes).hexdigest()

    if args.dry_run:
        log.info("DRY RUN: would write reading (%d chars, sha256:%s)",
                 len(reading_text), text_hash[:16])
        log.info("preview:\n%s\n... [truncated]", reading_text[:600])
        return 0

    # Write to site/assembly/audio/today/
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "reading.txt").write_bytes(reading_bytes)

    # Try to render audio
    audio_wav = OUT_DIR / "audio.wav"
    audio_status = "no_renderer"
    audio_sha = ""
    audio_bytes = 0
    if render_audio_piper(reading_text, audio_wav):
        audio_status = "rendered"
        audio_sha = sha256_of(audio_wav)
        audio_bytes = audio_wav.stat().st_size

    # Manifest
    manifest = {
        "schema": "narrowhighway.daily_reading/1",
        "date": iso_date,
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "references": {
            "psalm": f"Psalm {psalm_n}",
            "proverb": f"Proverbs {proverb_n}" if proverb_n else None,
        },
        "text": {
            "char_count": len(reading_text),
            "sha256": text_hash,
            "file": "reading.txt",
        },
        "audio": {
            "status": audio_status,    # rendered | no_renderer
            "file": "audio.wav" if audio_status == "rendered" else None,
            "sha256": audio_sha if audio_status == "rendered" else None,
            "size_bytes": audio_bytes if audio_status == "rendered" else None,
            "voice": PIPER_VOICE if audio_status == "rendered" else None,
        },
        "translation": "World English Bible (engwebp, Public Domain)",
        "source": "data/bible_en/verses.jsonl",
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Optionally archive a dated copy
    if args.archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        dest = ARCHIVE_DIR / iso_date
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT_DIR / "reading.txt", dest / "reading.txt")
        shutil.copy2(OUT_DIR / "manifest.json", dest / "manifest.json")
        if audio_status == "rendered":
            shutil.copy2(audio_wav, dest / "audio.wav")
        log.info("archived to %s", dest)

    log.info(
        "DONE · text=%d chars (sha256:%s) · audio=%s",
        len(reading_text), text_hash[:16], audio_status,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("interrupted by user")
        sys.exit(130)
