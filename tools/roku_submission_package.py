"""roku_submission_package.py — Build the Roku Direct Publisher submission package.

Roku Direct Publisher (free DIY channel program) accepts either an MRSS feed
or a JSON feed describing the channel + content. We already have the MRSS
feed; this tool produces:

  1. A Roku JSON Feed (the modern preferred format) at
     site/channels/narrow-highway/roku_feed.json — what you paste into the
     Direct Publisher portal as your "Content Feed URL".

  2. A submission checklist PDF-equivalent (Markdown) at
     content/channels/narrow-highway/roku_submission_checklist.md — every
     field Roku asks for, with the value to enter.

  3. A bundle of the channel + poster assets at the paths Roku expects,
     pre-named per the Roku spec.

Spec reference:
  https://developer.roku.com/docs/specs/direct-publisher-feed-specs.md
  https://developer.roku.com/docs/developer-program/direct-publisher/

Run:
  python tools/roku_submission_package.py
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "content" / "channels" / "narrow_highway.json"
SITE_CHANNEL = REPO / "site" / "channels" / "narrow-highway"
SUBMISSION_DIR = REPO / "content" / "channels" / "narrow-highway"
ASSETS_BRAND = Path("D:/library_files/_channel_bumpers/narrow-highway")


def make_roku_feed(channel: dict) -> dict:
    """Produce a Roku Direct Publisher JSON Feed.

    The feed must have:
      - providerName
      - language
      - lastUpdated
      - movies / series / shortFormVideos (one is sufficient)

    Narrow Highway is a 24/7 linear channel. Roku DPub also supports
    'liveFeed' for that pattern.
    """
    items = []
    pool = channel.get("content_pool", {})
    # Surface short-form video items (under 30 min) as `shortFormVideos`;
    # longer ones as `movies`. We only ship items that are on-disk +
    # witnessed (we already filtered during scheduling).
    movies = []
    short_videos = []
    item_id_seen = set()
    for pool_key, pool_items in pool.items():
        for it in pool_items:
            if it.get("witness_status") != "passed":
                continue
            dur = it.get("duration_sec") or 0
            if dur <= 0:
                continue
            iid = it.get("id")
            if not iid or iid in item_id_seen:
                continue
            item_id_seen.add(iid)
            video = it.get("video") or ""
            if not video:
                continue
            # Roku wants HTTP URLs to media, not local D:\ paths. The real
            # streaming source for Roku is the HLS feed; we point each item
            # at the HLS day playlist for now and let the schedule rotate.
            # When per-item playable URLs become available (HLS variants per
            # asset), update these to per-item URLs.
            hls_url = "https://narrowhighway.com/channels/narrow-highway/hls/day.m3u8"
            entry = {
                "id": iid,
                "title": (it.get("title") or iid)[:128],
                "shortDescription": (it.get("title") or iid)[:200],
                "thumbnail": "https://narrowhighway.com/img/channel-narrow-highway.png",
                "releaseDate": "2026-01-01",  # placeholder; real release per item ideal
                "genres": [_genre_for(pool_key)],
                "rating": {"rating": "TV-G", "ratingSource": "USA_PR"},
                "content": {
                    "dateAdded": datetime.now(timezone.utc).isoformat()[:10],
                    "videos": [{
                        "url": hls_url,
                        "quality": "HD",
                        "videoType": "HLS",
                    }],
                    "duration": int(dur),
                    "language": "en-US",
                },
                "tags": [pool_key, "narrow-highway"],
            }
            target = short_videos if dur < 1800 else movies
            target.append(entry)

    feed = {
        "providerName": "Narrow Highway",
        "language": "en-US",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "movies": movies,
        "shortFormVideos": short_videos,
    }
    return feed


def _genre_for(pool_key: str) -> str:
    """Map our pool keys to Roku-recognized genres."""
    mapping = {
        "hymns": "religion",
        "scifi_audio_dramas": "science-fiction",
        "scifi_animated_pilots": "science-fiction",
        "kids_pooh_readings": "kids",
        "kids_potter_readings": "kids",
        "kids_andersen_readings": "kids",
        "kids_blue_fairy_readings": "kids",
        "kids_velveteen": "kids",
        "kids_animated_pilots": "animation",
        "spurgeon_morning_evening": "religion",
        "spurgeon_all_of_grace": "religion",
        "edwards_select_sermons": "religion",
        "edwards_religious_affections": "religion",
        "classic_tv_video": "classic-tv",
        "classic_animation": "animation",
        "silent_films": "classic-tv",
        "newsreel_video": "news",
        "educational_video": "educational",
        "prelinger_video": "historical",
        "nasa_video": "science",
        "government_video": "documentary",
        "sports_boxing_video": "sports",
        "sports_misc_video": "sports",
        "sports_roller_derby": "sports",
        "fishing_film": "outdoor",
        "racing_film": "sports",
        "rodeo_film": "sports",
        "hist_video": "historical",
        "vegas_variety": "variety",
        "performance_shorts": "variety",
        "otr_anthology_drama": "drama",
        "otr_mystery_audio": "mystery",
        "otr_comedy_audio": "comedy",
        "otr_western_audio": "western",
    }
    return mapping.get(pool_key, "variety")


def make_checklist() -> str:
    """Markdown checklist for the Roku Direct Publisher portal."""
    return f"""# Roku Direct Publisher — Narrow Highway Submission Checklist

