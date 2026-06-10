#!/usr/bin/env python
"""Pass 1 of the project-wide nav consolidation.

Remove links to admin/operator pages from visitor-facing navigation
(topnav, lens-bar, and footer nav blocks). The admin pages remain
accessible by direct URL; they're just not surfaced to visitors who
are browsing the lens grid.

Admin pages hidden from visitor nav:
  inbox, dashboard, verifiers, benchmark, curate, contributor,
  install, setup, run, reach, agents, gaps, theory

These remain in `site/` and still respond to requests — operators
who know the URL can still reach them.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# Pages that should NOT appear in visitor nav
ADMIN_PAGES = {
    "inbox", "dashboard", "verifiers", "benchmark", "curate",
    "contributor", "install", "setup", "run", "reach", "agents",
    "gaps", "theory", "keep",
}

# Matches a single <a> tag whose href points to one of the admin pages.
# Handles variations: with attrs (class="active"), with text content,
# optional surrounding whitespace + separators.
ADMIN_HREF_PAT = "|".join(ADMIN_PAGES)
LINK_RE = re.compile(
    rf'(\s*\|\s*|\s*<span class="sep">[·•]</span>\s*)?'
    rf'<a\s+[^>]*href="/(?:{ADMIN_HREF_PAT})\.html"[^>]*>[^<]*</a>'
    rf'(\s*\|\s*|\s*<span class="sep">[·•]</span>\s*)?',
    re.IGNORECASE,
)

# Also catch links that appear inline in body prose (e.g.,
# "<a href="/verifiers.html">Verifiers</a>" in a sentence). Conservative:
# only strip them when they're explicitly in nav contexts.
# We'll target only inside <nav> and <footer> and class="lens-bar" elements.

NAV_BLOCK_RES = [
    (re.compile(r'<nav\s+class="topnav"[^>]*>', re.IGNORECASE), '</nav>'),
    (re.compile(r'<div\s+class="lens-bar"[^>]*>', re.IGNORECASE), '</div>'),
    (re.compile(r'<footer[^>]*>',                 re.IGNORECASE), '</footer>'),
    (re.compile(r'<nav\s+class="footer-nav"[^>]*>', re.IGNORECASE), '</nav>'),
]


def strip_admin_links_in_block(s: str) -> str:
    """Strip admin-page links from a single block of HTML, leaving the
    rest intact. Handles trailing separators."""
    return LINK_RE.sub("", s)


def process_file(path: Path) -> tuple[int, str]:
    """Return (changes_made, new_content). Walks each nav/footer block
    and strips admin links from inside it. Body prose is left alone."""
    src = path.read_text(encoding="utf-8")
    new = src
    changes = 0
    for open_re, close_tag in NAV_BLOCK_RES:
        # Find all opening tags
        for m in list(open_re.finditer(new)):
            start = m.end()
            end = new.find(close_tag, start)
            if end < 0:
                continue
            block = new[start:end]
            cleaned = strip_admin_links_in_block(block)
            if cleaned != block:
                new = new[:start] + cleaned + new[end:]
                changes += 1
    return changes, new


def main() -> int:
    total_changes = 0
    files_touched = 0
    for p in sorted(SITE.glob("*.html")):
        # Skip the admin pages themselves — they can keep their own nav
        # (operators reading them already know what they're looking at).
        if p.stem in ADMIN_PAGES:
            continue
        changes, new = process_file(p)
        if changes:
            p.write_text(new, encoding="utf-8")
            print(f"  {p.name}  -{changes} admin-nav block(s) cleaned")
            files_touched += 1
            total_changes += changes
    print(f"\n-- touched {files_touched} files, {total_changes} blocks cleaned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
