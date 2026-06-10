"""Parse public-domain classical-wisdom sources into packet substrate.

Inputs (already fetched into data/raw_sources/):
  aurelius_meditations.txt   — Project Gutenberg 2680 (George Long 1862)
  larochefoucauld_maxims.txt — Project Gutenberg 9105 (Bund/Friswell 1871)
  didache_pg42053.txt        — PG 42053 (Hitchcock-Brown 1884, English section)
  anf01_pg.txt               — PG 77576 (Roberts-Donaldson Ante-Nicene Fathers Vol I)

Outputs:
  data/aurelius/sayings.jsonl       — ~500 Roman-numeral sayings across 12 books
  data/larochefoucauld/maxims.jsonl — 504 numbered maxims
  data/didache/chapters.jsonl       — 16 chapters (English translation)
  data/clement1/chapters.jsonl      — 65 chapters of 1 Clement
  data/polycarp/chapters.jsonl      — 14 chapters of Polycarp's Epistle to the Philippians

All texts are unambiguously public domain (US: published before 1928).
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
RAW = REPO / "data" / "raw_sources"


# ── Marcus Aurelius ──────────────────────────────────────────────────────

AURELIUS_BOOK_MARKERS = [
    "THE FIRST BOOK", "THE SECOND BOOK", "THE THIRD BOOK", "THE FOURTH BOOK",
    "THE FIFTH BOOK", "THE SIXTH BOOK", "THE SEVENTH BOOK", "THE EIGHTH BOOK",
    "THE NINTH BOOK", "THE TENTH BOOK", "THE ELEVENTH BOOK", "THE TWELFTH BOOK",
]
AURELIUS_SAYING_RE = re.compile(r"^([IVXLC]+)\.\s+(.+)", re.MULTILINE)


def extract_aurelius(out_path: Path) -> int:
    text = (RAW / "aurelius_meditations.txt").read_text(encoding="utf-8", errors="replace")
    # Find each book's start line
    book_positions: list[tuple[int, int]] = []  # (book_number, start_index)
    for idx, marker in enumerate(AURELIUS_BOOK_MARKERS, start=1):
        # Match the marker on its own line
        m = re.search(rf"^{re.escape(marker)}\s*$", text, re.MULTILINE)
        if m:
            book_positions.append((idx, m.end()))
    # End boundaries — next book's start, or commentary section (BOOK II "Both...)
    end_idx = re.search(r"^BOOK [IVX]+\s+", text, re.MULTILINE)
    final_end = end_idx.start() if end_idx else len(text)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for i, (book_num, start) in enumerate(book_positions):
            stop = book_positions[i + 1][1] - len(AURELIUS_BOOK_MARKERS[i + 1]) - 2 if i + 1 < len(book_positions) else final_end
            block = text[start:stop]
            # Split by Roman-numeral paragraph markers at the start of a line
            # A saying starts with "I. " or "XV. " on a new paragraph.
            # Use a regex split keeping the marker.
            parts = re.split(r"\n\n(?=[IVXLC]+\.\s)", "\n\n" + block.strip())
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                m = re.match(r"^([IVXLC]+)\.\s+([\s\S]+)$", p)
                if not m:
                    continue
                roman, body = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
                if len(body) < 20:
                    continue
                packet = {
                    "id": f"aur_{book_num:02d}_{roman.lower()}",
                    "kind": "aurelius",
                    "reference": f"Meditations {book_num}.{roman}",
                    "book": book_num,
                    "section_roman": roman,
                    "text": body,
                    "source": "Marcus Aurelius, Meditations (trans. George Long, 1862)",
                    "license": "Public Domain (PG #2680)",
                    "axes": _derive_axes(body),
                    "themes": _derive_themes(body),
                }
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
                written += 1
    return written


# ── La Rochefoucauld ─────────────────────────────────────────────────────

# Each maxim begins "N.--" on its own line. Body may span multiple lines.
LARO_MAXIM_RE = re.compile(
    r"^(\d{1,3})\.--(.+?)(?=^\d{1,3}\.--|^\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_larochefoucauld(out_path: Path) -> int:
    text = (RAW / "larochefoucauld_maxims.txt").read_text(encoding="utf-8", errors="replace")
    # Restrict to body — between *** START *** and *** END ***
    body_match = re.search(
        r"\*\*\*\s*START.*?\*\*\*(.*?)\*\*\*\s*END",
        text, re.DOTALL,
    )
    body = body_match.group(1) if body_match else text

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    # Split paragraphs by blank-line gaps so we can find each maxim block
    # cleanly. Then match the numbered prefix.
    pat = re.compile(r"^(\d{1,3})\.--\s*(.+?)(?=\n\n\d{1,3}\.--|\n\n\s*$|\Z)",
                     re.MULTILINE | re.DOTALL)
    with out_path.open("w", encoding="utf-8") as fh:
        for m in pat.finditer(body):
            num = int(m.group(1))
            content = re.sub(r"\s+", " ", m.group(2)).strip()
            if not content:
                continue
            packet = {
                "id": f"laroch_{num:03d}",
                "kind": "larochefoucauld",
                "reference": f"Maxim {num}",
                "number": num,
                "text": content,
                "source": "François de La Rochefoucauld, Maxims (trans. Bund/Friswell, 1871)",
                "license": "Public Domain (PG #9105)",
                "axes": _derive_axes(content),
                "themes": _derive_themes(content),
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


# ── Didache (English translation from PG 42053) ──────────────────────────

DIDACHE_CHAP_RE = re.compile(
    r"^Chap\.?\s+([IVX]+|[0-9]+):\s*(\d+)\s+—\s*(.+?)(?=^Chap\.?\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_didache(out_path: Path) -> int:
    text = (RAW / "didache_pg42053.txt").read_text(encoding="utf-8", errors="replace")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for m in DIDACHE_CHAP_RE.finditer(text):
            chap_roman = m.group(1)
            chap_num = m.group(2)
            content_raw = m.group(3)
            # Strip footnote marks like [N], page numbers, line numbers, Greek
            content = re.sub(r"\[\d+\]", "", content_raw)
            content = re.sub(r"^\s*\d{3,4}\s*$", "", content, flags=re.MULTILINE)  # drop page numbers
            # Drop any Greek runs (any line that's >50% Greek characters)
            cleaned_lines = []
            for line in content.splitlines():
                if not line.strip():
                    cleaned_lines.append("")
                    continue
                greek_count = sum(1 for c in line if 'Ͱ' <= c <= 'Ͽ' or 'ἀ' <= c <= '῿')
                if greek_count > len(line) * 0.3:
                    continue
                cleaned_lines.append(line)
            content = "\n".join(cleaned_lines)
            content = re.sub(r"\s+", " ", content).strip()
            if len(content) < 20:
                continue
            packet = {
                "id": f"did_{int(chap_num):02d}",
                "kind": "didache",
                "reference": f"Didache {chap_num}",
                "chapter": int(chap_num),
                "chapter_roman": chap_roman,
                "text": content,
                "source": "Didache, Teaching of the Twelve Apostles (trans. Hitchcock & Brown, 1884)",
                "license": "Public Domain (PG #42053)",
                "axes": _derive_axes(content),
                "themes": _derive_themes(content),
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


# ── 1 Clement (from ANF01) ───────────────────────────────────────────────

# CHAP. I.—_Title._  ...body... (chapter title is italicised between underscores)
ANF_CHAP_RE = re.compile(
    r"^\s*CHAP\.\s+([IVXLC]+)\.[—-]\s*_?([^_\n]*?)_?\s*$",
    re.MULTILINE,
)


def _extract_anf_section(start_re: str, end_re: str, kind: str, ref_prefix: str,
                        source_label: str, out_path: Path) -> int:
    """Generic extractor for any single-work section of ANF01."""
    text = (RAW / "anf01_pg.txt").read_text(encoding="utf-8", errors="replace")
    start_m = re.search(start_re, text, re.MULTILINE)
    if not start_m:
        return 0
    end_m = re.search(end_re, text[start_m.end():], re.MULTILINE)
    end_idx = start_m.end() + end_m.start() if end_m else len(text)
    section = text[start_m.end():end_idx]

    # Find chapter markers and their following bodies
    chapter_positions = [(m.start(), m.end(), m.group(1), m.group(2).strip())
                         for m in ANF_CHAP_RE.finditer(section)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for i, (start, head_end, roman, title) in enumerate(chapter_positions):
            body_end = chapter_positions[i + 1][0] if i + 1 < len(chapter_positions) else len(section)
            body = section[head_end:body_end]
            # Strip footnote refs like [12], page numbers, blank chaff
            body = re.sub(r"\[\d+\]", "", body)
            body = re.sub(r"^\s*\d{1,4}\s*$", "", body, flags=re.MULTILINE)
            body = re.sub(r"\s+", " ", body).strip()
            if len(body) < 40:
                continue
            # Convert Roman to int for stable id ordering
            num = _roman_to_int(roman)
            packet = {
                "id": f"{kind}_{num:02d}",
                "kind": kind,
                "reference": f"{ref_prefix} {roman}",
                "chapter": num,
                "chapter_roman": roman,
                "title": title,
                "text": body,
                "source": source_label,
                "license": "Public Domain (PG #77576)",
                "axes": _derive_axes(body),
                "themes": _derive_themes(body),
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


def _roman_to_int(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    n = 0
    for i, c in enumerate(s):
        v = vals.get(c, 0)
        if i + 1 < len(s) and vals.get(s[i + 1], 0) > v:
            n -= v
        else:
            n += v
    return n


def extract_clement1(out_path: Path) -> int:
    return _extract_anf_section(
        start_re=r"^\s+THE FIRST EPISTLE OF CLEMENT TO THE CORINTHIANS\.\[1\]",
        end_re=r"^\s+THE EPISTLE OF POLYCARP\.\s*$",
        kind="clement1",
        ref_prefix="1 Clement",
        source_label="First Epistle of Clement to the Corinthians (trans. Roberts-Donaldson, 1885)",
        out_path=out_path,
    )


def extract_polycarp(out_path: Path) -> int:
    return _extract_anf_section(
        start_re=r"^\s+THE EPISTLE OF POLYCARP TO THE PHILIPPIANS\.",
        end_re=r"^\s+THE MARTYRDOM OF POLYCARP\.|^\s+THE EPISTLES OF IGNATIUS",
        kind="polycarp",
        ref_prefix="Polycarp to the Philippians",
        source_label="Epistle of Polycarp to the Philippians (trans. Roberts-Donaldson, 1885)",
        out_path=out_path,
    )


# ── Axis + theme derivation (reused from Proverbs patterns) ──────────────

sys.path.insert(0, str(REPO / "scripts"))
from extract_proverbs import derive_axes as _derive_axes, derive_themes as _derive_themes


def main():
    n_aur = extract_aurelius(REPO / "data" / "aurelius" / "sayings.jsonl")
    print(f"Aurelius: {n_aur} sayings")

    n_lar = extract_larochefoucauld(REPO / "data" / "larochefoucauld" / "maxims.jsonl")
    print(f"La Rochefoucauld: {n_lar} maxims")

    n_did = extract_didache(REPO / "data" / "didache" / "chapters.jsonl")
    print(f"Didache: {n_did} chapters")

    n_cle = extract_clement1(REPO / "data" / "clement1" / "chapters.jsonl")
    print(f"1 Clement: {n_cle} chapters")

    n_pol = extract_polycarp(REPO / "data" / "polycarp" / "chapters.jsonl")
    print(f"Polycarp to the Philippians: {n_pol} chapters")

    print(f"TOTAL new packets: {n_aur + n_lar + n_did + n_cle + n_pol}")


if __name__ == "__main__":
    main()
