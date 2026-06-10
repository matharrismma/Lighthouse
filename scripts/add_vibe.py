"""Add vibe.css + vibe.js to every HTML file.

Inserts vibe.css after lens-polish.css and vibe.js after audio.js.
Idempotent.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

CSS_TAG = '<link rel="stylesheet" href="/vibe.css">'
JS_TAG  = '<script src="/vibe.js"></script>'

LENS_RE  = re.compile(r'(<link\s+rel="stylesheet"\s+href="/lens-polish\.css"\s*/?>)', re.IGNORECASE)
AUDIO_RE = re.compile(r'(<script\s+src="/audio\.js"></script>)', re.IGNORECASE)
HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)

added_css = 0
added_js  = 0
skipped   = 0

for path in SITE.rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="replace")
    has_css = "/vibe.css" in text
    has_js  = "/vibe.js"  in text
    if has_css and has_js:
        skipped += 1
        continue

    if not has_css:
        if LENS_RE.search(text):
            text = LENS_RE.sub(r'\1\n  ' + CSS_TAG, text, count=1)
        elif HEAD_END.search(text):
            m = HEAD_END.search(text)
            text = text[: m.start()] + f"  {CSS_TAG}\n" + text[m.start():]
        else:
            continue
        added_css += 1

    if not has_js:
        if AUDIO_RE.search(text):
            text = AUDIO_RE.sub(r'\1\n  ' + JS_TAG, text, count=1)
        elif HEAD_END.search(text):
            m = HEAD_END.search(text)
            text = text[: m.start()] + f"  {JS_TAG}\n" + text[m.start():]
        else:
            continue
        added_js += 1

    path.write_text(text, encoding="utf-8")

print(f"Added vibe.css to {added_css} files, vibe.js to {added_js} files. Skipped {skipped}.")
