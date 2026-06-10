"""Inject the Shepherd chip script tag into every HTML page on the site.

The Shepherd is the OS conversational layer. Per
project_shepherd_os_proselytize_on_ask_2026-05-17.md it must be present on EVERY
page so the user can summon it from anywhere.

Strategy: append <script defer src="/nh-shepherd.js"></script> just before
</body> in each HTML file. Skip if already present. Skip legacy files. Skip
HTML that doesn't look like a full document (no <body>).
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
TAG = '<script defer src="/nh-shepherd.js"></script>'

# Files we leave alone — internal/handoff/legacy
SKIP = {"inbox_legacy.html", "index_legacy.html", "radio_legacy.html",
        "handoff.html", "agents.html", "engine.html", "health.html",
        "robots.html", "sitemap.xml"}


def find_html_files():
    out = []
    for path in SITE.rglob("*.html"):
        if path.name in SKIP:
            continue
        out.append(path)
    return out


def inject_one(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if 'nh-shepherd.js' in text:
        return "skip-existing"
    if '</body>' not in text:
        return "skip-no-body"
    new = text.replace('</body>', f'  {TAG}\n</body>', 1)
    path.write_text(new, encoding="utf-8")
    return "injected"


def main():
    counts = {"injected": 0, "skip-existing": 0, "skip-no-body": 0}
    files = find_html_files()
    for f in files:
        r = inject_one(f)
        counts[r] = counts.get(r, 0) + 1
        if r == "injected":
            print(f"  + {f.relative_to(SITE)}")
    print()
    print(f"Files processed: {len(files)}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
