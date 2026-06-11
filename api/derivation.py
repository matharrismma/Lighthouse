"""
Multi-step verification — the derivation chain (Task B keystone, Fable 2026-06-10).

A single verifier confirms ONE claim. A DERIVATION is an ordered chain of claims
where each step's verifier must confirm AND each step may build only on prior
steps that themselves confirmed. This runner verifies every step deterministically
(via the existing verifier dispatch) and checks the links, producing ONE checkable
trail with a composite verdict.

The engine never generates the answer — it verifies a PROVIDED derivation and
reports EXACTLY where it breaks (the elimination trail; the trail is the trust —
project_mapping_reality_2026-06-10). This is what makes "solve a real calculus/
physics problem, every step verified" real (project_moat_track_2026-06-10): the
free 64-verifier stack confirms each structured step; the chain ties them into a
proof.

THE BRIDGE: a step's `spec` is the exact kwargs its verifier wants (the structured
form). Supplying structured steps directly is the faithful, oracle-free path
(this module). An oracle-assisted prose->steps translator can ride on top later
(oracle STRUCTURES, this runner JUDGES — runs on prod), per
project_academia_connection_atlas_2026-06-09.

A step:
  {
    "id": "s1",                 # unique within the derivation (default: s<index>)
    "domain": "mathematics",    # -> verify_<domain>
    "spec": {...},              # the structured claim (kwargs for that verifier)
    "uses": ["s0"],             # ids of prior steps this builds on (optional)
    "claim": "f'(x) = 2x"       # human-readable, for the trail (optional)
  }

Composite verdict:
  HOLDS      — every step CONFIRMED and every `uses` -> a CONFIRMED prior step.
  BROKEN     — a step MISMATCH/ERROR, or `uses` -> a missing/unconfirmed step;
               `broken_at` = the first such step (the trail stops being trustworthy there).
  INCOMPLETE — a step's verifier returned NOT_APPLICABLE (couldn't run: the spec
               wasn't structured enough — the prose->spec bridge gap); `gap_at`.
"""
from __future__ import annotations

from typing import Any, Dict, List

_TERMINAL_FAIL = ("MISMATCH", "ERROR")


def _collect_statuses(res: Any, acc: List) -> None:
    """Walk a verifier result of any shape and append (status, detail) pairs.

    Handles: a VerifierResult dataclass, a dict with a "status", a dict nesting
    a list under checks/results/verifications, and lists of any of these."""
    if res is None:
        return
    if isinstance(res, list):
        for r in res:
            _collect_statuses(r, acc)
        return
    status = getattr(res, "status", None)
    if status is not None and not isinstance(res, dict):
        acc.append((str(status), str(getattr(res, "detail", "") or "")))
        return
    if isinstance(res, dict):
        if "status" in res:
            acc.append((str(res["status"]), str(res.get("detail", "") or "")))
            return
        for key in ("checks", "results", "verifications", "domain_results"):
            sub = res.get(key)
            if isinstance(sub, list):
                _collect_statuses(sub, acc)
                return
        # Umbrella wrappers (e.g. verify_statistics) return a dict KEYED by
        # check-name whose VALUES are themselves status-dicts/lists. Walk them.
        for v in res.values():
            if isinstance(v, (dict, list)):
                _collect_statuses(v, acc)


def verify_step(domain: str, spec: Dict[str, Any]) -> Dict[str, str]:
    """Run one step's verifier and reduce its (possibly multi-part) result to a
    single status. A step CONFIRMS iff at least one applicable invariant confirmed
    and none contradicted; it FAILS on any applicable MISMATCH/ERROR; it is
    NOT_APPLICABLE if the verifier could not run (spec too thin)."""
    from api import agent_manifest as _am  # local import: avoid import cycles
    domain = (domain or "").strip()
    if not domain:
        return {"status": "ERROR", "detail": "step missing 'domain'"}
    out = _am.dispatch(f"verify_{domain}", spec or {})
    if not out.get("ok"):
        return {"status": "ERROR", "detail": str(out.get("error", "dispatch failed"))[:300]}
    acc: List = []
    _collect_statuses(out.get("result"), acc)
    if not acc:
        return {"status": "ERROR", "detail": "verifier returned no status"}
    applicable = [(s, d) for s, d in acc if s != "NOT_APPLICABLE"]
    fails = [(s, d) for s, d in applicable if s in _TERMINAL_FAIL]
    if fails:
        s, d = fails[0]
        return {"status": s, "detail": d[:300]}
    if not applicable:
        return {"status": "NOT_APPLICABLE", "detail": acc[0][1][:300]}
    confs = [d for s, d in applicable if s == "CONFIRMED"]
    return {"status": "CONFIRMED", "detail": (confs[0] if confs else "")[:300]}


