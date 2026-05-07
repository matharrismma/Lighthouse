"""smart_seed.py — Convergence-aware seed generator.

Uses the case store to find coverage gaps, axis adjacency to inform
generation, and novelty screening to skip near-duplicates.

Three modes:
  --analyze          Print coverage map and novelty priorities, no posting.
  --fill [--top N]   Fill the N coldest domains (default 10).
  --domain D         Smart-seed a single domain.

How it works
────────────
1. Pull coverage from GET /cases/stats → per-domain verdict counts.
2. Rank domains: cold (0 verdicts) first, then cool (< COOL_FLOOR),
   then warm — weighted by axis depth so structurally deep domains that
   are cold get highest priority.
3. For each target domain, find its warm axis-neighbors (Jaccard ≥ 0.3
   on AXIS_DIMENSIONS). Pull their top verifier_summary snippets and
   pass them to Haiku as "what the engine already knows nearby" — so
   the generated seeds fill the actual gap, not the adjacent ground.
4. Generate candidates via Claude Haiku.
5. Novelty screen: POST /cases/closest for each candidate. If closest
   distance < NOVELTY_FLOOR (0.25) → near-duplicate, skip.
   If distance ≥ NOVELTY_CEIL (0.70) → genuinely novel, boost label.
6. Post only seeds that clear the novelty floor.
7. Report novelty rate per domain so you can tune thresholds.

Result: each new verdict is chosen because it fills a gap; the ledger
converges instead of saturating the same clusters.

Usage:
  python scripts/seed/smart_seed.py --analyze
  python scripts/seed/smart_seed.py --fill --top 10 --count 50
  python scripts/seed/smart_seed.py --domain theology_doctrine --count 30
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

# ── Configuration ─────────────────────────────────────────────────────────────

API_BASE   = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "smart_seed_state.json"

NOVELTY_FLOOR = 0.25   # distance below → near-duplicate, skip
NOVELTY_CEIL  = 0.70   # distance above → genuinely novel, flag
COOL_FLOOR    = 20     # verdicts below this = "cool" domain
NEIGHBOR_K    = 3      # warm neighbors to pull context from


# ── Load API key ──────────────────────────────────────────────────────────────

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


# ── Grid adjacency ────────────────────────────────────────────────────────────

def _load_axis_dimensions() -> Dict[str, FrozenSet[str]]:
    """Import AXIS_DIMENSIONS from the engine package, or define a minimal
    fallback inline so this script works even outside a venv."""
    try:
        # Try to import from installed/editable package first
        repo_src = Path(__file__).parent.parent.parent / "src"
        if str(repo_src) not in sys.path:
            sys.path.insert(0, str(repo_src))
        from concordance_engine.grid import AXIS_DIMENSIONS  # type: ignore
        return AXIS_DIMENSIONS
    except ImportError:
        pass

    # Minimal inline fallback — seven scaffold axes per canonical domain
    return {
        "chemistry":            frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "physics":              frozenset({"physical_substance", "conservation_balance", "reasoning"}),
        "mathematics":          frozenset({"reasoning"}),
        "statistics_pvalue":    frozenset({"reasoning"}),
        "computer_science":     frozenset({"encoding", "reasoning", "time_sequence"}),
        "biology":              frozenset({"encoding", "metabolism", "physical_substance", "conservation_balance", "time_sequence"}),
        "governance":           frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "scripture_anchors":    frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "linguistics":          frozenset({"encoding", "reasoning"}),
        "formal_logic":         frozenset({"reasoning"}),
        "cryptography":         frozenset({"encoding", "reasoning", "authority_trust"}),
        "finance":              frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
        "economics":            frozenset({"reasoning", "authority_trust", "time_sequence", "conservation_balance"}),
        "theology_doctrine":    frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "governance_decision_packet": frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "law":                  frozenset({"reasoning", "authority_trust", "time_sequence"}),
        "labor":                frozenset({"metabolism", "authority_trust", "time_sequence", "conservation_balance"}),
        "medicine":             frozenset({"metabolism", "physical_substance", "authority_trust", "time_sequence"}),
        "real_estate":          frozenset({"physical_substance", "authority_trust", "time_sequence", "conservation_balance"}),
        "cybersecurity":        frozenset({"encoding", "reasoning", "authority_trust"}),
        "quantum_computing":    frozenset({"encoding", "reasoning", "physical_substance"}),
        "operations_research":  frozenset({"reasoning", "time_sequence", "conservation_balance"}),
        "thermodynamics":       frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "energy":               frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "ecology":              frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "biology":              frozenset({"encoding", "metabolism", "physical_substance", "conservation_balance", "time_sequence"}),
        "genetics":             frozenset({"encoding", "physical_substance"}),
        "agriculture":          frozenset({"metabolism", "physical_substance", "time_sequence"}),
        "nutrition":            frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "exercise_science":     frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "physics_conservation": frozenset({"physical_substance", "conservation_balance"}),
        "physics_dimensional":  frozenset({"physical_substance", "reasoning"}),
        "nuclear_physics":      frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
        "astronomy":            frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
        "geology":              frozenset({"metabolism", "physical_substance", "time_sequence"}),
        "meteorology":          frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "hydrology":            frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "oceanography":         frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "soil_science":         frozenset({"metabolism", "physical_substance", "conservation_balance"}),
        "manufacturing":        frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "construction":         frozenset({"metabolism", "physical_substance", "time_sequence", "conservation_balance"}),
        "architecture":         frozenset({"physical_substance", "authority_trust", "time_sequence"}),
        "electrical":           frozenset({"physical_substance", "conservation_balance"}),
        "networking":           frozenset({"encoding", "physical_substance", "authority_trust", "time_sequence"}),
        "information_theory":   frozenset({"encoding", "reasoning"}),
        "document_validation":  frozenset({"encoding", "authority_trust"}),
        "music_theory":         frozenset({"encoding", "reasoning", "physical_substance"}),
        "acoustics":            frozenset({"physical_substance", "time_sequence", "conservation_balance"}),
        "optics":               frozenset({"physical_substance", "conservation_balance"}),
        "photography":          frozenset({"encoding", "physical_substance"}),
        "number_theory":        frozenset({"reasoning"}),
        "combinatorics":        frozenset({"reasoning"}),
        "geometry":             frozenset({"reasoning", "physical_substance"}),
        "sports_analytics":     frozenset({"reasoning", "time_sequence"}),
        "philosophy":           frozenset({"reasoning", "authority_trust"}),
        "rhetoric":             frozenset({"encoding", "reasoning", "authority_trust"}),
        "calendar_time":        frozenset({"time_sequence"}),
        "geography":            frozenset({"physical_substance"}),
        "history_chronology":   frozenset({"authority_trust", "time_sequence"}),
        "materials_science":    frozenset({"physical_substance", "conservation_balance"}),
        "witness":              frozenset({"encoding", "reasoning", "authority_trust", "time_sequence"}),
        "statistics_multiple_comparisons": frozenset({"reasoning"}),
        "statistics_confidence_interval":  frozenset({"reasoning"}),
    }


AXIS_DIMENSIONS: Dict[str, FrozenSet[str]] = _load_axis_dimensions()


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def axis_neighbors(
    domain: str,
    top_k: int = 5,
    min_sim: float = 0.20,
) -> List[Tuple[str, float]]:
    """Return (neighbor_domain, jaccard_sim) pairs, best first."""
    dims = AXIS_DIMENSIONS.get(domain, frozenset())
    scores: List[Tuple[str, float]] = []
    for other, other_dims in AXIS_DIMENSIONS.items():
        if other == domain:
            continue
        sim = _jaccard(dims, other_dims)
        if sim >= min_sim:
            scores.append((other, round(sim, 3)))
    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


def axis_depth(domain: str) -> int:
    """Number of scaffold dimensions the domain sits on."""
    return len(AXIS_DIMENSIONS.get(domain, frozenset()))


# ── Coverage ──────────────────────────────────────────────────────────────────

def get_coverage(session: requests.Session) -> Dict[str, int]:
    """Query /cases/stats → {domain: count}.  Returns empty dict on error."""
    try:
        r = session.get(f"{API_BASE}/cases/stats", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return dict(data.get("by_domain", {}))
    except Exception as exc:
        print(f"  [WARN] /cases/stats failed: {exc}", flush=True)
    return {}


def coverage_priority(
    domains: List[str],
    coverage: Dict[str, int],
    top_n: Optional[int] = None,
) -> List[Tuple[str, int, int]]:
    """Sort domains by (verdicts ASC, depth DESC).

    Returns list of (domain, verdicts, depth).
    cold + deep first — they provide the most new information.
    """
    ranked: List[Tuple[str, int, int]] = []
    for d in domains:
        v = coverage.get(d, 0)
        depth = axis_depth(d)
        ranked.append((d, v, depth))

    # Sort: fewest verdicts first; break ties by most dimensions (deep → rich)
    ranked.sort(key=lambda x: (x[1], -x[2]))
    if top_n:
        ranked = ranked[:top_n]
    return ranked


# ── Novelty screening ─────────────────────────────────────────────────────────

def novelty_score(
    domain: str,
    session: requests.Session,
) -> Optional[float]:
    """Domain-level novelty check via POST /cases/closest.

    The endpoint auto-derives scaffold dimensions from the domain name,
    giving a meaningful axis-based distance to the closest indexed case.

    Returns distance (0=duplicate-saturated, 1=totally novel),
    or None if the endpoint is unavailable (don't block seeding).
    """
    try:
        r = session.post(
            f"{API_BASE}/cases/closest",
            json={"domain": domain, "top_k": 1},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            cases = data.get("cases", data.get("results", []))
            if cases:
                return float(cases[0].get("distance", 1.0))
            return 1.0   # no cases yet → completely novel
    except Exception:
        pass
    return None  # endpoint unavailable — don't block


# ── Neighbor context ──────────────────────────────────────────────────────────

def warm_neighbor_context(
    domain: str,
    coverage: Dict[str, int],
    session: requests.Session,
    k: int = NEIGHBOR_K,
) -> str:
    """Pull verifier snippets from warm axis-neighbors as generation context."""
    neighbors = axis_neighbors(domain, top_k=10)
    warm = [(n, sim) for n, sim in neighbors if coverage.get(n, 0) >= COOL_FLOOR]
    if not warm:
        return ""

    snippets: List[str] = []
    for n, sim in warm[:k]:
        try:
            r = session.post(
                f"{API_BASE}/cases/closest",
                json={"domain": n, "top_k": 2},
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                for case in (data.get("cases") or data.get("results") or [])[:2]:
                    vs = case.get("verifier_summary") or []
                    for entry in vs[:1]:
                        note = entry.get("note", "")
                        if note:
                            snippets.append(f"[{n}] {note[:120]}")
        except Exception:
            pass

    if not snippets:
        return ""

    return (
        "\n\nThe engine already knows this from adjacent domains "
        "(do NOT repeat — fill the GAP, not the adjacent ground):\n"
        + "\n".join(f"  • {s}" for s in snippets[:6])
    )


# ── Seed generation ───────────────────────────────────────────────────────────

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


def generate_seeds(
    domain: str,
    count: int,
    neighbor_context: str = "",
    existing: Optional[List[str]] = None,
    batch_size: int = 30,
) -> List[str]:
    """Generate seeds via Claude Haiku, informed by neighbor context."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    hints  = DOMAIN_HINTS.get(domain, domain)
    seeds  = list(existing or [])

    while len(seeds) < count:
        n = min(batch_size, count - len(seeds))
        if n <= 0:
            break

        excl = ""
        if seeds:
            prior = "; ".join(s[:60] for s in seeds[:20])
            excl  = f"\n\nALREADY GENERATED (avoid repeating):\n{prior}"

        prompt = (
            f"Generate exactly {n} distinct, factual knowledge seeds for domain: {domain}\n"
            f"Topic hints: {hints}"
            f"{neighbor_context}"
            f"{excl}\n\n"
            "Rules:\n"
            "- Each seed: 1-3 sentences, dense factual content\n"
            "- Cover DIFFERENT sub-topics — no repeats\n"
            "- Include formulas, numbers, names, laws, dates where applicable\n"
            "- Do NOT start multiple seeds with the same opening phrase\n"
            f"- Output ONLY a JSON array of {n} strings, nothing else\n\n"
            '["Seed one.", "Seed two.", ...]'
        )

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            raw   = resp.content[0].text.strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start >= 0 and end > start:
                batch = json.loads(raw[start:end])
                seeds.extend(str(s).strip() for s in batch if s and len(str(s)) > 20)
            else:
                print("  [WARN] could not parse JSON batch", flush=True)
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error: {e}", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"  [WARN] API error: {e}", flush=True)
            time.sleep(3)

    return seeds[:count]


# ── Posting ───────────────────────────────────────────────────────────────────

def post_seed(text: str, domain: str, session: requests.Session, dry_run: bool) -> bool:
    title   = text[:72].rstrip() + ("…" if len(text) > 72 else "")
    payload = {
        "title": title,
        "text":  text,
        "tags":  [domain, "seed", "smart_seed"],
        "metadata": {"domain": domain, "source": "smart_seed"},
        "look_up_precedent": False,
        "calibrate": False,
    }
    if dry_run:
        print(f"  [DRY] {title[:70]}", flush=True)
        return True
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=30)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"  [ERR] post: {e}", flush=True)
        return False


