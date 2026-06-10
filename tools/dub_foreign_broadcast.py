"""Foreign-broadcast translate-and-dub pipeline.

Per [sports property targets memo](project_sports_property_targets_2026-05-16.md),
the highest-leverage moat is: take a foreign-language broadcast (e.g. CMLL
lucha libre Spanish commentary), translate + dub it via our existing engine
room, and we become the only English-language home for that property.

Pipeline:
  1. Whisper transcribes the original commentary (Spanish/Korean/Japanese/etc.)
  2. Claude translates AND tone-adapts (family-safe, pastoral, broadcaster cadence)
  3. ElevenLabs renders the English translation in our brand voices
  4. ffmpeg muxes the new English audio over the original video, muting the
     original commentary but keeping crowd noise + match sounds

Pre-req:
  - openai-whisper or faster-whisper installed (pip install faster-whisper)
  - ANTHROPIC_API_KEY env var set
  - ELEVENLABS_API_KEY env var set + voice_ids configured in render_audio_premium.py
  - ffmpeg (via imageio-ffmpeg, already installed)

Usage:
  python tools/dub_foreign_broadcast.py --check
  python tools/dub_foreign_broadcast.py --input <video.mp4> --source-lang es --voice newscaster --out <dubbed.mp4>
  python tools/dub_foreign_broadcast.py --input <video.mp4> --source-lang es --transcript-only

Standing rules:
- Alignment-gate the translated script before render (no political/profane carryover)
- Family-mode: filter slurs, violence-glorification, betting talk in commentary
- Preserve original ambient audio (crowd, action sounds) by mixing under
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SYSTEM_TRANSLATION_PROMPT = """You are a broadcast-script translator/adapter for Narrow Highway, a curated
Christian-family content portal.

Input: timestamped transcript of foreign-language sports commentary.
Output: English broadcast script, line-by-line, matching the original timing.

Standing rules:
- KEEP family-safe at all times
- DROP profanity, slurs, gambling/betting talk, alcohol-promo references
- DROP politically-charged side commentary (stay on the sport)
- PRESERVE genuine sportsmanship, technical analysis, and personality from announcers
- KEEP the energy: lucha libre commentary is animated, KBO commentary is precise, AFL is wry
- Use period-appropriate, accessible English (no dated slang, no current-day political loading)
- When the original speaker says something untranslatable or culturally specific,
  paraphrase to the equivalent meaning in the announcing tradition of that sport

Output strict JSON:
{
  "lines": [
    { "start": <float seconds>, "end": <float seconds>, "text": "<English line>" },
    ...
  ]
}

Each line should be 1-3 sentences, matched to the timing of the source line.
Do not output prose outside the JSON.
"""


def has_whisper() -> bool:
    try:
        import faster_whisper  # noqa
        return True
    except ImportError:
        try:
            import whisper  # noqa
            return True
        except ImportError:
            return False


def has_anthropic() -> bool:
    try:
        import anthropic  # noqa
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    except ImportError:
        return False


def has_elevenlabs() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def has_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg")


def transcribe(video_path: Path, lang: str) -> list[dict]:
    """Transcribe video commentary using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
        # Use base model first (faster, decent quality); upgrade to medium/large later
        model = WhisperModel("base", device="auto", compute_type="int8")
        segments, info = model.transcribe(str(video_path), language=lang)
        return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                for s in segments]
    except ImportError:
        print("[err] faster-whisper not installed; pip install faster-whisper")
        return []


def translate_and_adapt(segments: list[dict], source_lang: str) -> list[dict]:
    """Send transcript to Claude for translation + family-safe adaptation."""
    try:
        import anthropic
    except ImportError:
        print("[err] anthropic SDK not installed")
        return []
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[err] ANTHROPIC_API_KEY not set")
        return []
    client = anthropic.Anthropic(api_key=key)
    payload = json.dumps({"source_lang": source_lang, "lines": segments}, ensure_ascii=False)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=SYSTEM_TRANSLATION_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
        text = re.sub(r"\s*```\s*$", "", text.strip())
        blob = json.loads(text)
        return blob.get("lines", [])
    except Exception as e:
        print(f"[err] Claude translation failed: {e}")
        return []


