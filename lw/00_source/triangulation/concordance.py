"""
triangulation/concordance.py — Strong's Concordance

The concordance maps Strong's number → every verse where that word appears.
This is the full-corpus word study tool — the mechanism that prevents drift
by constraining interpretation to the word's actual range of use across all
of scripture, not just a single cited verse.

Two layers:
  1. English word index  — built from WEB text (available now)
  2. Strong's concordance — built from morphhb / MorphGNT (run after git clone)

Usage:
    from triangulation.concordance import Concordance
    c = Concordance()

    # Find every WEB verse containing a word
    c.english_search("lovingkindness")

    # After running build_concordance.py:
    c.strongs_verses("G142")    # every NT verse using airo
    c.strongs_verses("H2617")   # every OT verse using chesed

    # Full word study
    c.word_study("G26")         # agape — definition + all verses

CLI:
    python -m triangulation.concordance --word G26
    python -m triangulation.concordance --english lovingkindness
    python -m triangulation.concordance --study H430
"""

from __future__ import annotations

import json
import re
import sqlite3
import argparse
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent

WEB_DB       = ROOT / "web" / "web.db"
STRONGS_H    = ROOT / "original" / "lexicon" / "strongs_hebrew.json"
STRONGS_G    = ROOT / "original" / "lexicon" / "strongs_greek.json"
CONC_DB      = ROOT / "web" / "concordance.db"   # built by build_concordance.py

BOOK_NAMES = {
    1:"Genesis",2:"Exodus",3:"Leviticus",4:"Numbers",5:"Deuteronomy",
    6:"Joshua",7:"Judges",8:"Ruth",9:"1 Samuel",10:"2 Samuel",
    11:"1 Kings",12:"2 Kings",13:"1 Chronicles",14:"2 Chronicles",
    15:"Ezra",16:"Nehemiah",17:"Esther",18:"Job",19:"Psalms",
    20:"Proverbs",21:"Ecclesiastes",22:"Song of Solomon",23:"Isaiah",
    24:"Jeremiah",25:"Lamentations",26:"Ezekiel",27:"Daniel",
    28:"Hosea",29:"Joel",30:"Amos",31:"Obadiah",32:"Jonah",
    33:"Micah",34:"Nahum",35:"Habakkuk",36:"Zephaniah",37:"Haggai",
    38:"Zechariah",39:"Malachi",
    40:"Matthew",41:"Mark",42:"Luke",43:"John",44:"Acts",
    45:"Romans",46:"1 Corinthians",47:"2 Corinthians",48:"Galatians",
    49:"Ephesians",50:"Philippians",51:"Colossians",
    52:"1 Thessalonians",53:"2 Thessalonians",54:"1 Timothy",
    55:"2 Timothy",56:"Titus",57:"Philemon",58:"Hebrews",
    59:"James",60:"1 Peter",61:"2 Peter",
    62:"1 John",63:"2 John",64:"3 John",65:"Jude",66:"Revelation",
}


