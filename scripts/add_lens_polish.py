"""Add <link rel="stylesheet" href="/lens-polish.css"> to every HTML.
Inserts right after the mobile.css link. Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<link rel="stylesheet" href="/lens-polish.css">'
MOBILE_RE = re.compile(r'(<link\s+rel="stylesheet"\s+href="/mobile\.css"\s*/?>)', re.IGNORECASE)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = 0
skipped = 0

for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "/lens-polish.css" in text:
        skipped += 1
        continue
    if MOBILE_RE.search(text):
        new_text = MOBILE_RE.sub(r'\1\n  ' + INCLUDE, text, count=1)
    else:
        m = HEAD_END.search(text)
        if not m:
            continue
        new_text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]
    path.write_text(new_text, encoding="utf-8")
    added += 1

print(f"Added lens-polish.css to {added} files. Skipped {skipped}.")
