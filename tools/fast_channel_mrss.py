"""Generate an MRSS feed for a FAST channel.

MRSS (Media RSS) is the format Roku Direct Publisher consumes. Each <item> describes
one piece of VOD content; Roku ingests the feed, fetches the media URLs, and lists
the content in a Direct Publisher channel app.

Spec references:
  https://developer.roku.com/docs/specs/direct-publisher.md
  https://www.rssboard.org/media-rss

We emit:
  site/channels/<channel_id>/mrss.xml         — full content pool as MRSS items
  site/channels/<channel_id>/episodes.json    — same content as a simpler JSON

Each item points at:
  - the originating cached MP4 at https://narrowhighway.com/.../<id>.mp4 (when published)
  - a thumbnail (we use the still card we already rendered, if present)
  - a description (channel-level), title, GUID, pubDate

For Phase 1, all items are flagged as "Short-Form Movie" or "Series Episode" so
Roku categorizes them sensibly. Series episodes need season+episode numbers — we
derive these from item ordering within each category.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xe

REPO = Path(__file__).resolve().parent.parent

# Where the cached MP4s are physically — these need to be published behind a CDN
# (Cloudflare R2, etc.) for Roku to ingest. For now we point at a planned URL
# scheme; the publish step later swaps in real URLs.
PUBLIC_CDN_BASE = "https://narrowhighway.com/cdn/channels"


def stable_guid(channel_id: str, item_id: str) -> str:
    h = hashlib.sha256(f"{channel_id}::{item_id}".encode()).hexdigest()[:24]
    return f"nh-{channel_id}-{h}"


def rfc822_now() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def category_to_roku(category: str) -> str:
    """Map our internal category labels to Roku-Direct-Publisher categories."""
    cat = category.lower()
    if "animated" in cat or "pilot" in cat:
        return "Series Episode"
    if "audio_drama" in cat or "drama" in cat or "radio" in cat:
        return "Series Episode"
    return "Short-Form Movie"


def build_mrss(channel: dict, public_cdn_base: str = PUBLIC_CDN_BASE) -> str:
    ch_id = channel["channel_id"]
    name = channel["name"]
    desc = channel["description"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
        "<channel>",
        f"  <title>{xe(name)}</title>",
        f"  <link>https://narrowhighway.com/channels/{ch_id}/</link>",
        f"  <description>{xe(desc)}</description>",
        "  <language>en-us</language>",
        f"  <lastBuildDate>{rfc822_now()}</lastBuildDate>",
    ]

    # Walk content pool
    for category, items in channel["content_pool"].items():
        for ep_idx, item in enumerate(items, start=1):
            iid = item["id"]
            title = item["title"]
            guid = stable_guid(ch_id, iid)
            roku_cat = category_to_roku(category)
            media_url = f"{public_cdn_base}/{ch_id}/{iid}.mp4"
            thumb_url = f"{public_cdn_base}/{ch_id}/{iid}.png"
            lines += [
                "  <item>",
                f"    <title>{xe(title)}</title>",
                f"    <guid isPermaLink=\"false\">{guid}</guid>",
                f"    <pubDate>{rfc822_now()}</pubDate>",
                f"    <description>{xe(desc)}</description>",
                f"    <category>{xe(roku_cat)}</category>",
                f"    <media:content url=\"{media_url}\" medium=\"video\" type=\"video/mp4\" />",
                f"    <media:thumbnail url=\"{thumb_url}\" />",
                "    <media:credit role=\"producer\">Narrow Highway</media:credit>",
                "    <media:rating scheme=\"urn:simple\">nonadult</media:rating>",
                "  </item>",
            ]
    lines += ["</channel>", "</rss>"]
    return "\n".join(lines)


def build_episodes_json(channel: dict) -> dict:
    ch_id = channel["channel_id"]
    out = {
        "channel_id": ch_id,
        "name": channel["name"],
        "description": channel["description"],
        "generated": datetime.now(timezone.utc).isoformat(),
        "episodes": [],
    }
    for category, items in channel["content_pool"].items():
        for ep_idx, item in enumerate(items, start=1):
            out["episodes"].append({
                "id": item["id"],
                "title": item["title"],
                "category": category,
                "guid": stable_guid(ch_id, item["id"]),
                "media_path": item.get("video") or item.get("audio"),
                "duration_sec": item.get("duration_sec"),
                "youtube_id": item.get("youtube_id"),
                "season": 1,
                "episode": ep_idx,
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--cdn", default=PUBLIC_CDN_BASE)
    args = ap.parse_args()
    channel = json.loads(Path(args.channel).read_text(encoding="utf-8"))
    ch_id = channel["channel_id"]
    out_dir = REPO / "site" / "channels" / ch_id
    out_dir.mkdir(parents=True, exist_ok=True)

    mrss = build_mrss(channel, public_cdn_base=args.cdn)
    (out_dir / "mrss.xml").write_text(mrss, encoding="utf-8")

    eps = build_episodes_json(channel)
    (out_dir / "episodes.json").write_text(json.dumps(eps, indent=2), encoding="utf-8")

    print(f"MRSS:     {out_dir / 'mrss.xml'}")
    print(f"Episodes: {out_dir / 'episodes.json'}  ({len(eps['episodes'])} items)")


if __name__ == "__main__":
    main()
