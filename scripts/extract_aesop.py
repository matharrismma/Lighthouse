#!/usr/bin/env python
"""Extract Aesop's Fables (Townsend 1887) from PG #21.

Output: data/aesop/fables.jsonl — ~300 fables.

Source format: After a table of contents, each fable is structured as:
  Title\n\n\n
  Body text (potentially multi-paragraph)\n\n
  Moral (often present as a final short paragraph)\n\n\n
"""
from __future__ import annotations
import io
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "raw_sources" / "aesop" / "townsend_en.txt"
OUT_DIR = REPO / "data" / "aesop"
OUT_FILE = OUT_DIR / "fables.jsonl"

# A line that looks like a fable title: starts with capital, mostly title-case,
# 3-100 characters, no terminal punctuation.
_TITLE_RE = re.compile(
    r"^([A-Z][A-Za-z][A-Za-z, \-\'’‘]{2,100})\s*$"
)


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:80]


def split_fables(body: str) -> List[Tuple[str, str]]:
    """Split body into (title, full_body) pairs.

    In Townsend's PG #21 edition, each fable appears as two consecutive
    chunks separated by 3+ newlines: a title chunk (one line) and a body
    chunk (multi-line). Walk them in pairs.
    """
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    chunks = [c.strip() for c in re.split(r"\n{3,}", text)]
    pairs: List[Tuple[str, str]] = []
    i = 0
    while i < len(chunks) - 1:
        c = chunks[i]
        if not c:
            i += 1
            continue
        # Heuristic: a title is short (< 110 chars), no terminal punctuation,
        # mostly title-cased.
        first_line = c.split("\n", 1)[0].strip()
        is_title = (
            _TITLE_RE.match(c)
            and len(c) < 110
            and not c.endswith(".")
        )
        if is_title:
            body_chunk = chunks[i + 1].strip()
            if body_chunk and len(body_chunk) > 60:
                pairs.append((first_line, body_chunk))
                i += 2
                continue
        i += 1
    return pairs


def derive_axes(text: str) -> List[str]:
    """Aesop's are moral fables — usually about reasoning, social interaction,
    consequence. Tag axes loosely."""
    axes = {"reasoning", "information_encoding", "time_sequence"}
    t = text.lower()
    if any(w in t for w in ("fight", "war", "kill", "blood")):
        axes.add("physical_substance")
    if any(w in t for w in ("trust", "promise", "friend", "betray", "honest")):
        axes.add("authority_trust")
    if any(w in t for w in ("share", "give", "equal", "fair", "scales", "balance")):
        axes.add("conservation_balance")
    if any(w in t for w in ("eat", "food", "feed", "hunger", "thirst")):
        axes.add("metabolism")
    return sorted(axes)


def extract_moral(body: str) -> Tuple[str, Optional[str]]:
    """Many Aesop's fables end with a one-line moral.

    Heuristic: if the body's last paragraph is short (< 200 chars), italic-style,
    or starts with a moral-like cue, treat it as the moral.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return body, None
    last = paragraphs[-1]
    # Moral cues
    moral_cue = (
        len(last) < 240
        and len(paragraphs) >= 2
        and last[0].isupper()
        and "." in last
    )
    if moral_cue:
        story = "\n\n".join(paragraphs[:-1])
        return story, last
    return body, None


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1
    raw = SRC.read_text(encoding="utf-8", errors="replace")
    # Skip header
    start = raw.find("*** START OF")
    start = raw.find("\n", start) + 1
    end = raw.find("*** END OF")
    body = raw[start:end]

    # Body of fables begins after the table of contents — find the SECOND
    # occurrence of "The Wolf And The Lamb" (the first is in the TOC).
    first = body.find("The Wolf And The Lamb")
    second = body.find("The Wolf And The Lamb", first + 1)
    if second < 0:
        print("body start not found", file=sys.stderr)
        return 1
    fable_body = body[second:]

    pairs = split_fables(fable_body)
    print(f"detected {len(pairs):,} fable candidates", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT_FILE.open("w", encoding="utf-8") as out:
        seen_slugs = set()
        for title, raw_body in pairs:
            story, moral = extract_moral(raw_body)
            # Normalize whitespace inside the story
            story = re.sub(r"\s+", " ", story).strip()
            if moral:
                moral = re.sub(r"\s+", " ", moral).strip()

            slug = slugify(title)
            if slug in seen_slugs or not slug:
                continue
            seen_slugs.add(slug)

            rec = {
                "id":          f"aesop_{slug}",
                "kind":        "aesop",
                "title":       title,
                "text":        story[:4000],
                "moral":       moral,
                "axes":        derive_axes(story + " " + (moral or "")),
                "source":      "Aesop's Fables, Townsend translation (1887, PD)",
                "license":     "Public Domain",
                "attribution": "Project Gutenberg #21",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    print(f"wrote {written:,} fables to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
