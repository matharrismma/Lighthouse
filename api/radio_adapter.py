"""TV screenplay → radio drama adapter.

Dade was written as television. The fountain parser correctly separates
dialogue from action, but the action lines were written for a camera:
"The camera descends through the canopy" doesn't work for radio because
the listener's ear cannot see a camera.

This module takes a parsed fountain episode (kind=action, dialogue,
scene_heading, transition) and rewrites each scene for the ear:

  • DIALOGUE — kept verbatim. Never touched. The voices ARE the show.
  • SCENE_HEADING — kept (read by narrator with INT./EXT. expanded).
  • ACTION — rewritten as either:
      (a) aural narration — paint the same image by sound and feel.
          "The camera descends through the canopy" becomes
          "Morning on the mountain. Tulip poplar above, white oak, hickory.
          The wind in the canopy. The forest is old."
      (b) [SFX: ...] tags — for ambient beds or punctuating sounds
          like a slamming door or a creek over stone. The producer
          generates these via ElevenLabs Sound Effects.
      (c) DROPPED — when blocking exists only for the camera and the
          dialogue carries the scene, the action is cut.
  • TRANSITION — dropped (fade-in/cut-to are visual).

Each scene is sent to Claude as one unit with tight instructions and the
show's voice register. The TV master fountain stays untouched on disk;
the radio version is written to a parallel file. Operator approves
before any audio production runs against it.

Cost: ~$0.30-0.50 per Dade episode in Claude tokens (Sonnet 4.5 / Opus
4.5 depending on which is available).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import anthropic
except Exception:
    anthropic = None  # type: ignore


_MODEL_PREFERENCE = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-3-5-sonnet-latest",
]


_ADAPTER_SYSTEM = """\
You are adapting a television screenplay scene for radio drama production. The
show's voice is M.R. Harris — first-person mountain plainness, long sentences
that earn their place, theological grain that is structural not preachy.

