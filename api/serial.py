"""Serial — generate continuing fiction/non-fiction in the operator's voice.

Architecture:
  data/serials/<slug>/
      world.json         — characters, places, lore, motifs (the canon)
      style.md           — voice guide (sentence rhythm, vocabulary, themes)
      index.jsonl        — ordered episode metadata (summaries for continuity)
      episodes/<NNN>.json — full script + extracted notes

Generation:
  1. Operator (or scheduled job) calls generate_episode(slug, optional_direction).
  2. Engine loads style.md + world.json + last K episode summaries.
  3. Composes a prompt + calls Claude Opus 4.5 with tool-use for structured output.
  4. Saves the draft + appends a summary to the index for next time.
  5. Operator reviews. Optionally edits via write_episode.
  6. Produces audio via existing radio.produce_audio() once an episode is
     copied into the radio system (or this module can voice directly).

Posture: The serial is the operator's voice. Claude is a quill, not the
author. Every draft passes through the operator before going live. The
world bible + style guide are the load-bearing inputs; the prompt
explicitly tells the model to stay inside that box.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_SERIALS_DIR = _REPO / "data" / "serials"
_lock = Lock()

SLUG_RE = re.compile(r"^[a-z0-9_\-]{2,64}$")
EP_NUM_RE = re.compile(r"^\d{1,5}$")
MAX_DIRECTION_LEN = 2000
MAX_SCRIPT_LEN = 12000

# How many prior-episode summaries to include in continuity context.
# More = better continuity but a bigger prompt. 5 is enough for most arcs.
CONTINUITY_WINDOW = 5


def _serial_dir(slug: str) -> Path:
    if not SLUG_RE.match(slug or ""):
        raise ValueError(f"invalid serial slug: {slug!r}")
    d = _SERIALS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "episodes").mkdir(parents=True, exist_ok=True)
    return d


def list_serials() -> List[Dict[str, Any]]:
    """All declared serials. Each row: slug, name, episode_count, latest."""
    if not _SERIALS_DIR.exists():
        return []
    out = []
    for d in sorted(_SERIALS_DIR.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name
        world_path = d / "world.json"
        name = slug
        blurb = ""
        if world_path.exists():
            try:
                w = json.loads(world_path.read_text(encoding="utf-8"))
                name = w.get("name", slug)
                blurb = w.get("blurb", "")
            except (OSError, json.JSONDecodeError):
                pass
        ep_dir = d / "episodes"
        # Only canonical NNN.json — skip sidecars like NNN.radio.json
        ep_files = sorted(ep_dir.glob("[0-9][0-9][0-9].json")) if ep_dir.exists() else []
        latest = None
        if ep_files:
            try:
                latest_rec = json.loads(ep_files[-1].read_text(encoding="utf-8"))
                latest = {
                    "ep_num": latest_rec.get("ep_num"),
                    "title":  latest_rec.get("title"),
                    "drafted_at_iso": latest_rec.get("drafted_at_iso"),
                }
            except (OSError, json.JSONDecodeError):
                pass
        out.append({
            "slug":          slug,
            "name":          name,
            "blurb":         blurb,
            "episode_count": len(ep_files),
            "latest":        latest,
        })
    return out


def get_world(slug: str) -> Optional[Dict[str, Any]]:
    """Load the world bible for a serial."""
    d = _serial_dir(slug)
    p = d / "world.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def set_world(slug: str, world: Dict[str, Any]) -> Dict[str, Any]:
    """Operator: write/replace the world bible."""
    d = _serial_dir(slug)
    p = d / "world.json"
    with _lock:
        p.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    return world


def get_style(slug: str) -> str:
    """Load the style guide (markdown)."""
    d = _serial_dir(slug)
    p = d / "style.md"
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def set_style(slug: str, style_md: str) -> None:
    """Operator: write/replace the style guide."""
    d = _serial_dir(slug)
    p = d / "style.md"
    with _lock:
        p.write_text(style_md, encoding="utf-8")


def _ep_path(slug: str, ep_num: int) -> Path:
    d = _serial_dir(slug)
    return d / "episodes" / f"{ep_num:03d}.json"


def get_episode(slug: str, ep_num: int) -> Optional[Dict[str, Any]]:
    p = _ep_path(slug, ep_num)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_episodes(slug: str, limit: int = 100) -> List[Dict[str, Any]]:
    """All episodes of a serial, oldest first (chronological listening order)."""
    d = _serial_dir(slug)
    ep_dir = d / "episodes"
    if not ep_dir.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in sorted(ep_dir.glob("[0-9][0-9][0-9].json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "ep_num":         rec.get("ep_num"),
                "title":          rec.get("title"),
                "summary":        rec.get("summary", "")[:300],
                "drafted_at_iso": rec.get("drafted_at_iso"),
                "produced":       rec.get("produced", False),
                "audio_url":      rec.get("audio_url"),
                "word_count":     rec.get("word_count", 0),
                "part_label":     rec.get("part_label"),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return out[:limit]


def _continuity_summaries(slug: str, window: int = CONTINUITY_WINDOW) -> List[Dict[str, Any]]:
    """Return the last `window` episode summaries for continuity context."""
    eps = list_episodes(slug, limit=1000)
    return [
        {"ep_num": e["ep_num"], "title": e["title"], "summary": e["summary"]}
        for e in eps[-window:]
    ]


def _next_ep_num(slug: str) -> int:
    eps = list_episodes(slug, limit=10000)
    return max((e["ep_num"] or 0) for e in eps) + 1 if eps else 1


def write_episode(slug: str, ep_num: int, title: str, script: str,
                  summary: str = "", continuity_note: str = "") -> Dict[str, Any]:
    """Operator drops in / edits an episode directly. Used for both
    pure-human episodes and edits to Claude-generated drafts."""
    p = _ep_path(slug, ep_num)
    existing: Dict[str, Any] = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

    script = (script or "").strip()[:MAX_SCRIPT_LEN]
    if not script:
        raise ValueError("script required")

    rec = {
        **existing,
        "serial":           slug,
        "ep_num":           ep_num,
        "title":            (title or "").strip()[:200],
        "script":           script,
        "summary":          (summary or "").strip()[:1000],
        "continuity_note":  (continuity_note or "").strip()[:1000],
        "drafted_at_iso":   existing.get("drafted_at_iso") or
                            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_edited_iso":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with _lock:
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


# ── Generation via Claude API ────────────────────────────────────────

def generate_episode(slug: str, direction: str = "",
                      target_minutes: int = 10) -> Dict[str, Any]:
    """Have Claude draft the next episode in the operator's voice.

    Args:
        slug: which serial
        direction: free-text guidance from operator ("Mara reaches the river",
                   "introduce a new character: Brother Cassian", etc.)
        target_minutes: rough length target. 10 min ≈ 1500 words.

    Returns the drafted episode record (already saved to disk).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    world = get_world(slug)
    if world is None:
        raise ValueError(f"serial {slug!r} has no world.json — define it first")
    style = get_style(slug)
    if not style:
        raise ValueError(f"serial {slug!r} has no style.md — define it first")

    next_num = _next_ep_num(slug)
    prior = _continuity_summaries(slug, CONTINUITY_WINDOW)
    target_words = max(300, min(2500, target_minutes * 150))

    prior_block = ""
    if prior:
        prior_block = "## Last episodes (for continuity)\n\n" + "\n".join(
            f"**Episode {p['ep_num']} — {p['title']}**\n{p['summary']}\n"
            for p in prior
        )
    else:
        prior_block = "## This is Episode 1 — opening the serial.\n"

    direction_block = (
        f"\n## Operator's direction for this episode\n{direction.strip()}\n"
        if direction.strip()
        else "\n## Operator's direction\n(none — use your judgment for the next beat)\n"
    )

    prompt = (
        f"You are drafting Episode {next_num} of an ongoing serial titled "
        f"\"{world.get('name', slug)}\". Write in the operator's voice "
        f"(see style guide below). Stay strictly inside the world bible. "
        f"Target ~{target_words} words (~{target_minutes} minutes spoken).\n\n"
        f"# Style guide\n\n{style}\n\n"
        f"# World bible (JSON canon)\n\n"
        f"```json\n{json.dumps(world, ensure_ascii=False, indent=2)}\n```\n\n"
        f"{prior_block}\n"
        f"{direction_block}\n"
        f"## Output requirements\n"
        f"Call the `submit_episode` tool with:\n"
        f"  - title: a short episode title (max 80 chars)\n"
        f"  - script: the full prose, read aloud as audio. ~{target_words} words. "
        f"No chapter headings inside. No '[narrator]' bracketing — just prose, "
        f"as if the operator is speaking it.\n"
        f"  - summary: 2-3 sentences capturing what happened, for continuity "
        f"on the NEXT episode.\n"
        f"  - continuity_note: any open threads, character whereabouts, "
        f"or pending consequences the next episode should pick up.\n"
        f"\n"
        f"Write naturally. Don't announce yourself. Don't say 'in this episode'. "
        f"Start in the middle of a scene if continuity requires."
    )

    body = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 8192,
        "tools": [{
            "name": "submit_episode",
            "description": "Submit the drafted episode.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title":           {"type": "string"},
                    "script":          {"type": "string"},
                    "summary":         {"type": "string"},
                    "continuity_note": {"type": "string"},
                },
                "required": ["title", "script", "summary"],
            },
        }],
        "tool_choice": {"type": "tool", "name": "submit_episode"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            r = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"Anthropic error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Anthropic network error: {e}")

    drafted: Optional[Dict[str, str]] = None
    for blk in r.get("content") or []:
        if blk.get("type") == "tool_use" and blk.get("name") == "submit_episode":
            drafted = blk.get("input") or None
            break
    if not drafted:
        raise RuntimeError("Claude did not return a structured episode")

    rec = write_episode(
        slug=slug,
        ep_num=next_num,
        title=drafted.get("title", f"Episode {next_num}"),
        script=drafted.get("script", ""),
        summary=drafted.get("summary", ""),
        continuity_note=drafted.get("continuity_note", ""),
    )
    rec["generated_by"] = "claude-opus-4-5"
    rec["operator_direction"] = direction
    rec["target_minutes"] = target_minutes
    # Persist the generation metadata too
    p = _ep_path(slug, next_num)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


