"""Single-scene assembly test — validates the ffmpeg pipeline before pilot orchestration.

Takes:
  - scifi_01_automated_house_dawn.png (hero frame)
  - First 60 sec of source X Minus One Soft Rains MP3
  - Slow ken-burns push-in via ffmpeg
  - Outputs a 60-sec MP4 with synced audio

If this works end-to-end, we know the assembly pipeline is solid and the full
pilot orchestrator just iterates this loop across the 22 scenes.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
REPO = Path(__file__).resolve().parent.parent

SOURCE_AUDIO = Path("D:/library_files/x_minus_one/XMinusOne56-12-05078ThereWillComeSoftRains-ZeroHour.mp3")
HERO_FRAME = Path("D:/library_files/_hero_frames/scifi_01_automated_house_dawn.png")
OUT = Path("D:/library_files/_pilots/_tests")
OUT.mkdir(parents=True, exist_ok=True)
OUTPUT = OUT / "test_scene_01_assembly.mp4"

SCENE_DURATION_SEC = 60
FPS = 30
WIDTH = 1920
HEIGHT = 1080


def ken_burns_filter(duration_sec: int, fps: int = 30,
                     start_zoom: float = 1.0, end_zoom: float = 1.10,
                     start_x: float = 0.5, start_y: float = 0.5,
                     end_x: float = 0.5, end_y: float = 0.5):
    """
    Build a zoompan filter for a slow Ken Burns push-in.
    Zooms from start_zoom to end_zoom over duration_sec at fps.
    Centered crop by default.

    zoompan in ffmpeg works on stills by treating the image as a 1-frame loop.
    We expand it to (duration*fps) frames using d=, then drive z, x, y as expressions.
    """
    total_frames = duration_sec * fps
    # 'on' is the current output frame index (0..total_frames-1)
    z_expr = f"min({start_zoom}+({end_zoom}-{start_zoom})*on/{total_frames-1},{end_zoom})"
    # x, y are TOP-LEFT corner of the crop window in input pixel coords
    # iw/ih are input width/height; the zoompan output is fixed size s=WIDTHxHEIGHT
    # To keep cropping centered on (start_x*iw, start_y*ih) drifting to (end_x*iw, end_y*ih):
    x_expr = (
        f"iw*({start_x}+({end_x}-{start_x})*on/{total_frames-1}) - iw/zoom/2"
    )
    y_expr = (
        f"ih*({start_y}+({end_y}-{start_y})*on/{total_frames-1}) - ih/zoom/2"
    )
    return (
        f"zoompan="
        f"z='{z_expr}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={total_frames}:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={fps}"
    )


def main():
    assert SOURCE_AUDIO.exists(), f"Missing source audio: {SOURCE_AUDIO}"
    assert HERO_FRAME.exists(), f"Missing hero frame: {HERO_FRAME}"

    print(f"Source audio: {SOURCE_AUDIO.name}  ({SOURCE_AUDIO.stat().st_size//1024} KB)")
    print(f"Hero frame:   {HERO_FRAME.name}  ({HERO_FRAME.stat().st_size//1024} KB)")
    print(f"Output:       {OUTPUT}")
    print()

    kb = ken_burns_filter(SCENE_DURATION_SEC, FPS, start_zoom=1.0, end_zoom=1.08)

    cmd = [
        FF, "-y",
        "-loop", "1", "-i", str(HERO_FRAME),
        "-ss", "0", "-t", str(SCENE_DURATION_SEC), "-i", str(SOURCE_AUDIO),
        "-filter_complex", f"[0:v]{kb}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-shortest",
        "-movflags", "+faststart",
        str(OUTPUT),
    ]

    print("Running ffmpeg...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAILED:")
        print(r.stderr[-3000:])
        raise SystemExit(1)
    print(f"OK — wrote {OUTPUT.stat().st_size//1024} KB MP4")
    print()
    # Probe the output to confirm
    p = subprocess.run([FF, "-hide_banner", "-i", str(OUTPUT)], capture_output=True, text=True)
    for line in p.stderr.splitlines():
        if any(k in line for k in ("Duration", "Stream", "Video", "Audio")):
            print("  ", line.strip())


if __name__ == "__main__":
    main()
