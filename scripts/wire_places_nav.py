#!/usr/bin/env python
"""Insert Places link right after Bibles in every page's topnav and lens-bar.

Same pattern as wire_bibles_nav.py / wire_apothecary_nav.py. Idempotent.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"


def main() -> int:
    total = 0
    for p in sorted(SITE.glob("*.html")):
        if p.name == "places.html":
            continue
        original = p.read_text(encoding="utf-8")
        if 'href="/bibles.html"' not in original:
            continue

        new = original
        n1 = 0
        n2 = 0

        # Topnav: bibles.html line on its own, indented. Insert Places after.
        bibles_topnav = re.compile(
            r'^(?P<indent>[ \t]+)<a href="/bibles\.html"[^>]*>Bibles</a>\s*$',
            re.MULTILINE,
        )
        out_lines: list[str] = []
        lines = new.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            out_lines.append(lines[i])
            m = bibles_topnav.match(lines[i].rstrip("\r\n"))
            if m:
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                nxt = lines[j] if j < len(lines) else ""
                if "/places.html" not in nxt:
                    ind = m.group("indent")
                    out_lines.append(f'{ind}<a href="/places.html">Places</a>\n')
                    n1 += 1
            i += 1
        new = "".join(out_lines)

        # Lens-bar: bibles.html link may be inline.
        if 'class="lens-bar"' in new:
            lb_idx = new.find('class="lens-bar"')
            end_idx = new.find("</div>", lb_idx)
            if end_idx > lb_idx:
                head = new[:lb_idx]
                lb = new[lb_idx:end_idx]
                tail = new[end_idx:]
                if '/places.html' not in lb:
                    inline_pat = re.compile(
                        r'(<a href="/bibles\.html"[^>]*>Bibles</a>)(?!\s*<a href="/places\.html")'
                    )
                    lb2, n2 = inline_pat.subn(
                        r'\1<a href="/places.html">Places</a>', lb, count=1
                    )
                    new = head + lb2 + tail

        if (n1 + n2) > 0 and new != original:
            p.write_text(new, encoding="utf-8")
            print(f"{p.name}  topnav+{n1}  lens-bar+{n2}")
            total += n1 + n2
    print(f"-- {total} total insertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