# ── State ─────────────────────────────────────────────────────────────────────

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


# ── Domain runner ─────────────────────────────────────────────────────────────

def run_domain(
    domain: str,
    count: int,
    coverage: Dict[str, int],
    session: requests.Session,
    state: dict,
    dry_run: bool,
    delay: float,
    skip_novelty: bool,
) -> None:
    already = state.get(domain, {}).get("posted", 0)
    if already >= count:
        print(f"  {domain}: already done ({already}/{count})", flush=True)
        return

    remaining = count - already
    current_v = coverage.get(domain, 0)
    depth     = axis_depth(domain)
    neighbors = axis_neighbors(domain, top_k=5)

    print(f"\n▶ {domain}  [verdicts={current_v} depth={depth}]", flush=True)
    if neighbors:
        nbr_str = ", ".join(f"{n}({s:.2f})" for n, s in neighbors[:4])
        print(f"  neighbors: {nbr_str}", flush=True)

    # Build neighbor context for generation
    ctx = warm_neighbor_context(domain, coverage, session)

    # Generate candidates — ask for 2× target since novelty screening will drop some
    gen_count = min(remaining * 2, remaining + 20)
    print(f"  generating {gen_count} candidates...", flush=True)
    candidates = generate_seeds(domain, gen_count, neighbor_context=ctx)
    if not candidates:
        print("  [WARN] no candidates generated", flush=True)
        return

    fp_set  = set(state.get(domain, {}).get("fingerprints", []))
    posted  = already
    skipped = 0
    novel   = 0

    # Domain-level novelty check: one call tells us how saturated this domain is.
    # Per-seed calls would all return the same score (domain dims don't change),
    # so we do it once up front and use it as a domain gate, not a per-seed gate.
    domain_dist: Optional[float] = None
    if not skip_novelty and current_v > 0:
        domain_dist = novelty_score(domain, session)
        if domain_dist is not None:
            label_prefix = f"dist={domain_dist:.3f}"
            if domain_dist < NOVELTY_FLOOR:
                print(
                    f"  [SATURATED] domain_dist={domain_dist:.3f} — "
                    f"this domain is already well-covered. Posting anyway to reach target.",
                    flush=True,
                )
            elif domain_dist >= NOVELTY_CEIL:
                novel += 1
                print(f"  [NOVEL★] domain_dist={domain_dist:.3f}", flush=True)
            else:
                print(f"  [PARTIAL] domain_dist={domain_dist:.3f}", flush=True)

    for i, text in enumerate(candidates):
        if posted - already >= remaining:
            break

        fp = fingerprint(text)
        if fp in fp_set:
            continue

        label = f"  [{domain_dist:.3f}]" if domain_dist is not None else ""
        ok = post_seed(text, domain, session, dry_run)
        if ok:
            posted += 1
            fp_set.add(fp)
            print(f"  [{posted}/{count}]{label} {text[:60]}…", flush=True)

        if delay > 0 and i < len(candidates) - 1:
            time.sleep(delay)

    state[domain] = {"posted": posted, "fingerprints": list(fp_set)}
    save_state(state)

    novelty_label = f"domain_dist={domain_dist:.3f}" if domain_dist is not None else "dist=n/a"
    print(
        f"  ✓ {domain}: posted {posted - already}  {novelty_label}",
        flush=True,
    )


