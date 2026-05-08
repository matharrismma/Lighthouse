"""
seed_generator.py — AI-powered domain seed generator
─────────────────────────────────────────────────────
Uses Claude Haiku to generate domain knowledge seeds and posts them
to the Concordance journal. Much faster than hand-writing seeds.

Usage:
  python scripts/seed/seed_generator.py --domain mathematics --count 100
  python scripts/seed/seed_generator.py --all --count 100 --delay 0.3
  python scripts/seed/seed_generator.py --all --count 100 --batch 20

State is tracked in seed_gen_state.json — re-runs skip finished domains.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time
from pathlib import Path

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

API_BASE   = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "seed_gen_state.json"

# Load API key: env var > .env file
def _load_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if k:
        return k
    # Walk up from script dir looking for .env
    for d in [Path(__file__).parent, Path(__file__).parent.parent.parent]:
        env_file = d / ".env"
        if env_file.exists():
            for line in env_file.read_text("utf-8", errors="replace").splitlines():
                m = re.match(r"ANTHROPIC_API_KEY=(.+)", line.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'")
    return ""

ANTHROPIC_KEY = _load_key()

# All 60 verifier domains
ALL_DOMAINS = [
    "acoustics", "agriculture", "architecture", "astronomy", "biology",
    "calendar_time", "chemistry", "combinatorics", "computer_science",
    "construction", "cryptography", "cybersecurity", "document_validation",
    "ecology", "economics", "electrical", "energy", "exercise_science",
    "finance", "formal_logic", "genetics", "geography", "geology",
    "geometry", "governance_decision_packet", "history_chronology",
    "hydrology", "information_theory", "labor", "law", "linguistics",
    "manufacturing", "materials_science", "mathematics", "medicine",
    "meteorology", "music_theory", "networking", "nuclear_physics",
    "number_theory", "nutrition", "oceanography", "operations_research",
    "optics", "philosophy", "photography", "physics_conservation",
    "physics_dimensional", "quantum_computing", "real_estate", "rhetoric",
    "scripture_anchors", "soil_science", "sports_analytics",
    "statistics_pvalue", "statistics_multiple_comparisons",
    "statistics_confidence_interval", "theology_doctrine", "thermodynamics",
    "witness",
]

DOMAIN_HINTS = {
    "acoustics": "sound waves, acoustics, decibels, Fourier, room acoustics, hearing",
    "agriculture": "crops, soil, irrigation, yield, farming, agronomy, pest management",
    "architecture": "building design, structural systems, materials, codes, space planning",
    "astronomy": "stars, galaxies, orbital mechanics, cosmology, spectra, telescopes",
    "biology": "cells, metabolism, evolution, genetics, ecology, physiology, taxonomy",
    "calendar_time": "timekeeping, calendar systems, epochs, UTC, leap years, ISO 8601",
    "chemistry": "chemical reactions, bonding, stoichiometry, thermodynamics, kinetics",
    "combinatorics": "counting, permutations, combinations, graph theory, probability",
    "computer_science": "algorithms, data structures, complexity, paradigms, systems",
    "construction": "structural engineering, materials, codes, project management, foundations",
    "cryptography": "encryption, hashing, public-key, RSA, ECC, protocols, PKI",
    "cybersecurity": "threats, defenses, OWASP, network security, incident response",
    "document_validation": "provenance, signatures, notarization, chain of custody, attestation",
    "ecology": "ecosystems, food webs, succession, biodiversity, nutrient cycles",
    "economics": "supply/demand, macro, micro, monetary policy, trade, markets",
    "electrical": "circuits, Ohm's law, AC/DC, capacitors, inductors, power systems",
    "energy": "thermodynamics, renewables, fossil fuels, efficiency, storage, grid",
    "exercise_science": "physiology, biomechanics, training principles, VO2 max, EPOC",
    "finance": "time value of money, DCF, bonds, equities, risk, portfolio theory",
    "formal_logic": "propositional logic, predicate logic, inference rules, proofs, paradoxes",
    "genetics": "DNA, RNA, transcription, translation, Mendelian inheritance, mutations",
    "geography": "cartography, climate zones, plate tectonics, population, geopolitics",
    "geology": "rock cycle, plate tectonics, stratigraphy, mineralogy, geologic time",
    "geometry": "Euclidean, non-Euclidean, trigonometry, vectors, coordinate geometry",
    "governance_decision_packet": "decision-making, governance, transparency, accountability, fiduciary",
    "history_chronology": "historical events, dates, timelines, causation, periodization",
    "hydrology": "water cycle, watersheds, runoff, groundwater, flood frequency",
    "information_theory": "entropy, channel capacity, compression, Shannon, coding theory",
    "labor": "labor economics, wages, unions, employment law, productivity",
    "law": "legal principles, common law, statutory interpretation, contracts, torts",
    "linguistics": "phonology, morphology, syntax, semantics, pragmatics, language families",
    "manufacturing": "processes, tolerances, quality control, lean, materials joining",
    "materials_science": "crystal structure, phase diagrams, mechanical properties, failure",
    "mathematics": "algebra, calculus, number theory, topology, analysis, set theory",
    "medicine": "anatomy, physiology, pathology, pharmacology, diagnostics, treatment",
    "meteorology": "atmosphere, weather systems, thermodynamics, forecasting, climate",
    "music_theory": "harmony, counterpoint, rhythm, form, scales, modes, voice leading",
    "networking": "TCP/IP, routing, DNS, HTTP, TLS, load balancing, protocols",
    "nuclear_physics": "radioactive decay, fission, fusion, half-life, radiation types",
    "number_theory": "primes, modular arithmetic, Diophantine equations, cryptographic foundations",
    "nutrition": "macronutrients, micronutrients, metabolism, dietary guidelines, RDAs",
    "oceanography": "ocean circulation, salinity, tides, marine ecosystems, seafloor",
    "operations_research": "linear programming, queuing, optimization, simulation, game theory",
    "optics": "refraction, diffraction, lenses, interference, laser, fiber optics",
    "philosophy": "epistemology, metaphysics, ethics, logic, political philosophy",
    "photography": "exposure triangle, optics, sensors, composition, color theory",
    "physics_conservation": "conservation of energy, momentum, charge, mass-energy equivalence",
    "physics_dimensional": "dimensional analysis, SI units, unit conversion, scaling laws",
    "quantum_computing": "qubits, superposition, entanglement, quantum gates, algorithms",
    "real_estate": "valuation, cap rate, ROI, zoning, financing, market analysis",
    "rhetoric": "classical rhetoric, Aristotelian appeals, argument structure, style",
    "scripture_anchors": "Bible verses, Scripture references, hermeneutics, biblical theology",
    "soil_science": "soil classification, horizons, texture, pH, fertility, erosion",
    "sports_analytics": "statistics, performance metrics, expected value, tracking data",
    "statistics_pvalue": "p-values, hypothesis testing, null hypothesis, Type I/II errors",
    "statistics_multiple_comparisons": "Bonferroni, FDR, Benjamini-Hochberg, family-wise error",
    "statistics_confidence_interval": "confidence intervals, margin of error, bootstrap, coverage",
    "theology_doctrine": "systematic theology, doctrine, church history, creeds, confessions",
    "thermodynamics": "laws of thermodynamics, entropy, enthalpy, Gibbs energy, cycles",
    "witness": "eyewitness testimony, attestation, chain of custody, credibility standards",
}


_active_state_file: Path = STATE_FILE


def load_state() -> dict:
    if _active_state_file.exists():
        try:
            return json.loads(_active_state_file.read_text("utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict):
    _active_state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def generate_seeds(domain: str, count: int, batch_size: int = 75,
                   existing: list[str] = None) -> list[str]:
    """Use Claude Haiku to generate domain knowledge seeds.

    Uses large batches (default 75) to minimize API round-trips and pass
    previously-generated seeds as exclusions so each batch is diverse.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    hints = DOMAIN_HINTS.get(domain, domain)
    seeds = list(existing or [])

    while len(seeds) < count:
        n = min(batch_size, count - len(seeds))
        if n <= 0:
            break

        # Build exclusion hint from already-generated seeds to reduce dups
        excl = ""
        if seeds:
            # Summarize first words of each existing seed as exclusion hint
            prior_topics = "; ".join(s[:60] for s in seeds[:30])
            excl = f"\n\nALREADY COVERED (do NOT repeat these topics):\n{prior_topics}\n"

        prompt = f"""Generate exactly {n} distinct, factual knowledge seeds for the domain: {domain}
Topic hints: {hints}{excl}
Rules:
- Each seed is 1-3 sentences of dense, accurate factual content
- Cover DIFFERENT sub-topics — no repeats of already-covered content
- Be specific: include formulas, numbers, names, laws, dates where applicable
- Do NOT start multiple seeds with the same opening phrase
- Output ONLY a JSON array of {n} strings, nothing else
- No markdown, no preamble, just the JSON array

["Seed text one here.", "Seed text two here.", ...]"""

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                batch = json.loads(raw[start:end])
                new = [str(s).strip() for s in batch
                       if s and len(str(s)) > 20]
                seeds.extend(new)
            else:
                print(f"  [WARN] could not parse JSON from response", flush=True)
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error for {domain}: {e}", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"  [WARN] API error for {domain}: {e}", flush=True)
            time.sleep(3)

    return seeds[:count]


