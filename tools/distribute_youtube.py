"""YouTube upload scaffold.

Per [distribution memo](project_distribution_1000_true_fans_2026-05-16.md), every
YouTube upload carries:
  - title with category-appropriate prefix
  - description with deep-link back to a narrowhighway.com deck card
  - tags optimized for Christian-family discovery
  - branded thumbnail (from render_art.py output)
  - end-screen / outro pointing to our channel + a related video

Pre-req:
  - YouTube Data API v3 access (free quota, 10k units/day default)
  - Google OAuth credentials → tokens.json
  - pip install google-auth google-auth-oauthlib google-api-python-client

OAuth setup steps (one-time):
  1. https://console.cloud.google.com/ — create project "narrowhighway"
  2. Enable "YouTube Data API v3"
  3. Create OAuth 2.0 Desktop credentials → client_secrets.json (download)
  4. Place at: ~/.narrowhighway/client_secrets.json
  5. First run will open browser; sign in with the YouTube channel's Google account
  6. tokens.json gets cached for re-use

Quotas:
  - Each upload costs ~1600 quota units (default 10k/day = ~6 uploads/day)
  - For higher volume, request quota increase (free) at Google Cloud Console

Usage:
  python tools/distribute_youtube.py --check
  python tools/distribute_youtube.py --upload <video.mp4> --title "Daily Devotion — May 16" --deck daily
  python tools/distribute_youtube.py --batch site/upload_queue.json
  python tools/distribute_youtube.py --schedule daily-devotions  # uploads today's pending devotion video
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CRED_DIR = Path.home() / ".narrowhighway"
CRED_DIR.mkdir(parents=True, exist_ok=True)
CLIENT_SECRETS = CRED_DIR / "client_secrets.json"
TOKENS = CRED_DIR / "tokens.json"

CHANNEL_TAGS_BASE = [
    "christian", "christian family", "devotional", "hymn", "scripture", "bible",
    "narrow highway", "family safe", "public domain", "classic",
]

DESCRIPTION_OUTRO = """

—

Narrow Highway is a curated internet for Christian families. A daily anchor of devotion, hymn, scripture, and almanac wisdom — all family-safe, all free, all ad-free.

More at https://narrowhighway.com

Today's deck: {deck_url}

(no paid ads anywhere · 1000 true fans, not a million casual ones)
"""

DECK_URLS = {
    "daily": "https://narrowhighway.com/daily.html",
    "hymn": "https://narrowhighway.com/hymns.html",
    "almanac": "https://narrowhighway.com/almanac.html",
    "tv": "https://narrowhighway.com/watch.html",
    "radio": "https://narrowhighway.com/radio.html",
    "kids": "https://narrowhighway.com/kids.html",
    "codex": "https://narrowhighway.com/canon.html",
    "schedule": "https://narrowhighway.com/schedule.html",
}


def have_creds() -> bool:
    return CLIENT_SECRETS.exists()


def have_tokens() -> bool:
    return TOKENS.exists()


def try_import():
    try:
        from googleapiclient.discovery import build  # noqa: F401
        from googleapiclient.http import MediaFileUpload  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        return True, None
    except ImportError as e:
        return False, str(e)


def get_youtube_service():
    """Authenticate via OAuth and return the YouTube Data API service."""
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube"]
    creds = None
    if TOKENS.exists():
        creds = Credentials.from_authorized_user_file(str(TOKENS), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKENS.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video_path: Path, title: str, description: str, tags: list[str],
           privacy: str = "private", thumbnail_path: Path | None = None) -> dict | None:
    """Upload a video. Returns the YouTube response dict on success."""
    from googleapiclient.http import MediaFileUpload
    youtube = get_youtube_service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": (tags + CHANNEL_TAGS_BASE)[:30],
            "categoryId": "22",  # People & Blogs (broad fit; "Education" = 27, "Music" = 10)
        },
        "status": {
            "privacyStatus": privacy,  # 'private' (default), 'unlisted', 'public'
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
            "publicStatsViewable": True,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/*")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    print(f"[uploading] {video_path.name} → '{title}'…")
    while response is None:
        status, response = req.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  {pct}%")
    video_id = response.get("id")
    print(f"[uploaded] id={video_id}  https://youtu.be/{video_id}")

    if thumbnail_path and thumbnail_path.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=str(thumbnail_path)).execute()
            print(f"[thumbnail set]")
        except Exception as e:
            print(f"[thumb skip] {e}")

    return response


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--upload", help="Path to MP4 to upload")
    ap.add_argument("--title", help="Video title")
    ap.add_argument("--description", help="Override default description")
    ap.add_argument("--deck", choices=list(DECK_URLS.keys()), default="daily",
                    help="Deck the video belongs to (governs the outro link)")
    ap.add_argument("--thumbnail", help="Path to thumbnail PNG/JPG (optional)")
    ap.add_argument("--privacy", choices=["private","unlisted","public"], default="private",
                    help="Upload privacy; default 'private' so operator can review before going public")
    ap.add_argument("--tags", nargs="*", default=[])
    args = ap.parse_args()

    if args.check:
        ok, err = try_import()
        print(f"google-api-python-client: {'OK' if ok else 'NOT INSTALLED — pip install google-api-python-client google-auth google-auth-oauthlib'}")
        print(f"client_secrets.json:      {'OK at ' + str(CLIENT_SECRETS) if have_creds() else 'NOT FOUND at ' + str(CLIENT_SECRETS)}")
        print(f"tokens.json:              {'OK (cached OAuth)' if have_tokens() else 'WILL CREATE on first upload'}")
        return 0

    if not args.upload:
        ap.print_help()
        return 0

    video = Path(args.upload)
    if not video.exists():
        print(f"[err] {video} not found")
        return 1
    if not args.title:
        print("[err] --title required")
        return 2
    deck_url = DECK_URLS.get(args.deck, DECK_URLS["daily"])
    desc = args.description or ""
    full_desc = desc + DESCRIPTION_OUTRO.format(deck_url=deck_url)

    ok, err = try_import()
    if not ok:
        print(f"[skip] {err}")
        return 1
    if not have_creds():
        print(f"[skip] place OAuth client_secrets.json at {CLIENT_SECRETS}")
        return 1

    thumb = Path(args.thumbnail) if args.thumbnail else None
    response = upload(video, args.title, full_desc, args.tags,
                      privacy=args.privacy, thumbnail_path=thumb)
    return 0 if response else 1


if __name__ == "__main__":
    sys.exit(main())
