"""Fountain screenplay parser → narrator/character segments for audio.

Fountain is a plain-text screenplay format. Key elements:
  • Title page (key: value lines at top, terminated by blank line)
  • Synopses = lines starting with "= "
  • Scene headings — INT./EXT. lines, or lines that look like them
  • Action — plain paragraphs
  • CHARACTER — line in ALL CAPS, blank line above, dialogue below
  • Dialogue — paragraph(s) under a character line
  • Parentheticals — (whispered) etc. — usually skipped or read as direction
  • Transitions — FADE IN:, CUT TO:, FADE OUT.
  • Boneyard /* ... */ — comments, ignored
  • Notes [[ ... ]] — production notes, ignored
  • Centered ">text<" — usually titles, treated as action

This parser emits a list of segments:
    {"kind": "narrator", "text": "..."}  ← scene heading + action + transitions
    {"kind": "dialogue", "speaker": "ELDER PAINE", "text": "..."}
    {"kind": "scene_break", "text": "..."}  ← optional, for pause cues

The audio producer reads segments and calls ElevenLabs per segment with
the speaker's voice (or narrator's voice for action/scene_break).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_TITLE_KEY_RE = re.compile(r"^[A-Z][a-zA-Z _-]*:\s")
_SCENE_HEADING_RE = re.compile(
    r"^(INT\.?|EXT\.?|EST\.?|INT/EXT\.?|I/E\.?)[\s\.\:]",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"^(FADE IN:|FADE OUT\.?|CUT TO:|DISSOLVE TO:|SMASH CUT TO:|MATCH CUT TO:|JUMP CUT TO:|FADE TO BLACK\.?)$",
    re.IGNORECASE,
)
_SYNOPSIS_RE = re.compile(r"^=\s")
_PARENTHETICAL_RE = re.compile(r"^\s*\(.+\)\s*$")
_CHARACTER_RE = re.compile(r"^([A-Z][A-Z0-9 .'\-]+?)(\s*\((CONT'D|V\.O\.|O\.S\.|O\.C\.|MORE)\))?\s*$")
# Allow CHARACTER lines to also be all-caps with a tilde character or two
_BONEYARD_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_NOTE_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
_FORCED_ACTION_RE = re.compile(r"^!")          # ! prefix forces action
_FORCED_SCENE_RE  = re.compile(r"^\.[A-Z]")    # . prefix forces scene heading
_FORCED_CHARACTER_RE = re.compile(r"^@")       # @ prefix forces character


def _strip_inline_emphasis(text: str) -> str:
    """Remove Fountain's *italic*, **bold**, ***bold-italic***, _underline_."""
    # Three-star bold-italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text


def parse(fountain_text: str) -> Dict[str, Any]:
    """Parse a Fountain document. Returns:
        {
          "title": str,
          "credit": str,
          "author": str,
          "synopses": [str],
          "segments": [ {kind, ...}, ...],
          "characters": [str],  # unique speakers (in order seen)
        }
    """
    # Strip boneyard + notes
    text = _BONEYARD_RE.sub("", fountain_text)
    text = _NOTE_RE.sub("", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    meta: Dict[str, str] = {}
    synopses: List[str] = []
    segments: List[Dict[str, Any]] = []
    characters: List[str] = []  # unique, ordered

    # ── 1. Title page ─────────────────────────────────────────────
    # Parses lines like "Title: ..." at the top until a blank line is seen.
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            break
        m = _TITLE_KEY_RE.match(line)
        if m:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip()
            i += 1
            # Continuation lines (indented) belong to previous key
            while i < len(lines) and lines[i].startswith(("    ", "\t")):
                meta[key.strip().lower()] += " " + lines[i].strip()
                i += 1
        else:
            # Not a title page after all; rewind
            i = 0
            break

    # ── 2. Body — scan paragraphs ─────────────────────────────────
    # Group consecutive non-blank lines into "paragraphs," then classify.
    paragraphs: List[List[str]] = []
    current: List[str] = []
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line)
        i += 1
    if current:
        paragraphs.append(current)

    last_was_character = False
    pending_speaker: Optional[str] = None
    pending_dialogue: List[str] = []

    def _flush_dialogue() -> None:
        nonlocal pending_speaker, pending_dialogue
        if pending_speaker and pending_dialogue:
            text_combined = " ".join(pending_dialogue).strip()
            text_combined = _strip_inline_emphasis(text_combined)
            if text_combined:
                # Normalize speaker (strip (CONT'D), (V.O.), etc.)
                base_speaker = re.sub(r"\s*\([^)]+\)\s*", "", pending_speaker).strip()
                segments.append({
                    "kind":    "dialogue",
                    "speaker": base_speaker,
                    "text":    text_combined,
                })
                if base_speaker not in characters:
                    characters.append(base_speaker)
        pending_speaker = None
        pending_dialogue = []

    for para in paragraphs:
        first_line = para[0]
        first_stripped = first_line.strip()

        # Synopsis lines (= text) — collect into synopsis list, skip in segments
        if _SYNOPSIS_RE.match(first_stripped):
            for ln in para:
                if _SYNOPSIS_RE.match(ln.strip()):
                    synopses.append(ln.strip()[2:].strip())
                else:
                    synopses.append(ln.strip())
            continue

        # Forced scene heading via . prefix
        if _FORCED_SCENE_RE.match(first_stripped):
            _flush_dialogue()
            scene = first_stripped[1:].strip()
            segments.append({"kind": "scene_heading", "text": scene})
            continue

        # Standard scene heading (INT./EXT.)
        if _SCENE_HEADING_RE.match(first_stripped) and len(para) == 1:
            _flush_dialogue()
            segments.append({"kind": "scene_heading", "text": first_stripped})
            continue

        # Transition (FADE IN:, CUT TO:, etc.)
        if _TRANSITION_RE.match(first_stripped) and len(para) == 1:
            _flush_dialogue()
            segments.append({"kind": "transition", "text": first_stripped})
            continue

        # Forced action via ! prefix
        if _FORCED_ACTION_RE.match(first_stripped):
            _flush_dialogue()
            txt = "\n".join(para).strip()
            txt = re.sub(r"^!", "", txt)
            segments.append({
                "kind": "action",
                "text": _strip_inline_emphasis(txt),
            })
            continue

        # Forced character via @ prefix
        if _FORCED_CHARACTER_RE.match(first_stripped):
            speaker_line = first_stripped[1:].strip()
            # Treat remainder as dialogue
            _flush_dialogue()
            pending_speaker = speaker_line
            pending_dialogue = []
            for ln in para[1:]:
                stripped = ln.strip()
                if _PARENTHETICAL_RE.match(stripped):
                    continue
                pending_dialogue.append(stripped)
            _flush_dialogue()
            continue

        # Detect character + dialogue paragraph:
        # First line is ALL CAPS (with optional (V.O.)/(CONT'D))
        # AND subsequent lines are dialogue (not all-caps).
        char_match = _CHARACTER_RE.match(first_stripped)
        if (char_match and len(para) >= 2
            and first_stripped == first_stripped.upper()
            and any(c.isalpha() for c in first_stripped)
            and not _SCENE_HEADING_RE.match(first_stripped)
            and not _TRANSITION_RE.match(first_stripped)):
            _flush_dialogue()
            pending_speaker = first_stripped
            pending_dialogue = []
            for ln in para[1:]:
                stripped = ln.strip()
                if _PARENTHETICAL_RE.match(stripped):
                    continue  # skip parentheticals from audio
                pending_dialogue.append(stripped)
            _flush_dialogue()
            continue

        # Default: action / description paragraph
        _flush_dialogue()
        txt = "\n".join(para).strip()
        # Drop lines that look like centered titles (> ... <)
        if txt.startswith(">") and txt.endswith("<"):
            continue
        segments.append({
            "kind": "action",
            "text": _strip_inline_emphasis(txt),
        })

    _flush_dialogue()

    return {
        "title":   meta.get("title", ""),
        "credit":  meta.get("credit", ""),
        "author":  meta.get("author", ""),
        "draft_date": meta.get("draft date", ""),
        "metadata": meta,
        "synopses": synopses,
        "segments": segments,
        "characters": characters,
        "stats": {
            "segments": len(segments),
            "dialogue_segments": sum(1 for s in segments if s["kind"] == "dialogue"),
            "action_segments":   sum(1 for s in segments if s["kind"] == "action"),
            "unique_speakers":   len(characters),
        },
    }


