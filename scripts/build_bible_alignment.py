#!/usr/bin/env python
"""Build a Bible-corpus alignment table per target language.

For each English token (and short n-gram), find the most-likely target-
language phrase by co-occurrence statistics across the ~31,000 parallel
verses. This produces a usable bilingual lexicon entirely offline, from
the PD Bibles we've already ingested.

Algorithm (simple, well-understood):
  1. For each language, align verses where both English AND target have
     the same (book, chapter, verse) key.
  2. For each English token in a paired verse, count its co-occurrence
     with each target token in that verse.
  3. Score candidates by Dice coefficient: 2 * count(x,y) / (count(x) + count(y)).
  4. Keep the top-3 candidates per English token, with min-freq threshold.

CJK (zh, ja, ko) need character-level segmentation since they don't use
spaces. We use simple unicode-block-based heuristics: each Han character
is a token; consecutive Hangul characters group; consecutive kana likewise.

Output: data/lang_corpus/<lang>.jsonl, one line per English source phrase:
  {"src":"anxiety","candidates":[{"text":"cuidado","score":0.42,"freq":12}, ...]}

The mt_adapter's bible_corpus provider reads this table for free, fast,
offline translation of single words and short phrases.
"""
from __future__ import annotations
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "lang_corpus"

EN_FILE = REPO / "data" / "bible_en" / "verses.jsonl"
TARGETS = {
    # Latin-script European languages
    "es": REPO / "data" / "bible_es" / "verses.jsonl",
    "fr": REPO / "data" / "bible_fr" / "verses.jsonl",
    "pt": REPO / "data" / "bible_pt" / "verses.jsonl",
    "de": REPO / "data" / "bible_de" / "verses.jsonl",
    "it": REPO / "data" / "bible_it" / "verses.jsonl",
    "nl": REPO / "data" / "bible_nl" / "verses.jsonl",
    "ro": REPO / "data" / "bible_ro" / "verses.jsonl",
    "vi": REPO / "data" / "bible_vi" / "verses.jsonl",
    "ht": REPO / "data" / "bible_ht" / "verses.jsonl",
    "la": REPO / "data" / "bible_la" / "verses.jsonl",
    "sw": REPO / "data" / "bible_sw" / "verses.jsonl",
    # Cyrillic
    "ru": REPO / "data" / "bible_ru" / "verses.jsonl",
    "uk": REPO / "data" / "bible_uk" / "verses.jsonl",
    # RTL (Arabic script + Hebrew script)
    "ar": REPO / "data" / "bible_ar" / "verses.jsonl",
    "fa": REPO / "data" / "bible_fa" / "verses.jsonl",
    "he": REPO / "data" / "bible_he" / "verses.jsonl",
    # Brahmic
    "my": REPO / "data" / "bible_my" / "verses.jsonl",
    "hi": REPO / "data" / "bible_hi" / "verses.jsonl",
    # CJK
    "zh": REPO / "data" / "bible_zh" / "verses.jsonl",
    "ko": REPO / "data" / "bible_ko" / "verses.jsonl",
    "ja": REPO / "data" / "bible_ja" / "verses.jsonl",
}

# English stopwords — common function words that align to many target
# tokens spuriously. Drop them from the source vocabulary.
EN_STOP = set("""
the a an and or but if then so to of in on at by for with from as is are was were be been being
have has had do does did will would shall should may might must can could
this that these those it its his her him my your our their them they we us you i me he she
not no nor yes oh ah lo behold
all any some each every many few much most least less more
who whom whose what which when where why how
into upon onto unto over under above below before after again still also too very just only
""".split())

# Tokenize English: lowercase words of length >= 3, drop stopwords + numbers.
EN_TOKEN_RE = re.compile(r"[A-Za-z']+")


def en_tokens(text: str) -> List[str]:
    out = []
    for m in EN_TOKEN_RE.finditer(text):
        tok = m.group(0).lower().strip("'")
        if len(tok) < 3:
            continue
        if tok in EN_STOP:
            continue
        out.append(tok)
    return out


