"""build_learning_bundle.py — "learning that can't be cut off", in any language.

The longest lever for the poor (Matt, 2026-06-23): free, true, sovereign literacy
that reaches the unreached. This packages a reading on-ramp into a SINGLE
self-contained file that runs from an SD card on any cheap device — no internet,
no install, no account, no cutoff.

It aims real curriculum data (data/<source>/units.jsonl) — it does NOT invent
lessons. The reader SHELL is language-agnostic (lang + direction + localized UI,
incl. right-to-left); the CONTENT is per-language and must be authored to that
language's own writing system. A bundle marked with a `review` note is an honest
STARTER pending a native-literacy reviewer — reading instruction is the one place
we never ship a guess.

Verified self-contained (no external references at all) + a sha256 manifest.

Usage:
    python tools/build_learning_bundle.py                 # English phonics -> school.html
    python tools/build_learning_bundle.py --lang es \\
        --source data/reading_es/units.jsonl              # Spanish -> school-es.html
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Localized UI + an honest per-language review banner (empty = reviewed/native set).
LABELS = {
    "en": {
        "brand": "Read", "dir": "ltr",
        "title": "Read — a free school that works anywhere",
        "lesson": "Lesson", "of": "of", "examples": "Examples",
        "read_aloud": "Read this out loud", "practice": "Practice together",
        "check": "Check:", "show": "Show the answer", "back": "Back", "next": "Next",
        "footer": ("Free, and yours — to keep, to copy, to give. Works with no internet, "
                   "on any device. This school teaches reading; for the deeper questions "
                   "it points beyond itself, to Christ."),
        "review": "",
        "source": "data/phonics/units.jsonl",
    },
    "es": {
        "brand": "Leer", "dir": "ltr",
        "title": "Leer — una escuela gratuita que funciona en cualquier lugar",
        "lesson": "Lección", "of": "de", "examples": "Ejemplos",
        "read_aloud": "Lee en voz alta", "practice": "Practiquen juntos",
        "check": "Comprueba:", "show": "Mostrar la respuesta", "back": "Atrás",
        "next": "Siguiente",
        "footer": ("Gratis, y tuyo — para guardar, copiar y regalar. Funciona sin internet, "
                   "en cualquier dispositivo. Esta escuela enseña a leer; para las preguntas "
                   "más profundas, señala más allá de sí misma, a Cristo."),
        "review": ("Inicio (borrador) — pendiente de revisión por un educador nativo en "
                   "alfabetización."),
        "source": "data/reading_es/units.jsonl",
    },
    "mcguffey": {
        "brand": "Read", "dir": "ltr", "html_lang": "en",
        "title": "Read — McGuffey's Eclectic Primer (1879)",
        "lesson": "Lesson", "of": "of", "examples": "New words",
        "read_aloud": "Read this aloud", "practice": "Practice together",
        "check": "Check:", "show": "Show the answer", "back": "Back", "next": "Next",
        "footer": ("Free, and yours — to keep, to copy, to give. Works with no internet, "
                   "on any device. This school teaches reading; for the deeper questions "
                   "it points beyond itself, to Christ."),
        "review": ("From McGuffey's Eclectic Primer, Revised Edition (W.H. McGuffey, 1879) "
                   "— public domain, via Project Gutenberg. A time-tested reader."),
        "source": "data/reading_en_mcguffey/units.jsonl",
    },
}


def _read_units(path: Path):
    if not path.exists():
        raise SystemExit(f"no curriculum data at {path} — run this where the data lives")
    units = []
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


# The offline "school" — one file, no external anything. System fonts only. Data
# is INLINED (fetch() doesn't work from file://). Logical CSS props so dir=rtl
# mirrors cleanly. All visible strings are placeholders, filled per language.
_TEMPLATE = """<!DOCTYPE html>
<html lang="__LANG__" dir="__DIR__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
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
  .review { background:#fff4dd; border:1px solid #e3c98c; border-radius:8px;
    padding:8px 12px; font-size:13px; color:#7a5a16; margin:12px 0 0; }
  h1 { font-size:clamp(24px,6vw,34px); line-height:1.15; margin:18px 0 2px; }
  .seq { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); }
  .rule { font-size:19px; background:var(--card); border:1px solid var(--line);
    border-inline-start:4px solid var(--accent); border-radius:10px; padding:14px 16px; margin:14px 0; }
  .h { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--soft); margin:20px 0 6px; }
  .ex { display:flex; flex-wrap:wrap; gap:8px; }
  .ex span { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:6px 13px; font-size:17px; }
  .say { font-size:clamp(20px,5.4vw,27px); font-weight:600; padding:14px 16px; background:#fff;
    border:2px dashed var(--line); border-radius:10px; white-space:pre-wrap; }
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
    <div class="brand">__BRAND__<span class="x"> ·</span></div>
    <div class="prog" id="prog"></div>
  </header>
  __REVIEW_BANNER__
  <div id="toc" class="toc-list"></div>
  <div id="view"></div>
  <footer>__FOOTER__</footer>
</div>

<nav class="bar">
  <button class="toc" id="tocBtn" aria-label="lessons">☰</button>
  <button id="prev">◀ __LBL_BACK__</button>
  <button id="next">__LBL_NEXT__ ▶</button>
</nav>

