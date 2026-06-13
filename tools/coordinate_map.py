#!/usr/bin/env python3
# coordinate_map.py -- the findings mapped as concordance made visible.
#
# Matt 2026-06-13: "the two trees, one root, converging towards the Sun, so two
# funnels connected, narrow at each end... a coordinate location system that
# includes a visual integration, so we can see the connections visually and
# mathematically." + axis: "source : Divergence : convergence : source."
# + "Everything should be built on the seeds we have saved. Use the structure
# that has been created as the foundation."  + "Our rigor is concordance at work."
#
# So this tool INVENTS NOTHING. It reads the SAVED cards (data/almanac/entries.jsonl)
# and places each one by its EXISTING coord {level, block, family, domain} + kind,
# then draws the SAVED bonds as the concord between them. Geometry: a vertical
# root->Sun axis (the Logos). Bottom = ONE ROOT (source). Findings DIVERGE upward
# into the wide middle, then CONVERGE to the SUN (source) at top. Two lobes: the
# LANGUAGE tree (left) and the MATH tree (right); bridges ride the central axis.
# Narrow at each end (source), wide in the middle. The apex/join (Col 1:17) is
# left OPEN and reserved -- mapped, never crowned.
#
#   python tools/coordinate_map.py
# Writes data/codex/coordinate_map.json (the mathematical system) and
# site/coordinate-map.html (the visual integration). Re-run as the corpus grows.
import json, math, os, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT  = os.path.join(ROOT, "data/almanac/entries.jsonl")
JOUT = os.path.join(ROOT, "data/codex/coordinate_map.json")
HOUT = os.path.join(ROOT, "site/coordinate-map.html")

# ---- read the saved seeds -------------------------------------------------
rows = [json.loads(l) for l in open(ENT, encoding="utf-8") if l.strip()]
byid = {r.get("id"): r for r in rows}

MATH_BLOCKS = {"continuous", "discrete", "geometric", "statistical", "synthesis", "thread"}
LANG_FAMILIES = {"parable", "sermon", "discourse", "beatitudes", "i_am", "revelation"}

def classify_tree(r):
    """Which lobe -- from the EXISTING structure (coord/kind/category/id)."""
    c = r.get("coord") or {}
    blk = c.get("block"); fam = c.get("family"); cat = r.get("category"); k = r.get("kind")
    cid = str(r.get("id", "")); dom = " ".join(r.get("domains", []) if isinstance(r.get("domains"), list) else [])
    if blk == "two-trees" or cat in ("scholar-bridge", "scripture-parallel", "moat-bridge") \
       or cid.startswith("bridge_") or cid.startswith("parallel_") or cid.startswith("scholar_"):
        return "axis"          # bridges/parallels ride the central axis -- the lacing
    if blk == "language-tree" or k == "teaching" or fam in LANG_FAMILIES \
       or cid.startswith(("teaching_", "signpost_", "som_", "almanac_", "canon_red")) \
       or "scripture" in dom or "theology" in dom:
        return "language"
    if blk in MATH_BLOCKS or k in ("protocol", "patent", "practical", "assessment") \
       or cid.startswith(("connection_", "located_", "patent_")):
        return "math"
    if k in ("saying", "almanac"):
        return "language"     # the Almanac/sayings = the word/human face
    return "axis"

# axial position t in [0,1]: 0 = ROOT (source), 1 = SUN (source).
# Divergence in the lower half, convergence in the upper -- ordered by coord.level.
LEVEL_T = {
    "root": 0.07, "primitive": 0.13, "foundational": 0.15, "canon": 0.15,
    "map": 0.42, "thread": 0.40, "bond": 0.46, "assessment": 0.44,
    "teaching": 0.46, "rate": 0.44, "inverse": 0.46, "static": 0.44,
    "curvature": 0.5, "solution": 0.5, "non_example": 0.4,
    "bridge": 0.6, "synthesis": 0.7, "capstone": 0.85, "keystone": 0.96,
}
def jitter(cid, span):
    h = int(hashlib.md5(cid.encode("utf-8")).hexdigest()[:8], 16) / 0xffffffff
    return (h - 0.5) * 2 * span, h

