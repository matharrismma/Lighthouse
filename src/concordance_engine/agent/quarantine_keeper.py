"""Quarantine Keeper — ultra-low-power triage for the airlock.

The quarantine state holds claims that were stripped (decomposed) but
couldn't be classified to any domain. They are airlocked: not wrong,
not confirmed, just unverifiable with the information available.

The keeper tends the airlock. It:
  1. Attempts rule-based recovery — runs each claim through the existing
     dispatch rules (zero cost, offline-capable). Any that match a rule
     are recovered immediately; no oracle needed.
  2. Finds nearest domain by keyword overlap — each unrecovered claim is
     scored against domain keyword sets. Nearest domain is recorded as a
     hint for future dispatch or manual triage.
  3. Clusters unrecovered claims by shared keywords — groups orphans so
     a human or future oracle can handle them as a batch.

Ultra-low-power contract:
  * NO oracle calls. NO LLM calls. NO network calls.
  * Pure Python, no external dependencies.
  * Deterministic. Idempotent. Works offline.
  * Suitable for LoRa mesh node, microSD, or constrained deployment.

The keeper does not resolve quarantine — it organizes it. Resolution
happens when either a new dispatch rule is added (recovery on next run)
or a human provides the missing information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# ── Domain keyword index ────────────────────────────────────────────────
# Lightweight keyword sets for domain proximity scoring.
# Deliberately minimal — the keeper's job is to connect, not classify.

_DOMAIN_KEYWORDS: Dict[str, FrozenSet[str]] = {
    "mathematics":      frozenset({"integral", "derivative", "equation", "formula", "calculate", "sum", "product", "proof", "theorem", "value", "equals", "solve"}),
    "chemistry":        frozenset({"molecule", "compound", "reaction", "element", "bond", "molar", "mass", "pH", "acid", "base", "solution", "oxidation", "reduction"}),
    "physics":          frozenset({"force", "velocity", "acceleration", "energy", "momentum", "mass", "gravity", "wave", "field", "charge", "pressure", "power"}),
    "biology":          frozenset({"cell", "organism", "dna", "protein", "gene", "evolution", "species", "metabolism", "tissue", "organ", "ecosystem"}),
    "genetics":         frozenset({"allele", "genotype", "phenotype", "dominant", "recessive", "chromosome", "mutation", "heredity", "trait", "locus", "homozygous", "heterozygous"}),
    "agriculture":      frozenset({"crop", "soil", "fertilizer", "yield", "harvest", "irrigation", "pest", "seed", "plant", "farm", "grow", "season", "drought"}),
    "nutrition":        frozenset({"calorie", "protein", "carbohydrate", "fat", "vitamin", "mineral", "diet", "nutrient", "fiber", "intake", "food"}),
    "medicine":         frozenset({"diagnosis", "treatment", "symptom", "disease", "patient", "dose", "drug", "therapy", "clinical", "injury", "pain", "chronic"}),
    "labor":            frozenset({"wage", "overtime", "salary", "hour", "flsa", "employee", "employer", "exempt", "contractor", "pay", "work", "classification"}),
    "governance":       frozenset({"vote", "rule", "policy", "authority", "law", "decision", "committee", "majority", "quorum", "governance", "organization"}),
    "finance":          frozenset({"interest", "rate", "loan", "investment", "return", "capital", "debt", "asset", "liability", "budget", "cash", "equity"}),
    "economics":        frozenset({"supply", "demand", "price", "market", "elasticity", "inflation", "gdp", "trade", "cost", "marginal", "utility"}),
    "law":              frozenset({"statute", "contract", "liability", "damages", "court", "jurisdiction", "plaintiff", "defendant", "claim", "legal", "rights"}),
    "construction":     frozenset({"structure", "load", "beam", "concrete", "foundation", "framing", "material", "build", "code", "safety", "contractor", "project"}),
    "real_estate":      frozenset({"property", "lease", "rent", "mortgage", "title", "appraisal", "zoning", "landlord", "tenant", "purchase", "easement"}),
    "cryptography":     frozenset({"encrypt", "decrypt", "hash", "key", "signature", "cipher", "public", "private", "certificate", "block", "protocol"}),
    "computer_science": frozenset({"algorithm", "complexity", "data structure", "runtime", "memory", "bit", "byte", "sort", "search", "graph", "tree", "recursion"}),
    "statistics":       frozenset({"mean", "median", "variance", "standard deviation", "probability", "distribution", "regression", "confidence", "hypothesis", "sample", "population"}),
    "astronomy":        frozenset({"star", "planet", "orbit", "galaxy", "light year", "mass", "telescope", "solar", "lunar", "gravitational", "luminosity"}),
    "hydrology":        frozenset({"water", "river", "rainfall", "aquifer", "runoff", "watershed", "flood", "drought", "flow", "precipitation", "groundwater"}),
    "meteorology":      frozenset({"temperature", "humidity", "pressure", "wind", "rain", "forecast", "climate", "storm", "atmosphere", "weather"}),
    "geology":          frozenset({"rock", "mineral", "stratum", "fault", "earthquake", "erosion", "sediment", "plate", "volcanic", "seismic"}),
    "energy":           frozenset({"power", "electricity", "solar", "wind", "battery", "grid", "kilowatt", "voltage", "current", "generation", "storage"}),
    "exercise_science": frozenset({"exercise", "muscle", "strength", "cardio", "training", "repetition", "load", "fatigue", "recovery", "vo2", "heart rate"}),
    "nutrition":        frozenset({"calorie", "protein", "carbohydrate", "fat", "vitamin", "mineral", "diet", "nutrient", "fiber"}),
    "formal_logic":     frozenset({"proposition", "syllogism", "valid", "sound", "implies", "premise", "conclusion", "satisfiable", "tautology", "contradiction"}),
    "linguistics":      frozenset({"syntax", "morpheme", "phoneme", "grammar", "semantics", "word", "sentence", "language", "utterance", "token"}),
    "quantum_computing":frozenset({"qubit", "superposition", "entanglement", "gate", "circuit", "decoherence", "measurement", "quantum", "register", "amplitude"}),
}


# ── Socratic question templates ────────────────────────────────────────
# One question per domain. Ultra-low-power: no oracle, pure lookup.
# Each question asks for the *one piece of concrete data* that would
# let the classifier dispatch the orphan claim to the right worker.
# The keeper attaches the question to each orphan so the frontend can
# surface it and let the user refine before re-running.

_FALLBACK_QUESTION = (
    "What specific values, measurements, or concrete facts would make this claim verifiable?"
)

_DOMAIN_QUESTIONS: Dict[str, str] = {
    "mathematics":        "What is the equation, expression, or value being claimed? Include specific numbers.",
    "chemistry":          "What is the chemical equation or compound formula? Include coefficients if known.",
    "physics":            "What physical law applies and what are the before/after values? Include units.",
    "biology":            "What organism, process, or measurement is being claimed? Include specific values.",
    "genetics":           "What is the DNA sequence, gene name, or hereditary trait? Include allele notation if known.",
    "agriculture":        "What crop, soil condition, or farming practice is described? Include location or USDA zone if known.",
    "nutrition":          "What food, serving size, and nutritional claim is being made?",
    "medicine":           "What is the specific diagnosis, medication name, dosage, and condition being treated?",
    "labor":              "What was the hourly rate, weekly hours worked, employment classification, or wage being claimed?",
    "governance":         "What decision, authority level, or policy is described? Who made it and under what scope?",
    "finance":            "What is the principal amount, interest rate, time period, or specific financial calculation?",
    "economics":          "What prices, quantities, or market conditions are being claimed? Include specific numbers.",
    "law":                "What jurisdiction, statute name, or contractual term is being referenced?",
    "construction":       "What material, structural specification, load value, or building code section applies?",
    "real_estate":        "What property address, price, lease terms, or zoning classification is involved?",
    "cryptography":       "What algorithm name, key length, or hash value is being described?",
    "computer_science":   "What algorithm, data structure, or code behavior is claimed? Include a concrete example.",
    "statistics":         "What test type, sample size, and statistical values (mean, SD, p-value) are being claimed?",
    "astronomy":          "What celestial object, orbital period, or distance is being described? Include units.",
    "hydrology":          "What water flow rate, watershed area, or precipitation values are involved? Include units.",
    "meteorology":        "What temperature, pressure, humidity, or weather event is described? Include location and date.",
    "geology":            "What rock type, mineral hardness, seismic magnitude, or dating method is being claimed?",
    "energy":             "What power load (watts), storage capacity (Ah/kWh), or energy consumption is involved?",
    "electrical":         "What voltage, current, resistance, or circuit configuration is described? Include units.",
    "networking":         "What IP address, subnet mask, or CIDR range is being described?",
    "acoustics":          "What frequency (Hz), decibel level, or wave properties are being claimed?",
    "optics":             "What lens focal length, refractive indices, or angles of incidence/refraction are involved?",
    "manufacturing":      "What tolerance, dimension, surface finish (Ra), or Cp/Cpk value is described?",
    "thermodynamics":     "What temperature, pressure, entropy change, or thermodynamic process is described?",
    "fluid_dynamics":     "What flow rate, viscosity, pressure, or Reynolds number is involved? Include units.",
    "soil_science":       "What soil type, pH range, organic matter content, or amendment is described?",
    "cybersecurity":      "What vulnerability type, CVE, attack vector, or security control is described?",
    "photography":        "What aperture (f/), shutter speed, ISO, or exposure value is being claimed?",
    "sports_analytics":   "What athlete, performance metric, game record, or statistical formula is claimed?",
    "calendar_time":      "What date, time zone, or duration is described? Provide the full date in YYYY-MM-DD format.",
    "information_theory": "What channel capacity, entropy value (bits), or signal-to-noise ratio is claimed?",
    "number_theory":      "What number, divisibility property, or modular arithmetic relationship is claimed?",
    "combinatorics":      "What counting problem, permutation P(n,k), or combination C(n,k) is described?",
    "geometry":           "What shape, dimension, angle, or area/volume formula applies? Include values.",
    "music_theory":       "What interval (semitones), chord quality, or frequency ratio is described?",
    "exercise_science":   "What activity, duration, body weight, and MET or heart rate zone is described?",
    "formal_logic":       "State the propositions and connectives symbolically (e.g. P → Q, ¬P ∨ Q).",
    "linguistics":        "What word, Strong's number (G/H), or translation is being analyzed?",
    "quantum_computing":  "What qubit operation, gate sequence, or quantum algorithm is described?",
    "geography":          "What latitude/longitude coordinates, country, or geographic distance is involved?",
    "cryptography":       "What algorithm name, key length, or hash value is being described?",
}


# ── Data structures ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class QuarantineQuestion:
    """The one Socratic question that would resolve an orphan claim.

    Ultra-low-power: derived entirely from _DOMAIN_QUESTIONS lookup
    on the nearest_domain. No oracle, no network. The frontend surfaces
    this question and lets the user supply the missing concrete value,
    then re-runs with the enriched situation.
    """
    claim: str
    question: str
    nearest_domain: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "question": self.question,
            "nearest_domain": self.nearest_domain,
        }


@dataclass(frozen=True)
class RecoveredClaim:
    """A quarantined claim that matched a dispatch rule on retry."""
    claim: str
    domain: str
    spec: Dict[str, Any]
    rule_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {"claim": self.claim, "domain": self.domain,
                "spec": self.spec, "rule_id": self.rule_id}


@dataclass(frozen=True)
class OrphanClaim:
    """A claim with no rule match. Nearest domain recorded as a hint."""
    claim: str
    nearest_domain: Optional[str]
    proximity_score: float   # 0.0–1.0; token overlap fraction
    cluster_key: str         # shared keyword group label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "nearest_domain": self.nearest_domain,
            "proximity_score": round(self.proximity_score, 3),
            "cluster_key": self.cluster_key,
        }


@dataclass
class QuarantineManifest:
    """The keeper's organized triage of the quarantine state."""
    recovered: List[RecoveredClaim] = field(default_factory=list)
    orphans: List[OrphanClaim] = field(default_factory=list)
    questions: List[QuarantineQuestion] = field(default_factory=list)

    @property
    def recovery_count(self) -> int:
        return len(self.recovered)

    @property
    def orphan_count(self) -> int:
        return len(self.orphans)

    def to_dict(self) -> Dict[str, Any]:
        clusters: Dict[str, List[str]] = {}
        for o in self.orphans:
            clusters.setdefault(o.cluster_key, []).append(o.claim)
        out: Dict[str, Any] = {
            "recovery_count": self.recovery_count,
            "orphan_count": self.orphan_count,
            "recovered": [r.to_dict() for r in self.recovered],
            "orphans": [o.to_dict() for o in self.orphans],
            "clusters": {k: v for k, v in clusters.items() if v},
        }
        if self.questions:
            out["questions"] = [q.to_dict() for q in self.questions]
        return out


