#!/usr/bin/env python3
"""SEO backfill — add canonical URL + Open Graph cards to every public
top-level HTML page that's missing them.

Reads existing <title> + meta description and inserts:
  - <link rel="canonical" href="...">
  - og:type, og:site_name, og:title, og:description, og:url, og:image
  - twitter:card, twitter:title, twitter:description, twitter:image

Operator/noindex pages are skipped. Idempotent — re-running is a no-op.

Run from repo root:
    python tools/seo_backfill.py            # dry-run, prints what would change
    python tools/seo_backfill.py --apply    # writes the changes
"""
import argparse
import re
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
ORIGIN   = "https://narrowhighway.com"
OG_IMAGE = f"{ORIGIN}/img/og_card.png"

# Pages that should NEVER be indexed — operator surfaces, error pages,
# engine internals. The noindex meta on these is the authoritative signal;
# this list is belt-and-suspenders so the script never touches them.
SKIP_FILES = {
    "404.html", "offline.html", "health.html", "robots.html",
    "keep.html", "inbox.html", "engine-queue.html", "outreach.html",
    "profile.html", "dashboard.html", "tasks.html", "publish.html",
    "run.html", "install.html", "setup.html", "nfc.html", "handoff.html",
    "mcp.html", "pyodide.html", "training.html",
    "you.html", "share.html", "residue.html", "gaps.html",
    "misalignments.html", "steward.html", "agents.html", "connect.html",
    "reach.html", "shepherd-room.html", "curate.html",
}

TITLE_RE  = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESC_RE   = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"\s*/?\s*>', re.IGNORECASE)
NOINDEX_RE = re.compile(r'<meta\s+name="robots"\s+content="[^"]*noindex', re.IGNORECASE)
CANON_RE  = re.compile(r'<link\s+rel="canonical"', re.IGNORECASE)
OG_RE     = re.compile(r'property="og:', re.IGNORECASE)


def html_escape_attr(s: str) -> str:
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def build_block(filename: str, title: str, desc: str, *, add_canon: bool, add_og: bool) -> str:
    """Build the canonical + OG block to insert."""
    url = f"{ORIGIN}/{filename}"
    t = html_escape_attr(title.strip())
    d = html_escape_attr(desc.strip())
    parts = []
    if add_canon:
        parts.append(f'  <link rel="canonical" href="{url}">')
    if add_og:
        parts.extend([
            f'  <meta property="og:type" content="website">',
            f'  <meta property="og:site_name" content="Narrow Highway">',
            f'  <meta property="og:title" content="{t}">',
            f'  <meta property="og:description" content="{d}">',
            f'  <meta property="og:url" content="{url}">',
            f'  <meta property="og:image" content="{OG_IMAGE}">',
            f'  <meta name="twitter:card" content="summary_large_image">',
            f'  <meta name="twitter:title" content="{t}">',
            f'  <meta name="twitter:description" content="{d}">',
            f'  <meta name="twitter:image" content="{OG_IMAGE}">',
        ])
    return "\n".join(parts)


def process(path: Path, apply: bool) -> tuple[str, int]:
    """Return (status, lines_added)."""
    if path.name in SKIP_FILES:
        return "skip:list", 0
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"skip:read_error:{e}", 0
    if NOINDEX_RE.search(text):
        return "skip:noindex", 0

    m_title = TITLE_RE.search(text)
    m_desc  = DESC_RE.search(text)
    if not m_title:
        return "skip:no_title", 0
    title = re.sub(r"\s+", " ", m_title.group(1)).strip()
    desc  = m_desc.group(1).strip() if m_desc else title

    has_canon = bool(CANON_RE.search(text))
    has_og    = bool(OG_RE.search(text))
    add_canon = not has_canon
    add_og    = not has_og
    if not add_canon and not add_og:
        return "ok:already_covered", 0

    block = build_block(path.name, title, desc, add_canon=add_canon, add_og=add_og)

    # Insert after the description meta if we have one; else after <title>.
    anchor = m_desc.group(0) if m_desc else m_title.group(0)
    if anchor not in text:
        return "skip:anchor_not_found", 0
    new_text = text.replace(anchor, anchor + "\n" + block, 1)
    if new_text == text:
        return "skip:replace_noop", 0

    added = block.count("\n") + 1
    if apply:
        path.write_text(new_text, encoding="utf-8")
    label = []
    if add_canon: label.append("canon")
    if add_og:    label.append("og")
    return "fix:" + "+".join(label), added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = ap.parse_args()

    files = sorted(SITE_DIR.glob("*.html"))
    by_status: dict[str, int] = {}
    fixed: list[tuple[str, str, int]] = []
    for f in files:
        status, added = process(f, args.apply)
        by_status[status] = by_status.get(status, 0) + 1
        if status.startswith("fix:"):
            fixed.append((f.name, status, added))

    print(f"\n{'APPLIED' if args.apply else 'DRY-RUN'} — site/*.html ({len(files)} files)\n")
    print("Status summary:")
    for k, v in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}  {k}")
    if fixed:
        print(f"\nFixed ({len(fixed)} pages):")
        for name, st, n in fixed:
            print(f"  {name:36s}  {st:18s}  +{n} lines")
    if not args.apply:
        print("\nRun again with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
