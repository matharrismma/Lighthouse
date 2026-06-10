#!/usr/bin/env python
"""Insert <a href="/apothecary.html">Apothecary</a> right after the Today link
in every site/*.html that has a .topnav and/or .lens-bar block.

Skip apothecary.html itself (already correct).
Idempotent: if "/apothecary.html" already appears in the nav block, leave it alone.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
SKIP = {"apothecary.html"}

# Match the Today line in either nav region; preserve original indentation.
TODAY_LINE = re.compile(
    r'^(?P<indent>[ \t]*)<a href="/daily\.html"[^>]*>Today</a>\s*$',
    re.MULTILINE,
)

APO_TOPNAV_LINE = '      <a href="/apothecary.html">Apothecary</a>'
APO_LENSBAR_LINE = '    <a href="/apothecary.html">Apothecary</a>'


def has_apothecary_in_nav(html: str) -> bool:
    return '"/apothecary.html"' in html


def insert_after_today(html: str, path: Path) -> tuple[str, int]:
    """Insert Apothecary after every Today line that doesn't already have it next."""
    changes = 0
    new_lines: list[str] = []
    lines = html.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        if TODAY_LINE.match(line.rstrip("\r\n")):
            # peek at next non-empty line; skip if already has apothecary
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            nxt = lines[j] if j < len(lines) else ""
            if "/apothecary.html" not in nxt:
                indent = re.match(r"^([ \t]*)", line).group(1)
                ins = f'{indent}<a href="/apothecary.html">Apothecary</a>\n'
                new_lines.append(ins)
                changes += 1
        i += 1
    return "".join(new_lines), changes


def main() -> int:
    total = 0
    for p in sorted(SITE.rglob("*.html")):
        if p.name in SKIP:
            continue
        original = p.read_text(encoding="utf-8")
        if 'href="/daily.html">Today' not in original:
            continue
        updated, n = insert_after_today(original, p)
        if n > 0 and updated != original:
            p.write_text(updated, encoding="utf-8")
            rel = p.relative_to(SITE.parent)
            print(f"{rel}  +{n} insertion(s)")
            total += n
    print(f"-- {total} total insertions across site/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
