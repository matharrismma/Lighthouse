"""build_learning_bundle.py — "learning that can't be cut off."

The longest lever for the poor (Matt, 2026-06-23): free, true, sovereign literacy
that reaches the unreached and grows with them. This packages the reading on-ramp
(the phonics curriculum) into a SINGLE self-contained file that runs from an SD
card on any cheap device — no internet, no install, no account, no cutoff.

It aims what we already have (data/phonics/units.jsonl) — it does not invent
lessons. The output is verified self-contained (no external references at all),
so it works the same on the grid or off it, and carries a sha256 manifest so a
copy can be confirmed unaltered.

Usage (run where the curriculum data lives — the droplet):
    python tools/build_learning_bundle.py [--out dist/learning-bundle]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_PHONICS = _REPO / "data" / "phonics" / "units.jsonl"


def _read_units(path: Path):
    units = []
    if not path.exists():
        raise SystemExit(f"no curriculum data at {path} — run this where the data lives")
    for line in path.read_text("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            units.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    units.sort(key=lambda u: (u.get("unit_seq", 9999), u.get("id", "")))
    return units


# The offline "school" — one file, no external anything. System fonts only.
# Data is INLINED (fetch() does not work from file://; <script> always does).
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Read — a free school that works anywhere</title>
<style>
  :root { --bg:#fbf7ee; --ink:#221c12; --soft:#5d5443; --line:#d9cdb3;
          --accent:#9a6a1e; --card:#fffdf7; --ok:#3f7d3f; }
  * { box-sizing:border-box; }
  html,body { margin:0; background:var(--bg); color:var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    line-height:1.6; -webkit-text-size-adjust:100%; }
  .wrap { max-width:720px; margin:0 auto; padding:14px 16px 120px; }
  header { display:flex; align-items:baseline; justify-content:space-between; gap:10px;
    padding:10px 0 12px; border-bottom:2px solid var(--line); }
  .brand { font-weight:800; letter-spacing:.02em; }
  .brand .x { color:var(--accent); }
  .prog { font-size:13px; color:var(--soft); font-variant-numeric:tabular-nums; }
  h1 { font-size:clamp(24px,6vw,34px); line-height:1.15; margin:18px 0 2px; }
  .seq { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); }
  .rule { font-size:19px; background:var(--card); border:1px solid var(--line);
    border-left:4px solid var(--accent); border-radius:10px; padding:14px 16px; margin:14px 0; }
  .h { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--soft); margin:20px 0 6px; }
  .ex { display:flex; flex-wrap:wrap; gap:8px; }
  .ex span { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:6px 13px; font-size:17px; }
  .say { font-size:clamp(20px,5.4vw,27px); font-weight:600; padding:14px 16px; background:#fff;
    border:2px dashed var(--line); border-radius:10px; }
  .mode { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; margin:10px 0; }
  .mode .lab { font-weight:700; color:var(--accent); }
  .mode .ins { font-size:14px; color:var(--soft); margin:2px 0 6px; }
  .mode .scr { font-size:16px; }
  .check { background:#f3efe2; border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:16px 0; }
  .check .q { font-weight:600; font-size:18px; }
  button { font:inherit; cursor:pointer; }
  .reveal { margin-top:10px; background:var(--accent); color:#fff; border:none; border-radius:8px;
    padding:11px 16px; font-weight:700; min-height:44px; }
  .ans { margin-top:10px; display:none; }
  .ans.show { display:block; }
  .ans .a { font-weight:700; color:var(--ok); font-size:18px; }
  .ans .note { font-size:14px; color:var(--soft); margin-top:4px; }
  nav.bar { position:fixed; left:0; right:0; bottom:0; background:var(--bg); border-top:2px solid var(--line);
    display:flex; gap:8px; padding:10px 12px; max-width:720px; margin:0 auto; }
  nav.bar button { flex:1; min-height:52px; border:1px solid var(--line); background:var(--card);
    border-radius:10px; font-weight:700; font-size:16px; color:var(--ink); }
  nav.bar button:disabled { opacity:.4; }
  nav.bar .toc { flex:0 0 auto; min-width:52px; }
  .toc-list { display:none; }
  .toc-list.show { display:block; }
  .toc-list a { display:block; padding:11px 10px; border-bottom:1px solid var(--line);
    color:var(--ink); text-decoration:none; font-size:16px; }
  footer { margin-top:30px; padding-top:16px; border-top:1px solid var(--line); font-size:13px; color:var(--soft); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">Read<span class="x"> ·</span></div>
    <div class="prog" id="prog"></div>
  </header>

  <div id="toc" class="toc-list" aria-label="All lessons"></div>
  <div id="view"></div>

  <footer>
    Free, and yours — to keep, to copy, to give. Works with no internet, on any device.
    This school teaches reading; for the deeper questions it points beyond itself, to Christ.
  </footer>
</div>

<nav class="bar">
  <button class="toc" id="tocBtn" aria-label="All lessons">☰</button>
  <button id="prev">◀ Back</button>
  <button id="next">Next ▶</button>
</nav>

<script>
var UNITS = window.NH_UNITS || [];
var i = 0;
function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function render(){
  var u = UNITS[i]; if(!u){return;}
  document.getElementById("prog").textContent = "Lesson " + (i+1) + " of " + UNITS.length;
  var h = "";
  h += '<div class="seq">' + esc(u.track || "reading") + '</div>';
  h += '<h1>' + esc(u.title || u.id) + '</h1>';
  if(u.rule){ h += '<div class="rule">' + esc(u.rule) + '</div>'; }
  if(u.examples && u.examples.length){
    h += '<div class="h">Examples</div><div class="ex">';
    for(var e=0;e<u.examples.length;e++){ h += '<span>' + esc(u.examples[e]) + '</span>'; }
    h += '</div>';
  }
  if(u.decodable_sentence){ h += '<div class="h">Read this out loud</div><div class="say">' + esc(u.decodable_sentence) + '</div>'; }
  if(u.modes && u.modes.length){
    h += '<div class="h">Practice together</div>';
    for(var m=0;m<u.modes.length;m++){ var mo=u.modes[m];
      h += '<div class="mode"><div class="lab">' + esc(mo.label||"") + '</div>';
      if(mo.instruction){ h += '<div class="ins">' + esc(mo.instruction) + '</div>'; }
      if(mo.script){ h += '<div class="scr">' + esc(mo.script) + '</div>'; }
      h += '</div>';
    }
  }
  if(u.check && (u.check.prompt || u.check.question)){
    var q = u.check.prompt || u.check.question;
    h += '<div class="check"><div class="q">Check: ' + esc(q) + '</div>';
    h += '<button class="reveal" data-reveal="1">Show the answer</button>';
    h += '<div class="ans"><div class="a">' + esc(u.check.answer||"") + '</div>';
    if(u.check.teaching_note){ h += '<div class="note">' + esc(u.check.teaching_note) + '</div>'; }
    h += '</div></div>';
  }
  document.getElementById("view").innerHTML = h;
  document.getElementById("prev").disabled = (i<=0);
  document.getElementById("next").disabled = (i>=UNITS.length-1);
  document.getElementById("toc").classList.remove("show");
  window.scrollTo(0,0);
  try{ localStorage.setItem("nh_read_at", String(i)); }catch(e){}
}
function go(n){ i=Math.max(0,Math.min(UNITS.length-1,n)); render(); }
document.getElementById("prev").onclick=function(){go(i-1);};
document.getElementById("next").onclick=function(){go(i+1);};
document.addEventListener("keydown",function(e){ if(e.key==="ArrowLeft")go(i-1); if(e.key==="ArrowRight")go(i+1); });
var toc = document.getElementById("toc"); var th="";
for(var t=0;t<UNITS.length;t++){ th += '<a href="#" data-i="'+t+'">'+(t+1)+'. '+esc(UNITS[t].title||UNITS[t].id)+'</a>'; }
toc.innerHTML = th;
toc.addEventListener("click",function(e){ var a=e.target.closest("a"); if(a){ e.preventDefault(); go(parseInt(a.getAttribute("data-i"),10)); } });
document.getElementById("tocBtn").onclick=function(){ toc.classList.toggle("show"); };
document.getElementById("view").addEventListener("click",function(e){ var b=e.target.closest("[data-reveal]"); if(b){ var a=b.nextElementSibling; if(a){a.classList.add("show");} b.style.display="none"; } });
try{ var saved=parseInt(localStorage.getItem("nh_read_at"),10); if(!isNaN(saved)) i=Math.max(0,Math.min(UNITS.length-1,saved)); }catch(e){}
render();
</script>
</body>
</html>
"""


