"""RSS / Atom feeds for every lens.

Any subscriber can pull the keeping into their own reader (Feedly,
NetNewsWire, Reeder, an LLM, a Cron job). If the engine ever goes
dark, what subscribers already pulled is theirs. The substrate
becomes durable through redundancy.

Lenses with feeds:
  /feeds/almanac.xml        — new almanac entries (every CONFIRMED/MISMATCH/etc.)
  /feeds/radio.xml          — new radio episodes (with audio enclosures = podcast!)
  /feeds/hearth.xml         — recent Hearth messages across all rooms
  /feeds/hearth/<room>.xml  — recent messages in one room
  /feeds/seeds.xml          — newly crafted seeds
  /feeds/misalignments.xml  — disagreement flags
  /feeds/receipts.xml       — promoted writings
  /feeds/polymathic.xml     — recent polymathic runs

The radio feed includes <enclosure> tags for MP3s, so it's a valid
podcast feed — any podcast app can subscribe.
"""
from __future__ import annotations

import html
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
BASE_URL = "https://narrowhighway.com"


def _rfc822(ts_seconds: int) -> str:
    """RFC-822 date string, required by RSS 2.0 (pubDate field)."""
    try:
        dt = datetime.fromtimestamp(int(ts_seconds), tz=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _esc(s: Any) -> str:
    """XML-escape a string. None becomes empty."""
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def _cdata(s: Any) -> str:
    """Wrap in CDATA for fields where escaping every char is overkill."""
    s = "" if s is None else str(s)
    # Defensive: split any literal ']]>' that would close our CDATA
    s = s.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{s}]]>"


