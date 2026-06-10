"""Multi-voice audio production via ElevenLabs.

Takes an "audio plan" (list of {voice_id, text} segments) and produces a
single MP3 by calling ElevenLabs once per segment and concatenating the
resulting MP3 byte streams.

MP3 concatenation works because MP3 is a frame-based format — raw byte
concatenation of independent MP3 streams plays back cleanly in virtually
every player, including web Audio elements. There may be tiny seam
artifacts (sub-millisecond) but no glitch is audible at normal listening.

For cleaner stitching with a small silent gap between speakers, we
optionally insert a short silent-MP3 frame as a beat. This emulates the
brief breath between lines in a real radio drama.

Cost discipline:
  • This is operator-only. Each call hits the ElevenLabs API.
  • Costs are roughly per-character. A 30-page episode (~5000 words ≈
    27,000 characters) costs whatever ElevenLabs's per-char rate × char
    count comes to. Budget-conscious operators should produce one episode,
    listen, decide.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


_ELEVENLABS_BASE = "https://api.elevenlabs.io/v1/text-to-speech"
_DEFAULT_MODEL = "eleven_multilingual_v2"

# ~250 ms of silence as a single-frame MP3, base64-encodable but we ship raw.
# Generated once: 1 frame of MPEG-1 Layer 3, 64 kbps mono, 24 kHz, 144 bytes of
# header + silence padding. Skipping for now — most players handle raw concat
# cleanly. If we hear glitches, swap to a real silence frame.
_SILENCE_BYTES = b""


def _post_elevenlabs(text: str, voice_id: str, api_key: str,
                     stability: float = 0.55,
                     similarity_boost: float = 0.78,
                     style: float = 0.1,
                     timeout: int = 180) -> bytes:
    """Single ElevenLabs call. Returns raw MP3 bytes."""
    url = f"{_ELEVENLABS_BASE}/{voice_id}/stream"
    payload = {
        "text": text,
        "model_id": _DEFAULT_MODEL,
        "voice_settings": {
            "stability":         stability,
            "similarity_boost":  similarity_boost,
            "style":             style,
            "use_speaker_boost": True,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "xi-api-key":   api_key,
            "accept":       "audio/mpeg",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"ElevenLabs error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs network error: {e}")


def produce(plan: List[Dict[str, Any]],
            output_path: Path,
            api_key: Optional[str] = None,
            on_progress=None,
            dry_run: bool = False) -> Dict[str, Any]:
    """Run the audio plan, producing one MP3 at `output_path`.

    Args:
        plan: list of {voice_id, text, kind?, speaker?}.
        output_path: where to write the final MP3.
        api_key: ELEVENLABS_API_KEY (auto-loaded from env if None).
        on_progress: optional callback(i, total, segment) for UI updates.
        dry_run: if True, do not call ElevenLabs. Returns plan stats only.

    Returns:
        {
          "ok": True,
          "segments_produced": N,
          "bytes_written": M,
          "estimated_chars": C,
          "voices_used": [...],
        }
    """
    if dry_run:
        total_chars = sum(len(seg.get("text", "")) for seg in plan)
        voices_used = sorted(set(seg.get("voice_id") for seg in plan if seg.get("voice_id")))
        return {
            "ok": True,
            "dry_run": True,
            "segments_in_plan": len(plan),
            "estimated_chars": total_chars,
            "voices_used":     voices_used,
        }

    if api_key is None:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    if not plan:
        raise ValueError("plan is empty")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parts: List[bytes] = []
    total = len(plan)
    voices_used = set()

    # ElevenLabs has a hard cap per request (~5000 chars). We chunk long
    # segments to stay under this limit and keep concatenation seamless.
    MAX_CHARS = 4500

    def _chunk(text: str) -> List[str]:
        if len(text) <= MAX_CHARS:
            return [text]
        # Try to split at sentence boundaries
        chunks: List[str] = []
        buf = ""
        for sentence in _split_sentences(text):
            if len(buf) + len(sentence) > MAX_CHARS and buf:
                chunks.append(buf.strip())
                buf = sentence
            else:
                buf = (buf + " " + sentence).strip() if buf else sentence
        if buf:
            chunks.append(buf.strip())
        return chunks

    for i, segment in enumerate(plan, start=1):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        voice_id = segment.get("voice_id")
        if not voice_id:
            continue
        voices_used.add(voice_id)
        for sub in _chunk(text):
            try:
                mp3 = _post_elevenlabs(sub, voice_id, api_key)
                parts.append(mp3)
                if _SILENCE_BYTES:
                    parts.append(_SILENCE_BYTES)
            except Exception as e:
                if on_progress:
                    on_progress(i, total, segment, error=str(e))
                raise
        if on_progress:
            on_progress(i, total, segment, error=None)

    combined = b"".join(parts)
    output_path.write_bytes(combined)
    return {
        "ok": True,
        "segments_produced": len(parts),
        "bytes_written":     len(combined),
        "voices_used":       sorted(voices_used),
    }


_SENT_END = (".", "!", "?", ":", ";")


def _split_sentences(text: str) -> List[str]:
    """Crude sentence splitter — good enough for chunking long action paragraphs."""
    sentences: List[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in _SENT_END and len(buf) > 60:
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


def estimate_cost(plan: List[Dict[str, Any]],
                  price_per_1k_chars: float = 0.30) -> Dict[str, Any]:
    """Estimate ElevenLabs cost in USD given a per-1k-char price.

    Default price assumes ~$0.30 per 1k chars (mid-tier). Operators with
    different plans pass their own number.
    """
    total = sum(len(seg.get("text", "")) for seg in plan)
    return {
        "characters":       total,
        "estimated_usd":    round(total / 1000.0 * price_per_1k_chars, 2),
        "price_per_1k":     price_per_1k_chars,
    }
