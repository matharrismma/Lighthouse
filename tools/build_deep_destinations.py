#!/usr/bin/env python3
"""Generate deep-destination pages from a shared template + per-page config.

Each deep destination follows the same shape:
  greeting → scoped airlock → today's-draw → tile grid → footer note

This script writes site/learn-deep.html, site/codex-deep.html, and
site/take-part.html — the remaining three of the 8 deep destinations
(Desk + Family + Watch & Listen already shipped as hand-written files
since they pioneered the pattern).

Run from repo root:
    python tools/build_deep_destinations.py            # dry-run, prints paths
    python tools/build_deep_destinations.py --apply    # writes the files
"""
import argparse
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
ORIGIN = "https://narrowhighway.com"

# Shared template. {slug} {title} {description} {eyebrow} {h1_default}
# {tagline} {airlock_ask} {airlock_hint} {airlock_placeholder}
# {today_card_label} {today_card_src} {rooms_html} {footer_note}
# {schema_json} {greetings_js}
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Narrow Highway</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{origin}/{slug}.html">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Narrow Highway">
  <meta property="og:title" content="{title} · Narrow Highway">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{origin}/{slug}.html">
  <meta property="og:image" content="{origin}/img/og_card.png">
  <meta name="twitter:card" content="summary_large_image">

  <script type="application/ld+json">
{schema_json}
  </script>

  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,400;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

  <link rel="stylesheet" href="/nh-shell.css">
  <script defer src="/nh-shell.js"></script>

  <style>
    :root {{
      --paper: #faf6ec; --rule: #d4c8a5; --rule-strong: #b9ac82;
      --ink: #1f1a14; --ink-2: #3a3328;
      --brass: #9b7c3c; --brass-hi: #c9a851; --oxblood: #7a3a32; --pass: #4f7a3a;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background:
        radial-gradient(ellipse at top, rgba(255,255,255,.4), transparent 60%),
        linear-gradient(180deg, #f5efdc 0%, #f0e8d0 100%);
      color: var(--ink); font-family: 'Crimson Pro', Georgia, serif;
      line-height: 1.55; min-height: 100dvh; -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--oxblood); text-decoration: underline; text-decoration-color: rgba(122,58,50,.4); text-underline-offset: 2px; }}
    a:hover {{ color: var(--brass); text-decoration-color: var(--brass); }}
    .fwrap {{ max-width: 960px; margin: 0 auto; padding: 26px 22px 60px; }}

    .greeting {{ margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--rule); }}
    .greeting .eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: .22em; text-transform: uppercase; color: var(--brass); margin-bottom: 6px; }}
    .greeting h1 {{ font-family: 'Crimson Pro', Georgia, serif; font-weight: 600; font-size: clamp(1.7rem, 4vw, 2.4rem); color: var(--ink); letter-spacing: -0.01em; margin-bottom: 4px; }}
    .greeting .tag {{ font-style: italic; color: var(--ink-2); font-size: 15px; max-width: 56ch; }}

    .airlock {{ background: var(--paper); border: 1px solid var(--rule-strong); border-left: 4px solid var(--brass); border-radius: 4px; padding: 18px 22px 16px; margin-bottom: 22px; box-shadow: 0 1px 0 rgba(43,24,16,.04), 0 8px 24px rgba(43,24,16,.06); }}
    .airlock .ask {{ font-family: 'Crimson Pro', Georgia, serif; font-weight: 600; font-size: 1.15rem; color: var(--ink); margin-bottom: 6px; }}
    .airlock .hint {{ font-style: italic; color: var(--ink-2); font-size: 13.5px; margin-bottom: 12px; max-width: 56ch; }}
    .airlock form {{ display: flex; gap: 8px; }}
    .airlock input {{ flex: 1; padding: 11px 14px; background: #fffdf6; color: var(--ink); border: 1px solid var(--rule-strong); border-radius: 4px; font-family: 'Crimson Pro', Georgia, serif; font-size: 15px; outline: none; }}
    .airlock input:focus {{ border-color: var(--brass); box-shadow: 0 0 0 3px rgba(155,124,60,.18); }}
    .airlock button {{ padding: 0 18px; background: var(--brass); color: #fff; border: 1px solid var(--brass); border-radius: 4px; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: .15em; text-transform: uppercase; font-weight: 600; }}
    .airlock button:hover {{ background: var(--brass-hi); border-color: var(--brass-hi); }}

    .routing {{ margin-top: 12px; padding: 11px 14px; background: #fdf9ea; border: 1px solid var(--rule); border-left: 3px solid var(--brass); border-radius: 0 4px 4px 0; display: none; }}
    .routing.show {{ display: block; }}
    .routing .hd {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: .16em; text-transform: uppercase; color: var(--brass); margin-bottom: 4px; }}
    .routing .name {{ font-weight: 600; font-size: 1.05rem; color: var(--ink); }}
    .routing .why {{ font-style: italic; color: var(--ink-2); font-size: 13px; }}
    .routing .go {{ display: inline-block; margin-top: 8px; padding: 6px 14px; background: var(--brass); color: #fff !important; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: .14em; text-transform: uppercase; text-decoration: none; }}
    .routing .go:hover {{ background: var(--brass-hi); text-decoration: none; }}

    .today-card {{ background: var(--paper); border: 1px solid var(--rule); border-radius: 4px; padding: 18px 22px; margin-bottom: 22px; }}
    .today-card .lbl {{ font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--brass); margin-bottom: 8px; display: flex; justify-content: space-between; gap: 12px; }}
    .today-card .lbl .src {{ color: var(--ink-2); font-style: italic; letter-spacing: normal; text-transform: none; font-family: 'Crimson Pro', Georgia, serif; }}
    .today-card h3 {{ font-family: 'Crimson Pro', Georgia, serif; font-weight: 600; font-size: 1.3rem; color: var(--ink); margin-bottom: 6px; }}
    .today-card p {{ font-size: 15px; color: var(--ink-2); line-height: 1.55; margin: 0; }}
    .today-card .empty {{ font-style: italic; color: var(--ink-2); font-size: 14px; }}
    .today-card .more {{ display: inline-block; margin-top: 10px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--oxblood); }}

    .rooms-h {{ font-family: 'JetBrains Mono', monospace; font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--brass); margin-bottom: 14px; }}
    .rooms {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; margin-bottom: 28px; }}
    .room {{ display: block; background: var(--paper); border: 1px solid var(--rule); border-left: 3px solid var(--brass); border-radius: 0 4px 4px 0; padding: 14px 16px; text-decoration: none; color: var(--ink); transition: border-left-color .12s, background .12s, transform .15s; }}
    .room:hover {{ border-left-color: var(--oxblood); background: #fdf9ea; text-decoration: none; transform: translateY(-1px); }}
    .room .icn {{ font-size: 1.5em; filter: sepia(.5) saturate(.7); display: inline-block; margin-right: 6px; vertical-align: middle; }}
    .room .nm {{ font-family: 'Crimson Pro', Georgia, serif; font-weight: 600; font-size: 1.05rem; color: var(--ink); vertical-align: middle; }}
    .room .d {{ font-family: 'Crimson Pro', Georgia, serif; font-style: italic; font-size: 13px; color: var(--ink-2); margin-top: 5px; line-height: 1.45; }}

    .family-note {{ margin-top: 22px; padding-top: 14px; border-top: 1px solid var(--rule); text-align: center; font-style: italic; color: var(--ink-2); font-size: 13.5px; max-width: 56ch; margin-left: auto; margin-right: auto; }}
  </style>
</head>

<body class="nh-shell-cream" data-nh-toc="off">

<main class="fwrap">

  <div class="greeting">
    <div class="eyebrow">{eyebrow}</div>
    <h1 id="dGreet">{h1_default}</h1>
    <p class="tag">{tagline}</p>
  </div>

  <section class="airlock">
    <div class="ask">{airlock_ask}</div>
    <div class="hint">{airlock_hint}</div>
    <form id="dAir" onsubmit="return dAirSubmit(event);">
      <input id="dAirIn" type="text" placeholder="{airlock_placeholder}" autocomplete="off">
      <button type="submit" id="dAirSend">Send &rarr;</button>
    </form>
    <div class="routing" id="dRouting"></div>
  </section>

{today_card_block}

  <div class="rooms-h">{rooms_heading}</div>
  <div class="rooms">
{rooms_html}
  </div>

  <p class="family-note">{footer_note}</p>

</main>

<script>
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const $ = id => document.getElementById(id);

(function () {{
  const h = new Date().getHours();
  const greetings = {greetings_js};
  const part = h < 5 ? 'late' : h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
  if (greetings[part]) $('dGreet').textContent = greetings[part];
}})();

async function dAirSubmit(ev) {{
  ev.preventDefault();
  const txt = ($('dAirIn').value || '').trim();
  if (!txt) return false;
  const send = $('dAirSend'); send.disabled = true; send.textContent = '…';
  const routeBox = $('dRouting'); routeBox.classList.remove('show');
  try {{
    const r = await fetch('/airlock/classify', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{text: txt}}),
    }});
    if (!r.ok) throw new Error('classify failed');
    const j = await r.json();
    routeBox.innerHTML =
      '<div class="hd">The shepherd suggests</div>' +
      '<div class="name">' + esc(j.destination_label || j.route || '—') + '</div>' +
      '<div class="why"><em>' + esc(j.why || '') + '</em> &middot; confidence ' + Number(j.confidence || 0).toFixed(2) + '</div>' +
      (j.url ? '<a class="go" href="' + esc(j.url) + '">Open ' + esc(j.destination_label || 'destination') + ' &rarr;</a>' : '');
    routeBox.classList.add('show');
  }} catch (e) {{
    routeBox.innerHTML = '<div class="hd">The airlock is quiet</div><div class="why">Try a room below directly.</div>';
    routeBox.classList.add('show');
  }} finally {{
    send.disabled = false; send.textContent = 'Send →';
  }}
  return false;
}}

{today_card_js}
</script>

</body>
</html>
"""


TODAY_CARD_BLOCK = """
  <section class="today-card" id="dToday">
    <div class="lbl"><span>{today_card_label}</span><span class="src" id="dTodaySrc">—</span></div>
    <h3 id="dTodayT">Loading…</h3>
    <p id="dTodayB">A card surfaced from today's substrate.</p>
  </section>
"""

TODAY_CARD_JS = """
(async function () {
  try {
    const r = await fetch('/daily-card');
    if (!r.ok) throw 0;
    const j = await r.json();
    const card = j && j.card;
    if (!card) throw 0;
    $('dTodayT').textContent = card.title || '(untitled)';
    $('dTodayB').innerHTML =
      (card.body ? esc(String(card.body).slice(0, 260)) + (card.body.length > 260 ? '…' : '') : '') +
      (card.url ? ' <a class="more" href="' + esc(card.url) + '">Open the card →</a>' : '');
    const src = card.source || {};
    $('dTodaySrc').textContent = src.label || src.author || (j.date || '');
  } catch (e) {
    $('dTodayT').textContent = 'The substrate is quiet today.';
    $('dTodayB').innerHTML = '<span class="empty">No card surfaced. Open a room below and draw from there.</span>';
    $('dTodaySrc').textContent = '';
  }
})();
"""


def render_rooms(rooms):
    parts = []
    for r in rooms:
        parts.append(
            f'    <a class="room" href="{r["url"]}">\n'
            f'      <div><span class="icn">{r["icon"]}</span><span class="nm">{r["name"]}</span></div>\n'
            f'      <div class="d">{r["blurb"]}</div>\n'
            f'    </a>'
        )
    return "\n".join(parts)


def render_page(cfg):
    has_today = cfg.get("today_card", True)
    today_block = TODAY_CARD_BLOCK.format(today_card_label=cfg.get("today_card_label", "Today's draw")) if has_today else ""
    today_js = TODAY_CARD_JS if has_today else ""
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": cfg["title"] + " · Narrow Highway",
        "description": cfg["description"],
        "url": f"{ORIGIN}/{cfg['slug']}.html",
        "isPartOf": {"@id": f"{ORIGIN}/#website"},
        "publisher": {"@id": f"{ORIGIN}/#org"},
    }
    schema.update(cfg.get("schema_extra", {}))
    return TEMPLATE.format(
        origin=ORIGIN,
        slug=cfg["slug"],
        title=cfg["title"],
        description=cfg["description"],
        eyebrow=cfg["eyebrow"],
        h1_default=cfg["h1_default"],
        tagline=cfg["tagline"],
        airlock_ask=cfg["airlock_ask"],
        airlock_hint=cfg["airlock_hint"],
        airlock_placeholder=cfg["airlock_placeholder"],
        rooms_heading=cfg.get("rooms_heading", "The rooms"),
        rooms_html=render_rooms(cfg["rooms"]),
        today_card_block=today_block,
        today_card_js=today_js,
        footer_note=cfg["footer_note"],
        schema_json=json.dumps(schema, indent=4),
        greetings_js=json.dumps(cfg["greetings"], indent=4),
    )


# ── Per-destination configs ─────────────────────────────────────
CONFIGS = [
    {
        "slug": "learn-deep",
        "title": "Learn",
        "description": "The learn desk — homeschool pathways, the encyclopedia, the bible library, reading plans. One drawer for the family's whole curriculum.",
        "eyebrow": "Learn",
        "h1_default": "Open the book.",
        "tagline": "Homeschool pathways, the encyclopedia, public-domain Bibles in parallel, reading plans, places, characters. Tools for the family's whole curriculum.",
        "airlock_ask": "What do you want to learn?",
        "airlock_hint": "A subject, a verse, a word, a place — name it. The shepherd will point you to the right shelf.",
        "airlock_placeholder": "phonics for a 5-year-old…  or…  what does ' selah' mean in Hebrew…  or…  geography of Acts.",
        "today_card": True,
        "today_card_label": "Today's draw",
        "rooms": [
            {"icon": "🎓", "name": "Homeschool pathways",   "url": "/learn.html",         "blurb": "Visible learning paths from phonics upward — taught along the Narrow Highway."},
            {"icon": "📚", "name": "Curriculum",            "url": "/curriculum.html",    "blurb": "Whole-family lessons, free, sequenced. Submit your own to the substrate."},
            {"icon": "📖", "name": "Bibles in parallel",    "url": "/bibles.html",        "blurb": "Every public-domain Bible translation, side-by-side. KJV, Geneva, Tyndale, ASV, more."},
            {"icon": "📑", "name": "Reading plans",         "url": "/reading.html",       "blurb": "Walk through Scripture and the classics on a rhythm that holds."},
            {"icon": "🪑", "name": "The Reading Room",      "url": "/reading-room.html",  "blurb": "Sit and read — full-text works from the library."},
            {"icon": "🏛️", "name": "Encyclopedia",          "url": "/encyclopedia.html",  "blurb": "A curated A–Z reference, weighed through the gates."},
            {"icon": "📕", "name": "The Library",           "url": "/library.html",       "blurb": "Everything we've kept — books, films, music, magazines."},
            {"icon": "🗺️", "name": "Bible places",          "url": "/places.html",        "blurb": "Geography of Scripture — every city, river, mountain we found in the keeping."},
            {"icon": "📜", "name": "Atlas",                  "url": "/atlas.html",         "blurb": "The Concordance map — verifier-gate grid across topics."},
            {"icon": "🧪", "name": "Field kit",             "url": "/fieldkit.html",      "blurb": "Thirteen cards — the working pocket guide to discernment."},
        ],
        "greetings": {
            "morning":   "Good morning. Open the book.",
            "afternoon": "Good afternoon. The reading room is open.",
            "evening":   "Good evening. A page or two before bed.",
            "late":      "Up late — the lamp is on the desk.",
        },
        "footer_note": "Every text here is in the public domain or shared under a permissive license. Nothing locked, nothing watermarked, nothing tracked.",
        "schema_extra": {
            "audience":   {"@type": "PeopleAudience", "audienceType": "homeschool families"},
            "about":      [{"@type": "EducationalOccupationalProgram"}, {"@type": "Book"}, {"@type": "DefinedTermSet"}],
            "keywords":   "homeschool curriculum, Christian education, parallel Bibles, encyclopedia, reading plans",
        },
    },

    {
        "slug": "codex-deep",
        "title": "Codex",
        "description": "The codex desk — the canonical manuscript. Guidance, tradition, the assembly, testimony, the witness roll. Where the engine's outputs are bound into a book.",
        "eyebrow": "Codex",
        "h1_default": "The manuscript.",
        "tagline": "The engine produces. The codex collects and binds. Guidance, tradition, the assembly, testimony, the witness roll — the manuscript layer of the work.",
        "airlock_ask": "What do you want to read in the manuscript?",
        "airlock_hint": "A doctrine, a Father, a theme, a tradition — name it. The shepherd will surface what's been bound.",
        "airlock_placeholder": "what does the codex say about justification…  or…  show me the witness roll…  or…  the assembly today.",
        "today_card": True,
        "today_card_label": "Today's reading",
        "rooms": [
            {"icon": "📖", "name": "The Codex",          "url": "/codex.html",          "blurb": "The bound manuscript. Three layers: body, engine outputs, index."},
            {"icon": "📜", "name": "Canon",              "url": "/canon.html",          "blurb": "What we hold as canonical. The substrate from which everything else is weighed."},
            {"icon": "🧭", "name": "Guidance",           "url": "/guidance.html",       "blurb": "The working canon's guidance document. How the codex is built and held."},
            {"icon": "🏛️", "name": "Tradition",          "url": "/tradition.html",      "blurb": "Following the Levitical tradition — pattern, not claim."},
            {"icon": "👥", "name": "The Assembly",       "url": "/assembly.html",       "blurb": "The working canon, the assembly's order, today's reading."},
            {"icon": "🕯️", "name": "Testimony",          "url": "/testimony.html",      "blurb": "Covenant testimony — what we have heard, seen, handled."},
            {"icon": "🌿", "name": "Witness Roll",       "url": "/witnesses.html",      "blurb": "Every witness who attested, signed, sealed."},
            {"icon": "🏠", "name": "Refuge",             "url": "/refuge.html",         "blurb": "The City of Refuge — where the falsely accused find shelter while the trial is heard."},
            {"icon": "🪶", "name": "Organic Design",     "url": "/organic-design.html", "blurb": "Organic Intelligence (OI) — what we are, what we are not."},
            {"icon": "📚", "name": "Works of M.R. Harris", "url": "/works.html",        "blurb": "The author's books: Dade, Molasses, Apokalypsis."},
        ],
        "greetings": {
            "morning":   "Good morning. The manuscript is open.",
            "afternoon": "Good afternoon. The codex sits on the desk.",
            "evening":   "Good evening. A page from the manuscript.",
            "late":      "Up late — the candle is lit beside the codex.",
        },
        "footer_note": "The codex is not authored synthesis. The engine produces; we curate; the index is generated. The body, the outputs, and the index — together, the manuscript.",
        "schema_extra": {
            "about":    [{"@type": "Book"}, {"@type": "CreativeWork"}],
            "keywords": "Christian codex, theological canon, working canon, witness roll, Levitical tradition, organic intelligence",
        },
    },

    {
        "slug": "take-part",
        "title": "Take Part",
        "description": "Take part in Narrow Highway — submit a recipe, a lesson, a story, a song, a testimony. Pitch a show. Support the work. Become a witness.",
        "eyebrow": "Take Part",
        "h1_default": "Pull up a chair.",
        "tagline": "Submit a recipe to the cookbook, a lesson to the curriculum, a testimony to the roll, a pitch for a show. The engine produces; the community fills the well.",
        "airlock_ask": "What do you want to bring?",
        "airlock_hint": "A recipe, a lesson, a story, a hymn — name it. The shepherd will route it to the right submission desk.",
        "airlock_placeholder": "I have a great cornbread recipe to share…  or…  pitch a show on the early church…  or…  I'd like to support the work.",
        "today_card": False,
        "rooms": [
            {"icon": "🍞", "name": "Submit a recipe",       "url": "/submit-recipe.html",     "blurb": "Add to the heritage cookbook. Public-domain or your own kitchen — both welcome."},
            {"icon": "📝", "name": "Submit a lesson",       "url": "/submit-curriculum.html", "blurb": "Add to the curriculum. One subject, one age band, sequenced."},
            {"icon": "📨", "name": "Submit content",        "url": "/submit-content.html",    "blurb": "A story, a song, a testimony, a photograph. The engine can render submissions into shows."},
            {"icon": "🎬", "name": "Pitch a show",          "url": "/pitch.html",             "blurb": "A series idea — the engine produces, we curate, the channel airs the survivors."},
            {"icon": "🕯️", "name": "Become a witness",      "url": "/witness.html",           "blurb": "Attest as a witness. Your testimony joins the roll, signed and sealed."},
            {"icon": "✍️", "name": "Scribe",                "url": "/scribe.html",            "blurb": "Help fill the substrate — transcribe, translate, curate."},
            {"icon": "🤝", "name": "Support",               "url": "/support.html",           "blurb": "Covenant tiers. Free use of everything; what's earned funds what's next."},
            {"icon": "🏢", "name": "Sponsors",              "url": "/sponsors.html",          "blurb": "Sponsor as studio — fund a whole show, the way 1950s P&G funded Hallmark."},
            {"icon": "✉️", "name": "Contact",               "url": "/contact.html",           "blurb": "Reach the operator. Plain email, plain answer."},
        ],
        "greetings": {
            "morning":   "Good morning. Pull up a chair.",
            "afternoon": "Good afternoon. The desk is open.",
            "evening":   "Good evening. A seat by the lamp.",
            "late":      "Up late — the desk is still staffed.",
        },
        "footer_note": "Everything submitted is weighed through the gates. The engine never auto-publishes; the operator reviews. Nothing posted without an actual human saying yes.",
        "schema_extra": {
            "keywords": "Christian community, submit content, sponsor a show, witness testimony, scribe, Christian creators",
        },
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    for cfg in CONFIGS:
        out = SITE / f"{cfg['slug']}.html"
        html = render_page(cfg)
        if args.apply:
            out.write_text(html, encoding="utf-8")
            print(f"  wrote {out}  ({len(html):,} chars, {len(cfg['rooms'])} rooms)")
        else:
            print(f"  would write {out}  ({len(html):,} chars, {len(cfg['rooms'])} rooms)")
    if not args.apply:
        print("\n  --apply to write")


if __name__ == "__main__":
    sys.exit(main() or 0)
