#!/usr/bin/env python3
# surface_map.py -- every SURFACE (page/tool/content) gets a map/visual location.
#
# Matt 2026-06-13: "EVERYTHING must have a map/visual location" + "use and map the
# use of .org and .tv to move periphery tools and content." The coordinate map
# places the CARDS; this places the SURFACES -- the 151 site pages -- by domain
# (.com core / .org authority+registry / .tv gift+family) and category, so nothing
# lacks a location, and the periphery->routing is mapped. The classification is a
# PLAN; the actual DNS/deploy moves are operator-gated. Elegant: simple, durable,
# a clean sectioned visual (no fragile positioning).
#
#   python tools/surface_map.py
# Writes data/codex/surface_map.json + site/surface-map.html.
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOUT = os.path.join(ROOT, "data/codex/surface_map.json")
HOUT = os.path.join(ROOT, "site/surface-map.html")

pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "site", "*.html")))

# DOMAIN: .tv (gift/family content) | .org (authority/registry/community) | .com (core app/engine)
TV = ["channel", "door-tv", "stream", "watch", "listen", "fast", "cartoon", "story",
      "hymn", "music", "video", "pilot", "pooh", "serial", "apokalypsis", "koa",
      "molasses", "art", "game", "trivia", "play", "sing", "kids", "recipe", "hearth"]
ORG = ["assembly", "registry", "witness", "take-part", "submit", "common-book",
       "member", "covenant", "elder", "connect", "community", "marketplace", "chronicle"]
# CATEGORY (grouping within a domain)
CATS = [("codex", ["codex"]), ("maps", ["map", "coordinate", "roadmap", "atlas-map"]),
        ("atlas", ["atlas"]), ("almanac", ["almanac"]),
        ("proof", ["proof", "seal", "verif", "benchmark", "ten-second", "wedge"]),
        ("scripture", ["scripture", "bible", "canon", "gate", "word", "shema", "trivia"]),
        ("agent", ["mcp", "agent", "llms", "api", "capab", "identity"]),
        ("cards", ["card", "well", "stack", "daily"]),
        ("explain", ["about", "guide", "start", "two-tree", "concord", "index", "home"]),
        ("channels", ["channel", "door-tv", "stream", "watch", "listen", "fast"]),
        ("media", ["cartoon", "story", "hymn", "music", "video", "pilot", "pooh",
                   "serial", "apokalypsis", "koa", "molasses", "art"]),
        ("kids", ["kids", "play", "game", "sing"]),
        ("practical", ["recipe", "hearth", "apothec", "maker", "herb", "calendar"]),
        ("community", ["assembly", "registry", "witness", "take-part", "submit",
                       "common-book", "member", "covenant", "elder", "connect",
                       "community", "marketplace", "church", "chronicle"])]

def domain(name):
    n = name.lower()
    if any(k in n for k in TV):
        return ".tv"
    if any(k in n for k in ORG):
        return ".org"
    return ".com"

def category(name):
    n = name.lower()
    for label, kws in CATS:
        if any(k in n for k in kws):
            return label
    return "other"

surfaces = []
for p in pages:
    surfaces.append({"page": p, "domain": domain(p), "category": category(p)})

by_dom = {}
for s in surfaces:
    by_dom.setdefault(s["domain"], {}).setdefault(s["category"], []).append(s["page"])

counts = {d: sum(len(v) for v in cats.values()) for d, cats in by_dom.items()}
json.dump({"meta": {"purpose": "every surface gets a map/visual location; periphery->.org/.tv routing PLAN (moves are operator-gated)",
                    "domains": {".com": "core app/engine", ".org": "authority/registry/community", ".tv": "gift/family content"}},
           "counts": counts, "total": len(surfaces), "surfaces": surfaces},
          open(JOUT, "w", encoding="utf-8"), indent=1)