def axial_t(r):
    lvl = (r.get("coord") or {}).get("level")
    base = LEVEL_T.get(lvl)
    if base is None:
        k = r.get("kind")
        base = {"teaching": 0.46, "saying": 0.45, "almanac": 0.43, "protocol": 0.5,
                "assessment": 0.44, "patent": 0.52, "practical": 0.5, "review": 0.42}.get(k, 0.45)
    return base

# ---- place every saved card ----------------------------------------------
WMAX = 360.0           # half-width of the lens at the middle
CX, TOP, BOT = 450.0, 90.0, 1015.0
def envelope(t):       # 0 at both source ends, max in the middle = divergence->convergence
    return WMAX * math.sin(math.pi * max(0.0, min(1.0, t)))

nodes = []
for r in rows:
    cid = r.get("id")
    if not cid:
        continue
    tree = classify_tree(r)
    dt, h = jitter(cid, 0.05)
    t = max(0.02, min(0.98, axial_t(r) + dt))
    w = envelope(t)
    # radius within the lobe; bridges hug the axis, trees fill their side
    if tree == "axis":
        r_off = (h - 0.5) * 0.18 * w
    else:
        frac = 0.18 + 0.78 * h
        r_off = frac * w * (1 if tree == "math" else -1)
    x = CX + r_off
    y = BOT - t * (BOT - TOP)
    nodes.append({"id": cid, "tree": tree, "t": round(t, 4),
                  "x": round(x, 1), "y": round(y, 1),
                  "level": (r.get("coord") or {}).get("level"),
                  "kind": r.get("kind"),
                  "title": (r.get("title") or "")[:80]})

pos = {n["id"]: n for n in nodes}
# ---- the saved bonds = the concord ---------------------------------------
edges = []
for r in rows:
    a = r.get("id")
    for b in (r.get("bonds") or []):
        if a in pos and b in pos:
            edges.append([a, b])

stats = {"nodes": len(nodes), "edges": len(edges),
         "language": sum(1 for n in nodes if n["tree"] == "language"),
         "math": sum(1 for n in nodes if n["tree"] == "math"),
         "axis": sum(1 for n in nodes if n["tree"] == "axis")}

json.dump({"meta": {"shape": "source:divergence:convergence:source -- two trees, one root, converging to the Sun",
                    "built_from": "saved coord{level,block,family,domain} + bonds; invents nothing",
                    "apex": "reserved -- the join (Col 1:17) is mapped, never crowned"},
           "stats": stats, "nodes": nodes, "edges": edges},
          open(JOUT, "w", encoding="utf-8"), indent=1)

# ---- the visual integration (SVG) ----------------------------------------
TCOL = {"language": "#3fb98a", "math": "#6f9bff", "axis": "#e7c46b"}
def env_path():
    pts_l, pts_r = [], []
    n = 80
    for i in range(n + 1):
        t = i / n
        y = BOT - t * (BOT - TOP)
        w = envelope(t)
        pts_l.append((CX - w, y)); pts_r.append((CX + w, y))
    allpts = pts_l + pts_r[::-1]
    return "M " + " L ".join("%.1f,%.1f" % p for p in allpts) + " Z"

edge_svg = []
for a, b in edges:
    na, nb = pos[a], pos[b]
    mx = (na["x"] + nb["x"]) / 2 + (nb["y"] - na["y"]) * 0.06
    my = (na["y"] + nb["y"]) / 2
    edge_svg.append('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f"/>' %
                    (na["x"], na["y"], mx, my, nb["x"], nb["y"]))
