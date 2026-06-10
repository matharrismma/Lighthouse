#!/usr/bin/env python
"""Extract John Bunyan's Pilgrim's Progress Part 1 (1678, PD) from PG #131.

Output: data/pilgrim/sections.jsonl — 404 numbered sections.

Source format: the PG edition marks sections {1}, {2}, ... up to {404},
each containing a paragraph or two of allegorical text. Bible references
appear in square brackets [Book Ch:V].
"""
from __future__ import annotations
import io
import json
import re
import sys
from pathlib import Path
from typing import List

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "raw_sources" / "pilgrim" / "en.txt"
OUT_DIR = REPO / "data" / "pilgrim"
OUT_FILE = OUT_DIR / "sections.jsonl"

# Recognize Bible book abbreviations as they appear in Bunyan's marginal
# refs — Heb. Rom. Matt. Rev. 1 Cor. 2 Pet. etc.
_BIB_REF_RE = re.compile(
    r"\b((?:[1-3]\s+)?[A-Z][a-zA-Z]{1,12}\.?)\s+(\d+):(\d+(?:-\d+)?)"
)


def derive_axes(text: str) -> List[str]:
    """Pilgrim's Progress is allegorical journey. Standard axes:
       - time_sequence (journey)
       - authority_trust (gates, witnesses)
       - information_encoding (allegory)
    Tweak per-section by content cues."""
    axes = {"time_sequence", "authority_trust", "information_encoding"}
    t = text.lower()
    if any(w in t for w in ("burden", "guilt", "sin", "shame", "doubt", "fear", "despair")):
        axes.add("metabolism")
    if any(w in t for w in ("body", "wound", "tired", "weary", "strength", "sleep")):
        axes.add("physical_substance")
    if any(w in t for w in ("balance", "scales", "weigh", "judge", "judgment")):
        axes.add("conservation_balance")
    if any(w in t for w in ("reason", "argue", "discourse", "logic", "wisdom")):
        axes.add("reasoning")
    return sorted(axes)


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1

    raw = SRC.read_text(encoding="utf-8", errors="replace")
    # Strip PG header + footer
    start = raw.find("*** START OF")
    end = raw.find("*** END OF")
    if start < 0 or end < 0:
        print("PG markers not found", file=sys.stderr)
        return 1
    # Move past the header line
    start = raw.find("\n", start) + 1
    body = raw[start:end]

    # Split on {N} markers
    chunks = re.split(r"\{(\d+)\}", body)
    # First chunk is the preface (before {1}); skip it.
    # After split: [preface, '1', text1, '2', text2, ...]
    if len(chunks) < 3:
        print("no numbered sections found", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT_FILE.open("w", encoding="utf-8") as out:
        # Track section numbers to avoid duplicates from the two-part numbering
        # (PG edition starts at {1} fresh in different appendix sections — we
        # keep ALL sections as they appear since each is unique content).
        seen_numbers = set()
        i = 1
        while i < len(chunks):
            try:
                num = int(chunks[i])
            except (ValueError, IndexError):
                i += 2
                continue
            if i + 1 >= len(chunks):
                break
            text_raw = chunks[i + 1]

            # The text continues until the next {N} marker which is already
            # split out. Trim leading/trailing whitespace + normalize.
            text = text_raw.strip()
            if not text:
                i += 2
                continue

            # Extract scripture-style references in [...] brackets first
            bracket_refs = re.findall(r"\[([^\]]+)\]", text)
            # Also catch inline Bible refs even without brackets
            inline_refs = []
            for m in _BIB_REF_RE.finditer(text):
                inline_refs.append(f"{m.group(1)} {m.group(2)}:{m.group(3)}")
            # Dedupe + cap
            refs = []
            seen = set()
            for r in bracket_refs + inline_refs:
                r = re.sub(r"\s+", " ", r).strip(" .,;:")
                if r and r not in seen:
                    seen.add(r)
                    refs.append(r)
            refs = refs[:25]

            # Strip bracketed paratext from the visible text (it was Bunyan's
            # marginal Bible-ref notes, not body content). Keep bare text.
            visible = re.sub(r"\[[^\]]+\]", "", text)
            visible = re.sub(r"\s+", " ", visible).strip()
            if not visible:
                i += 2
                continue

            # Skip very-short sections (often just a quoted Bible verse marker)
            if len(visible) < 40:
                i += 2
                continue

            # Construct a unique ID. Use both section number and seen-count
            # so duplicate section numbers (rare but possible) don't collide.
            seq_id = num
            disambig = 0
            while (seq_id, disambig) in seen_numbers:
                disambig += 1
            seen_numbers.add((seq_id, disambig))
            id_suffix = f"{seq_id:03d}" + (f"_{disambig}" if disambig else "")

            # Derive a short title from the first sentence
            first_sentence = re.split(r"(?<=[.!?])\s", visible, maxsplit=1)[0][:80]

            rec = {
                "id":             f"pilgrim_{id_suffix}",
                "kind":           "pilgrim",
                "section":        num,
                "title":          first_sentence,
                "text":           visible[:6000],
                "scripture_refs": refs,
                "axes":           derive_axes(visible),
                "source":         "Pilgrim's Progress, Part 1 (John Bunyan, 1678)",
                "license":        "Public Domain",
                "attribution":    "Project Gutenberg #131",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            i += 2

    print(f"wrote {written:,} sections to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