def _rss_envelope(
    title: str,
    link: str,
    description: str,
    items_xml: str,
    extra_channel: str = "",
) -> str:
    """Wrap items in a complete RSS 2.0 document."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"\n'
        '     xmlns:atom="http://www.w3.org/2005/Atom"\n'
        '     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"\n'
        '     xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        '  <channel>\n'
        f'    <title>{_esc(title)}</title>\n'
        f'    <link>{_esc(link)}</link>\n'
        f'    <description>{_esc(description)}</description>\n'
        f'    <language>en-US</language>\n'
        f'    <atom:link href="{_esc(link)}" rel="self" type="application/rss+xml"/>\n'
        f'    <generator>Concordance Engine</generator>\n'
        f'    {extra_channel}\n'
        f'{items_xml}\n'
        '  </channel>\n'
        '</rss>\n'
    )


# ── Per-lens feed builders ──────────────────────────────────────────

def almanac_feed() -> str:
    """RSS for newly added Almanac entries."""
    try:
        from api import packets_index as _pi
        all_packets = _pi.load_all()
    except Exception:
        all_packets = []
    items = [p for p in all_packets if p.get("kind") == "almanac"]
    items.sort(key=lambda p: p.get("timestamp", 0), reverse=True)
    items = items[:50]
    items_xml = "\n".join(_almanac_item(p) for p in items)
    return _rss_envelope(
        title="The Almanac · Concordance Engine",
        link=f"{BASE_URL}/almanac.html",
        description="The ledger of falsifiable claims. Carry what survives.",
        items_xml=items_xml,
    )


def _almanac_item(p: Dict[str, Any]) -> str:
    pid = p.get("id", "")
    title = p.get("title") or p.get("id", "(untitled)")
    verdict = p.get("verdict") or ""
    summary = p.get("summary", "")
    link = f"{BASE_URL}/almanac.html?q={pid}"
    pub = _rfc822(p.get("timestamp", time.time()))
    desc = f"<strong>{_esc(verdict)}</strong> — {_esc(summary)}" if verdict else _esc(summary)
    return (
        '    <item>\n'
        f'      <title>{_esc(verdict)} · {_esc(title)}</title>\n'
        f'      <link>{_esc(link)}</link>\n'
        f'      <guid isPermaLink="false">almanac/{_esc(pid)}</guid>\n'
        f'      <pubDate>{pub}</pubDate>\n'
        f'      <description>{_cdata(desc)}</description>\n'
        '    </item>'
    )


def radio_feed() -> str:
    """Podcast feed for radio episodes — includes MP3 enclosures."""
    try:
        from api import radio as _r
        all_eps = []
        for show in _r.SHOWS:
            eps = _r.list_episodes(show["slug"], limit=100)
            for ep in eps:
                all_eps.append((show, ep))
    except Exception:
        all_eps = []
    # Newest first by aired_at_iso
    def _aired_ts(pair):
        ep = pair[1]
        try:
            iso = (ep.get("aired_at_iso") or "").replace("Z", "+00:00")
            return datetime.fromisoformat(iso).timestamp()
        except Exception:
            return 0
    all_eps.sort(key=_aired_ts, reverse=True)
    all_eps = all_eps[:50]
    items_xml = "\n".join(_radio_item(s, e) for s, e in all_eps)
    extra = (
        '<itunes:author>M.R. Harris</itunes:author>\n'
        '    <itunes:summary>Six shows from the Concordance Engine — devotion, parable, almanac, walk, news, Bible study.</itunes:summary>\n'
        '    <itunes:category text="Religion &amp; Spirituality"/>\n'
        '    <itunes:explicit>false</itunes:explicit>'
    )
    return _rss_envelope(
        title="Concordance Radio · Narrow Highway",
        link=f"{BASE_URL}/radio.html",
        description="Six shows voiced by the engine. Devotion, parable, almanac, walk, news, Bible study.",
        items_xml=items_xml,
        extra_channel=extra,
    )


def _radio_item(show: Dict[str, Any], ep: Dict[str, Any]) -> str:
    ep_date = ep.get("ep_date", "")
    title = ep.get("title") or "(untitled episode)"
    link = f"{BASE_URL}/radio.html?show={show['slug']}"
    try:
        iso = (ep.get("aired_at_iso") or "").replace("Z", "+00:00")
        ts = int(datetime.fromisoformat(iso).timestamp())
    except Exception:
        ts = int(time.time())
    pub = _rfc822(ts)
    audio_url = ep.get("audio_url")
    audio_size = ep.get("audio_bytes", 0)
    enclosure = ""
    if audio_url and audio_size > 0:
        enclosure = (
            f'      <enclosure url="{_esc(BASE_URL + audio_url)}" '
            f'length="{audio_size}" type="audio/mpeg"/>\n'
        )
    desc = f"<strong>{_esc(show['name'])}</strong><br/>" + _esc(ep.get("script", "")[:600]) + "…"
    return (
        '    <item>\n'
        f'      <title>{_esc(show["name"])} · {_esc(title)}</title>\n'
        f'      <link>{_esc(link)}</link>\n'
        f'      <guid isPermaLink="false">radio/{_esc(show["slug"])}/{_esc(ep_date)}</guid>\n'
        f'      <pubDate>{pub}</pubDate>\n'
        f'      <itunes:author>{_esc(show.get("host", "M.R. Harris"))}</itunes:author>\n'
        f'      <itunes:duration>{int(show.get("duration_min", 10)) * 60}</itunes:duration>\n'
        f'      <description>{_cdata(desc)}</description>\n'
        f'{enclosure}'
        '    </item>'
    )


def hearth_feed(room: Optional[str] = None) -> str:
    """RSS for Hearth messages. Without `room`, all rooms; otherwise filtered."""
    try:
        from api import hearth as _h
        rooms = [room] if room else [r["slug"] for r in _h.ROOMS]
        all_msgs = []
        for rs in rooms:
            for m in _h.recent_messages(rs, limit=100):
                all_msgs.append(m)
        all_msgs.sort(key=lambda m: m.get("ts_ms", 0), reverse=True)
        all_msgs = all_msgs[:50]
    except Exception:
        all_msgs = []
    items_xml = "\n".join(_hearth_item(m) for m in all_msgs)
    title = (
        f"The Hearth · {room.title()} Room · Concordance Engine"
        if room else "The Hearth · all rooms · Concordance Engine"
    )
    link = f"{BASE_URL}/hearth.html" + (f"?room={room}" if room else "")
    return _rss_envelope(
        title=title,
        link=link,
        description="Where everyone knows your name. Append-only conversation in the keeping.",
        items_xml=items_xml,
    )


def _hearth_item(m: Dict[str, Any]) -> str:
    handle = m.get("handle", "anon")
    body = m.get("body", "")
    rm = m.get("room", "")
    link = f"{BASE_URL}/hearth.html?room={rm}"
    pub = _rfc822(int(m.get("ts_ms", 0) / 1000))
    desc = _cdata(f'<strong>{_esc(rm.title())} Room</strong><br/>{_esc(body)}')
    title_text = f"{handle} in {rm.title()} Room"
    return (
        '    <item>\n'
        f'      <title>{_esc(title_text)}</title>\n'
        f'      <link>{_esc(link)}</link>\n'
        f'      <guid isPermaLink="false">hearth/{_esc(rm)}/{_esc(m.get("id",""))}</guid>\n'
        f'      <pubDate>{pub}</pubDate>\n'
        f'      <description>{desc}</description>\n'
        '    </item>'
    )


def seeds_feed() -> str:
    try:
        from api.seeds import load_seeds
        all_seeds = load_seeds()
    except Exception:
        all_seeds = []
    all_seeds.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
    all_seeds = all_seeds[:50]
    items_xml = "\n".join(_seed_item(s) for s in all_seeds)
    return _rss_envelope(
        title="Seeds · Questions that planted themselves · Concordance Engine",
        link=f"{BASE_URL}/seeds.html",
        description="Search-misses that crafted themselves into reusable packets. The keeping grows from every question.",
        items_xml=items_xml,
    )


def _seed_item(s: Dict[str, Any]) -> str:
    sid = s.get("id", "")
    query = s.get("query", "")
    summary = s.get("summary", "")
    link = f"{BASE_URL}/?q={_esc(query)}"
    pub = _rfc822(s.get("timestamp", time.time()))
    return (
        '    <item>\n'
        f'      <title>Seed · {_esc(query)}</title>\n'
        f'      <link>{_esc(link)}</link>\n'
        f'      <guid isPermaLink="false">seed/{_esc(sid)}</guid>\n'
        f'      <pubDate>{pub}</pubDate>\n'
        f'      <description>{_cdata(_esc(summary))}</description>\n'
        '    </item>'
    )


def polymathic_feed() -> str:
    try:
        from api import polymathic_journal as _pj
        runs = _pj.all_runs(limit=50)
    except Exception:
        runs = []
    items_xml = "\n".join(_polymathic_item(r) for r in runs)
    return _rss_envelope(
        title="Polymathic · Multi-domain runs · Concordance Engine",
        link=f"{BASE_URL}/poly.html",
        description="Recent polymathic situations the engine classified and verified across all 48 domains.",
        items_xml=items_xml,
    )


def _polymathic_item(r: Dict[str, Any]) -> str:
    rid = r.get("run_id", "")
    sit = r.get("situation", "")[:200]
    verdict = r.get("verdict") or ""
    domains = ", ".join(r.get("domains") or [])
    link = f"{BASE_URL}/poly.html?run={rid}"
    pub = _rfc822(r.get("saved_at", time.time()))
    desc = _cdata(f"<strong>{_esc(verdict)}</strong> across {_esc(domains)}<br/>{_esc(sit)}")
    return (
        '    <item>\n'
        f'      <title>{_esc(verdict or "Polymathic")} · {_esc(sit[:80])}</title>\n'
        f'      <link>{_esc(link)}</link>\n'
        f'      <guid isPermaLink="false">poly/{_esc(rid)}</guid>\n'
        f'      <pubDate>{pub}</pubDate>\n'
        f'      <description>{desc}</description>\n'
        '    </item>'
    )
