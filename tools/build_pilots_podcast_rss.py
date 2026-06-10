"""Build the Narrow Highway Theatre podcast RSS feed.

Separate from /podcast.rss (which is the daily devotional feed), this feed
contains the long-form pilots from Sci-Fi Theatre and Hundred Acre Theatre.

Output:
  site/podcast-theatre.rss   — submit this URL to Apple Podcasts Connect and Spotify for Podcasters
  site/podcast-theatre.html  — human-readable subscribe page

Episodes pulled from:
  data/publish/<pilot>/audio_podcast.mp3 + title.txt + description.txt
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from html import escape as html_escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
import imageio_ffmpeg, subprocess

REPO = Path(__file__).resolve().parent.parent
PUBLISH_DIR = REPO / "data" / "publish"
SITE = REPO / "site"
FF = imageio_ffmpeg.get_ffmpeg_exe()

SHOW = {
    "title": "Narrow Highway · Theatre",
    "subtitle": "Golden-age radio drama and classic children's stories, rendered anew.",
    "description": (
        "Sci-Fi Theatre adapts public-domain golden-age sci-fi radio drama (Dimension X, X Minus One, Mercury Theatre, Quiet Please) "
        "into illustrated short films. Hundred Acre Theatre dramatizes A.A. Milne's original 1926 Winnie-the-Pooh stories. "
        "Each episode closes with a pastoral observation. From narrowhighway.com — a curated internet for Christian families."
    ),
    "author": "Matt Harris · Narrow Highway",
    "owner_email": "mharris.wcs@icloud.com",
    "language": "en-us",
    "category_main": "Arts",
    "category_sub": "Performing Arts",
    "explicit": "no",
    "image_url": "/icon-512.svg",
}

PILOTS = [
    {
        "pilot": "soft_rains_v4",
        "guid": "softrains-v4-2026-05-17",
        "season": 1,
        "episode": 1,
        "kind": "Sci-Fi Theatre",
        "pub_date": datetime(2026, 5, 17, 19, 0, 0, tzinfo=timezone.utc),
    },
    {
        "pilot": "hundred_acre",
        "guid": "hundred-acre-1-2026-05-17",
        "season": 1,
        "episode": 1,
        "kind": "Hundred Acre Theatre",
        "pub_date": datetime(2026, 5, 17, 20, 0, 0, tzinfo=timezone.utc),
    },
]


def get_audio_duration_sec(mp3: Path) -> int:
    r = subprocess.run([FF, "-hide_banner", "-i", str(mp3)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(int(h) * 3600 + int(m) * 60 + float(s))
    return 0


def fmt_itunes_duration(sec: int) -> str:
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_rss(base_url: str) -> str:
    items_xml = []
    for ep in PILOTS:
        pkg = PUBLISH_DIR / ep["pilot"]
        if not pkg.exists():
            print(f"  [SKIP] {ep['pilot']}: publish package missing")
            continue
        title = (pkg / "title.txt").read_text(encoding="utf-8").strip()
        description = (pkg / "description.txt").read_text(encoding="utf-8").strip()
        audio = pkg / "audio_podcast.mp3"
        if not audio.exists():
            print(f"  [SKIP] {ep['pilot']}: audio_podcast.mp3 missing")
            continue
        size_bytes = audio.stat().st_size
        duration_sec = get_audio_duration_sec(audio)
        pub_date_rfc = formatdate(ep["pub_date"].timestamp(), usegmt=True)
        # Audio URL — served from the engine /media route OR linked to CDN/YouTube later
        audio_url = f"{base_url}/media/podcast/{ep['pilot']}.mp3"
        item = f"""    <item>
      <title>{xml_escape(ep['kind'] + ' · S' + str(ep['season']) + 'E' + str(ep['episode']) + ' · ' + title)}</title>
      <description>{xml_escape(description)}</description>
      <itunes:summary>{xml_escape(description)}</itunes:summary>
      <itunes:author>{xml_escape(SHOW['author'])}</itunes:author>
      <itunes:duration>{fmt_itunes_duration(duration_sec)}</itunes:duration>
      <itunes:season>{ep['season']}</itunes:season>
      <itunes:episode>{ep['episode']}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>no</itunes:explicit>
      <enclosure url="{xml_escape(audio_url)}" length="{size_bytes}" type="audio/mpeg"/>
      <guid isPermaLink="false">{xml_escape(ep['guid'])}</guid>
      <pubDate>{pub_date_rfc}</pubDate>
      <link>{xml_escape(base_url)}/pilots.html</link>
    </item>"""
        items_xml.append(item)
        print(f"  [OK] {ep['pilot']}: {fmt_itunes_duration(duration_sec)}, {size_bytes//1024//1024} MB")

    image_url = f"{base_url}{SHOW['image_url']}"
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{xml_escape(SHOW['title'])}</title>
    <link>{xml_escape(base_url)}/pilots.html</link>
    <atom:link href="{xml_escape(base_url)}/podcast-theatre.rss" rel="self" type="application/rss+xml"/>
    <language>{SHOW['language']}</language>
    <itunes:author>{xml_escape(SHOW['author'])}</itunes:author>
    <itunes:owner>
      <itunes:name>{xml_escape(SHOW['author'])}</itunes:name>
      <itunes:email>{SHOW['owner_email']}</itunes:email>
    </itunes:owner>
    <itunes:summary>{xml_escape(SHOW['description'])}</itunes:summary>
    <description>{xml_escape(SHOW['description'])}</description>
    <itunes:subtitle>{xml_escape(SHOW['subtitle'])}</itunes:subtitle>
    <itunes:image href="{xml_escape(image_url)}"/>
    <image><url>{xml_escape(image_url)}</url><title>{xml_escape(SHOW['title'])}</title><link>{xml_escape(base_url)}</link></image>
    <itunes:category text="{SHOW['category_main']}">
      <itunes:category text="{SHOW['category_sub']}"/>
    </itunes:category>
    <itunes:explicit>{SHOW['explicit']}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <copyright>Public-domain source material; original animation and pastoral observations © Matt Harris 2026.</copyright>
    <lastBuildDate>{formatdate(datetime.now(timezone.utc).timestamp(), usegmt=True)}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    return feed


def build_subscribe_page(base_url: str):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Theatre Podcast — Narrow Highway</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 760px; margin: 1.5em auto; padding: 0 1em; background: #fafaf6; color: #2a2a28; line-height: 1.6; }}
  h1 {{ color: #1a3a52; border-bottom: 2px solid #c9b48a; padding-bottom: 0.3em; }}
  h2 {{ color: #1a3a52; }}
  nav.top {{ font-size: 0.9em; margin-bottom: 0.4em; }} nav.top a {{ color: #1a3a52; text-decoration: none; }}
  .ep {{ background: #fff; border: 1px solid #d4c8a5; border-radius: 6px; padding: 1em 1.3em; margin: 1em 0; }}
  .ep h3 {{ color: #1a3a52; margin: 0 0 0.3em; }}
  .ep .meta {{ color: #6a5a3a; font-size: 0.9em; margin-bottom: 0.6em; }}
  .ep .desc {{ font-size: 0.95em; color: #444; }}
  .subscribe {{ display: flex; flex-wrap: wrap; gap: 0.5em; margin: 1em 0; }}
  .subscribe a {{ background: #1a3a52; color: #fff; padding: 0.6em 1.2em; border-radius: 4px; text-decoration: none; font-size: 0.92em; }}
  .subscribe a.alt {{ background: #f0eada; color: #1a3a52; border: 1px solid #c9b48a; }}
  audio {{ width: 100%; margin: 0.5em 0; }}
</style>
</head>
<body>
<nav class="top"><a href="/">← Narrow Highway</a></nav>
<h1>Theatre Podcast</h1>
<p><em>Sci-Fi Theatre and Hundred Acre Theatre — audio-only feed.</em></p>

<h2>Subscribe</h2>
<div class="subscribe">
  <a href="podcasts://{base_url.replace('https://','').replace('http://','')}/podcast-theatre.rss">📻 Apple Podcasts</a>
  <a class="alt" href="https://podcasts.apple.com/" target="_blank">Apple Podcasts (after submission)</a>
  <a class="alt" href="https://open.spotify.com/" target="_blank">Spotify (after submission)</a>
  <a class="alt" href="/podcast-theatre.rss">RSS feed (XML)</a>
</div>

<h2>Episodes</h2>
<div class="ep">
  <h3>Sci-Fi Theatre · S1E1 · There Will Come Soft Rains</h3>
  <div class="meta">Ray Bradbury 1950 · X Minus One 1956 broadcast · 23 min</div>
  <audio controls preload="metadata" src="/media/podcast/soft_rains_v4.mp3"></audio>
  <div class="desc">An empty house keeps its routine after the family is gone. Sara Teasdale's poem read aloud by the wall at five o'clock. A storm comes. The house dies as the dawn returns.</div>
</div>
<div class="ep">
  <h3>Hundred Acre Theatre · S1E1 · In Which We Are Introduced to Winnie-the-Pooh</h3>
  <div class="meta">A.A. Milne 1926 · LibriVox narration · 18 min</div>
  <audio controls preload="metadata" src="/media/podcast/hundred_acre.mp3"></audio>
  <div class="desc">Edward Bear comes downstairs bump-bump-bump on the back of his head. He hears a buzzing in the oak. He decides the only reason for a buzzing-noise is bees, and so on.</div>
</div>

  <script defer src="/nh-shepherd.js"></script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://narrowhighway.com")
    args = ap.parse_args()
    print(f"Building theatre podcast feed at base {args.base_url}")
    print()

    # Copy audio_podcast.mp3 from each publish package to /media/podcast/ so the engine serves it
    media_podcast = Path("D:/library_files/podcast")
    media_podcast.mkdir(parents=True, exist_ok=True)
    for ep in PILOTS:
        src = PUBLISH_DIR / ep["pilot"] / "audio_podcast.mp3"
        if src.exists():
            dst = media_podcast / f"{ep['pilot']}.mp3"
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                import shutil
                shutil.copy2(src, dst)
                print(f"  [COPY] {dst}")

    feed = build_rss(args.base_url)
    (SITE / "podcast-theatre.rss").write_text(feed, encoding="utf-8")
    print(f"\nWrote {SITE / 'podcast-theatre.rss'} ({len(feed) // 1024} KB)")

    page = build_subscribe_page(args.base_url)
    (SITE / "podcast-theatre.html").write_text(page, encoding="utf-8")
    print(f"Wrote {SITE / 'podcast-theatre.html'}")
    print()
    print("Next steps for podcast distribution:")
    print(f"  1. Submit {args.base_url}/podcast-theatre.rss to:")
    print(f"     • Apple Podcasts Connect: https://podcastsconnect.apple.com")
    print(f"     • Spotify for Podcasters: https://podcasters.spotify.com")
    print(f"     • Amazon Music / Audible: https://podcasters.amazon.com")
    print(f"     • YouTube Music: auto-pulled from YouTube uploads")
    print(f"     • Pocket Casts / Overcast / Castro: index our feed automatically once it's findable")
    print(f"  2. Apple takes ~24-48 hours to review; the others are usually faster.")


if __name__ == "__main__":
    main()
