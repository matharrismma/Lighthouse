"""Whisper-transcribe pilot source audio with word-level timestamps.

Output:
  D:/library_files/_pilots/<name>/transcript.json   — segments + word-level timings
  D:/library_files/_pilots/<name>/transcript.srt    — burnable subtitle track
  D:/library_files/_pilots/<name>/transcript.txt    — plain text for reference

Reusable across pilots: pass --audio <path> --out-dir <dir>.

Used downstream for:
  - YouTube auto-subtitle upload (.srt)
  - Adobe Animate lip-sync (word-level JSON timing)
  - Scene cut refinement (cut on natural speech beats, not arbitrary timestamps)
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from datetime import timedelta


def fmt_srt_ts(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(audio_path: Path, out_dir: Path, model_size: str = "base.en"):
    from faster_whisper import WhisperModel
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print(f"Transcribing: {audio_path.name}")
    segments_iter, info = model.transcribe(
        str(audio_path),
        language="en",
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
    )
    print(f"  Detected language: {info.language} (prob {info.language_probability:.2f})")
    print(f"  Duration: {info.duration:.1f}s")
    segments = []
    srt_lines = []
    txt_lines = []
    n = 0
    for seg in segments_iter:
        n += 1
        words = []
        for w in seg.words or []:
            words.append({"start": w.start, "end": w.end, "word": w.word.strip()})
        segments.append({
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": words,
        })
        srt_lines.append(f"{n}\n{fmt_srt_ts(seg.start)} --> {fmt_srt_ts(seg.end)}\n{seg.text.strip()}\n")
        txt_lines.append(seg.text.strip())
        if n % 20 == 0:
            print(f"  ... segment {n} @ {seg.start:.1f}s")
    print(f"Total segments: {n}")
    (out_dir / "transcript.json").write_text(
        json.dumps({"language": info.language, "duration": info.duration, "segments": segments}, indent=2),
        encoding="utf-8")
    (out_dir / "transcript.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (out_dir / "transcript.txt").write_text("\n".join(txt_lines), encoding="utf-8")
    print(f"Wrote {out_dir}/transcript.json/.srt/.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="base.en", help="tiny.en / base.en / small.en / medium.en / large-v3")
    args = ap.parse_args()
    transcribe(Path(args.audio), Path(args.out_dir), args.model)


if __name__ == "__main__":
    main()