class Concordance:
    """
    Strong's Concordance — word → all verses.

    The core anti-drift tool. A word's meaning is not determined by one verse
    in isolation — it is constrained by every verse where that word appears.
    """

    def __init__(self):
        self._web: Optional[sqlite3.Connection] = None
        self._conc: Optional[sqlite3.Connection] = None
        self._h: Optional[dict] = None
        self._g: Optional[dict] = None

    def _get_web(self):
        if self._web is None and WEB_DB.exists():
            self._web = sqlite3.connect(str(WEB_DB))
        return self._web

    def _get_conc(self):
        if self._conc is None and CONC_DB.exists():
            self._conc = sqlite3.connect(str(CONC_DB))
        return self._conc

    def _get_lex(self, prefix: str) -> Optional[dict]:
        if prefix == "H":
            if self._h is None and STRONGS_H.exists():
                with open(STRONGS_H, encoding="utf-8") as f:
                    self._h = json.load(f)
            return self._h
        if self._g is None and STRONGS_G.exists():
            with open(STRONGS_G, encoding="utf-8") as f:
                self._g = json.load(f)
        return self._g

    def _lex_entry(self, strongs_num: str) -> Optional[dict]:
        prefix = strongs_num[0].upper()
        key = strongs_num[1:].lstrip("0") or "0"
        lex = self._get_lex(prefix)
        if lex is None:
            return None
        for pad in (key, key.zfill(4), key.zfill(5)):
            entry = lex.get(prefix + pad)
            if entry:
                return entry
        return None

    def _row_to_ref(self, b: int, c: int, v: int, t: str) -> dict:
        return {
            "ref": f"{BOOK_NAMES.get(b, str(b))} {c}:{v}",
            "book_num": b,
            "chapter": c,
            "verse": v,
            "text": t,
        }

    # ------------------------------------------------------------------
    # English word search (WEB full-text, available immediately)
    # ------------------------------------------------------------------

    def english_search(self, word: str, whole_word: bool = True, limit: int = 50) -> dict:
        """
        Find all WEB verses containing an English word or phrase.

        whole_word=True uses word-boundary matching (slower but precise).
        """
        db = self._get_web()
        if db is None:
            return {"status": "source_missing", "detail": "Run fetch_sources.py first"}

        if whole_word:
            pattern = f"% {word} %"
            rows = db.execute(
                "SELECT b,c,v,t FROM t_web WHERE ' '||lower(t)||' ' LIKE ?  LIMIT ?",
                (f"% {word.lower()} %", limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT b,c,v,t FROM t_web WHERE lower(t) LIKE ? LIMIT ?",
                (f"%{word.lower()}%", limit)
            ).fetchall()

        return {
            "query": word,
            "count": len(rows),
            "results": [self._row_to_ref(b, c, v, t) for b, c, v, t in rows],
            "layer": "WEB English",
            "note": "For original-language word studies, use strongs_verses() after running build_concordance.py",
        }

    # ------------------------------------------------------------------
    # Strong's concordance (requires concordance.db from build_concordance.py)
    # ------------------------------------------------------------------

    def strongs_verses(self, strongs_num: str, limit: int = 200) -> dict:
        """
        Return every verse in scripture where this Strong's word appears.

        Requires build_concordance.py to have been run after cloning
        morphhb (Hebrew) and MorphGNT (Greek) into original/hebrew and original/greek.
        """
        strongs_num = strongs_num.strip().upper()
        conc = self._get_conc()

        if conc is None:
            # Concordance DB not built yet — explain what to do
            entry = self._lex_entry(strongs_num)
            return {
                "strongs": strongs_num,
                "status": "concordance_not_built",
                "definition": entry,
                "detail": (
                    "The Strong's concordance (word → verses) requires the "
                    "morphologically-tagged original language texts. "
                    "Run these two commands to clone them, then run build_concordance.py:\n"
                    "  git clone https://github.com/openscriptures/morphhb "
                    "lw/00_source/original/hebrew\n"
                    "  git clone https://github.com/morphgnt/sblgnt "
                    "lw/00_source/original/greek\n"
                    "  cd lw/00_source && python build_concordance.py"
                ),
            }

        rows = conc.execute(
            "SELECT b, c, v, word_pos, word FROM concordance WHERE strongs=? ORDER BY b,c,v LIMIT ?",
            (strongs_num, limit)
        ).fetchall()

        if not rows:
            return {"strongs": strongs_num, "status": "not_found", "count": 0}

        web = self._get_web()
        results = []
        for b, c, v, pos, word in rows:
            verse_text = ""
            if web:
                row = web.execute("SELECT t FROM t_web WHERE b=? AND c=? AND v=?", (b, c, v)).fetchone()
                verse_text = row[0] if row else ""
            results.append({
                "ref": f"{BOOK_NAMES.get(b, str(b))} {c}:{v}",
                "word_position": pos,
                "original_word": word,
                "web_text": verse_text,
            })

        entry = self._lex_entry(strongs_num)
        return {
            "strongs": strongs_num,
            "definition": entry,
            "occurrence_count": len(results),
            "verses": results,
            "status": "ok",
            "drift_note": (
                f"This word ({strongs_num}) appears in {len(results)} verses. "
                f"Any interpretation must be consistent with how the word is used "
                f"across ALL of these occurrences, not just one."
            ),
        }

    # ------------------------------------------------------------------
    # Full word study — definition + all verses
    # ------------------------------------------------------------------

    def word_study(self, strongs_num: str) -> dict:
        """
        Complete word study: definition + all verses + drift guidance.

        This is the primary anti-drift tool. Run this before accepting
        any interpretation of a verse that hinges on a specific word.
        """
        strongs_num = strongs_num.strip().upper()
        entry = self._lex_entry(strongs_num)

        result = {
            "strongs": strongs_num,
            "word": entry.get("lemma", entry.get("word", "")) if entry else "",
            "transliteration": entry.get("translit", entry.get("xlit", "")) if entry else "",
            "definition": entry.get("strongs_def", entry.get("kjv_def", "")) if entry else "",
            "derivation": entry.get("derivation", "") if entry else "",
        }

        if entry is None:
            result["status"] = "not_in_lexicon"
            return result

        # Add verse occurrences
        conc_result = self.strongs_verses(strongs_num)
        result.update(conc_result)
        result["study_complete"] = conc_result.get("status") == "ok"

        return result

    def ready(self) -> dict:
        return {
            "web_sqlite": WEB_DB.exists(),
            "concordance_db": CONC_DB.exists(),
            "strongs_hebrew": STRONGS_H.exists(),
            "strongs_greek": STRONGS_G.exists(),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Strong's Concordance — word → all verses")
    parser.add_argument("--word", help="Strong's number, e.g. G26 or H430")
    parser.add_argument("--english", help="English word to search in WEB text")
    parser.add_argument("--study", help="Full word study (definition + all verses)")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    c = Concordance()

    if args.status:
        print(json.dumps(c.ready(), indent=2))
    elif args.word:
        print(json.dumps(c.strongs_verses(args.word), indent=2, ensure_ascii=False))
    elif args.english:
        print(json.dumps(c.english_search(args.english), indent=2, ensure_ascii=False))
    elif args.study:
        print(json.dumps(c.word_study(args.study), indent=2, ensure_ascii=False))
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python -m triangulation.concordance --english lovingkindness")
        print("  python -m triangulation.concordance --word G26      # agape")
        print("  python -m triangulation.concordance --word H2617    # chesed")
        print("  python -m triangulation.concordance --study G142    # airo — lift/take away")
        print("  python -m triangulation.concordance --status")


import json

if __name__ == "__main__":
    main()