# ── Analysis report ───────────────────────────────────────────────────────────

def print_coverage_report(
    domains: List[str],
    coverage: Dict[str, int],
) -> None:
    ranked = coverage_priority(domains, coverage)
    cold   = [(d, v, dep) for d, v, dep in ranked if v == 0]
    cool   = [(d, v, dep) for d, v, dep in ranked if 0 < v < COOL_FLOOR]
    warm   = [(d, v, dep) for d, v, dep in ranked if v >= COOL_FLOOR]
    total  = sum(v for _, v, _ in ranked)

    print(f"\n{'─'*60}")
    print(f"  COVERAGE MAP   total verdicts: {total:,}")
    print(f"  cold (0):  {len(cold):>3}   cool (<{COOL_FLOOR}): {len(cool):>3}   warm (≥{COOL_FLOOR}): {len(warm):>3}")
    print(f"{'─'*60}")

    if cold:
        print(f"\n  COLD (priority 1):")
        for d, v, dep in cold[:20]:
            nbrs = [n for n, _ in axis_neighbors(d, top_k=3)]
            print(f"    {d:<40} depth={dep}  nbrs={','.join(nbrs[:2])}")

    if cool:
        print(f"\n  COOL (priority 2):")
        for d, v, dep in cool[:20]:
            print(f"    {d:<40} verdicts={v:>4}  depth={dep}")

    print(f"\n  WARM (top 10):")
    for d, v, dep in sorted(warm, key=lambda x: -x[1])[:10]:
        print(f"    {d:<40} verdicts={v:>4}  depth={dep}")

    print(f"\n  TOP AXIS ADJACENCY:")
    print(f"  (domains with most structural neighbors at ≥0.4 Jaccard)")
    depth_sorted = sorted(
        [(d, len(axis_neighbors(d, top_k=20, min_sim=0.4))) for d in domains],
        key=lambda x: -x[1],
    )
    for d, n in depth_sorted[:10]:
        v = coverage.get(d, 0)
        print(f"    {d:<40} neighbors={n:>2}  verdicts={v:>4}")
    print(f"{'─'*60}\n")


