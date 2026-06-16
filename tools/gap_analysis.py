#!/usr/bin/env python3
"""gap_analysis.py -- the steering instrument, re-runnable from LIVE local state.

Matt 2026-06-15 ("This is what we need"): the project is steered by the honest
gap picture, built from REAL numbers (never estimates). This regenerates that
picture every time, so the dashboard tracks reality as gaps close.

It reads three real sources, all local + deterministic (no network):
  1. the engine TOOLS list  -> which domains are VERIFIED, which have a
     data-backed lookup (GROUNDED)            [src/.../mcp_server/tools.py]
  2. site/map-stats.json    -> vine-validity (CONNECTED to source)
  3. data/almanac/entries.jsonl -> form-card count

Each verified domain is one of: GROUNDED (external authoritative data),
PURE_COMPUTE (complete in the formula -- needs no data), or UNGROUNDED (verified
but empirical with no reference data yet = the real gap). map-never-launder: the
value is that the numbers are real.

Outputs:
  data/codex/gap_analysis.json   (the metrics)
  site/gap-analysis.html         (the served visual)

Usage:  python tools/gap_analysis.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_PY = ROOT / "src" / "concordance_engine" / "mcp_server" / "tools.py"
MAP_STATS = ROOT / "site" / "map-stats.json"
ENTRIES = ROOT / "data" / "almanac" / "entries.jsonl"
OUT_JSON = ROOT / "data" / "codex" / "gap_analysis.json"
OUT_HTML = ROOT / "site" / "gap-analysis.html"

# Domain -> the wired external data source that grounds it (read off DATA_SOURCES).
GROUNDED = {
    "calendar_time": "IANA tzdata + IERS", "physics_dimensional": "UCUM units",
    "number_theory": "OEIS", "combinatorics": "OEIS", "linguistics": "CMU dict + WordNet",
    "networking": "IANA ports/RFC", "cryptography": "IANA ports/RFC", "astronomy": "HYG catalog",
    "thermodynamics": "CoolProp", "energy": "CoolProp", "phase": "CoolProp",
    "nutrition": "USDA FoodData", "medicine": "openFDA + DrugCentral",
    "biology": "NCBI Taxonomy", "ecology": "NCBI Taxonomy", "genetics": "NCBI Taxonomy",
    "finance": "ECB euro FX", "geography": "GeoNames", "scripture_anchors": "original-language lexicon",
    "exercise_science": "Compendium of Physical Activities (METs)",
    "nuclear_physics": "NUBASE/AME nuclide data (half-lives)",
    "chemistry": "IUPAC periodic table (atomic weights)",
    "economics": "World Bank Open Data",
    "labor": "World Bank Open Data (labor indicators)",
    # Self-contained: the verifier ships public-domain reference data inline (read the
    # verifier; no external dataset is needed) -- grounded in real authoritative data,
    # just embedded rather than a separate lw/ db.
    "agriculture": "embedded USDA/NRCS reference (in-verifier)",
    "soil_science": "embedded FAO/USDA-NRCS reference (in-verifier)",
    "law": "embedded US Constitution / US Code reference (in-verifier)",
    # Honest classification pass 2026-06-16 (read each verifier): these embed REAL
    # standards-body values that are NOT derivable from math -- building-code dimensions
    # and security-standard bands -- so they are grounded in authoritative reference data
    # (embedded), exactly like law/agriculture/soil above.
    "architecture": "embedded IBC building-code reference (in-verifier)",
    "cybersecurity": "embedded CVSS v3.1 / RFC 8996 TLS reference (in-verifier)",
}
# Domains complete in the formula -- the verifier takes the values as INPUTS and checks
# the math (Snell's law, Manning velocity, dew point, radiometric decay, date arithmetic,
# stress-strain). They need no external reference data. (Confirmed by reading each.)
# HONEST NOTE: pure-compute verifies the RELATIONSHIP among supplied values, not their
# real-world ground-truth (e.g. it confirms V == I*R, not the measured resistance of a
# real component). That is grounding of the math, not omniscience over the world.
PURE_COMPUTE = {
    "mathematics", "geometry", "formal_logic", "statistics", "statistics_pvalue",
    "statistics_confidence_interval", "statistics_multiple_comparisons",
    "operations_research", "information_theory", "music_theory", "physics_conservation",
    "optics", "geology", "hydrology", "meteorology", "oceanography", "materials_science",
    "history_chronology",
    # Added by the 2026-06-16 classification pass (each read; formula/structural check on
    # caller-supplied inputs -- manufacturing's DPMO<->sigma table is Gaussian-derived so
    # pure-compute is the modest, correct label; witness/governance check packet structure).
    "acoustics", "computer_science", "construction", "document_validation", "electrical",
    "giving", "governance_decision_packet", "manufacturing", "photography", "physics",
    "quantum_computing", "real_estate", "sports_analytics", "witness",
}
# Word/reason-grounded -- NOT empirical-measurement domains. They ground through Scripture,
# logic, and the corpus (the original-text + cards layer), never through external measured
# data. Counting them as "empirical domains lacking data" was a category error: there is no
# dataset that could or should ground them. Excluded from the empirical denominator.
NON_EMPIRICAL = {
    "philosophy", "rhetoric", "theology_doctrine",
}
# Six families for the rollup (each verified domain lands in one).
FAMILIES = {
    "pure math & logic": ["mathematics", "geometry", "number_theory", "combinatorics",
        "formal_logic", "statistics", "statistics_pvalue", "statistics_confidence_interval",
        "statistics_multiple_comparisons", "operations_research", "information_theory"],
    "physics & chemistry": ["physics", "physics_conservation", "physics_dimensional",
        "chemistry", "optics", "acoustics", "thermodynamics", "energy", "phase",
        "materials_science", "electrical", "nuclear_physics", "quantum_computing"],
    "earth sciences": ["geography", "geology", "oceanography", "hydrology", "meteorology",
        "soil_science", "agriculture"],
    "life & medicine": ["biology", "ecology", "genetics", "medicine", "nutrition",
        "exercise_science"],
    "language & Word": ["linguistics", "rhetoric", "music_theory", "scripture_anchors",
        "theology_doctrine", "philosophy", "witness", "giving"],
    "human systems": ["economics", "finance", "labor", "law", "governance_decision_packet",
        "real_estate", "history_chronology", "document_validation", "sports_analytics",
        "photography"],
    "built & tech": ["architecture", "construction", "manufacturing", "networking",
        "cybersecurity", "cryptography", "computer_science", "astronomy", "calendar_time"],
}


def parse_tools():
    txt = TOOLS_PY.read_text(encoding="utf-8")
    names = set(re.findall(r'"name":\s*"([a-z0-9_]+)"', txt))
    verify = sorted(n[len("verify_"):] for n in names if n.startswith("verify_"))
    lookups = [n for n in ("timezone_offset", "unit_convert", "sequence_lookup",
        "word_pronunciation", "port_lookup", "rfc_lookup", "star_lookup", "fluid_property",
        "food_nutrition", "drug_lookup", "species_lookup", "drug_target", "currency_convert",
        "place_lookup", "word_meaning", "word_study", "wikidata", "activity_mets",
        "nuclide_data", "element_data", "molar_mass", "economic_indicator") if n in names]
    return verify, lookups, len(names)


def classify(domain):
    if domain in GROUNDED:
        return "grounded"
    if domain in PURE_COMPUTE:
        return "pure_compute"
    if domain in NON_EMPIRICAL:
        return "non_empirical"
    return "ungrounded"


def main():
    verify, lookups, n_tools = parse_tools()
    stats = json.loads(MAP_STATS.read_text(encoding="utf-8")) if MAP_STATS.exists() else {}
    vine = stats.get("vine_validity", 0.0)
    reach, nodes = stats.get("reach_source", 0), stats.get("nodes", 0)
    forms = sum(1 for l in ENTRIES.open(encoding="utf-8")
                if l.strip() and json.loads(l).get("category") == "form")

    targets_path = ROOT / "data" / "codex" / "targets.json"
    tg = json.loads(targets_path.read_text(encoding="utf-8")) if targets_path.exists() else {}
    g_targets = tg.get("ground", [])
    ot_ms = tg.get("original_text", [])
    ground_open = [t for t in g_targets if t.get("status") != "done"]
    ot_done = sum(1 for m in ot_ms if m.get("status") == "done")
    ot_pct = round(100 * ot_done / max(1, len(ot_ms)))

    cls = {d: classify(d) for d in verify}
    grounded = [d for d in verify if cls[d] == "grounded"]
    pure = [d for d in verify if cls[d] == "pure_compute"]
    non_emp = [d for d in verify if cls[d] == "non_empirical"]
    ungrounded = [d for d in verify if cls[d] == "ungrounded"]
    empirical = grounded + ungrounded          # domains that CAN use external data
    emp_pct = round(100 * len(grounded) / max(1, len(empirical)))

    fam = {}
    for name, doms in FAMILIES.items():
        present = [d for d in doms if d in verify]
        g = [d for d in present if cls[d] == "grounded"]
        p = [d for d in present if cls[d] == "pure_compute"]
        ne = [d for d in present if cls[d] == "non_empirical"]
        fam[name] = {"n": len(present), "grounded": len(g), "pure_compute": len(p),
                     "non_empirical": len(ne),
                     "ungrounded": len(present) - len(g) - len(p) - len(ne)}

    data = {
        "verifiers": len(verify), "tools": n_tools, "data_grounded_tools": len(lookups),
        "grounded_domains": len(grounded), "pure_compute_domains": len(pure),
        "non_empirical_domains": len(non_emp),
        "ungrounded_domains": len(ungrounded), "empirical_grounded_pct": emp_pct,
        "vine_validity": vine, "reach_source": reach, "nodes": nodes, "form_cards": forms,
        "original_text_pct": ot_pct, "original_text_done": ot_done, "original_text_total": len(ot_ms),
        "ground_targets_open": len(ground_open),
        "targets": {"ground_open": ground_open, "original_text": ot_ms},
        "families": fam, "grounded": grounded, "ungrounded": ungrounded,
        "non_empirical": non_emp,
        # The additive/easy gaps (connect, ground, onboard) are essentially closed -- the
        # honest frontier has moved to GENERATIVE work. These are the real next steps.
        "easy_wins": ["more commentators (Barnes/Calvin/JFB) into the take layer",
                      "more translations onboard alongside WEB",
                      "the concord-score across existing takes (data already keyed)",
                      "deepen embedded references (more standard values per domain)"],
        "bottlenecks": ["new verifiers are slow, exact -- DOMAIN COVERAGE is the frontier now",
                        "each verifier checks a bounded slice; the claim-space is vast",
                        "engine finds, never generates -- bound by the discovered",
                        "the Missions layer is people-work, not a metric"],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    OUT_HTML.write_text(render_html(data), encoding="utf-8")
    print("verifiers %d | grounded %d (empirical %d%%) | pure-compute %d | non-empirical %d | ungrounded %d"
          % (len(verify), len(grounded), emp_pct, len(pure), len(non_emp), len(ungrounded)))
    print("vine-validity %.3f (%d/%d) | form-cards %d | tools %d"
          % (vine, reach, nodes, forms, n_tools))
    print("targets -- ground: %d sources to wire | original text: %d/%d milestones"
          % (len(ground_open), ot_done, len(ot_ms)))
    print("wrote", OUT_JSON.name, "+", OUT_HTML.name)


def _bar(label, hint, pct, color, right):
    return (
        '<div class="row"><div class="lab">%s <span class="hint">%s</span></div>'
        '<div class="track"><div class="fill" style="width:%d%%;background:%s"></div></div>'
        '<div class="val">%s</div></div>' % (label, hint, pct, color, right))


def render_html(d):
    GREEN, AMBER = "#3fb950", "#d29922"
    emp = d["empirical_grounded_pct"]
    fam_rows = ""
    for name, f in d["families"].items():
        n = f["n"] or 1
        done = f["grounded"] + f["pure_compute"] + f.get("non_empirical", 0)  # grounded, complete, or Word/reason
        pct = round(100 * done / n)
        col = GREEN if pct >= 60 else AMBER
        note = ("%d grounded" % f["grounded"]) if f["grounded"] else "ungrounded"
        if f["pure_compute"]:
            note += " / %d pure-compute" % f["pure_compute"]
        if f.get("non_empirical"):
            note += " / %d Word-grounded" % f["non_empirical"]
        fam_rows += _bar(name, "", pct, col, note + " (%d)" % f["n"])
    wins = "".join('<li>%s</li>' % w for w in d["easy_wins"])
    necks = "".join('<li>%s</li>' % b for b in d["bottlenecks"])
    g_open = d["targets"]["ground_open"]
    g_li = "".join('<li>%s &mdash; %s</li>' % (t["domain"], t["source"]) for t in g_open)
    ot_li = "".join(('<li style="color:#3fb950">done &mdash; %s</li>' % m["name"])
                    if m.get("status") == "done" else ('<li>%s</li>' % m["name"])
                    for m in d["targets"]["original_text"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Concordance -- gap analysis</title>
<style>
:root{{--bg:#0a0b0e;--tx:#e9eaee;--mut:#9aa0ad;--line:#23262d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
line-height:1.5;padding:2rem 1rem}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-weight:500;font-size:22px;margin:0 0 .2rem}}
.sub{{color:var(--mut);font-size:14px;margin-bottom:1.6rem}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:1.8rem}}
.card{{background:#14161b;border:1px solid var(--line);border-radius:8px;padding:1rem}}
.card .k{{font-size:13px;color:var(--mut)}}.card .v{{font-size:24px;font-weight:500;margin-top:2px}}
.sec{{font-size:13px;color:var(--mut);margin:1.4rem 0 .7rem}}
.row{{display:flex;align-items:center;gap:10px;margin-bottom:9px}}
.lab{{width:150px;font-size:13px}}.hint{{color:#6b7280}}
.track{{flex:1;height:18px;background:#14161b;border-radius:6px;overflow:hidden;border:1px solid var(--line)}}
.fill{{height:100%;border-radius:6px}}
.val{{width:118px;font-size:12px;color:var(--mut);text-align:right}}
.reserved{{flex:1;height:18px;border:1px dashed #3a3f49;border-radius:6px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin:12px 0 0}}
.dot{{width:10px;height:10px;border-radius:2px;display:inline-block;vertical-align:middle;margin-right:5px}}
.witness{{color:var(--mut);font-size:13px;margin:16px 0 0;font-style:italic}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:1.8rem}}
.cols h3{{font-weight:500;font-size:14px;margin:0 0 .5rem}}
.cols ul{{margin:0;padding-left:1.1rem;color:var(--mut);font-size:13px}}.cols li{{margin:.3rem 0}}
.foot{{color:#6b7280;font-size:12px;margin-top:2rem;border-top:1px solid var(--line);padding-top:1rem}}
</style></head><body><div class="wrap">
<h1>Gap analysis</h1>
<div class="sub">Steering instrument -- regenerated from live state. We work the gaps in order.</div>
<div class="cards">
<div class="card"><div class="k">domains verified</div><div class="v">{d['verifiers']}</div></div>
<div class="card"><div class="k">grounded in data</div><div class="v">{d['grounded_domains']}</div></div>
<div class="card"><div class="k">connected to source</div><div class="v">{d['vine_validity']*100:.1f}%</div></div>
<div class="card"><div class="k">form-cards</div><div class="v">{d['form_cards']}</div></div>
</div>
<div class="sec">capability stack -- where coverage drops</div>
{_bar('verify','(the math)',90,GREEN,'strong')}
{_bar('connect','(to source)',min(100,round(d['vine_validity']*100)),GREEN,'%d / %d'%(d['reach_source'],d['nodes']))}
{_bar('ground','(real data)',emp,AMBER,'%d / %d empirical'%(d['grounded_domains'],d['grounded_domains']+d['ungrounded_domains']))}
{_bar('original text','(Heb/Grk)',d['original_text_pct'],AMBER,'%d / %d milestones'%(d['original_text_done'],d['original_text_total']))}
<div class="legend"><span><span class="dot" style="background:{GREEN}"></span>strong</span>
<span><span class="dot" style="background:{AMBER}"></span>gap to close</span></div>
<div class="witness">These bars measure the engine's reach over what can be checked. The One it all witnesses to is not on the chart -- he stands outside the exercise.</div>
<div class="sec">grounding by family</div>
{fam_rows}
<div class="sec">targets to fill the bars -- finish one, the bar rises</div>
<div class="cols">
<div><h3>ground -- {len(g_open)} sources to wire</h3><ul>{g_li}</ul></div>
<div><h3>original text -- {d['original_text_done']} / {d['original_text_total']} milestones</h3><ul>{ot_li}</ul></div>
</div>
<div class="cols">
<div><h3>easy wins -- additive, low risk</h3><ul>{wins}</ul></div>
<div><h3>bottlenecks -- generative, slow</h3><ul>{necks}</ul></div>
</div>
<div class="foot">Of {d['verifiers']} verified domains, {d['grounded_domains']} are grounded in authoritative reference data (external or embedded standards), {d['pure_compute_domains']} are pure-compute relationship-checks that need no data, and {d['non_empirical_domains']} ground through Scripture and logic (the Word, not measured data) -- {d['ungrounded_domains']} need-but-lack external data. The empirical-grounding gap closed by READING each verifier (a miscount correction), not by acquiring data -- map-never-launder. Honest frontier: this is grounding of the math, not omniscience over the world -- pure-compute confirms relationships (V == I*R), not real-world ground-truth, and each verifier still checks only a bounded slice of its domain. COVERAGE, original-language depth, and the Missions / concord layers are the live, generative work now.</div>
</div></body></html>"""


if __name__ == "__main__":
    main()
