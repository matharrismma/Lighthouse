"""Generate ElevenLabs MP3s for a novel and write a chapter manifest.

USAGE:
  set ELEVENLABS_API_KEY=...
  python scripts/generate_audiobook.py \
      --source "C:/path/to/novel.docx"  \
      --work-id participant_initiated_risk \
      --title "Participant-Initiated Risk" \
      --author "M.R. Harris" \
      --voice <voice_id>  \
      --model eleven_turbo_v2_5 \
      [--dry-run] [--chunks-only]

  --dry-run     : prepare chunks + manifest WITHOUT calling ElevenLabs.
                  No API key needed. Inspect data/audio/sources/<work_id>/
                  and the manifest before paying for generation.
  --chunks-only : write chunks to disk but do not call the API.

What it does:
  1. Read source (.docx or .pdf), normalize to plain text.
  2. Split into chunks at natural breakpoints (chapter headings →
     paragraph clusters → ~2000-char target, never mid-sentence).
  3. For each chunk: compute content hash; if cache miss, call API and
     write data/audio/cache/<sha>.mp3 (skipped in dry-run / chunks-only).
  4. Write data/audio/manifests/<work_id>.json with the chapter list and
     hash → mp3 mapping.

The runtime engine never sees the API key. It just serves the cached
MP3s and the manifest via /tts/audio/<sha>.mp3 and /tts/manifest/<id>.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterable

REPO = Path(__file__).parent.parent
AUDIO_ROOT = REPO / "data" / "audio"
CACHE_DIR = AUDIO_ROOT / "cache"
MANIFEST_DIR = AUDIO_ROOT / "manifests"
SOURCES_DIR = AUDIO_ROOT / "sources"

# Reasonable defaults. Chunks under 2500 chars usually produce clean audio
# and keep individual API calls fast enough to recover from failures.
TARGET_CHUNK_CHARS = 2200
MAX_CHUNK_CHARS = 2800

# Recognize "Chapter N" / "CHAPTER N" / "Prologue" / "Epilogue" / "Frame N"
CHAPTER_HEAD_RE = re.compile(
    r"^\s*(prologue|epilogue|chapter\s+\d+|chapter\s+[ivxlcdm]+|frame\s+\d+|part\s+\w+)\b",
    re.IGNORECASE,
)


def _import_chunk_hash():
    sys.path.insert(0, str(REPO))
    from api.tts import chunk_hash
    return chunk_hash


# ── Source reading ──────────────────────────────────────────────────────

def read_source_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document
        except ImportError as e:
            raise RuntimeError("install python-docx: pip install python-docx") from e
        d = Document(path)
        return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("install pypdf: pip install pypdf") from e
        r = PdfReader(str(path))
        pages = []
        for pg in r.pages:
            pages.append((pg.extract_text() or "").strip())
        return "\n\n".join(pages)
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError(f"unsupported source format: {path.suffix}")


# ── Chunking ────────────────────────────────────────────────────────────

def split_into_chapters(text: str) -> list[tuple[str, str]]:
    """Walk paragraphs. Whenever a Chapter/Part/Frame heading is detected,
    start a new chapter. Returns list of (chapter_title, body_text).
    Falls back to a single 'Whole work' chapter if no headings found.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chapters: list[tuple[str, list[str]]] = [("Opening", [])]
    for p in paragraphs:
        first_line = p.splitlines()[0].strip()
        if CHAPTER_HEAD_RE.match(first_line):
            # New chapter starts here
            chapters.append((first_line, []))
            # If the heading is on its own line and there's more text below,
            # keep the rest as body of this chapter
            rest = "\n".join(p.splitlines()[1:]).strip()
            if rest:
                chapters[-1][1].append(rest)
        else:
            chapters[-1][1].append(p)
    # Drop empty Opening if nothing landed there
    if chapters[0][1] == []:
        chapters.pop(0)
    out: list[tuple[str, str]] = []
    for title, body_parts in chapters:
        body = "\n\n".join(body_parts).strip()
        if body:
            out.append((title, body))
    if not out:
        out = [("Whole work", text.strip())]
    return out


