#!/usr/bin/env python
"""Insert Apothecary chip into lens-bars where Today shares a line with .lens-label.

Pattern: <span class="lens-label">Lenses</span><a href="/daily.html">Today</a>
Insert:  ...Today</a><a href="/apothecary.html">Apothecary</a>
Idempotent: skip if /apothecary.html is already next to Today in the lens-bar.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
TODAY_INLINE = re.compile(
    r'(<a href="/daily\.html"[^>]*>Today</a>)(?!\s*<a href="/apothecary\.html")'
)


def main() -> int:
    total = 0
    for p in sorted(SITE.glob("*.html")):
        if p.name == "apothecary.html":
            continue
        original = p.read_text(encoding="utf-8")
        # Only process pages that have a lens-bar with inline Today
        if 'class="lens-bar"' not in original:
            continue
        lb_idx = original.find('class="lens-bar"')
        # carve out the lens-bar region (up to closing </div> after it)
        end_idx = original.find("</div>", lb_idx)
        if end_idx == -1:
            continue
        head = original[:lb_idx]
        lb_region = original[lb_idx:end_idx]
        tail = original[end_idx:]
        if '/apothecary.html' in lb_region:
            continue
        new_lb, n = TODAY_INLINE.subn(
            r'\1<a href="/apothecary.html">Apothecary</a>', lb_region, count=1
        )
        if n == 0:
            continue
        p.write_text(head + new_lb + tail, encoding="utf-8")
        print(f"site/{p.name}  lens-bar +1")
        total += 1
    print(f"-- {total} lens-bar insertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
