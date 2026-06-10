#!/usr/bin/env python
"""Slim the topnav across all visitor-facing pages to 7 anchors.

Two structural patterns exist in the codebase:
  A) index.html — <nav class="topnav"><wordmark/><div class="navlinks">...</div></nav>
  B) every other lens page — <nav class="topnav"><home-icon/><a>...</a><a>...</a>...</nav>

Both get the same slim link set, with the current page marked .active.
Admin pages (Pass 1 list) are skipped — their nav is already different.

Slim links: Today | Apothecary | Shepherd | Scribe | Bibles | Almanac | Field Kit
The full lens inventory still lives in the lens-bar on each page.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# Admin pages — keep their nav as-is.
ADMIN_PAGES = {
    "inbox", "dashboard", "verifiers", "benchmark", "curate",
    "contributor", "install", "setup", "run", "reach", "agents",
    "gaps", "theory",
}

# slug → (href, label, mobile_keep)
# Library is the umbrella for Bibles, Places, Encyclopedia, Canon, Archetypes,
# Field Kit. Bibles stays in nav (high-use); the rest are inside Library.
LINKS = [
    ("daily",     "/daily.html",      "Today",     True),
    ("apothecary","/apothecary.html", "Apothecary",False),
    ("walk",      "/walk.html",       "Shepherd",  True),
    ("scribe",    "/scribe.html",     "Scribe",    True),
    ("bibles",    "/bibles.html",     "Bibles",    False),
    ("almanac",   "/almanac.html",    "Almanac",   True),
    ("library",   "/library.html",    "Library",   False),
]


# Pages that should mark "Library" active in the topnav.
LIBRARY_PAGES = {"library", "places", "encyclopedia", "canon", "archetypes", "fieldkit"}


def is_active(slug: str, page_stem: str) -> bool:
    if slug == page_stem:
        return True
    if slug == "library" and page_stem in LIBRARY_PAGES:
        return True
    return False


def render_pattern_b_links(page_stem: str) -> str:
    """For pages that have flat <a> tags directly inside <nav class=topnav>.
    Keeps the home icon already present; emits the 7 slim links + connect."""
    out_lines = []
    for slug, href, label, mobile in LINKS:
        cls_parts = []
        if mobile:
            cls_parts.append("keep-on-mobile")
        if is_active(slug, page_stem):
            cls_parts.append("active")
        cls = f' class="{" ".join(cls_parts)}"' if cls_parts else ""
        out_lines.append(f'            <a href="{href}"{cls}>{label}</a>')
    return "\n".join(out_lines)


def render_pattern_a_navlinks(page_stem: str) -> str:
    """For index.html — inside <div class="navlinks">."""
    out_lines = []
    for slug, href, label, mobile in LINKS:
        cls_parts = []
        if mobile:
            cls_parts.append("keep-on-mobile")
        if is_active(slug, page_stem):
            cls_parts.append("active")
        cls = f' class="{" ".join(cls_parts)}"' if cls_parts else ""
        out_lines.append(f'    <a href="{href}"{cls}>{label}</a>')
    out_lines.append('')
    out_lines.append('    <span class="live-dot always" id="liveDot">live</span>')
    out_lines.append('    <a href="/connect.html" class="cta always">Connect →</a>')
    return "\n".join(out_lines)


NAVLINKS_OPEN_A = re.compile(r'<div\s+class="navlinks"[^>]*>', re.IGNORECASE)
TOPNAV_OPEN = re.compile(r'<nav\s+class="topnav"[^>]*>', re.IGNORECASE)


def slim_pattern_a(s: str, stem: str) -> tuple[int, str]:
    m = NAVLINKS_OPEN_A.search(s)
    if not m:
        return 0, s
    start = m.end()
    depth = 1
    i = start
    while i < len(s) and depth > 0:
        open_div = s.find('<div', i)
        close_div = s.find('</div>', i)
        if close_div < 0:
            return 0, s
        if 0 <= open_div < close_div:
            depth += 1
            i = open_div + 4
        else:
            depth -= 1
            i = close_div + 6
    end = i - 6
    new = s[:start] + '\n' + render_pattern_a_navlinks(stem) + '\n  ' + s[end:]
    return 1, new


def slim_pattern_b(s: str, stem: str) -> tuple[int, str]:
    """Find <nav class="topnav">, replace contents *except* the first
    nav-home <a> if it exists, with the slim link set."""
    m = TOPNAV_OPEN.search(s)
    if not m:
        return 0, s
    nav_start = m.end()
    nav_end = s.find('</nav>', nav_start)
    if nav_end < 0:
        return 0, s
    block = s[nav_start:nav_end]
    # Preserve the home icon link if present
    home_match = re.search(r'<a\s+href="/"\s+class="nav-home"[^>]*>.*?</a>',
                           block, flags=re.DOTALL | re.IGNORECASE)
    home = home_match.group(0) if home_match else ''
    new_block = ('\n      ' + home + '\n' if home else '\n')
    new_block += render_pattern_b_links(stem) + '\n    '
    new = s[:nav_start] + new_block + s[nav_end:]
    return 1, new


def main() -> int:
    files_touched = 0
    for p in sorted(SITE.glob('*.html')):
        if p.stem in ADMIN_PAGES:
            continue
        stem = p.stem if p.stem != 'index' else ''
        src = p.read_text(encoding='utf-8')
        # Try Pattern A first (index.html); fall through to B otherwise.
        n, new = slim_pattern_a(src, stem)
        if n == 0:
            n, new = slim_pattern_b(src, stem)
        if n and new != src:
            p.write_text(new, encoding='utf-8')
            print(f"  {p.name:30s}  topnav slimmed")
            files_touched += 1
    print(f"\n-- topnav slimmed in {files_touched} files")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
