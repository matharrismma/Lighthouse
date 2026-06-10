"""Add <script src="/i18n.js"></script> to every HTML file in site/.

Idempotent — skips files that already have the include. Inserts the
script tag right before </head> for maximum compatibility.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<script src="/i18n.js"></script>'
# Match the </head> closing tag exactly (case-insensitive, any whitespace)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = []
skipped = []
errored = []

# Walk all .html files (including subdirs like use-cases/)
for path in SITE.rglob("*.html"):
    rel = path.relative_to(SITE)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        errored.append((str(rel), f"read: {e}"))
        continue

    # Already has the include?
    if "/i18n.js" in text:
        skipped.append(str(rel))
        continue

    # Find </head> and insert before it
    m = HEAD_END.search(text)
    if not m:
        errored.append((str(rel), "no </head> found"))
        continue

    new_text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]

    try:
        path.write_text(new_text, encoding="utf-8")
        added.append(str(rel))
    except OSError as e:
        errored.append((str(rel), f"write: {e}"))

print(f"Added i18n.js include to {len(added)} files")
for f in added:
    print(f"  + {f}")
print(f"\nSkipped (already had it): {len(skipped)}")
for f in skipped:
    print(f"  = {f}")
if errored:
    print(f"\nErrored: {len(errored)}")
    for f, err in errored:
        print(f"  ! {f}: {err}")
