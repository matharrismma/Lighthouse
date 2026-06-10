"""Scripture lookup — swap verse text by reader language.

For a (lang, book, chapter, verse) tuple, return the verse text in the
requested language using a parallel public-domain translation. When the
language is not available, fall back to English (the canonical substrate).

This is the load-bearing rule: parallel PD translations over machine
translation wherever they exist. Each `data/bible_<lang>/verses.jsonl`
file shares the same {book (English), chapter, verse, text} shape so a
single index can serve every language.

Today:
  en  — substrate is in scattered files (proverbs/, james/, ecclesiastes/,
        psalms/, sermon_on_mount/). The English path is unchanged and goes
        through the existing apothecary retrieval; `lookup_verse()` for `en`
        returns None so callers know to keep the original text.
  es  — Reina-Valera 1909 (data/bible_es/verses.jsonl).

Tomorrow:
  zh, ar, fr, pt, ru, hi, sw — each its own bible_<lang>/verses.jsonl.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).parent.parent

# Supported translations by language code → (file path, translation label).
# `en` is intentionally absent: English packets ARE the substrate, so no
# lookup is needed. Add a row here for each new language ingested.
_TRANSLATIONS: Dict[str, Tuple[Path, str]] = {
    "es": (_REPO / "data" / "bible_es" / "verses.jsonl", "Reina-Valera 1909"),
    "zh": (_REPO / "data" / "bible_zh" / "verses.jsonl", "Chinese Union Version (Simplified)"),
    "fr": (_REPO / "data" / "bible_fr" / "verses.jsonl", "Louis Segond 1910"),
    "pt": (_REPO / "data" / "bible_pt" / "verses.jsonl", "Bíblia Portuguesa Mundial"),
    "de": (_REPO / "data" / "bible_de" / "verses.jsonl", "Lutherbibel 1912"),
    "ko": (_REPO / "data" / "bible_ko" / "verses.jsonl", "Korean Bible 1910"),
    "ja": (_REPO / "data" / "bible_ja" / "verses.jsonl", "口語訳聖書 (Kogoyaku 1954/1955)"),
    "ar": (_REPO / "data" / "bible_ar" / "verses.jsonl", "Smith-Van Dyke 1865"),
    "ru": (_REPO / "data" / "bible_ru" / "verses.jsonl", "Russian Synodal 1876"),
    "fa": (_REPO / "data" / "bible_fa" / "verses.jsonl", "Persian Old Version (OPV)"),
    "vi": (_REPO / "data" / "bible_vi" / "verses.jsonl", "Vietnamese 1934"),
    "it": (_REPO / "data" / "bible_it" / "verses.jsonl", "Diodati Riveduta 1885"),
    "my": (_REPO / "data" / "bible_my" / "verses.jsonl", "Judson Burmese 1835"),
    "uk": (_REPO / "data" / "bible_uk" / "verses.jsonl", "Kulish Ukrainian 1871"),
    "nl": (_REPO / "data" / "bible_nl" / "verses.jsonl", "Statenvertaling 1637"),
    "ro": (_REPO / "data" / "bible_ro" / "verses.jsonl", "Cornilescu 1924"),
    "ht": (_REPO / "data" / "bible_ht" / "verses.jsonl", "Haitian Creole"),
    "he": (_REPO / "data" / "bible_he" / "verses.jsonl", "Hebrew (Leningrad-Aleppo)"),
    "la": (_REPO / "data" / "bible_la" / "verses.jsonl", "Vulgata Clementina"),
    "hi": (_REPO / "data" / "bible_hi" / "verses.jsonl", "Indian Revised Version Hindi"),
    "sw": (_REPO / "data" / "bible_sw" / "verses.jsonl", "Kiswahili Contemporary Version (Open Neno)"),
}

# Catalog metadata for the Atlas of Bibles lens. Extends `_TRANSLATIONS`
# with year, public-domain source URL, and a human-readable language name.
# Keep in sync with `_TRANSLATIONS` keys when adding a new translation.
_CATALOG_META: Dict[str, Dict[str, str]] = {
    "en": {
        "language_name": "English",
        "language_label": "English",
        "translation":   "World English Bible",
        "year":          "1997 (revision ongoing)",
        "source":        "ebible.org / lw/00_source/web/web.db",
        "license":       "Public Domain",
    },
    "es": {
        "language_name": "Español",
        "language_label": "Spanish",
        "translation":   "Reina-Valera 1909",
        "year":          "1909",
        "source":        "eBible.org · spaRV1909",
        "license":       "Public Domain",
    },
    "zh": {
        "language_name": "中文",
        "language_label": "Chinese (Mandarin, simplified)",
        "translation":   "Chinese Union Version (Simplified)",
        "year":          "1919",
        "source":        "eBible.org · cmn-cu89s",
        "license":       "Public Domain",
    },
    "fr": {
        "language_name": "Français",
        "language_label": "French",
        "translation":   "Louis Segond 1910",
        "year":          "1910",
        "source":        "eBible.org · fraLSG",
        "license":       "Public Domain",
    },
    "pt": {
        "language_name": "Português",
        "language_label": "Portuguese (Brasil)",
        "translation":   "Bíblia Portuguesa Mundial",
        "year":          "2022",
        "source":        "eBible.org · porbrbsl",
        "license":       "Public Domain",
    },
    "de": {
        "language_name": "Deutsch",
        "language_label": "German",
        "translation":   "Lutherbibel 1912",
        "year":          "1912",
        "source":        "eBible.org · deu1912",
        "license":       "Public Domain",
    },
    "ko": {
        "language_name": "한국어",
        "language_label": "Korean",
        "translation":   "Korean Bible 1910",
        "year":          "1910",
        "source":        "eBible.org · kor",
        "license":       "Public Domain",
    },
    "ja": {
        "language_name": "日本語",
        "language_label": "Japanese",
        "translation":   "口語訳聖書 (Kogoyaku 1954/1955)",
        "year":          "1954-1955",
        "source":        "bible.salterrae.net via tadd/jpn.bible",
        "license":       "Public Domain",
    },
    "ar": {
        "language_name": "العربية", "language_label": "Arabic",
        "translation": "Smith-Van Dyke (Smith Van Dyck)",
        "year": "1865", "source": "eBible.org · arb-vd", "license": "Public Domain",
    },
    "ru": {
        "language_name": "Русский", "language_label": "Russian",
        "translation": "Russian Synodal Translation",
        "year": "1876", "source": "eBible.org · russyn", "license": "Public Domain",
    },
    "fa": {
        "language_name": "فارسی", "language_label": "Persian (Farsi)",
        "translation": "Persian Old Version (OPV)",
        "year": "various", "source": "eBible.org · pesOPV", "license": "Public Domain",
    },
    "vi": {
        "language_name": "Tiếng Việt", "language_label": "Vietnamese",
        "translation": "Vietnamese 1934",
        "year": "1934", "source": "eBible.org · vie1934", "license": "Public Domain",
    },
    "it": {
        "language_name": "Italiano", "language_label": "Italian",
        "translation": "Diodati Riveduta 1885",
        "year": "1885", "source": "eBible.org · ita1885", "license": "Public Domain",
    },
    "my": {
        "language_name": "မြန်မာ", "language_label": "Burmese",
        "translation": "Judson Burmese Bible",
        "year": "1835", "source": "eBible.org · mya", "license": "Public Domain",
    },
    "uk": {
        "language_name": "Українська", "language_label": "Ukrainian",
        "translation": "Kulish Ukrainian 1871",
        "year": "1871", "source": "eBible.org · ukr1871", "license": "Public Domain",
    },
    "nl": {
        "language_name": "Nederlands", "language_label": "Dutch",
        "translation": "Statenvertaling 1637",
        "year": "1637", "source": "eBible.org · nld", "license": "Public Domain",
    },
    "ro": {
        "language_name": "Молдовенясвэ (Romanian, Cyrillic)",
        "language_label": "Romanian (Moldavian Cyrillic script)",
        "translation": "Cornilescu 1924 (Cyrillic edition)",
        "year": "1924",
        "source": "eBible.org · ron1924",
        "license": "Public Domain",
    },
    "ht": {
        "language_name": "Kreyòl Ayisyen", "language_label": "Haitian Creole",
        "translation": "Haitian Creole",
        "year": "2019", "source": "eBible.org · hat", "license": "Public Domain",
    },
    "he": {
        "language_name": "עברית", "language_label": "Hebrew",
        "translation": "Hebrew (Leningrad-Aleppo basis)",
        "year": "2022", "source": "eBible.org · heb", "license": "Public Domain",
    },
    "la": {
        "language_name": "Latine", "language_label": "Latin",
        "translation": "Vulgata Clementina",
        "year": "1592", "source": "eBible.org · latVUC", "license": "Public Domain",
    },
    "hi": {
        "language_name": "हिन्दी", "language_label": "Hindi",
        "translation": "Indian Revised Version (IRV) Hindi",
        "year": "2019",
        "source": "eBible.org · hinirv (BridgeConn)",
        "license": "CC-BY-SA 4.0",
    },
    "sw": {
        "language_name": "Kiswahili", "language_label": "Swahili",
        "translation": "Toleo Wazi Neno (Open Kiswahili Contemporary)",
        "year": "2015",
        "source": "eBible.org · swhonen (Biblica)",
        "license": "CC-BY-SA 4.0",
    },
}

# Full WEB English Bible — the canonical English Scripture substrate for
# parallel lookups + alignment. Single file, same shape as the other
# parallel translations. The scattered per-book files (proverbs/, james/,
# ecclesiastes/, psalms/, sermon_on_mount/) remain for Apothecary's
# axis/theme-tagged retrieval; they're separate concerns.
_EN_FULL_BIBLE: Path = _REPO / "data" / "bible_en" / "verses.jsonl"

# Multi-verse English packets (Psalms by chapter, Sermon on the Mount by
# pericope). Used by the parallel viewer to render these at their native
# granularity for English while Spanish renders verse-by-verse.
_EN_CHAPTER_FILES: Dict[str, Path] = {
    "Psalms": _REPO / "data" / "psalms" / "chapters.jsonl",
}
_EN_PERICOPE_FILE = _REPO / "data" / "sermon_on_mount" / "units.jsonl"  # book="Matthew"

# Cache keyed by language code → {(book_lower, chapter, verse): text}
_CACHE: Dict[str, Dict[Tuple[str, int, int], str]] = {}
_CACHE_MTIME: Dict[str, float] = {}


def supported_languages() -> Dict[str, str]:
    """Return {lang_code: translation_label} for languages with a Bible parallel.

    Always includes 'en' in the response so the UI can list the canonical
    language alongside the swap-targets.
    """
    out = {"en": "World English Bible"}
    for lang, (_, label) in _TRANSLATIONS.items():
        out[lang] = label
    return out


def _load(lang: str) -> Dict[Tuple[str, int, int], str]:
    spec = _TRANSLATIONS.get(lang)
    if not spec:
        return {}
    path, _label = spec
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if lang in _CACHE and _CACHE_MTIME.get(lang) == mtime:
        return _CACHE[lang]
    idx: Dict[Tuple[str, int, int], str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            book = (rec.get("book") or "").strip().lower()
            try:
                ch = int(rec.get("chapter"))
                vs = int(rec.get("verse"))
            except (TypeError, ValueError):
                continue
            text = rec.get("text")
            if not book or not text:
                continue
            idx[(book, ch, vs)] = text
    except OSError:
        return {}
    _CACHE[lang] = idx
    _CACHE_MTIME[lang] = mtime
    return idx


def preload_all() -> None:
    """Pre-warm the in-memory cache for every registered translation.

    Called from a background thread at module load so that the first
    /scripture/parallel call doesn't have to block on ~280 MB of I/O.
    """
    for lang in _TRANSLATIONS:
        try:
            _load(lang)
        except Exception:
            pass


# Kick off background preload on import — the thread is daemon so it
# won't prevent process exit. By the time a user navigates to the
# parallel viewer, most (or all) translations will be warm in memory.
threading.Thread(target=preload_all, daemon=True, name="bible-preload").start()


def lookup_verse(lang: str, book: str, chapter: int, verse: int) -> Optional[str]:
    """Return the verse text in `lang`, or None if not available.

    `book` is the canonical English book name (e.g., "Proverbs", "1 John").
    Returning None means the caller should keep the English fallback.
    """
    if not lang or lang == "en":
        return None
    idx = _load(lang)
    if not idx:
        return None
    return idx.get((book.strip().lower(), chapter, verse))


def lookup_packet(lang: str, packet: Dict[str, Any]) -> Optional[str]:
    """Convenience: given a Scripture packet (with book/chapter/verse fields),
    return the parallel-language text, or None if no swap is available.

    Falls back to parsing the `reference` field (e.g. "Proverbs 12:25") when
    book/chapter/verse aren't all present as separate fields.
    """
    if not lang or lang == "en":
        return None

    book = packet.get("book")
    ch = packet.get("chapter")
    vs = packet.get("verse")

    if not (book and isinstance(ch, int) and isinstance(vs, int)):
        ref = packet.get("reference") or ""
        # Parse "Proverbs 12:25" or "1 Kings 19:11"
        import re
        m = re.match(r"^(.+?)\s+(\d+):(\d+)\s*$", ref.strip())
        if not m:
            return None
        book = m.group(1).strip()
        try:
            ch = int(m.group(2))
            vs = int(m.group(3))
        except ValueError:
            return None

    return lookup_verse(lang, book, ch, vs)


def lookup_chapter(lang: str, book: str, chapter: int) -> Optional[str]:
    """Return the full chapter text as joined verses, or None when unavailable.

    Joins each verse with a leading verse number in square brackets, e.g.
    "[1] verse text [2] next verse …", same convention as the English
    psalm-chapter packets use. Returns None for `lang=en` (no swap needed)
    or when the chapter is missing.
    """
    if not lang or lang == "en":
        return None
    idx = _load(lang)
    if not idx:
        return None
    book_l = book.strip().lower()
    verses = []
    v = 1
    # Walk verses 1..N until a gap. Caps at 200 (longest chapter is Ps 119:176).
    while v <= 200:
        text = idx.get((book_l, chapter, v))
        if text is None:
            break
        verses.append(f"[{v}] {text}")
        v += 1
    if not verses:
        return None
    return " ".join(verses)


def lookup_range(lang: str, book: str, chapter: int,
                 verse_start: int, verse_end: int) -> Optional[str]:
    """Return verses [verse_start..verse_end] joined, or None when not all present.

    Used for pericope-bundled packets (Sermon on the Mount pericopes).
    """
    if not lang or lang == "en":
        return None
    idx = _load(lang)
    if not idx:
        return None
    book_l = book.strip().lower()
    verses = []
    for v in range(verse_start, verse_end + 1):
        text = idx.get((book_l, chapter, v))
        if text is None:
            return None  # partial range — keep English rather than splice
        verses.append(text)
    if not verses:
        return None
    return " ".join(verses)


def translation_label(lang: str) -> Optional[str]:
    spec = _TRANSLATIONS.get(lang)
    if spec:
        return spec[1]
    if lang == "en":
        return "World English Bible"
    return None


# ── English-substrate index (scattered per-book files) ───────────────────

_EN_INDEX: Optional[Dict[Tuple[str, int, int], str]] = None
_EN_INDEX_MTIME: float = 0.0


def _load_english_index() -> Dict[Tuple[str, int, int], str]:
    """Build (book_lower, ch, v) → text for the full English WEB Bible."""
    global _EN_INDEX, _EN_INDEX_MTIME
    if not _EN_FULL_BIBLE.exists():
        _EN_INDEX = {}
        return _EN_INDEX
    mtime = _EN_FULL_BIBLE.stat().st_mtime
    if _EN_INDEX is not None and mtime == _EN_INDEX_MTIME:
        return _EN_INDEX
    idx: Dict[Tuple[str, int, int], str] = {}
    try:
        for line in _EN_FULL_BIBLE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            book = (rec.get("book") or "").strip().lower()
            try:
                ch = int(rec.get("chapter"))
                vs = int(rec.get("verse"))
            except (TypeError, ValueError):
                continue
            text = rec.get("text")
            if not book or not text:
                continue
            idx[(book, ch, vs)] = text
    except OSError:
        return _EN_INDEX or {}
    _EN_INDEX = idx
    _EN_INDEX_MTIME = mtime
    return idx


def english_verse(book: str, chapter: int, verse: int) -> Optional[str]:
    """Return the English (WEB) text for (book, ch, v) when present."""
    idx = _load_english_index()
    return idx.get((book.strip().lower(), chapter, verse))


def english_chapter_text(book: str, chapter: int) -> Optional[str]:
    """Return joined English text for a chapter — uses verse-level index when
    available, else falls back to the chapter-packet text (e.g. for Psalms).
    """
    idx = _load_english_index()
    book_l = book.strip().lower()
    verses = []
    v = 1
    while v <= 200:
        text = idx.get((book_l, chapter, v))
        if text is None:
            break
        verses.append(f"[{v}] {text}")
        v += 1
    if verses:
        return " ".join(verses)
    # Fallback: chapter-packet text (e.g., psalms/chapters.jsonl)
    path = _EN_CHAPTER_FILES.get(book)
    if path and path.exists():
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (rec.get("book") == book) and int(rec.get("chapter", -1)) == chapter:
                    return rec.get("text")
        except OSError:
            return None
    return None


def english_pericope_text(book: str, chapter: int,
                           verse_start: int, verse_end: int) -> Optional[str]:
    """Return joined English text for a verse range.

    Uses verse-level index first; falls back to the Sermon-on-the-Mount
    pericope file for Matthew 5-7 when the range matches a known pericope.
    """
    idx = _load_english_index()
    book_l = book.strip().lower()
    verses = []
    for v in range(verse_start, verse_end + 1):
        text = idx.get((book_l, chapter, v))
        if text is None:
            verses = []
            break
        verses.append(text)
    if verses:
        return " ".join(verses)
    # Fallback: SoM pericope packet
    if book == "Matthew" and _EN_PERICOPE_FILE.exists():
        try:
            for line in _EN_PERICOPE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (int(rec.get("chapter", -1)) == chapter
                        and int(rec.get("verse_start", -1)) == verse_start
                        and int(rec.get("verse_end", -1)) == verse_end):
                    return rec.get("text")
        except OSError:
            return None
    return None


# ── Catalog ──────────────────────────────────────────────────────────────

def _english_stats() -> Dict[str, Any]:
    """Compute English coverage stats for the catalog view."""
    idx = _load_english_index()
    verse_count = len(idx)
    books = set()
    for (book_l, _ch, _v) in idx.keys():
        # Title-case book name back for display
        books.add(book_l.title() if " " not in book_l else
                  " ".join(p.capitalize() for p in book_l.split()))
    return {
        "verse_count": verse_count,
        "book_count":  len(books),
        "books":       sorted(books),
    }


def _parallel_stats(lang: str) -> Dict[str, Any]:
    idx = _load(lang)
    books = set()
    for (book_l, _ch, _v) in idx.keys():
        books.add(" ".join(p.capitalize() for p in book_l.split()))
    return {
        "verse_count": len(idx),
        "book_count":  len(books),
        "books":       sorted(books),
    }


def catalog() -> List[Dict[str, Any]]:
    """Return the catalog of available Bible translations + coverage stats.

    Each entry: {lang, language_name, language_label, translation, year,
    source, license, verse_count, book_count, books}.
    """
    rows: List[Dict[str, Any]] = []

    # English row
    meta_en = dict(_CATALOG_META["en"])
    stats_en = _english_stats()
    rows.append({
        "lang": "en",
        **meta_en,
        **stats_en,
    })

    # Parallel translations
    for lang in sorted(_TRANSLATIONS.keys()):
        meta = dict(_CATALOG_META.get(lang) or {"translation": _TRANSLATIONS[lang][1]})
        stats = _parallel_stats(lang)
        rows.append({
            "lang": lang,
            **meta,
            **stats,
        })

    return rows


# ── Parallel viewer ──────────────────────────────────────────────────────

import re as _re  # noqa: E402

_REF_RE = _re.compile(r"^\s*(?P<book>[A-Za-z0-9]+(?:\s+[A-Za-z]+)*)\s+(?P<ch>\d+)(?::(?P<vstart>\d+)(?:-(?P<vend>\d+))?)?\s*$")


def _normalize_ref_string(ref: str) -> str:
    """Normalize stylistic variants so the parser sees one canonical form.

    - en/em dashes → hyphen
    - smart apostrophes → ascii
    - trailing translation tags (NKJV, NIV, ESV, KJV, ASV, etc.) stripped
    - collapse whitespace
    """
    if not ref:
        return ""
    # Unicode dash variants
    s = ref.replace("–", "-").replace("—", "-").replace("−", "-")
    # Strip trailing translation/version tags
    s = _re.sub(
        r"\s*\b(?:NKJV|NIV|ESV|KJV|ASV|NASB|NLT|NRSV|RSV|MSG|CSB|WEB|RV|RV1909|LSG|BPM|CUV)\b\s*$",
        "",
        s,
        flags=_re.IGNORECASE,
    )
    return _re.sub(r"\s+", " ", s).strip()


def parse_ref(ref: str) -> Optional[Dict[str, Any]]:
    """Parse a reference like 'Proverbs 12:25', 'Psalm 23', 'Matthew 5:3-12',
    or even 'Isaiah 41:9–10 NKJV'.

    Returns {book, chapter, verse_start, verse_end} or None on failure.
    `verse_start`/`verse_end` are None for a whole-chapter reference.
    """
    s = _normalize_ref_string(ref)
    if not s:
        return None
    m = _REF_RE.match(s)
    if not m:
        return None
    book = m.group("book").strip()
    # Normalize Psalm/Psalms (singular often appears for individual chapters)
    if book.lower() == "psalm":
        book = "Psalms"
    try:
        ch = int(m.group("ch"))
        vs = m.group("vstart")
        ve = m.group("vend")
        return {
            "book":         book.title() if " " not in book else " ".join(p.capitalize() for p in book.split()),
            "chapter":      ch,
            "verse_start":  int(vs) if vs else None,
            "verse_end":    int(ve) if ve else (int(vs) if vs else None),
        }
    except ValueError:
        return None


def parallel_lookup(ref: str, langs: Optional[List[str]] = None) -> Dict[str, Any]:
    """For a verse reference, return {lang → text} across every translation.

    Granularity is the smallest available:
      - "Proverbs 12:25"   → single verse
      - "Matthew 5:3-12"   → verse range
      - "Psalm 23"         → whole chapter
    Missing translations come back with text=null.

    If `langs` is given (e.g. ["en","es","fr"]), only those languages are
    returned. Otherwise all 22 translations are included.
    """
    parsed = parse_ref(ref)
    if not parsed:
        return {"ref": ref, "error": "could not parse reference", "results": []}

    book = parsed["book"]
    ch = parsed["chapter"]
    vs = parsed["verse_start"]
    ve = parsed["verse_end"]

    # Determine which languages to include
    want_langs = set(l.strip().lower() for l in langs) if langs else None

    results: List[Dict[str, Any]] = []

    # English (always included)
    if want_langs is None or "en" in want_langs:
        en_meta = dict(_CATALOG_META["en"])
        if vs is None:
            en_text = english_chapter_text(book, ch)
        elif ve and ve > vs:
            en_text = english_pericope_text(book, ch, vs, ve)
        else:
            en_text = english_verse(book, ch, vs)
        results.append({
            "lang": "en",
            **en_meta,
            "text": en_text,
        })

    # Each parallel translation
    for lang in sorted(_TRANSLATIONS.keys()):
        if want_langs is not None and lang not in want_langs:
            continue
        meta = dict(_CATALOG_META.get(lang) or {"translation": _TRANSLATIONS[lang][1]})
        if vs is None:
            text = lookup_chapter(lang, book, ch)
        elif ve and ve > vs:
            text = lookup_range(lang, book, ch, vs, ve)
        else:
            text = lookup_verse(lang, book, ch, vs)
        results.append({
            "lang": lang,
            **meta,
            "text": text,
        })

    return {
        "ref":      f"{book} {ch}" + (f":{vs}" if vs else "") + (f"-{ve}" if ve and ve > (vs or 0) else ""),
        "parsed":   parsed,
        "results":  results,
    }
