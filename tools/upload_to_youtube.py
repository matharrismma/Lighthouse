"""Upload publish-package pilots to YouTube via the Data API.

Reads from data/publish/<pilot>/ (created by build_publish_package.py):
  - video.mp4
  - title.txt
  - description.txt
  - tags.txt
  - thumbnail_youtube.png

On success, writes the video URL into site/youtube.json so the homepage
auto-swaps from local playback to YouTube embed.

One-time setup (you do this once at Google Cloud Console):
  1. Visit https://console.cloud.google.com
  2. Create a project (e.g. "narrowhighway-distribution")
  3. APIs & Services → Library → enable "YouTube Data API v3"
  4. APIs & Services → OAuth consent screen:
       - User Type: External
       - App name: Narrow Highway
       - User support email: your email
       - Scopes: add ./auth/youtube.upload
       - Test users: add your YouTube channel's email
       - Save
  5. APIs & Services → Credentials → Create credentials → OAuth client ID:
       - Application type: Desktop app
       - Name: narrowhighway-uploader
       - Download the JSON → save it as:
           C:/Users/hdven/.config/narrowhighway/client_secrets.json
       - (Or any path — pass --secrets <path> to the script)

First-run behavior:
  - A browser opens automatically
  - Sign in with the Google account that OWNS your YouTube channel
  - Approve the "youtube.upload" scope
  - Token is cached locally → subsequent runs are automatic

Usage:
  python tools/upload_to_youtube.py --pilot soft_rains_v4
  python tools/upload_to_youtube.py --pilot hundred_acre
  python tools/upload_to_youtube.py --pilot soft_rains_v4 --secrets C:/path/client_secrets.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_SECRETS = Path.home() / ".config" / "narrowhighway" / "client_secrets.json"
DEFAULT_TOKEN   = Path.home() / ".config" / "narrowhighway" / "youtube_token.json"
REPO = Path(__file__).resolve().parent.parent


def authenticate(secrets_path: Path, token_path: Path):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets_path.exists():
                print(f"ERROR: client_secrets.json not found at {secrets_path}")
                print("See top-of-file instructions to set this up.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"Saved auth token to {token_path}")
    return creds


def upload(youtube, video: Path, title: str, description: str, tags: list[str],
           thumbnail: Path | None = None, privacy: str = "public"):
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {
            "title": title[:100],   # YouTube limit
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "24",  # Entertainment (use 22 People & Blogs for podcasts, 27 Education, 24 Entertainment, 1 Film & Animation)
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,    # "public" | "unlisted" | "private"
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    print(f"Uploading {video.name} ({video.stat().st_size // 1024 // 1024} MB) as {privacy}...")
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  uploaded {pct}%")
    vid = response.get("id")
    print(f"Uploaded — video ID: {vid}")
    print(f"URL: https://www.youtube.com/watch?v={vid}")
    if thumbnail and thumbnail.exists():
        # YouTube thumbnail size limit is 2 MB. Compress if needed.
        thumb_for_upload = thumbnail
        if thumbnail.stat().st_size > 1_900_000:
            from PIL import Image
            print(f"Compressing thumbnail ({thumbnail.stat().st_size//1024} KB) to fit YouTube 2MB cap...")
            compressed = thumbnail.with_name(thumbnail.stem + "_compressed.jpg")
            img = Image.open(thumbnail).convert("RGB")
            for q in (90, 85, 80, 75, 70, 65):
                img.save(compressed, format="JPEG", quality=q, optimize=True)
                if compressed.stat().st_size <= 1_900_000:
                    print(f"  -> {compressed.stat().st_size//1024} KB at q={q}")
                    thumb_for_upload = compressed
                    break
        try:
            print(f"Setting thumbnail...")
            media_thumb = MediaFileUpload(str(thumb_for_upload),
                                          mimetype="image/jpeg" if thumb_for_upload.suffix == ".jpg" else "image/png")
            youtube.thumbnails().set(videoId=vid, media_body=media_thumb).execute()
            print(f"Thumbnail set.")
        except Exception as e:
            print(f"  Thumbnail upload failed (non-fatal): {e}")
            print(f"  You can set it manually at https://studio.youtube.com/video/{vid}/edit")
    return vid


def update_youtube_json(pilot: str, video_id: str):
    """Update site/youtube.json with the new video ID so homepage auto-swaps."""
    yt_path = REPO / "site" / "youtube.json"
    data = {}
    if yt_path.exists():
        try:
            data = json.loads(yt_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    key = {"soft_rains_v4": "soft_rains", "hundred_acre": "pooh"}.get(pilot, pilot)
    data[key] = video_id
    yt_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Updated {yt_path}: {key} = {video_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True, help="e.g. soft_rains_v4 or hundred_acre")
    ap.add_argument("--secrets", default=str(DEFAULT_SECRETS))
    ap.add_argument("--token", default=str(DEFAULT_TOKEN))
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    args = ap.parse_args()

    pkg = REPO / "data" / "publish" / args.pilot
    if not pkg.exists():
        print(f"ERROR: publish package not found at {pkg}")
        print(f"Run: python tools/build_publish_package.py --pilot {args.pilot}")
        sys.exit(1)

    video = pkg / "video.mp4"
    title = (pkg / "title.txt").read_text(encoding="utf-8").strip()
    description = (pkg / "description.txt").read_text(encoding="utf-8").strip()
    tags = [t.strip() for t in (pkg / "tags.txt").read_text(encoding="utf-8").split(",") if t.strip()]
    thumbnail = pkg / "thumbnail_youtube.png"

    print(f"=== Uploading {args.pilot} to YouTube ===")
    print(f"Title:  {title}")
    print(f"Tags:   {', '.join(tags[:6])}{'...' if len(tags) > 6 else ''}")
    print(f"Video:  {video} ({video.stat().st_size // 1024 // 1024} MB)")
    print()

    creds = authenticate(Path(args.secrets), Path(args.token))
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=creds)
    vid = upload(youtube, video, title, description, tags, thumbnail, args.privacy)
    update_youtube_json(args.pilot, vid)
    print()
    print("Done. Homepage will auto-show YouTube embed on next page load.")


if __name__ == "__main__":
    main()