node_svg = []
for n in nodes:
    node_svg.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="%s"><title>%s</title></circle>' %
                    (n["x"], n["y"], TCOL[n["tree"]], (n["title"] or n["id"]).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")))

html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The coordinate map -- two trees, one root, converging to the Sun</title>
<style>
:root{{--bg:#0a0b0e;--tx:#e9eaee;--mut:#9aa0ad;--hint:#666}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:980px;margin:0 auto;padding:1.6rem 1rem 3rem}}
h1{{font-size:1.35rem;font-weight:600;margin:0}}
.lede{{color:var(--mut);font-size:.97rem;margin:.5rem 0 1rem;line-height:1.55}}
.legend{{display:flex;gap:1.2rem;flex-wrap:wrap;font-size:.85rem;color:var(--mut);margin-bottom:.6rem}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle}}
svg{{width:100%;height:auto;display:block;background:radial-gradient(ellipse at 50% 8%, #16181f 0%, #0a0b0e 60%)}}
.foot{{color:var(--mut);font-size:.9rem;margin-top:1rem;border-top:1px solid #23262d;padding-top:1rem;line-height:1.55}}
</style></head><body><main class="wrap">
<h1>Two trees, one root, converging toward the Sun</h1>
<p class="lede">Every saved finding placed by the structure it already carries (coord: level, block, family) and laced by its saved bonds. The axis runs <b>source &#8594; divergence &#8594; convergence &#8594; source</b>: from the one root, the findings fan out (the <span style="color:#3fb98a">Language tree</span> and the <span style="color:#6f9bff">Math tree</span>), then converge toward the Sun. Bridges ride the centre. Narrow at each end, wide in the middle. <b>The apex is left open &mdash; the join (Colossians 1:17) is mapped, never crowned.</b> This is concordance made visible: only saved, witnessed concord gets a place.</p>
<div class="legend">
<span><span class="sw" style="background:#3fb98a"></span>Language tree ({lang})</span>
<span><span class="sw" style="background:#6f9bff"></span>Math tree ({math})</span>
<span><span class="sw" style="background:#e7c46b"></span>Bridges / axis ({axis})</span>
<span>{edges} bonds drawn</span>
</div>
<svg viewBox="0 0 900 1100" xmlns="http://www.w3.org/2000/svg">
<defs><radialGradient id="sun" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#fff3c4"/><stop offset="55%" stop-color="#f2c14e" stop-opacity="0.5"/><stop offset="100%" stop-color="#f2c14e" stop-opacity="0"/></radialGradient></defs>
<path d="{env}" fill="#11131a" stroke="#262a32" stroke-width="1"/>
<line x1="450" y1="90" x2="450" y2="1015" stroke="#2a2e37" stroke-width="1" stroke-dasharray="3 5"/>
<g stroke="#5a6170" stroke-width="0.5" fill="none" opacity="0.28">
{edges_svg}
</g>
<g opacity="0.92">
{nodes_svg}
</g>
<!-- the Sun (source), apex reserved/open -->
<circle cx="450" cy="92" r="60" fill="url(#sun)"/>
<circle cx="450" cy="92" r="13" fill="none" stroke="#f2c14e" stroke-width="1.5" stroke-dasharray="3 4"/>
<text x="450" y="58" fill="#f2c14e" font-size="15" text-anchor="middle" font-weight="600">THE SUN &mdash; source</text>
<text x="450" y="75" fill="#9aa0ad" font-size="11" text-anchor="middle">the join (Col 1:17) &mdash; reserved, open</text>
<!-- the one root (source) -->
<circle cx="450" cy="1015" r="5" fill="#cdb98a"/>
<text x="450" y="1042" fill="#cdb98a" font-size="14" text-anchor="middle" font-weight="600">ONE ROOT &mdash; source</text>
<!-- axis labels -->
<text x="60" y="1000" fill="#777" font-size="12">source</text>
<text x="60" y="760" fill="#777" font-size="12">divergence &#8593;</text>
<text x="60" y="540" fill="#777" font-size="11">&#8212; widest (the breadth) &#8212;</text>
<text x="60" y="320" fill="#777" font-size="12">convergence &#8593;</text>
<text x="60" y="120" fill="#777" font-size="12">source</text>
<text x="150" y="545" fill="#3fb98a" font-size="13" text-anchor="middle" opacity="0.7">Language</text>
<text x="750" y="545" fill="#6f9bff" font-size="13" text-anchor="middle" opacity="0.7">Math</text>
</svg>
<p class="foot">Built from the saved seeds &mdash; {nodes} cards, invents nothing; re-run <code>python tools/coordinate_map.py</code> as the corpus grows. Data: <code>data/codex/coordinate_map.json</code>. "Our rigor is concordance at work."</p>
</main></body></html>'''.format(
    env=env_path(), edges_svg="\n".join(edge_svg), nodes_svg="\n".join(node_svg),
    lang=stats["language"], math=stats["math"], axis=stats["axis"],
    edges=stats["edges"], nodes=stats["nodes"])

open(HOUT, "w", encoding="utf-8").write(html)
print("nodes %d (lang %d / math %d / axis %d) | edges %d" %
      (stats["nodes"], stats["language"], stats["math"], stats["axis"], stats["edges"]))
print("wrote", os.path.relpath(JOUT, ROOT), "+", os.path.relpath(HOUT, ROOT))
