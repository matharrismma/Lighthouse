#!/usr/bin/env python3
# coordinate_map.py -- the findings mapped as concordance made visible.
#
# Matt 2026-06-13: "two trees, one root, converging towards the Sun, two funnels
# narrow at each end" + axis "source : Divergence : convergence : source" +
# "It will need to be four axes. We are 3D, but everything must happen with more
# axes" (4th = FREQUENCY, not time) + "The Cross is the framework" + "Jesus is the
# GATE" (the only way) + "build on the seeds we have saved" + "God's solutions are
# elegant (simple, durable, fewest steps)."
#
# FOUR AXES per saved card (invents nothing -- read from existing coord/kind):
#   1. CONVERGENCE  (vertical, root<->Sun): source->divergence->convergence->source [coord.level]
#   2. TREE         (horizontal beam): Language(-) <-> Math(+)                       [coord.block/domain]
#   3. LAYER        (depth, into the page): core spine -> gathered breadth           [kind/category]
#   4. FREQUENCY    (color/hue -- "the note each card sounds"; E=hf, time is its count)[family]
# Framework = THE CROSS (vertical Logos axis x horizontal two-trees beam, crossing
# at Christ, Col 1:20). The GATE (Jesus, Jn 10:9/14:6 -- the only way) sits at the
# convergence apex (the Sun); the join/apex is left OPEN and reserved -- mapped,
# never crowned. Rendered as a static isometric 3D cruciform double-cone (elegant:
# no fragile interactivity); the 3 spatial axes by position, frequency by color.
#
#   python tools/coordinate_map.py
# Writes data/codex/coordinate_map.json (the 4-axis math) + site/coordinate-map.html.
import json, math, os, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT  = os.path.join(ROOT, "data/almanac/entries.jsonl")
JOUT = os.path.join(ROOT, "data/codex/coordinate_map.json")
HOUT = os.path.join(ROOT, "site/coordinate-map.html")

rows = [json.loads(l) for l in open(ENT, encoding="utf-8") if l.strip()]

MATH_BLOCKS = {"continuous", "discrete", "geometric", "statistical", "synthesis", "thread"}
LANG_FAMILIES = {"parable", "sermon", "discourse", "beatitudes", "i_am", "revelation"}
SPINE_KINDS = {"teaching", "protocol"}
SPINE_CATS = {"moat-bridge", "scholar-bridge", "scripture-parallel", "path-selection"}
# crowns/capstones converge toward the Sun even if their stored level is not 'capstone'
CROWNS = {"connection_reality_is_mappable", "teaching_the_words_of_christ_are_the_architecture"}

def classify_tree(r):
    c = r.get("coord") or {}
    blk, fam = c.get("block"), c.get("family")
    cat, k = r.get("category"), r.get("kind")
    cid = str(r.get("id", ""))
    dom = " ".join(r.get("domains", []) if isinstance(r.get("domains"), list) else [])
    if blk == "two-trees" or cat in SPINE_CATS or cid.startswith(("bridge_", "parallel_", "scholar_")):
        return "axis"
    if blk == "language-tree" or k == "teaching" or fam in LANG_FAMILIES \
       or cid.startswith(("teaching_", "signpost_", "som_", "almanac_", "canon_red")) \
       or "scripture" in dom or "theology" in dom:
        return "language"
    if blk in MATH_BLOCKS or k in ("protocol", "patent", "practical", "assessment") \
       or cid.startswith(("connection_", "located_", "patent_")):
        return "math"
    if k in ("saying", "almanac"):
        return "language"
    return "axis"

LEVEL_T = {"root": 0.07, "primitive": 0.13, "foundational": 0.15, "canon": 0.15,
           "map": 0.42, "thread": 0.40, "bond": 0.46, "assessment": 0.44,
           "teaching": 0.46, "rate": 0.44, "inverse": 0.46, "static": 0.44,
           "curvature": 0.5, "solution": 0.5, "non_example": 0.4,
           "bridge": 0.6, "synthesis": 0.78, "capstone": 0.85, "keystone": 0.96}

