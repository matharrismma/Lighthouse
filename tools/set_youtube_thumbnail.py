"""Set/update the thumbnail for an already-uploaded YouTube video.

Use this if the initial upload failed at thumbnail step (e.g. file too big)
or to refresh the thumbnail on an existing video.

Usage:
  python tools/set_youtube_thumbnail.py --video-id vM-lMRTUddA --thumbnail data/publish/soft_rains_v4/thumbnail_youtube.png
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_TOKEN = Path.home() / ".config" / "narrowhighway" / "youtube_token.json"
REPO = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--thumbnail", required=True)
    ap.add_argument("--token", default=str(DEFAULT_TOKEN))
    ap.add_argument("--secrets", default=None,
                    help="Path to client_secrets.json (only needed if token doesn't exist yet)")
    args = ap.parse_args()

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from PIL import Image

    token_path = Path(args.token)
    if not token_path.exists():
        if not args.secrets:
            print(f"ERROR: token not found at {token_path}. Provide --secrets to do first-time auth.")
            sys.exit(1)
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(args.secrets, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    else:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")

    thumb = Path(args.thumbnail)
    if thumb.stat().st_size > 1_900_000:
        print(f"Compressing thumbnail {thumb.stat().st_size//1024} KB -> JPEG under 2MB...")
        compressed = thumb.with_name(thumb.stem + "_compressed.jpg")
        img = Image.open(thumb).convert("RGB")
        for q in (90, 85, 80, 75, 70, 65, 60):
            img.save(compressed, format="JPEG", quality=q, optimize=True)
            if compressed.stat().st_size <= 1_900_000:
                print(f"  -> {compressed.stat().st_size//1024} KB at q={q}")
                thumb = compressed
                break

    youtube = build("youtube", "v3", credentials=creds)
    print(f"Setting thumbnail for {args.video_id}...")
    media = MediaFileUpload(str(thumb),
                            mimetype="image/jpeg" if thumb.suffix == ".jpg" else "image/png")
    youtube.thumbnails().set(videoId=args.video_id, media_body=media).execute()
    print(f"OK. View at https://www.youtube.com/watch?v={args.video_id}")


if __name__ == "__main__":
    main()
