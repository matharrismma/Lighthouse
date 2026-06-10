"""Pilot orchestrator — assembles a complete episode MP4 from a JSON manifest.

Reads content/pilots/<name>.json and produces D:/library_files/_pilots/<name>/final.mp4.

Phased pipeline (each phase idempotent — re-running skips already-done work):

  PHASE 1: Voice prep
    For intro + closing: render via ElevenLabs API → MP3
    (Body audio is the original PD broadcast — no rendering needed.)

  PHASE 2: Motion prep
    For each scene:
      - ken_burns: ffmpeg zoompan over still → silent MP4 of scene duration
      - runway: gen3a_turbo image-to-video → 5/10-sec clip + freeze last frame
                to scene duration → silent MP4 of scene duration
      - runway_existing: reuse existing clip file + freeze if needed
    Intro and closing get their own ken_burns rendered the same way.

  PHASE 3: Per-segment audio mux
    - body.mp4   = concat(scene silent clips) + source audio slice [0..body_dur]
    - intro.mp4  = ken_burns(intro frame) + intro voice
    - closing.mp4 = ken_burns(closing frame) + closing voice

  PHASE 4: Final concat
    - final.mp4 = concat(intro.mp4, body.mp4, closing.mp4)

Usage:
  python tools/build_pilot.py --manifest content/pilots/soft_rains.json
  python tools/build_pilot.py --manifest content/pilots/soft_rains.json --phase voice
  python tools/build_pilot.py --manifest content/pilots/soft_rains.json --dry-run
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
import base64
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import os

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()

ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY") or ""
RUNWAY_KEY = os.environ.get("RUNWAY_API_KEY") or ""
ELEVEN_API = "https://api.elevenlabs.io/v1"
RUNWAY_API = "https://api.dev.runwayml.com/v1"


def log(msg: str, indent: int = 0):
    print(("  " * indent) + msg, flush=True)


# ====== ElevenLabs ======
def tts_render(voice_id: str, text: str, settings: dict, out_path: Path) -> Path:
    if out_path.exists() and out_path.stat().st_size > 1024:
        log(f"[SKIP-TTS] {out_path.name} exists", 1)
        return out_path
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": settings.get("stability", 0.5),
            "similarity_boost": settings.get("similarity_boost", 0.75),
            "style": settings.get("style", 0.4),
            "use_speaker_boost": True,
        },
    }
    req = urllib.request.Request(
        f"{ELEVEN_API}/text-to-speech/{voice_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json", "accept": "audio/mpeg"},
        method="POST",
    )
    log(f"[TTS] {out_path.name} ({len(text)} chars)", 1)
    with urllib.request.urlopen(req, timeout=120) as r:
        audio = r.read()
    out_path.write_bytes(audio)
    log(f"  -> {len(audio)//1024} KB", 2)
    return out_path


# ====== Runway image-to-video ======
class RunwayModerationError(Exception):
    """Raised when Runway rejects a prompt — caller should fall back."""


def _resize_for_data_uri(image_path: Path, target_max_kb: int = 3000) -> bytes:
    """Read a PNG and re-encode it as JPEG below the target size for Runway's data-URI cap.
    Returns the resized bytes (with JPEG content-type). Preserves aspect ratio.
    Iterates quality down until size fits.
    """
    from PIL import Image
    import io
    raw = image_path.read_bytes()
    if len(raw) // 1024 <= target_max_kb:
        return raw  # already small enough as-is
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    # Downscale if very large (preserve aspect)
    max_dim = 1920
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    # Iterate quality down until under target_max_kb
    for q in (90, 85, 80, 75, 70, 65, 60):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, optimize=True)
        size_kb = buf.tell() // 1024
        if size_kb <= target_max_kb:
            log(f"  [resize] {image_path.name}: {len(raw)//1024} KB PNG -> {size_kb} KB JPEG (q={q})", 2)
            return buf.getvalue()
    # Last resort
    buf.seek(0); return buf.read()


def runway_i2v(image_path: Path, prompt: str, duration_sec: int, out_path: Path,
               model: str = "gen3a_turbo", ratio: str = "1280:768") -> Path:
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-RUNWAY] {out_path.name} exists", 1)
        return out_path
    log(f"[RUNWAY] {out_path.name} ({duration_sec}s via {model})", 1)
    img_bytes = _resize_for_data_uri(image_path, target_max_kb=3000)
    # Determine MIME type from bytes magic
    mime = "image/png" if img_bytes[:4] == b"\x89PNG" else "image/jpeg"
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{img_b64}"
    payload = {"promptImage": data_uri, "promptText": prompt, "model": model,
               "duration": duration_sec}
    # Schema differences by model family:
    #   kling2.5_turbo_pro / seedance2 reject the `ratio` field
    #   gen3a/gen4 family require `ratio`
    #   veo3 family accepts `ratio`
    if not model.startswith("kling") and not model.startswith("seedance"):
        payload["ratio"] = ratio
    req = urllib.request.Request(
        f"{RUNWAY_API}/image_to_video",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RUNWAY_KEY}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # Submit with retry on transient network/SSL errors
    submit_attempts = 0
    resp = None
    while submit_attempts < 5:
        submit_attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:600]
            log(f"  SUBMIT HTTP {e.code}: {body}", 2)
            if e.code in (400, 422):
                raise RunwayModerationError(f"Runway submit rejected: {body}")
            if e.code == 429:
                # Daily limit / rate limit — treat as moderation-fallback so build continues
                raise RunwayModerationError(f"Runway rate-limited (429): {body}")
            # Other HTTP errors: retry once or twice then give up
            if submit_attempts >= 3:
                raise
            log(f"  submit retry {submit_attempts}/5 in 15s...", 2)
            time.sleep(15)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            log(f"  submit network error #{submit_attempts}: {e}", 2)
            if submit_attempts >= 5:
                raise RunwayModerationError(f"Runway submit network failure 5x: {e}")
            time.sleep(15)
    if resp is None:
        raise RunwayModerationError("Runway submit returned no response after retries")
    tid = resp.get("id")
    log(f"  task_id={tid}", 2)
    # poll with DNS/network retry — transient failures should not kill the build
    # 360 × 5s = 30 min total — kling clips can take 8+ min when busy
    consecutive_net_fails = 0
    data = {}
    status = "PENDING"
    for _ in range(360):
        time.sleep(5)
        preq = urllib.request.Request(
            f"{RUNWAY_API}/tasks/{tid}",
            headers={"Authorization": f"Bearer {RUNWAY_KEY}", "X-Runway-Version": "2024-11-06"},
        )
        try:
            with urllib.request.urlopen(preq, timeout=30) as r:
                data = json.loads(r.read())
            consecutive_net_fails = 0
        except (urllib.error.URLError, OSError) as e:
            consecutive_net_fails += 1
            log(f"  poll net error #{consecutive_net_fails}: {e}", 2)
            if consecutive_net_fails >= 12:  # ~1 min of failures = give up
                raise RuntimeError(f"Runway {tid} polling network down for 60s")
            time.sleep(10)  # back off
            continue
        status = data.get("status")
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    if status != "SUCCEEDED":
        failure_code = data.get("failureCode", "")
        failure = data.get("failure", "")
        # Moderation failures during processing
        if "SAFETY" in str(failure_code) or "MODERATION" in str(failure_code):
            raise RunwayModerationError(f"Runway {tid} {status}: {failure_code} {failure}")
        # If stuck in RUNNING/PENDING/THROTTLED after 30 min, give up THIS clip and fall back to KB
        if status in ("RUNNING", "PENDING", "THROTTLED"):
            log(f"  TIMEOUT after 30 min — clip still {status}. Falling back to Ken Burns.", 2)
            raise RunwayModerationError(f"Runway {tid} stuck {status} after timeout")
        raise RuntimeError(f"Runway {tid} ended {status}: {failure} {failure_code}")
    url = data["output"][0]
    with urllib.request.urlopen(url, timeout=120) as r:
        out_path.write_bytes(r.read())
    log(f"  -> {out_path.stat().st_size//1024} KB", 2)
    return out_path


# ====== ffmpeg helpers ======
def get_audio_duration(path: Path) -> float:
    r = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def get_video_duration(path: Path) -> float:
    return get_audio_duration(path)


def ken_burns_clip(frame_path: Path, motion: dict, duration_sec: float,
                   width: int, height: int, fps: int, out_path: Path) -> Path:
    """Produce a silent MP4 of the given duration with Ken Burns motion over the still."""
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-KB] {out_path.name} exists", 1)
        return out_path
    sz, ez = motion.get("start_zoom", 1.0), motion.get("end_zoom", 1.08)
    sx, sy = motion.get("start_xy", [0.5, 0.5])
    ex, ey = motion.get("end_xy", [0.5, 0.5])
    total_frames = max(2, int(duration_sec * fps))
    z_expr = f"min({sz}+({ez}-{sz})*on/{total_frames-1},{ez})"
    x_expr = f"iw*({sx}+({ex}-{sx})*on/{total_frames-1}) - iw/zoom/2"
    y_expr = f"ih*({sy}+({ey}-{sy})*on/{total_frames-1}) - ih/zoom/2"
    kb = (f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
          f"d={total_frames}:s={width}x{height}:fps={fps}")
    log(f"[KB] {out_path.name} ({duration_sec:.1f}s zoom {sz}->{ez})", 1)
    cmd = [
        FF, "-y", "-loop", "1", "-i", str(frame_path),
        "-filter_complex", f"[0:v]{kb}[v]",
        "-map", "[v]", "-t", str(duration_sec),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL ffmpeg ken_burns: {r.stderr[-1000:]}", 2)
        raise RuntimeError("ken_burns ffmpeg failed")
    return out_path


def freeze_extend_clip(clip_path: Path, target_duration_sec: float,
                      width: int, height: int, fps: int, out_path: Path) -> Path:
    """Take a short clip, extend it to target duration by freezing the last frame.
    Output is scaled to (width, height) and silent."""
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-FRZ] {out_path.name} exists", 1)
        return out_path
    clip_dur = get_video_duration(clip_path)
    extra = max(0, target_duration_sec - clip_dur)
    log(f"[FRZ] {out_path.name} (clip {clip_dur:.1f}s + freeze {extra:.1f}s)", 1)
    scale_pad = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
    filt = f"[0:v]{scale_pad},tpad=stop_mode=clone:stop_duration={extra:.3f}[v]"
    cmd = [
        FF, "-y", "-i", str(clip_path),
        "-filter_complex", filt,
        "-map", "[v]", "-t", str(target_duration_sec),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL ffmpeg freeze_extend: {r.stderr[-1000:]}", 2)
        raise RuntimeError("freeze_extend ffmpeg failed")
    return out_path


def loop_extend_clip(clip_path: Path, target_duration_sec: float,
                     width: int, height: int, fps: int, out_path: Path) -> Path:
    """Loop a short clip enough times to reach target duration, with a crossfade
    on each loop seam for seamlessness. Output silent, scaled to (width, height).

    For 60s-80s limited animation feel: loops are how Hanna-Barbera animated
    long scenes from short cycles. We embrace that.
    """
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-LOOP] {out_path.name} exists", 1)
        return out_path
    clip_dur = get_video_duration(clip_path)
    if clip_dur <= 0.1:
        raise RuntimeError(f"clip duration unreadable for {clip_path}")
    loops_needed = max(1, int(target_duration_sec / clip_dur) + 1)
    log(f"[LOOP] {out_path.name} (clip {clip_dur:.1f}s × {loops_needed} loops -> {target_duration_sec:.1f}s)", 1)

    scale_pad = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")
    cmd = [
        FF, "-y",
        "-stream_loop", str(loops_needed - 1),
        "-i", str(clip_path),
        "-filter_complex", f"[0:v]{scale_pad}[v]",
        "-map", "[v]", "-t", str(target_duration_sec),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL ffmpeg loop_extend: {r.stderr[-1000:]}", 2)
        raise RuntimeError("loop_extend ffmpeg failed")
    return out_path


def concat_silent_clips(clips: list[Path], out_path: Path, width: int, height: int, fps: int) -> Path:
    """Concatenate silent MP4s into one silent track."""
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-CONCAT] {out_path.name} exists", 1)
        return out_path
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips) + "\n", encoding="utf-8")
    log(f"[CONCAT-V] {out_path.name} from {len(clips)} clips", 1)
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c", "copy", "-movflags", "+faststart", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL concat: {r.stderr[-1000:]}", 2)
        raise RuntimeError("concat ffmpeg failed")
    return out_path


def mux_audio(video_path: Path, audio_path: Path, audio_start_sec: float,
              audio_duration_sec: float, out_path: Path) -> Path:
    """Mux an audio slice onto a video. Video duration sets the output duration."""
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-MUX] {out_path.name} exists", 1)
        return out_path
    log(f"[MUX] {out_path.name} (audio {audio_start_sec:.1f}+{audio_duration_sec:.1f}s)", 1)
    cmd = [
        FF, "-y", "-i", str(video_path),
        "-ss", str(audio_start_sec), "-t", str(audio_duration_sec), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL mux: {r.stderr[-1000:]}", 2)
        raise RuntimeError("mux ffmpeg failed")
    return out_path


def mix_voice_over_music(voice_path: Path, music_path: Path,
                         music_volume_db: float, voice_lead_in_sec: float,
                         out_path: Path) -> Path:
    """Mix a voice track over a background music track.
    Music plays from t=0; voice starts at voice_lead_in_sec.
    Music ducked by music_volume_db (typically -10 to -15 dB).
    Output duration = max(voice_end, music_end).
    """
    if out_path.exists() and out_path.stat().st_size > 1024:
        log(f"[SKIP-VMIX] {out_path.name} exists", 1)
        return out_path
    log(f"[VMIX] {out_path.name} (voice +{voice_lead_in_sec}s over music @{music_volume_db}dB)", 1)
    delay_ms = int(voice_lead_in_sec * 1000)
    filt = (
        f"[0:a]adelay={delay_ms}|{delay_ms}[v];"
        f"[1:a]volume={music_volume_db}dB[m];"
        f"[v][m]amix=inputs=2:duration=longest:normalize=0[a]"
    )
    cmd = [
        FF, "-y",
        "-i", str(voice_path),
        "-i", str(music_path),
        "-filter_complex", filt,
        "-map", "[a]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL voice-over-music mix: {r.stderr[-1500:]}", 2)
        raise RuntimeError("mix_voice_over_music ffmpeg failed")
    return out_path


def overlay_foley_on_audio(base_audio_path: Path, base_start_sec: float, base_duration_sec: float,
                            foley_overlays: list[dict], out_path: Path) -> Path:
    """Take a base audio track (e.g., broadcast body), slice it, and overlay foley clips
    at specified time offsets and volumes.

    foley_overlays = [{"clip": Path, "start_sec": float, "duration_sec": float, "volume_db": float}, ...]
    """
    if out_path.exists() and out_path.stat().st_size > 1024:
        log(f"[SKIP-FOLEY] {out_path.name} exists", 1)
        return out_path
    log(f"[FOLEY] {out_path.name} (base + {len(foley_overlays)} overlays)", 1)

    inputs = ["-ss", str(base_start_sec), "-t", str(base_duration_sec), "-i", str(base_audio_path)]
    for ov in foley_overlays:
        inputs += ["-i", str(ov["clip"])]

    # filter_complex: delay each overlay to its offset, then amix all together
    filter_parts = ["[0:a]volume=0dB[base]"]
    mix_inputs = ["[base]"]
    for i, ov in enumerate(foley_overlays):
        idx = i + 1
        delay_ms = int(ov["start_sec"] * 1000)
        vol_db = ov.get("volume_db", -8)
        filter_parts.append(f"[{idx}:a]volume={vol_db}dB,adelay={delay_ms}|{delay_ms}[f{idx}]")
        mix_inputs.append(f"[f{idx}]")
    filter_parts.append(f"{''.join(mix_inputs)}amix=inputs={len(foley_overlays)+1}:duration=first:normalize=0[a]")
    filt = ";".join(filter_parts)

    cmd = [FF, "-y", *inputs, "-filter_complex", filt, "-map", "[a]",
           "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL foley overlay: {r.stderr[-1500:]}", 2)
        raise RuntimeError("overlay_foley_on_audio ffmpeg failed")
    return out_path


def mux_arbitrary_audio(video_path: Path, audio_path: Path, out_path: Path) -> Path:
    """Mux an already-prepared audio file onto a video (no slicing)."""
    if out_path.exists() and out_path.stat().st_size > 10000:
        log(f"[SKIP-MUXA] {out_path.name} exists", 1)
        return out_path
    log(f"[MUXA] {out_path.name}", 1)
    cmd = [
        FF, "-y", "-i", str(video_path), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL mux arbitrary: {r.stderr[-1000:]}", 2)
        raise RuntimeError("mux_arbitrary_audio failed")
    return out_path


def concat_with_audio(parts: list[Path], out_path: Path) -> Path:
    """Final concat of intro/body/closing — all must have same codec."""
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{c.as_posix()}'" for c in parts) + "\n", encoding="utf-8")
    log(f"[FINAL-CONCAT] {out_path.name} from {len(parts)} parts", 1)
    # Re-encode at concat because intro/body/closing may have come from different filter chains
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k",
           "-pix_fmt", "yuv420p", "-r", "30",
           "-movflags", "+faststart",
           str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"FAIL final concat: {r.stderr[-1000:]}", 2)
        raise RuntimeError("final concat ffmpeg failed")
    return out_path


# ====== Pilot build ======
def build(manifest_path: Path, phase_filter: str | None = None, dry_run: bool = False):
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = m["name"]
    out_dir = Path(m["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = m["resolution"]
    fps = m["fps"]
    source_audio = Path(m["source_audio"])
    assert source_audio.exists(), f"Missing source audio: {source_audio}"

    hero_dir = Path("D:/library_files/_hero_frames")
    motion_test_dir = Path("D:/library_files/_motion_tests")

    print(f"=== Building pilot: {name} ({m['title']}) ===")
    print(f"Output dir: {out_dir}")
    print(f"Source audio: {source_audio.name}")
    print(f"Scenes: {len(m['scenes'])}")
    print()

    if dry_run:
        print("DRY RUN — would generate the following voice + motion assets:")
        if m.get("intro"):
            print(f"  intro voice: ElevenLabs voice {m['intro']['voice_id']} ({len(m['intro']['text'])} chars)")
        if m.get("closing"):
            print(f"  closing voice: ElevenLabs voice {m['closing']['voice_id']} ({len(m['closing']['text'])} chars)")
        runway_scenes = [s for s in m["scenes"] if s["motion"]["type"] == "runway"]
        print(f"  runway clips needed: {len(runway_scenes)} (cost ~{sum(s['motion'].get('duration_clip_sec',5) for s in runway_scenes)*5} credits)")
        return

    # === PHASE 1: voice prep ===
    if not phase_filter or phase_filter == "voice":
        print("--- PHASE 1: Voice prep ---")
        intro = m["intro"]
        intro_audio = out_dir / "intro.mp3"
        tts_render(intro["voice_id"], intro["text"], intro, intro_audio)
        closing = m["closing"]
        closing_audio = out_dir / "closing.mp3"
        tts_render(closing["voice_id"], closing["text"], closing, closing_audio)
        print()

    # === PHASE 2: motion prep ===
    if not phase_filter or phase_filter == "motion":
        print("--- PHASE 2: Motion prep ---")

        def render_motion(label: str, frame_path: Path, motion: dict, duration_sec: float, out_clip: Path):
            mtype = motion["type"]
            try:
                if mtype == "ken_burns":
                    ken_burns_clip(frame_path, motion, duration_sec, width, height, fps, out_clip)
                elif mtype in ("runway", "runway_action"):
                    short = out_clip.parent / f"{out_clip.stem}_short.mp4"
                    runway_i2v(frame_path, motion["prompt"], motion["duration_clip_sec"], short,
                               model=motion.get("model", "gen3a_turbo"),
                               ratio=motion.get("ratio", "1280:720"))
                    freeze_extend_clip(short, duration_sec, width, height, fps, out_clip)
                elif mtype == "runway_loop":
                    short = out_clip.parent / f"{out_clip.stem}_short.mp4"
                    runway_i2v(frame_path, motion["prompt"], motion["duration_clip_sec"], short,
                               model=motion.get("model", "gen3a_turbo"),
                               ratio=motion.get("ratio", "1280:720"))
                    loop_extend_clip(short, duration_sec, width, height, fps, out_clip)
                elif mtype == "runway_existing":
                    clip_path = Path(motion["clip_path"])
                    assert clip_path.exists(), f"Missing existing runway clip: {clip_path}"
                    freeze_extend_clip(clip_path, duration_sec, width, height, fps, out_clip)
                else:
                    raise ValueError(f"Unknown motion type: {mtype}")
            except RunwayModerationError as e:
                # Graceful fallback: Ken Burns over the same hero frame
                log(f"  [MODERATION-FALLBACK] {label}: {e}", 2)
                log(f"  [KB-FALLBACK] {label} -> ken_burns over {frame_path.name}", 2)
                fallback_motion = {
                    "type": "ken_burns",
                    "start_zoom": 1.0, "end_zoom": 1.08,
                    "start_xy": [0.5, 0.5], "end_xy": [0.5, 0.5],
                }
                ken_burns_clip(frame_path, fallback_motion, duration_sec, width, height, fps, out_clip)

        def render_scene(scene):
            """Render a scene's silent video. Supports two formats:
            1. Single motion (legacy): scene has 'hero_frame' + 'motion' fields.
            2. Multi-cut (preferred for true animation): scene has 'cuts' = list of
               cut dicts, each with 'hero_frame', 'motion', 'duration_sec'. Cuts are
               rendered individually and concatenated within the scene.
            """
            sid = scene["id"]
            scene_clip = out_dir / f"scene_{sid}_silent.mp4"
            if scene_clip.exists() and scene_clip.stat().st_size > 10000:
                log(f"[SKIP-SCENE] scene_{sid}_silent.mp4 exists", 1)
                return
            cuts = scene.get("cuts")
            if cuts:
                # Multi-cut scene: render each cut, concat them
                cut_clips = []
                for ci, cut in enumerate(cuts):
                    cut_label = f"scene {sid} cut {ci+1}/{len(cuts)}"
                    cut_frame = hero_dir / f"{cut['hero_frame']}.png"
                    assert cut_frame.exists(), f"Missing cut frame: {cut_frame}"
                    cut_out = out_dir / f"scene_{sid}_cut{ci+1}_silent.mp4"
                    render_motion(cut_label, cut_frame, cut["motion"],
                                  cut["duration_sec"], cut_out)
                    cut_clips.append(cut_out)
                # Concat cuts within this scene
                concat_silent_clips(cut_clips, scene_clip, width, height, fps)
            else:
                # Legacy single motion
                frame = hero_dir / f"{scene['hero_frame']}.png"
                assert frame.exists(), f"Missing hero frame: {frame}"
                render_motion(f"scene {sid}", frame, scene["motion"],
                              scene["duration_sec"], scene_clip)

        # Per-scene motion
        for scene in m["scenes"]:
            render_scene(scene)

        # Intro motion
        intro = m["intro"]
        intro_frame = hero_dir / f"{intro['hero_frame']}.png"
        render_motion("intro", intro_frame, intro["motion"], intro["duration_target_sec"],
                      out_dir / "intro_silent.mp4")

        # Closing motion
        closing = m["closing"]
        closing_frame = hero_dir / f"{closing['hero_frame']}.png"
        render_motion("closing", closing_frame, closing["motion"], closing["duration_target_sec"],
                      out_dir / "closing_silent.mp4")
        print()

    # === PHASE 3: per-segment audio composition + mux ===
    if not phase_filter or phase_filter == "mux":
        print("--- PHASE 3: Per-segment audio composition + mux ---")
        # ---- BODY ----
        # 1. concat all scene clips silently
        scene_clips = [out_dir / f"scene_{s['id']}_silent.mp4" for s in m["scenes"]]
        body_silent = out_dir / "body_silent.mp4"
        concat_silent_clips(scene_clips, body_silent, width, height, fps)
        # 2. compose body audio = source slice + foley overlays
        body_dur = sum(s["duration_sec"] for s in m["scenes"])
        body_audio_path = out_dir / "body_audio_mixed.mp3"
        foley = m.get("foley_overlays", [])
        if foley:
            # Foley offsets are relative to source audio. We slice source to body window
            # and rebase foley start_sec to be relative to the slice start.
            base_start = m["source_audio_start_sec"]
            rebased = []
            for ov in foley:
                rebased.append({
                    "clip": Path(ov["clip"]),
                    "start_sec": ov["start_sec"] - base_start,
                    "duration_sec": ov["duration_sec"],
                    "volume_db": ov.get("volume_db", -8),
                })
            overlay_foley_on_audio(source_audio, base_start, body_dur, rebased, body_audio_path)
        else:
            # No foley — just slice the source audio
            cmd = [FF, "-y", "-ss", str(m["source_audio_start_sec"]),
                   "-t", str(body_dur), "-i", str(source_audio),
                   "-c:a", "libmp3lame", "-b:a", "192k", str(body_audio_path)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        body_with_audio = out_dir / "body.mp4"
        mux_arbitrary_audio(body_silent, body_audio_path, body_with_audio)

        # ---- INTRO ----
        intro_voice = out_dir / "intro.mp3"
        music_cfg = m.get("music", {})
        intro_theme = music_cfg.get("intro_theme")
        if intro_theme and Path(intro_theme).exists():
            intro_mixed_audio = out_dir / "intro_mixed.mp3"
            mix_voice_over_music(
                voice_path=intro_voice,
                music_path=Path(intro_theme),
                music_volume_db=music_cfg.get("intro_theme_volume_db", -10),
                voice_lead_in_sec=2.0,
                out_path=intro_mixed_audio,
            )
            intro_audio_final = intro_mixed_audio
        else:
            intro_audio_final = intro_voice
        intro_audio_dur = get_audio_duration(intro_audio_final)
        # If intro audio is longer than the silent video, EXTEND (don't replace) the video.
        # For runway_loop: stream-loop to the new duration. For others: ken_burns extend.
        intro_silent = out_dir / "intro_silent.mp4"
        intro_video_dur = get_video_duration(intro_silent)
        if intro_audio_dur > intro_video_dur + 0.5:
            log(f"  intro audio ({intro_audio_dur:.1f}s) longer than video ({intro_video_dur:.1f}s) — extending", 2)
            intro_mtype = m['intro']['motion'].get('type', 'ken_burns')
            if intro_mtype in ("runway_loop", "runway", "runway_action", "runway_existing"):
                # Loop-extend from the short motion clip (if it exists) or the current silent
                source_clip = out_dir / "intro_silent_short.mp4"
                if not source_clip.exists():
                    source_clip = intro_silent
                intro_silent.unlink(missing_ok=True)
                loop_extend_clip(source_clip, intro_audio_dur, width, height, fps, intro_silent)
            else:
                intro_silent.unlink(missing_ok=True)
                ken_burns_clip(
                    Path("D:/library_files/_hero_frames") / f"{m['intro']['hero_frame']}.png",
                    m['intro']['motion'],
                    intro_audio_dur, width, height, fps, intro_silent
                )
        intro_with_audio = out_dir / "intro.mp4"
        if intro_with_audio.exists(): intro_with_audio.unlink()
        mux_arbitrary_audio(intro_silent, intro_audio_final, intro_with_audio)

        # ---- CLOSING ----
        closing_voice = out_dir / "closing.mp3"
        closing_theme = music_cfg.get("closing_theme")
        if closing_theme and Path(closing_theme).exists():
            closing_mixed_audio = out_dir / "closing_mixed.mp3"
            mix_voice_over_music(
                voice_path=closing_voice,
                music_path=Path(closing_theme),
                music_volume_db=music_cfg.get("closing_theme_volume_db", -10),
                voice_lead_in_sec=2.0,
                out_path=closing_mixed_audio,
            )
            closing_audio_final = closing_mixed_audio
        else:
            closing_audio_final = closing_voice
        closing_audio_dur = get_audio_duration(closing_audio_final)
        closing_silent = out_dir / "closing_silent.mp4"
        closing_video_dur = get_video_duration(closing_silent)
        if closing_audio_dur > closing_video_dur + 0.5:
            log(f"  closing audio ({closing_audio_dur:.1f}s) longer than video ({closing_video_dur:.1f}s) — extending", 2)
            closing_mtype = m['closing']['motion'].get('type', 'ken_burns')
            if closing_mtype in ("runway_loop", "runway", "runway_action", "runway_existing"):
                source_clip = out_dir / "closing_silent_short.mp4"
                if not source_clip.exists():
                    source_clip = closing_silent
                closing_silent.unlink(missing_ok=True)
                loop_extend_clip(source_clip, closing_audio_dur, width, height, fps, closing_silent)
            else:
                closing_silent.unlink(missing_ok=True)
                ken_burns_clip(
                    Path("D:/library_files/_hero_frames") / f"{m['closing']['hero_frame']}.png",
                    m['closing']['motion'],
                    closing_audio_dur, width, height, fps, closing_silent
                )
        closing_with_audio = out_dir / "closing.mp4"
        if closing_with_audio.exists(): closing_with_audio.unlink()
        mux_arbitrary_audio(closing_silent, closing_audio_final, closing_with_audio)
        print()

    # === PHASE 4: final concat ===
    if not phase_filter or phase_filter == "concat":
        print("--- PHASE 4: Final concat ---")
        parts = [out_dir / "intro.mp4", out_dir / "body.mp4", out_dir / "closing.mp4"]
        for p in parts:
            assert p.exists(), f"Missing part: {p}"
        final = out_dir / "final.mp4"
        if final.exists():
            final.unlink()
        concat_with_audio(parts, final)
        print()
        # Probe
        probe = subprocess.run([FF, "-hide_banner", "-i", str(final)], capture_output=True, text=True)
        print(f"=== FINAL: {final} ===")
        for line in probe.stderr.splitlines():
            if "Duration" in line or "Stream" in line:
                print("  ", line.strip())
        size_mb = final.stat().st_size / 1024 / 1024
        print(f"  Size: {size_mb:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to pilot manifest JSON")
    ap.add_argument("--phase", choices=["voice", "motion", "mux", "concat"],
                    default=None, help="Run only one phase")
    ap.add_argument("--dry-run", action="store_true", help="Print what would happen without doing it")
    args = ap.parse_args()
    build(Path(args.manifest), phase_filter=args.phase, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
