"""original_language.py — Scripture in the original first.

Standing rule (Matt 2026-06-07): original language first; WEB is the translation
vehicle; the goal is the original intent; on any confusion include the original
word and its specific definition.

This is the one reusable capability every Scripture surface uses to obey that
rule. Given a reference, it returns the original-language words (Greek MorphGNT
for the NT) with each word's lemma and — where confidently matched — its Strong's
lexical definition. The original word is ALWAYS returned (100% reliable from
MorphGNT); the definition is attached where the lemma bridges to Strong's, and
the theologically load-bearing words are curated so they are never wrong. Words
without a confident match return their original form with definition=null rather
than a guessed gloss.

NT (Greek, MorphGNT) and OT (Hebrew, OSHB/WLC + strongs_hebrew) are both wired.

Sources:
  lw/00_source/original/greek/greek/<NN>-<Abbr>-morphgnt.txt   (MorphGNT, NT)
  lw/00_source/original/lexicon/strongs_greek.json            (Strong's Greek)
  lw/00_source/original/hebrew/hebrew/wlc/<Stem>.xml          (OSHB/WLC, OT)
  lw/00_source/original/lexicon/strongs_hebrew.json           (Strong's Hebrew)

The OSHB OSIS files give the Strong's number directly on each word's lemma
attribute (e.g. lemma="b/7225" -> H7225, prefixes b/c/d/l stripped), so the
Hebrew bridge to Strong's is by key, not by lemma-matching.
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
GREEK_DIR = REPO / "lw" / "00_source" / "original" / "greek" / "greek"
STRONGS_GREEK = REPO / "lw" / "00_source" / "original" / "lexicon" / "strongs_greek.json"
HEBREW_DIR = REPO / "lw" / "00_source" / "original" / "hebrew" / "hebrew" / "wlc"
STRONGS_HEBREW = REPO / "lw" / "00_source" / "original" / "lexicon" / "strongs_hebrew.json"

# Normalized book name -> MorphGNT book number (01-27 = Matthew..Revelation).
_NT_BOOKS = {b: i + 1 for i, b in enumerate([
    "matthew", "mark", "luke", "john", "acts", "romans", "1 corinthians",
    "2 corinthians", "galatians", "ephesians", "philippians", "colossians",
    "1 thessalonians", "2 thessalonians", "1 timothy", "2 timothy", "titus",
    "philemon", "hebrews", "james", "1 peter", "2 peter", "1 john", "2 john",
    "3 john", "jude", "revelation",
])}

# Normalized OT book name -> OSHB/WLC OSIS file stem (also the osisID prefix).
_OT_BOOKS = {
    "genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num",
    "deuteronomy": "Deut", "joshua": "Josh", "judges": "Judg", "ruth": "Ruth",
    "1 samuel": "1Sam", "2 samuel": "2Sam", "1 kings": "1Kgs", "2 kings": "2Kgs",
    "1 chronicles": "1Chr", "2 chronicles": "2Chr", "ezra": "Ezra",
    "nehemiah": "Neh", "esther": "Esth", "job": "Job", "psalm": "Ps",
    "psalms": "Ps", "proverbs": "Prov", "ecclesiastes": "Eccl",
    "song of solomon": "Song", "song of songs": "Song", "song": "Song",
    "isaiah": "Isa", "jeremiah": "Jer", "lamentations": "Lam", "ezekiel": "Ezek",
    "daniel": "Dan", "hosea": "Hos", "joel": "Joel", "amos": "Amos",
    "obadiah": "Obad", "jonah": "Jonah", "micah": "Mic", "nahum": "Nah",
    "habakkuk": "Hab", "zephaniah": "Zeph", "haggai": "Hag", "zechariah": "Zech",
    "malachi": "Mal",
}

# Curated lemma -> Strong's key, for load-bearing words whose MorphGNT lemma form
# differs from Strong's dictionary form (verified by hand). Keyed by normalized
# (accent-stripped, lowercased) MorphGNT lemma.
_CURATED = {
    "συνιστημι": "G4921",   # Col 1:17 "hold together"
    "συνιστανω": "G4921",
    "φερω": "G5342",        # Heb 1:3 "upholding/bearing"
}

_LOCK = threading.Lock()
_strongs_cache: Dict[str, Any] = {"by_key": None, "by_lemma": None}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def _strongs():
    if _strongs_cache["by_key"] is not None:
        return _strongs_cache["by_key"], _strongs_cache["by_lemma"]
    with _LOCK:
        try:
            by_key = json.loads(STRONGS_GREEK.read_text(encoding="utf-8"))
        except Exception:
            by_key = {}
        by_lemma: Dict[str, str] = {}
        for k, e in by_key.items():
            lem = _norm((e or {}).get("lemma", ""))
            if lem and lem not in by_lemma:
                by_lemma[lem] = k
        _strongs_cache["by_key"] = by_key
        _strongs_cache["by_lemma"] = by_lemma
        return by_key, by_lemma


def _morphgnt_file(booknum: int) -> Optional[Path]:
    if not GREEK_DIR.exists():
        return None
    hits = list(GREEK_DIR.glob(f"{booknum + 60}-*-morphgnt.txt"))
    return hits[0] if hits else None


def _strongs_for_lemma(lemma: str) -> Optional[dict]:
    by_key, by_lemma = _strongs()
    n = _norm(lemma)
    key = _CURATED.get(n) or by_lemma.get(n)
    if not key:
        return None
    e = by_key.get(key) or {}
    return {
        "strongs": key,
        "translit": e.get("translit"),
        "definition": e.get("strongs_def"),
        "kjv": e.get("kjv_def"),
    }


# ---- Hebrew (OSHB/WLC) ------------------------------------------------------
_strongs_heb_cache: Dict[str, Any] = {"by_key": None}
_WORD_RE = re.compile(r"<w\b([^>]*)>(.*?)</w>", re.DOTALL)
_LEMMA_RE = re.compile(r'lemma="([^"]*)"')
_MORPH_RE = re.compile(r'morph="([^"]*)"')
_TAG_RE = re.compile(r"<[^>]+>")
_NUM_RE = re.compile(r"\d+")


def _strongs_hebrew():
    if _strongs_heb_cache["by_key"] is not None:
        return _strongs_heb_cache["by_key"]
    with _LOCK:
        try:
            by_key = json.loads(STRONGS_HEBREW.read_text(encoding="utf-8"))
        except Exception:
            by_key = {}
        _strongs_heb_cache["by_key"] = by_key
        return by_key


def _oshb_strongs(lemma_attr: str) -> Optional[str]:
    """OSHB lemma attr -> principal Strong's key. 'b/7225'->H7225, 'c/d/776'->H776,
    '1254 a'->H1254. Prefix particles (b/c/d/l...) precede; the root is the last
    slash-segment carrying a number."""
    if not lemma_attr:
        return None
    for seg in reversed(lemma_attr.split("/")):
        m = _NUM_RE.search(seg)
        if m:
            return "H" + str(int(m.group(0)))
    return None


def _strongs_for_hkey(key: Optional[str]) -> Optional[dict]:
    if not key:
        return None
    e = _strongs_hebrew().get(key)
    if not e:
        return None
    return {
        "strongs": key,
        "translit": e.get("xlit"),
        "definition": e.get("strongs_def"),
        "kjv": e.get("kjv_def"),
    }


def _lookup_hebrew(ref: str, stem: str, ch: int, vs: Optional[int],
                   ve: Optional[int]) -> Dict[str, Any]:
    f = HEBREW_DIR / (stem + ".xml")
    if not f.exists():
        return {"ref": ref, "error": "OSHB/WLC source not found", "words": []}
    xml = f.read_text(encoding="utf-8")
    if vs is None:  # whole chapter
        blocks = re.findall(
            r'<verse osisID="%s\.%d\.\d+">(.*?)</verse>' % (re.escape(stem), ch),
            xml, re.DOTALL)
    else:
        blocks = []
        for v in range(vs, (ve or vs) + 1):
            m = re.search(
                r'<verse osisID="%s\.%d\.%d">(.*?)</verse>' % (re.escape(stem), ch, v),
                xml, re.DOTALL)
            if m:
                blocks.append(m.group(1))
    words: List[dict] = []
    matched = 0
    for block in blocks:
        for attrs, inner in _WORD_RE.findall(block):
            lm = _LEMMA_RE.search(attrs)
            mp = _MORPH_RE.search(attrs)
            lemma_attr = lm.group(1) if lm else ""
            morph = mp.group(1) if mp else None
            text = _TAG_RE.sub("", inner).replace("/", "").strip()
            key = _oshb_strongs(lemma_attr)
            lex = _strongs_for_hkey(key)
            if lex:
                matched += 1
            words.append({
                "hebrew": text, "lemma": lemma_attr, "morph": morph,
                **(lex or {"strongs": key, "translit": None,
                           "definition": None, "kjv": None}),
            })
    return {
        "ref": ref,
        "lang": "hbo",
        "source": "OSHB/WLC",
        "lexicon": "Strong's Hebrew",
        "words": words,
        "word_count": len(words),
        "defined": matched,
        "note": "Original Hebrew first (Westminster Leningrad Codex via the Open "
                "Scriptures Hebrew Bible morphology); WEB is the translation. "
                "Strong's number is read directly from each word's OSHB lemma; "
                "prefix particles (b/c/d/l) are stripped to the root.",
    }


def lookup_original(ref: str) -> Dict[str, Any]:
    """Return original-language words (+ definitions where confident) for a ref."""
    from api import scripture_lookup as _sl
    parsed = _sl.parse_ref((ref or "").strip())
    if not parsed:
        return {"ref": ref, "error": "could not parse reference", "words": []}
    book = (parsed.get("book") or "").strip().lower()
    ch = parsed.get("chapter")
    vs = parsed.get("verse_start")
    ve = parsed.get("verse_end") or vs
    booknum = _NT_BOOKS.get(book)
    if not booknum:
        stem = _OT_BOOKS.get(book)
        if stem:
            return _lookup_hebrew(ref, stem, ch, vs, ve)
        return {"ref": ref, "lang": None, "words": [],
                "note": "Could not match the reference to a wired book "
                        "(NT Greek or OT Hebrew)."}
    f = _morphgnt_file(booknum)
    if not f:
        return {"ref": ref, "error": "MorphGNT source not found", "words": []}
    want = set()
    if vs is None:
        prefix = f"{booknum:02d}{ch:02d}"   # whole chapter
        chapter_mode = True
    else:
        chapter_mode = False
        for v in range(vs, (ve or vs) + 1):
            want.add(f"{booknum:02d}{ch:02d}{v:02d}")
    words: List[dict] = []
    matched = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) < 7:
            continue
        vid = p[0]
        if chapter_mode:
            if not vid.startswith(prefix):
                continue
        elif vid not in want:
            continue
        word, lemma = p[4], p[6]
        lex = _strongs_for_lemma(lemma)
        if lex:
            matched += 1
        words.append({"greek": word, "lemma": lemma, **(lex or {"strongs": None, "definition": None})})
    return {
        "ref": ref,
        "lang": "grc",
        "source": "MorphGNT",
        "lexicon": "Strong's Greek",
        "words": words,
        "word_count": len(words),
        "defined": matched,
        "note": "Original Greek first; WEB is the translation. Definitions shown where "
                "the lemma confidently bridges to Strong's; key words are curated.",
    }


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/scripture/original", tags=["scripture"])
    def scripture_original(ref: str = ""):
        if not ref.strip():
            return {"ref": "", "error": "ref is required", "words": []}
        return lookup_original(ref)

    return router
