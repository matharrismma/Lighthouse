"""Add <script src="/audio.js"></script> after a11y.js on every HTML.
Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<script src="/audio.js"></script>'
A11Y_RE = re.compile(r'(<script\s+src="/a11y\.js"></script>)', re.IGNORECASE)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = 0
skipped = 0

for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "/audio.js" in text:
        skipped += 1
        continue
    if A11Y_RE.search(text):
        new_text = A11Y_RE.sub(r'\1\n  ' + INCLUDE, text, count=1)
    else:
        m = HEAD_END.search(text)
        if not m:
            continue
        new_text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]
    path.write_text(new_text, encoding="utf-8")
    added += 1

print(f"Added audio.js to {added} files. Skipped {skipped}.")
