"""KOA trilogy close-reading producer.

Reads each chapter of the KOA trilogy in order (Line → Door → Keeping) and
produces a close theological reading via Claude. Uses the Ch 1 reading of
The Line as the gold-standard exemplar; subsequent chapters are read at the
same depth.

The reading is *theological*, not bullet-extraction:
  • Symbolism, recurring images, what isn't said
  • Character arcs as doctrine
  • Scripture allusions
  • Cross-references to the project's existing substrate (the engine memos,
    the Apokalypsis serial, the four gates, the keeping framework)
  • Lyrical passages / songs (for music substrate)
  • Memorable lines (potential codex epigraphs)

Output: data/serials/_source/koa/codex_extraction/<book>/ch_<n>_reading.md

Resumable: skips chapters that already have a reading file.

Usage:
    python scripts/koa_chapter_reader.py [--book the-line|the-door|the-keeping|all]
                                          [--from N] [--to M]
                                          [--dry-run]
"""
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Load .env (handle BOM + empty shell values)
env_path = REPO / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not os.environ.get(k):
            os.environ[k] = v

import anthropic  # noqa: E402

KOA_DIR = REPO / "data" / "serials" / "_source" / "koa"
OUT_DIR = KOA_DIR / "codex_extraction"
EXEMPLAR = OUT_DIR / "the-line" / "ch_001_reading.md"

BOOKS = [
    ("the-line",    "The Line",    "Book 1"),
    ("the-door",    "The Door",    "Book 2"),
    ("the-keeping", "The Keeping", "Book 3"),
]

MODEL = "claude-opus-4-5"

SYSTEM_PROMPT = """You are producing close theological readings of M.R. Harris's Kings of Appalachia trilogy. You serve as part of a project that is building a codex — the canonical theological work of which this fiction is a load-bearing part.

Your task: read one chapter carefully and produce a structured close-reading in Markdown. The reading must operate at the same depth as the exemplar reading you'll see in context.

CRITICAL: This is NOT bullet-point extraction. This is close-reading commentary in the tradition of literary-theological criticism — like reading Flannery O'Connor or Marilynne Robinson where the theology IS the work and runs UNDERNEATH the plot.

What you look for:
  • Symbolism, recurring images, recurring lines (litanies, prayers, refrains)
  • Character arcs as doctrine
  • What ISN'T said — the silences, the unwritten pages, the abandoned framing
  • Scripture allusions (direct quotes, parallels, structural echoes)
  • Names — the names that "stick" and what their plainness says
  • Body knowing below language — embodied theology
  • Liturgy of the ordinary
  • Faith without map / vocational reveal
  • Eucharistic / sacramental substrates hidden in practical details
  • Cross-references to the project's working substrate:
    – "the keeping" as load-bearing terminology
    – Four gates (RED → FLOOR → BROTHERS → GOD)
    – Hitchhiker's Guide / Don't Panic posture
    – The engine serves Christ, not pattern recognition
    – The kingdom-economy / wilderness substrate

Output structure (follow exemplar):
  • Top title: "# The [Book] — Chapter [N] — A Theological Reading"
  • Source line citing the txt file
  • Multiple "## " section headings, each named for the theological theme/move
  • Quote source text directly when load-bearing
  • Explain what's underneath the plot in each section
  • End with two structured sections:
    – "## Theological themes named in this chapter (carry forward)" — numbered list
    – "## Cross-references to existing substrate" — bullet list of scripture refs + project memos
    – "## Notes for the codex compiler" — operational notes

Length: 1500-2500 words of careful commentary. Quality over coverage — better to fully develop 8 themes than skim 20.

Voice: thoughtful, attentive, willing to dwell on a single image for a paragraph. Not breathless. Not credulous. Generous to the text. Quote when quoting earns its place. Avoid restating the plot — the reader has the source open beside the reading.

You will receive:
  1. This system prompt (the approach)
  2. The exemplar reading of The Line Ch 1 (the gold standard)
  3. The new chapter's source text
  4. Brief context about which book and chapter

Return ONLY the Markdown reading. No preamble, no apology, no meta-commentary. Begin with the title heading. End with the section structure described above.
"""


def _chapter_files(slug: str) -> list[tuple[int, Path]]:
    """Return [(chapter_num, source_path)] for a book.

    ch_001.txt is title page; the actual chapters begin at ch_002.txt = Chapter 1.
    """
    book_dir = KOA_DIR / slug
    files = sorted(book_dir.glob("ch_*.txt"))
    out = []
    for i, p in enumerate(files):
        if i == 0:
            continue  # title page
        chapter_num = i  # ch_002.txt → Chapter 1, ch_003.txt → Chapter 2, etc.
        out.append((chapter_num, p))
    return out


def _read_exemplar() -> str:
    return EXEMPLAR.read_text(encoding="utf-8")


