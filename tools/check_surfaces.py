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
    ("/breath.html",     "Breath"),   # the map drawn by evidence (verified vs resonance)
    ("/breath-graph.json", None),     # the evidence-labelled runtime data -- checked as JSON below
    ("/enter.html",   "door"),        # the cinematic pitch
    ("/curriculum",   None),          # the lessons API -- checked as JSON below
    ("/identity",     "Jesus Christ"),# who this serves
    # ── crawlable record + proofs (the discovery moat) + the Acts-2 community ──
    ("/almanac/book",    "Almanac"),  # the whole tested record, server-rendered
    ("/curriculum/book", "Phonics"),  # the whole free curriculum, server-rendered
    ("/verified",        None),       # JSON: proven claims index -- checked below
    ("/grid/scaffold",   None),       # JSON: the dimensional grid -- checked below
    ("/grid/spectrum",   None),       # JSON: the map's Fourier/spectral modes -- checked below
    ("/missions",        None),       # JSON: the Acts-2 missions -- checked below
]


def fetch(url, timeout=15, accept=None):
    headers = {"User-Agent": "nh-surface-check/1.0"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
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
            elif path in ("/brain-graph.json", "/breath-graph.json"):
                d = json.loads(body)
                n = len(d.get("x", []))  # parallel-array node count
                if n <= 0:
                    note = "no graph nodes"
                elif path == "/breath-graph.json":
                    ev = (d.get("meta") or {}).get("node_evidence") or {}
                    status, note = "UP", "%d nodes (%d verified)" % (n, ev.get("verified", 0))
                else:
                    status, note = "UP", "%d nodes" % n
            elif path == "/verified":
                d = json.loads(body)
                n = d.get("proven_total") or 0
                if n <= 0:
                    note = "no proven claims"
                else:
                    status, note = "UP", "%d proven claims" % n
            elif path == "/grid/scaffold":
                d = json.loads(body)
                n = d.get("dimension_count") or len(d.get("dimensions", []))
                if n < 7:
                    note = "grid under 7 dims"
                else:
                    status, note = "UP", "%d dimensions" % n
            elif path == "/grid/spectrum":
                d = json.loads(body)
                modes = d.get("modes", [])
                ax = d.get("effective_axes", 0)
                if not modes or ax < 1:
                    note = "no spectral modes"
                else:
                    status, note = "UP", "%d modes, %d axes" % (len(modes), ax)
            elif path == "/missions":
                d = json.loads(body)
                n = d.get("count", 0)
                if n < 1:
                    note = "no missions"
                else:
                    status, note = "UP", "%d missions" % n
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

    # The seal proof moat: derive a real cite_url from /verified and confirm the
    # proof SERVER-RENDERS crawlable HTML (not a JS shell or a redirect). A seal
    # is a capability-URL, so we discover one through the verified index.
    try:
        _, vbody = fetch(base.rstrip("/") + "/verified")
        items = (json.loads(vbody) or {}).get("items") or []
        cite = (items[0].get("cite_url") if items else "") or ""
        if not cite:
            rows.append(("/seal/{hash}", "ERR", "no cite_url in /verified")); ok_all = False
        else:
            if cite.startswith("http"):
                surl = cite
            elif cite.startswith("/"):
                surl = base.rstrip("/") + cite
            else:
                surl = base.rstrip("/") + "/seal/" + cite
            scode, sbody = fetch(surl, accept="text/html")
            if scode == 200 and "without trusting us" in sbody.lower():
                rows.append(("/seal/{hash}", "UP", "proof SSR (%d bytes)" % len(sbody)))
            else:
                rows.append(("/seal/{hash}", "ERR", "seal not server-rendered")); ok_all = False
    except Exception as e:  # noqa: BLE001
        rows.append(("/seal/{hash}", "ERR", type(e).__name__ + ": " + str(e)[:50])); ok_all = False

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
