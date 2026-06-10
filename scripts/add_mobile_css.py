"""Add <link rel="stylesheet" href="/mobile.css"> to every HTML file.

Inserts right before </head>. Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<link rel="stylesheet" href="/mobile.css">'
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = 0
skipped = 0

for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "/mobile.css" in text:
        skipped += 1
        continue
    m = HEAD_END.search(text)
    if not m:
        continue
    new_text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]
    path.write_text(new_text, encoding="utf-8")
    added += 1

print(f"Added mobile.css to {added} files. Skipped {skipped}.")