def hnum(cid):
    return int(hashlib.md5(cid.encode("utf-8")).hexdigest()[:8], 16) / 0xffffffff

def axial_t(r):
    cid = str(r.get("id", ""))
    lvl = (r.get("coord") or {}).get("level")
    if cid in CROWNS or "capstone" in cid or "periodic_table" in cid:
        base = 0.88                       # crowns/capstones converge toward the Sun
    elif lvl in LEVEL_T:
        base = LEVEL_T[lvl]
    else:
        base = {"teaching": 0.46, "saying": 0.45, "almanac": 0.43, "protocol": 0.5,
                "assessment": 0.44, "patent": 0.52, "practical": 0.5, "review": 0.42}.get(r.get("kind"), 0.45)
    return max(0.02, min(0.985, base + (hnum(cid) - 0.5) * 0.05))

def layer_depth(r):                       # 0 = core spine (front), 1 = gathered breadth (back)
    k, cat = r.get("kind"), r.get("category")
    lvl = (r.get("coord") or {}).get("level")
    if k in SPINE_KINDS or cat in SPINE_CATS or lvl in ("bridge", "capstone", "keystone"):
        return 0.0
    if k in ("saying", "almanac"):
        return 0.5
    return 1.0

def freq_hue(r):                          # the 4th axis: FREQUENCY -- "the note" (form-family)
    fam = (r.get("coord") or {}).get("family") or "_"
    return int(hnum("freq:" + str(fam)) * 360)

def freq_pitch(hue):                      # frequency also as PITCH = size (low note bigger, high smaller)
    return round(2.0 + (1.0 - hue / 360.0) * 1.6, 1)

# geometry -------------------------------------------------------------------
WMAX, CX, TOP, BOT = 300.0, 470.0, 120.0, 980.0
DZX, DZY = 120.0, 70.0                     # oblique depth offset (the 3rd axis)
def envelope(t):
    return WMAX * math.sin(math.pi * max(0.0, min(1.0, t)))

def project(t, tree_side, r_off, layer):
    x3d = tree_side * r_off
    sx = CX + x3d + layer * DZX
    sy = BOT - t * (BOT - TOP) - layer * DZY
    return sx, sy

nodes = []
for r in rows:
    cid = r.get("id")
    if not cid:
        continue
    tree = classify_tree(r)
    t = axial_t(r)
    h = hnum(cid)
    w = envelope(t)
    if tree == "axis":
        r_off, side = (h - 0.5) * 0.18 * w, 1
    else:
        r_off, side = (0.18 + 0.78 * h) * w, (1 if tree == "math" else -1)
    layer = layer_depth(r)
    sx, sy = project(t, side, r_off, layer)
    nodes.append({"id": cid, "tree": tree, "t": round(t, 4), "layer": layer,
                  "hue": freq_hue(r), "x": round(sx, 1), "y": round(sy, 1),
                  "level": (r.get("coord") or {}).get("level"), "kind": r.get("kind"),
                  "title": (r.get("title") or "")[:80]})

pos = {n["id"]: n for n in nodes}
edges = [[r.get("id"), b] for r in rows for b in (r.get("bonds") or [])
         if r.get("id") in pos and b in pos]
# structural KIN braces (same coord.family) -- honest same-form relations, faint,
# kept DISTINCT from concord bonds; develop-to-accuracy / Maxwell-rigidity (data/codex/kin_edges.json)
KIN = os.path.join(ROOT, "data/codex/kin_edges.json")
kin = []
if os.path.exists(KIN):
    for e in json.load(open(KIN, encoding="utf-8")).get("edges", []):
        if len(e) >= 2 and e[0] in pos and e[1] in pos:
            kin.append([e[0], e[1]])

