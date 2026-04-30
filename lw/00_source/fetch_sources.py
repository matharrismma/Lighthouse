"""
fetch_sources.py — Layer 0 WORD source downloader

Downloads all three sub-layers needed for triangulation:
  1. WEB XML        — locked English translation (christos-c/bible-corpus)
                      Converts XML → SQLite for fast verse lookup
  2. Strong's H     — Hebrew lexicon H1–H8674 (openscriptures/strongs)
  3. Strong's G     — Greek lexicon G1–G5624 (openscriptures/strongs)

Run once from this directory:
    cd lw/00_source
    python fetch_sources.py

Everything lands under:
    web/web.db                           (SQLite, schema: t_web(id,b,c,v,t))
    original/lexicon/strongs_hebrew.json
    original/lexicon/strongs_greek.json

The original language texts (morphhb, MorphGNT) require separate git clones.
See original/README.md for those instructions.

All sources are public domain. No API keys required.
"""

import json
import hashlib
import re
import sqlite3
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Verified source URLs (confirmed available 2026-04-30)
# ---------------------------------------------------------------------------

SOURCES = {
    "web_xml": {
        "url": "https://raw.githubusercontent.com/christos-c/bible-corpus/master/bibles/English-WEB.xml",
        "dest": ROOT / "web" / "_web_raw.xml",
        "desc": "World English Bible — XML (christos-c/bible-corpus, ~5.4MB)",
    },
    "strongs_hebrew_js": {
        "url": "https://raw.githubusercontent.com/openscriptures/strongs/master/hebrew/strongs-hebrew-dictionary.js",
        "dest": ROOT / "original" / "lexicon" / "_strongs_hebrew_raw.js",
        "desc": "Strong's Hebrew Dictionary — JS source (openscriptures/strongs)",
    },
    "strongs_greek_js": {
        "url": "https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongs-greek-dictionary.js",
        "dest": ROOT / "original" / "lexicon" / "_strongs_greek_raw.js",
        "desc": "Strong's Greek Dictionary — JS source (openscriptures/strongs)",
    },
}

