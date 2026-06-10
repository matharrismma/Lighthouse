"""Extract Molasses.epub into a serial under data/serials/molasses/.

Molasses is a 4-part novel (~43k words) by M.R. Harris about the Great
Molasses Flood of Boston, January 15, 1919. The EPUB title page credits
K. Hale Harris (the author's wife) but Matt confirmed the public byline
on narrowhighway.com should be M.R. Harris.

EPUB structure:
  ch001.xhtml — title/dedication (~21 words, skip into world.json metadata)
  ch002.xhtml — Part 1: Sept 29 1918 / Jan 15 1919  (~13k words)
  ch003.xhtml — Part 2: aftermath  (~7.5k words)
  ch004.xhtml — Part 3: THE PROCEEDING (the trial)  (~13k words)
  ch005.xhtml — Part 4: coda  (~9.5k words)

Output:
  data/serials/molasses/world.json
  data/serials/molasses/episodes/001.json  (Part 1)
  data/serials/molasses/episodes/002.json  (Part 2)
  data/serials/molasses/episodes/003.json  (Part 3)
  data/serials/molasses/episodes/004.json  (Part 4)
"""
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = Path("C:/Users/hdven/iCloudDrive/M.R_/Molasses.epub")
OUT_DIR = REPO / "data" / "serials" / "molasses"
EP_DIR = OUT_DIR / "episodes"

PART_FILES = [
    ("EPUB/text/ch002.xhtml", 1, "The Tank"),
    ("EPUB/text/ch003.xhtml", 2, "The Flood"),
    ("EPUB/text/ch004.xhtml", 3, "The Proceeding"),
    ("EPUB/text/ch005.xhtml", 4, "What Remains"),
]


def html_to_paragraphs(raw: str) -> list[dict]:
    """Convert XHTML body to a list of structured paragraphs.

    Each paragraph dict:
      {"kind": "heading"|"paragraph"|"break", "text": str, "level": int?}
    """
    # Drop the head, keep body
    m = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else raw

    # Strip any inline scripts/styles
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.DOTALL | re.IGNORECASE)

    paragraphs = []

    # Find all block-level elements in order
    pattern = re.compile(
        r"<(h[1-6]|p|div|hr)([^>]*)>(.*?)</\1>|<hr[^>]*/?>",
        re.DOTALL | re.IGNORECASE,
    )

    for m in pattern.finditer(body):
        tag = (m.group(1) or "hr").lower()
        inner = m.group(3) or ""
        # Strip nested HTML
        text = re.sub(r"<[^>]+>", "", inner)
        # Normalize whitespace, decode common entities
        text = (text.replace("&nbsp;", " ")
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&quot;", '"')
                    .replace("&#39;", "'")
                    .replace("&#8212;", "—")
                    .replace("&#8211;", "–")
                    .replace("&#8217;", "'")
                    .replace("&#8216;", "'")
                    .replace("&#8220;", '"')
                    .replace("&#8221;", '"'))
        text = re.sub(r"\s+", " ", text).strip()
        if not text and tag != "hr":
            continue
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            paragraphs.append({"kind": "heading", "level": int(tag[1]), "text": text})
        elif tag == "hr":
            paragraphs.append({"kind": "break"})
        elif tag in {"p", "div"} and text:
            # Skip stray filename leakage like "ch004.xhtml"
            if re.match(r"^ch\d+\.xhtml$", text.strip()):
                continue
            paragraphs.append({"kind": "paragraph", "text": text})

    return paragraphs


def detect_chapter_breaks(paragraphs: list[dict]) -> list[tuple[int, str]]:
    """Find positions where 'Chapter N' or 'PART N' markers appear.

    Returns list of (index, marker_label).
    """
    breaks = []
    for i, p in enumerate(paragraphs):
        if p.get("kind") != "paragraph" and p.get("kind") != "heading":
            continue
        text = p.get("text", "")
        m = re.match(r"^(Chapter\s+\d+|PART\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|\d+))[\s—–-]*", text, re.IGNORECASE)
        if m:
            breaks.append((i, m.group(0).strip()))
    return breaks


