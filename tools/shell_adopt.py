#!/usr/bin/env python3
"""Cohesion sweep — adopt nh-shell across the high-value user-facing pages.

Two patterns existed before nh-shell:
  Pattern A: <header class="topbar"> ... </header> with "Concordance Engine"
             or "Narrow Highway" brand and a hand-rolled nav. Needs REMOVAL
             before the shell can be added (otherwise double headers).
  Pattern B: no explicit top nav. Safe to add the shell directly.

The shell injects its own header + footer at runtime, so the page only needs:
  <link rel="stylesheet" href="/nh-shell.css">
  <script defer src="/nh-shell.js"></script>
inside <head>. We insert them right after the existing canonical link or
the description meta — same anchor seo_backfill.py uses, for consistency.

Idempotent: re-running is a no-op.

Run from repo root:
    python tools/shell_adopt.py            # dry-run
    python tools/shell_adopt.py --apply    # write
"""
import argparse
import re
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

# Pages we explicitly DO NOT touch:
#   - operator surfaces (noindex)
#   - SPAs that intentionally have their own chrome (bible-trivia, games,
#     pyodide — full-experience pages)
#   - tool child pages under /tools/ (single-purpose focused surfaces)
#   - error / PWA / robots
SKIP = {
    # Operator / noindex
    "404.html", "offline.html", "health.html", "robots.html",
    "keep.html", "inbox.html", "engine-queue.html", "outreach.html",
    "profile.html", "dashboard.html", "tasks.html", "publish.html",
    "run.html", "install.html", "setup.html", "nfc.html", "handoff.html",
    "mcp.html", "pyodide.html", "training.html",
    "you.html", "share.html", "residue.html", "gaps.html",
    "misalignments.html", "steward.html", "agents.html", "connect.html",
    "reach.html", "shepherd-room.html", "curate.html",
    "listen.html",  # noindex per audit
    "witness.html", # noindex per audit
    # Full-experience UIs that would clash visually with the shell
    "bible-trivia.html", "games.html",
    # SPA templates with no real page
    "card.html", "unit.html",
    # Operator dashboards
    "roadmap.html",
}

SHELL_LINK   = '<link rel="stylesheet" href="/nh-shell.css">'
SHELL_SCRIPT = '<script defer src="/nh-shell.js"></script>'

HAS_SHELL_RE   = re.compile(r'nh-shell\.js', re.IGNORECASE)
CANON_RE       = re.compile(r'<link\s+rel="canonical"[^>]*>', re.IGNORECASE)
DESC_RE        = re.compile(r'<meta\s+name="description"[^>]*>', re.IGNORECASE)
TITLE_END_RE   = re.compile(r'</title>', re.IGNORECASE)
HEAD_END_RE    = re.compile(r'</head>', re.IGNORECASE)

# Old chrome to remove. The block is <header class="topbar"> ... </header>.
# Some pages have a <nav class="topnav"> sibling — that's part of the same
# pattern we strip. The shell replaces both.
TOPBAR_RE = re.compile(r'<header\s+class="topbar"[^>]*>.*?</header>', re.DOTALL | re.IGNORECASE)
# A standalone <nav class="topnav"> NOT inside a <header> — older pattern
# (games.html style). Match a complete element greedily by name only.
STANDALONE_TOPNAV_RE = re.compile(r'<nav\s+class="topnav"[^>]*>.*?</nav>', re.DOTALL | re.IGNORECASE)


def find_insert_anchor(text: str) -> tuple[int, str]:
    """Return (insert_position, anchor_label) inside <head>. Prefer canonical,
    then description, then </title>, then </head>."""
    for re_, name in [(CANON_RE, "after canonical"), (DESC_RE, "after description"),
                       (TITLE_END_RE, "after title"), (HEAD_END_RE, "before </head>")]:
        m = re_.search(text)
        if m:
            return (m.end(), name)
    return (-1, "no anchor")


def process(path: Path, apply: bool) -> tuple[str, dict]:
    name = path.name
    if name in SKIP:
        return "skip:list", {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"skip:read_error:{e}", {}
    if HAS_SHELL_RE.search(text):
        return "ok:already_has_shell", {}

    details = {}
    # Remove the old chrome if present
    new_text = text
    new_text, n_topbar = TOPBAR_RE.subn("", new_text)
    if n_topbar:
        details["topbar_removed"] = n_topbar
    # Only strip standalone topnav if NO header.topbar was found (otherwise
    # the topnav was usually nested inside it and already gone).
    if n_topbar == 0:
        new_text, n_topnav = STANDALONE_TOPNAV_RE.subn("", new_text)
        if n_topnav:
            details["topnav_removed"] = n_topnav

    # Inject the shell tags
    pos, where = find_insert_anchor(new_text)
    if pos < 0:
        return "skip:no_head_anchor", details
    insertion = "\n  " + SHELL_LINK + "\n  " + SHELL_SCRIPT
    new_text = new_text[:pos] + insertion + new_text[pos:]
    details["inserted"] = where

    if new_text == text:
        return "skip:no_change", details
    if apply:
        path.write_text(new_text, encoding="utf-8")
    return "fix:adopted", details


# Tier 1 priority list — the pages a Christian-mother-on-Tuesday would visit.
# These get adopted first. Others are tackled in a future pass.
TIER_1 = [
    "apothecary.html", "recipes.html", "bibles.html", "almanac.html",
    "hearth.html", "prayer.html", "maker.html", "calendar.html",
    "letters.html", "common-book.html", "encyclopedia.html", "places.html",
    "watch.html", "live.html", "schedule.html", "podcast.html",
    "podcast-theatre.html", "church-streams.html",
    "reading.html", "reading-room.html", "library.html",
    "household.html", "works.html", "learn.html", "curriculum.html",
    "canon.html", "codex.html", "paths.html",
    "contact.html", "try.html", "search.html",
    "wallet-help.html", "wallet-transparency.html",
    "apokalypsis.html", "molasses.html", "dade.html",
    "fieldkit.html", "characters.html", "archetypes.html",
    "atlas.html", "chronicle.html", "places.html",
    "submit-curriculum.html", "submit-recipe.html",
    # Engine-internal but useful surfaces
    "poly.html", "packets.html", "seeds.html", "receipts.html",
    "shelves.html", "stack.html", "theory.html", "parable.html",
    "walk.html",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="Process every site/*.html, not just TIER_1")
    args = ap.parse_args()

    if args.all:
        targets = sorted({p.name for p in SITE_DIR.glob("*.html")})
    else:
        targets = TIER_1

    by_status: dict[str, int] = {}
    fixed: list[tuple[str, dict]] = []
    print(f"\n{'APPLYING' if args.apply else 'DRY-RUN'} — {len(targets)} pages\n")
    for name in targets:
        p = SITE_DIR / name
        if not p.exists():
            print(f"  missing: {name}")
            continue
        status, details = process(p, args.apply)
        by_status[status] = by_status.get(status, 0) + 1
        if status.startswith("fix:"):
            fixed.append((name, details))
        # Print details for fixed + skipped-noteworthy
        if status.startswith("fix:") or "topbar" in details:
            extra = " " + str(details) if details else ""
            print(f"  {name:32s}  {status}{extra}")

    print("\nStatus summary:")
    for k, v in sorted(by_status.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}  {k}")
    print(f"\nFixed: {len(fixed)} pages")
    if not args.apply:
        print("\nRun again with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