<script>
var UNITS = window.NH_UNITS || [];
var L = window.NH_LABELS || {};
var i = 0;
function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function render(){
  var u = UNITS[i]; if(!u){return;}
  document.getElementById("prog").textContent = L.lesson + " " + (i+1) + " " + L.of + " " + UNITS.length;
  var h = "";
  h += '<div class="seq">' + esc(u.track || "") + '</div>';
  h += '<h1>' + esc(u.title || u.id) + '</h1>';
  if(u.rule){ h += '<div class="rule">' + esc(u.rule) + '</div>'; }
  if(u.examples && u.examples.length){
    h += '<div class="h">' + esc(L.examples) + '</div><div class="ex">';
    for(var e=0;e<u.examples.length;e++){ h += '<span>' + esc(u.examples[e]) + '</span>'; }
    h += '</div>';
  }
  if(u.decodable_sentence){ h += '<div class="h">' + esc(L.read_aloud) + '</div><div class="say">' + esc(u.decodable_sentence) + '</div>'; }
  if(u.modes && u.modes.length){
    h += '<div class="h">' + esc(L.practice) + '</div>';
    for(var m=0;m<u.modes.length;m++){ var mo=u.modes[m];
      h += '<div class="mode"><div class="lab">' + esc(mo.label||"") + '</div>';
      if(mo.instruction){ h += '<div class="ins">' + esc(mo.instruction) + '</div>'; }
      if(mo.script){ h += '<div class="scr">' + esc(mo.script) + '</div>'; }
      h += '</div>';
    }
  }
  if(u.check && (u.check.prompt || u.check.question)){
    var q = u.check.prompt || u.check.question;
    h += '<div class="check"><div class="q">' + esc(L.check) + ' ' + esc(q) + '</div>';
    h += '<button class="reveal" data-reveal="1">' + esc(L.show) + '</button>';
    h += '<div class="ans"><div class="a">' + esc(u.check.answer||"") + '</div>';
    if(u.check.teaching_note){ h += '<div class="note">' + esc(u.check.teaching_note) + '</div>'; }
    h += '</div></div>';
  }
  document.getElementById("view").innerHTML = h;
  document.getElementById("prev").disabled = (i<=0);
  document.getElementById("next").disabled = (i>=UNITS.length-1);
  document.getElementById("toc").classList.remove("show");
  window.scrollTo(0,0);
  try{ localStorage.setItem("nh_read_at_"+(L.lang||"x"), String(i)); }catch(e){}
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
try{ var saved=parseInt(localStorage.getItem("nh_read_at_"+(L.lang||"x")),10); if(!isNaN(saved)) i=Math.max(0,Math.min(UNITS.length-1,saved)); }catch(e){}
render();
</script>
</body>
</html>
"""


def build(lang: str = "en", source: str = "", out_dir: Path = None) -> dict:
    lab = LABELS.get(lang)
    if lab is None:
        raise SystemExit(f"no labels for lang {lang!r} — add it to LABELS (UI strings)")
    src = Path(source) if source else (_REPO / lab["source"])
    if not src.is_absolute():
        src = _REPO / src
    units = _read_units(src)
    if not units:
        raise SystemExit("no units parsed")
    out_dir = out_dir or (_REPO / "dist" / ("learning-bundle-" + lang))

    data = json.dumps(units, ensure_ascii=False).replace("</", "<\\/")
    labels_js = dict(lab)
    labels_js["lang"] = lang
    ljson = json.dumps(labels_js, ensure_ascii=False).replace("</", "<\\/")
    inject = ('<script>window.NH_UNITS=' + data + ';window.NH_LABELS=' + ljson + ';</script>')

    review_html = (f'<div class="review">{lab["review"]}</div>' if lab["review"] else "")
    html = _TEMPLATE
    for k, v in {
        "__LANG__": lab.get("html_lang", lang), "__DIR__": lab["dir"], "__TITLE__": lab["title"],
        "__BRAND__": lab["brand"], "__REVIEW_BANNER__": review_html,
        "__LBL_BACK__": lab["back"], "__LBL_NEXT__": lab["next"], "__FOOTER__": lab["footer"],
    }.items():
        html = html.replace(k, v)
    html = html.replace("<script>\nvar UNITS", inject + "\n<script>\nvar UNITS", 1)

    low = html.lower()
    for bad in ("http://", "https://", "//fonts", "src=\"http", "@import", "cdn"):
        if bad in low:
            raise SystemExit(f"NOT self-contained: found {bad!r} — offline guarantee broken")
    if "__lbl_" in low or "__lang__" in low or "__title__" in low:
        raise SystemExit("a placeholder was left unfilled")

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = "school.html" if lang == "en" else f"school-{lang}.html"
    school = out_dir / fname
    school.write_text(html, encoding="utf-8")

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    manifest = {
        "bundle": "learning-bundle-" + lang, "lang": lang,
        "what": f"A free, offline, ownable reading school ({lang})",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "units": len(units), "self_contained": True,
        "starter_pending_review": bool(lab["review"]),
        "file": fname,
        "sha256": _sha(school), "bytes": school.stat().st_size,
        "note": f"Verify a copy is unaltered: sha256sum {fname} and compare.",
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the offline learning bundle")
    ap.add_argument("--lang", default="en", help="language code (en, es, ...)")
    ap.add_argument("--source", default="", help="path to units.jsonl (default per lang)")
    ap.add_argument("--out", default="", help="output dir (default dist/learning-bundle-<lang>)")
    args = ap.parse_args()
    m = build(lang=args.lang, source=args.source,
              out_dir=Path(args.out) if args.out else None)
    print(json.dumps(m, ensure_ascii=False, indent=2))
