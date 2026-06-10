"""Re-broadcast a FAST channel's HLS day.m3u8 to YouTube Live as a 24/7 stream.

YouTube Live accepts RTMP. We point ffmpeg at our day.m3u8 (or directly at the
ordered .ts segments) and push the result to YouTube's primary ingest endpoint.

Key behaviors:
  - `-re` flag tells ffmpeg to read input at native rate (not as-fast-as-possible),
    matching a real broadcast clock.
  - `-stream_loop -1` loops the input forever, so when the day ends we restart it.
  - When stream-copying, codec params are passed straight through. If YouTube
    complains about input, we can re-encode by passing --reencode.

Usage:
  # Set env var first:
  set YT_STREAM_KEY=xxxx-xxxx-xxxx-xxxx

  python tools/fast_channel_youtube_live.py --channel nh-scifi-theatre

The stream key never appears in logs or git — it's read from $YT_STREAM_KEY.
Each channel gets its own env var: YT_STREAM_KEY_<CH> overrides $YT_STREAM_KEY
for that channel specifically.

Background mode:
  Pass --supervise to run in a loop with auto-restart on ffmpeg crash.
  Logs to data/live/<channel_id>.log.
"""
from __future__ import annotations
import argparse, os, sys, time, subprocess, signal
from pathlib import Path
import imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
YOUTUBE_INGEST = "rtmp://a.rtmp.youtube.com/live2"


def _load_dotenv() -> None:
    """Load KEY=value pairs from the repo .env into os.environ.

    Lets YT_STREAM_KEY live in .env (gitignored) alongside the other
    secrets, instead of having to be exported in every shell. Existing
    env vars win — .env only fills gaps."""
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and name not in os.environ:
                os.environ[name] = value
    except Exception:
        pass


def get_stream_key(channel_id: str) -> str:
    """Read stream key from env (or repo .env). Per-channel override beats the generic one."""
    _load_dotenv()
    per_channel_var = f"YT_STREAM_KEY_{channel_id.upper().replace('-', '_')}"
    key = os.environ.get(per_channel_var) or os.environ.get("YT_STREAM_KEY")
    if not key:
        raise RuntimeError(
            f"No YouTube stream key. Add YT_STREAM_KEY=... to {REPO / '.env'} "
            f"or set the {per_channel_var} / YT_STREAM_KEY environment variable."
        )
    return key


def build_ffmpeg_cmd(source: Path, stream_key: str, reencode: bool = False,
                     concat: bool = False) -> list[str]:
    """Build the ffmpeg command for RTMP push.

    `source` is either an HLS day.m3u8 playlist, or — when concat=True — a
    concat-demuxer list (one `file '...'` line per encoded cache MP4). The
    concat path lets the channel stream straight from the encoded cache with
    no multi-GB HLS day baked to disk first: ffmpeg loops the list, re-encodes
    to YouTube's CBR spec, and pushes. Re-encode is forced for concat input."""
    cmd = [
        FF, "-hide_banner",
        "-re",                # native-rate read
        "-stream_loop", "-1", # loop forever
    ]
    if concat:
        cmd += ["-f", "concat", "-safe", "0"]
    cmd += ["-i", str(source)]
    if reencode:
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            # 720p keeps a 24/7 live encode light enough for an 8 GB box.
            # Fine quality for a FAST channel; bump to 1080p once the stream
            # moves to the workshop machine.
            "-s", "1280x720",
            # True CBR. libx264 only holds a steady bitrate — padding static
            # content (bumpers, scripture cards) with filler — when HRD-CBR
            # is enabled. Without nal-hrd=cbr the encoder undershoots hard on
            # low-motion content and trips YouTube's "bitrate too low" warning.
            "-b:v", "3000k", "-maxrate", "3000k", "-bufsize", "3000k",
            "-x264-params", "nal-hrd=cbr",
            # keyframe every 60 frames = 2 s at 30 fps. YouTube requires the
            # keyframe interval to be <= 4 s; sc_threshold 0 makes it exact.
            "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        ]
    else:
        cmd += ["-c", "copy"]
    cmd += [
        "-f", "flv",
        f"{YOUTUBE_INGEST}/{stream_key}",
    ]
    return cmd


def run_once(cmd: list[str], log_path: Path) -> int:
    """Run a single ffmpeg push session, logging to log_path. Returns exit code."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting ffmpeg push\n",
                        encoding="utf-8")
    # Redact the stream key in echoed cmd
    safe_cmd = list(cmd)
    for i, a in enumerate(safe_cmd):
        if YOUTUBE_INGEST in a:
            base, _, _ = a.rpartition("/")
            safe_cmd[i] = f"{base}/<REDACTED>"
    with log_path.open("a", encoding="utf-8") as logf:
        logf.write(f"cmd: {' '.join(safe_cmd)}\n\n")
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGINT)
            proc.wait()
        return proc.returncode


def supervise(channel_id: str, source: Path, reencode: bool, concat: bool = False):
    """Auto-restart loop. ffmpeg crashes are common over multi-hour pushes."""
    stream_key = get_stream_key(channel_id)
    log_path = REPO / "data" / "live" / f"{channel_id}.log"
    restarts = 0
    while True:
        cmd = build_ffmpeg_cmd(source, stream_key, reencode=reencode, concat=concat)
        print(f"[{time.strftime('%H:%M:%S')}] Starting push for {channel_id} (restart #{restarts})")
        rc = run_once(cmd, log_path)
        print(f"[{time.strftime('%H:%M:%S')}] ffmpeg exited rc={rc}")
        if rc == 0:
            print("  Clean exit — stopping supervisor.")
            return
        restarts += 1
        wait = min(60, 5 + restarts * 5)
        print(f"  Restarting in {wait}s...")
        time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="channel id (e.g. nh-scifi-theatre)")
    ap.add_argument("--reencode", action="store_true",
                    help="Re-encode instead of stream-copy (slower but more compatible)")
    ap.add_argument("--supervise", action="store_true",
                    help="Run in auto-restart loop")
    ap.add_argument("--concat", default=None,
                    help="Stream straight from a concat list of encoded cache "
                         "MP4s instead of an HLS day.m3u8 (forces --reencode).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the ffmpeg cmd (with redacted key) and exit")
    args = ap.parse_args()

    concat = bool(args.concat)
    if concat:
        source = Path(args.concat)
        args.reencode = True  # concat input must be normalised for YouTube
        if not source.exists():
            print(f"[FATAL] No concat list at {source}")
            sys.exit(1)
    else:
        source = REPO / "site" / "channels" / args.channel / "hls" / "day.m3u8"
        if not source.exists():
            print(f"[FATAL] No playlist at {source}")
            print("        Run tools/fast_channel_hls.py first to build the day.")
            sys.exit(1)

    if args.dry_run:
        cmd = build_ffmpeg_cmd(source, "<STREAM_KEY>", reencode=args.reencode, concat=concat)
        print(" ".join(cmd))
        return

    if args.supervise:
        supervise(args.channel, source, args.reencode, concat)
    else:
        stream_key = get_stream_key(args.channel)
        cmd = build_ffmpeg_cmd(source, stream_key, reencode=args.reencode, concat=concat)
        log_path = REPO / "data" / "live" / f"{args.channel}.log"
        rc = run_once(cmd, log_path)
        sys.exit(rc)


if __name__ == "__main__":
    main()
