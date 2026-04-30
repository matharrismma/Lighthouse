"""
build_concordance.py — Build concordance.db from morphologically-tagged texts.

Requires the original language git clones:
    git clone https://github.com/openscriptures/morphhb original/hebrew
    git clone https://github.com/morphgnt/sblgnt     original/greek

Builds:
    web/concordance.db
    Schema: concordance(b INTEGER, c INTEGER, v INTEGER,
                        word_pos INTEGER, word TEXT, strongs TEXT)
    Index:  strongs_idx ON concordance(strongs)

Run:
    cd lw/00_source
    python build_concordance.py

After this, Concordance.strongs_verses() and word_study() are fully active.
"""
from __future__ import annotations

import json
import re
import sqlite3
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT    = Path(__file__).parent
HEB_DIR = ROOT / "original" / "hebrew"
GRK_DIR = ROOT / "original" / "greek"
LEX_DIR = ROOT / "original" / "lexicon"
CONC_DB = ROOT / "web" / "concordance.db"

# ---------------------------------------------------------------------------
# Book number maps
# ---------------------------------------------------------------------------

# morphhb uses OSIS book IDs → book number 1-39
HEB_BOOKS = {
    "Gen":1,"Exod":2,"Lev":3,"Num":4,"Deut":5,"Josh":6,"Judg":7,"Ruth":8,
    "1Sam":9,"2Sam":10,"1Kgs":11,"2Kgs":12,"1Chr":13,"2Chr":14,"Ezra":15,
    "Neh":16,"Esth":17,"Job":18,"Ps":19,"Prov":20,"Eccl":21,"Song":22,
    "Isa":23,"Jer":24,"Lam":25,"Ezek":26,"Dan":27,"Hos":28,"Joel":29,
    "Amos":30,"Obad":31,"Jonah":32,"Mic":33,"Nah":34,"Hab":35,"Zeph":36,
    "Hag":37,"Zech":38,"Mal":39,
}

# MorphGNT file prefixes (61-87) → unified book number (40-66, NT order)
GRK_FILE_BOOKS = {
    "61":40,"62":41,"63":42,"64":43,"65":44,"66":45,"67":46,"68":47,
    "69":48,"70":49,"71":50,"72":51,"73":52,"74":53,"75":54,"76":55,
    "77":56,"78":57,"79":58,"80":59,"81":60,"82":61,"83":62,"84":63,
    "85":64,"86":65,"87":66,
}

# ---------------------------------------------------------------------------
# Hebrew parser — morphhb OSIS XML
# ---------------------------------------------------------------------------

OSIS_NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"

def _parse_hebrew_lemma(lemma: str) -> list[str]:
    """
    Extract Strong's numbers from a morphhb lemma attribute.

    Actual formats observed:
        '430'          → ['H430']        (bare number)
        'b/7225'       → ['H7225']       (preposition prefix)
        '1254 a'       → ['H1254']       (disambiguation suffix)
        'c/d/776'      → ['H776']        (multiple prefixes)
        'l'            → []              (particle only, no number)
        '3068+'        → ['H3068']       (dagesh marker)

    Rule: split on '/', take each segment, strip trailing space + letter
    and trailing '+', keep only segments that are purely numeric.
    """
    results = []
    for seg in lemma.split("/"):
        # strip trailing disambiguation: ' a', ' b', ' c', ' d', ' e'
        seg = re.sub(r'\s+[a-e]$', '', seg.strip())
        # strip trailing dagesh marker
        seg = seg.rstrip('+')
        if seg.isdigit():
            results.append(f"H{seg}")
    return results