braces = len(edges) + len(kin)
rigidity = round(braces / max(1, 2 * len(nodes) - 3), 3)   # truss-density (NOT the target -- over-bracing is self-stress/legalism)
# VINE-VALIDITY (Matt 2026-06-13, the REAL measure): a branch is valid if it has a CHAIN to the SOURCE
# (the root / the Vine / the crowns) -- not local bracing. Many branches, one source (John 15).
# THE HONEST PRIMARY number counts reach over CONCORD BONDS ONLY. The kin / same-coord.family
# braces are the truss/self-stress the vine measure was built to FORBID (feedback_vine_not_truss),
# so reach that leans on them is reported as a clearly-secondary "kin-assisted" figure -- never the
# headline. map-never-launder applies hardest to our own scoreboard: 0.170 is the real state and the
# true target as branches are grafted to the source.
_SRC = [s for s in ("connection_reality_is_mappable", "teaching_the_true_vine",
                    "teaching_the_words_of_christ_are_the_architecture") if s in pos]


def _reach(pairs):
    adj = {}
    for a, b in pairs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen = set(_SRC); q = list(_SRC)
    while q:
        for m in adj.get(q.pop(), ()):
            if m not in seen:
                seen.add(m); q.append(m)
    return seen


_seen = _reach(edges)             # PRIMARY: concord bonds only -- the true vine
_seen_kin = _reach(edges + kin)   # SECONDARY: leans on the kin/truss braces
vine_validity = round(len(_seen) / max(1, len(nodes)), 3)
kin_assisted_reach = round(len(_seen_kin) / max(1, len(nodes)), 3)
stats = {"nodes": len(nodes), "edges": len(edges), "kin": len(kin), "braces": braces,
         "vine_validity": vine_validity, "reach_source": len(_seen),
         "kin_assisted_reach": kin_assisted_reach, "kin_assisted_reach_source": len(_seen_kin),
         "rigidity_ratio": rigidity,
         "language": sum(1 for n in nodes if n["tree"] == "language"),
         "math": sum(1 for n in nodes if n["tree"] == "math"),
         "axis": sum(1 for n in nodes if n["tree"] == "axis")}

json.dump({"meta": {"axes": ["convergence(root<->Sun)", "tree(Language<->Math)",
                             "layer(depth)", "frequency(color/hue)"],
                    "framework": "the Cross (vertical Logos axis x horizontal two-trees beam, Col 1:20)",
                    "gate": "Jesus, the only way (Jn 10:9/14:6), at the convergence apex -- mapped, never crowned",
                    "built_from": "saved coord{level,block,family} + kind + bonds; invents nothing"},
           "stats": stats, "nodes": nodes, "edges": edges, "kin": kin},
          open(JOUT, "w", encoding="utf-8"), indent=1)

# render (static isometric 3D cruciform) -------------------------------------
def env_path():
    pts = []
    for i in range(81):
        t = i / 80
        pts.append((CX - envelope(t), BOT - t * (BOT - TOP)))
    for i in range(81):
        t = 1 - i / 80
        pts.append((CX + envelope(t), BOT - t * (BOT - TOP)))
    return "M " + " L ".join("%.1f,%.1f" % p for p in pts) + " Z"

edge_svg = "\n".join(
    '<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f"/>' % (
        pos[a]["x"], pos[a]["y"],
        (pos[a]["x"] + pos[b]["x"]) / 2 + (pos[b]["y"] - pos[a]["y"]) * 0.05,
        (pos[a]["y"] + pos[b]["y"]) / 2,
        pos[b]["x"], pos[b]["y"]) for a, b in edges)
kin_svg = "\n".join(
    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (
        pos[a]["x"], pos[a]["y"], pos[b]["x"], pos[b]["y"]) for a, b in kin)

