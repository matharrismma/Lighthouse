"""Build a podcast RSS feed from our audio library.

Generates a single RSS 2.0 feed (iTunes-compatible) listing audio episodes.
Submit the URL to Apple Podcasts Connect, Spotify for Podcasters, Google
Podcasts, iHeartRadio — all crawl this one URL.

Per [distribution memo](project_distribution_1000_true_fans_2026-05-16.md), every
episode description includes "more at narrowhighway.com" with a deep-link to
the relevant deck.

Sources:
  - site/hymns.json + (Piper or ElevenLabs) renders at D:/library_files/hymn_renders/
  - site/stations.json (existing OTR catalog)
  - data/devotionals/<date>.json (Anthropic-generated devotions)
  - any manifest with audio_renders[] in data/library_inventory/acquired/

Output:
  site/podcast.rss          — the feed URL (served at /podcast.rss)
  site/podcast.html         — human-readable preview / subscribe page

Usage:
  python tools/build_podcast_rss.py
  python tools/build_podcast_rss.py --base-url https://narrowhighway.com
  python tools/build_podcast_rss.py --section devotional
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from email.utils import formatdate
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
DEV_DIR = REPO / "data" / "devotionals"
ACQUIRED = REPO / "data" / "library_inventory" / "acquired"

DEFAULT_BASE = "https://narrowhighway.com"
OUTRO_LINE = "Find more like this at NarrowHighway.com — a curated internet for Christian families."

# Podcast metadata. Apple Podcasts requires all these.
SHOW = {
    "title": "Narrow Highway · Daily",
    "subtitle": "Devotions, hymns, almanac wisdom, and the songs Christians have sung for centuries.",
    "description": (
        "A daily anchor for Christian families. One short devotion, one hymn read or sung, "
        "one verified almanac wisdom, one anchored Scripture passage. Public-domain, "
        "family-safe, ad-free. From narrowhighway.com — a curated internet for Christian families. "
        "Better to have 1000 die-hard fans than a million casual ones."
    ),
    "author": "M.R. Harris",
    "owner_email": "ops@narrowhighway.com",  # change to a real address before submitting
    "language": "en-us",
    "category": "Religion & Spirituality",
    "subcategory": "Christianity",
    "explicit": False,
    "image_url": None,  # set to a 1400-3000 px square PNG/JPEG URL before submitting
    "image_path": "/icon-512.png",  # fallback if image_url not set
}


def iso_to_rfc2822(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    return formatdate(dt.timestamp(), usegmt=True)


def now_rfc2822() -> str:
    return formatdate(datetime.now(timezone.utc).timestamp(), usegmt=True)


def collect_devotionals(base: str) -> list[dict]:
    items = []
    if not DEV_DIR.exists():
        return items
    for fp in sorted(DEV_DIR.glob("*.json"), reverse=True):
        try:
            blob = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        date = blob.get("date") or fp.stem
        slug = f"devotion-{date}"
        # Audio URL: we expect the marquee rendering at /audio/devotionals/<date>.mp3
        # (this path is what render_audio_premium.py writes; mirror manually if needed)
        audio_url = f"{base}/audio/devotionals/{date}.mp3"
        items.append({
            "guid": f"nh-devotion-{date}",
            "title": f"{date} · {blob.get('title','Devotion')}",
            "description": f"{blob.get('body','')}\n\n{OUTRO_LINE}",
            "scripture_ref": blob.get("scripture_ref", ""),
            "audio_url": audio_url,
            "duration": 120,  # estimate; replace with real after render
            "pub_date_rfc2822": iso_to_rfc2822(blob.get("generated_at", "")),
            "category": "Devotion",
            "deck_link": f"{base}/daily.html",
        })
    return items


def collect_hymns(base: str) -> list[dict]:
    items = []
    hymns_json = SITE / "hymns.json"
    if not hymns_json.exists():
        return items
    blob = json.loads(hymns_json.read_text(encoding="utf-8"))
    for h in blob.get("hymns", []):
        slug = h.get("slug")
        # Audio at /audio/hymns/<slug>.mp3 — written by render_audio.py (Piper) or render_audio_premium.py
        audio_url = f"{base}/audio/hymns/{slug}.mp3"
        body = (h.get("text") or "").strip()
        desc = (
            f"{h.get('title')} — {h.get('author','—')} ({h.get('year','')})\n"
            f"Meter: {h.get('meter','')}\n"
            f"Scripture: {' · '.join(h.get('scripture', []))}\n\n"
            f"{body}\n\n"
            f"{OUTRO_LINE}"
        )
        items.append({
            "guid": f"nh-hymn-{slug}",
            "title": f"Hymn · {h.get('title')}",
            "description": desc,
            "audio_url": audio_url,
            "duration": 180,  # estimate
            "pub_date_rfc2822": now_rfc2822(),
            "category": "Hymn",
            "deck_link": f"{base}/hymns.html",
        })
    return items


def collect_acquired_audio(base: str, category_filter: str | None = None) -> list[dict]:
    """Surface any acquired audio that has been MARQUEE-rendered (i.e. has a
    /audio/<slug>/marquee.mp3 entry). For Stage 1 we wire this minimally; bulk
    surfacing comes later when we have lots of marquee renders to feed."""
    items = []
    # Conservative: skip for now; bulk acquisition adds 1000s of episodes which
    # we DON'T want all in the public podcast feed. Curated marquee only.
    return items


def build_rss(base: str, sections: list[str]) -> str:
    """Build the full RSS 2.0 + iTunes-extended XML."""
    items: list[dict] = []
    if "devotional" in sections:
        items.extend(collect_devotionals(base))
    if "hymn" in sections:
        items.extend(collect_hymns(base))
    if "acquired" in sections:
        items.extend(collect_acquired_audio(base))

    items.sort(key=lambda x: x.get("pub_date_rfc2822", ""), reverse=True)
    items = items[:200]  # Apple caps; we cap too

    img = SHOW.get("image_url") or f"{base}{SHOW['image_path']}"

    item_xml = []
    for it in items:
        guid = xml_escape(it["guid"])
        title = xml_escape(it["title"])
        desc = xml_escape(it["description"])
        link = xml_escape(it.get("deck_link", base))
        audio = xml_escape(it["audio_url"])
        pub = it["pub_date_rfc2822"]
        duration = it.get("duration", 180)
        h, rem = divmod(duration, 3600); m, s = divmod(rem, 60)
        dur = f"{h:02d}:{m:02d}:{s:02d}"
        category = xml_escape(it.get("category", ""))
        item_xml.append(f"""    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{guid}</guid>
      <description><![CDATA[{it['description']}]]></description>
      <itunes:summary><![CDATA[{it['description']}]]></itunes:summary>
      <enclosure url="{audio}" type="audio/mpeg" length="0"/>
      <pubDate>{pub}</pubDate>
      <itunes:duration>{dur}</itunes:duration>
      <itunes:explicit>{'yes' if SHOW['explicit'] else 'no'}</itunes:explicit>
      <itunes:keywords>{category}, Christian, family, hymn, devotional, narrow highway</itunes:keywords>
    </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{xml_escape(SHOW['title'])}</title>
    <link>{xml_escape(base)}</link>
    <atom:link href="{xml_escape(base)}/podcast.rss" rel="self" type="application/rss+xml"/>
    <description><![CDATA[{SHOW['description']}]]></description>
    <language>{SHOW['language']}</language>
    <copyright>Public Domain content; original commentary © {datetime.now().year} M.R. Harris</copyright>
    <pubDate>{now_rfc2822()}</pubDate>
    <lastBuildDate>{now_rfc2822()}</lastBuildDate>
    <itunes:author>{xml_escape(SHOW['author'])}</itunes:author>
    <itunes:owner>
      <itunes:name>{xml_escape(SHOW['author'])}</itunes:name>
      <itunes:email>{xml_escape(SHOW['owner_email'])}</itunes:email>
    </itunes:owner>
    <itunes:summary><![CDATA[{SHOW['description']}]]></itunes:summary>
    <itunes:subtitle>{xml_escape(SHOW['subtitle'])}</itunes:subtitle>
    <itunes:category text="{xml_escape(SHOW['category'])}">
      <itunes:category text="{xml_escape(SHOW['subcategory'])}"/>
    </itunes:category>
    <itunes:explicit>{'yes' if SHOW['explicit'] else 'no'}</itunes:explicit>
    <itunes:image href="{xml_escape(img)}"/>
    <image>
      <url>{xml_escape(img)}</url>
      <title>{xml_escape(SHOW['title'])}</title>
      <link>{xml_escape(base)}</link>
    </image>
{chr(10).join(item_xml)}
  </channel>