def _parse_hebrew_book(xml_path: Path, book_num: int, rows: list) -> int:
    """Parse one morphhb XML file, append (b,c,v,pos,word,strongs) rows."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f"  [WARN] parse error in {xml_path.name}: {e}")
        return 0

    root = tree.getroot()
    added = 0

    for verse_el in root.iter(f"{OSIS_NS}verse"):
        osis_id = verse_el.get("osisID", "")
        parts = osis_id.split(".")
        if len(parts) < 3:
            continue
        try:
            c, v = int(parts[1]), int(parts[2])
        except ValueError:
            continue

        word_pos = 0
        for w_el in verse_el.iter(f"{OSIS_NS}w"):
            lemma    = w_el.get("lemma", "")
            word_text = (w_el.text or "").strip()
            for strongs in _parse_hebrew_lemma(lemma):
                rows.append((book_num, c, v, word_pos, word_text, strongs))
                added += 1
            word_pos += 1

    return added


def build_hebrew(rows: list) -> int:
    """Walk all morphhb XML files and collect rows."""
    if not HEB_DIR.exists():
        print(f"  [SKIP] Hebrew source not found at {HEB_DIR}")
        print("         Run: git clone https://github.com/openscriptures/morphhb original/hebrew")
        return 0

    # Find the wlc directory wherever it landed after git clone / Move-Item
    wlc_dirs = list(HEB_DIR.rglob("wlc"))
    if not wlc_dirs:
        print(f"  [SKIP] No 'wlc' subdirectory found under {HEB_DIR}")
        return 0
    wlc = wlc_dirs[0]

    total = 0
    for bk_name, bk_num in sorted(HEB_BOOKS.items(), key=lambda x: x[1]):
        candidates = list(wlc.glob(f"{bk_name}.xml"))
        if not candidates:
            continue
        n = _parse_hebrew_book(candidates[0], bk_num, rows)
        print(f"    {bk_name}: {n:,} tagged words")
        total += n
    return total


# ---------------------------------------------------------------------------
# Greek parser — MorphGNT text files
# ---------------------------------------------------------------------------

def _load_greek_lemma_map() -> dict[str, str]:
    """
    Build lemma → Strong's G number reverse map from strongs_greek.json.

    strongs_greek.json keys are like 'G976'; entries have a 'lemma' field
    containing the Greek lemma string.  We invert this so we can look up
    Strong's from the lemma token in each MorphGNT line.
    """
    lex_path = LEX_DIR / "strongs_greek.json"
    if not lex_path.exists():
        print(f"  [WARN] {lex_path} not found — Greek Strong's lookup disabled")
        return {}
    with open(lex_path, encoding="utf-8") as f:
        data = json.load(f)
    lemma_to_g: dict[str, str] = {}
    for gnum, entry in data.items():
        lemma = entry.get("lemma", "").strip()
        if lemma:
            lemma_to_g[lemma] = gnum
    return lemma_to_g


def build_greek(rows: list) -> int:
    """
    Walk MorphGNT text files and collect rows.

    MorphGNT line format (space-separated, 7 fields):
        BBCCVV  POS  morph  surface  normalized  lemma  lexeme

    Where BB = 01-27 (1-indexed NT book order, 01=Matthew).
    Unified book number = int(BB) + 39 (so Matt=40, Rev=66).

    Strong's G numbers come from a reverse map built from strongs_greek.json
    (the MorphGNT files themselves contain no Strong's numbers).
    """
    if not GRK_DIR.exists():
        print(f"  [SKIP] Greek source not found at {GRK_DIR}")
        print("         Run: git clone https://github.com/morphgnt/sblgnt original/greek")
        return 0

    lemma_to_g = _load_greek_lemma_map()
    if not lemma_to_g:
        print("  [SKIP] No lemma→Strong's map — skipping Greek")
        return 0

    total = 0
    miss  = 0

    for txt_path in sorted(GRK_DIR.rglob("*-morphgnt.txt")):
        m = re.match(r"^(\d{2})", txt_path.name)
        if not m:
            continue
        file_prefix = m.group(1)
        bk_num = GRK_FILE_BOOKS.get(file_prefix)
        if bk_num is None:
            continue

        added = 0
        with open(txt_path, encoding="utf-8") as f:
            for word_pos, line in enumerate(f):
                line = line.rstrip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 6:
                    continue

                ref = parts[0]
                if len(ref) != 6 or not ref.isdigit():
                    continue
                ch = int(ref[2:4])
                vs = int(ref[4:6])

                lemma   = parts[5]          # index 5 = lemma
                strongs = lemma_to_g.get(lemma)
                if strongs is None:
                    miss += 1
                    continue

                word_text = parts[3]        # index 3 = surface form
                rows.append((bk_num, ch, vs, word_pos, word_text, strongs))
                added += 1

        if added:
            print(f"    {txt_path.name}: {added:,} tagged words")
            total += added

    if miss:
        print(f"  [INFO] {miss:,} Greek word occurrences had no Strong's match "
              "(proper nouns, rare forms — expected)")
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 62)
    print("Lighthouse — Build Strong's concordance")
    print("=" * 62)

    CONC_DB.parent.mkdir(parents=True, exist_ok=True)

    rows: list = []

    print("\n[1/2] Hebrew (morphhb OT):")
    h_count = build_hebrew(rows)

    print(f"\n[2/2] Greek (MorphGNT NT):")
    g_count = build_greek(rows)

    if not rows:
        print("\n[ERROR] No rows collected — check that git clones are present.")
        print("Required:")
        print("  git clone https://github.com/openscriptures/morphhb original/hebrew")
        print("  git clone https://github.com/morphgnt/sblgnt     original/greek")
        return

    print(f"\n[BUILD] Writing {len(rows):,} rows to concordance.db …")

    # Build fresh DB in /tmp then copy to avoid OneDrive write issues
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        tmp_path = tf.name

    con = sqlite3.connect(tmp_path)
    con.execute("DROP TABLE IF EXISTS concordance")
    con.execute("""
        CREATE TABLE concordance (
            b INTEGER, c INTEGER, v INTEGER,
            word_pos INTEGER, word TEXT, strongs TEXT
        )
    """)
    con.executemany("INSERT INTO concordance VALUES (?,?,?,?,?,?)", rows)
    con.execute("CREATE INDEX strongs_idx ON concordance(strongs)")
    con.execute("CREATE INDEX bcv_idx    ON concordance(b,c,v)")
    con.commit()
    con.close()

    shutil.copy(tmp_path, str(CONC_DB))
    Path(tmp_path).unlink(missing_ok=True)

    print(f"  [OK]  concordance.db — {len(rows):,} word occurrences")
    print(f"         Hebrew: {h_count:,}  Greek: {g_count:,}")
    print("\nVerify:")
    print("  python -m triangulation.concordance --word G26     # agape")
    print("  python -m triangulation.concordance --word H2617   # chesed")
    print("  python -m triangulation.concordance --study G142   # airo")
    print("=" * 62)


if __name__ == "__main__":
    main()
