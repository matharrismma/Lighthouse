"""build_full_sitemap.py — Generate sitemap_cards.xml from witnessed cards.

The hand-curated site/sitemap.xml has ~40 URLs (top-level pages + feeds).
This generator produces a SECOND sitemap, site/sitemap_cards.xml, with one
entry per passed-witness card. Plus a sitemap-index file
(site/sitemap_index.xml) that points to both.

Google + Bing + AI crawlers honor sitemap-index files. Submitting just
sitemap_index.xml to Search Console makes both the hand-curated sitemap
and the auto-generated card sitemap discoverable.

Sitemap size limit: 50,000 URLs OR 50 MB per file. We're well under both.
If we ever exceed 50k cards, split into shards (sitemap_cards_001.xml etc.).

Run:
  python tools/build_full_sitemap.py            # produces all three files
  python tools/build_full_sitemap.py --print-stats   # just count what would ship

Outputs:
  site/sitemap_cards.xml      — auto-generated (every witnessed card)
  site/sitemap_index.xml      — points to sitemap.xml + sitemap_cards.xml
  (site/sitemap.xml is left alone — it's the hand-curated one)
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
SITE_DIR = REPO / "site"
SITE_BASE = "https://narrowhighway.com"

# Which lifecycle stages produce a public crawlable URL
INDEXABLE_STAGES = {"public", "featured", "public_review"}

# How priority maps from lifecycle stage
STAGE_PRIORITY = {
    "featured": "0.9",
    "public": "0.7",
    "public_review": "0.5",
}

# How frequently each stage changes
STAGE_CHANGEFREQ = {
    "featured": "weekly",
    "public": "monthly",
    "public_review": "weekly",
}


def _card_url(card_id: str) -> str:
    """Stable card URL — what crawlers will visit. Points at the SSR endpoint
    (/c/{id}) instead of the JS-SPA /card.html?id=X — crawlers get full HTML
    + JSON-LD + body text without executing JS."""
    return f"{SITE_BASE}/c/{card_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def collect_indexable_cards():
    """Yield (card_id, lifecycle_stage, updated_at) for every card that
    should be in the sitemap.

    Optimized: reads file bytes once, decodes UTF-8 with replace, and
    does a substring check BEFORE json.loads. Skips connection cards
    and engine_derived cards (they're not useful crawl targets — the
    substantive content cards are what crawlers want)."""
    if not CARDS_DIR.exists():
        return
    files = list(CARDS_DIR.glob("*.json"))
    total_seen = 0
    yielded = 0
    for f in files:
        total_seen += 1
        if total_seen % 1000 == 0:
            print(f"  scanned {total_seen}/{len(files)} files; yielded {yielded} so far", flush=True)
        try:
            raw = f.read_bytes()
        except Exception:
            continue
        # Fast pre-filter: skip the obviously-skippable without parsing
        if b'"witness_status": "passed"' not in raw and b'"witness_status": "single_witness"' not in raw:
            continue
        # Skip pure-connection cards (they have "kind": "connection")
        if b'"kind": "connection"' in raw:
            continue
        # Now parse only the survivors
        try:
            text = raw.decode("utf-8", errors="replace")
            c = json.loads(text)
        except Exception:
            continue
        # Lifecycle gate
        stage = c.get("lifecycle_stage") or "public"
        if stage not in INDEXABLE_STAGES:
            continue
        if c.get("retracted"):
            continue
        cid = c.get("id")
        if not cid:
            continue
        updated = c.get("updated_at") or c.get("created_at") or _now_iso()
        try:
            if "T" in updated:
                updated = updated.split("T")[0]
        except Exception:
            updated = _now_iso()[:10]
        yielded += 1
        yield (cid, stage, updated)
    print(f"  scan complete: {total_seen} files, {yielded} indexable cards", flush=True)


def write_card_sitemap():
    cards = list(collect_indexable_cards())
    out = SITE_DIR / "sitemap_cards.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for cid, stage, updated in cards:
        url = _card_url(cid)
        pri = STAGE_PRIORITY.get(stage, "0.6")
        freq = STAGE_CHANGEFREQ.get(stage, "monthly")
        lines.append(
            f"  <url><loc>{xml_escape(url)}</loc>"
            f"<lastmod>{xml_escape(updated)}</lastmod>"
            f"<changefreq>{freq}</changefreq>"
            f"<priority>{pri}</priority></url>"
        )
    lines.append("</urlset>")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out, len(cards)


def write_sitemap_index():
    """Top-level index pointing crawlers at both sitemaps."""
    out = SITE_DIR / "sitemap_index.xml"
    today = _now_iso()[:10]
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{SITE_BASE}/sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{SITE_BASE}/sitemap_cards.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{SITE_BASE}/sitemap_discernments.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
</sitemapindex>
"""
    out.write_text(xml, encoding="utf-8")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--print-stats", action="store_true",
                   help="Don't write files; just count what would ship")
    args = p.parse_args()

    cards = list(collect_indexable_cards())
    by_stage = {}
    for _, stage, _ in cards:
        by_stage[stage] = by_stage.get(stage, 0) + 1

    print(f"Indexable cards: {len(cards):,}")
    for stage, n in sorted(by_stage.items()):
        print(f"  {stage}: {n:,}")

    if args.print_stats:
        return

    out_cards, n_cards = write_card_sitemap()
    out_index = write_sitemap_index()
    print()
    print(f"WROTE {out_cards}  ({n_cards:,} card URLs)")
    print(f"WROTE {out_index}  (points to sitemap.xml + sitemap_cards.xml)")
    print()
    print("Submit to Google Search Console / Bing Webmaster as:")
    print(f"  {SITE_BASE}/sitemap_index.xml")


if __name__ == "__main__":
    main()
