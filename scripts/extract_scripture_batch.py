"""Batch-extract WEB Bible substrate into typed packet stores.

Generates four new substrates, all from lw/00_source/web/web.db:
  - data/ecclesiastes/verses.jsonl   (222 per-verse packets)
  - data/james/verses.jsonl          (108 per-verse packets)
  - data/psalms/chapters.jsonl       (150 per-chapter packets)
  - data/sermon_on_mount/units.jsonl (~20 pericope packets)

Shapes:
  per-verse: same as Proverbs (text, axes, themes per verse)
  per-chapter (Psalms): chapter title + full text + verse count
  per-pericope (SoM): teaching unit with verse range + summary tag
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
WEB_DB = REPO / "lw" / "00_source" / "web" / "web.db"

# Book numbers in WEB Protestant order
BOOK_ECCL = 21
BOOK_PSALMS = 19
BOOK_JAMES = 59
BOOK_MATTHEW = 40

# Reuse Proverbs axis + theme patterns
sys.path.insert(0, str(REPO / "scripts"))
from extract_proverbs import _AXIS_PATTERNS, _THEME_PATTERNS, derive_axes, derive_themes


def _connect() -> sqlite3.Connection:
    if not WEB_DB.exists():
        print(f"WEB DB not found: {WEB_DB}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(WEB_DB))


def _verses(con: sqlite3.Connection, book: int) -> list[tuple[int, int, str]]:
    return list(con.execute(
        "select c, v, t from t_web where b = ? order by c, v", (book,)
    ))


def _chapters(con: sqlite3.Connection, book: int) -> dict[int, list[tuple[int, str]]]:
    out: dict[int, list[tuple[int, str]]] = {}
    for c, v, t in _verses(con, book):
        out.setdefault(c, []).append((v, t))
    return out


# ── Per-verse extractors (Ecclesiastes + James) ─────────────────────────

def extract_per_verse(book: int, book_name: str, slug: str, out_path: Path) -> int:
    con = _connect()
    rows = _verses(con, book)
    con.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for c, v, t in rows:
            text = (t or "").strip()
            if not text:
                continue
            ref = f"{book_name} {c}:{v}"
            packet = {
                "id": f"{slug}_{c:02d}_{v:02d}",
                "kind": slug,  # ecclesiastes | james
                "reference": ref,
                "book": book_name,
                "chapter": c,
                "verse": v,
                "text": text,
                "axes": derive_axes(text),
                "themes": derive_themes(text),
                "source": "World English Bible",
                "license": "Public Domain",
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


# ── Per-chapter extractor (Psalms) ──────────────────────────────────────

# Approximate titles for each psalm — these are not in the WEB DB but are
# commonly known and useful for retrieval. Mapping is optional; psalms
# without a recognized title get a generic "Psalm N" label.
_PSALM_TITLES = {
    1: "The Two Paths", 8: "Crowned with Glory", 19: "The Heavens Declare",
    22: "My God, My God", 23: "The Shepherd Psalm", 27: "The Lord Is My Light",
    32: "Blessed is He Whose Sin is Forgiven", 34: "I Will Bless the LORD",
    37: "Fret Not Thyself", 42: "As the Hart Pants", 46: "God Is Our Refuge",
    51: "A Broken and Contrite Heart", 63: "My Soul Thirsteth", 73: "Surely God Is Good",
    84: "How Lovely Is Thy Dwelling Place", 90: "From Everlasting to Everlasting",
    91: "He That Dwelleth in the Secret Place", 100: "Make a Joyful Noise",
    103: "Bless the LORD, O My Soul", 107: "Give Thanks to the LORD",
    110: "The LORD Said Unto My Lord", 116: "I Love the LORD",
    117: "Praise the LORD All Nations", 118: "His Mercy Endureth Forever",
    119: "Thy Word Is a Lamp", 121: "I Lift Mine Eyes",
    127: "Except the LORD Build the House", 130: "Out of the Depths",
    133: "Behold How Good and Pleasant", 139: "Thou Hast Searched Me",
    145: "Great Is the LORD", 150: "Praise Ye the LORD",
}


def extract_psalms(out_path: Path) -> int:
    con = _connect()
    chapters = _chapters(con, BOOK_PSALMS)
    con.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for c in sorted(chapters.keys()):
            verses = chapters[c]
            full_text = " ".join(t for _, t in verses)
            packet = {
                "id": f"ps_{c:03d}",
                "kind": "psalm",
                "reference": f"Psalm {c}",
                "book": "Psalms",
                "chapter": c,
                "title": _PSALM_TITLES.get(c, f"Psalm {c}"),
                "verse_count": len(verses),
                "text": full_text,
                "axes": derive_axes(full_text),
                "themes": derive_themes(full_text),
                "source": "World English Bible",
                "license": "Public Domain",
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


# ── Per-pericope extractor (Sermon on the Mount, Mt 5-7) ────────────────

# Canonical pericope boundaries with names and primary axis tags
SOM_PERICOPES = [
    ("5:3-12",   "The Beatitudes",                  ["authority_trust", "metabolism"]),
    ("5:13-16",  "Salt and Light",                  ["authority_trust", "information_encoding"]),
    ("5:17-20",  "The Law Fulfilled",               ["authority_trust", "information_encoding"]),
    ("5:21-26",  "Anger and Reconciliation",        ["authority_trust", "metabolism"]),
    ("5:27-30",  "Lust and the Heart",              ["physical_substance", "authority_trust"]),
    ("5:31-32",  "Divorce",                         ["authority_trust", "metabolism"]),
    ("5:33-37",  "Oaths and Plain Speech",          ["information_encoding", "authority_trust"]),
    ("5:38-42",  "Retaliation",                     ["authority_trust", "conservation_balance"]),
    ("5:43-48",  "Love Your Enemies",               ["authority_trust", "metabolism"]),
    ("6:1-4",    "Giving in Secret",                ["authority_trust", "conservation_balance"]),
    ("6:5-15",   "The Lord's Prayer",               ["authority_trust", "information_encoding"]),
    ("6:16-18",  "Fasting in Secret",               ["authority_trust", "metabolism"]),
    ("6:19-24",  "Treasures in Heaven; One Master", ["conservation_balance", "authority_trust"]),
    ("6:25-34",  "Do Not Worry",                    ["time_sequence", "authority_trust"]),
    ("7:1-6",    "Do Not Judge; Cast Not Pearls",   ["authority_trust", "reasoning"]),
    ("7:7-12",   "Ask, Seek, Knock; The Golden Rule",["authority_trust", "time_sequence"]),
    ("7:13-14",  "The Narrow Gate",                 ["authority_trust", "time_sequence"]),
    ("7:15-20",  "False Prophets",                  ["authority_trust", "information_encoding"]),
    ("7:21-23",  "True and False Disciples",        ["authority_trust", "reasoning"]),
    ("7:24-29",  "Wise and Foolish Builders",       ["authority_trust", "physical_substance"]),
]


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def extract_sermon_on_mount(out_path: Path) -> int:
    con = _connect()
    cur = con.cursor()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for idx, (ref_range, title, axes) in enumerate(SOM_PERICOPES, start=1):
            ch_str, range_str = ref_range.split(":")
            chapter = int(ch_str)
            start_v, end_v = [int(x) for x in range_str.split("-")]
            verses = list(cur.execute(
                "select v, t from t_web where b = ? and c = ? and v between ? and ? order by v",
                (BOOK_MATTHEW, chapter, start_v, end_v)
            ))
            text = " ".join(t for _, t in verses)
            packet = {
                "id": f"som_{idx:02d}_{_slugify(title)[:30]}",
                "kind": "sermon_on_mount",
                "reference": f"Matthew {ref_range}",
                "title": title,
                "chapter": chapter,
                "verse_start": start_v,
                "verse_end": end_v,
                "verse_count": len(verses),
                "text": text,
                "axes": axes + [a for a in derive_axes(text) if a not in axes],
                "themes": derive_themes(text),
                "source": "World English Bible",
                "license": "Public Domain",
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    con.close()
    return written


def main():
    n_eccl = extract_per_verse(BOOK_ECCL, "Ecclesiastes", "ecclesiastes",
                                REPO / "data" / "ecclesiastes" / "verses.jsonl")
    print(f"Ecclesiastes: {n_eccl} verses")

    n_jas = extract_per_verse(BOOK_JAMES, "James", "james",
                               REPO / "data" / "james" / "verses.jsonl")
    print(f"James: {n_jas} verses")

    n_ps = extract_psalms(REPO / "data" / "psalms" / "chapters.jsonl")
    print(f"Psalms: {n_ps} chapters")

    n_som = extract_sermon_on_mount(REPO / "data" / "sermon_on_mount" / "units.jsonl")
    print(f"Sermon on the Mount: {n_som} pericopes")

    print(f"TOTAL new packets: {n_eccl + n_jas + n_ps + n_som}")


if __name__ == "__main__":
    main()
