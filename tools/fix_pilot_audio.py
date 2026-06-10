"""Re-mux pilot finals with stereo AAC audio for universal browser compatibility.

Some browsers (older Chromebook builds, some Safari versions) fail to decode
mono AAC streams in MP4 containers. Standard fix: upmix to stereo, normalize
loudness toward streaming targets, set proper movflags + channel layout headers.

Video is stream-copied (no re-encode) — fast.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import imageio_ffmpeg
import shutil

FF = imageio_ffmpeg.get_ffmpeg_exe()

PILOTS = [
    Path("D:/library_files/_pilots/soft_rains/final.mp4"),
    Path("D:/library_files/_pilots/hundred_acre/final.mp4"),
]


def remux_stereo(src: Path):
    if not src.exists():
        print(f"[MISS] {src}")
        return
    backup = src.with_name(src.stem + ".mono-backup.mp4")
    tmp = src.with_name(src.stem + ".stereo.tmp.mp4")
    print(f"[FIX] {src.name}  ({src.stat().st_size//1024//1024} MB mono)")
    # Backup original (idempotent)
    if not backup.exists():
        shutil.copy2(src, backup)
        print(f"  backup -> {backup.name}")
    # Re-encode audio to stereo at 192 kb/s. Loudnorm helps streaming.
    cmd = [
        FF, "-y", "-i", str(backup),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
        "-af", "pan=stereo|c0=c0|c1=c0,loudnorm=I=-16:LRA=11:TP=-1.5",
        "-movflags", "+faststart",
        str(tmp),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAIL: {r.stderr[-800:]}")
        return
    # Replace original
    src.unlink()
    tmp.rename(src)
    new_mb = src.stat().st_size // 1024 // 1024
    print(f"  OK  -> {new_mb} MB stereo, faststart, loudnorm -16 LUFS")


def main():
    for p in PILOTS:
        remux_stereo(p)


if __name__ == "__main__":
    main()
