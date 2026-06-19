#!/usr/bin/env python3
"""site_audit.py -- inventory the human-facing site/ surface as a link graph.

The site grew to ~167 HTML pages; most are unreachable from the front door.
This re-runnable tool reads every site/*.html and reports, for each page:
title, byte size, last-modified, OUTBOUND internal links (is it a hub?), and
INBOUND internal links (how many pages point here -- 0 = orphan). It then
clusters pages into families by a keyword map so the sprawl can be reorganized
into a navigable map (keep / merge / retire) instead of a flat dump.

    python tools/site_audit.py            # full report
    python tools/site_audit.py --orphans  # just the unreachable pages

Read-only, stdlib only. Judgment (keep/merge/retire) is a human's; this gives
the ground truth to judge from.
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(HERE, "site")

# Page families -- the connection map. A page is filed in the FIRST family whose
# keyword its name matches; "other" catches the rest (a signal it needs a home).
FAMILIES = [
    ("engine/verify",   ["verif", "gauntlet", "seal", "check", "benchmark", "proof", "attest"]),
    ("the map",         ["atlas", "grid", "brain", "breath", "coordinate", "map", "scaffold"]),
    ("scripture/codex", ["codex", "bible", "scripture", "canon", "concordance", "lexicon",
                         "commentary", "verse", "gospel", "psalm", "apokalypsis", "chronicle"]),
    ("learn/tutor",     ["read", "curriculum", "phonics", "lesson", "learn", "tutor", "trivia",
                         "characters", "archetype"]),
    ("apothecary/heal", ["apothecary", "herb", "remedy", "health", "nutrition"]),
    ("community/serve", ["mission", "assembly", "church", "giving", "connect", "common-book",
                         "household", "steward"]),
    ("write/keep",      ["scribe", "kept", "keep", "daily", "calendar", "card", "curate", "well"]),
    ("media/channels",  ["channel", "stream", "radio", "tv", "watch", "show", "apophenia"]),
    ("dev/agents",      ["mcp", "agents", "api", "developer"]),
    ("about/entry",     ["enter", "about", "identity", "contact", "search", "404", "index",
                         "profile", "manifesto", "story"]),
]

LINK_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', re.I)


def family_of(name):
    low = name.lower()
    for fam, kws in FAMILIES:
        if any(k in low for k in kws):
            return fam
    return "other"


def internal_target(href):
    """Normalize an href to a bare page name if it's an internal .html link, else None."""
    h = href.strip()
    if h.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
        return None
    h = h.split("#", 1)[0].split("?", 1)[0]
    h = h.lstrip("/")
    if not h or not h.endswith(".html"):
        return None
    return os.path.basename(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orphans", action="store_true", help="only list orphaned pages")
    args = ap.parse_args()
    if not os.path.isdir(SITE):
        print("no site/ dir at", SITE); return 1

    pages = sorted(f for f in os.listdir(SITE) if f.endswith(".html"))
    info = {}
    inbound = {p: set() for p in pages}
    outbound = {p: set() for p in pages}
    pageset = set(pages)

    for p in pages:
        path = os.path.join(SITE, p)
        try:
            body = open(path, encoding="utf-8", errors="replace").read()
        except Exception as e:  # noqa: BLE001
            info[p] = {"title": "(unreadable: %s)" % e, "size": 0, "mtime": 0, "desc": ""}
            continue
        tt = TITLE_RE.search(body)
        dd = DESC_RE.search(body)
        info[p] = {
            "title": re.sub(r"\s+", " ", (tt.group(1) if tt else "")).strip()[:70],
            "desc": (dd.group(1) if dd else "").strip()[:90],
            "size": len(body),
            "mtime": os.path.getmtime(path),
        }
        for m in LINK_RE.finditer(body):
            tgt = internal_target(m.group(1))
            if tgt and tgt in pageset:
                outbound[p].add(tgt)
                if tgt != p:
                    inbound[tgt].add(p)

    # cluster
    fams = {}
    for p in pages:
        fams.setdefault(family_of(p), []).append(p)

    now = time.time()
    orphans = [p for p in pages if p != "index.html" and not inbound[p]]

    if args.orphans:
        print("ORPHANED pages (0 inbound internal links) -- %d of %d\n" % (len(orphans), len(pages)))
        for p in sorted(orphans, key=lambda x: -info[x]["size"]):
            print("  %-34s %6d B  %s" % (p, info[p]["size"], info[p]["title"][:50]))
        return 0

    print("SITE AUDIT -- %d pages in site/\n" % len(pages))
    print("By family (reachability: inbound link count):")
    for fam, _ in FAMILIES + [("other", [])]:
        plist = fams.get(fam, [])
        if not plist:
            continue
        orphan_n = sum(1 for p in plist if p != "index.html" and not inbound[p])
        print("\n== %s  (%d pages, %d orphaned) ==" % (fam, len(plist), orphan_n))
        for p in sorted(plist, key=lambda x: -len(inbound[x])):
            age_d = int((now - info[p]["mtime"]) / 86400) if info[p]["mtime"] else -1
            flag = "ORPHAN" if (p != "index.html" and not inbound[p]) else "in=%d" % len(inbound[p])
            hub = " HUB(out=%d)" % len(outbound[p]) if len(outbound[p]) >= 12 else ""
            print("  %-32s %-7s out=%-3d %5dB %3dd  %s%s"
                  % (p, flag, len(outbound[p]), info[p]["size"], age_d, info[p]["title"][:42], hub))

    print("\n--- SUMMARY ---")
    print("total pages:      %d" % len(pages))
    print("orphaned (in=0):  %d  (%.0f%%)" % (len(orphans), 100.0 * len(orphans) / len(pages)))
    hubs = [p for p in pages if len(outbound[p]) >= 12]
    print("hub pages (out>=12): %s" % ", ".join(sorted(hubs, key=lambda x: -len(outbound[x]))[:10]))
    big_orphans = [p for p in orphans if info[p]["size"] > 8000]
    print("large orphans (>8KB, real work with no door): %d" % len(big_orphans))
    return 0


if __name__ == "__main__":
    sys.exit(main())