def main():
    if not SRC.exists():
        raise SystemExit(f"missing: {SRC}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EP_DIR.mkdir(parents=True, exist_ok=True)
    # Clear any prior episodes
    for f in EP_DIR.glob("*"):
        f.unlink()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_words = 0

    with zipfile.ZipFile(SRC) as z:
        # Pull title-page text into world.json blurb seed
        title_raw = z.read("EPUB/text/ch001.xhtml").decode("utf-8", errors="replace")
        title_paragraphs = html_to_paragraphs(title_raw)
        title_text = " ".join(p.get("text", "") for p in title_paragraphs if p.get("text"))

        for filename, ep_num, ep_title in PART_FILES:
            raw = z.read(filename).decode("utf-8", errors="replace")
            paragraphs = html_to_paragraphs(raw)

            # Drop any duplicate part-title heading at the start
            while paragraphs and paragraphs[0].get("kind") == "heading":
                paragraphs.pop(0)

            # Compute word count
            words = sum(len(p.get("text", "").split())
                        for p in paragraphs if p.get("text"))
            total_words += words

            # Detect internal chapter breaks for navigation
            chapter_breaks = detect_chapter_breaks(paragraphs)

            rec = {
                "serial":           "molasses",
                "ep_num":           ep_num,
                "title":            ep_title,
                "part_label":       f"Part {ep_num}",
                "paragraphs":       paragraphs,
                "chapter_breaks":   [{"index": idx, "label": lbl} for idx, lbl in chapter_breaks],
                "word_count":       words,
                "summary":          "",
                "drafted_at_iso":   now_iso,
                "ingested_from":    Path(filename).name,
                "source_kind":      "epub_chapter",
                "produced":         False,
                "audio_url":        None,
            }
            out = EP_DIR / f"{ep_num:03d}.json"
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ep {ep_num:02d} '{ep_title}' -- {words:,} words, {len(paragraphs)} paragraphs, {len(chapter_breaks)} internal chapters")

    # world.json — Matt confirmed public byline is M.R. Harris, title is "Molasses"
    world = {
        "slug": "molasses",
        "name": "Molasses",
        "tagline": "A novel of the Great Molasses Flood, Boston, 1919.",
        "author": "M.R. Harris",
        "blurb": (
            "January 15, 1919. The temperature has risen overnight from below freezing "
            "to above it. A two-million-gallon tank of molasses stands on Commercial Street "
            "in the North End of Boston. He is not on Commercial Street when it happens. "
            "He is in an office on the other side of the city, reading a set of plans for "
            "a water treatment facility in Dorchester, doing the ordinary work of a man who "
            "assesses structures and writes what he finds and goes on to the next structure. "
            "He hears the tank go. Then the proceeding, and what remains."
        ),
        "logline": "The Great Molasses Flood of 1919, told from the tank engineer's chair and the proceeding's table.",
        "status": "complete",
        "kind": "novel_with_text",
        "episode_count": 4,
        "total_words": total_words,
        "release_cadence": "Complete. Read at any pace.",
        "source": {
            "format": "EPUB",
            "filename": "Molasses.epub",
            "metadata_title": "Molasses",
            "metadata_creator_on_file": "K. Hale Harris (the author's wife; the work is M.R. Harris)",
            "public_byline": "M.R. Harris",
        },
        "principal_characters": [
            {"name": "The Engineer", "role": "Tank assessor / narrator-by-circumstance",
             "description": "Reads plans, assesses structures, writes what he finds. Was not on Commercial Street when the tank went. Carries the proceeding inside him afterward."},
            {"name": "Hugh Ogden", "role": "Court-appointed auditor",
             "description": "Appointed by the court on March 3, 1920. Described as a man who reads documents rather than deciding in advance what documents said — the quality the proceeding required."},
            {"name": "Marco", "role": "Lost in the flood",
             "description": "Appears in memory. The unfinished sentence: 'Marco would have—'"},
        ],
        "themes": [
            "What the gap between knowing and doing fills with.",
            "The proceeding — the legal sifting after the catastrophic event.",
            "Reading documents rather than deciding in advance what documents said.",
            "The true thing, said without apology and without ornament.",
            "Memory and the unfinished sentence."
        ],
        "voice_register": (
            "First-person and close-third by turns. Long sentences that earn their place, "
            "each clause measured. Plainness about the body and the work. Specific physical detail. "
            "Theological grain is structural, never preachy. The book is about precision — "
            "the precision of weather instruments, of structural assessments, of words said "
            "without ornament."
        ),
    }
    (OUT_DIR / "world.json").write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"Wrote world.json + {len(PART_FILES)} parts.")
    print(f"Total: {total_words:,} words across 4 parts.")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
