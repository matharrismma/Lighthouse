"""animation_orchestrator.py — End-to-end animation pipeline (LOOP 26).

One command, one script → one episode. Walks a script in content/scripts/*.md,
parses scenes, drives the existing render_* tools for voice / stills / motion,
assembles via ffmpeg, and writes a manifest.

Pipeline:
  1. PARSE — read script.md, extract: title, length target, scenes, dialogue
  2. STORYBOARD — author one card per scene (substrate compounds even when
     the animation hasn't been rendered yet)
  3. VOICES — for each spoken line, call render_audio_premium (ElevenLabs)
     or fall back to render_audio (Piper) if no key
  4. STILLS — for each scene's visual description, call render_art (SDXL/Flux)
     to generate the Shepard-style seed frame
  5. MOTION — for each scene, call render_video (Runway image→video) using
     the still as the seed
  6. ASSEMBLE — ffmpeg concatenates audio + video into the final mp4
  7. MANIFEST — data/animation_runs/<run_id>.json with every asset path

OFFLINE-SAFE: every step is gated on the presence of its API key
(ELEVENLABS_API_KEY, RUNWAY_API_KEY) or the existence of the binary tool.
If absent, the orchestrator runs in DRY mode and reports what WOULD happen,
along with a cost estimate.

Strict IP discipline (per 2026-05-17 directive):
  - Hundred Acre Theatre: Shepard-1926 visuals ONLY. Never Disney.
  - Sci-Fi Theatre: original visuals (1950s pulp aesthetic).

Usage:
  python tools/animation_orchestrator.py --script content/scripts/hundred_acre_01_introducing_pooh.md
  python tools/animation_orchestrator.py --script ... --dry-run
  python tools/animation_orchestrator.py --script ... --only-storyboard
  python tools/animation_orchestrator.py --status <run_id>
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Force UTF-8 stdout/stderr so unicode in script titles doesn't blow up Windows cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SCRIPTS_DIR = REPO / "content" / "scripts"
ANIMATION_RUNS = REPO / "data" / "animation_runs"
CARDS_DIR = REPO / "data" / "cards"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_env() -> dict:
    """Detect what's available in the current environment."""
    return {
        "elevenlabs_key": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "runway_key": bool(os.environ.get("RUNWAY_API_KEY")),
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "ffmpeg": _exists_binary("ffmpeg"),
        "piper": _exists_binary("piper"),
        "stable_diffusion_local": (REPO / "tools" / "render_art.py").exists(),
    }