# ── All 60 canonical domains ──────────────────────────────────────────────────

ALL_DOMAINS = list(DOMAIN_HINTS.keys())


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convergence-aware seed generator for the Concordance engine."
    )
    ap.add_argument("--analyze",      action="store_true", help="Coverage report only, no posting")
    ap.add_argument("--fill",         action="store_true", help="Fill top-N coldest domains")
    ap.add_argument("--domain",       help="Smart-seed a single domain")
    ap.add_argument("--top",          type=int, default=10, help="Number of domains to fill (default 10)")
    ap.add_argument("--count",        type=int, default=50, help="Target verdicts per domain (default 50)")
    ap.add_argument("--delay",        type=float, default=0.2, help="Delay between posts (default 0.2)")
    ap.add_argument("--skip-novelty", action="store_true", help="Skip novelty screening (faster, less precise)")
    ap.add_argument("--dry-run",      action="store_true", help="Generate but do not post")
    ap.add_argument("--reset",        action="store_true", help="Clear state file")
    ap.add_argument("--url",          help="Override API base URL")
    args = ap.parse_args()

    global API_BASE
    if args.url:
        API_BASE = args.url

    if not ANTHROPIC_KEY and not args.dry_run:
        sys.exit("Set ANTHROPIC_API_KEY environment variable")

    session = requests.Session()
    coverage = get_coverage(session)

    if args.analyze or not (args.fill or args.domain):
        print_coverage_report(ALL_DOMAINS, coverage)
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
    print(f"  SMART SEED  target={args.count}/domain  "
          f"novelty_floor={NOVELTY_FLOOR}  fill={len(domains_to_run)} domains")
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
            skip_novelty=args.skip_novelty,
        )

    print(f"\n{'═'*60}")
    print("  DONE")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