def split_chapter_to_chunks(body: str, target: int = TARGET_CHUNK_CHARS, hard_cap: int = MAX_CHUNK_CHARS) -> list[str]:
    """Greedy paragraph-respecting chunker. Never splits mid-sentence."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in paragraphs:
        # If a single paragraph exceeds hard_cap, split on sentence boundary
        if len(p) > hard_cap:
            if cur:
                out.append("\n\n".join(cur))
                cur, cur_len = [], 0
            sentences = re.split(r"(?<=[.!?])\s+", p)
            buf: list[str] = []
            buf_len = 0
            for s in sentences:
                if buf_len + len(s) + 1 > target and buf:
                    out.append(" ".join(buf))
                    buf, buf_len = [], 0
                buf.append(s)
                buf_len += len(s) + 1
            if buf:
                out.append(" ".join(buf))
            continue
        if cur_len + len(p) + 2 > target and cur:
            out.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p) + 2
    if cur:
        out.append("\n\n".join(cur))
    return out


# ── ElevenLabs ──────────────────────────────────────────────────────────

def generate_mp3(api_key: str, voice_id: str, model_id: str, text: str, out_path: Path) -> None:
    """POST to ElevenLabs and write the MP3 to out_path. Raises on failure."""
    try:
        import requests
    except ImportError as e:
        raise RuntimeError("install requests: pip install requests") from e
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }
    r = requests.post(url, headers=headers, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(r.content)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="path to source .docx/.pdf/.txt")
    p.add_argument("--work-id", required=True, help="snake_case identifier, e.g. participant_initiated_risk")
    p.add_argument("--title", required=True)
    p.add_argument("--author", default="M.R. Harris")
    p.add_argument("--voice", default="", help="ElevenLabs voice_id")
    p.add_argument("--model", default="eleven_turbo_v2_5")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--chunks-only", action="store_true",
                   help="write chunks + manifest but don't call API")
    args = p.parse_args()

    src = Path(args.source).expanduser()
    if not src.exists():
        print(f"source not found: {src}", file=sys.stderr); sys.exit(1)

    chunk_hash = _import_chunk_hash()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    work_src_dir = SOURCES_DIR / args.work_id / "chunks"
    work_src_dir.mkdir(parents=True, exist_ok=True)

    print(f"reading source: {src}")
    text = read_source_text(src)
    print(f"  source chars: {len(text):,}")

    chapters = split_into_chapters(text)
    print(f"  chapters detected: {len(chapters)}")

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    will_call_api = not (args.dry_run or args.chunks_only)
    if will_call_api and not api_key:
        print("ELEVENLABS_API_KEY not set — running as dry-run (no API calls).", file=sys.stderr)
        will_call_api = False
    if will_call_api and not args.voice:
        print("--voice is required for API calls — running as dry-run.", file=sys.stderr)
        will_call_api = False

    manifest: dict = {
        "work_id": args.work_id,
        "title": args.title,
        "author": args.author,
        "voice": args.voice,
        "model_id": args.model,
        "total_chars": len(text),
        "chapter_count": 0,
        "chapters": [],
        "generated_at": int(time.time()),
        "source_file": src.name,
        "license_note": "Engine-side cache only. Source copyright belongs to the author.",
    }

    total_chunks = 0
    total_cached = 0
    total_calls = 0
    for ch_idx, (ch_title, ch_body) in enumerate(chapters, start=1):
        ch_chunks = split_chapter_to_chunks(ch_body)
        ch_record: dict = {
            "index": ch_idx,
            "title": ch_title,
            "char_count": len(ch_body),
            "chunks": [],
        }
        for ck_idx, chunk in enumerate(ch_chunks, start=1):
            sha = chunk_hash(chunk)
            chunk_path = work_src_dir / f"ch{ch_idx:03d}_chunk{ck_idx:03d}_{sha[:8]}.txt"
            chunk_path.write_text(chunk, encoding="utf-8")
            mp3_path = CACHE_DIR / f"{sha}.mp3"
            cached = mp3_path.exists()
            ch_record["chunks"].append({
                "index": ck_idx,
                "sha": sha,
                "chars": len(chunk),
                "url": f"/tts/audio/{sha}.mp3",
                "source_file": str(chunk_path.relative_to(REPO)),
                "cached": cached,
            })
            total_chunks += 1
            if cached:
                total_cached += 1
            elif will_call_api:
                print(f"  ch{ch_idx:03d} chunk{ck_idx:03d}: generating ({len(chunk)} chars)...")
                try:
                    generate_mp3(api_key, args.voice, args.model, chunk, mp3_path)
                    total_calls += 1
                    ch_record["chunks"][-1]["cached"] = True
                except Exception as exc:
                    print(f"    FAILED: {exc}", file=sys.stderr)
                    ch_record["chunks"][-1]["error"] = str(exc)[:200]
        manifest["chapters"].append(ch_record)
    manifest["chapter_count"] = len(manifest["chapters"])

    manifest_path = MANIFEST_DIR / f"{args.work_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote manifest: {manifest_path.relative_to(REPO)}")
    print(f"  total chunks: {total_chunks}")
    print(f"  cached before run: {total_cached}")
    print(f"  API calls this run: {total_calls}")
    if not will_call_api:
        print("  (no API calls — set ELEVENLABS_API_KEY + --voice to generate)")


if __name__ == "__main__":
    main()
