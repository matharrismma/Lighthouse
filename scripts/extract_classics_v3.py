"""Extract Augustine Confessions, Imitation of Christ, Boethius Consolation.

All three are Project Gutenberg PD translations (Pusey, Benham, James — pre-1928).
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
RAW = REPO / "data" / "raw_sources"

sys.path.insert(0, str(REPO / "scripts"))
from extract_proverbs import derive_axes, derive_themes


def _roman(s: str) -> int:
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    n = 0
    for i, ch in enumerate(s):
        v = vals.get(ch, 0)
        if i+1 < len(s) and vals.get(s[i+1], 0) > v:
            n -= v
        else:
            n += v
    return n


def _strip_pg(text: str) -> str:
    """Strip PG header/footer."""
    m_start = re.search(r"\*\*\*\s*START OF.+?\*\*\*", text)
    m_end = re.search(r"\*\*\*\s*END OF.+?\*\*\*", text)
    if m_start:
        text = text[m_start.end():]
    if m_end:
        text = text[:m_end.start()] if hasattr(m_end, 'start') else text
        # m_end was searched in full text; re-search now
    m_end2 = re.search(r"\*\*\*\s*END OF.+?\*\*\*", text)
    if m_end2:
        text = text[:m_end2.start()]
    return text


# ── Augustine Confessions ───────────────────────────────────────────────
# Format: "BOOK I" line, then numbered paragraphs "I." through "XL.+"
# Each numbered paragraph is one packet.

def extract_augustine(out_path: Path) -> int:
    """Pusey edition has unnumbered prose — chunk by paragraph (blank-line splits)
    and treat each substantial paragraph as a packet."""
    text = _strip_pg((RAW / "augustine_confessions.txt").read_text(encoding="utf-8", errors="replace"))
    book_starts = []
    roman_book = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]
    for i, r in enumerate(roman_book, start=1):
        m = re.search(rf"^BOOK {r}\s*$", text, re.MULTILINE)
        if m:
            book_starts.append((i, m.end()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for idx, (book_num, start) in enumerate(book_starts):
            stop = book_starts[idx+1][1] - len(f"BOOK {roman_book[idx+1]}") - 2 \
                   if idx+1 < len(book_starts) else len(text)
            block = text[start:stop]
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
            seq = 0
            for para in paragraphs:
                # Skip transient footnotes / short artifacts
                body = re.sub(r"\s+", " ", para).strip()
                if len(body) < 120:
                    continue
                seq += 1
                packet = {
                    "id": f"aug_conf_{book_num:02d}_{seq:03d}",
                    "kind": "augustine_confessions",
                    "reference": f"Confessions {book_num}, §{seq}",
                    "book": book_num,
                    "section": seq,
                    "text": body,
                    "source": "Augustine, Confessions (trans. E. B. Pusey, 1838)",
                    "license": "Public Domain (PG #3296)",
                    "axes": derive_axes(body),
                    "themes": derive_themes(body),
                }
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
                written += 1
    return written


# ── Imitation of Christ ────────────────────────────────────────────────
# Format: "THE FIRST BOOK"..."CHAPTER I"..."CHAPTER II"...
# Each chapter is one packet.

IMITATION_BOOKS = [
    ("THE FIRST BOOK",  "ADMONITIONS PROFITABLE FOR THE SPIRITUAL LIFE", 1),
    ("THE SECOND BOOK", "ADMONITIONS CONCERNING THE INNER LIFE",         2),
    ("THE THIRD BOOK",  "ON INWARD CONSOLATION",                          3),
    ("THE FOURTH BOOK", "ON THE BLESSED SACRAMENT",                       4),
]


def extract_imitation(out_path: Path) -> int:
    text = _strip_pg((RAW / "imitation_christ.txt").read_text(encoding="utf-8", errors="replace"))
    book_positions = []
    for marker, _subtitle, num in IMITATION_BOOKS:
        m = re.search(rf"^{re.escape(marker)}\s*$", text, re.MULTILINE)
        if m:
            book_positions.append((num, m.end()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    chap_re = re.compile(r"^\s*CHAPTER\s+([IVXLC]+)\s*$", re.MULTILINE)
    with out_path.open("w", encoding="utf-8") as fh:
        for idx, (book_num, start) in enumerate(book_positions):
            stop = book_positions[idx+1][1] - len("THE NTH BOOK") - 2 if idx+1 < len(book_positions) else len(text)
            block = text[start:stop]
            chapter_marks = list(chap_re.finditer(block))
            for ci, m in enumerate(chapter_marks):
                roman = m.group(1)
                body_start = m.end()
                body_end = chapter_marks[ci+1].start() if ci+1 < len(chapter_marks) else len(block)
                body = block[body_start:body_end]
                # Drop chapter title (often a single line after marker)
                body_lines = body.strip().split("\n")
                # Skip the title line (often in caps) — keep everything after first blank line
                first_blank = next((i for i, l in enumerate(body_lines) if not l.strip()), 0)
                body = "\n".join(body_lines[first_blank+1:]) if first_blank else "\n".join(body_lines[1:])
                title_line = body_lines[0].strip() if body_lines else ""
                body = re.sub(r"\s+", " ", body).strip()
                if len(body) < 40:
                    continue
                num = _roman(roman)
                packet = {
                    "id": f"imit_{book_num:02d}_{num:02d}",
                    "kind": "imitation_christ",
                    "reference": f"Imitation {book_num}.{num}",
                    "book": book_num,
                    "chapter": num,
                    "chapter_roman": roman,
                    "title": title_line,
                    "text": body,
                    "source": "Thomas à Kempis, The Imitation of Christ (trans. William Benham, 1874)",
                    "license": "Public Domain (PG #1653)",
                    "axes": derive_axes(body),
                    "themes": derive_themes(body),
                }
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
                written += 1
    return written


# ── Boethius Consolation ──────────────────────────────────────────────
# Format: BOOK I / II / III / IV / V, each with alternating I, II prose
# and SONG I, SONG II verse. We extract each prose section as a packet
# and skip the verse (it doesn't packet-ize as wisdom).

def extract_boethius(out_path: Path) -> int:
    text = _strip_pg((RAW / "boethius_consolation.txt").read_text(encoding="utf-8", errors="replace"))
    # Find BOOK I., BOOK II., ... in body (after introduction)
    book_starts = []
    for i, name in enumerate(["BOOK I.", "BOOK II.", "BOOK III.", "BOOK IV.", "BOOK V."], start=1):
        # The first occurrence may be in TOC; use the LAST occurrence which is the body
        all_m = list(re.finditer(rf"^{re.escape(name)}\s*$", text, re.MULTILINE))
        if all_m:
            book_starts.append((i, all_m[-1].end()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    # Sections within a book: "I.", "II." for prose; "SONG I.", "SONG II." for verse
    section_re = re.compile(r"^([IVXLC]+)\.\s*$", re.MULTILINE)
    song_re    = re.compile(r"^SONG\s+([IVXLC]+)\.\s*$", re.MULTILINE)
    with out_path.open("w", encoding="utf-8") as fh:
        for idx, (book_num, start) in enumerate(book_starts):
            stop = book_starts[idx+1][1] - 20 if idx+1 < len(book_starts) else len(text)
            block = text[start:stop]
            # Find all section markers (prose only, skip SONG)
            prose_marks = []
            for m in section_re.finditer(block):
                # Confirm it's not preceded by "SONG"
                back = block[max(0, m.start()-10):m.start()]
                if "SONG" not in back:
                    prose_marks.append(m)
            # Walk prose marks, each section ends at next section marker (prose or song) or end of block
            all_marks = sorted(
                [(m.start(), m.end(), m.group(1), False) for m in prose_marks] +
                [(m.start(), m.end(), m.group(1), True)  for m in song_re.finditer(block)]
            )
            for ai, (s, e, roman, is_song) in enumerate(all_marks):
                next_start = all_marks[ai+1][0] if ai+1 < len(all_marks) else len(block)
                body = block[e:next_start]
                body = re.sub(r"\s+", " ", body).strip()
                if is_song or len(body) < 60:
                    continue
                num = _roman(roman)
                packet = {
                    "id": f"boe_{book_num:02d}_{num:02d}",
                    "kind": "boethius_consolation",
                    "reference": f"Consolation {book_num}.{roman}",
                    "book": book_num,
                    "section_roman": roman,
                    "section": num,
                    "text": body,
                    "source": "Boethius, The Consolation of Philosophy (trans. H. R. James, 1897)",
                    "license": "Public Domain (PG #14328)",
                    "axes": derive_axes(body),
                    "themes": derive_themes(body),
                }
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
                written += 1
    return written


def main():
    n_aug = extract_augustine(REPO / "data" / "augustine_confessions" / "sections.jsonl")
    print(f"Augustine: {n_aug} sections")
    n_imit = extract_imitation(REPO / "data" / "imitation_christ" / "chapters.jsonl")
    print(f"Imitation: {n_imit} chapters")
    n_boe = extract_boethius(REPO / "data" / "boethius_consolation" / "sections.jsonl")
    print(f"Boethius: {n_boe} prose sections")
    print(f"TOTAL: {n_aug + n_imit + n_boe}")


if __name__ == "__main__":
    main()
