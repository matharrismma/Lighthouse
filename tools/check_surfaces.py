#!/usr/bin/env python3
"""Surface health check -- are the public doors actually open?

A standing, re-runnable guard for the serve-the-least surfaces. GETs each public
page and the curriculum API, checks for 200 plus a content fingerprint so a blank
or error page is caught too (200-but-wrong is still down). Read-only; stdlib only.

    python tools/check_surfaces.py [--base https://narrowhighway.com]

Exits 0 if every surface is up, 1 otherwise -- so it can gate a deploy or a cron.
"""
import argparse
import json
import sys
import urllib.request

# (path, must_contain) -- the fingerprint proves the right page came back, not just any 200.
SURFACES = [
    ("/",             "work area"),   # the front door
    ("/read.html",    "tutor"),       # the lifelong tutor
    ("/kept.html",    "kept"),        # the file-system-for-life shelf
    ("/brain.html",      "brain"),    # the engine as a digital brain
    ("/brain-graph.json", None),      # the brain's runtime data -- checked as JSON below
    ("/enter.html",   "door"),        # the cinematic pitch
    ("/curriculum",   None),          # the lessons API -- checked as JSON below
    ("/identity",     "Jesus Christ"),# who this serves
]


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "nh-surface-check/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def check(base):
    rows = []
    ok_all = True
    for path, needle in SURFACES:
        url = base.rstrip("/") + path
        status, note = "ERR", ""
        try:
            code, body = fetch(url)
            if code != 200:
                note = "bad status"
            elif path == "/curriculum":
                d = json.loads(body)
                # shape: {tracks:{phonics:[...]}, totals, total_units}
                tracks = d.get("tracks", d)
                n = d.get("total_units") or sum(
                    len(v) for v in tracks.values() if isinstance(v, list)
                )
                if not n or n <= 0:
                    note = "no curriculum units"
                else:
                    status, note = "UP", "%d units" % n
            elif path == "/brain-graph.json":
                d = json.loads(body)
                n = len(d.get("x", []))  # parallel-array node count
                if n <= 0:
                    note = "no graph nodes"
                else:
                    status, note = "UP", "%d nodes" % n
            elif needle and needle.lower() not in body.lower():
                note = "missing %r" % needle
            else:
                status, note = "UP", "%d bytes" % len(body)
            if code == 200 and not note.startswith(("bad", "missing", "no ")):
                status = "UP"
        except Exception as e:  # noqa: BLE001 -- report any failure as down
            note = type(e).__name__ + ": " + str(e)[:60]
        if status != "UP":
            ok_all = False
        rows.append((path, status, note))
    return rows, ok_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://narrowhighway.com")
    args = ap.parse_args()
    rows, ok_all = check(args.base)
    print("surface          status  note")
    print("-" * 48)
    for path, status, note in rows:
        print("%-16s %-7s %s" % (path, status, note))
    print("-" * 48)
    print("ALL UP" if ok_all else "SOME SURFACES DOWN")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