# Tokenize target languages
LATIN_RE = re.compile(
    r"[A-Za-zÀ-ÿĀ-žƀ-ɏḀ-ỿ]+",
    re.UNICODE,
)
# Includes: basic Latin (A-z), Latin-1 Supplement (À-ÿ),
# Latin Extended-A (Ā-ž), Latin Extended-B (ƀ-ɏ), Latin Extended Additional (Ḁ-ỿ).
# The last block covers Vietnamese tone marks (ạ ẩ ầ ậ ự etc.).
# Han / Hangul / Kana ranges (Unicode blocks)
HAN_RE      = re.compile(r"[一-鿿]")
HANGUL_RE   = re.compile(r"[가-힯]+")
KANA_RE     = re.compile(r"[぀-ヿㇰ-ㇿ]+")
# Cyrillic / Arabic in case we add them
CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]+")
ARABIC_RE   = re.compile(r"[؀-ۿ]+")


def latin_tokens(text: str, min_len: int = 3) -> List[str]:
    return [m.group(0).lower() for m in LATIN_RE.finditer(text) if len(m.group(0)) >= min_len]


def cjk_tokens(text: str) -> List[str]:
    """Mixed-script segmentation for CJK languages.

    Han characters are individual tokens. Hangul syllable runs are one token.
    Kana runs are one token. Drops most punctuation and spaces.
    """
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if HAN_RE.match(ch):
            out.append(ch)
            i += 1
        elif "가" <= ch <= "힯":
            # Hangul syllable run
            j = i
            while j < n and "가" <= text[j] <= "힯":
                j += 1
            out.append(text[i:j])
            i = j
        elif ("぀" <= ch <= "ヿ") or ("ㇰ" <= ch <= "ㇿ"):
            # Kana run (hiragana + katakana)
            j = i
            while j < n and (("぀" <= text[j] <= "ヿ") or ("ㇰ" <= text[j] <= "ㇿ")):
                j += 1
            tok = text[i:j]
            if len(tok) >= 1:
                out.append(tok)
            i = j
        else:
            i += 1
    return out