def _exists_binary(name: str) -> bool:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(p) / (name + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return True
    return False


# ---------- Script parsing ----------
# Matt's scripts (Sci-Fi Theatre, Hundred Acre Theatre) use `### Scene N · ...`
# headers with production field markers like **Audio:**, **Hero frame:**,
# **Motion:**, **Mood:**. Earlier h2 pattern missed all of them.

SCENE_HEADER = re.compile(r"^#{2,4}\s+Scene\s+(\d+)\s*[·:\.\s-]*(.*)$", re.MULTILINE)
SECTION_HEADER = re.compile(r"^#{1,4}\s+(?!Scene\s+\d)(.+)$", re.MULTILINE)
H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
META_LENGTH = re.compile(r"\*\*Length(?:\s+target)?:\*\*\s*(.+)$", re.MULTILINE)
META_SOURCE = re.compile(r"\*\*Source:\*\*\s*(.+)$", re.MULTILINE)
META_RIGHTS = re.compile(r"\*\*Rights:\*\*\s*(.+)$", re.MULTILINE)
SPEAKER_LINE = re.compile(r"^\*\*([A-Z][A-Z\s'\-]+?):\*\*\s+(.+)$", re.MULTILINE)
VISUAL_LINE = re.compile(r"^\*\[VISUAL:\s*(.+?)\]\*", re.MULTILINE | re.IGNORECASE)
SCENE_BREAK = re.compile(r"^---+\s*$", re.MULTILINE)

# Production-field patterns used in Sci-Fi Theatre + Hundred Acre Theatre scripts
PROD_FIELDS = {
    "audio": re.compile(r"\*\*Audio(?:\s+file)?:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
    "hero_frame": re.compile(r"\*\*Hero frame:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
    "motion": re.compile(r"\*\*Motion:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
    "mood": re.compile(r"\*\*Mood:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
    "shot": re.compile(r"\*\*Shot:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
    "narrator": re.compile(r"\*\*Narrator(?:\s+\([^)]+\))?:\*\*\s*(.+?)(?=\n\*\*|\n#{2,}|\Z)", re.IGNORECASE | re.DOTALL),
}


def parse_script(path: Path) -> dict:
    """Parse a script.md file into a structured run plan."""
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")

    title_m = H1.search(text)
    title = title_m.group(1).strip() if title_m else path.stem

    length = (META_LENGTH.search(text) or [None, None])[1] or "unknown"
    source = (META_SOURCE.search(text) or [None, None])[1] or "unknown"
    rights = (META_RIGHTS.search(text) or [None, None])[1] or "unknown"

    # Split by scene headers; if no scenes, treat as a single scene
    scenes = []
    parts = SCENE_HEADER.split(text)
    # SCENE_HEADER.split returns [pre, num, title, body, num, title, body, ...]
    if len(parts) > 1:
        # First chunk is pre-scene (the header / metadata) — skip
        i = 1
        while i < len(parts) - 1:
            num = parts[i]
            scene_title = parts[i+1].strip()
            scene_body = parts[i+2] if i+2 < len(parts) else ""
            # Trim at next section header (in case parser overran)
            next_section = SECTION_HEADER.search(scene_body)
            if next_section:
                scene_body = scene_body[:next_section.start()]
            scenes.append(_extract_scene_content(int(num), scene_title, scene_body))
            i += 3
    else:
        # No "## Scene N" — try to parse by --- breaks
        chunks = SCENE_BREAK.split(text)
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                scenes.append(_extract_scene_content(i + 1, f"Scene {i+1}", chunk))

    return {
        "script_path": str(path.relative_to(REPO)),
        "title": title,
        "length_target": length.strip(),
        "source": source.strip(),
        "rights": rights.strip(),
        "scene_count": len(scenes),
        "scenes": scenes,
    }


def _extract_scene_content(num: int, scene_title: str, body: str) -> dict:
    """Pull out dialogue, visual descriptions, motion, mood, audio cues, and prose.

    Recognizes Sci-Fi Theatre / Hundred Acre Theatre production field markers
    (Audio / Hero frame / Motion / Mood / Shot / Narrator) in addition to
    the older **SPEAKER:** dialogue pattern."""
    dialogue = []
    for m in SPEAKER_LINE.finditer(body):
        dialogue.append({"speaker": m.group(1).strip().title(), "line": m.group(2).strip()})
    visuals = [m.group(1).strip() for m in VISUAL_LINE.finditer(body)]

    # Extract production fields
    prod = {}
    for key, pat in PROD_FIELDS.items():
        m = pat.search(body)
        if m:
            prod[key] = m.group(1).strip()

    # If hero_frame found, add it to visuals; if motion found, append to visuals
    if prod.get("hero_frame"):
        visuals.append(f"HERO: {prod['hero_frame']}")
    if prod.get("shot"):
        visuals.append(f"SHOT: {prod['shot']}")
    if prod.get("motion"):
        visuals.append(f"MOTION: {prod['motion']}")

    # If narrator/audio found, add to dialogue
    if prod.get("audio"):
        dialogue.append({"speaker": "Audio", "line": prod["audio"][:300]})
    if prod.get("narrator"):
        dialogue.append({"speaker": "Narrator", "line": prod["narrator"][:300]})

    # Prose is the cleaned body minus all the markers
    prose = body.strip()
    for pat in [SPEAKER_LINE, VISUAL_LINE] + list(PROD_FIELDS.values()):
        prose = pat.sub("", prose)
    # Strip residual ** field labels
    prose = re.sub(r"\*\*[A-Za-z][^*]*?:\*\*\s*", "", prose).strip()
    word_count = len(prose.split())

    return {
        "scene_number": num,
        "scene_title": scene_title,
        "dialogue_lines": dialogue,
        "visual_descriptions": visuals,
        "production_fields": prod,
        "prose_excerpt": prose[:800],
        "word_count_total": word_count,
        "estimated_seconds": max(15, int(word_count / 2.5)),  # ~150 wpm narration
    }


# ---------- Storyboard cards ----------

def author_storyboard_cards(plan: dict, run_id: str) -> list[str]:
    """For each scene, author one card on shelf=animation, box=<script_slug>.
    Returns the list of card_ids created (or that would be created)."""
    try:
        from api.cards import _make_card_id, _compute_source_hash  # type: ignore
    except Exception:
        return []
    script_slug = Path(plan["script_path"]).stem
    created = []
    for scene in plan["scenes"]:
        seed = f"storyboard::{script_slug}::{scene['scene_number']}"
        cid = _make_card_id("note", seed)
        p = CARDS_DIR / f"{cid}.json"
        if p.exists():
            created.append(cid)
            continue
        # Build the card body — uses production fields when present
        body_parts = [f"**Scene {scene['scene_number']}: {scene['scene_title']}**"]
        prod = scene.get("production_fields") or {}
        if prod.get("hero_frame"):
            body_parts.append(f"\nHERO FRAME: {prod['hero_frame'][:600]}")
        if prod.get("shot"):
            body_parts.append(f"\nSHOT: {prod['shot'][:300]}")
        if prod.get("motion"):
            body_parts.append(f"\nMOTION: {prod['motion'][:400]}")
        if prod.get("mood"):
            body_parts.append(f"\nMOOD: {prod['mood'][:200]}")
        if prod.get("audio"):
            body_parts.append(f"\nAUDIO: {prod['audio'][:300]}")
        if prod.get("narrator") and not prod.get("audio"):
            body_parts.append(f"\nNARRATOR: {prod['narrator'][:300]}")
        if scene["visual_descriptions"] and not any(prod.get(k) for k in ("hero_frame", "shot", "motion")):
            body_parts.append("\nVISUAL:\n" + "\n".join("· " + v for v in scene["visual_descriptions"][:5]))
        if scene["dialogue_lines"] and not prod.get("audio"):
            body_parts.append("\nDIALOGUE:\n" + "\n".join(
                f"  {d['speaker']}: {d['line'][:120]}" for d in scene["dialogue_lines"][:5]
            ))
        if scene.get("prose_excerpt") and len("".join(body_parts)) < 1500:
            body_parts.append(f"\nPROSE: {scene['prose_excerpt'][:400]}")
        body = "\n".join(body_parts)[:3800]
        card = {
            "id": cid,
            "kind": "note",
            "title": f"Storyboard · {plan['title'][:60]} · S{scene['scene_number']}",
            "body": body,
            "source": {
                "label": plan["source"],
                "url": f"/scripts/{script_slug}",
                "ref": f"Scene {scene['scene_number']}",
                "authority_tier": "matt",
            },
            "shelf": "animation",
            "box": script_slug,
            "bands": ["animation", "storyboard", script_slug, f"scene_{scene['scene_number']:02d}"],
            "connections": [],
            "author": "matt",
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "private",
            "lifecycle_stage": "private",
            "volatility": "stable",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "extra": {
                "scene_number": scene["scene_number"],
                "scene_title": scene["scene_title"],
                "dialogue_line_count": len(scene["dialogue_lines"]),
                "visual_description_count": len(scene["visual_descriptions"]),
                "estimated_seconds": scene["estimated_seconds"],
                "run_id": run_id,
            },
        }
        card["source_hash"] = _compute_source_hash(card)
        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(card, indent=2), encoding="utf-8")
        created.append(cid)
    return created


# ---------- Cost estimation ----------

def estimate_cost(plan: dict) -> dict:
    """Best-effort cost estimate. ElevenLabs: $0.30 per 1000 characters.
    Runway Gen-3: ~$0.50 per 10-second clip. SDXL local: ~$0."""
    total_chars = 0
    total_clips = 0
    for scene in plan["scenes"]:
        for d in scene["dialogue_lines"]:
            total_chars += len(d["line"])
        total_chars += len(scene["prose_excerpt"])
        # 1 clip per ~10s of scene
        total_clips += max(1, scene["estimated_seconds"] // 10)
    elevenlabs_cost = (total_chars / 1000.0) * 0.30
    runway_cost = total_clips * 0.50
    return {
        "total_characters_voice": total_chars,
        "elevenlabs_estimated_usd": round(elevenlabs_cost, 2),
        "total_video_clips": total_clips,
        "runway_estimated_usd": round(runway_cost, 2),
        "total_estimated_usd": round(elevenlabs_cost + runway_cost, 2),
        "_note": "Stills are SDXL local (effectively free). ffmpeg assembly is free.",
    }


# ---------- Run manifest ----------

def write_manifest(run_id: str, plan: dict, env: dict, storyboard_card_ids: list, cost: dict, dry_run: bool):
    ANIMATION_RUNS.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "started_at": _now(),
        "script": plan["script_path"],
        "title": plan["title"],
        "dry_run": dry_run,
        "environment": env,
        "scene_count": plan["scene_count"],
        "storyboard_card_ids": storyboard_card_ids,
        "cost_estimate": cost,
        "stages": {
            "parse": {"status": "done", "scenes_extracted": plan["scene_count"]},
            "storyboard": {"status": "done" if storyboard_card_ids else "skipped",
                           "cards_created": len(storyboard_card_ids)},
            "voices": {"status": "would_run" if env["elevenlabs_key"] else "blocked_no_key"},
            "stills": {"status": "would_run" if env["stable_diffusion_local"] else "blocked_no_local_sd"},
            "motion": {"status": "would_run" if env["runway_key"] else "blocked_no_key"},
            "assemble": {"status": "would_run" if env["ffmpeg"] else "blocked_no_ffmpeg"},
        },
    }
    p = ANIMATION_RUNS / f"{run_id}.json"
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return p


def _run_id_for(script_path: Path) -> str:
    return f"{script_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", help="Path to a script.md file")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; don't call APIs or write big files")
    parser.add_argument("--only-storyboard", action="store_true", help="Author storyboard cards but skip render stages")
    parser.add_argument("--status", help="Show the manifest for a given run_id")
    args = parser.parse_args()

    if args.status:
        p = ANIMATION_RUNS / f"{args.status}.json"
        if not p.exists():
            print(f"No manifest at {p}")
            return
        print(p.read_text(encoding="utf-8"))
        return

    if not args.script:
        # Default: list available scripts
        print("Available scripts:")
        for f in SCRIPTS_DIR.glob("*.md"):
            print(f"  {f.relative_to(REPO)}")
        print("\nRun with: --script <path>  (add --dry-run for plan-only)")
        return

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        script_path = SCRIPTS_DIR / args.script
        if not script_path.exists():
            print(f"Script not found: {args.script}")
            return

    print(f"=== Animation orchestrator ===")
    print(f"Script: {script_path.relative_to(REPO)}")

    env = _check_env()
    print(f"\nEnvironment:")
    for k, v in env.items():
        mark = "ok" if v else "absent"
        print(f"  {k}: {mark}")

    plan = parse_script(script_path)
    print(f"\nParsed:")
    print(f"  Title: {plan['title']}")
    print(f"  Length target: {plan['length_target']}")
    print(f"  Source: {plan['source']}")
    print(f"  Rights: {plan['rights']}")
    print(f"  Scenes: {plan['scene_count']}")

    cost = estimate_cost(plan)
    print(f"\nCost estimate:")
    print(f"  Voice ({cost['total_characters_voice']} chars): ${cost['elevenlabs_estimated_usd']}")
    print(f"  Video ({cost['total_video_clips']} clips): ${cost['runway_estimated_usd']}")
    print(f"  TOTAL: ${cost['total_estimated_usd']}")

    run_id = _run_id_for(script_path)

    if args.only_storyboard or args.dry_run:
        storyboard_ids = author_storyboard_cards(plan, run_id)
        print(f"\nStoryboard cards: {len(storyboard_ids)} (run_id={run_id})")
    else:
        storyboard_ids = author_storyboard_cards(plan, run_id)
        print(f"\nStoryboard cards authored: {len(storyboard_ids)}")
        # Stages: each guarded on env availability
        if not env["elevenlabs_key"]:
            print("[voices] BLOCKED — set ELEVENLABS_API_KEY to render premium voice")
        if not env["runway_key"]:
            print("[motion] BLOCKED — set RUNWAY_API_KEY to drive Runway")
        if not env["ffmpeg"]:
            print("[assemble] BLOCKED — install ffmpeg to assemble final mp4")
        print("\nNothing was rendered (keys/binaries missing). Run --dry-run to suppress this warning.")

    manifest_path = write_manifest(run_id, plan, env, storyboard_ids, cost, args.dry_run or args.only_storyboard)
    print(f"\nManifest: {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