</rss>
"""
    return xml


def build_subscribe_page(base: str, items_total: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Podcast · Narrow Highway</title>
  <meta name="description" content="Subscribe to Narrow Highway · Daily on Apple Podcasts, Spotify, Google Podcasts, or any podcast app. {items_total} episodes and counting.">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <meta name="theme-color" content="#0a0810">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Crimson+Pro:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
  <script src="/nh-nav.js" defer></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg:#0a0810; --surface:#161320; --border:#29232f; --border-hi:#3a3142;
      --text:#ede7db; --text-dim:#b3aabd; --muted:#6e6878; --accent:#c9a87c; --accent-soft:rgba(201,168,124,0.12);
    }}
    body {{ background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; line-height:1.6; min-height:100dvh; }}
    .hero {{ max-width:880px; margin:0 auto; padding:48px 24px 30px; }}
    .eyebrow {{ font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:.22em; text-transform:uppercase; color:var(--accent); margin-bottom:10px; }}
    h1 {{ font-size:clamp(28px,4vw,42px); font-weight:700; line-height:1.1; letter-spacing:-.02em; margin-bottom:14px; }}
    h1 em {{ font-family:'Crimson Pro',serif; font-style:italic; color:var(--accent); }}
    .sub {{ color:var(--text-dim); font-size:15.5px; max-width:62ch; }}
    .subscribe-grid {{ max-width:880px; margin:0 auto; padding:0 24px 40px; display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; }}
    .sub-card {{ background:var(--surface); border:1px solid var(--border-hi); border-radius:12px; padding:18px 20px; text-decoration:none; color:inherit; transition:all .15s; }}
    .sub-card:hover {{ border-color:var(--accent); background:#1d1828; transform:translateY(-2px); }}
    .sub-card-name {{ font-weight:600; font-size:15px; margin-bottom:4px; }}
    .sub-card-blurb {{ font-size:12.5px; color:var(--text-dim); }}
    .feed-row {{ max-width:880px; margin:24px auto 50px; padding:14px 16px; background:var(--surface); border:1px dashed var(--border-hi); border-radius:10px; font-family:'JetBrains Mono',monospace; font-size:12px; }}
    .feed-row a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
  </style>
</head>
<body data-nh-crumb="Podcast">
<header class="hero">
  <div class="eyebrow">🎙 The Podcast</div>
  <h1>The <em>daily anchor</em>, in your podcast app.</h1>
  <p class="sub">
    Devotions, hymns, almanac wisdom — anchored to Scripture, family-safe, ad-free.
    Subscribe in your podcast app and every morning lands a short reading you can listen to over coffee.
  </p>
</header>
<div class="subscribe-grid">
  <a class="sub-card" target="_blank" rel="noopener" href="https://podcasts.apple.com/podcast/id000000">
    <div class="sub-card-name">🎧 Apple Podcasts</div><div class="sub-card-blurb">Subscribe on iPhone, iPad, Mac</div>
  </a>
  <a class="sub-card" target="_blank" rel="noopener" href="https://open.spotify.com/show/000000">
    <div class="sub-card-name">🎵 Spotify</div><div class="sub-card-blurb">In the Spotify app</div>
  </a>
  <a class="sub-card" target="_blank" rel="noopener" href="https://podcasts.google.com/feed/000000">
    <div class="sub-card-name">🟢 Google Podcasts / YouTube Music</div><div class="sub-card-blurb">Android default</div>
  </a>
  <a class="sub-card" target="_blank" rel="noopener" href="https://overcast.fm">
    <div class="sub-card-name">☁️ Overcast / Pocket Casts</div><div class="sub-card-blurb">Any podcast app</div>
  </a>
</div>
<div class="feed-row">
  <strong>Raw feed URL:</strong> <a href="/podcast.rss">{base}/podcast.rss</a><br>
  Paste it into any podcast app under "add by URL". Updated automatically with each new episode.
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--section", action="append", choices=["devotional","hymn","acquired"],
                    help="Limit to specific sections; repeat for multiple")
    args = ap.parse_args()
    sections = args.section or ["devotional", "hymn"]

    rss = build_rss(args.base_url, sections)
    out_rss = SITE / "podcast.rss"
    out_rss.write_text(rss, encoding="utf-8")

    # Count items for the subscribe page
    item_total = rss.count("<item>")
    out_html = SITE / "podcast.html"
    # Only overwrite the subscribe page if it doesn't exist yet (operator may have edited it)
    if not out_html.exists():
        out_html.write_text(build_subscribe_page(args.base_url, item_total), encoding="utf-8")
        print(f"[wrote] {out_html.relative_to(REPO)}")

    print(f"[wrote] {out_rss.relative_to(REPO)} ({item_total} items)")
    print(f"        Submit URL: {args.base_url}/podcast.rss")
    print(f"        Apple Podcasts Connect: https://podcastsconnect.apple.com/")
    print(f"        Spotify for Podcasters: https://podcasters.spotify.com/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
