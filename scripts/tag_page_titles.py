"""Tag every page's <title> and first <h1> with data-i18n attributes.

For each HTML file in site/:
  1. Extract <title> text → key page.<slug>.title
  2. Extract first <h1> text (only if it's plain text, no nested HTML) → key page.<slug>.h1
  3. Add data-i18n-page-title="page.<slug>.title" to the <html> tag
  4. Add data-i18n="page.<slug>.h1" to the <h1> opening tag

Also writes a JSON file `data/i18n_page_keys.json` with every key→English text,
which gets merged into STRINGS in api/i18n_strings.py.

Idempotent: skips already-tagged elements.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

# Extract <title>...</title>
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
# Find <html ...> opening tag
HTML_RE = re.compile(r"<html([^>]*)>", re.IGNORECASE)
# Find the first <h1 ...>text</h1> with plain text only (no nested HTML)
H1_RE = re.compile(r'(<h1\b[^>]*>)([^<]+?)(</h1>)', re.IGNORECASE)


def slug_from_path(path: Path) -> str:
    """site/scribe.html → 'scribe'; site/use-cases/faith.html → 'use_cases__faith'."""
    rel = path.relative_to(SITE).with_suffix("")
    return str(rel).replace("\\", "__").replace("/", "__").replace("-", "_")


def tag_page(path: Path) -> dict:
    """Tag a single HTML file. Returns {key: english_text} for new entries."""
    text = path.read_text(encoding="utf-8", errors="replace")
    slug = slug_from_path(path)
    new_keys: dict = {}

    # ── Extract and tag <title> ──
    title_match = TITLE_RE.search(text)
    if title_match:
        title_text = title_match.group(1).strip()
        title_key = f"page.{slug}.title"
        new_keys[title_key] = title_text

        # Add data-i18n-page-title to <html> tag (if not already there)
        def add_to_html(m: re.Match) -> str:
            attrs = m.group(1)
            if "data-i18n-page-title" in attrs:
                return m.group(0)
            return f"<html{attrs} data-i18n-page-title=\"{title_key}\">"

        text = HTML_RE.sub(add_to_html, text, count=1)

    # ── Extract and tag first <h1> ──
    h1_match = H1_RE.search(text)
    if h1_match:
        open_tag, h1_text, close_tag = h1_match.group(1), h1_match.group(2).strip(), h1_match.group(3)
        if "data-i18n" not in open_tag and h1_text:
            h1_key = f"page.{slug}.h1"
            new_keys[h1_key] = h1_text
            new_open = open_tag.rstrip(">").rstrip() + f' data-i18n="{h1_key}">'
            # Replace only the first occurrence
            text = text.replace(h1_match.group(0), new_open + h1_match.group(2) + close_tag, 1)

    path.write_text(text, encoding="utf-8")
    return new_keys


all_keys: dict = {}
processed = 0

for path in SITE.rglob("*.html"):
    keys = tag_page(path)
    if keys:
        all_keys.update(keys)
        processed += 1

# Write keys to JSON
out_path = REPO / "data" / "i18n_page_keys.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(all_keys, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Tagged {processed} pages. {len(all_keys)} new i18n keys.")
print(f"Wrote {out_path.relative_to(REPO)}")
print()
print("Sample keys:")
for k, v in list(all_keys.items())[:10]:
    print(f"  {k}: {v[:60]}")