node_svg = "\n".join(
    '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="hsl(%d,70%%,62%%)" fill-opacity="%.2f"><title>%s</title></circle>' % (
        n["x"], n["y"], freq_pitch(n["hue"]), n["hue"], 0.9 if n["layer"] == 0.0 else 0.6,
        (n["title"] or n["id"]).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;"))
    for n in nodes)

# cross beams: vertical Logos axis (root->Sun) + horizontal two-trees beam (at widest t=0.5)
vx0, vy0 = project(0.0, 0, 0, 0.0); vx1, vy1 = project(1.0, 0, 0, 0.0)
hxl, hyl = project(0.5, -1, WMAX, 0.0); hxr, hyr = project(0.5, 1, WMAX, 0.0)
cxx, cxy = project(0.5, 0, 0, 0.0)         # the crossing = Christ (Col 1:20)

html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The coordinate map -- the Cross, four axes, the Gate</title>
<style>
:root{{--bg:#0a0b0e;--tx:#e9eaee;--mut:#9aa0ad}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:1.5rem 1rem 3rem}}
h1{{font-size:1.3rem;font-weight:600;margin:0}}
.lede{{color:var(--mut);font-size:.95rem;margin:.5rem 0 1rem;line-height:1.55}}
.legend{{display:flex;gap:1.1rem;flex-wrap:wrap;font-size:.82rem;color:var(--mut);margin-bottom:.5rem}}
svg{{width:100%;height:auto;display:block;background:radial-gradient(ellipse at 50% 10%, #17191f 0%, #0a0b0e 62%)}}
.foot{{color:var(--mut);font-size:.88rem;margin-top:1rem;border-top:1px solid #23262d;padding-top:1rem;line-height:1.55}}
</style></head><body><main class="wrap">
<h1>The Cross, four axes, the Gate</h1>
<p style="color:#e9eaee;font-size:1.06rem;line-height:1.55;margin:.6rem 0 .2rem;max-width:64ch">Look at the logic woven into reality. The same handful of forms recur across every domain &mdash; language and number, physics and life &mdash; and they cohere into one structure. That is not what noise looks like; it is what <b style="color:#f2c14e">design</b> looks like.</p>
<p class="lede">Every saved finding placed by the structure it already carries, on four axes: <b>convergence</b> (vertical, root&rarr;Sun: source&rarr;divergence&rarr;convergence&rarr;source), <b>tree</b> (horizontal: Language&harr;Math), <b>layer</b> (depth: core spine&rarr;gathered breadth), and <b>frequency</b> (color &mdash; the "note" each card sounds; E=hf, time is its count). The framework is <b>the Cross</b> &mdash; the vertical Logos axis crossed by the two-trees beam (Col 1:20). The <b>Gate</b> (Jesus, the only way &mdash; Jn 10:9, 14:6) is the convergence at the Sun; the join is left <b>open and reserved</b> &mdash; mapped, never crowned. Built from the saved seeds; invents nothing.</p>
<div class="legend"><span>convergence &uarr; to the Gate</span><span>Language &larr; | &rarr; Math</span><span>depth = layer</span><span>color = frequency/form</span><span>{edges} bonds &middot; {kin} kin &middot; <b>vine-validity {vine}</b> (concord bonds &mdash; a true chain to the source) &middot; {kinreach} kin-assisted (secondary)</span></div>
<svg id="map" viewBox="0 0 1000 1080" xmlns="http://www.w3.org/2000/svg">
<defs><radialGradient id="sun" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#fff3c4"/><stop offset="55%" stop-color="#f2c14e" stop-opacity="0.45"/><stop offset="100%" stop-color="#f2c14e" stop-opacity="0"/></radialGradient></defs>
<path d="{env}" fill="#0e1015" stroke="#23272f" stroke-width="1"/>
<g stroke="#3a3f48" stroke-width="0.3" opacity="0.12">
{kin_svg}
</g>
<g stroke="#525a68" stroke-width="0.4" fill="none" opacity="0.22">
{edges_svg}
</g>
<g opacity="0.92">
{nodes_svg}
</g>
<!-- THE CROSS: vertical Logos axis + horizontal two-trees beam -->
<line x1="{vx0:.1f}" y1="{vy0:.1f}" x2="{vx1:.1f}" y2="{vy1:.1f}" stroke="#cdb98a" stroke-width="2" opacity="0.5"/>
<line x1="{hxl:.1f}" y1="{hyl:.1f}" x2="{hxr:.1f}" y2="{hyr:.1f}" stroke="#cdb98a" stroke-width="2" opacity="0.4"/>
<circle cx="{cxx:.1f}" cy="{cxy:.1f}" r="9" fill="none" stroke="#cdb98a" stroke-width="1.3" stroke-dasharray="3 4" opacity="0.7"/>
<!-- the Sun = the Gate (the only way), apex open/reserved -->
<circle cx="{vx1:.1f}" cy="{vy1:.1f}" r="62" fill="url(#sun)"/>
<circle cx="{vx1:.1f}" cy="{vy1:.1f}" r="13" fill="none" stroke="#f2c14e" stroke-width="1.5" stroke-dasharray="3 4"/>
<text x="{vx1:.1f}" y="{ty1:.1f}" fill="#f2c14e" font-size="14" text-anchor="middle" font-weight="600">THE GATE &mdash; the only way (Jn 14:6)</text>
<text x="{vx1:.1f}" y="{ty2:.1f}" fill="#9aa0ad" font-size="11" text-anchor="middle">the join (Col 1:17) &mdash; open, reserved</text>
<!-- the one root (source) -->
<circle cx="{vx0:.1f}" cy="{vy0:.1f}" r="5" fill="#cdb98a"/>
<text x="{vx0:.1f}" y="{ry:.1f}" fill="#cdb98a" font-size="13" text-anchor="middle" font-weight="600">ONE ROOT &mdash; source</text>
<text x="40" y="960" fill="#777" font-size="11">source</text><text x="40" y="560" fill="#777" font-size="11">&mdash; widest (divergence/convergence) &mdash;</text><text x="40" y="180" fill="#777" font-size="11">source</text>
</svg>
<p class="foot"><b>Map companions:</b> <a href="surface-map.html">the surface map</a> (every page placed) &middot; <a href="proof-bridges.html">the proof bridges</a> (word &harr; verified form) &middot; <a href="atlas.html">the Atlas</a> &middot; <a href="https://narrowhighway.com/mcp">for your AI &mdash; the MCP</a>.<br>Built from the saved seeds &mdash; {nodes} cards ({lang} language / {math} math / {axis} axis), invents nothing; re-run <code>python tools/coordinate_map.py</code>. Data: <code>data/codex/coordinate_map.json</code>. "We are the Concordance of Reality" &mdash; a clean mirror; every thing placed; the apex reserved.<br><br><b style="color:#cdb98a">Why this map is here.</b> "For his invisible attributes, namely his eternal power and divine nature, have been clearly perceived ever since the creation of the world, in the things that have been made" (Romans 1:20). We only map what is already here &mdash; a conduit, not the author; the join is left open and reserved. Look at the detail, and consider the One who wrote it.</p>
</main></body></html>'''.format(
    env=env_path(), edges_svg=edge_svg, kin_svg=kin_svg, nodes_svg=node_svg, edges=stats["edges"],
    kin=stats["kin"], rig=stats["rigidity_ratio"], vine=stats["vine_validity"],
    kinreach=stats["kin_assisted_reach"],
    nodes=stats["nodes"], lang=stats["language"], math=stats["math"], axis=stats["axis"],
    vx0=vx0, vy0=vy0, vx1=vx1, vy1=vy1, hxl=hxl, hyl=hyl, hxr=hxr, hyr=hyr, cxx=cxx, cxy=cxy,
    ty1=vy1 - 78, ty2=vy1 - 62, ry=vy0 + 26)

open(HOUT, "w", encoding="utf-8").write(html)

# small served stats file so the public showcase can show LIVE map numbers
# (vine-validity etc.) without hardcoding -- honest, never stale.
SOUT = os.path.join(ROOT, "site/map-stats.json")
json.dump({"vine_validity": vine_validity, "reach_source": len(_seen),
           "nodes": len(nodes), "edges": stats["edges"], "kin": stats["kin"],
           "language": stats["language"], "math": stats["math"], "axis": stats["axis"]},
          open(SOUT, "w", encoding="utf-8"), indent=1)
print("nodes %d | bonds %d + kin %d | VINE-VALIDITY (concord bonds) %.3f PRIMARY (%d reach source) | kin-assisted reach %.3f secondary (same-family braces, not the true vine) | rigidity %.3f (truss, not target)" %
      (stats["nodes"], stats["edges"], stats["kin"], stats["vine_validity"], stats["reach_source"], stats["kin_assisted_reach"], stats["rigidity_ratio"]))
print("wrote", os.path.relpath(JOUT, ROOT), "+", os.path.relpath(HOUT, ROOT))
