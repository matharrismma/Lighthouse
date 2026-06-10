"""Radio — a broadcast lens for the keeping.

Scheduled programs. Voiced by ElevenLabs from text scripts. Anyone can
tune in to "now playing" or browse the archive. Episodes are pre-generated
MP3 files cached on disk, so replay costs zero ElevenLabs credits.

Why radio: it's an old form people remember. AM talk, BBC World Service,
Garrison Keillor's monologues, Paul Harvey's "rest of the story." The
twist is the voice — one operator writes scripts, the engine speaks them
in the operator's own cloned voice. The form scales without the operator
having to be in a studio at airtime.

Data shape:
  Shows (declared in SHOWS, below) — recurring programs.
  Episodes — one per air date per show. Stored as JSON sidecars at
    data/radio/<show_slug>/<YYYY-MM-DD>.json, with optional .mp3 sibling
    once the operator has run produce_audio().

Scheduling is informational, not enforced — the engine doesn't gate
playback by time. Visitors can replay anytime. The "now playing"
indicator is computed from the most recently aired episode + duration.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_RADIO_DIR = _REPO / "data" / "radio"
_lock = Lock()

# Pre-declared shows. The radio station has a deliberate small lineup.
# Add a show here to bring it into the schedule.
SHOWS: List[Dict[str, Any]] = [
    {
        "slug": "morning-devotion",
        "name": "Morning Devotion",
        "host": "M.R. Harris",
        "blurb": "Five minutes of Scripture set up for the day. Read aloud, slow.",
        "schedule": "Weekdays · 07:00 ET",
        "duration_min": 5,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "devotion",
    },
    {
        "slug": "almanac-of-the-week",
        "name": "Almanac of the Week",
        "host": "M.R. Harris",
        "blurb": "One verified claim. One that didn't survive. The reasoning between.",
        "schedule": "Saturdays · 09:00 ET",
        "duration_min": 12,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "almanac",
    },
    {
        "slug": "the-walk",
        "name": "The Walk",
        "host": "M.R. Harris",
        "blurb": "One situation. The four gates. What the Shepherd surfaces.",
        "schedule": "Sundays · 18:00 ET",
        "duration_min": 18,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "walk",
    },
    {
        "slug": "front-room-news",
        "name": "Front Room News",
        "host": "M.R. Harris",
        "blurb": "News through a long lens. Argue gently; nobody's enemy is in the room.",
        "schedule": "Weeknights · 19:30 ET",
        "duration_min": 15,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "news",
    },
    {
        "slug": "bible-study-live",
        "name": "Bible Study Live",
        "host": "M.R. Harris",
        "blurb": "One passage. Working through it in slow time, with the keeping's substrate.",
        "schedule": "Wednesdays · 19:00 ET",
        "duration_min": 25,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "bible",
    },
    {
        "slug": "parable-hour",
        "name": "The Parable Hour",
        "host": "M.R. Harris",
        "blurb": "A short story for what you carry. One parable, read slowly. No commentary.",
        "schedule": "Fridays · 21:00 ET",
        "duration_min": 8,
        "voice_id": "K3PzrzIx7M1m0k1Y7CQn",
        "category": "parable",
    },
]

SHOW_SLUGS = {s["slug"] for s in SHOWS}
EP_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_SCRIPT_LEN = 12000  # ~10 min of audio

# Show → Hearth room mapping. When an episode is voiced, a discussion
# post lands in this room so listeners can talk about it. Conversation
# accretes around the broadcast.
SHOW_HEARTH_ROOM = {
    "morning-devotion":    "front",
    "the-walk":            "prayer",   # walks are tender — Prayer Room
    "parable-hour":        "bible",    # parables open scripture
    "almanac-of-the-week": "health",   # almanac entries are largely health/practical
    "front-room-news":     "today",
    "bible-study-live":    "bible",
}

# Visitor_id under which the radio bot posts to the Hearth.
# Fixed hex so the operator can recognize "radio" posts.
RADIO_BOT_VISITOR_ID = "00add100fade"  # all hex chars; opaque, stable
RADIO_BOT_HANDLE = "the_radio"


def _show_dir(slug: str) -> Path:
    """data/radio/<show_slug>/ — created on demand."""
    d = _RADIO_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ep_paths(slug: str, ep_date: str) -> tuple:
    """(json_path, mp3_path) for an episode."""
    d = _show_dir(slug)
    return d / f"{ep_date}.json", d / f"{ep_date}.mp3"


def get_show(slug: str) -> Optional[Dict[str, Any]]:
    for s in SHOWS:
        if s["slug"] == slug:
            return s
    return None


def list_shows_with_stats() -> List[Dict[str, Any]]:
    """Shows + count of episodes + last-aired."""
    out = []
    for s in SHOWS:
        d = _show_dir(s["slug"])
        eps = sorted(d.glob("*.json"))
        last_aired = None
        if eps:
            try:
                rec = json.loads(eps[-1].read_text(encoding="utf-8"))
                last_aired = rec.get("aired_at_iso") or rec.get("ep_date")
            except (OSError, json.JSONDecodeError):
                pass
        # Has audio for at least the latest episode?
        has_audio = False
        for ep_path in eps:
            mp3 = ep_path.with_suffix(".mp3")
            if mp3.exists() and mp3.stat().st_size > 0:
                has_audio = True
                break
        out.append({
            **s,
            "episode_count": len(eps),
            "last_aired_iso": last_aired,
            "has_audio": has_audio,
        })
    return out


def list_episodes(slug: str, limit: int = 60) -> List[Dict[str, Any]]:
    """All episodes of a show, newest first (by ep_date)."""
    if slug not in SHOW_SLUGS:
        return []
    d = _show_dir(slug)
    eps = sorted(d.glob("*.json"), reverse=True)[:limit]
    out = []
    for p in eps:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        mp3 = p.with_suffix(".mp3")
        rec["has_audio"] = mp3.exists() and mp3.stat().st_size > 0
        if rec["has_audio"]:
            rec["audio_url"] = f"/radio/audio/{slug}/{rec.get('ep_date', '')}"
            rec["audio_bytes"] = mp3.stat().st_size
        out.append(rec)
    return out


def get_episode(slug: str, ep_date: str) -> Optional[Dict[str, Any]]:
    if slug not in SHOW_SLUGS or not EP_DATE_RE.match(ep_date or ""):
        return None
    json_path, mp3_path = _ep_paths(slug, ep_date)
    if not json_path.exists():
        return None
    try:
        rec = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rec["has_audio"] = mp3_path.exists() and mp3_path.stat().st_size > 0
    if rec["has_audio"]:
        rec["audio_url"] = f"/radio/audio/{slug}/{ep_date}"
        rec["audio_bytes"] = mp3_path.stat().st_size
    return rec


def write_episode(slug: str, ep_date: str, title: str, script: str,
                  notes: str = "", aired_at_iso: str = "") -> Dict[str, Any]:
    """Operator drops in a new episode. Audio is produced separately."""
    if slug not in SHOW_SLUGS:
        raise ValueError(f"unknown show: {slug!r}")
    if not EP_DATE_RE.match(ep_date or ""):
        raise ValueError("ep_date must be YYYY-MM-DD")
    script = (script or "").strip()
    if not script:
        raise ValueError("script required")
    if len(script) > MAX_SCRIPT_LEN:
        script = script[:MAX_SCRIPT_LEN]
    if not aired_at_iso:
        # default to ep_date at noon UTC
        aired_at_iso = f"{ep_date}T12:00:00Z"
    rec = {
        "show":         slug,
        "ep_date":      ep_date,
        "title":        (title or "").strip()[:200],
        "script":       script,
        "notes":        (notes or "").strip()[:1000],
        "aired_at_iso": aired_at_iso,
        "written_at_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    json_path, _ = _ep_paths(slug, ep_date)
    with _lock:
        json_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def now_playing() -> Optional[Dict[str, Any]]:
    """Most recently aired episode across all shows.

    Computes from each show's most recent episode's aired_at_iso.
    Returns the one with the latest air time. None if no episodes anywhere.
    """
    candidates: List[tuple] = []
    for s in SHOWS:
        eps = list_episodes(s["slug"], limit=1)
        if not eps:
            continue
        ep = eps[0]
        try:
            aired = datetime.fromisoformat(
                (ep.get("aired_at_iso") or "").replace("Z", "+00:00")
            )
            candidates.append((aired, s, ep))
        except (ValueError, TypeError):
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    aired, show, ep = candidates[0]
    return {
        "show":   {k: v for k, v in show.items()},
        "episode": ep,
        "aired_at_iso": ep.get("aired_at_iso"),
        "now_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── Audio production via ElevenLabs ─────────────────────────────────

def produce_audio(slug: str, ep_date: str) -> Dict[str, Any]:
    """Generate the MP3 for an episode via ElevenLabs.

    Reads the script, calls ElevenLabs streaming TTS, writes
    data/radio/<slug>/<ep_date>.mp3. Idempotent — re-running overwrites
    the existing file. Operator-only (gated at the endpoint level by IP).

    Returns:
        {ok: True, bytes_written: N, mp3_path: str}

    Raises ValueError / RuntimeError on failure with a human message.
    """
    if slug not in SHOW_SLUGS:
        raise ValueError(f"unknown show: {slug!r}")
    show = get_show(slug)
    if not show:
        raise ValueError(f"unknown show: {slug!r}")
    json_path, mp3_path = _ep_paths(slug, ep_date)
    if not json_path.exists():
        raise ValueError(f"no episode for {slug} on {ep_date}")
    try:
        rec = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"could not read episode: {e}")

    script = (rec.get("script") or "").strip()
    if not script:
        raise ValueError("episode has no script")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    voice_id = show.get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice_id:
        raise RuntimeError("no voice_id for show or ELEVENLABS_VOICE_ID")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    payload = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.78,
            "style": 0.0,
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detail = str(e)
        raise RuntimeError(f"ElevenLabs error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs network error: {e}")

    if not audio_bytes:
        raise RuntimeError("ElevenLabs returned empty audio")

    mp3_path.write_bytes(audio_bytes)
    # Update episode JSON with produced_at + size
    rec["produced_at_iso"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec["audio_bytes"] = len(audio_bytes)
    json_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cross-pollinate: drop a discussion post in the matching Hearth room.
    # Idempotent — if already posted, skip (the radio bot doesn't double-post).
    hearth_posted = False
    try:
        room = SHOW_HEARTH_ROOM.get(slug, "front")
        post_body = _hearth_post_for_episode(show, rec, ep_date)
        if post_body:
            from api import hearth as _hearth_mod
            # Naive duplicate-check: scan recent messages for the episode marker
            marker = f"radio·{slug}·{ep_date}"
            existing = _hearth_mod.recent_messages(room, limit=200)
            already = any(marker in (m.get("body") or "") for m in existing)
            if not already:
                _hearth_mod.post_message(
                    room=room,
                    visitor_id=RADIO_BOT_VISITOR_ID,
                    handle=RADIO_BOT_HANDLE,
                    body=post_body,
                )
                hearth_posted = True
    except Exception:
        # Hearth posting is best-effort; never block radio production
        pass

    return {
        "ok": True,
        "bytes_written": len(audio_bytes),
        "mp3_path": str(mp3_path.relative_to(_REPO)),
        "hearth_posted": hearth_posted,
        "hearth_room": SHOW_HEARTH_ROOM.get(slug),
    }


def _hearth_post_for_episode(show: Dict[str, Any], ep: Dict[str, Any],
                              ep_date: str) -> str:
    """Build the discussion-thread body the radio bot drops in the Hearth.

    Format includes a stable marker the dedupe check looks for, plus a
    listener-friendly intro that invites conversation. The marker stays in
    the body so it survives the polling refresh + search.
    """
    show_name = show.get("name", "")
    title = ep.get("title") or "(untitled episode)"
    slug = show.get("slug", "")
    return (
        f"📻 New on the radio — {show_name}, episode \"{title}\".\n\n"
        f"Take a listen, then come back and talk about it. "
        f"What landed? What pushed back? What did the verse open?\n\n"
        f"→ https://narrowhighway.com/radio.html?show={slug}\n\n"
        f"[radio·{slug}·{ep_date}]"
    )


def episode_audio_bytes(slug: str, ep_date: str) -> Optional[bytes]:
    """Return raw MP3 bytes for an episode, or None if no audio yet."""
    if slug not in SHOW_SLUGS or not EP_DATE_RE.match(ep_date or ""):
        return None
    _, mp3_path = _ep_paths(slug, ep_date)
    if not mp3_path.exists():
        return None
    try:
        return mp3_path.read_bytes()
    except OSError:
        return None


# ── Seed initial programming so the radio isn't empty on first visit ──

INITIAL_EPISODES: List[Dict[str, Any]] = [
    {
        "show": "morning-devotion",
        "ep_date": "2026-05-15",
        "title": "Psalm 1 — The Two Ways",
        "script": (
            "Good morning. This is the Morning Devotion. "
            "I want to read you Psalm 1 today. Slowly. "
            "Blessed is the man that walketh not in the counsel of the ungodly, "
            "nor standeth in the way of sinners, nor sitteth in the seat of the scornful. "
            "But his delight is in the law of the Lord; and in his law doth he meditate day and night. "
            "And he shall be like a tree planted by the rivers of water, that bringeth forth his fruit in his season; "
            "his leaf also shall not wither; and whatsoever he doeth shall prosper. "
            "The ungodly are not so: but are like the chaff which the wind driveth away. "
            "Therefore the ungodly shall not stand in the judgment, nor sinners in the congregation of the righteous. "
            "For the Lord knoweth the way of the righteous: but the way of the ungodly shall perish. "
            "Two ways. Two outcomes. The choice is real. "
            "Carry that with you today. "
            "The keeping is the substrate. Carry what survives."
        ),
        "notes": "Psalm 1 read straight; KJV.",
    },
    {
        "show": "the-walk",
        "ep_date": "2026-05-11",
        "title": "When a Brother Has Sinned Against You",
        "script": (
            "This is The Walk. Tonight, one situation. Tell me what to do when a brother has sinned against you. "
            "Matthew 18, verse 15. Moreover if thy brother shall trespass against thee, go and tell him his fault between thee and him alone: "
            "if he shall hear thee, thou hast gained thy brother. "
            "But if he will not hear thee, then take with thee one or two more, that in the mouth of two or three witnesses every word may be established. "
            "And if he shall neglect to hear them, tell it unto the church: but if he neglect to hear the church, let him be as an heathen man and a publican. "
            "Four gates. RED — is this honest? Have I really been sinned against, or am I bruised? "
            "FLOOR — is this safe? Going alone is not safe for the proud or the cowardly; the gate is for honest grievance. "
            "BROTHERS — bring witnesses if private speech failed. Not to win — to establish the matter. "
            "GOD — wait. The scripture's pacing is mercy. Each step gives the offender room to turn. "
            "If the offender repents at any step, the matter is closed. The goal was never the verdict. The goal was the brother. "
            "Walk through it. Carry what survives."
        ),
        "notes": "Mt 18:15-17 with the four-gates overlay.",
    },
    {
        "show": "parable-hour",
        "ep_date": "2026-05-12",
        "title": "The Lake That Lived",
        "script": (
            "The Parable Hour. One story. No commentary. "
            "In the deep of winter the lake froze. The fish below thought all was lost. "
            "But the water near the bed grew warmer than the ice above, "
            "for the Maker had made water unlike all other things — densest just above freezing. "
            "The ice covered them like a roof, and they lived. "
            "What unseen mercy is holding back the death you fear?"
        ),
        "notes": "From the parable substrate. Slow read.",
    },
    {
        "show": "almanac-of-the-week",
        "ep_date": "2026-05-10",
        "title": "Two claims about ginger",
        "script": (
            "This is Almanac of the Week. One verified, one that didn't survive, and the reasoning between. "
            "First: ginger reduces nausea. Verdict — CONFIRMED. "
            "Multiple randomized trials show ginger root, in doses around one gram daily, "
            "reduces nausea in pregnancy, in chemotherapy patients, and in postoperative recovery. "
            "The active compounds are gingerols and shogaols, both with anti-emetic effects on the GI tract. "
            "This is one of the few folk remedies that survived the trials cleanly. "
            "Second: the five-second rule. Verdict — MISMATCH. "
            "The claim that food picked up within five seconds is safe to eat is not supported. "
            "Bacterial transfer happens in well under a second, and the amount transferred depends on the food's moisture and the floor's contamination, not the timing. "
            "Wet food picks up ten times more bacteria in one second than dry food picks up in thirty. "
            "The reasoning between: both claims appeal to common experience, but only one survives controlled measurement. "
            "The almanac records both. Carry what survives."
        ),
        "notes": "Pulls from two Almanac entries with verdicts CONFIRMED and MISMATCH.",
    },
]


def seed_initial_episodes() -> int:
    """Drop initial episodes into the radio if none exist yet.

    Idempotent — skips episodes that already have a JSON file.
    Called once on first server boot so the radio has something to play.
    """
    n = 0
    for ep in INITIAL_EPISODES:
        json_path, _ = _ep_paths(ep["show"], ep["ep_date"])
        if json_path.exists():
            continue
        try:
            write_episode(
                slug=ep["show"],
                ep_date=ep["ep_date"],
                title=ep["title"],
                script=ep["script"],
                notes=ep.get("notes", ""),
                aired_at_iso=f"{ep['ep_date']}T12:00:00Z",
            )
            n += 1
        except ValueError:
            pass
    return n