def render_with_elevenlabs(lines: list[dict], voice: str, out_dir: Path) -> Path | None:
    """Render each line as an MP3 via ElevenLabs; concatenate at the right timings."""
    # Defer to render_audio_premium.py's synthesize function
    sys.path.insert(0, str(REPO / "tools"))
    try:
        import render_audio_premium as eleven
    except ImportError as e:
        print(f"[err] couldn't import render_audio_premium: {e}")
        return None
    if not eleven.voice_setup_ok(voice):
        print(f"[err] voice slot {voice} not configured")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    line_mp3s = []
    for i, ln in enumerate(lines):
        p = out_dir / f"line_{i:04d}.mp3"
        if not eleven.synthesize(ln["text"], voice, p):
            print(f"[err] ElevenLabs render failed at line {i}")
            return None
        line_mp3s.append((ln["start"], ln["end"], p))
    return out_dir


def mux_audio_over_video(video_path: Path, audio_dir: Path, lines: list[dict], out_path: Path) -> bool:
    """Use ffmpeg to overlay translated audio at correct timestamps over video,
    mixing original audio underneath (mute on commentary track, keep ambient).

    This is a simplified version — production-quality muxing needs SOX or a DAW.
    For v1 we just overlay the line MP3s sequentially and mix at -8dB original.
    """
    ff = has_ffmpeg()
    if not ff:
        print("[err] ffmpeg unavailable")
        return False
    # Build an ffmpeg concat-with-timestamps filter graph. Complex; for v1
    # we just stitch sequentially with adelay per line.
    inputs = ["-i", str(video_path)]
    filters = []
    mixin_count = 0
    for i, ln in enumerate(lines):
        mp3 = audio_dir / f"line_{i:04d}.mp3"
        if not mp3.exists():
            continue
        inputs.extend(["-i", str(mp3)])
        delay_ms = int(ln["start"] * 1000)
        filters.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        mixin_count += 1
    if mixin_count == 0:
        print("[err] no line audio files found")
        return False
    # Mix: original at -8dB + all line tracks at full
    mix_inputs = ";".join(filters)
    mix_chain = "".join(f"[a{i}]" for i in range(mixin_count))
    filter_complex = (
        f"{mix_inputs};"
        f"[0:a]volume=0.25[orig];"
        f"[orig]{mix_chain}amix=inputs={mixin_count+1}:duration=longest:dropout_transition=0[aout]"
    )
    cmd = [
        ff, "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=3600)
        if proc.returncode != 0:
            print(f"[ffmpeg err] {proc.stderr.decode('utf-8', errors='replace')[-600:]}")
            return False
        return True
    except Exception as e:
        print(f"[err] mux failed: {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--input", help="Path to foreign-language video")
    ap.add_argument("--source-lang", default="es", help="ISO 639-1 code (es, ko, ja, etc.)")
    ap.add_argument("--voice", default="newscaster")
    ap.add_argument("--out", help="Output dubbed MP4")
    ap.add_argument("--transcript-only", action="store_true",
                    help="Stop after Whisper transcription; print transcript")
    ap.add_argument("--translate-only", action="store_true",
                    help="Stop after Claude translation; print English script")
    args = ap.parse_args()

    if args.check:
        print(f"faster-whisper: {'[OK]' if has_whisper() else '[--] pip install faster-whisper'}")
        print(f"anthropic+key:  {'[OK]' if has_anthropic() else '[--] set ANTHROPIC_API_KEY + pip install anthropic'}")
        print(f"elevenlabs key: {'[OK]' if has_elevenlabs() else '[--] set ELEVENLABS_API_KEY'}")
        print(f"ffmpeg:         {'[OK] ' + has_ffmpeg() if has_ffmpeg() else '[--] pip install imageio-ffmpeg'}")
        return 0

    if not args.input or not Path(args.input).exists():
        print("--input <video.mp4> required")
        return 2

    src = Path(args.input)
    print(f"[1/4] Transcribing {src.name} ({args.source_lang}) via Whisper…")
    segments = transcribe(src, args.source_lang)
    if not segments:
        return 1
    print(f"  {len(segments)} segments transcribed")
    if args.transcript_only:
        print(json.dumps(segments, indent=2, ensure_ascii=False))
        return 0

    print(f"[2/4] Translating + adapting via Claude…")
    lines = translate_and_adapt(segments, args.source_lang)
    if not lines:
        return 1
    print(f"  {len(lines)} English lines produced")
    if args.translate_only:
        print(json.dumps(lines, indent=2, ensure_ascii=False))
        return 0

    if not args.out:
        print("--out required for full pipeline")
        return 2

    print(f"[3/4] Rendering English audio via ElevenLabs…")
    work_dir = Path(args.out).with_suffix(".linework")
    audio_dir = render_with_elevenlabs(lines, args.voice, work_dir)
    if not audio_dir:
        return 1

    print(f"[4/4] Muxing into {args.out}…")
    if not mux_audio_over_video(src, audio_dir, lines, Path(args.out)):
        return 1
    print(f"\n[done] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