INVIOLABLE RULES:
  1. DIALOGUE IS NEVER TOUCHED. Every line of dialogue passes through verbatim.
     You do not paraphrase, condense, or "improve" it. The voices ARE the show.
  2. SCENE HEADINGS are kept (the narrator reads them with INT./EXT. expanded
     to "Interior." / "Exterior." — this is handled downstream; you keep the
     scene heading text as-is).
  3. Action that is purely visual stage direction (camera moves, lighting,
     blocking that doesn't make a sound the listener could hear) must become
     ONE of:
       (a) AURAL_NARRATION — the narrator paints the same image by SOUND and
           FEEL, in M.R. Harris's voice. Short. Two or three sentences max
           per beat. The listener's ear builds the picture.
       (b) SFX — for ambient beds or punctuating sounds (a slamming door,
           a creek over stone, a fiddle far off, the wind in a canopy, a
           rooster at the wrong hour). Use the form [SFX: terse description].
           The producer generates these audibly via ElevenLabs Sound Effects.
           Combine multiple atmospheric layers in one [SFX:] when they share
           a beat.
       (c) DROPPED — if blocking exists only for the camera and the
           dialogue carries the scene, cut the action entirely. Tight is
           better than padded.

  4. Action that ALREADY describes a sound (a man chopping wood, water on
     gravel, a chair scraping) can become EITHER narration OR SFX. Use
     narration when it carries meaning the listener should hear in words;
     use SFX when it's atmosphere.

  5. Preserve the order of beats within a scene.

  6. Voice register for narration: plain, specific, masculine quiet of an
     old mountain man who has watched this place for sixty years.
     Theological grain is structural, not preachy. No flowery prose.

OUTPUT FORMAT — return a JSON object with this shape:

{
  "adapted_segments": [
    {"kind": "scene_heading", "text": "EXT. SAND MOUNTAIN - DAWN"},
    {"kind": "narrator", "text": "Morning on the mountain. The wind in the canopy."},
    {"kind": "sfx", "text": "wind moving through tulip poplar and white oak, distant creek over sandstone"},
    {"kind": "dialogue", "speaker": "ELDER PAINE", "text": "The boy is late."},
    ...
  ]
}

The "kind" field MUST be one of: scene_heading, narrator, sfx, dialogue.
"narrator" replaces "action" — the narrator speaks the adapted line.
"sfx" carries the bracketed sound cue (text WITHOUT the [SFX:] wrapper —
just the description). "dialogue" passes through verbatim with speaker.

Return ONLY the JSON object. No prose around it.
"""


def _client() -> Any:
    if anthropic is None:
        raise RuntimeError("anthropic SDK not installed")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=key)


def _pick_model(client: Any) -> str:
    # We don't probe; we try the preferred model and fall through on failure.
    return _MODEL_PREFERENCE[0]


def _segments_to_scenes(segments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group a flat segment list into scenes. Scene = scene_heading + everything
    after it until the next scene_heading (or EOF).
    """
    scenes: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for seg in segments:
        if seg.get("kind") == "scene_heading":
            if current:
                scenes.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        scenes.append(current)
    return scenes


def _scene_to_prompt_text(scene: List[Dict[str, Any]]) -> str:
    """Render a scene as plain text for Claude to read. Keeps speaker labels
    visible so the model can preserve dialogue exactly.
    """
    out = []
    for seg in scene:
        k = seg.get("kind")
        t = (seg.get("text") or "").strip()
        if k == "scene_heading":
            out.append(f"[SCENE HEADING] {t}")
        elif k == "transition":
            out.append(f"[TRANSITION] {t}")
        elif k == "action":
            out.append(f"[ACTION] {t}")
        elif k == "dialogue":
            sp = seg.get("speaker") or ""
            out.append(f"[DIALOGUE / {sp}] {t}")
        else:
            out.append(f"[{k}] {t}")
    return "\n\n".join(out)


def _adapt_scene(client: Any, model: str, scene_text: str,
                 attempt: int = 0) -> List[Dict[str, Any]]:
    """Send one scene to Claude and parse the returned JSON."""
    user_msg = (
        "Adapt this television scene for radio drama. Return ONLY the JSON object "
        "described in the system prompt — no markdown, no commentary, no code "
        "fences. Begin your response with `{` and end with `}`.\n\n"
        "Scene to adapt:\n\n" + scene_text
    )
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=_ADAPTER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            raw += block.text

    # Strip any accidental code fences or prose
    raw = raw.strip()
    if raw.startswith("```"):
        # remove leading fence (```json or ```)
        raw = re.sub(r"^```[a-zA-Z]*\s*\n", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3].rstrip()
    # Find the first `{` and the last `}` to be safe
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        if attempt < 1:
            time.sleep(2)
            return _adapt_scene(client, model, scene_text, attempt + 1)
        raise RuntimeError(f"adapter returned no JSON object. raw: {raw[:300]}")
    payload = raw[start:end + 1]
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as e:
        if attempt < 1:
            time.sleep(2)
            return _adapt_scene(client, model, scene_text, attempt + 1)
        raise RuntimeError(f"adapter JSON parse failed: {e}. payload: {payload[:300]}")

    segs = obj.get("adapted_segments") or []
    if not isinstance(segs, list):
        raise RuntimeError(f"adapter returned non-list adapted_segments: {type(segs)}")

    # Light validation
    out: List[Dict[str, Any]] = []
    for s in segs:
        if not isinstance(s, dict): continue
        k = s.get("kind")
        if k not in {"scene_heading", "narrator", "sfx", "dialogue"}:
            continue
        t = (s.get("text") or "").strip()
        if not t: continue
        rec = {"kind": k, "text": t}
        if k == "dialogue":
            rec["speaker"] = (s.get("speaker") or "").strip()
            if not rec["speaker"]:
                continue
        out.append(rec)
    return out


def adapt_episode(segments: List[Dict[str, Any]],
                  on_progress=None,
                  model: Optional[str] = None) -> Dict[str, Any]:
    """Adapt one episode (parsed TV segments) to a radio-drama segment list.

    Returns:
      {
        "adapted_segments": [...],
        "scene_count":      N,
        "model":            "claude-...",
        "stats": {
          "tv_segments":    M,
          "radio_segments": K,
          "tv_action":      ...,
          "radio_narrator": ...,
          "radio_sfx":      ...,
          "dialogue":       ... (should be identical across both),
        }
      }
    """
    client = _client()
    use_model = model or _pick_model(client)

    scenes = _segments_to_scenes(segments)
    adapted: List[Dict[str, Any]] = []

    for i, scene in enumerate(scenes, start=1):
        scene_text = _scene_to_prompt_text(scene)
        result = _adapt_scene(client, use_model, scene_text)
        adapted.extend(result)
        if on_progress:
            try:
                on_progress(i, len(scenes), result)
            except Exception:
                pass

    # Stats
    tv_kinds = {"action": 0, "dialogue": 0, "scene_heading": 0, "transition": 0}
    for s in segments:
        k = s.get("kind")
        if k in tv_kinds:
            tv_kinds[k] += 1
    radio_kinds = {"narrator": 0, "sfx": 0, "dialogue": 0, "scene_heading": 0}
    for s in adapted:
        k = s.get("kind")
        if k in radio_kinds:
            radio_kinds[k] += 1

    return {
        "adapted_segments": adapted,
        "scene_count":      len(scenes),
        "model":            use_model,
        "stats": {
            "tv_segments":      len(segments),
            "radio_segments":   len(adapted),
            "tv_action":        tv_kinds["action"],
            "tv_dialogue":      tv_kinds["dialogue"],
            "tv_scene_heading": tv_kinds["scene_heading"],
            "tv_transition":    tv_kinds["transition"],
            "radio_narrator":   radio_kinds["narrator"],
            "radio_sfx":        radio_kinds["sfx"],
            "radio_dialogue":   radio_kinds["dialogue"],
            "radio_scene_heading": radio_kinds["scene_heading"],
        },
    }