def post_seed(text: str, domain: str, session: requests.Session, dry_run: bool) -> bool:
    """Post a single seed to /capture. Returns True on success."""
    title = text[:72].rstrip() + ("…" if len(text) > 72 else "")
    payload = {
        "title": title,
        "text": text,
        "tags": [domain, "seed", "generated"],
        "metadata": {"domain": domain, "source": "seed_generator"},
        # Skip expensive O(n) per-entry operations — seeds don't need
        # precedent lookup or calibration; we just want fast ingestion.
        "look_up_precedent": False,
        "calibrate": False,
    }
    if dry_run:
        print(f"  [DRY] {domain}: {title[:60]}", flush=True)
        return True
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=30)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"  [ERR] {e}", flush=True)
        return False


def run_domain(domain: str, count: int, delay: float, batch: int,
               dry_run: bool, state: dict):
    done = state.get(domain, {}).get("posted", 0)
    if done >= count:
        print(f"  {domain}: already done ({done}/{count})", flush=True)
        return

    remaining = count - done
    print(f"\n▶ {domain}: generating {remaining} seeds...", flush=True)

    existing_fps = state.get(domain, {}).get("fingerprints", [])
    seeds = generate_seeds(domain, remaining, batch_size=batch)
    if not seeds:
        print(f"  [WARN] no seeds generated for {domain}", flush=True)
        return

    session = requests.Session()
    posted = done
    fp_set = set(state.get(domain, {}).get("fingerprints", []))

    for i, text in enumerate(seeds):
        fp = fingerprint(text)
        if fp in fp_set:
            continue
        ok = post_seed(text, domain, session, dry_run)
        if ok:
            posted += 1
            fp_set.add(fp)
            print(f"  [{posted}/{count}] {domain}: {text[:60]}…", flush=True)
        if delay > 0 and i < len(seeds) - 1:
            time.sleep(delay)

    state[domain] = {"posted": posted, "fingerprints": list(fp_set)}
    save_state(state)
    print(f"  ✓ {domain}: {posted} seeds total", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", help="Single domain to seed")
    ap.add_argument("--domains", help="Comma-separated list of domains to seed")
    ap.add_argument("--all", action="store_true", help="Seed all domains")
    ap.add_argument("--count", type=int, default=100, help="Seeds per domain (default 100)")
    ap.add_argument("--delay", type=float, default=0.3, help="Delay between posts (default 0.3)")
    ap.add_argument("--batch", type=int, default=20, help="Generation batch size (default 20)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset", action="store_true", help="Clear state and start fresh")
    ap.add_argument("--url", help="Override API URL")
    ap.add_argument("--state-file", help="Path to state JSON (default: seed_gen_state.json)")
    args = ap.parse_args()

    global API_BASE, _active_state_file
    if args.url:
        API_BASE = args.url
    if args.state_file:
        _active_state_file = Path(args.state_file)

    if not ANTHROPIC_KEY and not args.dry_run:
        sys.exit("Set ANTHROPIC_API_KEY environment variable")

    state = {} if args.reset else load_state()

    if args.all:
        domains = ALL_DOMAINS
    elif args.domains:
        domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    elif args.domain:
        domains = [args.domain]
    else:
        domains = []
    if not domains:
        ap.print_help(); sys.exit(1)

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f" Concordance seed generator")
    print(f" API: {API_BASE}")
    print(f" Domains: {len(domains)}  Count: {args.count}  Delay: {args.delay}s")
    print(f" Dry run: {args.dry_run}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for domain in domains:
        run_domain(domain, args.count, args.delay, args.batch, args.dry_run, state)

    # Final count
    total = sum(v.get("posted", 0) for v in state.values())
    print(f"\n✅ Done. Total seeds posted this run: {total}")
    try:
        h = requests.get(f"{API_BASE}/health", timeout=5).json()
        journal_total = h["modules"]["journal"]["total_entries"]
        print(f"   Journal total: {journal_total}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
