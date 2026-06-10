#!/usr/bin/env python
"""Insert Training link right after Apothecary in every page's
topnav and lens-bar. Idempotent.
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

APO_TOPNAV = re.compile(
    r'(<a href="/apothecary\.html"[^>]*>Apothecary</a>)(?!\s*<a href="/training\.html")'
)


def main() -> int:
    total = 0
    for p in sorted(SITE.glob("*.html")):
        if p.name == "training.html":
            continue
        original = p.read_text(encoding="utf-8")
        if 'href="/apothecary.html"' not in original:
            continue
        if '/training.html' in original and 'href="/training.html"' in original:
            # already wired
            continue
        new = APO_TOPNAV.sub(
            lambda m: m.group(1) + '\n      <a href="/training.html">Training</a>'
            if "\n" in original[max(0, original.find(m.group(0)) - 20):original.find(m.group(0))]
            else m.group(1) + '<a href="/training.html">Training</a>',
            original,
        )
        # Simpler: do two passes — one for newline-separated topnav, one for inline lens-bar.
        # Topnav usually has each <a> on its own line, indented 6 spaces.
        new = original
        # Pass 1: topnav (Apothecary on own line with indentation)
        topnav_pat = re.compile(
            r'^(?P<indent>[ \t]+)<a href="/apothecary\.html"[^>]*>Apothecary</a>\s*$',
            re.MULTILINE,
        )
        def topnav_repl(m):
            ind = m.group("indent")
            return f'{m.group(0)}\n{ind}<a href="/training.html">Training</a>'
        # Only replace if next non-empty line is not already training
        def topnav_smart_replace(text):
            out = []
            lines = text.splitlines(keepends=True)
            i = 0
            n = 0
            while i < len(lines):
                out.append(lines[i])
                if topnav_pat.match(lines[i].rstrip("\r\n")):
                    j = i + 1
                    while j < len(lines) and lines[j].strip() == "":
                        j += 1
                    nxt = lines[j] if j < len(lines) else ""
                    if "/training.html" not in nxt:
                        m = topnav_pat.match(lines[i].rstrip("\r\n"))
                        ind = m.group("indent")
                        out.append(f'{ind}<a href="/training.html">Training</a>\n')
                        n += 1
                i += 1
            return "".join(out), n

        new, n1 = topnav_smart_replace(new)

        # Pass 2: inline lens-bar (Apothecary not on its own line)
        inline_pat = re.compile(
            r'(<a href="/apothecary\.html"[^>]*>Apothecary</a>)(?!\s*<a href="/training\.html")'
        )
        # Only fire in the lens-bar region of the page
        n2 = 0
        if 'class="lens-bar"' in new:
            lb_idx = new.find('class="lens-bar"')
            end_idx = new.find("</div>", lb_idx)
            if end_idx > lb_idx:
                head = new[:lb_idx]
                lb = new[lb_idx:end_idx]
                tail = new[end_idx:]
                if '/training.html' not in lb:
                    lb2, n2 = inline_pat.subn(
                        r'\1<a href="/training.html">Training</a>', lb, count=1
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
