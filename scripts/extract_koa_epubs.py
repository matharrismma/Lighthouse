"""Extract the three KOA EPUBs and consolidate their prose into plain text
files we can ingest into the serial engine as source material.

Each EPUB → data/serials/_source/koa/<book_slug>/
  meta.json     (title, language, identifier, manifest)
  full.txt      (all chapter prose concatenated, headings preserved)
  ch_NNN.txt    (one per detected chapter)
"""
import json
import re
import sys
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
DESKTOP = Path(r"C:\Users\hdven\OneDrive\Desktop")
OUT_BASE = REPO / "data" / "serials" / "_source" / "koa"

BOOKS = [
    ("KoA_TheDoor_KDP.epub",     "the-door",     "The Door"),
    ("KoA_TheKeeping_FINAL.epub","the-keeping",  "The Keeping"),
    ("KoA_TheLine_FINAL.epub",   "the-line",     "The Line"),
]

NS_OPF = "{http://www.idpf.org/2007/opf}"
NS_DC  = "{http://purl.org/dc/elements/1.1/}"
NS_XHTML = "{http://www.w3.org/1999/xhtml}"


def _strip_xml(html_bytes: bytes) -> str:
    """Pull readable text from an XHTML page. Preserves paragraph breaks."""
    text = html_bytes.decode("utf-8", errors="replace")
    # Drop styles/scripts entirely
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level closers with double newlines
    text = re.sub(r"</(p|div|h[1-6]|li|blockquote)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Replace headings with marker prefixes so we can re-detect chapters later
    text = re.sub(r"<h1[^>]*>", "\n\n###H1### ", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>", "\n\n###H2### ", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>", "\n\n###H3### ", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    # Normalize whitespace within paragraphs
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_one(epub_path: Path, slug: str, title: str) -> dict:
    out_dir = OUT_BASE / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"slug": slug, "title": title, "source_file": epub_path.name}

    with zipfile.ZipFile(epub_path) as z:
        names = z.namelist()

        # Find the OPF (container.xml points at it)
        try:
            container = z.read("META-INF/container.xml")
            root = ET.fromstring(container)
            ns = "{urn:oasis:names:tc:opendocument:xmlns:container}"
            rootfile = root.find(f".//{ns}rootfile")
            opf_path = rootfile.attrib["full-path"] if rootfile is not None else None
        except (KeyError, ET.ParseError):
            opf_path = next((n for n in names if n.endswith(".opf")), None)

        opf_dir = ""
        if opf_path and "/" in opf_path:
            opf_dir = opf_path.rsplit("/", 1)[0] + "/"

        # Parse OPF to get reading order
        manifest_paths = []
        meta = {}
        if opf_path:
            try:
                opf_root = ET.fromstring(z.read(opf_path))
                meta_el = opf_root.find(f"{NS_OPF}metadata")
                if meta_el is not None:
                    for child in meta_el:
                        tag = child.tag.replace(NS_DC, "").replace(NS_OPF, "")
                        if child.text and tag in ("title", "creator", "language", "identifier", "publisher", "date"):
                            meta.setdefault(tag, []).append(child.text)
                # Build href map from manifest
                href_by_id = {}
                manifest_el = opf_root.find(f"{NS_OPF}manifest")
                if manifest_el is not None:
                    for item in manifest_el.findall(f"{NS_OPF}item"):
                        href_by_id[item.attrib.get("id", "")] = item.attrib.get("href", "")
                # Spine = reading order
                spine_el = opf_root.find(f"{NS_OPF}spine")
                if spine_el is not None:
                    for itemref in spine_el.findall(f"{NS_OPF}itemref"):
                        idref = itemref.attrib.get("idref", "")
                        if idref in href_by_id:
                            href = href_by_id[idref]
                            manifest_paths.append(opf_dir + href)
            except (KeyError, ET.ParseError) as e:
                summary["warn"] = f"opf parse failed: {e}"

        # Fallback if no spine: scan for xhtml/html files
        if not manifest_paths:
            manifest_paths = sorted([n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))])

        summary["metadata"] = meta
        summary["pages_in_spine"] = len(manifest_paths)

        # Concatenate prose
        all_text_parts = []
        chapters = []
        current_ch_lines = []
        ch_idx = 0

        for href in manifest_paths:
            try:
                raw = z.read(href)
            except KeyError:
                continue
            text = _strip_xml(raw)
            if not text or len(text) < 30:
                continue
            all_text_parts.append(text)
            # Split into chapters using ###H1### / ###H2### markers
            for line in text.split("\n"):
                if re.match(r"^###H[12]###", line):
                    if current_ch_lines:
                        ch_idx += 1
                        ch_text = "\n".join(current_ch_lines).strip()
                        if ch_text:
                            chapters.append((ch_idx, ch_text))
                            (out_dir / f"ch_{ch_idx:03d}.txt").write_text(
                                ch_text, encoding="utf-8"
                            )
                    current_ch_lines = [line.replace("###H1###", "#").replace("###H2###", "##").strip()]
                else:
                    current_ch_lines.append(line)

        if current_ch_lines:
            ch_idx += 1
            ch_text = "\n".join(current_ch_lines).strip()
            if ch_text:
                chapters.append((ch_idx, ch_text))
                (out_dir / f"ch_{ch_idx:03d}.txt").write_text(ch_text, encoding="utf-8")

        # Full concatenated text
        full = "\n\n".join(all_text_parts)
        # Clean the chapter markers from the full text for readability
        full = full.replace("###H1###", "#").replace("###H2###", "##").replace("###H3###", "###")
        (out_dir / "full.txt").write_text(full, encoding="utf-8")

        summary["chapter_count"]   = len(chapters)
        summary["word_count_full"] = len(full.split())
        summary["bytes_full"]      = len(full.encode("utf-8"))

        (out_dir / "meta.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return summary


def main():
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    overall = []
    for fname, slug, title in BOOKS:
        epub = DESKTOP / fname
        if not epub.exists():
            print(f"!! missing: {epub}")
            continue
        print(f"Extracting {title}...")
        s = extract_one(epub, slug, title)
        overall.append(s)
        print(f"  -> {s['chapter_count']} chapters, ~{s['word_count_full']:,} words")
    summary_path = OUT_BASE / "_index.json"
    summary_path.write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote summary index: {summary_path}")


if __name__ == "__main__":
    main()
