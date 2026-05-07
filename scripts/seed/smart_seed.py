"""smart_seed.py — Hub-and-spoke convergence-aware seed generator.

Each domain is seeded in two phases:
  Phase 1 — HUB: one broad claim that sits at the domain's centre.
             It connects to adjacent domains via axis overlap.
             The hub is posted first so it can be walked from.
  Phase 2 — SPOKES: N specific sub-topic seeds that branch from
             the hub. Each spoke is generated knowing the hub text
             so it fills the gap around it rather than duplicating it.

Navigation is graph-based. To reach new seeds, you only move from
the nearest seed. The case store wires neighbor edges on every insert
(SPOKE_K = 5 outgoing edges), so the entire corpus becomes navigable
without ever scanning all rows.

Modes
─────
  --analyze          Coverage map + hub inventory. No posting.
  --fill [--top N]   Fill N coldest domains hub-first (default 10).
  --domain D         Smart-seed a single domain.
  --walk D           Walk the graph from domain D's hub; print what's near.

Usage:
  python scripts/seed/smart_seed.py --analyze
  python scripts/seed/smart_seed.py --fill --top 10 --count 50
  python scripts/seed/smart_seed.py --domain theology_doctrine --count 30
  python scripts/seed/smart_seed.py --walk mathematics
  python scripts/seed/smart_seed.py --fill --top 20 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

# ── Configuration ──────────────────────────────────────────────────────────────

API_BASE   = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "smart_seed_state.json"

COOL_FLOOR    = 20    # verdicts below this = "cool" domain
NEIGHBOR_K    = 3     # warm neighbors to pull hub context from
SPOKE_BATCH   = 10    # spokes generated per hub in one Haiku call


# ── API key ────────────────────────────────────────────────────────────────────

def _load_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if k:
        return k
    for d in [Path(__file__).parent, Path(__file__).parent.parent.parent]:
        env_file = d / ".env"
        if env_file.exists():
            for line in env_file.read_text("utf-8", errors="replace").splitlines():
                m = re.match(r"ANTHROPIC_API_KEY=(.+)", line.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    return ""

ANTHROPIC_KEY = _load_key()


# ── Grid adjacency ─────────────────────────────────────────────────────────────

def _load_axis_dimensions() -> Dict[str, FrozenSet[str]]:
    repo_src = Path(__file__).parent.parent.parent / "src"
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    try:
        from concordance_engine.grid import AXIS_DIMENSIONS  # type: ignore
        return AXIS_DIMENSIONS
    except ImportError:
        pass
    # Minimal inline fallback
    return {
        "chemistry":         frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "physics":           frozenset({"physical_substance", "conservation_balance", "reasoning"}),
        "mathematics":       frozenset({"reasoning"}),
        "computer_science":  frozenset({"encoding", "reasoning", "time_sequence"}),
        "biology":           frozenset({"encoding", "metabolism", "physical_substance", "conservation_balance", "time_sequence"}),
        "governance":        frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "scripture_anchors": frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "linguistics":       frozenset({"encoding", "reasoning"}),
        "formal_logic":      frozenset({"reasoning"}),
        "cryptography":      frozenset({"encoding", "reasoning", "authority_trust"}),
        "finance":           frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
        "economics":         frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
        "theology_doctrine": frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "law":               frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "labor":             frozenset({"metabolism", "authority_trust", "time_sequence", "conservation_balance"}),
        "medicine":          frozenset({"metabolism", "physical_substance", "authority_trust", "time_sequence"}),
        "real_estate":       frozenset({"physical_substance", "authority_trust", "time_sequence", "conservation_balance"}),
        "cybersecurity":     frozenset({"encoding", "reasoning", "authority_trust"}),
        "quantum_computing": frozenset({"encoding", "reasoning", "physical_substance"}),
        "operations_research": frozenset({"reasoning", "time_sequence", "conservation_balance"}),
        "thermodynamics":    frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "energy":            frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "ecology":           frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "genetics":          frozenset({"encoding", "physical_substance"}),
        "agriculture":       frozenset({"metabolism", "physical_substance", "time_sequence"}),
        "nutrition":         frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "exercise_science":  frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "nuclear_physics":   frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
        "geology":           frozenset({"metabolism", "physical_substance", "time_sequence"}),
        "meteorology":       frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "hydrology":         frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "soil_science":      frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "manufacturing":     frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "construction":      frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "architecture":      frozenset({"physical_substance", "authority_trust", "time_sequence"}),
        "networking":        frozenset({"encoding", "physical_substance", "authority_trust", "time_sequence"}),
        "information_theory": frozenset({"encoding", "reasoning"}),
        "theology_doctrine": frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "witness":           frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "governance_decision_packet": frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "rhetoric":          frozenset({"encoding", "reasoning", "authority_trust"}),
        "philosophy":        frozenset({"reasoning", "authority_trust"}),
    }


AXIS_DIMENSIONS: Dict[str, FrozenSet[str]] = _load_axis_dimensions()


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def axis_neighbors(domain: str, top_k: int = 5, min_sim: float = 0.20) -> List[Tuple[str, float]]:
    dims = AXIS_DIMENSIONS.get(domain, frozenset())
    scores = [
        (other, round(_jaccard(dims, other_dims), 3))
        for other, other_dims in AXIS_DIMENSIONS.items()
        if other != domain
    ]
    scores = [(n, s) for n, s in scores if s >= min_sim]
    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


def axis_depth(domain: str) -> int:
    return len(AXIS_DIMENSIONS.get(domain, frozenset()))


# ── Coverage ───────────────────────────────────────────────────────────────────

def get_coverage(session: requests.Session) -> Dict[str, int]:
    try:
        r = session.get(f"{API_BASE}/cases/stats", timeout=10)
        if r.status_code == 200:
            return dict(r.json().get("by_domain", {}))
    except Exception as exc:
        print(f"  [WARN] /cases/stats: {exc}", flush=True)
    return {}


def get_hub(domain: str, session: requests.Session) -> Optional[Dict[str, Any]]:
    """Fetch the hub (highest-degree case) for a domain from the API."""
    try:
        r = session.get(f"{API_BASE}/cases/hub/{domain}", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def coverage_priority(
    domains: List[str],
    coverage: Dict[str, int],
    top_n: Optional[int] = None,
) -> List[Tuple[str, int, int]]:
    """Sort by (verdicts ASC, axis_depth DESC) — cold + deep domains first."""
    ranked = [(d, coverage.get(d, 0), axis_depth(d)) for d in domains]
    ranked.sort(key=lambda x: (x[1], -x[2]))
    return ranked[:top_n] if top_n else ranked


# ── Graph walk (via API) ───────────────────────────────────────────────────────

def walk_from_domain(
    domain: str,
    session: requests.Session,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Walk the case graph from a domain's hub, return closest cases found."""
    try:
        r = session.post(
            f"{API_BASE}/cases/closest",
            json={"domain": domain, "top_k": top_k},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("cases", data.get("results", []))
    except Exception as exc:
        print(f"  [WARN] graph walk failed: {exc}", flush=True)
    return []


# ── Hub context ────────────────────────────────────────────────────────────────

def hub_context_for_domain(
    domain: str,
    coverage: Dict[str, int],
    session: requests.Session,
) -> Tuple[Optional[str], str]:
    """Return (existing_hub_text, neighbor_context_string).

    existing_hub_text: text of the domain's current hub (if any), so
    spokes know what the hub already says and branch from it.

    neighbor_context: verifier snippets from warm axis-neighbors.
    """
    # Try to get the domain's existing hub
    existing_hub: Optional[str] = None
    cases = walk_from_domain(domain, session, top_k=3)
    if cases:
        # The first result (closest) is the most central — treat as hub
        vs = cases[0].get("verifier_summary") or []
        if vs:
            existing_hub = vs[0].get("note", "")[:200] if vs else None

    # Pull neighbor context from warm adjacent domains
    snippets: List[str] = []
    neighbors = axis_neighbors(domain, top_k=8)
    warm = [(n, sim) for n, sim in neighbors if coverage.get(n, 0) >= COOL_FLOOR]

    for n, sim in warm[:NEIGHBOR_K]:
        nbr_cases = walk_from_domain(n, session, top_k=2)
        for case in nbr_cases[:1]:
            vs = case.get("verifier_summary") or []
            note = vs[0].get("note", "") if vs else ""
            if note:
                snippets.append(f"[{n}] {note[:120]}")

    neighbor_ctx = ""
    if snippets:
        neighbor_ctx = (
            "\n\nThe engine already knows this from adjacent domains "
            "(your seeds must fill the GAP, not repeat this):\n"
            + "\n".join(f"  • {s}" for s in snippets)
        )

    return existing_hub, neighbor_ctx


# ── Generation ─────────────────────────────────────────────────────────────────

DOMAIN_HINTS = {
    "acoustics":            "sound waves, acoustics, decibels, Fourier, room acoustics, hearing",
    "agriculture":          "crops, soil, irrigation, yield, farming, agronomy, pest management",
    "architecture":         "building design, structural systems, materials, codes, space planning",
    "astronomy":            "stars, galaxies, orbital mechanics, cosmology, spectra, telescopes",
    "biology":              "cells, metabolism, evolution, genetics, ecology, physiology, taxonomy",
    "calendar_time":        "timekeeping, calendar systems, epochs, UTC, leap years, ISO 8601",
    "chemistry":            "chemical reactions, bonding, stoichiometry, thermodynamics, kinetics",
    "combinatorics":        "counting, permutations, combinations, graph theory, probability",
    "computer_science":     "algorithms, data structures, complexity, paradigms, systems",
    "construction":         "structural engineering, materials, codes, project management, foundations",
    "cryptography":         "encryption, hashing, public-key, RSA, ECC, protocols, PKI",
    "cybersecurity":        "threats, defenses, OWASP, network security, incident response",
    "document_validation":  "provenance, signatures, notarization, chain of custody, attestation",
    "ecology":              "ecosystems, food webs, succession, biodiversity, nutrient cycles",
    "economics":            "supply/demand, macro, micro, monetary policy, trade, markets",
    "electrical":           "circuits, Ohm's law, AC/DC, capacitors, inductors, power systems",
    "energy":               "thermodynamics, renewables, fossil fuels, efficiency, storage, grid",
    "exercise_science":     "physiology, biomechanics, training principles, VO2 max, EPOC",
    "finance":              "time value of money, DCF, bonds, equities, risk, portfolio theory",
    "formal_logic":         "propositional logic, predicate logic, inference rules, proofs, paradoxes",
    "genetics":             "DNA, RNA, transcription, translation, Mendelian inheritance, mutations",
    "geography":            "cartography, climate zones, plate tectonics, population, geopolitics",
    "geology":              "rock cycle, plate tectonics, stratigraphy, mineralogy, geologic time",
    "geometry":             "Euclidean, non-Euclidean, trigonometry, vectors, coordinate geometry",
    "governance_decision_packet": "decision-making, governance, transparency, accountability, fiduciary",
    "history_chronology":   "historical events, dates, timelines, causation, periodization",
    "hydrology":            "water cycle, watersheds, runoff, groundwater, flood frequency",
    "information_theory":   "entropy, channel capacity, compression, Shannon, coding theory",
    "labor":                "labor economics, wages, unions, employment law, productivity",
    "law":                  "legal principles, common law, statutory interpretation, contracts, torts",
    "linguistics":          "phonology, morphology, syntax, semantics, pragmatics, language families",
    "manufacturing":        "processes, tolerances, quality control, lean, materials joining",
    "materials_science":    "crystal structure, phase diagrams, mechanical properties, failure analysis",
    "mathematics":          "algebra, calculus, number theory, topology, analysis, set theory",
    "medicine":             "anatomy, physiology, pathology, pharmacology, diagnostics, treatment",
    "meteorology":          "atmosphere, weather systems, thermodynamics, forecasting, climate",
    "music_theory":         "harmony, counterpoint, rhythm, form, scales, modes, voice leading",
    "networking":           "TCP/IP, routing, DNS, HTTP, TLS, load balancing, protocols",
    "nuclear_physics":      "radioactive decay, fission, fusion, half-life, radiation types",
    "number_theory":        "primes, modular arithmetic, Diophantine equations, cryptographic foundations",
    "nutrition":            "macronutrients, micronutrients, metabolism, dietary guidelines, RDAs",
    "oceanography":         "ocean circulation, salinity, tides, marine ecosystems, seafloor",
    "operations_research":  "linear programming, queuing, optimization, simulation, game theory",
    "optics":               "refraction, diffraction, lenses, interference, laser, fiber optics",
    "philosophy":           "epistemology, metaphysics, ethics, logic, political philosophy",
    "photography":          "exposure triangle, optics, sensors, composition, color theory",
    "physics_conservation": "conservation of energy, momentum, charge, mass-energy equivalence",
    "physics_dimensional":  "dimensional analysis, SI units, unit conversion, scaling laws",
    "quantum_computing":    "qubits, superposition, entanglement, quantum gates, algorithms",
    "real_estate":          "valuation, cap rate, ROI, zoning, financing, market analysis",
    "rhetoric":             "classical rhetoric, Aristotelian appeals, argument structure, style",
    "scripture_anchors":    "Bible verses, Scripture references, hermeneutics, biblical theology",
    "soil_science":         "soil classification, horizons, texture, pH, fertility, erosion",
    "sports_analytics":     "statistics, performance metrics, expected value, tracking data",
    "statistics_pvalue":    "p-values, hypothesis testing, null hypothesis, Type I/II errors",
    "statistics_multiple_comparisons": "Bonferroni, FDR, Benjamini-Hochberg, family-wise error",
    "statistics_confidence_interval":  "confidence intervals, margin of error, bootstrap, coverage",
    "theology_doctrine":    "systematic theology, doctrine, church history, creeds, confessions",
    "thermodynamics":       "laws of thermodynamics, entropy, enthalpy, Gibbs energy, cycles",
    "witness":              "eyewitness testimony, attestation, chain of custody, credibility standards",
}


def _haiku(prompt: str, max_tokens: int = 4096) -> List[str]:
    """Send one Haiku call; return parsed JSON array of strings."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            raw   = resp.content[0].text.strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start >= 0 and end > start:
                batch = json.loads(raw[start:end])
                return [str(s).strip() for s in batch if s and len(str(s)) > 20]
            print("  [WARN] JSON not found in response", flush=True)
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error: {e}", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"  [WARN] Haiku error: {e}", flush=True)
            time.sleep(3 * (attempt + 1))
    return []


def generate_hub(
    domain: str,
    neighbor_ctx: str,
) -> Optional[str]:
    """Generate the one broad hub claim for a domain.

    The hub is the domain's centre-of-gravity: the claim that everything
    else connects back to. It should be broad enough to link to adjacent
    domains but specific enough to be verifiable.
    """
    hints = DOMAIN_HINTS.get(domain, domain)
    prompt = (
        f"You are building the hub node for domain: {domain}\n"
        f"Topic hints: {hints}\n"
        f"{neighbor_ctx}\n\n"
        "Generate exactly 1 HUB seed: the single most central, broadly applicable, "
        "verifiable factual claim for this domain. It should:\n"
        "  • Connect to adjacent domains (span multiple sub-topics)\n"
        "  • Be specific enough to verify (include a formula, law, or measurement)\n"
        "  • Be broad enough that many specific claims branch from it\n"
        "Output ONLY a JSON array with 1 string. No markdown.\n\n"
        '["Hub claim here."]'
    )
    results = _haiku(prompt, max_tokens=512)
    return results[0] if results else None


def generate_spokes(
    domain: str,
    hub_text: str,
    count: int,
    neighbor_ctx: str,
    existing: Optional[List[str]] = None,
) -> List[str]:
    """Generate spoke seeds that branch from the hub.

    Each spoke is a specific sub-topic that connects back to the hub.
    The spokes collectively cover the territory around the hub.
    """
    hints = DOMAIN_HINTS.get(domain, domain)
    excl  = ""
    if existing:
        prior = "; ".join(s[:60] for s in existing[:20])
        excl  = f"\n\nALREADY GENERATED (do NOT repeat):\n{prior}"

    prompt = (
        f"You are building SPOKE seeds branching from this HUB for domain: {domain}\n"
        f"Topic hints: {hints}\n\n"
        f"HUB (every spoke must connect back to this):\n{hub_text}\n"
        f"{neighbor_ctx}"
        f"{excl}\n\n"
        f"Generate exactly {count} SPOKE seeds. Each spoke:\n"
        "  • Covers ONE specific sub-topic that branches from the hub\n"
        "  • Is 1-3 sentences, dense with facts (formulas, measurements, names)\n"
        "  • Is clearly distinct from all other spokes\n"
        "  • Should make a reader say 'that connects back to the hub'\n"
        f"Output ONLY a JSON array of {count} strings. No markdown.\n\n"
        '["Spoke one.", "Spoke two.", ...]'
    )
    seeds: List[str] = []
    while len(seeds) < count:
        n = min(SPOKE_BATCH, count - len(seeds))
        batch = _haiku(prompt.replace(f"exactly {count}", f"exactly {n}"), max_tokens=4096)
        seeds.extend(batch)
        if not batch:
            break
    return seeds[:count]


# ── Post ───────────────────────────────────────────────────────────────────────

def post_seed(
    text: str,
    domain: str,
    is_hub: bool,
    session: requests.Session,
    dry_run: bool,
) -> bool:
    title   = text[:72].rstrip() + ("…" if len(text) > 72 else "")
    tags    = [domain, "seed", "hub" if is_hub else "spoke", "smart_seed"]
    payload = {
        "title": title,
        "text":  text,
        "tags":  tags,
        "metadata": {
            "domain": domain,
            "source": "smart_seed",
            "node_type": "hub" if is_hub else "spoke",
        },
        "look_up_precedent": False,
        "calibrate": False,
    }
    if dry_run:
        node = "HUB  " if is_hub else "spoke"
        print(f"  [DRY/{node}] {title[:65]}", flush=True)
        return True
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=30)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"  [ERR] post: {e}", flush=True)
        return False


# ── State ──────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ── Domain runner ──────────────────────────────────────────────────────────────

def run_domain(
    domain: str,
    count: int,
    coverage: Dict[str, int],
    session: requests.Session,
    state: dict,
    dry_run: bool,
    delay: float,
) -> None:
    already = state.get(domain, {}).get("posted", 0)
    if already >= count:
        print(f"  {domain}: already done ({already}/{count})", flush=True)
        return

    remaining = count - already
    depth     = axis_depth(domain)
    neighbors = axis_neighbors(domain, top_k=4)
    nbr_str   = ", ".join(f"{n}({s:.2f})" for n, s in neighbors[:3])

    print(f"\n▶ {domain}  [verdicts={coverage.get(domain, 0)} depth={depth}]", flush=True)
    if nbr_str:
        print(f"  axis neighbors: {nbr_str}", flush=True)

    fp_set  = set(state.get(domain, {}).get("fingerprints", []))
    posted  = already

    # Pull hub context from warm neighbors
    existing_hub, neighbor_ctx = hub_context_for_domain(domain, coverage, session)

    # ── Phase 1: Hub ──────────────────────────────────────────────────────
    hub_text: Optional[str] = existing_hub  # reuse existing hub if present

    if not hub_text:
        print("  [PHASE 1] generating hub…", flush=True)
        hub_text = generate_hub(domain, neighbor_ctx)
        if hub_text:
            fp = fingerprint(hub_text)
            if fp not in fp_set:
                ok = post_seed(hub_text, domain, is_hub=True, session=session, dry_run=dry_run)
                if ok:
                    posted += 1
                    fp_set.add(fp)
                    print(f"  [HUB ✓] {hub_text[:80]}…", flush=True)
                    if delay > 0:
                        time.sleep(delay)
    else:
        print(f"  [HUB existing] {hub_text[:80]}", flush=True)

    if not hub_text:
        print("  [WARN] no hub generated — skipping spokes", flush=True)
        state[domain] = {"posted": posted, "fingerprints": list(fp_set)}
        save_state(state)
        return

    # ── Phase 2: Spokes ───────────────────────────────────────────────────
    spoke_target = remaining - (posted - already)  # how many spokes we still need
    if spoke_target <= 0:
        state[domain] = {"posted": posted, "fingerprints": list(fp_set)}
        save_state(state)
        return

    print(f"  [PHASE 2] generating {spoke_target} spokes from hub…", flush=True)
    spokes = generate_spokes(
        domain=domain,
        hub_text=hub_text,
        count=spoke_target,
        neighbor_ctx=neighbor_ctx,
        existing=state.get(domain, {}).get("spoke_texts", []),
    )

    spoke_texts_done = list(state.get(domain, {}).get("spoke_texts", []))

    for i, text in enumerate(spokes):
        if posted - already >= remaining:
            break
        fp = fingerprint(text)
        if fp in fp_set:
            continue
        ok = post_seed(text, domain, is_hub=False, session=session, dry_run=dry_run)
        if ok:
            posted += 1
            fp_set.add(fp)
            spoke_texts_done.append(text[:120])
            print(f"  [spoke {posted}/{count}] {text[:65]}…", flush=True)
        if delay > 0 and i < len(spokes) - 1:
            time.sleep(delay)

    state[domain] = {
        "posted":      posted,
        "fingerprints": list(fp_set),
        "spoke_texts": spoke_texts_done[-50:],  # keep last 50 for exclusion hints
    }
    save_state(state)
    print(f"  ✓ {domain}: {posted - already} new seeds (1 hub + spokes)", flush=True)


# ── Walk report ────────────────────────────────────────────────────────────────

def print_walk_report(domain: str, session: requests.Session) -> None:
    print(f"\n{'─'*60}")
    print(f"  GRAPH WALK from {domain}")
    print(f"{'─'*60}")
    cases = walk_from_domain(domain, session, top_k=8)
    if not cases:
        print("  (no cases indexed yet)")
        return
    for i, c in enumerate(cases):
        dist     = c.get("distance", "?")
        verdict  = c.get("verdict", "")
        dom      = c.get("domain", "")
        nbrs     = len(c.get("neighbors") or [])
        vs       = c.get("verifier_summary") or []
        note     = vs[0].get("note", "")[:80] if vs else ""
        print(f"  {i+1}. dist={dist:.3f}  {dom}  [{verdict}]  degree={nbrs}")
        if note:
            print(f"     {note}")
    print(f"{'─'*60}\n")


# ── Coverage report ────────────────────────────────────────────────────────────

def print_coverage_report(
    domains: List[str],
    coverage: Dict[str, int],
    session: requests.Session,
) -> None:
    ranked = coverage_priority(domains, coverage)
    cold   = [(d, v, dep) for d, v, dep in ranked if v == 0]
    cool   = [(d, v, dep) for d, v, dep in ranked if 0 < v < COOL_FLOOR]
    warm   = [(d, v, dep) for d, v, dep in ranked if v >= COOL_FLOOR]
    total  = sum(coverage.get(d, 0) for d in domains)

    # Fetch hub stats from API
    try:
        r = session.get(f"{API_BASE}/cases/stats", timeout=8)
        avg_degree = r.json().get("avg_degree", "?") if r.status_code == 200 else "?"
    except Exception:
        avg_degree = "?"

    print(f"\n{'═'*60}")
    print(f"  COVERAGE MAP   total={total:,}  avg_degree={avg_degree}")
    print(f"  cold={len(cold)}  cool={len(cool)}  warm={len(warm)}")
    print(f"{'═'*60}")

    if cold:
        print(f"\n  COLD — needs hub-and-spokes:")
        for d, v, dep in cold[:20]:
            nbrs = [n for n, _ in axis_neighbors(d, top_k=3)]
            print(f"    {d:<40} depth={dep}  adj={','.join(nbrs[:2])}")

    if cool:
        print(f"\n  COOL — hub exists, needs more spokes:")
        for d, v, dep in cool[:15]:
            print(f"    {d:<40} v={v:>4}  depth={dep}")

    print(f"\n  WARM (top 10 by verdicts):")
    for d, v, dep in sorted(warm, key=lambda x: -x[1])[:10]:
        print(f"    {d:<40} v={v:>4}  depth={dep}")

    print(f"\n  HIGHEST CONNECTIVITY (most axis neighbors at ≥0.4 Jaccard):")
    conn = sorted(
        [(d, len(axis_neighbors(d, top_k=20, min_sim=0.4))) for d in domains],
        key=lambda x: -x[1],
    )
    for d, n in conn[:8]:
        print(f"    {d:<40} neighbors={n:>2}  verdicts={coverage.get(d, 0):>4}")
    print(f"{'═'*60}\n")


# ── All canonical domains ──────────────────────────────────────────────────────

ALL_DOMAINS = list(DOMAIN_HINTS.keys())


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Hub-and-spoke convergence-aware seed generator."
    )
    ap.add_argument("--analyze",  action="store_true", help="Coverage + hub report, no posting")
    ap.add_argument("--fill",     action="store_true", help="Fill top-N coldest domains")
    ap.add_argument("--domain",   help="Seed a single domain")
    ap.add_argument("--walk",     help="Walk the graph from this domain's hub")
    ap.add_argument("--top",      type=int,   default=10,  help="Domains to fill (default 10)")
    ap.add_argument("--count",    type=int,   default=50,  help="Seeds per domain (default 50)")
    ap.add_argument("--delay",    type=float, default=0.2, help="Delay between posts (default 0.2)")
    ap.add_argument("--dry-run",  action="store_true",     help="Generate but don't post")
    ap.add_argument("--reset",    action="store_true",     help="Clear state")
    ap.add_argument("--url",      help="Override API base URL")
    args = ap.parse_args()

    global API_BASE
    if args.url:
        API_BASE = args.url

    if not ANTHROPIC_KEY and not args.dry_run and not args.analyze and not args.walk:
        sys.exit("Set ANTHROPIC_API_KEY environment variable")

    session  = requests.Session()
    coverage = get_coverage(session)

    if args.walk:
        print_walk_report(args.walk, session)
        return

    if args.analyze or not (args.fill or args.domain):
        print_coverage_report(ALL_DOMAINS, coverage, session)
        if args.analyze:
            return

    state = {} if args.reset else load_state()

    if args.domain:
        domains_to_run = [(args.domain, coverage.get(args.domain, 0), axis_depth(args.domain))]
    elif args.fill:
        domains_to_run = coverage_priority(ALL_DOMAINS, coverage, top_n=args.top)
    else:
        ap.print_help()
        return

    print(f"\n{'═'*60}")
    print(f"  SMART SEED (hub-and-spoke)  target={args.count}/domain  "
          f"domains={len(domains_to_run)}")
    print(f"{'═'*60}\n")

    for domain, verdicts, depth in domains_to_run:
        run_domain(
            domain=domain,
            count=args.count,
            coverage=coverage,
            session=session,
            state=state,
            dry_run=args.dry_run,
            delay=args.delay,
        )

    print(f"\n{'═'*60}")
    print("  DONE")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