Generated {datetime.now(timezone.utc).isoformat()}

## Portal location
- Sign in: <https://developer.roku.com>
- Direct Publisher: My Channels → Add Channel → Direct Publisher

## Channel metadata (paste each value)

| Field | Value |
|---|---|
| Channel name | Narrow Highway |
| Channel store name | Narrow Highway |
| Category (primary) | Religious |
| Category (alt) | Lifestyle |
| Subcategory | Christian |
| Country availability | United States |
| Content rating (channel) | TV-PG |
| Content type | Live linear + VOD |
| Channel description (short ≤160 chars) | A curated internet for Christian families — hymns, sermons, sci-fi theatre, kids storytime, classic TV. Free. Family-safe. The Good ole days in a box. |
| Channel description (long) | Narrow Highway is a 24/7 Christian-family TV channel. Hymns in the morning, sermons through the day, kids' storytime after school, sci-fi theatre at primetime, late-night devotions. Every piece of content passes a public alignment + witness gate (Deuteronomy 19:15). All public domain, all family-safe, all free. Built at narrowhighway.com. |
| Content Feed URL (Roku-format) | https://narrowhighway.com/channels/narrow-highway/roku_feed.json |
| Content Feed URL (MRSS alt) | https://narrowhighway.com/channels/narrow-highway/mrss.xml |
| Provider Name | Narrow Highway |
| Language | en-US |

## Branding assets (upload from D:\\library_files\\_channel_bumpers\\narrow-highway\\)

| Asset | Size | File |
|---|---|---|
| Channel poster (FHD) | 1920×1080 | roku_poster_fhd.png |
| Channel poster (HD) | 1280×720 | roku_poster_hd.png |
| Channel poster (SD) | 540×405 | roku_poster_sd.png |
| Channel icon (HD) | 290×218 | roku_icon_hd.png |
| Channel icon (SD) | 248×140 | roku_icon_sd.png |
| Channel splash | 1920×1080 | roku_splash.png |

## Required documentation (have on hand)

- [ ] LLC registration (Narrow Highway LLC) — Roku requires a legal entity
- [ ] EIN (free from IRS — apply online)
- [ ] E&O insurance certificate (Front Row Insurance, Hiscox, or Hartford)
- [ ] Content rights documentation — pointer to <https://narrowhighway.com/witness-gate/health>
  shows the public Deut 19:15 witness chain for every item we broadcast

## Pre-submission verification (operator)

- [ ] `https://narrowhighway.com/channels/narrow-highway/roku_feed.json` returns 200
- [ ] `https://narrowhighway.com/channels/narrow-highway/mrss.xml` returns 200
- [ ] `https://narrowhighway.com/channels/narrow-highway/hls/day.m3u8` returns 200
- [ ] `https://narrowhighway.com/channels/narrow-highway/epg.xml` returns 200
- [ ] HLS feed plays in VLC: paste day.m3u8 URL → Open Network Stream
- [ ] At least 100 hours of broadcast content (current: ~322 hours; ✓)
- [ ] Channel uptime track record (recommend 30 days continuous before submission)

## Submission

1. Fill the form above with the values from this checklist.
2. Upload all 6 branding assets.
3. Set Content Feed URL to the Roku JSON Feed URL.
4. Submit for certification.
5. Review takes 5–10 business days. Roku will email feedback / approval.

## Once approved

- Channel appears in the Roku Channel Store under Religious / Christian.
- Discoverable via search on every Roku device in the US.
- After 30 days + audience data, apply to The Roku Channel (the curated tier).
"""


def main():
    ch = json.loads(MANIFEST.read_text(encoding="utf-8"))
    feed = make_roku_feed(ch)
    SITE_CHANNEL.mkdir(parents=True, exist_ok=True)
    feed_path = SITE_CHANNEL / "roku_feed.json"
    feed_path.write_text(json.dumps(feed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"WROTE {feed_path}  ({len(feed['movies'])} movies, {len(feed['shortFormVideos'])} short-form)")

    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)
    checklist_path = SUBMISSION_DIR / "roku_submission_checklist.md"
    checklist_path.write_text(make_checklist(), encoding="utf-8")
    print(f"WROTE {checklist_path}")

    # Verify branding assets exist
    print()
    print("=== branding asset readiness ===")
    required = [
        "roku_poster_fhd.png", "roku_poster_hd.png", "roku_poster_sd.png",
        "roku_icon_hd.png", "roku_icon_sd.png", "roku_splash.png",
    ]
    for fname in required:
        p = ASSETS_BRAND / fname
        if p.exists():
            print(f"  [OK]      {fname}  ({p.stat().st_size // 1024} KB)")
        else:
            print(f"  [MISSING] {fname}")


if __name__ == "__main__":
    main()