def build(out_dir: Path) -> dict:
    units = _read_units(_PHONICS)
    if not units:
        raise SystemExit("no units parsed")
    # Inline the data. Escape </script> so the payload can't break out.
    data = json.dumps(units, ensure_ascii=False).replace("</", "<\\/")
    inject = '<script>window.NH_UNITS=' + data + ';</script>'
    html = _TEMPLATE.replace("<script>\nvar UNITS", inject + "\n<script>\nvar UNITS", 1)

    # Self-contained guarantee: NO external references at all.
    low = html.lower()
    for bad in ("http://", "https://", "//fonts", "src=\"http", "@import", "cdn"):
        if bad in low:
            raise SystemExit(f"NOT self-contained: found {bad!r} — offline guarantee broken")

    out_dir.mkdir(parents=True, exist_ok=True)
    school = out_dir / "school.html"
    school.write_text(html, encoding="utf-8")
    readme = out_dir / "README.txt"
    readme.write_text(
        "Read — a free school that works anywhere\n"
        "========================================\n\n"
        "Open school.html in any web browser. It needs NO internet, no install,\n"
        "no account. Copy it to a phone, an SD card, a USB stick; hand it to anyone.\n"
        "It teaches reading from the beginning, one lesson at a time.\n\n"
        "Free, and yours to keep and to give. Made to serve, and to point to Christ\n"
        "— never to replace Him.\n\n"
        f"Lessons: {len(units)}\n",
        encoding="utf-8")

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    manifest = {
        "bundle": "learning-bundle",
        "what": "Read — a free, offline, ownable reading school (the phonics on-ramp)",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "units": len(units),
        "self_contained": True,
        "files": {
            "school.html": {"sha256": _sha(school), "bytes": school.stat().st_size},
            "README.txt": {"sha256": _sha(readme), "bytes": readme.stat().st_size},
        },
        "note": "Verify a copy is unaltered: sha256sum school.html and compare.",
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the offline learning bundle")
    ap.add_argument("--out", default=str(_REPO / "dist" / "learning-bundle"))
    args = ap.parse_args()
    m = build(Path(args.out))
    print(json.dumps(m, ensure_ascii=False, indent=2))