def verify_derivation(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify an ordered derivation. Every step is checked (the full trail is
    returned), but the COMPOSITE verdict is governed by the FIRST step that
    breaks — that is where the derivation stops being trustworthy."""
    if not isinstance(steps, list) or not steps:
        return {"verdict": "ERROR", "detail": "no steps provided", "trail": []}

    trail: List[Dict[str, Any]] = []
    seen_ids: set = set()
    confirmed_ids: set = set()
    verdict = "HOLDS"
    broken_at = None
    gap_at = None

    for i, step in enumerate(steps):
        sid = str(step.get("id") or f"s{i}")
        domain = str(step.get("domain", ""))
        spec = step.get("spec") or {}
        uses = [str(u) for u in (step.get("uses") or [])]

        # Link integrity: a step may build only on prior steps that CONFIRMED.
        missing = [u for u in uses if u not in seen_ids]
        unconfirmed = [u for u in uses if u in seen_ids and u not in confirmed_ids]
        link_ok = not missing and not unconfirmed

        sr = verify_step(domain, spec)
        st = sr["status"]

        entry: Dict[str, Any] = {
            "id": sid, "domain": domain, "claim": str(step.get("claim", "")),
            "uses": uses, "status": st, "detail": sr.get("detail", ""),
            "link_ok": link_ok,
        }
        if missing:
            entry["missing_refs"] = missing
        if unconfirmed:
            entry["builds_on_unconfirmed"] = unconfirmed
        trail.append(entry)
        seen_ids.add(sid)

        if st == "CONFIRMED" and link_ok:
            confirmed_ids.add(sid)
        elif verdict == "HOLDS":
            # first break governs the composite
            if st == "NOT_APPLICABLE":
                verdict, gap_at = "INCOMPLETE", sid
            else:  # MISMATCH / ERROR / broken link
                verdict, broken_at = "BROKEN", sid

    return {
        "verdict": verdict,
        "steps": len(steps),
        "confirmed_steps": len(confirmed_ids),
        "broken_at": broken_at,
        "gap_at": gap_at,
        "trail": trail,
        "note": ("The trail is the trust: each step is machine-verified and may "
                 "build only on confirmed prior steps. The engine verifies a "
                 "provided derivation; it does not generate the answer."),
    }


def seal_receipt(result: Dict[str, Any], problem: str = None) -> Dict[str, Any]:
    """Mint a citable, tamper-evident proof receipt for a verified derivation.

    Reuses the engine's existing receipt substrate (the content-addressed
    store): the SHA-256 content hash IS the permanent reference and the
    integrity proof — fetch it at GET /seal/{ref} and recompute to confirm it
    was not altered. The receipt records the deterministic verifier VERDICT +
    the full trail (the real proof) and, by doctrine, never a generated answer
    — a BROKEN refutation is as citable as a HOLDS confirmation. Binds the
    node's PUBLIC key for provenance when available; Ed25519 signing stays
    optional (the hash is the integrity guarantee, no private key required).
    """
    rec: Dict[str, Any] = {"kind": "derivation_receipt", "engine": "concordance"}
    if problem:
        rec["problem"] = problem
    for key in ("title", "verdict", "steps", "confirmed_steps", "broken_at",
                "gap_at", "trail", "structured_steps"):
        v = result.get(key)
        if v is not None:
            rec[key] = v
    rec["note"] = result.get("note") or (
        "The trail is the trust: each step is machine-verified by its domain "
        "verifier; the engine verifies a provided derivation, it never "
        "generates the answer.")
    try:
        from concordance_engine.user_identity import get_user_pubkey
        pk = get_user_pubkey()
        if pk:
            rec["issuer_public_key"] = pk
    except Exception:  # noqa: BLE001
        pass
    try:
        from concordance_engine import cas as _cas
        h = _cas.store(rec)
        return {"permanent_ref": h, "content_hash": h,
                "cite_url": "https://narrowhighway.com/seal/" + h,
                "verdict": rec.get("verdict")}
    except Exception as exc:  # noqa: BLE001
        return {"error": "seal unavailable: " + str(exc)[:120]}


# ── The bridge: prose -> structured steps (oracle STRUCTURES, verifier JUDGES) ──
# The real bottleneck (project_academia_connection_atlas_2026-06-09) is turning a
# natural-language problem into the structured specs the verifier stack can run.
# This translator uses the paid oracle ONLY to FORMALIZE — never to decide truth.
# Every value it proposes (including any intermediate it computes) is then checked
# by the deterministic chain runner above; if the oracle mis-structures or proposes
# a wrong value, the verdict is BROKEN/INCOMPLETE, honestly. Trust stays with the
# verifier, never the oracle (the discovery-loop discipline; Principle B). Runs on
# PROD only (no key locally) and is Steward-budget-gated — returns ok:False when
# unprovisioned, so the structured-submission path (/derivation/verify) still works.

# Supported domains the oracle may emit. V1 = the mathematics core (the calculus
# the moat targets), each spec shape tested end-to-end through dispatch. Extend by
# adding a domain's exact spec shape + example here (and confirming it dispatches).
_BRIDGE_SYS = """You translate a science or mathematics problem, claim, or THEORY into STRUCTURED VERIFICATION STEPS for a deterministic verifier. You do NOT decide truth and you do NOT have the final say — a separate engine checks every step you produce. Your only job is to FORMALIZE the verifiable, quantitative claims.

