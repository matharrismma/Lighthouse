"""Upload publish-package pilots to Internet Archive.

Internet Archive is the natural permanent home for PD-derived content:
  - free hosting forever
  - automatic streaming via their HLS pipeline
  - guaranteed-preservation backup
  - returns a permalink we can reference from the site

Setup (one-time, ~3 min):
  1. Sign up at https://archive.org/account/signup (or sign in)
  2. Visit https://archive.org/account/s3.php
  3. Copy your Access Key + Secret Key
  4. Add to .env:
       IA_ACCESS_KEY=...
       IA_SECRET_KEY=...

Usage:
  python tools/upload_to_archive_org.py --pilot soft_rains_v4
  python tools/upload_to_archive_org.py --pilot hundred_acre

The identifier becomes `narrowhighway-<pilot>` (e.g. `narrowhighway-soft_rains_v4`).
Permalink: https://archive.org/details/narrowhighway-soft_rains_v4
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from dotenv import load_dotenv
import os

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

ACCESS_KEY = os.environ.get("IA_ACCESS_KEY", "").strip()
SECRET_KEY = os.environ.get("IA_SECRET_KEY", "").strip()


def check_setup():
    missing = []
    if not ACCESS_KEY: missing.append("IA_ACCESS_KEY")
    if not SECRET_KEY: missing.append("IA_SECRET_KEY")
    if missing:
        print("Internet Archive setup required.")
        print("Missing env vars: " + ", ".join(missing))
        print()
        print("Setup steps:")
        print("  1. Sign up / log in: https://archive.org/account/signup")
        print("  2. Get keys: https://archive.org/account/s3.php")
        print("  3. Add to .env:")
        print("       IA_ACCESS_KEY=<your access key>")
        print("       IA_SECRET_KEY=<your secret key>")
        sys.exit(1)


def upload(pilot: str):
    pkg = REPO / "data" / "publish" / pilot
    if not pkg.exists():
        print(f"Publish package not found: {pkg}")
        sys.exit(1)

    video = pkg / "video.mp4"
    thumbnail = pkg / "thumbnail_youtube.png"
    audio = pkg / "audio_podcast.mp3"
    title = (pkg / "title.txt").read_text(encoding="utf-8").strip()
    description = (pkg / "description.txt").read_text(encoding="utf-8").strip()
    tags = [t.strip() for t in (pkg / "tags.txt").read_text(encoding="utf-8").split(",") if t.strip()]

    identifier = f"narrowhighway-{pilot.replace('_', '-')}"
    print(f"Uploading to Internet Archive as: {identifier}")
    print(f"Permalink will be: https://archive.org/details/{identifier}")
    print()

    try:
        from internetarchive import upload as ia_upload, configure
    except ImportError:
        print("ERROR: internetarchive package not installed. Run:")
        print("  pip install internetarchive")
        sys.exit(1)

    # Configure auth via env vars
    os.environ["IA_S3_ACCESS_KEY"] = ACCESS_KEY
    os.environ["IA_S3_SECRET_KEY"] = SECRET_KEY

    md = {
        "title": title,
        "description": description.replace("\n", "<br/>"),
        "creator": "Matt Harris · Narrow Highway",
        "subject": "; ".join(tags),
        "mediatype": "movies",
        "collection": "opensource_movies",
        "language": "eng",
        "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
        "rights": "Source audio (X Minus One 1956 / LibriVox) is public domain. New animation © Matt Harris 2026, released under CC BY 4.0.",
    }

    files = [str(video)]
    if thumbnail.exists():
        files.append(str(thumbnail))
    if audio.exists():
        files.append(str(audio))

    print("Uploading files:")
    for f in files:
        print(f"  - {f} ({Path(f).stat().st_size // 1024 // 1024} MB)")
    print()

    response = ia_upload(
        identifier,
        files=files,
        metadata=md,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        retries=3,
        retries_sleep=10,
        verbose=True,
    )
    print()
    for r in response:
        print(f"  {r.status_code}: {r.url if hasattr(r,'url') else r}")
    print()
    permalink = f"https://archive.org/details/{identifier}"
    print(f"DONE. Permalink: {permalink}")
    return permalink


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True)
    args = ap.parse_args()
    check_setup()
    permalink = upload(args.pilot)
    # Save permalink for later reference
    out = REPO / "data" / "publish" / args.pilot / "archive_org_permalink.txt"
    out.write_text(permalink, encoding="utf-8")
    print(f"Saved permalink to {out}")


if __name__ == "__main__":
    main()
