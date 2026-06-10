"""Add <script src="/a11y.js"></script> to every HTML file in site/.

Inserts right after the i18n.js include if present, else before </head>.
Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

INCLUDE = '<script src="/a11y.js"></script>'
I18N_INCLUDE_RE = re.compile(r'(<script\s+src="/i18n\.js"></script>)', re.IGNORECASE)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added = 0
skipped = 0
errored = []

for path in SITE.rglob("*.html"):
    rel = path.relative_to(SITE)
    text = path.read_text(encoding="utf-8", errors="replace")

    if "/a11y.js" in text:
        skipped += 1
        continue

    # Try to insert right after the i18n.js include
    if I18N_INCLUDE_RE.search(text):
        new_text = I18N_INCLUDE_RE.sub(r'\1\n  ' + INCLUDE, text, count=1)
    else:
        # Fall back to before </head>
        m = HEAD_END.search(text)
        if not m:
            errored.append((str(rel), "no </head> or i18n.js"))
            continue
        new_text = text[: m.start()] + f"  {INCLUDE}\n" + text[m.start():]

    path.write_text(new_text, encoding="utf-8")
    added += 1

print(f"Added a11y.js to {added} files. Skipped {skipped}.")
if errored:
    print(f"Errored: {errored}")
