"""Extract the Apokalypsis EPUB into the serial engine.

Reads Apokalypsis_Complete.epub from the desktop, splits it into episodes
based on heading structure, and writes one JSON file per episode at
data/serials/apokalypsis/episodes/NNN.json — ready to be voiced by
ElevenLabs (or matched up to pre-existing audio files).

Output:
  data/serials/apokalypsis/source/full.txt    (whole book, plain text)
  data/serials/apokalypsis/episodes/001.json  (one per detected episode)
  ...
"""
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
DESKTOP = Path(r"C:\Users\hdven\OneDrive\Desktop")
EPUB_PATH = DESKTOP / "Apokalypsis_Complete.epub"

SERIAL_DIR  = REPO / "data" / "serials" / "apokalypsis"
SOURCE_DIR  = SERIAL_DIR / "source"
EPISODES_DIR = SERIAL_DIR / "episodes"

NS_OPF = "{http://www.idpf.org/2007/opf}"
NS_DC  = "{http://purl.org/dc/elements/1.1/}"


def _strip_xml_to_text(html_bytes: bytes) -> str:
    """Pull plain text from an XHTML page, preserving paragraph + heading structure."""
    text = html_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Mark headings so we can split on them
    text = re.sub(r"<h1[^>]*>", "\n\n###H1### ", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>", "\n\n###H2### ", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>", "\n\n###H3### ", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", " ###/H###\n\n", text, flags=re.IGNORECASE)
    # Block-level closers → paragraph breaks
    text = re.sub(r"</(p|div|li|blockquote)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    if not EPUB_PATH.exists():
        print(f"!! Missing: {EPUB_PATH}")
        sys.exit(1)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {EPUB_PATH.name}")
    with zipfile.ZipFile(EPUB_PATH) as z:
        # Locate OPF
        try:
            container = z.read("META-INF/container.xml")
            cns = "{urn:oasis:names:tc:opendocument:xmlns:container}"
            rootfile = ET.fromstring(container).find(f".//{cns}rootfile")
            opf_path = rootfile.attrib["full-path"] if rootfile is not None else None
        except (KeyError, ET.ParseError):
            opf_path = next((n for n in z.namelist() if n.endswith(".opf")), None)

        opf_dir = ""
        if opf_path and "/" in opf_path:
            opf_dir = opf_path.rsplit("/", 1)[0] + "/"

        meta = {}
        spine_paths = []
        if opf_path:
            opf_root = ET.fromstring(z.read(opf_path))
            meta_el = opf_root.find(f"{NS_OPF}metadata")
            if meta_el is not None:
                for child in meta_el:
                    tag = child.tag.replace(NS_DC, "").replace(NS_OPF, "")
                    if child.text and tag in ("title", "creator", "language", "identifier", "publisher", "date"):
                        meta.setdefault(tag, []).append(child.text)
            href_by_id = {}
            mf = opf_root.find(f"{NS_OPF}manifest")
            if mf is not None:
                for item in mf.findall(f"{NS_OPF}item"):
                    href_by_id[item.attrib.get("id", "")] = item.attrib.get("href", "")
            spine = opf_root.find(f"{NS_OPF}spine")
            if spine is not None:
                for itemref in spine.findall(f"{NS_OPF}itemref"):
                    idref = itemref.attrib.get("idref", "")
                    if idref in href_by_id:
                        spine_paths.append(opf_dir + href_by_id[idref])

        if not spine_paths:
            spine_paths = sorted([n for n in z.namelist()
                                  if n.lower().endswith((".xhtml", ".html", ".htm"))])

        print(f"  metadata: {meta}")
        print(f"  pages in spine: {len(spine_paths)}")

        # Extract every page into ordered text
        full_pages = []
        for href in spine_paths:
            try:
                raw = z.read(href)
            except KeyError:
                continue
            text = _strip_xml_to_text(raw)
            if not text or len(text) < 20:
                continue
            # Strip "chNNN.xhtml" / similar filename echoes that leak from
            # certain epub generators
            text = re.sub(r"^\s*ch\d+\.xhtml\s*\n", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\n\s*ch\d+\.xhtml\s*\n", "\n", text, flags=re.IGNORECASE)
            full_pages.append((href, text.strip()))

    # Write the full plain text
    full_text = "\n\n".join(text for _, text in full_pages)
    full_text_clean = (full_text
        .replace("###H1###", "#")
        .replace("###H2###", "##")
        .replace("###H3###", "###")
        .replace(" ###/H###", ""))
    (SOURCE_DIR / "full.txt").write_text(full_text_clean, encoding="utf-8")
    print(f"  wrote full.txt ({len(full_text_clean):,} chars)")

    # ── Episode segmentation ────────────────────────────────────────
    # Strategy: each spine page that has substantial content (> 400 chars)
    # is one episode. EPUBs typically have one chapter per XHTML file.
    # The first 1-2 pages are usually front matter (title, copyright); we
    # skip those if they have no narrative content.

    # ── Detect TOC / front matter heuristically ──
    # A TOC page has many heading-marker lines, each followed by very short
    # text (chapter labels with no prose). Real chapters have one heading
    # and then continuous prose.
    def _looks_like_toc(text: str) -> bool:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return False
        # Count consecutive lines that match "Chapter N" / "Prologue" / "Part X" patterns
        toc_pattern = re.compile(
            r"^(Chapter\s+\w+|Part\s+\w+|Prologue|Epilogue|Interlude|Apokalypsis)\b",
            re.IGNORECASE
        )
        toc_hits = sum(1 for l in lines if toc_pattern.match(l.replace("###H1###", "").replace("###H2###", "").strip()))
        return toc_hits >= 5  # five or more chapter-like lines on one page = TOC

    def _looks_like_front_matter(text: str, word_count: int) -> bool:
        # Very short pages or copyright/dedication pages
        if word_count < 80:
            return True
        # Check for copyright markers
        lower = text.lower()
        if "copyright" in lower and word_count < 400:
            return True
        if "all rights reserved" in lower and word_count < 400:
            return True
        # Dedications are short and start with "for" or "to"
        if word_count < 150 and re.search(r"^(for|to)\s+\w", text.strip(), re.IGNORECASE | re.MULTILINE):
            return True
        return False

    episode_candidates = []
    for href, text in full_pages:
        word_count = len(text.split())
        if _looks_like_front_matter(text, word_count):
            print(f"    skipping front matter: {href} ({word_count}w)")
            continue
        if _looks_like_toc(text):
            print(f"    skipping TOC: {href}")
            continue

        # Pull title from first heading marker
        title = ""
        m = re.search(r"###H[12]### ([^\n#]+?)(?: ###/H###|\n)", text)
        if m:
            title = m.group(1).strip()
        # If the title is just "Chapter N", look for a subtitle on the next heading line
        # (the actual chapter title is often on the line after "Chapter N")
        if re.match(r"^Chapter\s+\d+\s*$", title, re.IGNORECASE):
            second_match = re.findall(r"###H[12]### ([^\n#]+?)(?: ###/H###|\n)", text)
            if len(second_match) >= 2:
                second = second_match[1].strip()
                # Avoid using something that's clearly not a title
                if second and len(second) < 80 and not re.match(r"^Chapter\s+\d+\s*$", second, re.IGNORECASE):
                    title = f"{title} — {second}"

        # Clean heading markers from final text
        clean = (text
            .replace("###H1###", "")
            .replace("###H2###", "")
            .replace("###H3###", "")
            .replace(" ###/H###", "")
            .strip())
        episode_candidates.append({
            "href":  href,
            "title": title,
            "text":  clean,
            "words": word_count,
        })

    print(f"  candidate episodes (after front matter / TOC filter): {len(episode_candidates)}")

    # Heuristic: if total candidates < 50, treat each as one episode.
    # If many short pages, merge consecutive ones until each has 800+ words.
    MIN_WORDS = 800
    merged = []
    buf_text = ""
    buf_title = ""
    buf_words = 0
    for c in episode_candidates:
        if buf_words >= MIN_WORDS:
            merged.append({"title": buf_title, "text": buf_text.strip(), "words": buf_words})
            buf_text = ""
            buf_title = ""
            buf_words = 0
        if not buf_title and c["title"]:
            buf_title = c["title"]
        buf_text += "\n\n" + c["text"]
        buf_words += c["words"]
    if buf_text.strip():
        merged.append({"title": buf_title, "text": buf_text.strip(), "words": buf_words})

    print(f"  final episode count after merge: {len(merged)}")

    # Write one JSON per episode
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i, ep in enumerate(merged, start=1):
        # Skip episodes if they already exist with audio — don't overwrite
        json_path = EPISODES_DIR / f"{i:03d}.json"
        mp3_path  = EPISODES_DIR / f"{i:03d}.mp3"
        title = ep["title"] or f"Episode {i}"
        rec = {
            "serial":         "apokalypsis",
            "ep_num":         i,
            "title":          title[:200],
            "script":         ep["text"][:14000],
            "summary":        "",
            "continuity_note": "",
            "word_count":     ep["words"],
            "drafted_at_iso": now_iso,
            "ingested_from":  "Apokalypsis_Complete.epub",
            "produced":       mp3_path.exists() and mp3_path.stat().st_size > 0,
        }
        if rec["produced"]:
            rec["audio_url"] = f"/serial/apokalypsis/audio/{i}"
            rec["audio_bytes"] = mp3_path.stat().st_size
        json_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  wrote {len(merged)} episode files to {EPISODES_DIR}")
    print(f"\nSample first episode:")
    if merged:
        first = merged[0]
        print(f"  title: {first['title']}")
        print(f"  words: {first['words']}")
        print(f"  opening: {first['text'][:200]}...")


if __name__ == "__main__":
    main()
