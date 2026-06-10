#!/usr/bin/env python
"""Add a "A tool the Shepherd uses" strip to every lens page.

Reinforces Matt's framing (2026-05-13): the Shepherd is the operating
system; the lenses are the tools he reaches into. Each lens page now
carries a small strip at the top that says so and links to /walk.html.

The strip is inserted right before the first <main tag (or, if no
<main> exists, right before <footer>). Skipped if the page already has
a .tool-strip element. Skipped for /walk.html itself (the Shepherd's
own page) and the homepage (which already explains the metaphor).
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# Pages that should NOT get the strip
SKIP_PAGES = {
    "index", "walk", "connect", "submit", "agents", "engine", "how-it-works",
    "library",  # Library page already explains the metaphor
    # admin pages — already excluded from visitor nav
    "inbox", "dashboard", "verifiers", "benchmark", "curate",
    "contributor", "install", "setup", "run", "reach",
    "gaps", "theory", "residue", "contact",
}

# Per-page label so the strip names which tool you're looking at.
# Default is the generic "this lens"; map specific pages to their kind.
LABEL_BY_PAGE = {
    "daily":         "the daily anchor",
    "apothecary":    "the compound tool",
    "scribe":        "the writing tool",
    "bibles":        "the Scripture tool",
    "places":        "the geography tool",
    "encyclopedia":  "the A&ndash;Z tool",
    "canon":         "the canon tool",
    "archetypes":    "the pattern tool",
    "fieldkit":      "the practical tool",
    "almanac":       "the ledger tool",
    "receipts":      "the audit tool",
    "misalignments": "the disagreement tool",
    "training":      "the practice tool",
    "parable":       "the parable tool",
    "chronicle":     "the chronicle tool",
    "atlas":         "the atlas tool",
    "packets":       "the packet index",
    "works":         "the author works tool",
    "listen":        "the audio tool",
    "witness":       "the witness tool",
    "poly":          "the polymathic tool",
}

STRIP_TMPL = (
    '<div class="tool-strip">\n'
    '  <span class="tool-strip-label"><b>A tool the Shepherd uses</b>'
    ' &middot; {label}</span>\n'
    '  <a class="tool-strip-link" href="/walk.html">Open the Shepherd &rarr;</a>\n'
    '</div>\n'
)


def already_has_strip(s: str) -> bool:
    return 'class="tool-strip"' in s


def add_strip(s: str, page_stem: str) -> tuple[bool, str]:
    if already_has_strip(s):
        return False, s
    label = LABEL_BY_PAGE.get(page_stem, "one tool in the keeping")
    strip = STRIP_TMPL.format(label=label)
    # Insert before the first <main; fallback to before <footer
    target_main = re.search(r'<main\b', s)
    if target_main:
        idx = target_main.start()
    else:
        target_footer = re.search(r'<footer\b', s)
        if target_footer:
            idx = target_footer.start()
        else:
            return False, s
    new = s[:idx] + strip + s[idx:]
    return True, new


def main() -> int:
    touched = 0
    for p in sorted(SITE.glob('*.html')):
        if p.stem in SKIP_PAGES:
            continue
        src = p.read_text(encoding='utf-8')
        changed, new = add_strip(src, p.stem)
        if changed:
            p.write_text(new, encoding='utf-8')
            print(f"  {p.name:30s}  +tool-strip")
            touched += 1
    print(f"\n-- tool-strip added to {touched} files")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