Rules:
- Break it into the smallest independently-checkable steps. Each step:
  {"id":"s0","domain":"<domain>","spec":{...},"uses":["s_prior"...],"claim":"short human description"}
  "uses" lists prior step ids this step builds on (may be empty).
- FAITHFULNESS (CRITICAL): encode the claim EXACTLY AS STATED. Copy the asserted value, label, interval name, coefficient, geometry, or category the text gives into the claimed_ field — EVEN IF YOU BELIEVE IT IS WRONG. Your only job is to FORMALIZE; you must NEVER "correct" the claim. The deterministic engine decides truth and will catch a false claim. Example: for "440 Hz and 880 Hz form a perfect fifth" you MUST set claimed_interval="fifth" (do NOT substitute "octave" because you think that's right) — let the engine break it. ONLY when the text explicitly ASKS you to find/compute an unstated value do you supply the standard one.
- Use ONLY these domains, with EXACTLY these spec shapes:

  mathematics (SymPy syntax: ** power, * multiply, sin/cos/exp/sqrt, oo infinity; an "equation" is set equal to zero, so "2x=6" -> "2*x - 6"):
    {"domain":"mathematics","spec":{"mode":"derivative","params":{"function":"x**2","variable":"x","claimed_derivative":"2*x"}}}
    {"domain":"mathematics","spec":{"mode":"integral","params":{"integrand":"2*x","variable":"x","claimed_antiderivative":"x**2"}}}
    {"domain":"mathematics","spec":{"mode":"limit","params":{"function":"sin(x)/x","variable":"x","point":0,"claimed_limit":"1"}}}
    {"domain":"mathematics","spec":{"mode":"solve","params":{"equation":"2*x - 6","variable":"x","claimed_solutions":[3]}}}
    {"domain":"mathematics","spec":{"mode":"equality","params":{"expr_a":"(x+1)**2","expr_b":"x**2+2*x+1","variables":["x"]}}}

  number_theory:
    {"domain":"number_theory","spec":{"factorial_n":5,"claimed_factorial":120}}
    {"domain":"number_theory","spec":{"n_prime":17,"claimed_prime":true}}
    {"domain":"number_theory","spec":{"gcd_a":12,"gcd_b":18,"claimed_gcd":6}}

  combinatorics:
    {"domain":"combinatorics","spec":{"perm_n":5,"perm_k":2,"claimed_permutations":20}}
    {"domain":"combinatorics","spec":{"comb_n":5,"comb_k":2,"claimed_combinations":10}}

  formal_logic (propositional: & and, | or, ~ not, >> implies):
    {"domain":"formal_logic","spec":{"variables":["p","q"],"formula":"p | ~p","claimed_tautology":true}}
    {"domain":"formal_logic","spec":{"variables":["p","q"],"formula":"p & ~p","claimed_contradiction":true}}

  geometry:
    {"domain":"geometry","spec":{"tri_a":3,"tri_b":4,"tri_c":5,"claimed_valid_triangle":true}}
    {"domain":"geometry","spec":{"pyth_a":3,"pyth_b":4,"pyth_c":5,"claimed_right_triangle":true}}
    {"domain":"geometry","spec":{"circle_radius":5,"claimed_circle_area":78.5398}}
    {"domain":"geometry","spec":{"coordination":"tetrahedral","claimed_central_angle_deg":109.47}}

  optics (SI units, lengths in metres; for refraction/TIR/NA set n_core = the DENSER medium the light starts in and n_cladding = the RARER medium it meets — air=1.00, water=1.33, typical glass=1.50; photon energy is ALWAYS in joules, so convert an eV claim by multiplying by 1.602176634e-19):
    {"domain":"optics","spec":{"wavelength_m":6.5e-7,"claimed_photon_energy_j":3.06e-19}}
    {"domain":"optics","spec":{"wavelength_m":6.5e-7,"slit_separation_m":1e-4,"screen_distance_m":2.0,"claimed_fringe_spacing_m":0.013}}
    {"domain":"optics","spec":{"n1":1.0,"n2":1.5,"theta1_deg":30,"claimed_theta2_deg":19.47}}
    {"domain":"optics","spec":{"n_core":1.5,"n_cladding":1.0,"claimed_critical_angle_deg":41.81}}
    {"domain":"optics","spec":{"n_core":1.5,"n_cladding":1.48,"claimed_numerical_aperture":0.2441}}
    {"domain":"optics","spec":{"mass_kg":9.109e-31,"velocity_m_s":1e6,"claimed_de_broglie_m":7.27e-10}}
    {"domain":"optics","spec":{"attenuation_db_per_km":0.2,"length_km":100,"claimed_loss_db":20}}
    {"domain":"optics","spec":{"num_channels":80,"bitrate_per_channel_gbps":100,"claimed_total_gbps":8000}}

  atomic:
    {"domain":"atomic","spec":{"atomic_number":6,"claimed_configuration":"1s2 2s2 2p2"}}
    {"domain":"atomic","spec":{"shell_n":3,"claimed_shell_capacity":18}}
    {"domain":"atomic","spec":{"n":3,"l":2,"m_l":-1,"m_s":0.5}}

  molecular_geometry (VSEPR):
    {"domain":"molecular_geometry","spec":{"bonding_domains":4,"lone_pairs":0,"claimed_geometry":"tetrahedral","claimed_bond_angle_deg":109.47}}

  statistics (umbrella — the spec carries ONE of pvalue / confidence_interval / multiple_comparisons; tail is "two"/"greater"/"less"; the p tolerance is loose, so use the published rounded p):
    {"domain":"statistics","spec":{"pvalue":{"test":"z","z":1.96,"tail":"two","claimed_p":0.05}}}
    {"domain":"statistics","spec":{"pvalue":{"test":"chi2","statistic":3.841,"df":1,"claimed_p":0.05}}}
    {"domain":"statistics","spec":{"confidence_interval":{"estimate":10.0,"ci_low":8.0,"ci_high":12.0}}}
    {"domain":"statistics","spec":{"multiple_comparisons":{"raw_p_values":[0.01,0.04,0.2],"method":"bonferroni","alpha":0.05}}}

  physics_dimensional (check both sides of an equation share the same SI dimensions; the "equation" MUST keep a literal "=" with BOTH sides intact, e.g. "F = m*a" — do NOT move terms to one side or use the set-to-zero form (that is ONLY for the mathematics solve mode); "symbols" maps EACH variable to its SI unit as a sympy unit expression — newton, joule, kilogram, meter, second, watt, pascal, coulomb, volt, ampere, kelvin, combined with * / **; numeric coefficients like 1/2 are ignored):
    {"domain":"physics_dimensional","spec":{"equation":"F = m*a","symbols":{"F":"newton","m":"kilogram","a":"meter/second**2"}}}
    {"domain":"physics_dimensional","spec":{"equation":"E = m*c**2","symbols":{"E":"joule","m":"kilogram","c":"meter/second"}}}
    {"domain":"physics_dimensional","spec":{"equation":"E = (1/2)*m*v**2","symbols":{"E":"joule","m":"kilogram","v":"meter/second"}}}

  chemistry (verify a chemical equation is balanced; use "->" for the arrow and " + " between species; coefficients are written as "2 H2O"; formulas keep inline subscripts like H2O / CO2 / C6H12O6 / Cu(OH)2; charges use ^ like Fe^3+):
    {"domain":"chemistry","spec":{"equation":"2 H2 + O2 -> 2 H2O"}}
    {"domain":"chemistry","spec":{"equation":"CH4 + 2 O2 -> CO2 + 2 H2O"}}

  music_theory (frequency ratios and equal-temperament pitch; interval names allowed: unison/octave/fifth/fourth/major_third/minor_third/major_sixth/minor_sixth/major_second/minor_second/major_seventh/minor_seventh; MIDI A4=69=440 Hz, middle C=60, each semitone +1):
    {"domain":"music_theory","spec":{"freq_a":440,"freq_b":880,"claimed_interval":"octave"}}
    {"domain":"music_theory","spec":{"freq_a":440,"freq_b":660,"claimed_interval":"fifth"}}
    {"domain":"music_theory","spec":{"midi_note":60,"claimed_frequency_hz":261.63}}

- If a claim does NOT fit any domain/spec above, OMIT it — do not invent a domain or spec. Fewer correct steps beat guesses.
- Output ONLY a JSON array of steps. No prose, no markdown, no code fence."""


def _extract_json_array(text: str):
    """Pull the first top-level JSON array out of a model response."""
    import json
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        out = json.loads(s[start:end + 1])
        return out if isinstance(out, list) else None
    except Exception:
        return None


def structure_prose(problem: str) -> Dict[str, Any]:
    """Oracle-assisted: formalize a prose math problem into verifiable steps.

    Returns {"ok": True, "steps": [...]} or {"ok": False, "error": "..."} when the
    oracle is unavailable (no key / over budget / failure). NEVER raises — the
    caller falls back to the structured-submission path."""
    import os
    problem = (problem or "").strip()
    if not problem:
        return {"ok": False, "error": "empty problem"}
    if len(problem) > 4000:
        problem = problem[:4000]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"ok": False, "error": "oracle unavailable (no key) — submit structured steps to /derivation/verify"}
    try:
        from api.offices import steward_budget_remaining_usd, ledger_record
    except Exception:
        steward_budget_remaining_usd = lambda: 0.0  # noqa: E731
        ledger_record = lambda *a, **k: None        # noqa: E731
    try:
        if steward_budget_remaining_usd() < 1.0:
            return {"ok": False, "error": "oracle over budget — submit structured steps to /derivation/verify"}
    except Exception:
        pass
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"],
                                     timeout=25.0, max_retries=1)
        resp = client.messages.create(
            model=os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5"),
            max_tokens=1200, system=_BRIDGE_SYS,
            messages=[{"role": "user", "content": problem}])
        try:
            ti = getattr(resp.usage, "input_tokens", 0) or 0
            to = getattr(resp.usage, "output_tokens", 0) or 0
            ledger_record("derivation_bridge", ti * 3e-6 + to * 15e-6)
        except Exception:
            pass
        raw = "".join(getattr(b, "text", "") for b in resp.content).strip()
        steps = _extract_json_array(raw)
        if not steps:
            return {"ok": False, "error": "oracle did not return parseable steps", "raw": raw[:400]}
        return {"ok": True, "steps": steps}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


def solve_prose(problem: str) -> Dict[str, Any]:
    """Full bridge: structure a prose problem, then JUDGE it with the chain runner.
    The oracle structured; the verdict below is the VERIFIER's, not the oracle's."""
    structured = structure_prose(problem)
    if not structured.get("ok"):
        return {"ok": False, "structured": False, "problem": problem,
                "message": structured.get("error", "could not structure the problem"),
                "hint": "Submit structured steps directly to POST /derivation/verify."}
    steps = structured["steps"]
    result = verify_derivation(steps)
    result.update({"ok": True, "structured": True, "problem": problem,
                   "structured_steps": steps,
                   "oracle_note": ("The oracle only FORMALIZED the prose into steps; the verdict and "
                                   "trail above are the deterministic verifier's. A wrong formalization "
                                   "shows up as BROKEN/INCOMPLETE — the oracle is never trusted.")})
    return result
