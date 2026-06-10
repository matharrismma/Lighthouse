"""KOA codex aggregator — walks the chapter readings, extracts themes +
scripture cross-references, clusters them, and produces a draft doctrinal
report organized under the codex's authority spine.

The authority spine (per Matt 2026-05-15):
  Tier 1: Words in Red (Jesus' direct words)
  Tier 2: Bible (rest of Scripture)
  Tier 3: Disciples + Didache + Church Fathers
  Tier 4: Matt's writing (KOA, etc.) — illustration, not authority

The aggregator's job is NOT to invent a doctrinal TOC. It's to surface what
the readings actually produced so Matt can direct the TOC's structure from
what's there.

Outputs to data/serials/_source/koa/codex_extraction/AGGREGATE_REPORT.md.

Usage:
    python scripts/koa_codex_aggregator.py
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXTRACTION_DIR = REPO / "data" / "serials" / "_source" / "koa" / "codex_extraction"
BOOKS = [
    ("the-line",    "The Line",    "Book 1"),
    ("the-door",    "The Door",    "Book 2"),
    ("the-keeping", "The Keeping", "Book 3"),
]
REPORT = EXTRACTION_DIR / "AGGREGATE_REPORT.md"


# Regexes for parsing the reading files
RX_SECTION_HEAD = re.compile(r"^##\s+(.+)$", re.MULTILINE)
RX_THEMES_BLOCK = re.compile(
    r"##\s+Theological themes named in this chapter[^\n]*\n+(.*?)(?=\n## |\Z)",
    re.IGNORECASE | re.DOTALL,
)
RX_CROSSREF_BLOCK = re.compile(
    r"##\s+Cross-references to existing substrate[^\n]*\n+(.*?)(?=\n## |\Z)",
    re.IGNORECASE | re.DOTALL,
)
RX_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", re.MULTILINE)
# Scripture-reference pattern: "Exodus 14-15", "1 Corinthians 11:23-26", "Hebrews 11:8", etc.
RX_SCRIPTURE = re.compile(
    r"\b(?:1\s+|2\s+|3\s+|I\s+|II\s+|III\s+)?(?:"
    r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|"
    r"Joshua|Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|"
    r"Job|Psalms?|Proverbs|Ecclesiastes|Song of Songs|"
    r"Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|"
    r"Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    r"Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|"
    r"Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation"
    r")\s+\d+(?::\d+(?:-\d+)?)?(?:-\d+(?::\d+)?)?",
)


def _parse_reading(path: Path) -> dict:
    """Return {themes: [...], cross_refs: [...], section_titles: [...]}"""
    text = path.read_text(encoding="utf-8")

    # Section titles (## headings)
    section_titles = [m.strip() for m in RX_SECTION_HEAD.findall(text)]

    # Themes
    themes = []
    m = RX_THEMES_BLOCK.search(text)
    if m:
        themes_block = m.group(1)
        for item in RX_LIST_ITEM.findall(themes_block):
            # Strip leading **bold** markers and trailing dashes
            t = re.sub(r"^\*\*([^*]+)\*\*\s*[—-]?\s*", r"\1: ", item).strip()
            themes.append(t)

    # Cross-references
    cross_refs = []
    m = RX_CROSSREF_BLOCK.search(text)
    if m:
        cr_block = m.group(1)
        for item in RX_LIST_ITEM.findall(cr_block):
            cross_refs.append(item.strip())

    # Scripture refs anywhere in the text
    scripture_hits = RX_SCRIPTURE.findall(text)

    return {
        "themes":          themes,
        "cross_refs":      cross_refs,
        "section_titles":  section_titles,
        "scripture_refs":  scripture_hits,
    }


def main():
    if not EXTRACTION_DIR.exists():
        print(f"ERROR: no extraction dir at {EXTRACTION_DIR}", file=sys.stderr)
        sys.exit(1)

    all_readings = []
    per_book = defaultdict(list)
    for slug, title, label in BOOKS:
        bdir = EXTRACTION_DIR / slug
        if not bdir.exists(): continue
        for f in sorted(bdir.glob("ch_*_reading.md")):
            parsed = _parse_reading(f)
            parsed["file"] = str(f.relative_to(REPO))
            parsed["book_slug"] = slug
            parsed["book_title"] = title
            parsed["book_label"] = label
            # Extract chapter number from filename
            m = re.match(r"ch_(\d+)_reading\.md", f.name)
            parsed["chapter_num"] = int(m.group(1)) if m else 0
            all_readings.append(parsed)
            per_book[slug].append(parsed)

    if not all_readings:
        print("No readings found yet.", file=sys.stderr)
        sys.exit(0)

    # ── Aggregation ──
    theme_counter = Counter()
    theme_to_chapters = defaultdict(list)
    crossref_counter = Counter()
    section_title_counter = Counter()
    scripture_counter = Counter()
    scripture_to_chapters = defaultdict(list)

    for r in all_readings:
        chapter_key = f"{r['book_slug']}/ch_{r['chapter_num']:03d}"
        for t in r["themes"]:
            # Normalize: take the part before colon or dash if it exists
            t_norm = re.split(r"[:—-]", t, maxsplit=1)[0].strip().lower()
            theme_counter[t_norm] += 1
            theme_to_chapters[t_norm].append(chapter_key)
        for cr in r["cross_refs"]:
            crossref_counter[cr] += 1
        for s in r["section_titles"]:
            section_title_counter[s] += 1
        for sref in r["scripture_refs"]:
            # Normalize
            s_norm = re.sub(r"\s+", " ", sref).strip()
            scripture_counter[s_norm] += 1
            scripture_to_chapters[s_norm].append(chapter_key)

    # ── Write report ──
    lines = []
    lines.append("# KOA Codex Aggregate Report")
    lines.append("")
    lines.append(f"Generated from {len(all_readings)} chapter readings across the trilogy.")
    lines.append("")
    lines.append("**Authority spine (codex hierarchy):**")
    lines.append("- Tier 1: Words in Red (Jesus' direct words)")
    lines.append("- Tier 2: Bible (rest of Scripture)")
    lines.append("- Tier 3: Disciples + Didache + Church Fathers")
    lines.append("- Tier 4: Matt's writing (KOA) — illustration, not authority")
    lines.append("")
    lines.append("This report surfaces what the readings produced. It does NOT impose a TOC.")
    lines.append("Matt directs the doctrinal TOC structure from what's surfaced here.")
    lines.append("")

    # Per-book counts
    lines.append("## Coverage")
    lines.append("")
    lines.append("| Book | Chapters read |")
    lines.append("|---|---|")
    for slug, title, label in BOOKS:
        lines.append(f"| {title} ({label}) | {len(per_book[slug])} |")
    lines.append("")

    # Recurring themes (frequency)
    lines.append("## Recurring themes (frequency across chapters)")
    lines.append("")
    lines.append("Themes named by the readings, ordered by how often they recur. **Recurrence is signal** — themes that surface in many chapters across multiple books are candidate codex chapter headings.")
    lines.append("")
    lines.append("| Recurrence | Theme | Chapters |")
    lines.append("|---|---|---|")
    for theme, count in theme_counter.most_common(80):
        chapters = theme_to_chapters[theme]
        chap_str = ", ".join(sorted(set(chapters))[:8])
        if len(set(chapters)) > 8:
            chap_str += f", + {len(set(chapters)) - 8} more"
        lines.append(f"| {count} | {theme} | {chap_str} |")
    lines.append("")

    # Scripture cross-references
    lines.append("## Scripture cross-references (Tier 1-2 substrate touched)")
    lines.append("")
    lines.append("Scripture passages identified by the readings. Concentration indicates which canonical passages the KOA trilogy most heavily illuminates. **These are candidate authority anchors for the codex's chapters.**")
    lines.append("")
    lines.append("| Recurrence | Passage | Chapters |")
    lines.append("|---|---|---|")
    for s, count in scripture_counter.most_common(60):
        chapters = scripture_to_chapters[s]
        chap_str = ", ".join(sorted(set(chapters))[:6])
        if len(set(chapters)) > 6:
            chap_str += f", + {len(set(chapters)) - 6} more"
        lines.append(f"| {count} | {s} | {chap_str} |")
    lines.append("")

    # Substrate cross-references (Tier 3 + project memos)
    lines.append("## Cross-references to existing project substrate")
    lines.append("")
    lines.append("Substrate echoes named by the readings — Patristics, project memos, four-gate concepts, etc.")
    lines.append("")
    lines.append("| Recurrence | Reference |")
    lines.append("|---|---|")
    for cr, count in crossref_counter.most_common(50):
        lines.append(f"| {count} | {cr} |")
    lines.append("")

    # Per-chapter section titles (the close-reading section heads)
    lines.append("## All section titles (one row per chapter)")
    lines.append("")
    lines.append("Each chapter's reading was organized by section. These section titles are themselves theological observations. Reading them in sequence gives a chapter-by-chapter spine of the trilogy's doctrinal moves.")
    lines.append("")
    for slug, title, label in BOOKS:
        chapters = sorted(per_book[slug], key=lambda r: r["chapter_num"])
        if not chapters: continue
        lines.append(f"### {title} ({label})")
        lines.append("")
        for r in chapters:
            lines.append(f"**Ch {r['chapter_num']:02d}** — {r['file']}")
            for st in r["section_titles"]:
                lines.append(f"  - {st}")
            lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report: {REPORT}")
    print(f"  Total readings: {len(all_readings)}")
    print(f"  Unique recurring themes: {len(theme_counter)}")
    print(f"  Unique scripture refs:   {len(scripture_counter)}")
    print(f"  Unique substrate refs:   {len(crossref_counter)}")


if __name__ == "__main__":
    main()
