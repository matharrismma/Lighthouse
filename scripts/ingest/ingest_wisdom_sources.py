"""
ingest_wisdom_sources.py — Wisdom source ingestion for Concordance.

Fetches patristic texts, confessional standards, and institutional
archives; chunks them into meaningful units; POSTs each chunk to
/capture with full provenance metadata.

Sources:
  1. Project Gutenberg   — Apostolic Fathers, Imitation of Christ, Confessions
  2. Westminster         — Shorter/Larger Catechisms, Confession of Faith
  3. CCEL               — Christian Classics Ethereal Library structured texts
  4. Library of Congress — Chronicling America historical primary sources
  5. Vatican DigiVatLib  — Apostolic Library catalog and transcribed texts

Usage:
  python scripts/ingest/ingest_wisdom_sources.py              # all sources
  python scripts/ingest/ingest_wisdom_sources.py --source gutenberg
  python scripts/ingest/ingest_wisdom_sources.py --source westminster
  python scripts/ingest/ingest_wisdom_sources.py --source loc
  python scripts/ingest/ingest_wisdom_sources.py --source vatican
  python scripts/ingest/ingest_wisdom_sources.py --dry-run    # no POST
  python scripts/ingest/ingest_wisdom_sources.py --reset      # re-ingest all
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# Reconfigure stdout to UTF-8 on Windows so Unicode text doesn't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

API_BASE    = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE  = Path(__file__).parent / "ingest_state.json"
ATLAS_FILE  = Path(__file__).parent / "source_atlas.json"
HEADERS     = {"User-Agent": "Concordance-Ingest/1.0 (wisdom-pipeline)"}

_DELAY = 1.0   # seconds between POSTs; override with --delay


# ── state management ─────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"ingested": []}

def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def _register_atlas(source_key: str, entry: dict) -> None:
    """Record a source in the Atlas — the book of maps for this corpus.

    Each entry links a logical source key to its human-readable metadata
    and canonical retrieval URL so any packet can be traced back to its
    origin. The Atlas is append-only: existing entries are updated in place,
    new ones are added. Written to source_atlas.json alongside ingest_state.
    """
    atlas = json.loads(ATLAS_FILE.read_text(encoding="utf-8")) if ATLAS_FILE.exists() else {}
    existing = atlas.get(source_key, {})
    existing.update(entry)
    existing["source_key"] = source_key
    atlas[source_key] = existing
    ATLAS_FILE.write_text(json.dumps(atlas, indent=2, ensure_ascii=False), encoding="utf-8")

def _chunk_id(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}:{text[:120]}".encode()).hexdigest()[:20]


# ── capture poster ────────────────────────────────────────────────────────────

def post(text: str, source: str, meta: dict[str, Any],
         tags: list[str], dry_run: bool) -> bool:
    cid   = _chunk_id(source, text)
    state = _load_state()
    if cid in state["ingested"]:
        return False  # already ingested

    if dry_run:
        preview = text[:120].replace("\n", " ")
        print(f"    [DRY] {source}  len={len(text)}  {preview!r}")
        return True

    try:
        r = requests.post(f"{API_BASE}/capture", json={
            "text": text,
            "source": source,
            "source_meta": meta,
            "tags": tags,
            "look_up_precedent": False,   # skip LLM precedent for bulk ingest
            "identity_acknowledged": True,
        }, timeout=30, headers=HEADERS)
        if r.status_code in (200, 201):
            state["ingested"].append(cid)
            _save_state(state)
            return True
        print(f"    [WARN] HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as exc:
        print(f"    [ERR] {exc}")
        return False


# ── gutenberg ─────────────────────────────────────────────────────────────────

GUTENBERG_SOURCES = {
    "apostolic_fathers": {
        "id": 77576,
        "title": "The Writings of the Apostolic Fathers",
        "note": "Clement, Ignatius, Polycarp, Papias, Hermas — earliest post-NT church writings",
        "author": "Various (Apostolic Fathers)",
        "date_approx": "c. 96–150 AD",
        "tradition": "Early Church",
        "source_url": "https://www.gutenberg.org/ebooks/77576",
        "tags": ["patristic", "early_church", "clement", "ignatius", "polycarp", "wisdom"],
    },
    "pilgrims_progress": {
        "id": 131,
        "title": "The Pilgrim's Progress",
        "note": "John Bunyan — archetypal journey of faith; second-most-read English Christian text",
        "author": "John Bunyan",
        "date_approx": "1678",
        "tradition": "Protestant",
        "source_url": "https://www.gutenberg.org/ebooks/131",
        "tags": ["wisdom", "allegory", "spiritual_journey", "puritan", "devotional"],
    },
    "imitation_of_christ": {
        "id": 1653,
        "title": "The Imitation of Christ",
        "note": "Thomas à Kempis — most widely read Christian book after the Bible",
        "author": "Thomas à Kempis",
        "date_approx": "c. 1420",
        "tradition": "Catholic mystical",
        "source_url": "https://www.gutenberg.org/ebooks/1653",
        "tags": ["wisdom", "devotional", "spiritual_formation"],
    },
    "augustine_confessions": {
        "id": 3296,
        "title": "Confessions",
        "note": "Augustine of Hippo — the paradigm case of introspective wisdom",
        "author": "Augustine of Hippo",
        "date_approx": "c. 400 AD",
        "tradition": "Patristic",
        "source_url": "https://www.gutenberg.org/ebooks/3296",
        "tags": ["wisdom", "patristic", "introspection", "theology", "augustine"],
    },
    "rule_of_saint_benedict": {
        "id": 50040,
        "title": "The Rule of Saint Benedict",
        "note": "6th-century community governance — 73 chapters of applied wisdom",
        "author": "Benedict of Nursia",
        "date_approx": "c. 516 AD",
        "tradition": "Benedictine",
        "source_url": "https://www.gutenberg.org/ebooks/50040",
        "tags": ["wisdom", "governance", "community", "monastic", "patristic"],
    },
}

def _fetch_gutenberg(gutenberg_id: int) -> str:
    for url in [
        f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt",
        f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}.txt",
    ]:
        try:
            r = requests.get(url, timeout=40, headers=HEADERS)
            if r.status_code == 200:
                return r.text
        except Exception:
            continue
    raise RuntimeError(f"Could not fetch Gutenberg ID {gutenberg_id}")

def _strip_gutenberg(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    start = re.search(r'\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG', text, re.I)
    end   = re.search(r'\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG', text, re.I)
    if start:
        text = text[start.end():]
    if end:
        text = text[:end.start()]
    return text.strip()

def _chunk_chapters(text: str, min_words: int = 60, max_words: int = 1200) -> list[str]:
    # Split on common chapter/section heading patterns
    parts = re.split(
        r'\n{2,}(?=(?:CHAPTER|Chapter|BOOK|Book|PART|Part|SECTION|Section|'
        r'[IVX]+\.\s|§\s*\d+|\d+\.\s))',
        text
    )
    result = []
    for part in parts:
        part = part.strip()
        words = part.split()
        if len(words) < min_words:
            continue
        # Break oversized chunks at paragraph boundaries
        if len(words) > max_words:
            paras = [p.strip() for p in re.split(r'\n{2,}', part) if p.strip()]
            buf, buf_words = [], 0
            for para in paras:
                pw = len(para.split())
                if buf_words + pw > max_words and buf:
                    result.append("\n\n".join(buf))
                    buf, buf_words = [], 0
                buf.append(para)
                buf_words += pw
            if buf:
                result.append("\n\n".join(buf))
        else:
            result.append(part)
    # Fallback: paragraph-based chunking if chapter split yields nothing
    if len(result) <= 1:
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        buf, buf_words = [], 0
        for para in paras:
            pw = len(para.split())
            if pw < 10:
                continue
            if buf_words + pw > max_words and buf:
                result.append("\n\n".join(buf))
                buf, buf_words = [], 0
            buf.append(para)
            buf_words += pw
        if buf:
            result.append("\n\n".join(buf))
    return result

def ingest_gutenberg(dry_run: bool) -> None:
    for key, cfg in GUTENBERG_SOURCES.items():
        print(f"\n  [{cfg['title']}]  ({cfg['note']})")
        if not dry_run:
            _register_atlas(f"gutenberg_{key}", {
                "title":      cfg["title"],
                "author":     cfg["author"],
                "date_approx": cfg["date_approx"],
                "tradition":  cfg["tradition"],
                "source_url": cfg.get("source_url", f"https://www.gutenberg.org/ebooks/{cfg['id']}"),
                "collection": "Project Gutenberg",
                "tags":       cfg["tags"],
            })
        try:
            time.sleep(2)   # polite gap between Gutenberg fetches
            raw    = _fetch_gutenberg(cfg["id"])
            body   = _strip_gutenberg(raw)
            chunks = _chunk_chapters(body)
            print(f"    {len(chunks)} sections found")
            ok = 0
            for i, chunk in enumerate(chunks):
                meta = {
                    "title": cfg["title"],
                    "author": cfg["author"],
                    "date_approx": cfg["date_approx"],
                    "tradition": cfg["tradition"],
                    "gutenberg_id": cfg["id"],
                    "source_url": cfg.get("source_url", f"https://www.gutenberg.org/ebooks/{cfg['id']}"),
                    "section_index": i,
                }
                if post(chunk, f"gutenberg_{key}", meta, cfg["tags"], dry_run):
                    ok += 1
                    if not dry_run:
                        time.sleep(_DELAY)
            print(f"    {ok}/{len(chunks)} posted")
        except Exception as exc:
            print(f"    ERROR: {exc}")


# ── westminster standards ─────────────────────────────────────────────────────

WESTMINSTER_SOURCES = [
    {
        "key": "westminster_shorter_catechism",
        "title": "Westminster Shorter Catechism",
        "url": "https://opc.org/sc.html",
        "date": "1647",
        "tags": ["catechism", "reformed", "doctrinal", "wisdom", "westminster"],
    },
    {
        "key": "westminster_larger_catechism",
        "title": "Westminster Larger Catechism",
        "url": "https://opc.org/lc.html",
        "date": "1647",
        "tags": ["catechism", "reformed", "doctrinal", "wisdom", "westminster"],
    },
    {
        "key": "westminster_confession",
        "title": "Westminster Confession of Faith",
        "url": "https://opc.org/wcf.html",
        "date": "1646",
        "tags": ["confession", "reformed", "doctrinal", "wisdom", "westminster"],
    },
    {
        "key": "heidelberg_catechism",
        "title": "Heidelberg Catechism",
        "url": "https://opc.org/documents/HC.pdf",
        "date": "1563",
        "tags": ["catechism", "reformed", "doctrinal", "wisdom", "heidelberg"],
        "format": "text",
        "text_url": "https://www.ccel.org/creeds/heidelberg-cat-ext.txt",
    },
]

def _html_to_text(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&[a-z#0-9]+;', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def _parse_qa(raw: str) -> list[tuple[str, str]]:
    text  = _html_to_text(raw) if '<' in raw else raw
    pairs = re.findall(
        r'Q(?:uestion)?\s*\.?\s*\d+\s*[.:]?\s*(.*?)\s+A(?:nswer)?\s*[.:]?\s*(.*?)(?=Q(?:uestion)?\s*\.?\s*\d+|$)',
        text, re.I | re.DOTALL
    )
    return [(q.strip(), a.strip()) for q, a in pairs if len(q) > 15 and len(a) > 15]

def _parse_wcf_chapters(html: str) -> list[tuple[str, str]]:
    """Extract WCF chapter-title + body pairs."""
    text = _html_to_text(html)
    # Split at "Chapter N." or "CHAPTER N."
    parts = re.split(r'(?:Chapter|CHAPTER)\s+[IVXLC\d]+\.?\s+', text)
    # Re-attach chapter titles via findall
    titles = re.findall(r'(?:Chapter|CHAPTER)\s+([IVXLC\d]+\.?\s+\S[^\n]{3,60}?)(?:\s+(?:Section|SECT|\d))', text, re.I)
    result = []
    for i, body in enumerate(parts[1:], 0):
        title = titles[i] if i < len(titles) else f"Chapter {i+1}"
        body  = body.strip()
        if len(body.split()) > 30:
            result.append((title.strip(), body[:3000]))
    return result

def ingest_westminster(dry_run: bool) -> None:
    for cfg in WESTMINSTER_SOURCES:
        print(f"\n  [{cfg['title']}]")
        if not dry_run:
            _register_atlas(cfg["key"], {
                "title":      cfg["title"],
                "author":     "Westminster Assembly / Reformed Church",
                "date":       cfg["date"],
                "tradition":  "Reformed",
                "source_url": cfg["url"],
                "collection": "Westminster Standards / Reformed Confessions",
                "tags":       cfg["tags"],
            })
        try:
            # For Heidelberg, try plain-text URL first
            fetch_url = cfg.get("text_url") or cfg["url"]
            r = requests.get(fetch_url, timeout=30, headers=HEADERS)
            r.raise_for_status()
            source_url = cfg["url"]

            # WCF uses chapter/article format, not Q&A
            if "confession" in cfg["key"]:
                chapters = _parse_wcf_chapters(r.text)
                if not chapters:
                    print(f"    WARNING: no chapters parsed from {fetch_url}")
                    continue
                print(f"    {len(chapters)} chapters found")
                ok = 0
                for i, (title, body) in enumerate(chapters):
                    text = f"{title}\n\n{body}"
                    meta = {
                        "title": cfg["title"],
                        "author": "Westminster Assembly",
                        "date": cfg["date"],
                        "tradition": "Reformed",
                        "source_url": source_url,
                        "chapter": i + 1,
                    }
                    if post(text, cfg["key"], meta, cfg["tags"], dry_run):
                        ok += 1
                        if not dry_run:
                            time.sleep(_DELAY * 0.3)
                print(f"    {ok}/{len(chapters)} posted")
            else:
                pairs = _parse_qa(r.text)
                if not pairs:
                    print(f"    WARNING: no Q&A pairs parsed — URL: {fetch_url}")
                    continue
                print(f"    {len(pairs)} Q&A pairs found")
                ok = 0
                for i, (question, answer) in enumerate(pairs):
                    text = f"Q: {question}\n\nA: {answer}"
                    meta = {
                        "title": cfg["title"],
                        "author": "Westminster Assembly",
                        "date": cfg["date"],
                        "tradition": "Reformed",
                        "source_url": source_url,
                        "qa_number": i + 1,
                    }
                    if post(text, cfg["key"], meta, cfg["tags"], dry_run):
                        ok += 1
                        if not dry_run:
                            time.sleep(_DELAY * 0.3)
                print(f"    {ok}/{len(pairs)} posted")
        except Exception as exc:
            print(f"    ERROR: {exc}")


# ── library of congress — chronicling america ─────────────────────────────────

LOC_QUERIES = [
    ("wisdom_scripture",   "scripture wisdom faith providence"),
    ("community_order",    "community governance council assembly"),
    ("moral_virtue",       "virtue moral philosophy conscience"),
    ("dispensation",       "divine dispensation judgment mercy"),
    ("covenant",           "covenant promise faithfulness"),
]

def ingest_loc(dry_run: bool, max_per_query: int = 25) -> None:
    # Chronicling America moved to www.loc.gov/collections/chronicling-america/
    base = "https://www.loc.gov/collections/chronicling-america/"
    for qkey, query in LOC_QUERIES:
        print(f"\n  [LoC Chronicling America] {query!r}")
        try:
            r = requests.get(base, params={
                "fo": "json",
                "q": query,
                "c": max_per_query,
                "at": "results",
            }, timeout=30, headers=HEADERS)
            r.raise_for_status()
            items = r.json().get("results", [])
            ok = 0
            for item in items:
                # description is a list of OCR text strings
                desc = item.get("description") or []
                raw  = " ".join(desc) if isinstance(desc, list) else str(desc)
                text = re.sub(r'\s+', ' ', raw).strip()[:2500]
                if len(text.split()) < 60:
                    continue
                source_url = item.get("url", "")
                meta = {
                    "title":      item.get("title", ""),
                    "date":       item.get("date", ""),
                    "source_url": source_url,
                    "collection": "Chronicling America, Library of Congress",
                    "query":      query,
                }
                if post(text, f"loc_{qkey}", meta,
                        ["loc", "historical", "primary_source", "chronicling_america"],
                        dry_run):
                    ok += 1
                    if not dry_run:
                        time.sleep(_DELAY * 0.5)
            print(f"    {ok}/{len(items)} posted")
        except Exception as exc:
            print(f"    ERROR: {exc}")

    # Also hit the main LOC JSON API for curated collections
    print("\n  [LoC Collections API]")
    try:
        r = requests.get(
            "https://www.loc.gov/collections/",
            params={"fo": "json", "q": "religion scripture theology", "c": 10, "at": "results"},
            timeout=30, headers=HEADERS
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            print(f"    {len(results)} collections found")
            for item in results:
                title = item.get("title", "")
                desc_raw = item.get("description", "")
                desc = " ".join(desc_raw) if isinstance(desc_raw, list) else str(desc_raw)
                if not title or len(desc.split()) < 20:
                    continue
                source_url = item.get("url", "")
                text = f"{title}\n\n{desc}"
                meta = {"title": title, "source_url": source_url,
                        "collection": "Library of Congress"}
                post(text, "loc_collections", meta,
                     ["loc", "collection_catalog", "institutional"], dry_run)
    except Exception as exc:
        print(f"    LoC Collections API error: {exc}")


# ── internet archive — patristic & theological texts ─────────────────────────
# DigiVatLib blocks automated access (403). Internet Archive has the same
# patristic corpus at scale with an open JSON API and no auth requirement.

ARCHIVE_SEARCHES = [
    ("patristic_fathers",   "apostolic fathers early church patristic",        ["patristic", "early_church", "wisdom"]),
    ("church_fathers",      "church fathers Chrysostom Tertullian Origen",     ["patristic", "church_fathers", "theology"]),
    ("reformed_theology",   "puritan sermon covenant theology",                ["reformed", "puritan", "theology", "wisdom"]),
    ("wisdom_devotional",   "Christian devotional prayer contemplation wisdom", ["devotional", "wisdom", "spiritual_formation"]),
    ("almanac_practical",   "farmers almanac almanack annual practical",       ["almanac", "practical", "agriculture", "astronomy", "weather"]),
    ("moral_philosophy",    "moral philosophy ethics conscience virtue Stoic", ["philosophy", "ethics", "wisdom", "virtue"]),
    ("national_geographic", "National Geographic magazine geography natural history 1888", ["geography", "natural_history", "ecology", "science", "exploration"]),
]

def ingest_vatican(dry_run: bool) -> None:
    # Called "ingest_vatican" for CLI compatibility (--source vatican)
    print()
    base = "https://archive.org/advancedsearch.php"
    for qkey, query, tags in ARCHIVE_SEARCHES:
        print(f"  [Internet Archive] {query!r}")
        if not dry_run:
            _register_atlas(f"archive_{qkey}", {
                "collection": "Internet Archive",
                "query":      query,
                "source_url": f"https://archive.org/search?query={requests.utils.quote(query)}",
                "tags":       tags,
            })
        try:
            r = requests.get(base, params={
                "q": f"{query} mediatype:texts",
                "fl": "identifier,title,description,creator,year",
                "rows": 20,
                "output": "json",
            }, timeout=30, headers=HEADERS)
            r.raise_for_status()
            docs = r.json().get("response", {}).get("docs", [])
            ok = 0
            for doc in docs:
                title = str(doc.get("title") or "")
                desc_raw = doc.get("description") or ""
                desc = " ".join(desc_raw) if isinstance(desc_raw, list) else str(desc_raw)
                desc = re.sub(r'<[^>]+>', ' ', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()
                creator = str(doc.get("creator") or "")
                year    = str(doc.get("year") or "")
                uid     = str(doc.get("identifier") or "")
                source_url = f"https://archive.org/details/{uid}" if uid else ""
                if not title or len(desc.split()) < 20:
                    continue
                text = f"{title}\n\nAuthor: {creator}\nYear: {year}\n\n{desc[:2000]}"
                meta = {
                    "title":      title,
                    "author":     creator,
                    "year":       year,
                    "source_url": source_url,
                    "collection": "Internet Archive",
                    "query":      query,
                }
                if post(text, f"archive_{qkey}", meta, tags, dry_run):
                    ok += 1
                    if not dry_run:
                        time.sleep(_DELAY * 0.5)
            print(f"    {ok}/{len(docs)} posted")
        except Exception as exc:
            print(f"    ERROR: {exc}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    global _DELAY, API_BASE
    parser = argparse.ArgumentParser(
        description="Ingest wisdom sources into Concordance via /capture")
    parser.add_argument(
        "--source",
        choices=["gutenberg", "westminster", "loc", "vatican", "all"],
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print chunks without POSTing")
    parser.add_argument("--reset", action="store_true",
                        help="Clear ingest state — re-ingest everything")
    parser.add_argument("--delay", type=float, default=_DELAY,
                        help=f"Seconds between POSTs (default {_DELAY})")
    parser.add_argument("--api", default=API_BASE,
                        help=f"API base URL (default {API_BASE})")
    args = parser.parse_args()

    _DELAY   = args.delay
    API_BASE = args.api

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("Ingest state cleared.")

    if not args.dry_run:
        try:
            r = requests.get(f"{API_BASE}/health", timeout=5, headers=HEADERS)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            print(f"API healthy at {API_BASE}")
        except Exception as exc:
            print(f"ERROR: API not reachable at {API_BASE}: {exc}")
            print("Start the server: .\\local\\restart_services.ps1")
            sys.exit(1)

    run_all = args.source == "all"
    state_before = len(_load_state().get("ingested", []))

    if run_all or args.source == "gutenberg":
        print("\n=== Gutenberg — Patristic & Wisdom Texts ===")
        ingest_gutenberg(args.dry_run)

    if run_all or args.source == "westminster":
        print("\n=== Westminster Standards ===")
        ingest_westminster(args.dry_run)

    if run_all or args.source == "loc":
        print("\n=== Library of Congress ===")
        ingest_loc(args.dry_run)

    if run_all or args.source == "vatican":
        print("\n=== Vatican Apostolic Library ===")
        ingest_vatican(args.dry_run)

    state_after = len(_load_state().get("ingested", []))
    added = state_after - state_before
    print(f"\n{'='*50}")
    print(f"  Ingested this run : {added}")
    print(f"  Total in state    : {state_after}")
    print(f"  State file        : {STATE_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
