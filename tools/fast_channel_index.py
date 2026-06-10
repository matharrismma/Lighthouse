"""Build site/channels/index.json — a directory of all FAST channels.

This is the discovery file partners crawl. Each channel entry lists:
  - URLs (live HLS, MRSS, EPG, landing page)
  - identity (id, name, description, logo, category, content rating)
  - inventory snapshot (hours, episode count)
  - distribution status per platform

Also writes site/channels/<id>/manifest.json — a single-channel partner manifest
that platforms can ingest to confirm channel metadata.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE_BASE = "https://narrowhighway.com"


# The single channel that is actually distributed publicly. Other manifests in
# content/channels/ are PROGRAMMING SOURCES — they feed the unified pool but
# are not stood up as separate live FAST channels. To promote a source to a
# live channel, give it its own HLS day + add it to LIVE_CHANNEL_IDS.
LIVE_CHANNEL_IDS = {"narrow-highway"}


def hours_from_inventory(inv: dict) -> float:
    if not inv:
        return 0.0
    if "total_hours" in inv:
        return float(inv["total_hours"])
    if "estimated_total_hours" in inv:
        return float(inv["estimated_total_hours"])
    return 0.0


def has_hls(ch_id: str) -> bool:
    return (REPO / "site" / "channels" / ch_id / "hls" / "day.m3u8").exists()


def channel_role(ch_id: str) -> str:
    """Return 'live' for the publicly-distributed channel(s), 'programming-source'
    for the sub-channel manifests that exist as templates / pool sources but aren't
    distributed as their own FAST channels.
    """
    return "live" if ch_id in LIVE_CHANNEL_IDS else "programming-source"


def episode_count_from_pool(pool: dict) -> int:
    return sum(len(items) for items in pool.values())


def build_partner_manifest(ch: dict, slug_dir: Path):
    """Write site/channels/<id>/manifest.json — single-channel partner readable file."""
    ch_id = ch["channel_id"]
    inv = ch.get("content_inventory_status", {})
    total_h = hours_from_inventory(inv)
    has_live = has_hls(ch_id)

    out = {
        "schema": "narrowhighway.fast.channel.manifest/1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "channel": {
            "id": ch_id,
            "name": ch["name"],
            "tagline": ch.get("tagline", ""),
            "description": ch["description"],
            "category": ch.get("category"),
            "audience": ch.get("audience"),
            "language": "en-us",
            "country": "US",
            "logo": f"{SITE_BASE}{ch.get('logo', '/img/logo.png')}",
            "color_primary": ch.get("color_primary"),
            "color_accent": ch.get("color_accent"),
            "publisher": {
                "name": "Narrow Highway",
                "url": SITE_BASE,
                "contact": "channels@narrowhighway.com",
            },
        },
        "urls": {
            "landing": f"{SITE_BASE}/channels/{ch_id}/",
            "live_hls": f"{SITE_BASE}/channels/{ch_id}/live.m3u8",
            "mrss": f"{SITE_BASE}/channels/{ch_id}/mrss.xml",
            "epg_xmltv": f"{SITE_BASE}/channels/{ch_id}/epg.xml",
            "now_playing": f"{SITE_BASE}/channels/{ch_id}/now.json",
            "episodes": f"{SITE_BASE}/channels/{ch_id}/episodes.json",
        },
        "role": channel_role(ch_id),
        "status": {
            "hls_live": has_live,
            "mrss_live": (slug_dir / "mrss.xml").exists(),
            "epg_live": (slug_dir / "epg.xml").exists(),
        },
        "inventory": {
            "total_hours": total_h,
            "episode_count": episode_count_from_pool(ch.get("content_pool", {})),
            "wurl_100hr_threshold_pct": min(100, int(total_h)),
        },
        "distribution": ch.get("distribution_targets", []),
        "license": "All content public domain or original work by Narrow Highway.",
    }
    (slug_dir / "manifest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def build_channels_index() -> dict:
    """Walk content/channels/*.json, write site/channels/index.json + per-channel manifest.json."""
    src_dir = REPO / "content" / "channels"
    site_dir = REPO / "site" / "channels"
    site_dir.mkdir(parents=True, exist_ok=True)

    channels = []
    for manifest_path in sorted(src_dir.glob("*.json")):
        try:
            ch = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [skip {manifest_path.name}] {e}")
            continue
        ch_id = ch["channel_id"]
        slug_dir = site_dir / ch_id
        slug_dir.mkdir(parents=True, exist_ok=True)
        per = build_partner_manifest(ch, slug_dir)
        channels.append({
            "id": ch_id,
            "name": ch["name"],
            "tagline": ch.get("tagline", ""),
            "category": ch.get("category"),
            "role": per["role"],  # 'live' or 'programming-source'
            "landing": per["urls"]["landing"],
            "live_hls": per["urls"]["live_hls"],
            "mrss": per["urls"]["mrss"],
            "manifest": f"{SITE_BASE}/channels/{ch_id}/manifest.json",
            "status": per["status"],
            "inventory_hours": per["inventory"]["total_hours"],
        })
        print(f"  [OK] {ch_id} -> {slug_dir / 'manifest.json'}")

    live = [c for c in channels if c.get("role") == "live"]
    sources = [c for c in channels if c.get("role") == "programming-source"]

    index = {
        "schema": "narrowhighway.fast.channels.index/2",
        "_note": (
            "We distribute ONE live channel (narrow-highway). The other manifests "
            "are programming sources — they feed the unified pool but are not "
            "themselves stood up as separate FAST channels. Promote a source to a "
            "live channel by adding its id to LIVE_CHANNEL_IDS in tools/fast_channel_index.py "
            "and building its HLS day."
        ),
        "live_channels": len(live),
        "programming_sources": len(sources),
        "generated": datetime.now(timezone.utc).isoformat(),
        "publisher": {
            "name": "Narrow Highway",
            "url": SITE_BASE,
            "contact": "channels@narrowhighway.com",
        },
        "channel_count": len(channels),
        "channels": channels,
    }
    (site_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nIndex: {site_dir / 'index.json'} ({len(channels)} channels)")
    return index


if __name__ == "__main__":
    build_channels_index()