# ── Audio production (reuses radio.py's ElevenLabs path) ────────────

def produce_audio_multi_voice(slug: str, ep_num: int) -> Dict[str, Any]:
    """Produce an episode using the serial's voice_cast (one voice per speaker).

    Reads the episode's `segments` list (already parsed from Fountain), maps
    each speaker to a voice via world.json.voice_cast, calls ElevenLabs once
    per segment, and stitches the resulting MP3 streams.

    Use this for screenplay-based serials (Dade) where multiple speakers
    need distinct voices. For single-narrator serials (Apokalypsis), use
    produce_audio() below.
    """
    from api import multi_voice
    rec = get_episode(slug, ep_num)
    if not rec:
        raise ValueError(f"episode {ep_num} of {slug!r} not found")
    world = get_world(slug)
    if not world:
        raise ValueError(f"serial {slug!r} has no world.json")

    voice_cast = world.get("voice_cast") or {}
    narrator = (voice_cast.get("_narrator") or {}).get("voice_id")
    if not narrator:
        narrator = os.environ.get("ELEVENLABS_VOICE_ID")
    if not narrator:
        raise RuntimeError("no narrator voice_id available (voice_cast._narrator or ELEVENLABS_VOICE_ID)")

    # Build speaker → voice_id map from voice_cast structure
    speaker_voices = {}
    for name, info in voice_cast.items():
        if name.startswith("_"):
            continue
        if isinstance(info, dict) and info.get("voice_id"):
            speaker_voices[name] = info["voice_id"]

    segments = rec.get("segments") or []
    if not segments:
        raise ValueError(f"episode {ep_num} has no segments (was it parsed from Fountain?)")

    from api import fountain
    plan = fountain.segments_to_audio_plan(
        segments=segments,
        voice_cast=speaker_voices,
        narrator_voice_id=narrator,
        include_scene_headings=True,
    )

    mp3_path = _ep_path(slug, ep_num).with_suffix(".mp3")
    result = multi_voice.produce(plan=plan, output_path=mp3_path)

    rec["produced"] = True
    rec["produced_at_iso"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec["audio_bytes"] = result["bytes_written"]
    rec["audio_url"] = f"/serial/{slug}/audio/{ep_num}"
    rec["voices_used"] = result.get("voices_used")
    p = _ep_path(slug, ep_num)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "bytes_written": result["bytes_written"],
        "audio_url":     rec["audio_url"],
        "voices_used":   result.get("voices_used"),
    }


