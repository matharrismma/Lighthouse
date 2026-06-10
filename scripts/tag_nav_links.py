"""Tag every nav link in every HTML page with data-i18n attributes.

Walks site/*.html, finds <nav class="topnav"> blocks, and for each
<a> link inside, adds data-i18n="<key>" based on the link's visible text.

Mapping from English link text → i18n key. The key already exists in
api/i18n_strings.py STRINGS (or has been added).

Idempotent: skips links that already have data-i18n.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

# Map of nav link visible text → i18n key.
# Keep in sync with STRINGS in api/i18n_strings.py.
TEXT_TO_KEY = {
    "Almanac":          "nav.almanac",
    "Library":          "nav.library",
    "MCP":              "nav.mcp",
    "Connect":          "nav.connect",
    "Curriculum":       "nav.curriculum",
    "Walk":             "nav.walk",
    "Scribe":           "nav.scribe",
    "Daily":            "nav.daily",
    "Today":            "nav.today",
    "Bibles":           "nav.bibles",
    "Shepherd":         "nav.shepherd",
    "Apothecary":       "nav.apothecary",
    "Parable":          "nav.parable",
    "Training":         "nav.training",
    "Places":           "nav.places",
    "Receipts":         "nav.receipts",
    "Misalignments":    "nav.misalignments",
    "Atlas":            "nav.atlas",
    "Encyclopedia":     "nav.encyclopedia",
    "Chronicle":        "nav.chronicle",
    "Canon":            "nav.canon",
    "Field Kit":        "nav.fieldkit",
    "Archetypes":       "nav.archetypes",
    "Packets":          "nav.packets",
    "Run":              "nav.run",
    "Benchmark":        "nav.benchmark",
    "How it works":     "nav.how_it_works",
    "Verifiers":        "nav.verifiers",
    "Install":          "nav.install",
}

# Match a complete <a ...>text</a> within a nav.topnav block.
# We process the WHOLE file, looking for matching anchor tags.
NAV_BLOCK = re.compile(
    r'(<nav\s+class="topnav"[^>]*>)(.*?)(</nav>)',
    re.DOTALL | re.IGNORECASE,
)
ANCHOR = re.compile(
    r'(<a\s+[^>]*?>)([^<]+?)(</a>)',
    re.DOTALL,
)

def process_anchor(match: re.Match) -> str:
    """Add data-i18n to an anchor if its text matches a known nav link."""
    open_tag, text, close_tag = match.group(1), match.group(2), match.group(3)
    if "data-i18n" in open_tag:
        return match.group(0)  # already tagged
    trimmed = text.strip()
    key = TEXT_TO_KEY.get(trimmed)
    if not key:
        return match.group(0)  # not a known nav link
    # Insert data-i18n into the opening tag, right before the closing '>'
    new_open = open_tag.rstrip(">").rstrip() + f' data-i18n="{key}">'
    return new_open + text + close_tag


def process_nav(match: re.Match) -> str:
    """Apply anchor tagging to the contents of a nav block."""
    open_nav, body, close_nav = match.group(1), match.group(2), match.group(3)
    new_body = ANCHOR.sub(process_anchor, body)
    return open_nav + new_body + close_nav


tagged_count = 0
file_count = 0
for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text, n = NAV_BLOCK.subn(process_nav, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        # Count how many new data-i18n attrs were added in this file
        added = new_text.count("data-i18n") - text.count("data-i18n")
        if added > 0:
            file_count += 1
            tagged_count += added
            print(f"  + {path.relative_to(SITE)}: tagged {added} nav links")

print(f"\nDone. Tagged {tagged_count} nav links across {file_count} files.")