def segments_to_plain_script(segments: List[Dict[str, Any]]) -> str:
    """Render parsed segments as a single readable script (for /serial pages
    that show 'read along' text). Speaker names are uppercase before dialogue.
    """
    parts: List[str] = []
    for s in segments:
        k = s["kind"]
        if k == "scene_heading":
            parts.append("\n" + s["text"].upper() + "\n")
        elif k == "transition":
            parts.append("\n" + s["text"] + "\n")
        elif k == "action":
            parts.append(s["text"])
        elif k == "dialogue":
            parts.append(f"\n{s['speaker']}:\n  {s['text']}\n")
    return "\n".join(parts).strip()


def segments_to_audio_plan(segments: List[Dict[str, Any]],
                           voice_cast: Dict[str, str],
                           narrator_voice_id: str,
                           include_scene_headings: bool = True) -> List[Dict[str, Any]]:
    """Turn parsed segments into a flat list of {voice_id, text} tuples
    ready for the multi-voice producer. Each entry is one ElevenLabs call.

    voice_cast maps SPEAKER → voice_id. Unmapped speakers fall back to narrator.
    """
    plan: List[Dict[str, Any]] = []
    for s in segments:
        k = s["kind"]
        if k == "scene_heading":
            if not include_scene_headings:
                continue
            # Convert to listener-friendly: "Interior. Paine Kitchen. Continuous."
            head = s["text"]
            spoken = head.replace("INT.", "Interior.").replace("EXT.", "Exterior.").replace("EST.", "Establishing.")
            spoken = re.sub(r"\s+-\s+", ". ", spoken)
            plan.append({
                "voice_id": narrator_voice_id,
                "text":     spoken,
                "kind":     "scene_heading",
            })
        elif k == "transition":
            # Silent in audio drama — transitions are visual
            continue
        elif k == "action":
            plan.append({
                "voice_id": narrator_voice_id,
                "text":     s["text"],
                "kind":     "action",
            })
        elif k == "narrator":
            # Radio-adapted equivalent of action — narrator speaks
            plan.append({
                "voice_id": narrator_voice_id,
                "text":     s["text"],
                "kind":     "narrator",
            })
        elif k == "sfx":
            # Sound effect cue — handled by SFX pipeline, not TTS. Skip for v1.
            # The producer will see kind=sfx and dispatch to ElevenLabs Sound
            # Effects API once that pass is enabled.
            plan.append({
                "voice_id": None,         # signals "not TTS"
                "text":     s["text"],     # SFX description
                "kind":     "sfx",
                "skip":     True,          # v1: drop. v2: dispatch to /sound-generation
            })
        elif k == "dialogue":
            speaker = s["speaker"]
            vid = voice_cast.get(speaker) or voice_cast.get(speaker.upper()) or narrator_voice_id
            plan.append({
                "voice_id": vid,
                "text":     s["text"],
                "kind":     "dialogue",
                "speaker":  speaker,
            })
    return plan
