"""ElevenLabs TTS — audiobook scaffold.

Layout:
  data/audio/cache/<sha256>.mp3            ← per-chunk MP3, content-addressed
  data/audio/manifests/<work_id>.json      ← chapter list + chunk → cache mapping
  data/audio/sources/<work_id>/chunks/*.txt← chunked source text (script output)

The endpoint `GET /tts/audio/<sha>.mp3` serves cached files.
`GET /tts/manifest/<work_id>` returns the chapter manifest for the player.

Generation happens **offline** via `scripts/generate_audiobook.py`. The
runtime engine never holds the ElevenLabs API key in memory or in source
control — the key lives in env var ELEVENLABS_API_KEY, read only by the
generation script. The web endpoint just serves pre-generated MP3s.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_AUDIO_ROOT = _REPO / "data" / "audio"
_CACHE_DIR = _AUDIO_ROOT / "cache"
_MANIFEST_DIR = _AUDIO_ROOT / "manifests"

_WORK_ID_RE = re.compile(r"^[a-z0-9_\-]{1,80}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")


def _valid_work_id(s: str) -> bool:
    return bool(_WORK_ID_RE.match((s or "").strip().lower()))


def _valid_sha(s: str) -> bool:
    return bool(_SHA_RE.match((s or "").strip().lower()))


def chunk_hash(text: str) -> str:
    """Content-addressed hash for a chunk of text. Stable across runs.

    Includes a salt prefix for the TTS namespace so we don't collide with
    other content-addressed stores in the repo. Same text → same MP3.
    """
    h = hashlib.sha256()
    h.update(b"elevenlabs|v1|")
    h.update(text.strip().encode("utf-8"))
    return h.hexdigest()


def cache_path_for(sha: str) -> Optional[Path]:
    """Return the cached MP3 path for a hash, or None if absent or invalid."""
    if not _valid_sha(sha):
        return None
    p = _CACHE_DIR / f"{sha}.mp3"
    return p if p.exists() else None


def manifest_path_for(work_id: str) -> Optional[Path]:
    if not _valid_work_id(work_id):
        return None
    p = _MANIFEST_DIR / f"{work_id}.json"
    return p if p.exists() else None


def load_manifest(work_id: str) -> Optional[Dict[str, Any]]:
    p = manifest_path_for(work_id)
    if not p:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_works() -> List[Dict[str, Any]]:
    """List every work that has a manifest."""
    out: List[Dict[str, Any]] = []
    if not _MANIFEST_DIR.exists():
        return out
    for p in sorted(_MANIFEST_DIR.glob("*.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chapters = m.get("chapters") or []
        generated = sum(1 for c in chapters if c.get("sha") and (_CACHE_DIR / f"{c['sha']}.mp3").exists())
        out.append({
            "work_id": m.get("work_id") or p.stem,
            "title": m.get("title") or p.stem,
            "author": m.get("author") or "",
            "voice": m.get("voice") or "",
            "model_id": m.get("model_id") or "",
            "chapter_count": len(chapters),
            "generated_count": generated,
            "total_chars": m.get("total_chars") or 0,
        })
    return out
