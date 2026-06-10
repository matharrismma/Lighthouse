"""Upload the pilot MP4s + their hero-frame posters to Cloudflare R2.

Reads credentials from .env:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET
  R2_PUBLIC_URL   (e.g. https://pub-xxxx.r2.dev OR https://cdn.narrowhighway.com)

Uploads each file to a stable key (pilots/<name>/final.mp4, posters/<name>.png).
Idempotent — uses ETag check to skip files already present and unchanged.

Output: prints the public URL for each uploaded asset. These URLs go into
site/index.html (and any other consumer) replacing the /media/_pilots/* paths.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import sys
import mimetypes

from dotenv import load_dotenv
import os

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "").strip()
ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
BUCKET     = os.environ.get("R2_BUCKET", "").strip()
PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")

UPLOADS = [
    # (local path, R2 key, label)
    (Path("D:/library_files/_pilots/soft_rains/final.mp4"),
     "pilots/soft_rains/final.mp4",
     "Soft Rains pilot"),
    (Path("D:/library_files/_pilots/hundred_acre/final.mp4"),
     "pilots/hundred_acre/final.mp4",
     "Hundred Acre pilot"),
    (Path("D:/library_files/_hero_frames/scifi_01_automated_house_dawn.png"),
     "posters/scifi_01_automated_house_dawn.png",
     "Soft Rains poster"),
    (Path("D:/library_files/_hero_frames/pooh_02_treetop_bee.png"),
     "posters/pooh_02_treetop_bee.png",
     "Pooh poster"),
]


def check_creds():
    missing = []
    for name in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                 "R2_BUCKET", "R2_PUBLIC_URL"]:
        if not os.environ.get(name):
            missing.append(name)
    if missing:
        print("Missing required env vars in .env:")
        for m in missing:
            print(f"  {m}")
        print()
        print("See tools/upload_pilots_r2.py docstring for setup steps.")
        sys.exit(1)


def md5_etag(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    check_creds()
    import boto3
    from botocore.client import Config

    endpoint = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    print(f"Endpoint: {endpoint}")
    print(f"Bucket:   {BUCKET}")
    print(f"Public:   {PUBLIC_URL}")
    print()

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    results = []
    for local, key, label in UPLOADS:
        if not local.exists():
            print(f"  [MISS] {label}: source missing at {local}")
            continue
        size_mb = local.stat().st_size / 1024 / 1024
        # Skip if already uploaded with same ETag (single-part upload only — multipart has different etag scheme)
        try:
            head = s3.head_object(Bucket=BUCKET, Key=key)
            remote_etag = head["ETag"].strip('"')
            if "-" not in remote_etag:
                local_etag = md5_etag(local)
                if local_etag == remote_etag:
                    public = f"{PUBLIC_URL}/{key}"
                    print(f"  [SKIP] {label}: already uploaded ({size_mb:.1f} MB)")
                    print(f"         {public}")
                    results.append((label, key, public, size_mb, "skip"))
                    continue
        except Exception:
            pass  # not present, proceed to upload

        ct, _ = mimetypes.guess_type(local.name)
        if not ct:
            ct = "application/octet-stream"
        # Cache for a year (we can bust by changing the key path / filename later)
        extra = {"ContentType": ct, "CacheControl": "public, max-age=31536000"}
        print(f"  [UP  ] {label}: {size_mb:.1f} MB -> {key}")
        s3.upload_file(str(local), BUCKET, key, ExtraArgs=extra)
        public = f"{PUBLIC_URL}/{key}"
        print(f"         {public}")
        results.append((label, key, public, size_mb, "uploaded"))

    print()
    # Write cdn-assets.json so the site automatically picks up the CDN URLs.
    import json
    cdn_map = {}
    label_to_key = {
        "Soft Rains pilot":    "soft_rains_video",
        "Hundred Acre pilot":  "pooh_video",
        "Soft Rains poster":   "soft_rains_poster",
        "Pooh poster":         "pooh_poster",
    }
    for label, key, public, _, _ in results:
        if label in label_to_key:
            cdn_map[label_to_key[label]] = public
    assets_path = REPO / "site" / "cdn-assets.json"
    assets_path.write_text(json.dumps(cdn_map, indent=2), encoding="utf-8")
    print(f"Wrote {assets_path}")
    print()
    print("Landing page will auto-use these URLs on next load.")
    print("Test at https://narrowhighway.com/ after the Cloudflare Pages deploy syncs site/cdn-assets.json.")


if __name__ == "__main__":
    main()
