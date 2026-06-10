"""Inject a Curriculum link into every site/*.html that has a lens-bar
but no Curriculum entry. Idempotent — re-runs are safe.

The Curriculum link goes FIRST in the lens-bar so it's discoverable on
every page a parent might land on. We don't touch pages without a
lens-bar (e.g. the operator pages) and we don't double-insert.
"""
import os
import re

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")

INJECT = '\n    <a href="/curriculum.html" class="lens-curriculum">Curriculum</a>'

# Match the lens-bar opening (label or first href) so we can inject right after
LENS_LABEL_RE = re.compile(
    r'(<div class="lens-bar"[^>]*>\s*<span class="lens-label">[^<]*</span>)'
)


def process(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    if 'href="/curriculum.html"' in html:
        return "skip (already has Curriculum)"
    if '<div class="lens-bar"' not in html:
        return "skip (no lens-bar)"
    if not LENS_LABEL_RE.search(html):
        return "skip (no recognizable lens-label)"
    new_html = LENS_LABEL_RE.sub(r"\1" + INJECT, html, count=1)
    if new_html == html:
        return "skip (no change)"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return "updated"


def main():
    updated = 0
    skipped = 0
    for fname in sorted(os.listdir(SITE)):
        if not fname.endswith(".html"):
            continue
        path = os.path.join(SITE, fname)
        result = process(path)
        if result == "updated":
            print(f"  + {fname}")
            updated += 1
        else:
            skipped += 1
    print(f"\nupdated {updated} pages, skipped {skipped}")


if __name__ == "__main__":
    main()