# Book name → (number, testament) — used when XML uses book names
BOOK_NAMES_TO_NUM = {
    "genesis": 1, "exodus": 2, "leviticus": 3, "numbers": 4, "deuteronomy": 5,
    "joshua": 6, "judges": 7, "ruth": 8, "1 samuel": 9, "2 samuel": 10,
    "1 kings": 11, "2 kings": 12, "1 chronicles": 13, "2 chronicles": 14,
    "ezra": 15, "nehemiah": 16, "esther": 17, "job": 18, "psalms": 19, "psalm": 19,
    "proverbs": 20, "ecclesiastes": 21, "song of solomon": 22, "isaiah": 23,
    "jeremiah": 24, "lamentations": 25, "ezekiel": 26, "daniel": 27,
    "hosea": 28, "joel": 29, "amos": 30, "obadiah": 31, "jonah": 32,
    "micah": 33, "nahum": 34, "habakkuk": 35, "zephaniah": 36, "haggai": 37,
    "zechariah": 38, "malachi": 39,
    "matthew": 40, "mark": 41, "luke": 42, "john": 43, "acts": 44,
    "romans": 45, "1 corinthians": 46, "2 corinthians": 47, "galatians": 48,
    "ephesians": 49, "philippians": 50, "colossians": 51,
    "1 thessalonians": 52, "2 thessalonians": 53, "1 timothy": 54,
    "2 timothy": 55, "titus": 56, "philemon": 57, "hebrews": 58,
    "james": 59, "1 peter": 60, "2 peter": 61,
    "1 john": 62, "2 john": 63, "3 john": 64, "jude": 65, "revelation": 66,
    # Common short forms
    "song of songs": 22, "song": 22,
}

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def _download(key: str, info: dict) -> bool:
    dest = info["dest"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        size = dest.stat().st_size
        print(f"  [EXISTS] {dest.name}  ({size:,} bytes) — skipping re-download")
        return True

    print(f"  [FETCH]  {info['desc']}")
    print(f"           {info['url']}")

    try:
        req = urllib.request.Request(
            info["url"],
            headers={"User-Agent": "Lighthouse-SourceFetcher/1.0 (public-domain)"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()

        with open(dest, "wb") as f:
            f.write(data)

        print(f"           → {dest.name}  ({len(data):,} bytes)")
        return True

    except urllib.error.HTTPError as e:
        print(f"  [ERROR]  HTTP {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"  [ERROR]  {e}")
        return False


# ---------------------------------------------------------------------------
# Build WEB SQLite from XML
# ---------------------------------------------------------------------------

def _build_web_sqlite() -> bool:
    xml_path = ROOT / "web" / "_web_raw.xml"
    db_path  = ROOT / "web" / "web.db"

    if not xml_path.exists():
        print("  [SKIP] XML source not present — cannot build SQLite")
        return False

    if db_path.exists():
        print(f"  [EXISTS] web.db — skipping rebuild")
        return True

    print("  [BUILD] Parsing WEB XML → SQLite …")

    try:
        tree = ET.parse(xml_path)
        root_el = tree.getroot()
    except ET.ParseError as e:
        print(f"  [ERROR] XML parse failed: {e}")
        return False

    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS t_web (id INTEGER PRIMARY KEY, b INTEGER, c INTEGER, v INTEGER, t TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_bcv ON t_web (b, c, v)")

    rows = []
    row_id = 1

    # christos-c/bible-corpus XML schema:
    #   <corpus> or <bible> root
    #     <book> or <b> with name/n attribute
    #       <chapter> or <c> with n attribute
    #         <verse> or <v> with n attribute
    #           text content (may contain <seg> children)

    books = (root_el.findall("book") or root_el.findall("b") or
             root_el.findall(".//book") or root_el.findall(".//b"))

    if not books:
        # Try alternate: flat verse list with attributes
        verses = root_el.findall(".//verse") or root_el.findall(".//v")
        for v_el in verses:
            bnum = int(v_el.get("book", v_el.get("b", 0)))
            cnum = int(v_el.get("chapter", v_el.get("c", 0)))
            vnum = int(v_el.get("verse", v_el.get("v", 0)))
            text = _collect_text(v_el)
            if bnum and cnum and vnum and text:
                rows.append((row_id, bnum, cnum, vnum, text))
                row_id += 1
    else:
        for b_el in books:
            book_name = (b_el.get("name") or b_el.get("n") or "").lower().strip()
            bnum = BOOK_NAMES_TO_NUM.get(book_name, 0)
            if not bnum:
                # Try numeric id attribute
                try:
                    bnum = int(b_el.get("id", b_el.get("num", 0)))
                except (TypeError, ValueError):
                    pass
            if not bnum:
                print(f"  [WARN] Could not resolve book: '{book_name}' — skipping")
                continue

            chapters = b_el.findall("chapter") or b_el.findall("c")
            for c_el in chapters:
                try:
                    cnum = int(c_el.get("n") or c_el.get("num") or 0)
                except (TypeError, ValueError):
                    continue

                verses_el = c_el.findall("verse") or c_el.findall("v")
                for v_el in verses_el:
                    try:
                        vnum = int(v_el.get("n") or v_el.get("num") or 0)
                    except (TypeError, ValueError):
                        continue
                    text = _collect_text(v_el)
                    if vnum and text:
                        rows.append((row_id, bnum, cnum, vnum, text))
                        row_id += 1

    if len(rows) < 20000:
        print(f"  [WARN] Only {len(rows)} verses found — XML structure may differ from expected.")
        print("         Inspect web/_web_raw.xml and adjust parser if needed.")
        if not rows:
            con.close()
            db_path.unlink(missing_ok=True)
            return False

    con.executemany("INSERT INTO t_web VALUES (?,?,?,?,?)", rows)
    con.commit()
    con.close()

    print(f"  [OK]   web.db — {len(rows):,} verses written")
    return len(rows) > 20000


def _collect_text(el) -> str:
    """Collect all text content from an element, including tails of children."""
    parts = []
    if el.text:
        parts.append(el.text.strip())
    for child in el:
        if child.text:
            parts.append(child.text.strip())
        if child.tail:
            parts.append(child.tail.strip())
    text = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Build Strong's JSON from JS source
# ---------------------------------------------------------------------------

def _build_strongs_json(js_path: Path, json_path: Path, label: str) -> bool:
    if not js_path.exists():
        print(f"  [SKIP] JS source not present for {label}")
        return False

    if json_path.exists():
        print(f"  [EXISTS] {json_path.name} — skipping rebuild")
        return True

    print(f"  [BUILD] Parsing {label} JS → JSON …")

    try:
        content = js_path.read_text(encoding="utf-8")
        # The JS file is a comment block followed by a plain object literal
        # Find the first '{' that starts the data
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])

        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

        print(f"  [OK]   {json_path.name} — {len(data):,} entries")
        return True

    except Exception as e:
        print(f"  [ERROR] {label}: {e}")
        return False


# ---------------------------------------------------------------------------
# Checksum + manifest
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_manifest(results: dict):
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "layers": {},
        "fetch_results": results,
    }
    for key, path in [
        ("WEB_sqlite",      ROOT / "web" / "web.db"),
        ("strongs_hebrew",  ROOT / "original" / "lexicon" / "strongs_hebrew.json"),
        ("strongs_greek",   ROOT / "original" / "lexicon" / "strongs_greek.json"),
    ]:
        if path.exists():
            manifest["layers"][key] = {
                "file": str(path.relative_to(ROOT)),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }

    mpath = ROOT / "source_manifest.json"
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  [MANIFEST] {mpath.name} written")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 62)
    print("Lighthouse — Layer 0 WORD source fetcher")
    print("=" * 62)
    results = {}

    # 1. WEB
    print("\n[1/3] World English Bible  (locked English layer)")
    ok = _download("web_xml", SOURCES["web_xml"])
    if ok:
        ok = _build_web_sqlite()
    results["WEB"] = "ok" if ok else "failed"

    # 2. Strong's Hebrew
    print("\n[2/3] Strong's Hebrew Lexicon  (OT triangulation key)")
    ok = _download("strongs_hebrew_js", SOURCES["strongs_hebrew_js"])
    if ok:
        ok = _build_strongs_json(
            ROOT / "original" / "lexicon" / "_strongs_hebrew_raw.js",
            ROOT / "original" / "lexicon" / "strongs_hebrew.json",
            "Hebrew H1–H8674",
        )
    results["strongs_H"] = "ok" if ok else "failed"

    # 3. Strong's Greek
    print("\n[3/3] Strong's Greek Lexicon  (NT triangulation key)")
    ok = _download("strongs_greek_js", SOURCES["strongs_greek_js"])
    if ok:
        ok = _build_strongs_json(
            ROOT / "original" / "lexicon" / "_strongs_greek_raw.js",
            ROOT / "original" / "lexicon" / "strongs_greek.json",
            "Greek G1–G5624",
        )
    results["strongs_G"] = "ok" if ok else "failed"

    _write_manifest(results)

    # Summary
    print("\n" + "=" * 62)
    all_ok = all(v == "ok" for v in results.values())
    if all_ok:
        print("All sources ready.")
        print("\nVerify:")
        print("  python -m triangulation.lookup --status")
        print("  python -m triangulation.lookup --ref Jn3:16")
        print("  python -m triangulation.lookup --word G26     # agape")
        print("  python -m triangulation.lookup --word H430    # Elohim")
        print("\nTriangulate:")
        print("  python -m triangulation.drift_check \\")
        print("    --ref Jn15:2 \\")
        print("    --claim \"branches that don't bear fruit are destroyed\" \\")
        print("    --strongs G142")
        print("\nOptional — clone original language texts:")
        print("  git clone https://github.com/openscriptures/morphhb original/hebrew")
        print("  git clone https://github.com/morphgnt/sblgnt original/greek")
    else:
        failed = [k for k, v in results.items() if v != "ok"]
        print(f"Failed: {failed}")
        print("Check your network connection and retry.")
        print("All sources are public domain — no keys required.")
    print("=" * 62)


if __name__ == "__main__":
    main()
