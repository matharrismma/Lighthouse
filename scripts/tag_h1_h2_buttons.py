"""Tag h2 headings and button text on pages with low i18n coverage.

For each .html in site/, finds <h2>...</h2> blocks and <button>...</button>
blocks with plain text inside (no nested HTML), and tags them with
data-i18n="page.<slug>.heading.<n>" or data-i18n="page.<slug>.button.<n>".

Outputs to data/i18n_extras_keys.json so STRINGS can auto-load them.

Skips text containing {} placeholders, ${} templates, or that's already tagged.
Idempotent.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

# Match <h2 ...>plain text</h2> with text that has no nested HTML
H2_RE = re.compile(r'(<h2\b[^>]*>)([^<]+?)(</h2>)', re.IGNORECASE)
# Match <button ...>plain text</button>
BUTTON_RE = re.compile(r'(<button\b[^>]*?>)([^<]+?)(</button>)', re.IGNORECASE)


def slug_from_path(path: Path) -> str:
    rel = path.relative_to(SITE).with_suffix("")
    return str(rel).replace("\\", "__").replace("/", "__").replace("-", "_")


def is_taggable(text: str) -> bool:
    """Heuristic: skip text that's purely symbolic, numeric, or templated."""
    t = text.strip()
    if not t or len(t) < 2:
        return False
    if "${" in t or "{{" in t:
        return False
    # Mostly punctuation/digits? Skip.
    alpha = sum(1 for c in t if c.isalpha())
    if alpha < 2:
        return False
    return True


def tag_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    slug = slug_from_path(path)
    new_keys: dict = {}
    heading_counter = [0]
    button_counter = [0]

    def handle_h2(m: re.Match) -> str:
        open_tag, inner, close = m.group(1), m.group(2), m.group(3)
        if "data-i18n" in open_tag:
            return m.group(0)
        clean = inner.strip()
        if not is_taggable(clean):
            return m.group(0)
        heading_counter[0] += 1
        key = f"page.{slug}.heading.{heading_counter[0]}"
        new_keys[key] = clean
        new_open = open_tag.rstrip(">").rstrip() + f' data-i18n="{key}">'
        return new_open + inner + close

    def handle_button(m: re.Match) -> str:
        open_tag, inner, close = m.group(1), m.group(2), m.group(3)
        if "data-i18n" in open_tag:
            return m.group(0)
        clean = inner.strip()
        if not is_taggable(clean):
            return m.group(0)
        button_counter[0] += 1
        key = f"page.{slug}.button.{button_counter[0]}"
        new_keys[key] = clean
        new_open = open_tag.rstrip(">").rstrip() + f' data-i18n="{key}">'
        return new_open + inner + close

    text = H2_RE.sub(handle_h2, text)
    text = BUTTON_RE.sub(handle_button, text)
    path.write_text(text, encoding="utf-8")
    return new_keys


# Focus on pages the audit flagged as low-coverage
TARGET_PAGES = [
    "engine.html", "grid.html", "poly.html", "keep.html", "setup.html",
    "install.html", "connect.html", "mcp.html", "contributor.html",
    "submit.html", "share.html", "theory.html", "canon.html",
]

# Also tag pages we missed from before
all_extras = {}
files_processed = 0
keys_added = 0

for page in TARGET_PAGES:
    p = SITE / page
    if not p.exists():
        continue
    keys = tag_page(p)
    if keys:
        all_extras.update(keys)
        files_processed += 1
        keys_added += len(keys)
        print(f"  + {page}: tagged {len(keys)} elements")

# Save extras to a separate JSON so STRINGS can pick them up
out_path = REPO / "data" / "i18n_extras_keys.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(all_extras, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nProcessed {files_processed} files, added {keys_added} keys")
print(f"Wrote {out_path.relative_to(REPO)}")