def target_tokens(lang: str, text: str) -> List[str]:
    # CJK character/syllable segmentation
    if lang in ("zh", "ja", "ko"):
        return cjk_tokens(text)
    # Cyrillic — Russian, Ukrainian, plus the eBible Cornilescu Romanian
    # (Moldavian tradition) which uses Cyrillic script not Latin.
    if lang in ("ru", "uk", "sr", "bg", "ro"):
        return [m.group(0).lower() for m in re.finditer(r"[Ѐ-ӿ]+", text) if len(m.group(0)) >= 3]
    # Arabic script — Arabic, Persian, Urdu. Word-level via Arabic range.
    if lang in ("ar", "fa", "ur"):
        # Arabic block (U+0600-U+06FF) + Arabic Supplement (U+0750-U+077F)
        # + Arabic Extended-A (U+08A0-U+08FF) + Arabic Presentation Forms
        return [m.group(0) for m in re.finditer(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]+", text) if len(m.group(0)) >= 2]
    # Hebrew script — Hebrew. Word-level. Strip cantillation/vowel marks if present.
    if lang == "he":
        # Hebrew letters U+05D0-U+05EA. Drop niqqud (U+05B0-U+05BC) for matching.
        cleaned = re.sub(r"[֑-ׇ]", "", text)
        return [m.group(0) for m in re.finditer(r"[א-ת]+", cleaned) if len(m.group(0)) >= 2]
    # Burmese — Myanmar block (no spaces between words traditionally). Use
    # a coarse character-cluster heuristic: split on Myanmar virama / spaces.
    if lang == "my":
        return [m.group(0) for m in re.finditer(r"[က-႟ꩠ-ꩿꧠ-꧿]+", text) if len(m.group(0)) >= 1]
    # Devanagari — Hindi. Spaces between words; tokenize on whitespace
    # over the Devanagari block. Includes Devanagari Extended (ऀ-ॿ) plus
    # the auxiliary Devanagari Extended-A block.
    if lang == "hi":
        return [m.group(0) for m in re.finditer(r"[ऀ-ॿ]+", text) if len(m.group(0)) >= 2]
    # Default: Latin-script (Spanish, French, Italian, Vietnamese, Dutch,
    # Romanian, Haitian Creole, German, Portuguese, Latin). The Latin
    # tokenizer covers diacritics (À-ÿ + Ā-ž) and most additional Latin
    # extended blocks needed for Vietnamese tone marks.
    return latin_tokens(text)


def load_verses(path: Path) -> Dict[Tuple[str, int, int], str]:
    idx: Dict[Tuple[str, int, int], str] = {}
    if not path.exists():
        return idx
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
        text = rec.get("text") or ""
        if not book or not text:
            continue
        idx[(book, ch, vs)] = text
    return idx


def align_language(lang: str, target_path: Path,
                   en_verses: Dict[Tuple[str, int, int], str],
                   min_freq: int = 3,
                   top_k: int = 3) -> List[Dict]:
    """For one target language, walk paired verses and compute Dice-coefficient
    alignment scores. Return a sorted list of {src, candidates}."""
    print(f"  aligning {lang}...", flush=True)
    target_verses = load_verses(target_path)

    # Find shared verse keys
    shared = set(en_verses.keys()) & set(target_verses.keys())
    print(f"    {len(shared):,} parallel verses", flush=True)

    # Co-occurrence counts: cooc[en_tok][tgt_tok] = N
    en_count: Counter = Counter()
    tgt_count: Counter = Counter()
    cooc: Dict[str, Counter] = defaultdict(Counter)

    for key in shared:
        en_text = en_verses[key]
        tgt_text = target_verses[key]
        en_set = set(en_tokens(en_text))
        tgt_set = set(target_tokens(lang, tgt_text))
        for et in en_set:
            en_count[et] += 1
        for tt in tgt_set:
            tgt_count[tt] += 1
        for et in en_set:
            for tt in tgt_set:
                cooc[et][tt] += 1

    print(f"    {len(en_count):,} EN tokens, {len(tgt_count):,} target tokens", flush=True)

    # Score each EN token: top-k target candidates by Dice coefficient.
    results: List[Dict] = []
    for et, et_freq in sorted(en_count.items()):
        if et_freq < min_freq:
            continue
        candidates: List[Tuple[str, float, int]] = []
        for tt, c in cooc[et].items():
            if c < min_freq:
                continue
            tt_freq = tgt_count[tt]
            if tt_freq < min_freq:
                continue
            dice = (2.0 * c) / (et_freq + tt_freq)
            candidates.append((tt, dice, c))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (-x[1], -x[2]))
        results.append({
            "src": et,
            "freq": et_freq,
            "candidates": [
                {"text": tt, "score": round(d, 3), "freq": c}
                for tt, d, c in candidates[:top_k]
            ],
        })

    print(f"    {len(results):,} aligned EN tokens kept", flush=True)
    return results


def main() -> int:
    if not EN_FILE.exists():
        print(f"missing English source: {EN_FILE}", file=sys.stderr)
        return 1
    print(f"loading English ({EN_FILE})...", flush=True)
    en_verses = load_verses(EN_FILE)
    print(f"  {len(en_verses):,} English verses indexed", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, int] = {}
    for lang, path in TARGETS.items():
        rows = align_language(lang, path, en_verses)
        out_file = OUT_DIR / f"{lang}.jsonl"
        with out_file.open("w", encoding="utf-8") as out:
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
        summary[lang] = len(rows)
        print(f"  -> wrote {len(rows):,} rows to {out_file.name}", flush=True)

    print()
    print("=== Summary ===")
    for lang, n in summary.items():
        print(f"  {lang}: {n:,} EN tokens with target candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
