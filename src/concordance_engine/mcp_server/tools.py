"""MCP tool implementations.

FastMCP server (server.py) imports the function-style API directly. List-style
API (TOOLS, list_tools, call_tool) used as fallback. ALL_TOOLS exposes a flat
{name: callable} map for tests and embedders.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..engine import (
    EngineConfig, validate_packet as _engine_validate,
    validate_and_seal as _engine_seal,
)
from ..verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance, scripture,
)
from ..verifiers import energy as _energy
from ..verifiers import acoustics as _acoustics
from ..verifiers import agriculture as _agriculture
from ..verifiers import astronomy as _astronomy
from ..verifiers import calendar_time as _calendar_time
from ..verifiers import combinatorics as _combinatorics
from ..verifiers import cryptography as _cryptography
from ..verifiers import document_validation as _document_validation
from ..verifiers import electrical as _electrical
from ..verifiers import exercise_science as _exercise_science
from ..verifiers import finance as _finance
from ..verifiers import formal_logic as _formal_logic
from ..verifiers import genetics as _genetics
from ..verifiers import geography as _geography
from ..verifiers import geology as _geology
from ..verifiers import geometry as _geometry
from ..verifiers import hydrology as _hydrology
from ..verifiers import information_theory as _information_theory
from ..verifiers import linguistics as _linguistics
from ..verifiers import manufacturing as _manufacturing
from ..verifiers import meteorology as _meteorology
from ..verifiers import music_theory as _music_theory
from ..verifiers import networking as _networking
from ..verifiers import number_theory as _number_theory
from ..verifiers import nutrition as _nutrition
from ..verifiers import optics as _optics
from ..verifiers import photography as _photography
from ..verifiers import sports_analytics as _sports_analytics
from ..verifiers import witness as _witness
from ..verifiers import quantum_computing as _quantum_computing
from ..verifiers import medicine as _medicine
from ..verifiers import cybersecurity as _cybersecurity
from ..verifiers import economics as _economics
from ..verifiers import labor as _labor
from ..verifiers import real_estate as _real_estate
from ..verifiers import construction as _construction
from ..verifiers import soil_science as _soil_science
from ..verifiers import thermodynamics as _thermodynamics
from ..verifiers import nuclear_physics as _nuclear_physics
from ..verifiers import ecology as _ecology
from ..verifiers import rhetoric as _rhetoric
from ..verifiers import philosophy as _philosophy
from ..verifiers import operations_research as _operations_research
from ..verifiers import law as _law
from ..verifiers import theology_doctrine as _theology_doctrine
from ..verifiers import history_chronology as _history_chronology
from ..verifiers import physical_constants as _physical_constants
from ..verifiers import periodic_table as _periodic_table
from ..verifiers import ephemeris as _ephemeris
from ..verifiers import layer_zero_grounding as _layer_zero_grounding
from ..verifiers import linear_algebra as _linear_algebra
from ..verifiers import probability as _probability
from ..verifiers import materials_science as _materials_science
from ..verifiers import architecture as _architecture
from ..verifiers import oceanography as _oceanography
from ..verifiers import phase as _phase
from ..verifiers import atomic as _atomic
from ..verifiers import molecular_geometry as _molecular_geometry
from ..verifiers import giving as _giving
from ..verifiers.base import VerifierResult
from ..walkthrough import (
    render_walkthrough, render_walkthrough_compact, render_walkthrough_html,
)
from ..ledger import find_closest as _find_closest


def _r(r: VerifierResult) -> Dict[str, Any]:
    return {"status": r.status, "detail": r.detail, "data": r.data}


# ---------------------------------------------------------------------
# Function-style API
# ---------------------------------------------------------------------

def validate_packet(packet, now_epoch=None):
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    res = _engine_validate(packet, now_epoch=now_epoch, config=cfg)
    return {
        "overall": res.overall,
        "gate_results": [
            {"gate": gr.gate, "status": gr.status,
             "reasons": gr.reasons, "details": gr.details}
            for gr in res.gate_results
        ],
    }


def seal_packet(packet, now_epoch=None, auto_precedent=False):
    """Run a packet through the four gates and return the sealed
    WitnessRecord as JSON. The agent surface for the canonical sealed
    record — same object the human walkthrough renderer consumes.

    Automatically binds the user's personal public key (subject_pubkey)
    as the soul anchor and embeds any existing witness attestations for
    this packet_id from the sidecar store.

    When `auto_precedent=True`, the Audit Chain is queried for the
    closest comparable precedent and (if found) sealed into the record.
    """
    from ..user_identity import get_user_pubkey
    from ..witness import list_for_precedent
    from ..witness_record import bind_subject, embed_attestations, with_permanent_ref
    from ..cas import store as _cas_store

    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    packet_id = packet.get("id")
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet_id,
    )

    # Bind soul anchor
    try:
        rec = bind_subject(rec, get_user_pubkey())
    except Exception:
        pass  # signing optional dep not installed

    # Embed any existing witness attestations for this packet
    if packet_id:
        try:
            atts = list_for_precedent(packet_id)
            if atts:
                rec = embed_attestations(rec, tuple(a.to_dict() for a in atts))
        except Exception:
            pass

    # Store in CAS — content_hash IS the permanent ref (no external service needed)
    try:
        d = rec.to_dict()
        h = _cas_store(d)
        rec = with_permanent_ref(rec, h)
        d = rec.to_dict()
    except Exception:
        d = rec.to_dict()

    return d


def walkthrough_packet(
    packet,
    now_epoch=None,
    fmt="markdown",
    expand_traces=False,
    auto_precedent=False,
):
    """Run a packet and return a human-readable walkthrough.

    `fmt` selects the renderer: "markdown" (Socratic walk, default),
    "compact" (one-screen status), or "html" (self-contained HTML page).
    `expand_traces=True` adds the verifier trace section to markdown
    and HTML outputs (compact ignores it). `auto_precedent=True` pulls
    in the closest comparable precedent before sealing.
    """
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet.get("id"),
    )
    fmt = (fmt or "markdown").lower()
    if fmt == "compact":
        return render_walkthrough_compact(rec)
    if fmt == "html":
        return render_walkthrough_html(rec, expand_traces=expand_traces)
    return render_walkthrough(rec, expand_traces=expand_traces)


# Map a chemistry VerifierResult.name -> the short output key, preserving the
# legacy keys ("equation"/"temperature") that existing callers/tests rely on.
_CHEM_RESULT_KEY = {
    "chemistry.equation": "equation",
    "chemistry.temperature_K": "temperature",
    "chemistry.pH_classification": "pH_classification",
    "chemistry.thermodynamic_feasibility": "thermodynamic_feasibility",
    "chemistry": "chemistry",
}


def verify_chemistry(equation=None, temperature_K=None, **spec):
    """Verify chemistry claims by routing a CHEM_VERIFY packet through chemistry.run().

    Three independent artifacts are recognised; any subset may be supplied:
      * equation balance     — equation="2 H2 + O2 -> 2 H2O"  (+ optional temperature_K)
      * pH classification    — pH=3, claimed_classification="acid"  (+ optional neutral_tolerance)
      * thermodynamic feasibility — delta_H_kJ_mol, delta_S_J_mol_K, temperature_K,
                                    claimed_spontaneous  (ΔG = ΔH - TΔS)

    Output is a dict keyed by check name, each value {"status","detail","data"} —
    backward compatible with the equation/temperature path (keys "equation",
    "balanced_form", "balanced_coefficients", "temperature").
    """
    # Build the CHEM_VERIFY packet from whatever the caller supplied. The dispatch
    # convention (agent_manifest.dispatch) calls this as verify_chemistry(**spec),
    # so pH / thermodynamic keys arrive in **spec; equation / temperature_K stay
    # positional for the legacy signature.
    chem_verify: Dict[str, Any] = {}
    if equation is not None:
        chem_verify["equation"] = equation
    if temperature_K is not None:
        chem_verify["temperature_K"] = temperature_K
    for k in ("pH", "claimed_classification", "neutral_tolerance",
              "delta_H_kJ_mol", "delta_S_J_mol_K", "claimed_spontaneous"):
        v = spec.get(k)
        if v is not None:
            chem_verify[k] = v
    # temperature_K may also ride in via the spec (e.g. a thermodynamic spec).
    if chem_verify.get("temperature_K") is None and spec.get("temperature_K") is not None:
        chem_verify["temperature_K"] = spec["temperature_K"]

    out: Dict[str, Any] = {}
    for r in chemistry.run({"CHEM_VERIFY": chem_verify}):
        out[_CHEM_RESULT_KEY.get(r.name, r.name)] = _r(r)
        if r.name == "chemistry.equation" and r.status == "MISMATCH" \
                and r.data and "balanced_lhs" in r.data:
            out["balanced_form"] = f"{r.data['balanced_lhs']} -> {r.data['balanced_rhs']}"
            out["balanced_coefficients"] = r.data.get("balanced_coefficients")
    return out


def verify_physics_dimensional(equation, symbols):
    return _r(physics.verify_dimensional_consistency(equation, symbols))


def verify_physics_conservation(before, after, tolerance_relative=1e-6,
                                 tolerance_absolute=0.0, law=None):
    if law:
        return _r(physics.verify_named_conservation(
            law, before, after,
            tolerance_relative=tolerance_relative,
            tolerance_absolute=tolerance_absolute,
        ))
    return _r(physics.verify_conservation(
        before, after,
        tolerance_relative=tolerance_relative,
        tolerance_absolute=tolerance_absolute,
    ))


def verify_mathematics(mode, params):
    """Mode dispatcher: equality|derivative|integral|limit|solve|matrix|inequality|series|ode."""
    mode = (mode or "").lower()
    out = {}
    import sympy as sp

    if mode == "equality":
        return _r(mathematics.verify_equality(params))
    if mode == "derivative":
        function = params["function"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        actual = sp.diff(f, x)
        out["computed_derivative"] = str(actual)
        if "claimed_derivative" in params:
            out.update(_r(mathematics.verify_derivative(params)))
        else:
            out["status"] = "CONFIRMED"
            out["detail"] = f"d/d{variable} of {function} = {actual}"
        return out
    if mode == "integral":
        integrand = params["integrand"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(integrand, locals={variable: x})
        try:
            anti = sp.integrate(f, x)
            out["computed_antiderivative"] = str(anti)
        except Exception as e:
            out["computed_antiderivative"] = None
            out["compute_error"] = str(e)
        if "claimed_antiderivative" in params:
            out.update(_r(mathematics.verify_integral(params)))
        return out
    if mode == "limit":
        function = params["function"]
        variable = params.get("variable", "x")
        point = params["point"]
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        try:
            actual = sp.limit(f, x, sp.sympify(str(point)))
            out["computed_limit"] = str(actual)
        except Exception as e:
            out["computed_limit"] = None
            out["compute_error"] = str(e)
        if "claimed_limit" in params:
            out.update(_r(mathematics.verify_limit(params)))
        return out
    if mode == "solve":
        eq = params["equation"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        if "=" in eq and "==" not in eq:
            lhs, rhs = eq.split("=", 1)
            eq_expr = sp.sympify(lhs, locals={variable: x}) - sp.sympify(rhs, locals={variable: x})
        else:
            eq_expr = sp.sympify(eq, locals={variable: x})
        actual = [str(s) for s in sp.solve(eq_expr, x)]
        out["computed_solutions"] = actual
        if "claimed_solutions" in params:
            out.update(_r(mathematics.verify_solve(params)))
        return out
    if mode == "matrix":
        return _r(mathematics.verify_matrix(params))
    if mode == "inequality":
        return _r(mathematics.verify_inequality(params))
    if mode == "series":
        return _r(mathematics.verify_series(params))
    if mode == "ode":
        return _r(mathematics.verify_ode(params))
    return {"status": "ERROR", "detail": f"unknown mode {mode!r}",
            "data": {"valid_modes": ["equality", "derivative", "integral", "limit",
                                     "solve", "matrix", "inequality", "series", "ode"]}}


def check(claim=None, steps=None, mode=None, params=None, domain="mathematics", seal=True):
    """THE one verification tool. Routes any kind of check through the derivation
    runner (the same path the HTTP API uses) so the result ALWAYS carries the worked
    math (the trail, step by step) and -- when it HOLDS -- a permanent, re-checkable
    seal (cite_url). The engine verifies a PROVIDED claim; it never generates the
    answer. The trail is the proof.

    Give exactly one of:
      - steps:  a multi-step derivation, list of
                {id, domain, spec, uses?, claim?} where spec is that domain's
                structured claim (math spec is {mode, params}).
      - mode + params (+ domain):  a single claim. For math, mode is one of
                equality|derivative|integral|limit|solve|matrix|inequality|series|ode
                and params is e.g. {expr_a, expr_b, variables} for equality.
      - claim:  a plain-language statement; the oracle structures it, the engine judges.

    Returns: {verdict (HOLDS/BROKEN/INCOMPLETE), steps, confirmed_steps,
              trail:[{id, domain, status, detail<-THE WORKED MATH, uses}],
              seal:{cite_url, content_hash}}.
    """
    from api import derivation as _d  # lazy import: avoids the tools<->derivation cycle
    if steps:
        result = _d.verify_derivation(list(steps))
    elif mode and params is not None:
        result = _d.verify_derivation(
            [{"id": "s1", "domain": domain or "mathematics",
              "spec": {"mode": mode, "params": params}}])
    elif claim:
        result = _d.solve_prose(str(claim))
    else:
        return {"error": "Provide one of: steps[], (mode + params [+ domain]), or claim (prose)."}
    if seal and isinstance(result, dict) and result.get("verdict") not in (None, "ERROR"):
        try:
            result.setdefault(
                "seal", _d.seal_receipt(result, claim if isinstance(claim, str) else None))
        except Exception as e:  # noqa: BLE001
            result["seal_error"] = str(e)[:200]
    return result


def verify_giving(spec):
    """Conservation of a giving / value-transfer chain -- every dollar accounted
    from the source to the end user (no leakage, no skim). See verifiers/giving.py."""
    return _r(_giving.verify(spec))


# ── Layer-0 source: PHOIBLE 2.0 + Glottolog (offline phoneme inventories) ──
_PHOIBLE_INDEX = None


def _load_phoible():
    global _PHOIBLE_INDEX
    if _PHOIBLE_INDEX is None:
        import json as _json
        from pathlib import Path as _Path
        p = (_Path(__file__).resolve().parents[3] / "lw" / "00_source" /
             "phoible" / "phoible_index.json")
        try:
            _PHOIBLE_INDEX = _json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            _PHOIBLE_INDEX = {"by_glottocode": {}, "name_index": {},
                              "meta": {"error": f"phoible index not provisioned: {exc}"}}
    return _PHOIBLE_INDEX


def language_data(query):
    """Phoneme inventory + language family + world region for a language, from the
    offline PHOIBLE 2.0 + Glottolog index (external Layer-0 source, attributed).
    Accepts a language name, ISO 639-3 code, or Glottocode."""
    idx = _load_phoible()
    by_gc = idx.get("by_glottocode") or {}
    if not by_gc:
        return {"status": "source_missing",
                "detail": idx.get("meta", {}).get("error", "PHOIBLE index not provisioned")}
    q = str(query or "").strip().lower()
    if not q:
        return {"status": "error", "detail": "provide a language name, ISO 639-3 code, or Glottocode"}
    ni = idx.get("name_index") or {}
    gc = ni.get(q)
    if not gc:
        hits = sorted(k for k in ni if k.startswith(q))
        if len(hits) == 1:
            gc = ni[hits[0]]
        else:
            sug = []
            for g in dict.fromkeys(ni[h] for h in hits[:10]):
                e = by_gc.get(g)
                if e:
                    sug.append(e.get("name"))
            return {"status": "not_found", "query": query,
                    "detail": f"no language matched '{query}'",
                    "suggestions": sug[:8], "source": idx.get("meta", {}).get("source")}
    e = by_gc.get(gc)
    if not e:
        return {"status": "not_found", "query": query, "detail": "matched id has no record"}
    out = {"status": "ok", "source": idx.get("meta", {}).get("source"),
           "license": idx.get("meta", {}).get("license")}
    out.update(e)
    return out


# ── Layer-0 source: Wikidata (CC0) -- live SPARQL lookup with an offline cache ──
_WD_CACHE = None
_WD_UA = ("NarrowHighway-Concordance/1.0 (https://narrowhighway.com; "
          "verification engine; conduit, not source)")


def _wd_cache_path():
    from pathlib import Path as _Path
    return _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "wikidata" / "cache.json"


def _wd_load_cache():
    global _WD_CACHE
    if _WD_CACHE is None:
        import json as _json
        try:
            _WD_CACHE = _json.loads(_wd_cache_path().read_text(encoding="utf-8"))
        except Exception:
            _WD_CACHE = {}
    return _WD_CACHE


def _wd_save_cache():
    import json as _json
    try:
        p = _wd_cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json.dumps(_WD_CACHE, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _wd_get(url):
    import json as _json
    import urllib.request as _u
    req = _u.Request(url, headers={"User-Agent": _WD_UA, "Accept": "application/json"})
    with _u.urlopen(req, timeout=15) as r:
        return _json.loads(r.read().decode("utf-8", "replace"))


def wikidata(query):
    """Look up an entity on Wikidata (CC0 public domain) by label and return key
    facts. Live SPARQL/API query, cached offline so common ones survive without a
    network. External Layer-0 -- attributed, crowd-sourced (CONCORDANT-grade, never
    a HOLDS); a starting reference to verify against the harder sources, not proof."""
    import urllib.parse as _up
    q = str(query or "").strip()
    if not q:
        return {"status": "error", "detail": "provide an entity label"}
    cache = _wd_load_cache()
    ck = q.lower()
    if ck in cache:
        out = dict(cache[ck]); out["cached"] = True
        return out
    try:
        # 1. resolve the label to a QID (forgiving search)
        s = _wd_get("https://www.wikidata.org/w/api.php?" + _up.urlencode({
            "action": "wbsearchentities", "search": q, "language": "en",
            "format": "json", "limit": 1}))
        hits = s.get("search") or []
        if not hits:
            return {"status": "not_found", "query": query,
                    "source": "Wikidata (CC0 public domain)"}
        qid = hits[0]["id"]
        label = hits[0].get("label", q)
        desc = hits[0].get("description", "")
        # 2. claims via the action API (avoids the rate-limited WDQS SPARQL endpoint)
        api = "https://www.wikidata.org/w/api.php?"
        ent = _wd_get(api + _up.urlencode({
            "action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"}))
        claims = (ent.get("entities", {}).get(qid, {}) or {}).get("claims", {}) or {}
        rows, idset = [], set()
        for pid, stmts in claims.items():
            for st in (stmts or [])[:2]:
                dv = (st.get("mainsnak", {}) or {}).get("datavalue", {}) or {}
                t, v = dv.get("type"), dv.get("value")
                if t == "wikibase-entityid" and isinstance(v, dict):
                    qv = v.get("id"); idset.add(qv); rows.append((pid, qv, True))
                elif t == "string":
                    rows.append((pid, str(v), False))
                elif t == "quantity" and isinstance(v, dict):
                    rows.append((pid, str(v.get("amount", "")).lstrip("+"), False))
                elif t == "time" and isinstance(v, dict):
                    rows.append((pid, str(v.get("time", "")).lstrip("+")[:10], False))
                elif t == "monolingualtext" and isinstance(v, dict):
                    rows.append((pid, v.get("text", ""), False))
            idset.add(pid)
        # 3. resolve property + item-value labels (batched, en)
        labels, ids = {}, [x for x in idset if x]
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            le = _wd_get(api + _up.urlencode({
                "action": "wbgetentities", "ids": "|".join(chunk),
                "props": "labels", "languages": "en", "format": "json"}))
            for k, vv in (le.get("entities", {}) or {}).items():
                lab = ((vv.get("labels", {}) or {}).get("en", {}) or {}).get("value")
                if lab:
                    labels[k] = lab
        _noise = ("commons category", "topic's main category", "image",
                  "locator map image", "logo image", "permanent duplicated item",
                  "category for", "category combines topics", "described at url")
        inst, facts, seen = [], [], set()
        for pid, val, is_item in rows:
            pl = labels.get(pid)
            vl = labels.get(val, val) if is_item else val
            if not pl or not vl:
                continue
            pll = pl.lower()
            if pl == "instance of":
                if vl not in inst:
                    inst.append(vl)
            elif pll.endswith(" id") or pll in _noise:
                continue  # drop external-identifier / category cruft
            elif (pl, vl) not in seen:
                seen.add((pl, vl))
                facts.append({"property": pl, "value": vl})
        out = {"status": "ok", "qid": qid, "label": label, "description": desc,
               "instance_of": inst[:6], "facts": facts[:18],
               "source": "Wikidata (CC0 public domain)",
               "url": "https://www.wikidata.org/wiki/" + qid}
        cache[ck] = out
        _wd_save_cache()
        return out
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "wikidata query failed: " + str(e)[:160]}


# ── Layer-0 source: Princeton WordNet 3.1 (offline lexical semantics, SQLite) ──
def word_meaning(word):
    """English lexical semantics from the offline WordNet 3.1 database (external
    Layer-0 source, attributed). word -> senses, each {pos, definition, synonyms,
    hypernyms (the is-a parents)}. Deepens the language tree's semantics level.
    Queried from a SQLite db (low memory); 147,478 lemmas, offline/ownable."""
    import json as _json
    import sqlite3 as _sql
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "wordnet" / "wordnet.db"
    if not p.exists():
        return {"status": "source_missing", "detail": "WordNet db not provisioned"}
    q = str(word or "").strip().lower()
    if not q:
        return {"status": "error", "detail": "provide a word"}
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        row = con.execute("SELECT data FROM senses WHERE lemma=?", (q,)).fetchone()
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "wordnet lookup failed: " + str(e)[:140]}
    if not row:
        return {"status": "not_found", "query": word,
                "source": meta.get("source", "Princeton WordNet 3.1")}
    return {"status": "ok", "word": q, "senses": _json.loads(row[0]),
            "source": meta.get("source"), "license": meta.get("license")}


_GEO_FEATURE = {
    "PPLC": "national capital", "PPLA": "first-order admin seat (e.g. state capital)",
    "PPLA2": "second-order admin seat", "PPLA3": "third-order admin seat",
    "PPLA4": "fourth-order admin seat", "PPLG": "seat of government",
    "PPL": "populated place", "PPLX": "section of populated place",
    "PPLL": "populated locality", "PPLS": "populated places", "STLMT": "settlement",
}


def place_lookup(name, limit=8):
    """Gazetteer lookup from the offline GeoNames cities5000 database (external
    Layer-0 source, attributed). name -> matching places, each {name, admin1,
    country, lat, lon, population, feature, timezone}, ordered by population so
    the most prominent match is first. Serves the local-community layer ("group
    you by your area") and basic geography. SQLite (low memory); 69,133 places
    with population >= 5000, offline/ownable. Data (c) GeoNames.org, CC-BY 4.0."""
    import sqlite3 as _sql
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "geonames" / "geonames.db"
    if not p.exists():
        return {"status": "source_missing", "detail": "GeoNames db not provisioned"}
    q = str(name or "").strip().lower()
    if not q:
        return {"status": "error", "detail": "provide a place name"}
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 8
    n = max(1, min(n, 25))
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        rows = con.execute(
            "SELECT name, ascii, lat, lon, cc, admin1, fcode, population, tz "
            "FROM places WHERE name_lc=? OR ascii_lc=? "
            "ORDER BY population DESC LIMIT ?", (q, q, n)).fetchall()
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        matches = []
        for r in rows:
            nm, asc, lat, lon, cc, a1, fcode, pop, tz = r
            cn = con.execute("SELECT name FROM countries WHERE cc=?", (cc,)).fetchone()
            an = con.execute("SELECT name FROM admin1 WHERE code=?",
                             (cc + "." + (a1 or ""),)).fetchone()
            matches.append({
                "name": asc or nm, "admin1": (an[0] if an else a1) or None,
                "country": cn[0] if cn else cc, "country_code": cc,
                "lat": lat, "lon": lon, "population": pop,
                "feature": _GEO_FEATURE.get(fcode, fcode), "feature_code": fcode,
                "timezone": tz})
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "geonames lookup failed: " + str(e)[:140]}
    if not matches:
        return {"status": "not_found", "query": name,
                "note": "GeoNames cities5000 covers populated places >= 5000; "
                        "smaller or historical places may be absent.",
                "source": meta.get("source", "GeoNames cities5000 gazetteer")}
    return {"status": "ok", "query": name, "count": len(matches),
            "matches": matches, "source": meta.get("source"),
            "license": meta.get("license"),
            "attribution": meta.get("attribution")}


def timezone_offset(zone, when=None):
    """UTC offset + daylight-saving state for an IANA time zone at an instant,
    from the offline IANA Time Zone Database (external Layer-0, attributed,
    PUBLIC DOMAIN). zone = an IANA name like "Asia/Tokyo" or "America/New_York"
    (use place_lookup to get a place's zone name). when = optional ISO date or
    datetime (default: now). Returns the offset, abbreviation, and whether DST is
    in effect -- the offset is a HISTORICAL/RULE fact, computed deterministically
    from the tzdb rules, not invented. Completes the calendar_time grounding;
    pairs with place_lookup (place -> zone) for "what time is it in X"."""
    import io as _io
    import json as _json
    import zipfile as _zip
    import zoneinfo as _zi
    import datetime as _dt
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "tzdata" / "tzdata.zip"
    if not p.exists():
        return {"status": "source_missing", "detail": "tzdata index not provisioned"}
    z = str(zone or "").strip()
    if not z:
        return {"status": "error", "detail": "provide an IANA zone name, e.g. Asia/Tokyo"}
    try:
        zf = _zip.ZipFile(str(p))
        meta = _json.loads(zf.read("meta.json"))
        if z not in zf.namelist():
            return {"status": "not_found", "query": zone,
                    "note": "not an IANA zone name; use place_lookup(name) to get "
                            "a place's zone (the 'timezone' field), then pass it here.",
                    "source": meta.get("source")}
        data = zf.read(z)
        if data[:4] != b"TZif":
            return {"status": "not_found", "query": zone,
                    "note": "that entry is not a zone (it is an auxiliary tzdb file)."}
        tz = _zi.ZoneInfo.from_file(_io.BytesIO(data), key=z)
        if when:
            try:
                moment = _dt.datetime.fromisoformat(str(when))
            except ValueError:
                return {"status": "error",
                        "detail": "could not parse 'when' as ISO 8601 (e.g. 2024-07-04 "
                                  "or 2024-07-04T13:30)"}
            moment = moment.replace(tzinfo=tz)
            when_str = str(when)
        else:
            moment = _dt.datetime.now(tz)
            when_str = moment.isoformat()
        off = moment.utcoffset()
        secs = int(off.total_seconds()) if off is not None else 0
        sign = "+" if secs >= 0 else "-"
        a = abs(secs)
        hhmm = "%s%02d:%02d" % (sign, a // 3600, (a % 3600) // 60)
        is_dst = bool(moment.dst())
        zf.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "tzdata lookup failed: " + str(e)[:140]}
    return {"status": "ok", "zone": z, "when": when_str,
            "utc_offset": hhmm, "offset_seconds": secs,
            "abbreviation": moment.tzname(), "is_dst": is_dst,
            "iana_version": meta.get("iana_version"),
            "source": meta.get("source"), "license": meta.get("license"),
            "attribution": meta.get("attribution")}


# --- UCUM unit converter (offline, deterministic, fails closed) -------------
_UCUM = {"doc": None, "memo": {}}
_UCUM_OFFSET = {"Cel", "[degF]", "[degR]"}


class _UcumUnsupported(Exception):
    pass


def _ucum_doc():
    if _UCUM["doc"] is None:
        import json as _json
        from pathlib import Path as _Path
        p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "ucum" / "ucum.json"
        if not p.exists():
            return None
        _UCUM["doc"] = _json.loads(p.read_text(encoding="utf-8"))
        _UCUM["memo"] = {}
    return _UCUM["doc"]


def _ucum_resolve_code(code):
    memo = _UCUM["memo"]
    if code in memo:
        return memo[code]
    units = _UCUM["doc"]["units"]
    if code not in units:
        raise _UcumUnsupported("unknown unit '%s'" % code)
    u = units[code]
    if u.get("base"):
        r = (1.0, {code: 1}); memo[code] = r; return r
    if u.get("special"):
        raise _UcumUnsupported("special/affine unit '%s'" % code)
    v = u.get("value"); expr = u.get("unit")
    if v is None or expr is None:
        raise _UcumUnsupported("unit '%s' has no definition" % code)
    m, d = _ucum_eval(expr)
    r = (v * m, d); memo[code] = r; return r


def _ucum_atom(sym):
    doc = _UCUM["doc"]; units = doc["units"]; pref = doc["prefixes"]
    if sym in units:
        return _ucum_resolve_code(sym)
    for plen in (2, 1):
        if len(sym) > plen and sym[:plen] in pref:
            rest = sym[plen:]
            if rest in units and units[rest].get("metric"):
                m, d = _ucum_resolve_code(rest)
                return (pref[sym[:plen]] * m, d)
    raise _UcumUnsupported("unresolved unit '%s'" % sym)


def _ucum_sym_exp(tok):
    import re as _re
    if tok.startswith("10*") or tok.startswith("10^"):
        rest = tok[3:]
        return tok[:3], (int(rest) if rest else 1)
    if "]" in tok:
        i = tok.rfind("]") + 1
        rest = tok[i:]
        return tok[:i], (int(rest) if rest else 1)
    mt = _re.search(r"([+-]?\d+)$", tok)
    if mt and mt.start() > 0:
        return tok[:mt.start()], int(mt.group(1))
    return tok, 1


def _ucum_term(tok):
    import re as _re
    if _re.match(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$", tok):
        return (float(tok), {})
    sym, exp = _ucum_sym_exp(tok)
    m, d = _ucum_atom(sym)
    if exp != 1:
        m = m ** exp
        d = {k: v * exp for k, v in d.items()}
    return (m, d)


def _ucum_eval(s):
    import re as _re
    s = _re.sub(r"\{[^}]*\}", "", s)
    toks = _re.split(r"([./])", s)
    if not toks or toks[0] == "":
        raise _UcumUnsupported("empty expression")
    mag, dim = _ucum_term(toks[0])
    dim = dict(dim)
    i = 1
    while i < len(toks):
        op = toks[i]
        m2, d2 = _ucum_term(toks[i + 1])
        i += 2
        if op == ".":
            mag *= m2
            for k, v in d2.items():
                dim[k] = dim.get(k, 0) + v
        else:
            mag /= m2
            for k, v in d2.items():
                dim[k] = dim.get(k, 0) - v
    return mag, {k: v for k, v in dim.items() if v != 0}


def _ucum_toK(v, u):
    return {"K": v, "Cel": v + 273.15, "[degF]": (v + 459.67) * 5.0 / 9.0,
            "[degR]": v * 5.0 / 9.0}[u]


def _ucum_fromK(k, u):
    return {"K": k, "Cel": k - 273.15, "[degF]": k * 9.0 / 5.0 - 459.67,
            "[degR]": k * 9.0 / 5.0}[u]


def _ucum_dimstr(dim, base_order):
    parts = []
    for b in base_order:
        e = dim.get(b)
        if e:
            parts.append(b if e == 1 else "%s%d" % (b, e))
    return ".".join(parts) if parts else "1"


def unit_convert(value, from_unit, to_unit=None):
    """Deterministic unit conversion via the offline UCUM table (external Layer-0,
    attributed, royalty-free). Resolves UCUM unit codes/expressions to their base
    dimension + magnitude and converts. from_unit, to_unit accept UCUM codes like
    'km', 'm/s', 'kg.m/s2', '[mi_i]', 'Cel'. If to_unit is omitted, returns the
    value in canonical base units. Affine temperatures (Cel, [degF], [degR], K)
    handled with offsets. Incommensurable units are REPORTED, not forced. The
    converter FAILS CLOSED -- an unparseable/non-linear unit returns 'unsupported'
    rather than a guess (a wrong conversion is worse than none). This is the units
    substrate under every dimensional check."""
    doc = _ucum_doc()
    if doc is None:
        return {"status": "source_missing", "detail": "UCUM index not provisioned"}
    try:
        val = float(value)
    except (TypeError, ValueError):
        return {"status": "error", "detail": "value must be numeric"}
    frm = str(from_unit or "").strip()
    if not frm:
        return {"status": "error", "detail": "provide from_unit (a UCUM code, e.g. km)"}
    to = str(to_unit).strip() if to_unit not in (None, "") else None
    meta = doc["meta"]
    base_order = doc["base_units"]
    src = {"source": meta.get("source"), "license": meta.get("license"),
           "ucum_version": meta.get("version"),
           "attribution": meta.get("attribution")}
    try:
        if to is None:
            mf, df = _ucum_eval(frm)
            out = {"status": "ok", "value": val, "from": frm,
                   "canonical_value": val * mf,
                   "canonical_units": _ucum_dimstr(df, base_order)}
            out.update(src)
            return out
        if frm in _UCUM_OFFSET or to in _UCUM_OFFSET:
            allow = _UCUM_OFFSET | {"K"}
            if frm not in allow or to not in allow:
                out = {"status": "unsupported",
                       "detail": "affine temperature converts only among "
                                 "K, Cel, [degF], [degR]"}
                out.update(src)
                return out
            res = _ucum_fromK(_ucum_toK(val, frm), to)
            out = {"status": "ok", "value": val, "from": frm, "to": to,
                   "result": res,
                   "note": "affine (offset) temperature conversion"}
            out.update(src)
            return out
        mf, df = _ucum_eval(frm)
        mt, dt = _ucum_eval(to)
        if df != dt:
            out = {"status": "incommensurable",
                   "detail": "units are not dimensionally compatible",
                   "from": frm, "from_dimension": _ucum_dimstr(df, base_order),
                   "to": to, "to_dimension": _ucum_dimstr(dt, base_order)}
            out.update(src)
            return out
        out = {"status": "ok", "value": val, "from": frm, "to": to,
               "result": val * mf / mt,
               "dimension": _ucum_dimstr(df, base_order)}
        out.update(src)
        return out
    except _UcumUnsupported as e:
        out = {"status": "unsupported", "detail": str(e),
               "note": "UCUM code unrecognized or not linearly convertible; the "
                       "converter fails closed rather than guess."}
        out.update(src)
        return out
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "ucum convert failed: " + str(e)[:140]}


def _oeis_norm_anum(s):
    s = str(s or "").strip().upper().lstrip("A").lstrip("0") or "0"
    try:
        return "A%06d" % int(s)
    except (TypeError, ValueError):
        return None


def sequence_lookup(anum=None, terms=None, limit=8):
    """Identify or look up an integer sequence in the offline OEIS index (external
    Layer-0, attributed, CC BY-SA). Either: anum (e.g. 'A000045' or 45) -> the
    sequence's name + terms; or terms (a list like [1,1,2,3,5,8] or a comma
    string) -> the OEIS sequences whose terms contain that run, most-canonical
    (lowest A-number) first. OEIS is a curated/crowd-sourced reference: a term
    match IDENTIFIES a sequence (CONCORDANT-grade), it does not PROVE the defining
    property. Grounds number_theory / combinatorics sequence claims."""
    import sqlite3 as _sql
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "oeis" / "oeis.db"
    if not p.exists():
        return {"status": "source_missing", "detail": "OEIS db not provisioned"}
    try:
        lim = max(1, min(int(limit), 25))
    except (TypeError, ValueError):
        lim = 8
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        src = {"source": meta.get("source"), "license": meta.get("license"),
               "attribution": meta.get("attribution"), "grade": meta.get("grade")}
        if anum not in (None, ""):
            a = _oeis_norm_anum(anum)
            if a is None:
                con.close()
                return {"status": "error", "detail": "bad A-number: %r" % anum}
            row = con.execute("SELECT anum,name,terms FROM sequences WHERE anum=?",
                              (a,)).fetchone()
            con.close()
            if not row:
                out = {"status": "not_found", "query": a}
                out.update(src)
                return out
            tlist = [t for t in row[2].split(",") if t != ""]
            out = {"status": "ok", "anum": row[0], "name": row[1],
                   "terms": tlist[:24], "terms_shown": min(24, len(tlist))}
            out.update(src)
            return out
        # identify by terms
        if terms in (None, ""):
            con.close()
            return {"status": "error",
                    "detail": "provide 'anum' (e.g. A000045) or 'terms' "
                              "(e.g. [1,1,2,3,5,8])"}
        if isinstance(terms, str):
            raw = [t for t in terms.replace(" ", ",").split(",") if t != ""]
        else:
            raw = list(terms)
        try:
            ints = [str(int(t)) for t in raw]
        except (TypeError, ValueError):
            con.close()
            return {"status": "error", "detail": "all terms must be integers"}
        if len(ints) < 3:
            con.close()
            return {"status": "error",
                    "detail": "give at least 3 terms to identify a sequence "
                              "(fewer is ambiguous)"}
        needle = "," + ",".join(ints) + ","
        rows = con.execute(
            "SELECT anum,name FROM sequences WHERE terms LIKE ? ESCAPE '\\' "
            "ORDER BY anum LIMIT ?",
            ("%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", lim + 1)
        ).fetchall()
        con.close()
        more = len(rows) > lim
        matches = [{"anum": r[0], "name": r[1]} for r in rows[:lim]]
        if not matches:
            out = {"status": "not_found", "query_terms": ints,
                   "note": "no OEIS sequence contains that exact run of terms."}
            out.update(src)
            return out
        out = {"status": "ok", "query_terms": ints, "count": len(matches),
               "more_matches": more, "matches": matches,
               "note": "term match identifies a sequence; it is a reference "
                       "pointer, not a proof of the defining property."}
        out.update(src)
        return out
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "oeis lookup failed: " + str(e)[:140]}


# ARPABET -> IPA (segmental). \\u escapes keep this source pure-ASCII.
_CMU_ARPA_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ",
    "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɝ",
    "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f",
    "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ",
    "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
_CMU_VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY",
               "IH", "IY", "OW", "OY", "UH", "UW"}


def _cmu_analyze(phones):
    toks = phones.split()
    stress = []
    ipa = []
    ok = True
    for ph in toks:
        base, st = ph, None
        if ph and ph[-1] in "012":
            base, st = ph[:-1], ph[-1]
        if base in _CMU_VOWELS:
            stress.append(st or "0")
        if base == "AH" and st == "0":
            ipa.append("ə")        # schwa
        elif base == "ER" and st == "0":
            ipa.append("ɚ")        # r-colored schwa
        elif base in _CMU_ARPA_IPA:
            ipa.append(_CMU_ARPA_IPA[base])
        else:
            ok = False
    return {"arpabet": phones, "syllable_count": len(stress),
            "stress_pattern": "-".join(stress),
            "ipa": ("".join(ipa) if ok else None)}


def word_pronunciation(word):
    """Pronunciation of an English word from the offline CMU Pronouncing
    Dictionary (external Layer-0, attributed, BSD-2). word -> each pronunciation
    variant as {arpabet, ipa, syllable_count, stress_pattern}. ARPABET is CMU's
    authoritative transcription; IPA is a deterministic segmental transliteration
    (no syllable-boundary stress marks); stress_pattern lists the vowel stresses
    (1 primary, 2 secondary, 0 none). The PHONICS level of the language tree --
    pairs with language_data (phoneme inventories), word_meaning (semantics), and
    word_study (original-language morphology). ~126k words, queried offline."""
    import sqlite3 as _sql
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "cmudict" / "cmudict.db"
    if not p.exists():
        return {"status": "source_missing", "detail": "cmudict db not provisioned"}
    q = str(word or "").strip().lower()
    if not q:
        return {"status": "error", "detail": "provide a word"}
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        rows = con.execute(
            "SELECT variant, arpabet FROM pron WHERE word=? ORDER BY variant",
            (q,)).fetchall()
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "cmudict lookup failed: " + str(e)[:140]}
    if not rows:
        return {"status": "not_found", "query": word,
                "note": "not in the CMU dictionary (proper nouns, rare or "
                        "non-English words may be absent).",
                "source": meta.get("source")}
    prons = []
    for var, ar in rows:
        a = _cmu_analyze(ar)
        a["variant"] = var
        prons.append(a)
    return {"status": "ok", "word": q, "pronunciations": prons,
            "scheme": meta.get("scheme"), "source": meta.get("source"),
            "license": meta.get("license"),
            "attribution": meta.get("attribution")}


def _protocols_db():
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[3] / "lw" / "00_source" / "protocols" / "protocols.db"
    return p if p.exists() else None


def port_lookup(query, protocol=None):
    """Look up an internet port or service in the offline IANA port registry
    (external Layer-0, attributed, public domain). query = a port NUMBER (e.g.
    443 -> the services on it, like https) OR a service NAME (e.g. 'ssh' -> its
    port 22). Optional protocol filters to tcp/udp/sctp/dccp. The authoritative
    'what runs on port N' / 'what port does X use' for the networking verifier."""
    import sqlite3 as _sql
    p = _protocols_db()
    if p is None:
        return {"status": "source_missing", "detail": "protocols db not provisioned"}
    q = str(query if query is not None else "").strip()
    if not q:
        return {"status": "error", "detail": "provide a port number or service name"}
    proto = str(protocol).strip().lower() if protocol else None
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        if q.isdigit():
            sql = ("SELECT port,protocol,service,description,reference FROM ports "
                   "WHERE port=?")
            args = [int(q)]
            if proto:
                sql += " AND protocol=?"
                args.append(proto)
            rows = con.execute(sql + " ORDER BY protocol,service", args).fetchall()
            mode = "by_port"
        else:
            sql = ("SELECT port,protocol,service,description,reference FROM ports "
                   "WHERE service=?")
            args = [q.lower()]
            if proto:
                sql += " AND protocol=?"
                args.append(proto)
            rows = con.execute(sql + " ORDER BY port,protocol", args).fetchall()
            mode = "by_service"
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "port lookup failed: " + str(e)[:140]}
    if not rows:
        return {"status": "not_found", "query": query,
                "source": meta.get("ports_source")}
    matches = [{"port": r[0], "protocol": r[1], "service": r[2],
                "description": r[3], "reference": r[4]} for r in rows]
    return {"status": "ok", "query": query, "mode": mode,
            "count": len(matches), "matches": matches,
            "source": meta.get("ports_source"),
            "license": meta.get("ports_license"),
            "attribution": meta.get("attribution")}


def rfc_lookup(number):
    """Look up an RFC in the offline RFC Index (external Layer-0, attributed,
    public domain). number = an RFC number (9113, 'RFC9113', 'rfc 9113') ->
    {doc_id, title, status, date, obsoletes, obsoleted_by, updates, updated_by,
    url}. If the RFC has been obsoleted, 'superseded_by' is set prominently so a
    dead RFC is never cited as current (e.g. RFC 7540 -> superseded by RFC 9113).
    The authoritative 'which RFC defines X' for networking / cryptography."""
    import sqlite3 as _sql
    p = _protocols_db()
    if p is None:
        return {"status": "source_missing", "detail": "protocols db not provisioned"}
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if not digits:
        return {"status": "error", "detail": "provide an RFC number, e.g. 9113"}
    num = int(digits)
    try:
        con = _sql.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
        row = con.execute(
            "SELECT doc_id,title,status,date,obsoletes,obsoleted_by,updates,"
            "updated_by FROM rfcs WHERE num=?", (num,)).fetchone()
        meta = dict(con.execute("SELECT k,v FROM meta").fetchall())
        con.close()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": "rfc lookup failed: " + str(e)[:140]}
    if not row:
        return {"status": "not_found", "query": number,
                "source": meta.get("rfc_source")}

    def _split(s):
        return [x for x in (s or "").split(",") if x]

    obs_by = _split(row[5])
    out = {"status": "ok", "doc_id": row[0], "number": num, "title": row[1],
           "current_status": row[2], "date": row[3],
           "obsoletes": _split(row[4]), "obsoleted_by": obs_by,
           "updates": _split(row[6]), "updated_by": _split(row[7]),
           "url": "https://www.rfc-editor.org/rfc/rfc%d" % num,
           "source": meta.get("rfc_source"), "license": meta.get("rfc_license"),
           "attribution": meta.get("attribution")}
    if obs_by:
        out["superseded_by"] = obs_by
        out["note"] = ("THIS RFC IS OBSOLETE -- superseded by " + ", ".join(obs_by)
                       + "; cite the newer RFC as current.")
    return out


def verify_statistics_pvalue(spec):
    return _r(statistics.verify_pvalue_calibration(spec))


def verify_statistics_multiple_comparisons(raw_p_values, method, alpha=0.05,
                                            claimed_rejected_indices=None):
    spec = {"raw_p_values": raw_p_values, "method": method, "alpha": alpha}
    if claimed_rejected_indices is not None:
        spec["claimed_rejected_indices"] = claimed_rejected_indices
    return _r(statistics.verify_multiple_comparisons(spec))


def verify_statistics_confidence_interval(estimate, ci_low, ci_high, *, spec=None):
    if spec:
        full = dict(spec)
        full.setdefault("estimate", estimate)
        full.setdefault("ci_low", ci_low)
        full.setdefault("ci_high", ci_high)
        return _r(statistics.verify_confidence_interval(full))
    return _r(statistics.verify_confidence_interval({
        "estimate": estimate, "ci_low": ci_low, "ci_high": ci_high,
    }))


def verify_computer_science(code, function_name=None, test_cases=None,
                             input_generator=None, claimed_class=None,
                             sizes=None, tolerance=0.40, *,
                             determinism_trials=None, claimed_space_class=None):
    out = {"static_termination": _r(computer_science.verify_static_termination(code))}
    if function_name and test_cases:
        out["functional_correctness"] = _r(computer_science.verify_functional_correctness({
            "code": code, "function_name": function_name, "test_cases": test_cases,
        }))
    if function_name and input_generator and claimed_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator, "claimed_class": claimed_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["runtime_complexity"] = _r(computer_science.verify_runtime_complexity(spec))
    if function_name and input_generator and claimed_space_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator,
                "claimed_space_class": claimed_space_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["space_complexity"] = _r(computer_science.verify_space_complexity(spec))
    if function_name and test_cases and determinism_trials and determinism_trials >= 2:
        out["determinism"] = _r(computer_science.verify_determinism({
            "code": code, "function_name": function_name,
            "test_cases": test_cases, "trials": determinism_trials,
        }))
    return out


def verify_biology(n_replicates=None, min_replicates=3, assay_classes=None,
                    min_assay_classes=2, dose_response=None, power_analysis=None,
                    *, bio_control=None, hardy_weinberg=None, primer=None,
                    molarity=None, mendelian=None):
    spec = {}
    if n_replicates is not None:
        spec["n_replicates"] = n_replicates
        spec["min_replicates"] = min_replicates
    if assay_classes is not None:
        spec["assay_classes"] = assay_classes
        spec["min_assay_classes"] = min_assay_classes
    if dose_response is not None:
        spec["dose_response"] = dose_response
    if power_analysis is not None:
        spec["power_analysis"] = power_analysis
    if hardy_weinberg is not None:
        spec["hardy_weinberg"] = hardy_weinberg
    if primer is not None:
        spec["primer"] = primer
    if molarity is not None:
        spec["molarity"] = molarity
    if mendelian is not None:
        spec["mendelian"] = mendelian
    packet = {"BIO_VERIFY": spec}
    if bio_control is not None:
        packet["BIO_CONTROL"] = bio_control
    results = biology.run(packet)
    return {"checks": [_r(r) for r in results]}


def verify_governance_decision_packet(decision_packet, witness_count=None, *, domain=None):
    out = {"shape": _r(governance.verify_decision_packet_shape(decision_packet))}
    if witness_count is not None:
        out["witness_consistency"] = _r(
            governance.verify_witness_count_consistency(
                decision_packet, {"witness_count": witness_count}))
    if domain:
        out["domain_profile"] = _r(governance.verify_domain_profile(domain, decision_packet))
    return out


def verify_energy(spec):
    """Run all applicable energy-system checks against the supplied spec.

    Spec is the contents of the ENERGY_VERIFY field — see
    `concordance_engine.verifiers.energy` docstring for the full
    field reference. Each check fires when its inputs are present;
    unsupplied checks return NOT_APPLICABLE.

    Off-grid system sizing, wire voltage drop, battery sizing,
    solar daily yield, peak-load-vs-inverter, runtime, kWh↔Wh,
    efficiency (with heat-pump COP carve-out), power balance.
    """
    packet = {"ENERGY_VERIFY": spec or {}}
    results = _energy.run(packet)
    return {"checks": [_r(r) for r in results]}


def verify_acoustics(spec):
    """Wave speed/frequency/wavelength, decibel ratios, Doppler shift, harmonic frequencies."""
    return {"checks": [_r(r) for r in _acoustics.run({"ACOUS_VERIFY": spec or {}})]}


def verify_agriculture(spec):
    """Hardiness zones, soil pH range, crop rotation rules, livestock stocking density."""
    return {"checks": [_r(r) for r in _agriculture.run({"AG_VERIFY": spec or {}})]}


def verify_astronomy(spec):
    """Kepler's third law, gravitational force, stellar parallax distance, distance modulus."""
    return {"checks": [_r(r) for r in _astronomy.run({"ASTRO_VERIFY": spec or {}})]}


def verify_calendar_time(spec):
    """Leap-year rule, ISO 8601 validity, day-of-week computation, duration addition."""
    return {"checks": [_r(r) for r in _calendar_time.run({"CAL_VERIFY": spec or {}})]}


def verify_combinatorics(spec):
    """Permutations, combinations, derangements, multinomial coefficients."""
    return {"checks": [_r(r) for r in _combinatorics.run({"COMB_VERIFY": spec or {}})]}


def verify_cryptography(spec):
    """Hash match, hash strength, HMAC, encoding roundtrip, key strength.
    Hash match:   {"hash_algorithm": "sha256", "data": "hello", "claimed_hash_hex": "2cf24dba..."}
    Hash strength:{"hash_strength_algorithm": "md5", "claimed_hash_strength": "broken"}
    HMAC:         {"hmac_algorithm": "sha256", "hmac_key": "secret", "hmac_data": "hello", "claimed_hmac_hex": "..."}
    Encoding:     {"encoded": "aGVsbG8=", "encoded_form": "base64", "claimed_decoded": "hello"}
    Key strength: {"cipher": "AES", "key_bits": 256, "claimed_key_strength": "strong"}"""
    return {"checks": [_r(r) for r in _cryptography.run({"CRYPTO_VERIFY": spec or {}})]}


def verify_document_validation(spec):
    """ISBN-13 check-digit validation and Luhn algorithm for credit card numbers.
    ISBN-13: {"isbn13": "9780306406157", "claimed_isbn13_valid": true}
    Luhn:    {"luhn_number": "4532015112830366", "claimed_luhn_valid": true}"""
    return {"checks": [_r(r) for r in _document_validation.run({"DOC_VERIFY": spec or {}})]}


def verify_electrical(spec):
    """Ohm's law, power equations, Kirchhoff voltage loop, RC time constant."""
    return {"checks": [_r(r) for r in _electrical.run({"ELEC_VERIFY": spec or {}})]}


def verify_exercise_science(spec):
    """Energy expenditure, heart rate formulas, MET lookup.
    Energy: {"claimed_met": 8.0, "weight_kg": 70, "duration_hours": 1.0, "claimed_kcal": 560}
    Max HR (Tanaka): {"age_years": 30, "claimed_max_hr": 187}
    HR zone (Karvonen): {"age_years": 30, "resting_hr": 60, "intensity_low": 0.7, "intensity_high": 0.8,
                         "claimed_zone_low_bpm": 149, "claimed_zone_high_bpm": 162}"""
    return {"checks": [_r(r) for r in _exercise_science.run({"EX_VERIFY": spec or {}})]}


def verify_finance(spec):
    """Accounting identity (A=L+E), compound interest, NPV, present value."""
    return {"checks": [_r(r) for r in _finance.run({"FIN_VERIFY": spec or {}})]}


def verify_formal_logic(spec):
    """Satisfiability, tautology, contradiction, entailment, logical equivalence (propositional)."""
    return {"checks": [_r(r) for r in _formal_logic.run({"LOGIC_VERIFY": spec or {}})]}


def verify_genetics(spec):
    """DNA/RNA complementarity, reverse complement, GC content, codon translation, ORF bounds."""
    return {"checks": [_r(r) for r in _genetics.run({"GENETICS_VERIFY": spec or {}})]}


def verify_geography(spec):
    """Lat/lon validity, Haversine distance, initial bearing, UTM zone assignment."""
    return {"checks": [_r(r) for r in _geography.run({"GEO_LOC_VERIFY": spec or {}})]}


def verify_geology(spec):
    """Radiometric decay dating, Mohs hardness scratch test, Richter amplitude ratio."""
    return {"checks": [_r(r) for r in _geology.run({"GEO_VERIFY": spec or {}})]}


def verify_geometry(spec):
    """Areas, volumes, perimeters, Pythagorean theorem, circle/sphere relationships."""
    return {"checks": [_r(r) for r in _geometry.run({"GEOM_VERIFY": spec or {}})]}


def verify_hydrology(spec):
    """Manning's equation, Darcy's law, unit hydrograph, flow-rate/velocity/area."""
    return {"checks": [_r(r) for r in _hydrology.run({"HYD_VERIFY": spec or {}})]}


def verify_information_theory(spec):
    """Shannon entropy, channel capacity, mutual information, Huffman code length bounds."""
    return {"checks": [_r(r) for r in _information_theory.run({"INFO_VERIFY": spec or {}})]}


def verify_linguistics(spec):
    """Strong's resolution, occurrence count, transliteration, gloss consistency, cognate pairs."""
    return {"checks": [_r(r) for r in _linguistics.run({"LING_VERIFY": spec or {}})]}


def verify_manufacturing(spec):
    """Tolerance stack-up, GD&T fits, surface roughness, process capability (Cp/Cpk)."""
    return {"checks": [_r(r) for r in _manufacturing.run({"MFG_VERIFY": spec or {}})]}


def verify_meteorology(spec):
    """Dew point, relative humidity, pressure altitude, wind chill, heat index."""
    return {"checks": [_r(r) for r in _meteorology.run({"MET_VERIFY": spec or {}})]}


def verify_music_theory(spec):
    """Interval semitone counts, chord quality (major/minor/dom7), frequency ratios."""
    return {"checks": [_r(r) for r in _music_theory.run({"MUS_VERIFY": spec or {}})]}


def verify_networking(spec):
    """Subnet masks, CIDR notation, IP address validity, broadcast/network address."""
    return {"checks": [_r(r) for r in _networking.run({"NET_VERIFY": spec or {}})]}


def verify_number_theory(spec):
    """Primality, GCD, LCM, modular arithmetic, Fibonacci membership, divisibility."""
    return {"checks": [_r(r) for r in _number_theory.run({"NUM_VERIFY": spec or {}})]}


def verify_nutrition(spec):
    """Macronutrient caloric values, BMR (Mifflin-St Jeor), TDEE, nutrient density."""
    return {"checks": [_r(r) for r in _nutrition.run({"NUT_VERIFY": spec or {}})]}


def verify_optics(spec):
    """Snell's law, thin-lens equation, diffraction grating, angular resolution."""
    return {"checks": [_r(r) for r in _optics.run({"OPT_VERIFY": spec or {}})]}


def verify_photography(spec):
    """Exposure triangle (aperture/shutter/ISO), EV calculation, depth-of-field."""
    return {"checks": [_r(r) for r in _photography.run({"PHOTO_VERIFY": spec or {}})]}


def verify_sports_analytics(spec):
    """Batting average, ERA, passer rating, Pythagorean win expectation, Elo rating."""
    return {"checks": [_r(r) for r in _sports_analytics.run({"SPORT_VERIFY": spec or {}})]}


def verify_witness(spec):
    """Gate-chain completeness, reasoning trace presence, anchor resolution, no-fabricated-answer check."""
    return {"checks": [_r(r) for r in _witness.run({"WIT_VERIFY": spec or {}})]}


def verify_physical_constants(spec):
    """CODATA 2018 fundamental constants: c, h, k_B, N_A, R, G, m_e, m_p, m_n, epsilon_0, mu_0, alpha, Rydberg, Bohr radius, Stefan-Boltzmann, Avogadro, Faraday, atmosphere, standard gravity. Public domain (NIST)."""
    return {"checks": [_r(r) for r in _physical_constants.run({"CONST_VERIFY": spec or {}})]}


def verify_periodic_table(spec):
    """IUPAC 2021 periodic table: symbol/name/atomic_number/atomic_mass cross-validation for all 118 elements. Public domain."""
    return {"checks": [_r(r) for r in _periodic_table.run({"PT_VERIFY": spec or {}})]}


def verify_atomic(spec):
    """Atomic structure: quantum-number validity (n,l,m_l,m_s), shell capacity (2n²), and ground-state electron configuration for Z=1-118 (Madelung order + the standard ground-state exceptions). The electron layer beneath chemistry, quantum, and the periodic table."""
    return {"checks": [_r(r) for r in _atomic.run({"ATOM_VERIFY": spec or {}})]}


def verify_molecular_geometry(spec):
    """VSEPR molecular geometry: bonding domains + lone pairs -> predicted shape and ideal bond angle (tetrahedral 109.47°, trigonal 120°, linear 180°, octahedral 90°). The atom's spatial face; co-confirms geometry on the symmetry axis."""
    return {"checks": [_r(r) for r in _molecular_geometry.run({"VSEPR_VERIFY": spec or {}})]}


def verify_ephemeris(spec):
    """Computational astronomy: Julian day, moon phase, equinox/solstice dates, sunrise/sunset by lat/lon. Algorithms from Meeus (public domain). Low-precision (±1 day for equinox, ±30 min for sunrise)."""
    return {"checks": [_r(r) for r in _ephemeris.run({"EPH_VERIFY": spec or {}})]}


def verify_layer_zero_grounding(spec):
    """Surface the WEB Bible (Layer 0) passages that anchor a Scripture-citing claim. Engine returns the actual text of cited verses; it does NOT interpret. CONFIRMED when one or more cited references resolve to real WEB passages; MISMATCH when any cited reference cannot be resolved (catches fabricated citations like 'Hezekiah 4:21'). Layer 0 is taken on faith; this verifier only surfaces."""
    return {"checks": [_r(r) for r in _layer_zero_grounding.run({"LAYER0_VERIFY": spec or {}})]}


def verify_linear_algebra(spec):
    """Vector and matrix operations computed via NumPy. Verifies claims about dot/cross products, vector magnitude, vector angle, matrix addition, matrix multiplication, determinant, trace, eigenvalues, matrix inverse (A·A⁻¹=I), and linear-system solutions (Ax=b). Pure math, no authority lookups — every CONFIRMED reproduces by hand."""
    return {"checks": [_r(r) for r in _linear_algebra.run({"LIN_VERIFY": spec or {}})]}


def verify_probability(spec):
    """Probability and distribution claims. Verifies discrete expected value and variance, binomial probability and mean, normal CDF (via erf) and the 68-95-99.7 rule, Poisson probability, Bayes' theorem, conditional probability, and independence checks. All math is stdlib + erf — no authority lookups."""
    return {"checks": [_r(r) for r in _probability.run({"PROB_VERIFY": spec or {}})]}


def verify_quantum_computing(spec):
    """Qubit normalization, Grover iterations, Shor period, BB84 QKD security, von Neumann entropy, fidelity.
    Normalization: {"amplitudes": [0.6, 0.8], "claimed_normalized": true}
    Grover: {"n_items": 64, "claimed_grover_iterations": 6}
    Shor period: {"shor_a": 2, "shor_N": 15, "shor_r": 4, "claimed_period_valid": true}
    BB84: {"qber": 0.09, "claimed_secure": true}
    vN entropy: {"density_eigenvalues": [0.5, 0.5], "claimed_entropy_bits": 1.0}"""
    return {"checks": [_r(r) for r in _quantum_computing.run({"QCOMP_VERIFY": spec or {}})]}


def verify_medicine(spec):
    """BMI, drug dosage, blood pressure (AHA 2017), A1C→eAG, eGFR Cockcroft-Gault, IBW Devine, MAP.
    BMI: {"weight_kg": 70, "height_m": 1.75, "claimed_bmi": 22.86, "claimed_bmi_class": "normal"}
    Dosage: {"dose_mg_per_kg": 5, "weight_kg": 70, "claimed_dose_mg": 350}
    BP: {"systolic": 125, "diastolic": 82, "claimed_bp_class": "hypertension_stage_1"}
    A1C: {"a1c_pct": 7.0, "claimed_eag_mg_dl": 154.1}
    eGFR: {"age_years": 45, "weight_kg": 70, "serum_creatinine": 1.1, "sex": "male", "claimed_egfr": 75.0}
    IBW: {"height_in": 70, "sex_ibw": "male", "claimed_ibw_kg": 75.5}
    MAP: {"systolic": 120, "diastolic": 80, "claimed_map_mmhg": 93.3}"""
    return {"checks": [_r(r) for r in _medicine.run({"MED_VERIFY": spec or {}})]}


def verify_cybersecurity(spec):
    """Password entropy, TLS version status, CVSS severity, subnet host count, port classification.
    Entropy: {"password_length": 16, "charset_size": 94, "claimed_entropy_bits": 104.9}
    TLS: {"tls_version": "1.3", "claimed_tls_status": "recommended"}
    CVSS: {"cvss_base_score": 9.1, "claimed_cvss_severity": "critical"}
    Subnet: {"cidr_prefix": 24, "claimed_host_count": 254}
    Port: {"port_number": 443, "claimed_port_class": "well_known"}"""
    return {"checks": [_r(r) for r in _cybersecurity.run({"CYBER_VERIFY": spec or {}})]}


def verify_economics(spec):
    """Simple/compound interest, PV/FV, Rule of 72, inflation adjustment, GDP per capita, price elasticity.
    Simple interest: {"principal": 1000, "rate": 0.05, "time_years": 3, "claimed_simple_interest": 150}
    Compound: {"principal": 1000, "rate": 0.05, "time_years": 3, "compounding_periods": 12, "claimed_compound_amount": 1161.62}
    Rule of 72: {"rate_percent": 7, "claimed_doubling_years": 10.3}
    Inflation: {"nominal_value": 1000, "inflation_rate": 0.03, "years": 10, "claimed_real_value": 744.09}"""
    return {"checks": [_r(r) for r in _economics.run({"ECON_VERIFY": spec or {}})]}


def verify_labor(spec):
    """Gross pay, FLSA overtime, annual-to-hourly, take-home pay, minimum wage compliance.
    Gross (≤40h): {"hourly_rate": 18.5, "hours_worked": 40, "claimed_gross_pay": 740.0}
    FLSA overtime (>40h): {"hourly_rate": 18.5, "regular_hours": 40, "overtime_hours": 5, "claimed_overtime_pay": 878.75}
    Take-home: {"gross_pay": 1000, "total_tax_rate": 0.28, "claimed_take_home": 720}
    Annual/hourly: {"annual_salary": 52000, "claimed_hourly_equivalent": 25.0}"""
    return {"checks": [_r(r) for r in _labor.run({"LABOR_VERIFY": spec or {}})]}


def verify_real_estate(spec):
    """Monthly mortgage payment, cap rate, GRM, LTV, DSCR, rental yield.
    Mortgage: {"loan_principal": 300000, "annual_rate": 0.065, "loan_term_months": 360, "claimed_monthly_payment": 1896.20}
    Cap rate: {"net_operating_income": 24000, "property_value": 400000, "claimed_cap_rate": 0.06}
    LTV: {"loan_amount": 240000, "appraised_value": 300000, "claimed_ltv": 0.80}
    DSCR: {"net_operating_income": 24000, "annual_debt_service": 22755, "claimed_dscr": 1.055}"""
    return {"checks": [_r(r) for r in _real_estate.run({"RE_VERIFY": spec or {}})]}


def verify_construction(spec):
    """Concrete volume, area (rect/circle), rebar weight, wall area, paint cans, floor tiles, beam load.
    Concrete: {"length_m": 10, "width_m": 5, "depth_m": 0.15, "claimed_concrete_m3": 7.5}
    Tiles: {"tile_area_m2": 50, "tile_size_m2": 0.25, "waste_factor": 0.10, "claimed_tile_count": 220}
    Beam: {"total_load_kn": 120, "span_m": 6, "claimed_load_intensity_kn_per_m": 20.0}"""
    return {"checks": [_r(r) for r in _construction.run({"CONSTR_VERIFY": spec or {}})]}


def verify_soil_science(spec):
    """Soil pH suitability, NPK fertilizer requirements, irrigation ETc, lime requirement, texture classification.
    pH: {"crop": "maize", "soil_ph": 6.2, "claimed_ph_suitable": true}
    NPK: {"crop_npk": "wheat", "area_hectares": 2.0, "claimed_n_kg": 240, "claimed_p_kg": 120, "claimed_k_kg": 120}
    Irrigation: {"reference_et0_mm_per_day": 5.0, "crop_coefficient": 1.15, "claimed_etc_mm_per_day": 5.75}
    Texture: {"sand_pct": 40, "silt_pct": 40, "clay_pct": 20, "claimed_texture_class": "loam"}"""
    return {"checks": [_r(r) for r in _soil_science.run({"SOIL_VERIFY": spec or {}})]}


def verify_thermodynamics(spec):
    """Carnot efficiency, ideal gas law (PV=nRT), specific heat (Q=mcΔT), entropy change (ΔS=Q/T).
    Carnot: {"T_hot_K": 600, "T_cold_K": 300, "claimed_efficiency": 0.5}
    Ideal gas: {"pressure_Pa": 101325, "volume_m3": 0.0224, "moles": 1.0, "claimed_temperature_K": 273.15}
    Specific heat: {"mass_kg": 1.0, "specific_heat_J_per_kgK": 4186, "delta_T_K": 10, "claimed_heat_J": 41860}
    Entropy: {"heat_J": 1000, "temperature_K": 500, "claimed_entropy_change_J_per_K": 2.0}"""
    return {"checks": [_r(r) for r in _thermodynamics.run({"THERMO_VERIFY": spec or {}})]}


def verify_nuclear_physics(spec):
    """Radioactive decay, binding energy per nucleon, half-life from activity, decay constant.
    Decay: {"half_life_seconds": 3600, "elapsed_seconds": 7200, "initial_count": 1e9, "claimed_remaining_count": 2.5e8}
    Binding energy: {"mass_defect_amu": 0.0304, "nucleon_count": 4, "claimed_binding_energy_MeV_per_nucleon": 7.07}
    Half-life: {"activity_Bq": 1e6, "atom_count": 1.44e9, "claimed_half_life_seconds": 1000}
    Decay constant: {"half_life_seconds": 3600, "claimed_decay_constant": 1.925e-4}"""
    return {"checks": [_r(r) for r in _nuclear_physics.run({"NUCLEAR_VERIFY": spec or {}})]}


def verify_ecology(spec):
    """Logistic population growth, trophic efficiency (10% rule), Shannon diversity index, carbon footprint.
    Logistic: {"carrying_capacity_K": 1000, "initial_population_N0": 100, "growth_rate_r": 0.5, "time_t": 5, "claimed_population": 731}
    Trophic: {"energy_input": 10000, "trophic_levels_up": 2, "trophic_efficiency": 0.10, "claimed_energy_output": 100}
    Shannon: {"species_proportions": [0.5, 0.3, 0.2], "claimed_shannon_index": 1.0297}
    Carbon: {"distance_km": 500, "emission_factor_kg_per_km": 0.21, "claimed_co2_kg": 105}"""
    return {"checks": [_r(r) for r in _ecology.run({"ECO_VERIFY": spec or {}})]}


def verify_rhetoric(spec):
    """Fallacy classification (formal vs informal), syllogism validity, argument structure completeness.
    Fallacy: {"fallacy_name": "ad hominem", "claimed_is_formal_fallacy": false}
    Syllogism: {"major_premise": "All M are P", "minor_premise": "All S are M", "conclusion": "All S are P", "claimed_valid": true}
    Structure: {"has_premise": true, "has_conclusion": true, "has_warrant": false, "claimed_is_complete_argument": true}"""
    return {"checks": [_r(r) for r in _rhetoric.run({"RHET_VERIFY": spec or {}})]}


def verify_philosophy(spec):
    """Modal logic (K-axiom), ethical framework classification, epistemic claim type, Leibniz identity principle.
    Modal: {"is_necessarily_true": true, "is_possibly_true": true, "claimed_consistent": true}
    Ethics: {"framework_name": "consequentialist", "claimed_focuses_on_outcomes": true}
    Epistemic: {"claim_requires_observation": false, "claimed_is_a_priori": true}
    Identity: {"object_a_properties": ["red","round"], "object_b_properties": ["round","red"], "claimed_are_identical": true}"""
    return {"checks": [_r(r) for r in _philosophy.run({"PHIL_VERIFY": spec or {}})]}


def verify_operations_research(spec):
    """LP feasibility, critical path (makespan), 0/1 knapsack optimal value, assignment cost.
    LP: {"variable_values": {"x": 3, "y": 2}, "constraints": [{"lhs_coeffs": {"x": 1, "y": 1}, "operator": "<=", "rhs": 10}], "claimed_feasible": true}
    Critical path: {"tasks": [{"id": "A", "duration": 3, "depends_on": []}, {"id": "B", "duration": 2, "depends_on": ["A"]}], "claimed_makespan": 5}
    Knapsack: {"items": [{"weight": 2, "value": 6}, {"weight": 3, "value": 10}], "capacity": 5, "claimed_optimal_value": 16}
    Assignment: {"assignment": [[0, 1], [1, 0]], "cost_matrix": [[3, 2], [5, 4]], "claimed_total_cost": 7}"""
    return {"checks": [_r(r) for r in _operations_research.run({"OR_VERIFY": spec or {}})]}


def verify_law(spec):
    """US federal law: contract formation, constitutional age requirements, FLSA overtime, Miranda completeness.
    Contract: {"has_offer": true, "has_acceptance": true, "has_consideration": true, "has_capacity": true, "has_legality": true, "claimed_contract_valid": true}
    Age: {"office": "president", "age": 38, "claimed_meets_age_requirement": true}
    FLSA: {"hours_worked": 50, "regular_rate": 20, "claimed_overtime_pay": 300}
    Miranda: {"warnings_given": ["You have the right to remain silent", "used against you in court", "right to attorney", "appointed attorney"], "claimed_miranda_complete": true}"""
    return {"checks": [_r(r) for r in _law.run({"LAW_VERIFY": spec or {}})]}


def verify_theology_doctrine(spec):
    """Orthodox Christian doctrine: gospel core facts (1 Cor 15:3-4), Trinity, salvation by grace, bodily resurrection, creation ex nihilo.
    Gospel: {"claimed_died_for_sins": true, "claimed_was_buried": true, "claimed_rose_third_day": true, "claimed_gospel_complete": true}
    Trinity: {"persons_named": ["Father", "Son", "Holy Spirit"], "claimed_trinitarian_complete": true}
    Salvation: {"claimed_salvation_mechanism": "grace_through_faith", "claimed_excludes_works": true}
    Resurrection: {"claimed_resurrection_type": "bodily", "claimed_is_bodily": true}
    Creation: {"claimed_creation_from_preexisting_matter": false, "claimed_ex_nihilo": true}"""
    return {"checks": [_r(r) for r in _theology_doctrine.run({"THEOL_VERIFY": spec or {}})]}


def verify_history_chronology(spec):
    """Year arithmetic (BCE/CE), century assignment, era classification, elapsed years BCE→CE, decade assignment.
    Year arithmetic: {"from_year": 100, "to_year": 2000, "claimed_elapsed_years": 1900}
    Century: {"year_CE": 1776, "claimed_century": 18}
    Era: {"year": -44, "claimed_era": "BCE"}
    BCE to CE: {"from_BCE": 44, "to_CE": 1066, "claimed_elapsed": 1109}
    Decade: {"year_CE": 1985, "claimed_decade_start": 1980}"""
    return {"checks": [_r(r) for r in _history_chronology.run({"HIST_VERIFY": spec or {}})]}


def verify_materials_science(spec):
    """Stress/strain (Young's modulus), thermal expansion, density, hardness comparison.
    Stress: {"youngs_modulus_Pa": 200e9, "strain": 0.001, "claimed_stress_Pa": 2e8}
    Thermal: {"thermal_expansion_coeff": 12e-6, "original_length_m": 1.0, "delta_T_K": 100, "claimed_delta_length_m": 0.0012}
    Density: {"mass_kg": 2.7, "volume_m3": 0.001, "claimed_density_kg_per_m3": 2700}
    Hardness: {"material_a_hardness": 800, "material_b_hardness": 200, "claimed_a_harder_than_b": true}"""
    return {"checks": [_r(r) for r in _materials_science.run({"MAT_VERIFY": spec or {}})]}


def verify_architecture(spec):
    """FAR, occupant load, stair compliance (IBC riser/tread), window-wall ratio, structural load superposition.
    FAR: {"total_floor_area_m2": 5000, "lot_area_m2": 2000, "claimed_far": 2.5}
    Occupant load: {"floor_area_m2": 500, "occupant_load_factor_m2_per_person": 5, "claimed_occupant_count": 100}
    Stair: {"riser_height_mm": 150, "tread_depth_mm": 280, "claimed_compliant": true}
    Load: {"dead_load_kPa": 3.0, "live_load_kPa": 2.4, "snow_load_kPa": 1.0, "claimed_total_load_kPa": 6.4}"""
    return {"checks": [_r(r) for r in _architecture.run({"ARCH_VERIFY": spec or {}})]}


def verify_oceanography(spec):
    """Hydrostatic pressure at depth, salinity classification, deep-water wave speed, tidal range type, pelagic zone.
    Pressure: {"depth_m": 1000, "claimed_pressure_Pa": 10158825}
    Salinity: {"salinity_ppt": 35, "claimed_classification": "marine"}
    Wave speed: {"wavelength_m": 100, "claimed_wave_speed_m_per_s": 12.47}
    Tidal: {"tidal_range_m": 3.0, "claimed_tidal_type": "mesotidal"}
    Zone: {"depth_m": 500, "claimed_zone": "mesopelagic"}"""
    return {"checks": [_r(r) for r in _oceanography.run({"OCEAN_VERIFY": spec or {}})]}


def verify_physics(spec):
    """Physics umbrella: dimensional / conservation / Newton's-second-law / kinetic-energy.
    Accepts either the legacy nested shape ('dimensional' / 'conservation' keys) or the flat
    PHYS_VERIFY shape (equation+symbols at top level, mass_kg+acceleration_m_per_s2+claimed_force_N
    for F=ma, mass_kg+velocity_m_per_s+claimed_kinetic_energy_J for KE).
    """
    out = {}
    # Legacy nested shape
    if "dimensional" in spec:
        d = spec["dimensional"]
        out["dimensional"] = _r(physics.verify_dimensional_consistency(d["equation"], d["symbols"]))
    if "conservation" in spec:
        c = spec["conservation"]
        law = c.get("law")
        before, after = c["before"], c["after"]
        tol_rel = c.get("tolerance_relative", 1e-6)
        tol_abs = c.get("tolerance_absolute", 0.0)
        if law:
            out["conservation"] = _r(physics.verify_named_conservation(
                law, before, after,
                tolerance_relative=tol_rel, tolerance_absolute=tol_abs))
        else:
            out["conservation"] = _r(physics.verify_conservation(
                before, after,
                tolerance_relative=tol_rel, tolerance_absolute=tol_abs))
    # Flat shape — delegate to the verifier module's run() so all the
    # checks (dimensional, conservation, Newton's 2nd, KE, kinematics,
    # relativistic) dispatch from one place.
    if not out:
        results = physics.run({"PHYS_VERIFY": spec or {}})
        if results:
            out["checks"] = [_r(r) for r in results]
    return out


def verify_statistics(spec):
    """Statistics umbrella: p-value recomputation, multiple comparisons correction, CI verification.
    Pass 'pvalue', 'multiple_comparisons', and/or 'confidence_interval' keys — each fires if present.
    p-value: spec={"pvalue": {"test": "paired_t", "n": 20, "mean_diff": 0.5, "sd_diff": 1.0, "tail": "two", "claimed_p": 0.0375}}
    Multiple comparisons: spec={"multiple_comparisons": {"raw_p_values": [0.01, 0.04, 0.1], "method": "bonferroni", "alpha": 0.05}}
    CI: spec={"confidence_interval": {"estimate": 5.0, "ci_low": 4.2, "ci_high": 5.8}}"""
    out = {}
    if "pvalue" in spec:
        out["pvalue"] = _r(statistics.verify_pvalue_calibration(spec["pvalue"]))
    if "multiple_comparisons" in spec:
        out["multiple_comparisons"] = _r(statistics.verify_multiple_comparisons(spec["multiple_comparisons"]))
    if "confidence_interval" in spec:
        out["confidence_interval"] = _r(statistics.verify_confidence_interval(spec["confidence_interval"]))
    return out


def verify_phase(spec):
    """Classify a packet by its declared 'phase': setup, positioning, or conversion.
    Cross-cutting verifier — runs on any packet; NA if no phase declared, CONFIRMED with guidance if valid.
    spec={"phase": "setup"} or {"phase": "positioning"} or {"phase": "conversion"}
    Anchored in Prov 24:27: prepare your work outside (setup) → position → convert. Order matters."""
    results = _phase.run(spec or {})
    return {"checks": [_r(r) for r in results]}


# ---------------------------------------------------------------------
# Domain-attestation tools
# ---------------------------------------------------------------------

def _gate_results_to_payload(grs):
    items = [
        {"gate": gr.gate, "status": gr.status,
         "reasons": list(gr.reasons or []),
         "details": dict(gr.details or {})}
        for gr in (grs or [])
    ]
    overall = "PASS"
    for it in items:
        if it["status"] == "REJECT":
            overall = "REJECT"
            break
        if it["status"] == "QUARANTINE" and overall == "PASS":
            overall = "QUARANTINE"
    return {"overall": overall, "results": items}


def attest_red(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_red(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


def attest_floor(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_floor(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


# ---------------------------------------------------------------------
# Layer 0 / Scripture tools
# ---------------------------------------------------------------------

def resolve_scripture_ref(ref):
    """Look up a scripture reference in the WEB and return its text.
    Accepts forms like "Jn3:16", "John 3:16", "1Co13:4". Returns
    `{ref, web_text, status, detail}`. Status `source_missing` means
    the Layer 0 data has not been provisioned yet — see the detail."""
    return scripture.resolve_ref(ref)


def word_study(strongs_num):
    """Strong's-keyed word study: definition, derivation, every verse
    where the word appears. Accepts "G26", "H2617", etc. Returns
    `{strongs, word, transliteration, definition, derivation, verses,
    occurrence_count}` or a `source_missing` status if Layer 0 has not
    been provisioned."""
    return scripture.word_study(strongs_num)


def verify_scripture_anchors(anchors):
    """Confirm each ref in `anchors` resolves to a real WEB verse.
    Used to catch fabricated scripture citations — the most common
    LLM-failure mode in this domain. Returns the standard verifier
    result shape (CONFIRMED / MISMATCH / SKIPPED)."""
    return _r(scripture.verify_scripture_anchors(list(anchors or [])))


def triangulate_claim(ref, claim, strongs_keys=None):
    """Triangulation: check whether an interpretation `claim` about a
    scripture verse `ref` is consistent with the original-language
    Strong's definitions.

    Without `strongs_keys`, returns NEEDS_MANUAL_VERIFICATION with the
    WEB text and instructions for completing the check. With Strong's
    numbers supplied (e.g. ['G142'] for airo), returns the per-word
    semantic range so a reviewer (or later automated tagging) can
    compare the claim to attested meaning."""
    return scripture.triangulate_claim(ref, claim, strongs_keys=strongs_keys)


def get_example_packet(name):
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "examples")
    candidates = [f"sample_packet_{name}.json", f"sample_packet_{name}_verify.json",
                  f"sample_packet_jda_{name}.json", f"{name}.json"]
    for c in candidates:
        path = os.path.join(examples_dir, c)
        if os.path.exists(path):
            with open(path) as f:
                return {"name": c, "packet": json.load(f)}
    available = sorted([f for f in os.listdir(examples_dir) if f.endswith(".json")])
    return {"error": f"no example named {name!r}", "available": available}


# ---------------------------------------------------------------------
# List-style API
# ---------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {"name": "validate_packet",
     "description": "Run a packet through the full Four-Gates engine.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"},
                                    "now_epoch": {"type": "integer"}},
                     "required": ["packet"]},
     "fn": lambda a: validate_packet(a["packet"], a.get("now_epoch"))},
    {"name": "verify_chemistry",
     "description": "Verify equation balance / suggest balancing coefficients. Optional temperature_K positivity.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "temperature_K": {"type": "number"}},
                     "required": ["equation"]},
     "fn": lambda a: verify_chemistry(a["equation"], a.get("temperature_K"))},
    {"name": "verify_physics_dimensional",
     "description": "Verify both sides of an equation reduce to identical SI units.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "symbols": {"type": "object"}},
                     "required": ["equation", "symbols"]},
     "fn": lambda a: verify_physics_dimensional(a["equation"], a["symbols"])},
    {"name": "verify_physics_conservation",
     "description": "Verify before/after match within tolerance. Optional 'law' (energy|momentum|charge|mass) enforces named-law key/unit profile.",
     "inputSchema": {"type": "object",
                     "properties": {"before": {"type": "object"},
                                    "after": {"type": "object"},
                                    "tolerance_relative": {"type": "number"},
                                    "tolerance_absolute": {"type": "number"},
                                    "law": {"type": "string"}},
                     "required": ["before", "after"]},
     "fn": lambda a: verify_physics_conservation(
        a["before"], a["after"],
        a.get("tolerance_relative", 1e-6), a.get("tolerance_absolute", 0.0),
        law=a.get("law"))},
    {"name": "verify_mathematics",
     "description": (
         "Sympy verification. mode=equality|derivative|integral|limit|solve|matrix|inequality|series|ode. "
         "Integral: mode='integral', params={\"integrand\":\"x**2\",\"claimed_antiderivative\":\"x**3/3\"} "
         "(use 'integrand', NOT 'expression'). "
         "Derivative: mode='derivative', params={\"function\":\"x**3\",\"claimed_derivative\":\"3*x**2\"}. "
         "Equality: mode='equality', params={\"expr_a\":\"sin(x)**2+cos(x)**2\",\"expr_b\":\"1\"}."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"mode": {"type": "string"}, "params": {"type": "object"}},
                     "required": ["mode", "params"]},
     "fn": lambda a: verify_mathematics(a["mode"], a["params"])},
    {"name": "verify_giving",
     "description": (
         "Conservation of a giving / value-transfer chain -- prove every dollar is "
         "accounted from the donor to the END USER, no leakage. spec={source, links:[{name,fee}], "
         "delivered, claimed_delivered_fraction?, tolerance?}. Confirms iff source == sum(fees) + "
         "delivered; reports the unaccounted leak + the % that reached the end user."
     ),
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_giving(a["spec"])},
    {"name": "language_data",
     "description": (
         "Phoneme inventory + language family + world region for a language, from the "
         "offline PHOIBLE 2.0 + Glottolog index (external Layer-0 source). query = a "
         "language name, ISO 639-3 code, or Glottocode. Returns family, macroarea, "
         "coordinates, and the consonants/vowels/tones with counts."
     ),
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
     "fn": lambda a: language_data(a["query"])},
    {"name": "wikidata",
     "description": (
         "Look up an entity on Wikidata (CC0 public domain) by label -> key facts "
         "(description, instance-of, notable property/value pairs). Live SPARQL, cached "
         "offline. Crowd-sourced reference (CONCORDANT-grade, not a HOLDS) -- a starting "
         "point to verify against the harder sources, never proof. query = an entity label."
     ),
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
     "fn": lambda a: wikidata(a["query"])},
    {"name": "word_meaning",
     "description": (
         "English lexical semantics from the offline WordNet 3.1 database. word -> senses, "
         "each {pos, definition, synonyms, hypernyms (is-a parents)}. The semantics level of "
         "the language tree -- pairs with word_study (original Greek/Hebrew) and language_data "
         "(phonemes). 147k lemmas, offline."
     ),
     "inputSchema": {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]},
     "fn": lambda a: word_meaning(a["word"])},
    {"name": "place_lookup",
     "description": (
         "Gazetteer lookup from the offline GeoNames cities5000 database. name -> matching "
         "places ordered by population, each {name, admin1, country, lat, lon, population, "
         "feature, timezone}. Serves the local-community layer (group you by your area) and "
         "basic geography; disambiguates same-named places by size. 69k places (pop >= 5000), "
         "offline. Data (c) GeoNames.org, CC-BY 4.0."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "limit": {"type": "integer"}},
                     "required": ["name"]},
     "fn": lambda a: place_lookup(a["name"], a.get("limit", 8))},
    {"name": "timezone_offset",
     "description": (
         "UTC offset + daylight-saving state for an IANA time zone at an instant, from the "
         "offline IANA Time Zone Database (public domain). zone = an IANA name like "
         "'Asia/Tokyo' (use place_lookup to get a place's zone). when = optional ISO date/"
         "datetime (default now). Returns utc_offset, abbreviation, is_dst -- a deterministic "
         "rule fact, not invented. Completes the calendar_time grounding."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"zone": {"type": "string"},
                                    "when": {"type": "string"}},
                     "required": ["zone"]},
     "fn": lambda a: timezone_offset(a["zone"], a.get("when"))},
    {"name": "unit_convert",
     "description": (
         "Deterministic unit conversion via the offline UCUM table. from_unit/to_unit are "
         "UCUM codes/expressions: 'km', 'm/s', 'kg.m/s2', '[mi_i]' (intl mile), '[lb_av]', "
         "'Cel', '[degF]'. Omit to_unit to get the value in canonical base units. Handles "
         "affine temperatures. Incommensurable units are reported (not forced); unparseable/"
         "non-linear units return 'unsupported' -- it fails closed, never guesses. The units "
         "substrate under every dimensional check."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"value": {"type": "number"},
                                    "from_unit": {"type": "string"},
                                    "to_unit": {"type": "string"}},
                     "required": ["value", "from_unit"]},
     "fn": lambda a: unit_convert(a["value"], a["from_unit"], a.get("to_unit"))},
    {"name": "sequence_lookup",
     "description": (
         "Identify or look up an integer sequence in the offline OEIS index. anum (e.g. "
         "'A000045' or 45) -> name + terms; OR terms (a list like [1,1,2,3,5,8] or a comma "
         "string, >=3) -> OEIS sequences whose terms contain that run, lowest A-number first. "
         "OEIS is a curated reference: a term match IDENTIFIES (not proves) a sequence. "
         "Grounds number_theory / combinatorics. CC BY-SA, (c) OEIS Foundation."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"anum": {"type": "string"},
                                    "terms": {"type": "array", "items": {"type": "number"}},
                                    "limit": {"type": "integer"}}},
     "fn": lambda a: sequence_lookup(a.get("anum"), a.get("terms"), a.get("limit", 8))},
    {"name": "word_pronunciation",
     "description": (
         "Pronunciation of an English word from the offline CMU Pronouncing Dictionary. "
         "word -> each variant as {arpabet, ipa (segmental), syllable_count, stress_pattern}. "
         "ARPABET is CMU's authoritative transcription; IPA is a deterministic transliteration. "
         "The phonics level of the language tree (pairs with language_data, word_meaning, "
         "word_study). ~126k words, offline. BSD-2, (c) Carnegie Mellon University."
     ),
     "inputSchema": {"type": "object", "properties": {"word": {"type": "string"}},
                     "required": ["word"]},
     "fn": lambda a: word_pronunciation(a["word"])},
    {"name": "port_lookup",
     "description": (
         "Look up an internet port or service in the offline IANA port registry. query = a "
         "port NUMBER (443 -> https) OR a service NAME ('ssh' -> port 22). Optional protocol "
         "(tcp/udp/sctp). The authoritative 'what runs on port N / what port does X use' for "
         "networking. Public domain (IANA)."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"},
                                    "protocol": {"type": "string"}},
                     "required": ["query"]},
     "fn": lambda a: port_lookup(a["query"], a.get("protocol"))},
    {"name": "rfc_lookup",
     "description": (
         "Look up an RFC in the offline RFC Index. number (9113, 'RFC9113') -> {title, status, "
         "date, obsoletes, obsoleted_by, url}. If the RFC is obsoleted, 'superseded_by' is set "
         "prominently so a dead RFC is never cited as current (RFC 7540 -> superseded by 9113). "
         "'Which RFC defines X' for networking/crypto. Public domain (IETF)."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"number": {"type": "string"}},
                     "required": ["number"]},
     "fn": lambda a: rfc_lookup(a["number"])},
    {"name": "verify_statistics_pvalue",
     "description": "Recompute p from inputs and compare to claimed_p. Tests: two_sample_t, one_sample_t, paired_t, z, chi2, f, one_proportion_z, two_proportion_z, fisher_exact, mannwhitney, wilcoxon_signed_rank, regression_coefficient_t.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_statistics_pvalue(a["spec"])},
    {"name": "verify_statistics_multiple_comparisons",
     "description": "Bonferroni or BH/FDR adjustment with rejection-set verification.",
     "inputSchema": {"type": "object",
                     "properties": {"raw_p_values": {"type": "array"},
                                    "method": {"type": "string"},
                                    "alpha": {"type": "number"},
                                    "claimed_rejected_indices": {"type": "array"}},
                     "required": ["raw_p_values", "method"]},
     "fn": lambda a: verify_statistics_multiple_comparisons(
        a["raw_p_values"], a["method"], a.get("alpha", 0.05),
        a.get("claimed_rejected_indices"))},
    {"name": "verify_statistics_confidence_interval",
     "description": "Verify CI well-formed and contains estimate. With 'spec' raw inputs, recompute bounds.",
     "inputSchema": {"type": "object",
                     "properties": {"estimate": {"type": "number"},
                                    "ci_low": {"type": "number"},
                                    "ci_high": {"type": "number"},
                                    "spec": {"type": "object"}},
                     "required": ["estimate", "ci_low", "ci_high"]},
     "fn": lambda a: verify_statistics_confidence_interval(
        a["estimate"], a["ci_low"], a["ci_high"], spec=a.get("spec"))},
    {"name": "verify_computer_science",
     "description": "Verify Python: termination, correctness, runtime O(.), space O(.), determinism.",
     "inputSchema": {"type": "object",
                     "properties": {"code": {"type": "string"},
                                    "function_name": {"type": "string"},
                                    "test_cases": {"type": "array"},
                                    "input_generator": {"type": "string"},
                                    "claimed_class": {"type": "string"},
                                    "claimed_space_class": {"type": "string"},
                                    "sizes": {"type": "array"},
                                    "tolerance": {"type": "number"},
                                    "determinism_trials": {"type": "integer"}},
                     "required": ["code"]},
     "fn": lambda a: verify_computer_science(
        a["code"], a.get("function_name"), a.get("test_cases"),
        a.get("input_generator"), a.get("claimed_class"),
        a.get("sizes"), a.get("tolerance", 0.40),
        determinism_trials=a.get("determinism_trials"),
        claimed_space_class=a.get("claimed_space_class"))},
    {"name": "verify_biology",
     "description": (
         "Biology checks: replicates, assays, dose-response, power, Hardy-Weinberg, "
         "primer Tm/GC, molarity, Mendelian. "
         "Pass bio_control dict to verify nested health control system claims: "
         "failure_mode (setpoint_drift|loop_saturation|compensation_collapse|"
         "cross_layer_override|sensor_failure), failure_layer (L1-L6), "
         "intervention_layers, and required safety fields."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"n_replicates": {"type": "integer"},
                                    "min_replicates": {"type": "integer"},
                                    "assay_classes": {"type": "array"},
                                    "min_assay_classes": {"type": "integer"},
                                    "dose_response": {"type": "object"},
                                    "power_analysis": {"type": "object"},
                                    "bio_control": {"type": "object"},
                                    "hardy_weinberg": {"type": "object"},
                                    "primer": {"type": "object"},
                                    "molarity": {"type": "object"},
                                    "mendelian": {"type": "object"}}},
     "fn": lambda a: verify_biology(
        a.get("n_replicates"), a.get("min_replicates", 3),
        a.get("assay_classes"), a.get("min_assay_classes", 2),
        a.get("dose_response"), a.get("power_analysis"),
        bio_control=a.get("bio_control"),
        hardy_weinberg=a.get("hardy_weinberg"), primer=a.get("primer"),
        molarity=a.get("molarity"), mendelian=a.get("mendelian"))},
    {"name": "verify_governance_decision_packet",
     "description": "Decision packet structural check. Optional 'domain' (governance|business|household|education|church) activates per-domain profile.",
     "inputSchema": {"type": "object",
                     "properties": {"decision_packet": {"type": "object"},
                                    "witness_count": {"type": "integer"},
                                    "domain": {"type": "string"}},
                     "required": ["decision_packet"]},
     "fn": lambda a: verify_governance_decision_packet(
        a["decision_packet"], a.get("witness_count"), domain=a.get("domain"))},
    {"name": "attest_red",
     "description": "Run only the RED-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_red(a["packet"])},
    {"name": "attest_floor",
     "description": "Run only the FLOOR-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_floor(a["packet"])},
    {"name": "resolve_scripture_ref",
     "description": (
         "Look up a scripture reference in the World English Bible and return "
         "its text. Accepts forms like 'Jn3:16', 'John 3:16', '1Co13:4'. "
         "Returns {ref, web_text, status, detail}. Status 'source_missing' "
         "means Layer 0 data has not been provisioned — run "
         "lw/00_source/fetch_sources.py once."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"}},
                     "required": ["ref"]},
     "fn": lambda a: resolve_scripture_ref(a["ref"])},
    {"name": "word_study",
     "description": (
         "Strong's-keyed word study. Pass a Strong's number like 'G26' "
         "(agape) or 'H2617' (chesed). Returns word, transliteration, "
         "definition, derivation, every verse where the word appears, "
         "and occurrence count."),
     "inputSchema": {"type": "object",
                     "properties": {"strongs_num": {"type": "string"}},
                     "required": ["strongs_num"]},
     "fn": lambda a: word_study(a["strongs_num"])},
    {"name": "verify_scripture_anchors",
     "description": (
         "Confirm each ref in 'anchors' resolves to a real WEB verse. Use "
         "this before citing scripture in a load-bearing claim — fabricated "
         "references are the most common LLM failure mode in this domain. "
         "Returns CONFIRMED / MISMATCH / SKIPPED."),
     "inputSchema": {"type": "object",
                     "properties": {"anchors": {"type": "array",
                                                "items": {"type": "string"}}},
                     "required": ["anchors"]},
     "fn": lambda a: verify_scripture_anchors(a["anchors"])},
    {"name": "triangulate_claim",
     "description": (
         "Triangulation: check whether an interpretation 'claim' about a "
         "verse 'ref' survives at all three layers (WEB text, Strong's "
         "original-language meaning, the claim itself). Without "
         "strongs_keys returns NEEDS_MANUAL_VERIFICATION + the WEB text "
         "and instructions. With Strong's numbers supplied, returns the "
         "per-word semantic range so the claim can be checked against "
         "attested meaning."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"},
                                    "claim": {"type": "string"},
                                    "strongs_keys": {"type": "array",
                                                     "items": {"type": "string"}}},
                     "required": ["ref", "claim"]},
     "fn": lambda a: triangulate_claim(a["ref"], a["claim"], a.get("strongs_keys"))},
    {"name": "get_example_packet",
     "description": "Return a canonical example packet by name.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"}},
                     "required": ["name"]},
     "fn": lambda a: get_example_packet(a["name"])},
    # ── Extended domain verifiers ────────────────────────────────────
    {"name": "verify_energy",
     "description": "Off-grid sizing, wire voltage drop, battery/solar sizing, peak-load-vs-inverter, runtime, kWh↔Wh, efficiency, power balance. Pass spec as ENERGY_VERIFY contents.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_energy(a["spec"])},
    {"name": "verify_acoustics",
     "description": "Wave speed/frequency/wavelength (v=fλ), decibel ratios, Doppler shift, harmonic frequencies.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_acoustics(a["spec"])},
    {"name": "verify_agriculture",
     "description": "USDA hardiness zone lookup, soil pH range for crops, crop rotation compatibility, livestock stocking density.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_agriculture(a["spec"])},
    {"name": "verify_astronomy",
     "description": "Kepler's third law (T²∝a³), gravitational force, stellar parallax distance, distance modulus (m-M).",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_astronomy(a["spec"])},
    {"name": "verify_calendar_time",
     "description": "Gregorian leap-year rule, ISO 8601 datetime validity, day-of-week (Zeller/Tomohiko), duration addition.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_calendar_time(a["spec"])},
    {"name": "verify_combinatorics",
     "description": "Permutations P(n,k), combinations C(n,k), derangements D(n), multinomial coefficients.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_combinatorics(a["spec"])},
    {"name": "verify_cryptography",
     "description": "Hash match, hash strength (NIST), HMAC, base64/hex roundtrip, key-length strength. "
                    "Hash match: spec={\"hash_algorithm\":\"sha256\",\"data\":\"hello\",\"claimed_hash_hex\":\"2cf24dba...\"}. "
                    "Hash strength: spec={\"hash_strength_algorithm\":\"md5\",\"claimed_hash_strength\":\"broken\"}. "
                    "Key strength: spec={\"cipher\":\"AES\",\"key_bits\":256,\"claimed_key_strength\":\"strong\"}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_cryptography(a["spec"])},
    {"name": "verify_document_validation",
     "description": "ISBN-13 check-digit and Luhn algorithm for credit card numbers. "
                    "ISBN-13: spec={\"isbn13\":\"9780306406157\",\"claimed_isbn13_valid\":true}. "
                    "Luhn: spec={\"luhn_number\":\"4532015112830366\",\"claimed_luhn_valid\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_document_validation(a["spec"])},
    {"name": "verify_electrical",
     "description": "Ohm's law (V=IR), power (P=VI/I²R/V²/R), Kirchhoff voltage loop sum, RC time constant (τ=RC).",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_electrical(a["spec"])},
    {"name": "verify_exercise_science",
     "description": "Energy expenditure (MET×kg×hours), max heart rate Tanaka (208-0.7×age), Karvonen HR zone, MET lookup. "
                    "Energy: spec={\"claimed_met\":8,\"weight_kg\":70,\"duration_hours\":1,\"claimed_kcal\":560}. "
                    "Max HR: spec={\"age_years\":30,\"claimed_max_hr\":187}. "
                    "HR zone: spec={\"age_years\":30,\"resting_hr\":60,\"intensity_low\":0.7,\"intensity_high\":0.8,"
                    "\"claimed_zone_low_bpm\":149,\"claimed_zone_high_bpm\":162}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_exercise_science(a["spec"])},
    {"name": "verify_finance",
     "description": "Accounting identity (A=L+E), compound interest A=P(1+r/n)^(nt), NPV, present value PV=FV/(1+r)^t.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_finance(a["spec"])},
    {"name": "verify_formal_logic",
     "description": (
         "Propositional logic checks — use boolean 'claimed_' fields, NOT a test_type string. "
         "Satisfiable: spec={\"formula\":\"(A>>B)&A\",\"claimed_satisfiable\":true}. "
         "Tautology: spec={\"formula\":\"p|~p\",\"claimed_tautology\":true}. "
         "Contradiction: spec={\"formula\":\"p&~p\",\"claimed_contradiction\":true}. "
         "Entailment: spec={\"premises\":[\"p\",\"p>>q\"],\"conclusion\":\"q\",\"claimed_entailment\":true}. "
         "Equivalence: spec={\"formula_a\":\"~~p\",\"formula_b\":\"p\",\"claimed_equivalent\":true}."
     ),
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_formal_logic(a["spec"])},
    {"name": "verify_genetics",
     "description": (
         "DNA/RNA base complementarity, reverse complement, GC content, codon→amino-acid translation. "
         "Complement: spec={\"sequence\":\"ATCG\",\"claimed_complement\":\"TAGC\"} "
         "(use 'sequence', NOT 'dna_sequence'). "
         "Reverse complement: spec={\"sequence\":\"ATCG\",\"claimed_reverse_complement\":\"CGAT\"}. "
         "GC content: spec={\"sequence\":\"GCGC\",\"claimed_gc_fraction\":1.0}. "
         "Codon: spec={\"codon\":\"ATG\",\"claimed_amino_acid\":\"Met\"}."
     ),
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_genetics(a["spec"])},
    {"name": "verify_geography",
     "description": "Lat/lon range validity, Haversine great-circle distance, initial bearing, UTM zone assignment.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geography(a["spec"])},
    {"name": "verify_geology",
     "description": "Radiometric decay dating (N=N₀·e^(−λt)), Mohs hardness scratch test, Richter scale amplitude ratio.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geology(a["spec"])},
    {"name": "verify_geometry",
     "description": "Areas and volumes of standard shapes, Pythagorean theorem, circle/sphere relationships, triangle angle sum.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geometry(a["spec"])},
    {"name": "verify_hydrology",
     "description": "Manning's equation (open channel flow), Darcy's law (porous media), continuity equation Q=Av.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_hydrology(a["spec"])},
    {"name": "verify_information_theory",
     "description": "Shannon entropy H(X), channel capacity C=B·log₂(1+SNR), mutual information, Huffman minimum code length.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_information_theory(a["spec"])},
    {"name": "verify_linguistics",
     "description": "Strong's number resolution (G/H range), occurrence count, transliteration normalization, gloss consistency, cognate pair detection.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_linguistics(a["spec"])},
    {"name": "verify_manufacturing",
     "description": "Tolerance stack-up (worst-case/RSS), GD&T fit class (clearance/interference), surface roughness Ra, process capability Cp/Cpk.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_manufacturing(a["spec"])},
    {"name": "verify_meteorology",
     "description": "Dew point (Magnus formula), relative humidity, pressure altitude, wind chill (NWS), heat index.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_meteorology(a["spec"])},
    {"name": "verify_music_theory",
     "description": "Interval semitone counts, chord quality (major/minor/dom7/dim), frequency ratio for equal temperament.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_music_theory(a["spec"])},
    {"name": "verify_networking",
     "description": "Subnet mask validity, CIDR notation, IP address range, network/broadcast address computation.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_networking(a["spec"])},
    {"name": "verify_number_theory",
     "description": "Primality testing, GCD/LCM, modular arithmetic, Fibonacci membership, perfect/abundant/deficient classification.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_number_theory(a["spec"])},
    {"name": "verify_nutrition",
     "description": "Macro caloric values (4/4/9 kcal/g), BMR (Mifflin-St Jeor), TDEE with activity factor, nutrient density.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_nutrition(a["spec"])},
    {"name": "verify_optics",
     "description": "Snell's law (n₁sinθ₁=n₂sinθ₂), thin-lens equation (1/f=1/do+1/di), diffraction grating, Rayleigh criterion.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_optics(a["spec"])},
    {"name": "verify_photography",
     "description": "Exposure value (EV), equivalent exposures (aperture/shutter/ISO triangle), depth-of-field hyperfocal distance.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_photography(a["spec"])},
    {"name": "verify_sports_analytics",
     "description": "Batting average, ERA, NFL passer rating, Pythagorean win expectation, Elo rating change.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_sports_analytics(a["spec"])},
    {"name": "verify_witness",
     "description": "Gate-chain completeness, reasoning trace presence, anchor resolution, no-fabricated-answer check. Verifies a witness/attestation record is structurally sound.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_witness(a["spec"])},
    {"name": "verify_quantum_computing",
     "description": "Qubit normalization (Σ|aᵢ|²=1), Grover optimal iterations (T=floor(π√N/4)), "
                    "Shor period (a^r≡1 mod N), BB84 QKD security (QBER<11%), von Neumann entropy, fidelity. "
                    "Normalization: spec={\"amplitudes\":[0.6,0.8],\"claimed_normalized\":true}. "
                    "Grover: spec={\"n_items\":64,\"claimed_grover_iterations\":6}. "
                    "BB84: spec={\"qber\":0.09,\"claimed_secure\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_quantum_computing(a["spec"])},
    {"name": "verify_medicine",
     "description": "BMI, drug dosage, blood pressure (AHA 2017), A1C→eAG, eGFR (Cockcroft-Gault), IBW (Devine), MAP. "
                    "BMI: spec={\"weight_kg\":70,\"height_m\":1.75,\"claimed_bmi\":22.86}. "
                    "BP: spec={\"systolic\":125,\"diastolic\":82,\"claimed_bp_class\":\"hypertension_stage_1\"}. "
                    "MAP: spec={\"systolic\":120,\"diastolic\":80,\"claimed_map_mmhg\":93.3}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_medicine(a["spec"])},
    {"name": "verify_cybersecurity",
     "description": "Password entropy, TLS version status, CVSS severity, subnet host count, port classification. "
                    "Entropy: spec={\"password_length\":16,\"charset_size\":94,\"claimed_entropy_bits\":104.9}. "
                    "CVSS: spec={\"cvss_base_score\":9.1,\"claimed_cvss_severity\":\"critical\"}. "
                    "Port: spec={\"port_number\":443,\"claimed_port_class\":\"well_known\"}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_cybersecurity(a["spec"])},
    {"name": "verify_economics",
     "description": "Simple/compound interest, PV/FV, Rule of 72, inflation adjustment, GDP per capita, price elasticity. "
                    "Simple interest: spec={\"principal\":1000,\"rate\":0.05,\"time_years\":3,\"claimed_simple_interest\":150}. "
                    "Rule of 72: spec={\"rate_percent\":7,\"claimed_doubling_years\":10.3}. "
                    "Inflation: spec={\"nominal_value\":1000,\"inflation_rate\":0.03,\"years\":10,\"claimed_real_value\":744.09}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_economics(a["spec"])},
    {"name": "verify_labor",
     "description": (
         "Wage and labor law verification. "
         "Gross pay (≤40h only, no overtime): spec={\"hourly_rate\":18.5,\"hours_worked\":40,\"claimed_gross_pay\":740.0}. "
         "FLSA overtime (hours_worked>40 — ALWAYS use this form): "
         "spec={\"hourly_rate\":18.5,\"regular_hours\":40,\"overtime_hours\":5,\"claimed_overtime_pay\":878.75}. "
         "Take-home: spec={\"gross_pay\":1000,\"total_tax_rate\":0.28,\"claimed_take_home\":720}. "
         "Annual/hourly: spec={\"annual_salary\":52000,\"claimed_hourly_equivalent\":25.0}. "
         "NOTE: when total hours > 40, use overtime spec (regular_hours + overtime_hours), not gross_pay spec."
     ),
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_labor(a["spec"])},
    {"name": "verify_real_estate",
     "description": "Monthly mortgage, cap rate, GRM, LTV, DSCR, rental yield. "
                    "Mortgage: spec={\"loan_principal\":300000,\"annual_rate\":0.065,\"loan_term_months\":360,\"claimed_monthly_payment\":1896.20}. "
                    "Cap rate: spec={\"net_operating_income\":24000,\"property_value\":400000,\"claimed_cap_rate\":0.06}. "
                    "LTV: spec={\"loan_amount\":240000,\"appraised_value\":300000,\"claimed_ltv\":0.80}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_real_estate(a["spec"])},
    {"name": "verify_construction",
     "description": "Concrete volume, rect/circle areas, rebar weight, wall area, paint coverage, tile count, beam load. "
                    "Concrete: spec={\"length_m\":10,\"width_m\":5,\"depth_m\":0.15,\"claimed_concrete_m3\":7.5}. "
                    "Tiles: spec={\"tile_area_m2\":50,\"tile_size_m2\":0.25,\"waste_factor\":0.10,\"claimed_tile_count\":220}. "
                    "Beam: spec={\"total_load_kn\":120,\"span_m\":6,\"claimed_load_intensity_kn_per_m\":20.0}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_construction(a["spec"])},
    {"name": "verify_soil_science",
     "description": "Soil pH suitability, NPK fertilizer requirements, irrigation ETc (Kc*ET0), lime requirement, USDA texture class. "
                    "pH: spec={\"crop\":\"maize\",\"soil_ph\":6.2,\"claimed_ph_suitable\":true}. "
                    "Texture: spec={\"sand_pct\":40,\"silt_pct\":40,\"clay_pct\":20,\"claimed_texture_class\":\"loam\"}. "
                    "Irrigation: spec={\"reference_et0_mm_per_day\":5.0,\"crop_coefficient\":1.15,\"claimed_etc_mm_per_day\":5.75}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_soil_science(a["spec"])},
    {"name": "verify_thermodynamics",
     "description": "Carnot efficiency (η=1−Tc/Th), ideal gas law (PV=nRT), specific heat (Q=mcΔT), entropy change (ΔS=Q/T). "
                    "Carnot: spec={\"T_hot_K\":600,\"T_cold_K\":300,\"claimed_efficiency\":0.5}. "
                    "Specific heat: spec={\"mass_kg\":1.0,\"specific_heat_J_per_kgK\":4186,\"delta_T_K\":10,\"claimed_heat_J\":41860}. "
                    "Entropy: spec={\"heat_J\":1000,\"temperature_K\":500,\"claimed_entropy_change_J_per_K\":2.0}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_thermodynamics(a["spec"])},
    {"name": "verify_nuclear_physics",
     "description": "Radioactive decay (N=N0·e^-λt), binding energy per nucleon (mass_defect_amu×931.5/A), half-life from activity (T=ln2·N/A), decay constant (λ=ln2/T). "
                    "Decay: spec={\"half_life_seconds\":3600,\"elapsed_seconds\":7200,\"initial_count\":1e9,\"claimed_remaining_count\":2.5e8}. "
                    "Binding: spec={\"mass_defect_amu\":0.0304,\"nucleon_count\":4,\"claimed_binding_energy_MeV_per_nucleon\":7.07}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_nuclear_physics(a["spec"])},
    {"name": "verify_ecology",
     "description": "Logistic population growth, trophic efficiency (10% rule), Shannon diversity (H=−Σp·lnp), carbon footprint transport. "
                    "Logistic: spec={\"carrying_capacity_K\":1000,\"initial_population_N0\":100,\"growth_rate_r\":0.5,\"time_t\":5,\"claimed_population\":731}. "
                    "Trophic: spec={\"energy_input\":10000,\"trophic_levels_up\":2,\"claimed_energy_output\":100}. "
                    "Shannon: spec={\"species_proportions\":[0.5,0.3,0.2],\"claimed_shannon_index\":1.0297}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_ecology(a["spec"])},
    {"name": "verify_rhetoric",
     "description": "Fallacy classification (formal vs informal, 18-entry catalogue), Aristotelian syllogism validity (20 valid mood-figure pairs), argument structure completeness. "
                    "Fallacy: spec={\"fallacy_name\":\"ad hominem\",\"claimed_is_formal_fallacy\":false}. "
                    "Syllogism: spec={\"major_premise\":\"All M are P\",\"minor_premise\":\"All S are M\",\"conclusion\":\"All S are P\",\"claimed_valid\":true}. "
                    "Structure: spec={\"has_premise\":true,\"has_conclusion\":true,\"has_warrant\":false,\"claimed_is_complete_argument\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_rhetoric(a["spec"])},
    {"name": "verify_philosophy",
     "description": "Modal logic K-axiom (necessarily-P→possibly-P), ethical framework classification (deontological/consequentialist/virtue/contractarian), epistemic claim type (a priori vs a posteriori), Leibniz identity principle. "
                    "Modal: spec={\"is_necessarily_true\":true,\"is_possibly_true\":true,\"claimed_consistent\":true}. "
                    "Ethics: spec={\"framework_name\":\"consequentialist\",\"claimed_focuses_on_outcomes\":true}. "
                    "Epistemic: spec={\"claim_requires_observation\":false,\"claimed_is_a_priori\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_philosophy(a["spec"])},
    {"name": "verify_operations_research",
     "description": "LP feasibility (constraint evaluation), critical path makespan (topological sort), 0/1 knapsack optimal value (DP), assignment cost (Σ cost_matrix[i][j]). "
                    "LP: spec={\"variable_values\":{\"x\":3,\"y\":2},\"constraints\":[{\"lhs_coeffs\":{\"x\":1,\"y\":1},\"operator\":\"<=\",\"rhs\":10}],\"claimed_feasible\":true}. "
                    "Critical path: spec={\"tasks\":[{\"id\":\"A\",\"duration\":3,\"depends_on\":[]},{\"id\":\"B\",\"duration\":2,\"depends_on\":[\"A\"]}],\"claimed_makespan\":5}. "
                    "Knapsack: spec={\"items\":[{\"weight\":2,\"value\":6},{\"weight\":3,\"value\":10}],\"capacity\":5,\"claimed_optimal_value\":16}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_operations_research(a["spec"])},
    {"name": "verify_law",
     "description": "US federal law: contract formation (5 elements), constitutional age requirements (president=35/senator=30/rep=25), FLSA overtime (1.5×rate for hours>40), Miranda completeness (4 warnings). "
                    "Contract: spec={\"has_offer\":true,\"has_acceptance\":true,\"has_consideration\":true,\"has_capacity\":true,\"has_legality\":true,\"claimed_contract_valid\":true}. "
                    "Age: spec={\"office\":\"president\",\"age\":38,\"claimed_meets_age_requirement\":true}. "
                    "FLSA: spec={\"hours_worked\":50,\"regular_rate\":20,\"claimed_overtime_pay\":300}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_law(a["spec"])},
    {"name": "verify_theology_doctrine",
     "description": "Orthodox Christian doctrine from Scripture: gospel core facts (1 Cor 15:3-4 — died/buried/rose), Nicene Trinity (Father/Son/Holy Spirit), salvation by grace (Eph 2:8-9, not works), bodily resurrection (Luke 24:39), creation ex nihilo (Gen 1:1/Heb 11:3). "
                    "Gospel: spec={\"claimed_died_for_sins\":true,\"claimed_was_buried\":true,\"claimed_rose_third_day\":true,\"claimed_gospel_complete\":true}. "
                    "Trinity: spec={\"persons_named\":[\"Father\",\"Son\",\"Holy Spirit\"],\"claimed_trinitarian_complete\":true}. "
                    "Salvation: spec={\"claimed_salvation_mechanism\":\"grace_through_faith\",\"claimed_excludes_works\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_theology_doctrine(a["spec"])},
    {"name": "verify_history_chronology",
     "description": "BCE/CE year arithmetic, century assignment (ceil(year/100)), era classification, elapsed years BCE→CE (no year 0: from_BCE+to_CE-1), decade assignment. "
                    "Year arithmetic: spec={\"from_year\":100,\"to_year\":2000,\"claimed_elapsed_years\":1900}. "
                    "Century: spec={\"year_CE\":1776,\"claimed_century\":18}. "
                    "BCE to CE: spec={\"from_BCE\":44,\"to_CE\":1066,\"claimed_elapsed\":1109}. "
                    "Era: spec={\"year\":-44,\"claimed_era\":\"BCE\"}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_history_chronology(a["spec"])},
    {"name": "verify_materials_science",
     "description": "Stress/strain (σ=Eε, σ=F/A), thermal expansion (ΔL=αL₀ΔT), density (ρ=m/V), hardness comparison (Vickers/Brinell HV). "
                    "Stress: spec={\"youngs_modulus_Pa\":200e9,\"strain\":0.001,\"claimed_stress_Pa\":2e8}. "
                    "Thermal: spec={\"thermal_expansion_coeff\":12e-6,\"original_length_m\":1.0,\"delta_T_K\":100,\"claimed_delta_length_m\":0.0012}. "
                    "Density: spec={\"mass_kg\":2.7,\"volume_m3\":0.001,\"claimed_density_kg_per_m3\":2700}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_materials_science(a["spec"])},
    {"name": "verify_architecture",
     "description": "FAR (floor_area/lot_area), occupant load (ceil(area/factor)), IBC stair compliance (riser 102–178mm, tread ≥279mm), window-wall ratio, structural load superposition. "
                    "FAR: spec={\"total_floor_area_m2\":5000,\"lot_area_m2\":2000,\"claimed_far\":2.5}. "
                    "Occupant: spec={\"floor_area_m2\":500,\"occupant_load_factor_m2_per_person\":5,\"claimed_occupant_count\":100}. "
                    "Stair: spec={\"riser_height_mm\":150,\"tread_depth_mm\":280,\"claimed_compliant\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_architecture(a["spec"])},
    {"name": "verify_oceanography",
     "description": "Hydrostatic pressure at depth (P=Patm+ρgd, ρ=1025 kg/m³), salinity classification (fresh/brackish/marine/hypersaline), deep-water wave speed (c=√(gλ/2π)), tidal range type (micro/meso/macrotidal), pelagic zone (epipelagic→hadopelagic). "
                    "Pressure: spec={\"depth_m\":1000,\"claimed_pressure_Pa\":10158825}. "
                    "Salinity: spec={\"salinity_ppt\":35,\"claimed_classification\":\"marine\"}. "
                    "Wave: spec={\"wavelength_m\":100,\"claimed_wave_speed_m_per_s\":12.47}. "
                    "Zone: spec={\"depth_m\":500,\"claimed_zone\":\"mesopelagic\"}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_oceanography(a["spec"])},
    {"name": "verify_physics",
     "description": "Physics umbrella — dimensional analysis and/or conservation law. "
                    "Pass 'dimensional' key: spec={\"dimensional\":{\"equation\":\"F=m*a\",\"symbols\":{\"F\":\"newton\",\"m\":\"kilogram\",\"a\":\"meter/second**2\"}}}. "
                    "Pass 'conservation' key: spec={\"conservation\":{\"before\":{\"KE\":5.0,\"PE\":10.0},\"after\":{\"KE\":8.0,\"PE\":7.0},\"law\":\"energy\"}}. "
                    "Both keys fire independently if supplied.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_physics(a["spec"])},
    {"name": "verify_statistics",
     "description": "Statistics umbrella — p-value recomputation, multiple comparisons correction, CI verification. "
                    "Pass 'pvalue' key: spec={\"pvalue\":{\"test\":\"paired_t\",\"n\":20,\"mean_diff\":0.5,\"sd_diff\":1.0,\"tail\":\"two\",\"claimed_p\":0.0375}}. "
                    "Pass 'multiple_comparisons' key: spec={\"multiple_comparisons\":{\"raw_p_values\":[0.01,0.04],\"method\":\"bonferroni\"}}. "
                    "Pass 'confidence_interval' key: spec={\"confidence_interval\":{\"estimate\":5.0,\"ci_low\":4.2,\"ci_high\":5.8}}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_statistics(a["spec"])},
    {"name": "verify_phase",
     "description": "Classify a packet by its declared phase: setup, positioning, or conversion (Prov 24:27). "
                    "Cross-cutting — NA if no phase declared; CONFIRMED with canonical guidance if valid. "
                    "spec={\"phase\":\"setup\"} or {\"phase\":\"positioning\"} or {\"phase\":\"conversion\"}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_phase(a["spec"])},
]


TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools():
    return [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]


def call_tool(name, arguments):
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}", "available": list(TOOL_BY_NAME.keys())}
    try:
        return tool["fn"](arguments or {})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


ALL_TOOLS: Dict[str, Any] = {
    "check": check,
    "verify_giving": verify_giving,
    "language_data": language_data,
    "wikidata": wikidata,
    "word_meaning": word_meaning,
    "place_lookup": place_lookup,
    "timezone_offset": timezone_offset,
    "unit_convert": unit_convert,
    "sequence_lookup": sequence_lookup,
    "word_pronunciation": word_pronunciation,
    "port_lookup": port_lookup,
    "rfc_lookup": rfc_lookup,
    "validate_packet": validate_packet,
    "seal_packet": seal_packet,
    "walkthrough_packet": walkthrough_packet,
    "verify_chemistry": verify_chemistry,
    "verify_physics_dimensional": verify_physics_dimensional,
    "verify_physics_conservation": verify_physics_conservation,
    "verify_mathematics": verify_mathematics,
    "verify_statistics_pvalue": verify_statistics_pvalue,
    "verify_statistics_multiple_comparisons": verify_statistics_multiple_comparisons,
    "verify_statistics_confidence_interval": verify_statistics_confidence_interval,
    "verify_computer_science": verify_computer_science,
    "verify_biology": verify_biology,
    "verify_governance_decision_packet": verify_governance_decision_packet,
    "verify_energy": verify_energy,
    "verify_acoustics": verify_acoustics,
    "verify_agriculture": verify_agriculture,
    "verify_astronomy": verify_astronomy,
    "verify_calendar_time": verify_calendar_time,
    "verify_combinatorics": verify_combinatorics,
    "verify_cryptography": verify_cryptography,
    "verify_document_validation": verify_document_validation,
    "verify_electrical": verify_electrical,
    "verify_exercise_science": verify_exercise_science,
    "verify_finance": verify_finance,
    "verify_formal_logic": verify_formal_logic,
    "verify_genetics": verify_genetics,
    "verify_geography": verify_geography,
    "verify_geology": verify_geology,
    "verify_geometry": verify_geometry,
    "verify_hydrology": verify_hydrology,
    "verify_information_theory": verify_information_theory,
    "verify_linguistics": verify_linguistics,
    "verify_manufacturing": verify_manufacturing,
    "verify_meteorology": verify_meteorology,
    "verify_music_theory": verify_music_theory,
    "verify_networking": verify_networking,
    "verify_number_theory": verify_number_theory,
    "verify_nutrition": verify_nutrition,
    "verify_optics": verify_optics,
    "verify_photography": verify_photography,
    "verify_sports_analytics": verify_sports_analytics,
    "verify_witness": verify_witness,
    "verify_quantum_computing": verify_quantum_computing,
    "verify_medicine": verify_medicine,
    "verify_cybersecurity": verify_cybersecurity,
    "verify_economics": verify_economics,
    "verify_labor": verify_labor,
    "verify_real_estate": verify_real_estate,
    "verify_construction": verify_construction,
    "verify_soil_science": verify_soil_science,
    "verify_thermodynamics": verify_thermodynamics,
    "verify_nuclear_physics": verify_nuclear_physics,
    "verify_ecology": verify_ecology,
    "verify_rhetoric": verify_rhetoric,
    "verify_philosophy": verify_philosophy,
    "verify_operations_research": verify_operations_research,
    "verify_law": verify_law,
    "verify_theology_doctrine": verify_theology_doctrine,
    "verify_history_chronology": verify_history_chronology,
    "verify_materials_science": verify_materials_science,
    "verify_architecture": verify_architecture,
    "verify_oceanography": verify_oceanography,
    "verify_physics": verify_physics,
    "verify_statistics": verify_statistics,
    "verify_phase": verify_phase,
    "verify_physical_constants": verify_physical_constants,
    "verify_periodic_table": verify_periodic_table,
    "verify_atomic": verify_atomic,
    "verify_molecular_geometry": verify_molecular_geometry,
    "verify_ephemeris": verify_ephemeris,
    "verify_layer_zero_grounding": verify_layer_zero_grounding,
    "verify_linear_algebra": verify_linear_algebra,
    "verify_probability": verify_probability,
    "attest_red": attest_red,
    "attest_floor": attest_floor,
    "resolve_scripture_ref": resolve_scripture_ref,
    "word_study": word_study,
    "verify_scripture_anchors": verify_scripture_anchors,
    "triangulate_claim": triangulate_claim,
    "get_example_packet": get_example_packet,
}
