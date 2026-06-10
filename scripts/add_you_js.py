"""Add <script src="/you.js"></script> to every HTML.

Inserts right after vibe.js. Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<script src="/you.js"></script>'
VIBE_RE = re.compile(r'(<script\s+src="/vibe\.js"></script>)', re.IGNORECASE)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = 0
skipped = 0

for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "/you.js" in text:
        skipped += 1
        continue
    if VIBE_RE.search(text):
        text = VIBE_RE.sub(r'\1\n  ' + INCLUDE, text, count=1)
    elif HEAD_END.search(text):
        m = HEAD_END.search(text)
        text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]
    else:
        continue
    path.write_text(text, encoding="utf-8")
    added += 1

print(f"Added you.js to {added} files. Skipped {skipped}.")