DOM_COL = {".com": "#6f9bff", ".org": "#3fb98a", ".tv": "#e7c46b"}
DOM_NOTE = {".com": "core -- the Concordance (engine, proofs, maps, scripture, agents)",
            ".org": "authority / registry / community",
            ".tv": "gift / family -- curated, free content"}
cols = []
for dom in [".com", ".org", ".tv"]:
    cats = by_dom.get(dom, {})
    n = counts.get(dom, 0)
    blocks = []
    for cat in sorted(cats):
        chips = "".join('<a class="chip" href="%s">%s</a>' % (pg, pg.replace(".html", "")) for pg in sorted(cats[cat]))
        blocks.append('<div class="cat"><h3>%s <span>(%d)</span></h3>%s</div>' % (cat, len(cats[cat]), chips))
    cols.append('<section class="col"><div class="dom" style="border-color:%s"><b style="color:%s">%s</b> <span>%d</span><p>%s</p></div>%s</section>'
                % (DOM_COL[dom], DOM_COL[dom], dom, n, DOM_NOTE[dom], "".join(blocks)))

html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The surface map -- every page placed (.com / .org / .tv)</title>
<style>
:root{--bg:#0a0b0e;--tx:#e9eaee;--mut:#9aa0ad;--card:#14161c;--line:#262a32}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5}
.wrap{max-width:1100px;margin:0 auto;padding:1.5rem 1rem 3rem}
h1{font-size:1.3rem;margin:0}.lede{color:var(--mut);font-size:.95rem;margin:.5rem 0 1.3rem;line-height:1.55}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;align-items:start}
.dom{border-left:3px solid;padding:.2rem 0 .2rem .7rem;margin-bottom:.8rem}
.dom b{font-size:1.1rem}.dom span{color:var(--mut)}.dom p{color:var(--mut);font-size:.82rem;margin:.2rem 0 0}
.cat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.6rem .7rem;margin-bottom:.6rem}
.cat h3{font-size:.85rem;font-weight:600;margin:0 0 .4rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.cat h3 span{color:#555}
.chip{display:inline-block;font-size:.78rem;color:#cdd2db;text-decoration:none;background:#1c1f26;border:1px solid var(--line);border-radius:6px;padding:2px 7px;margin:2px}
.chip:hover{background:#262a32}
.foot{color:var(--mut);font-size:.88rem;margin-top:1.4rem;border-top:1px solid var(--line);padding-top:1rem;line-height:1.55}
a.lk{color:#9db4ff;text-decoration:none}
</style></head><body><main class="wrap">
<h1>The surface map &mdash; every page placed</h1>
<p class="lede">Every surface of the project given a location, by domain &mdash; <b style="color:#6f9bff">.com</b> the core (the Concordance: engine, proofs, maps, scripture, agents), <b style="color:#3fb98a">.org</b> authority / registry / community, <b style="color:#e7c46b">.tv</b> the gift &mdash; curated, free family content. The periphery routes outward so the core stays lean. This is the <b>routing plan</b>; the actual DNS/deploy moves are the operator's to make. Companion to the <a class="lk" href="coordinate-map.html">coordinate map</a> (which places the findings). Nothing is discarded &mdash; everything has a place, because it is all in reality.</p>
<div class="cols">''' + "".join(cols) + '''</div>
<p class="foot">''' + str(len(surfaces)) + ''' surfaces placed (''' + " &middot; ".join("%s %d" % (d, counts.get(d, 0)) for d in [".com", ".org", ".tv"]) + '''). Re-run <code>python tools/surface_map.py</code>. Data: <code>data/codex/surface_map.json</code>. Classification is heuristic &mdash; refine as the project settles. "A place for everything because it is all in reality."</p>
</main></body></html>'''

open(HOUT, "w", encoding="utf-8").write(html)
print("surfaces %d | .com %d / .org %d / .tv %d" % (len(surfaces), counts.get(".com", 0), counts.get(".org", 0), counts.get(".tv", 0)))
print("wrote", os.path.relpath(JOUT, ROOT), "+", os.path.relpath(HOUT, ROOT))