def _build_user_message(book_title: str, book_label: str, chapter_num: int,
                        source_text: str, exemplar: str) -> str:
    return f"""Below is the gold-standard exemplar reading you must match in depth and approach.

=== EXEMPLAR: The Line, Chapter 1 (close reading) ===

{exemplar}

=== END EXEMPLAR ===

Now produce a close reading at the same depth for:

Book: {book_title} ({book_label})
Chapter: {chapter_num}

=== SOURCE TEXT ===

{source_text}

=== END SOURCE TEXT ===

Produce the Markdown close-reading now. Begin with the title heading."""


def read_chapter(client, book_slug: str, book_title: str, book_label: str,
                 chapter_num: int, source_path: Path,
                 out_path: Path, exemplar: str) -> dict:
    """Run one chapter reading via Claude. Returns timing/cost stats."""
    source = source_path.read_text(encoding="utf-8")
    source_words = len(source.split())

    user_msg = _build_user_message(book_title, book_label, chapter_num, source, exemplar)

    t0 = time.time()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    elapsed = time.time() - t0

    reading = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            reading += block.text
    reading = reading.strip()

    # Light validation
    if not reading.startswith("# "):
        # Try to find the first heading
        idx = reading.find("# ")
        if idx >= 0:
            reading = reading[idx:]

    reading_words = len(reading.split())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(reading, encoding="utf-8")

    usage = resp.usage
    return {
        "source_words":   source_words,
        "reading_words":  reading_words,
        "elapsed_sec":    elapsed,
        "input_tokens":   getattr(usage, "input_tokens", 0),
        "output_tokens":  getattr(usage, "output_tokens", 0),
    }


def main():
    book_filter = "all"
    from_ch = 1
    to_ch = 999
    dry = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--book" and i + 1 < len(args):
            book_filter = args[i + 1]; i += 1
        elif a == "--from" and i + 1 < len(args):
            from_ch = int(args[i + 1]); i += 1
        elif a == "--to" and i + 1 < len(args):
            to_ch = int(args[i + 1]); i += 1
        elif a == "--dry-run":
            dry = True
        i += 1

    if not EXEMPLAR.exists():
        print(f"ERROR: exemplar missing at {EXEMPLAR}", file=sys.stderr)
        sys.exit(1)
    exemplar = _read_exemplar()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not configured", file=sys.stderr)
        sys.exit(1)
    print(f"API key length: {len(api_key)}, prefix: {api_key[:7]}")

    client = anthropic.Anthropic(api_key=api_key) if not dry else None

    total_in = 0
    total_out = 0
    total_chapters = 0
    t_total = time.time()

    print(f"\n=== KOA chapter reader — model: {MODEL} ===")
    print(f"Book filter: {book_filter}  Range: ch{from_ch}-ch{to_ch}  Dry: {dry}\n")

    for slug, title, label in BOOKS:
        if book_filter != "all" and book_filter != slug:
            continue

        chapters = _chapter_files(slug)
        print(f"--- {title} ({label}): {len(chapters)} chapters ---")

        for chapter_num, src_path in chapters:
            if chapter_num < from_ch or chapter_num > to_ch:
                continue

            out_path = OUT_DIR / slug / f"ch_{chapter_num:03d}_reading.md"
            if out_path.exists():
                print(f"  ch{chapter_num:02d}: already read ({out_path.stat().st_size:,} bytes), skip")
                continue

            print(f"  ch{chapter_num:02d}: reading {src_path.name}...", flush=True)

            if dry:
                source = src_path.read_text(encoding="utf-8")
                print(f"    [dry-run] would read {len(source.split())} words")
                continue

            try:
                stats = read_chapter(
                    client, slug, title, label, chapter_num,
                    src_path, out_path, exemplar
                )
                print(f"    -> {stats['reading_words']:,} words of reading"
                      f"  in {stats['elapsed_sec']:.0f}s"
                      f"  (in {stats['input_tokens']:,}t, out {stats['output_tokens']:,}t)",
                      flush=True)
                total_in += stats["input_tokens"]
                total_out += stats["output_tokens"]
                total_chapters += 1
            except Exception as e:
                print(f"    FAILED: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr, flush=True)
                continue

        print()

    elapsed = (time.time() - t_total) / 60
    print(f"=== Done in {elapsed:.1f} min ===")
    print(f"Chapters read: {total_chapters}")
    print(f"Total input tokens:  {total_in:,}")
    print(f"Total output tokens: {total_out:,}")
    # Opus 4.5 pricing approx: $15/M input, $75/M output (no caching)
    cost = (total_in / 1_000_000 * 15.0) + (total_out / 1_000_000 * 75.0)
    print(f"Approx cost (Opus 4.5): ${cost:.2f}")


if __name__ == "__main__":
    main()