def estimate_audio_cost(slug: str, ep_num: int,
                       price_per_1k_chars: float = 0.30) -> Dict[str, Any]:
    """Estimate how much ElevenLabs would cost to produce this episode."""
    from api import multi_voice, fountain
    rec = get_episode(slug, ep_num)
    if not rec:
        raise ValueError(f"episode {ep_num} of {slug!r} not found")
    world = get_world(slug)
    if not world:
        raise ValueError(f"serial {slug!r} has no world.json")
    voice_cast = world.get("voice_cast") or {}
    narrator = (voice_cast.get("_narrator") or {}).get("voice_id") or \
               os.environ.get("ELEVENLABS_VOICE_ID") or "_narrator_placeholder"
    speaker_voices = {
        name: info["voice_id"]
        for name, info in voice_cast.items()
        if not name.startswith("_") and isinstance(info, dict) and info.get("voice_id")
    }
    segments = rec.get("segments") or []
    plan = fountain.segments_to_audio_plan(
        segments=segments,
        voice_cast=speaker_voices,
        narrator_voice_id=narrator,
        include_scene_headings=True,
    )
    return multi_voice.estimate_cost(plan, price_per_1k_chars=price_per_1k_chars)


def produce_audio(slug: str, ep_num: int,
                  voice_id: Optional[str] = None) -> Dict[str, Any]:
    """Voice an episode via ElevenLabs. Writes data/serials/<slug>/episodes/<n>.mp3."""
    rec = get_episode(slug, ep_num)
    if not rec:
        raise ValueError(f"episode {ep_num} of {slug!r} not found")
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    vid = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if not vid:
        raise RuntimeError("no voice_id provided and ELEVENLABS_VOICE_ID not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream"
    payload = {
        "text": rec.get("script", ""),
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.78,
            "style": 0.1,
            "use_speaker_boost": True,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "xi-api-key": api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"ElevenLabs error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs network error: {e}")

    mp3_path = _ep_path(slug, ep_num).with_suffix(".mp3")
    mp3_path.write_bytes(audio_bytes)
    rec["produced"] = True
    rec["produced_at_iso"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec["audio_bytes"] = len(audio_bytes)
    rec["audio_url"] = f"/serial/{slug}/audio/{ep_num}"
    p = _ep_path(slug, ep_num)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "bytes_written": len(audio_bytes), "audio_url": rec["audio_url"]}


def episode_audio_bytes(slug: str, ep_num: int) -> Optional[bytes]:
    p = _ep_path(slug, ep_num).with_suffix(".mp3")
    if not p.exists():
        return None
    try:
        return p.read_bytes()
    except OSError:
        return None
