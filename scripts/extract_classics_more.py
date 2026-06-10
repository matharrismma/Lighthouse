"""Extract additional ANF01 works: Ignatius's 7 authentic letters,
Barnabas, Martyrdom of Polycarp.

For Ignatius, ANF01 prints SHORTER and LONGER recensions side-by-side
per chapter. We extract only the SHORTER (authentic) form.
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


def _roman_to_int(s: str) -> int:
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    n = 0
    for i, ch in enumerate(s):
        v = vals.get(ch, 0)
        if i+1 < len(s) and vals.get(s[i+1], 0) > v:
            n -= v
        else:
            n += v
    return n


# Chapter heading: CHAP. I.—_Title text._ on its own line.
CHAP_RE = re.compile(
    r"^\s*CHAP\.\s+([IVXLC]+)\.[—-]\s*_?([^_\n]*?)_?\s*$",
    re.MULTILINE,
)


def extract_section_shorter(text: str, start_char: int, end_char: int,
                             kind: str, ref_prefix: str, source_label: str,
                             out_path: Path) -> int:
    """Extract chapters from a section. For each CHAP. marker, look for
    'SHORTER.' block and capture body up to 'LONGER.' or next CHAP."""
    section = text[start_char:end_char]
    chapter_positions = [(m.start(), m.end(), m.group(1), m.group(2).strip())
                         for m in CHAP_RE.finditer(section)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    seen_ids = set()
    with out_path.open("w", encoding="utf-8") as fh:
        for i, (start, head_end, roman, title) in enumerate(chapter_positions):
            body_end = chapter_positions[i+1][0] if i+1 < len(chapter_positions) else len(section)
            block = section[head_end:body_end]

            # If a SHORTER. marker is present, take only the shorter portion.
            shorter_m = re.search(r"^\s*SHORTER\.\s*$", block, re.MULTILINE)
            longer_m  = re.search(r"^\s*LONGER\.\s*$",  block, re.MULTILINE)
            if shorter_m and longer_m and longer_m.start() > shorter_m.end():
                body = block[shorter_m.end():longer_m.start()]
            elif shorter_m:
                body = block[shorter_m.end():]
            else:
                body = block  # no recension markers — entire chapter

            body = re.sub(r"\[\d+\]", "", body)
            body = re.sub(r"^\s*\d{1,4}\s*$", "", body, flags=re.MULTILINE)
            body = re.sub(r"\s+", " ", body).strip()
            if len(body) < 40:
                continue
            num = _roman_to_int(roman)
            pid = f"{kind}_{num:02d}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            packet = {
                "id": pid,
                "kind": kind,
                "reference": f"{ref_prefix} {roman}",
                "chapter": num,
                "chapter_roman": roman,
                "title": title,
                "text": body,
                "source": source_label,
                "license": "Public Domain (PG #77576)",
                "axes": derive_axes(body),
                "themes": derive_themes(body),
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    return written


# Body-section character spans in anf01_pg.txt (verified by inspection).
# Each Ignatius letter body ends where the next one begins, and after
# Smyrnaeans the file moves to a separate Ignatius-to-Polycarp section.
IGNATIUS_BODIES = {
    "ignatius_eph":    (259416, 305527,  "Ignatius to the Ephesians"),
    "ignatius_mag":    (305528, 335613,  "Ignatius to the Magnesians"),
    "ignatius_tra":    (335614, 366931,  "Ignatius to the Trallians"),
    "ignatius_rom":    (366932, 391311,  "Ignatius to the Romans"),
    "ignatius_phild":  (391312, 422765,  "Ignatius to the Philadelphians"),
    "ignatius_smy":    (422766, 460000,  "Ignatius to the Smyrnaeans"),
    "ignatius_polyc":  (460000, 494831,  "Ignatius to Polycarp"),
}


def main():
    text = (RAW / "anf01_pg.txt").read_text(encoding="utf-8", errors="replace")

    total = 0

    # ── Ignatius's 7 letters (shorter recension) ───────────────────────
    for kind, (start, end, label) in IGNATIUS_BODIES.items():
        out = REPO / "data" / kind / "chapters.jsonl"
        n = extract_section_shorter(
            text, start, end, kind,
            ref_prefix=label,
            source_label=f"{label} (shorter recension; trans. Roberts-Donaldson, 1885)",
            out_path=out,
        )
        print(f"  {kind}: {n} chapters")
        total += n

    # ── Barnabas ──────────────────────────────────────────────────────
    # Find body start dynamically (heading after introduction)
    m_b = re.search(r"^\s+THE EPISTLE OF BARNABAS\.\s*\[\d+\]\s*$", text, re.MULTILINE)
    end_b = re.search(r"^\s+THE EPISTLES OF IGNATIUS\.\s*$|^\s+THE FRAGMENTS OF PAPIAS\.\s*$",
                       text[m_b.end():] if m_b else "", re.MULTILINE) if m_b else None
    if m_b and end_b:
        n = extract_section_shorter(
            text, m_b.end(), m_b.end() + end_b.start(),
            kind="barnabas",
            ref_prefix="Barnabas",
            source_label="Epistle of Barnabas (trans. Roberts-Donaldson, 1885)",
            out_path=REPO / "data" / "barnabas" / "chapters.jsonl",
        )
        print(f"  barnabas: {n} chapters")
        total += n
    else:
        print("  barnabas: BOUNDARY NOT FOUND")

    # ── Martyrdom of Polycarp ─────────────────────────────────────────
    m_p = re.search(r"^\s+THE MARTYRDOM OF POLYCARP\.\s*$", text, re.MULTILINE)
    if m_p:
        # Find body start: first CHAP. after this heading
        first_chap = re.search(r"^\s*CHAP\.\s+I\.", text[m_p.end():], re.MULTILINE)
        body_start = m_p.end() + first_chap.start() if first_chap else m_p.end()
        # Body ends at next major work
        end_p = re.search(r"^\s+THE EPISTLE OF BARNABAS\.", text[body_start:], re.MULTILINE)
        body_end = body_start + end_p.start() if end_p else len(text)
        n = extract_section_shorter(
            text, body_start, body_end,
            kind="martyrdom_polycarp",
            ref_prefix="Martyrdom of Polycarp",
            source_label="Martyrdom of Polycarp (trans. Roberts-Donaldson, 1885)",
            out_path=REPO / "data" / "martyrdom_polycarp" / "chapters.jsonl",
        )
        print(f"  martyrdom_polycarp: {n} chapters")
        total += n

    print(f"TOTAL new packets: {total}")


if __name__ == "__main__":
    main()