# ── Proximity scoring ───────────────────────────────────────────────────

def _tokenize(text: str) -> FrozenSet[str]:
    import re
    return frozenset(w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 2)


def _nearest_domain(claim: str) -> Tuple[Optional[str], float]:
    tokens = _tokenize(claim)
    if not tokens:
        return None, 0.0
    best_domain: Optional[str] = None
    best_score = 0.0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        overlap = len(tokens & keywords)
        if overlap == 0:
            continue
        score = overlap / max(len(tokens), len(keywords))
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain, best_score


def _cluster_key(claim: str) -> str:
    """Derive a short cluster label from the claim's top keyword."""
    tokens = _tokenize(claim)
    best_domain, _ = _nearest_domain(claim)
    if best_domain:
        return best_domain
    # Fallback: first high-frequency content word
    stopwords = frozenset({"the", "and", "for", "that", "this", "was", "are", "with", "have", "from"})
    words = [w for w in claim.lower().split() if len(w) > 3 and w not in stopwords]
    return words[0] if words else "unknown"


# ── Rule-based recovery ─────────────────────────────────────────────────

def _try_dispatch(claim: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
    """Attempt rule-based dispatch on a single claim.
    Returns (domain, spec, rule_id) or None.
    """
    try:
        from .dispatch import dispatch
        result = dispatch(claim)
        if result is not None:
            return result.domain, result.spec, result.rule_id
    except Exception:
        pass
    return None


# ── Public API ──────────────────────────────────────────────────────────

def tend_quarantine(quarantined_claims: List[str]) -> QuarantineManifest:
    """Tend the quarantine airlock. Ultra-low-power: rule-based only.

    Attempts recovery via existing dispatch rules (zero oracle cost),
    then scores unrecovered claims against domain keyword sets and
    organizes into proximity clusters.

    Returns a QuarantineManifest with recovered claims separated from
    orphans, and orphans grouped by cluster key for efficient triage.
    """
    manifest = QuarantineManifest()

    for claim in quarantined_claims:
        dispatched = _try_dispatch(claim)
        if dispatched is not None:
            domain, spec, rule_id = dispatched
            manifest.recovered.append(RecoveredClaim(
                claim=claim, domain=domain, spec=spec, rule_id=rule_id,
            ))
        else:
            nearest, score = _nearest_domain(claim)
            cluster = _cluster_key(claim)
            manifest.orphans.append(OrphanClaim(
                claim=claim,
                nearest_domain=nearest,
                proximity_score=score,
                cluster_key=cluster,
            ))
            # Socratic question — one targeted ask per orphan claim
            question = _DOMAIN_QUESTIONS.get(nearest or "", _FALLBACK_QUESTION)
            manifest.questions.append(QuarantineQuestion(
                claim=claim,
                question=question,
                nearest_domain=nearest,
            ))

    # Sort orphans: highest proximity first (easiest to resolve at top)
    manifest.orphans.sort(key=lambda o: -o.proximity_score)
    # Questions follow the same order as orphans
    manifest.questions.sort(
        key=lambda q: -next(
            (o.proximity_score for o in manifest.orphans if o.claim == q.claim), 0.0
        )
    )
    return manifest
