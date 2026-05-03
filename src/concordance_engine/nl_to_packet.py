"""
nl_to_packet — turn natural-language claims into Concordance packets.

Bridges the gap between "a person types a sentence" and "the engine has a
packet to verify." Without this, the engine sits behind a JSON wall and the
discernment never reaches the user. With this, the four-gate pipeline is
addressable in plain English for the most common claim shapes.

The strategy is **deterministic-first, no LLM**: regex/parser-based templates
cover the high-volume shapes (chemistry equations, p-values, dimensional
checks, common math). For freeform claims that don't match any template, the
parser returns ``None`` and an MCP host (Claude Desktop, etc.) is expected to
do its own NL→packet conversion before re-submitting.

Public API:
    from concordance_engine.nl_to_packet import parse, ParseResult

    result = parse("the p-value for n=30, mean 5.2, sd 1.0, mu0=5 is 0.282")
    if result is not None:
        packet = result.packet            # dict ready for engine.validate_packet
        domain = result.domain            # 'statistics' | 'chemistry' | ...
        confidence = result.confidence    # heuristic, 0.0–1.0

The module is **standalone** — imports only stdlib. No SymPy, no SciPy. It
builds packets; the verifiers do the work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Pattern


# ---------------------------------------------------------------------------
# Result type

@dataclass(frozen=True)
class ParseResult:
    domain: str
    packet: Dict[str, Any]
    confidence: float
    template: str            # which template matched, for diagnosability
    notes: str = ""          # any caveats — partial parse, defaulted fields


# ---------------------------------------------------------------------------
# Helpers

# Numeric pattern accepting -3.14, .5, 1e-5, 1.2e+3, 1/2 (as fraction)
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_NUM_OR_FRAC = rf"(?:{_NUM}|\d+\s*/\s*\d+)"


def _to_float(s: str) -> float:
    s = s.strip().replace(",", "")
    if "/" in s and "e" not in s.lower():
        num, denom = s.split("/")
        return float(num) / float(denom)
    return float(s)


def _norm_arrow(text: str) -> str:
    """Normalize various arrow forms to '->'."""
    return (text
            .replace("⇌", "->").replace("⇋", "->")
            .replace("→", "->").replace("⟶", "->")
            .replace("⇒", "->").replace("=>", "->"))


# ---------------------------------------------------------------------------
# Template: chemistry equation
# Examples that match:
#   "is C3H8 + 5 O2 -> 3 CO2 + 4 H2O balanced?"
#   "balance Cu + 2 HCl → CuCl2 + H2"
#   "Fe + Cl2 -> FeCl3"

# A single chemistry term: optional integer coefficient, then a formula.
# Formula starts with an uppercase letter and may include digits, parens,
# hydrate dot (·), inline charges (^2+, ^-), and embedded dots (Na2CO3·10H2O).
_CHEM_TERM = r"(?:\d+\s+)?[A-Z][A-Za-z0-9()·\.\^+\-]*"
# A side: one term, optionally followed by " + term + term + ..."
_CHEM_SIDE = rf"{_CHEM_TERM}(?:\s*\+\s*{_CHEM_TERM})*"
_CHEM_EQUATION = re.compile(rf"(?P<lhs>{_CHEM_SIDE})\s*->\s*(?P<rhs>{_CHEM_SIDE})")


def _try_chemistry(text: str) -> Optional[ParseResult]:
    t = _norm_arrow(text)
    m = _CHEM_EQUATION.search(t)
    if not m:
        return None
    lhs = m.group("lhs").strip(" ?.,;")
    rhs = m.group("rhs").strip(" ?.,;")
    # Reassemble with single ' -> ' separator
    eq = f"{lhs} -> {rhs}"
    packet: Dict[str, Any] = {
        "domain": "chemistry",
        "id": "nl-chem-001",
        "scope": "adapter",
        "created_epoch": 1,
        "required_witnesses": 0,
        "witness_count": 0,
        "CHEM_VERIFY": {"equation": eq},
    }
    # Optional temperature
    tm = re.search(rf"(?:T|temperature)\s*=?\s*(?P<v>{_NUM})\s*(K|kelvin)\b", text, re.I)
    if tm:
        packet["CHEM_VERIFY"]["temperature_K"] = _to_float(tm.group("v"))
    return ParseResult(
        domain="chemistry",
        packet=packet,
        confidence=0.85,
        template="chem.equation",
        notes="Matched equation only; CHEM_RED attestation defaulted to engine inferences.",
    )


# ---------------------------------------------------------------------------
# Template: one-sample t-test (the most common stats claim)
# Examples that match:
#   "p = 0.282 from a one-sample t-test, n=30, mean=5.2, sd=1.0, mu0=5.0"
#   "t-test: n=12, mean=4.7, sd=0.8, mu0=5, p-value 0.21"

def _try_stat_one_sample_t(text: str) -> Optional[ParseResult]:
    if not re.search(r"\b(?:t.?test|one.?sample\s*t|student'?s\s*t)\b", text, re.I):
        return None
    fields = {}
    for key, pattern in [
        ("n",      rf"\bn\s*=?\s*(?P<v>\d+)\b"),
        ("mean",   rf"\b(?:mean|x[̄\-_]?bar|sample\s*mean)\s*=?\s*(?P<v>{_NUM})"),
        ("sd",     rf"\b(?:sd|std|s|stdev|standard\s*deviation)\s*=?\s*(?P<v>{_NUM})"),
        ("mu0",    rf"\b(?:mu0|μ0|mu_0|μ_0|null\s*mean|hypothesized\s*mean)\s*=?\s*(?P<v>{_NUM})"),
        ("p",      rf"\bp(?:\s*-?\s*value)?\s*=?\s*(?P<v>{_NUM})"),
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            fields[key] = _to_float(m.group("v"))
    required = {"n", "mean", "sd", "mu0", "p"}
    missing = required - fields.keys()
    if missing:
        return None
    tail = "two-sided"
    if re.search(r"\bone[-\s]?sided\b|\bone[-\s]?tailed\b", text, re.I):
        tail = "one-sided"
    return ParseResult(
        domain="statistics",
        packet={
            "domain": "statistics",
            "id": "nl-stat-001",
            "scope": "adapter",
            "created_epoch": 1,
            "required_witnesses": 0,
            "witness_count": 0,
            "STAT_VERIFY": {
                "test": "one_sample_t",
                "n": int(fields["n"]),
                "mean": fields["mean"],
                "sd": fields["sd"],
                "mu0": fields["mu0"],
                "tail": tail,
                "claimed_p": fields["p"],
            },
        },
        confidence=0.9,
        template="stat.one_sample_t",
        notes="" if "tail" in fields else "tail defaulted to two-sided",
    )


# ---------------------------------------------------------------------------
# Template: dimensional analysis (physics)
# Examples that match:
#   "F = m * a where F is in newtons, m in kg, a in m/s^2"
#   "v = sqrt(2*g*h), v in m/s, g in m/s^2, h in m"

_PHYS_UNIT_LINE = re.compile(
    rf"(?P<sym>[A-Za-z_]\w*)\s+(?:in|is\s+in)\s+(?P<unit>[A-Za-z0-9·*\^/\.\s\-]+?)(?=\s*(?:,|$))",
    re.I,
)


def _try_physics_dimensional(text: str) -> Optional[ParseResult]:
    if not re.search(r"\b(?:dimension|unit)s?\b|\bin\s+(?:m/s|kg|N|J|W|Pa|K|A|mol|cd)\b", text, re.I):
        # Heuristic: needs to mention units explicitly
        return None
    # Pull the equation: anything with a single = sign
    m = re.search(r"(?P<eq>[A-Za-z_]\w*\s*=\s*[^,;\.?]+)", text)
    if not m:
        return None
    equation = m.group("eq").strip()
    # Pull symbol→unit map
    units: Dict[str, str] = {}
    for um in _PHYS_UNIT_LINE.finditer(text):
        sym = um.group("sym")
        unit = um.group("unit").strip().strip(".")
        if sym in equation:
            units[sym] = unit
    if not units:
        return None
    return ParseResult(
        domain="physics",
        packet={
            "domain": "physics",
            "id": "nl-phys-001",
            "scope": "adapter",
            "created_epoch": 1,
            "required_witnesses": 0,
            "witness_count": 0,
            "PHYS_VERIFY": {
                "equation": equation,
                "units": units,
            },
        },
        confidence=0.7,
        template="phys.dimensional",
        notes=f"Parsed equation '{equation}' with {len(units)} unit annotations.",
    )


# ---------------------------------------------------------------------------
# Template: math equality / derivative / integral
# Examples that match:
#   "d/dx(x^2) = 2x"
#   "integral of 2x dx = x^2 + C"
#   "limit of sin(x)/x as x->0 is 1"
#   "x^2 + 2x + 1 simplifies to (x+1)^2"

def _try_math(text: str) -> Optional[ParseResult]:
    # Derivative pattern
    m = re.search(
        r"d\s*/\s*d(?P<var>[a-zA-Z])\s*\(\s*(?P<f>[^)]+)\s*\)\s*=\s*(?P<g>[^.,;?\n]+)",
        text,
    )
    if m:
        return ParseResult(
            domain="mathematics",
            packet={
                "domain": "mathematics",
                "id": "nl-math-001",
                "scope": "adapter",
                "created_epoch": 1,
                "required_witnesses": 0,
                "witness_count": 0,
                "MATH_VERIFY": {
                    "derivative": {
                        "function": m.group("f").strip(),
                        "variable": m.group("var"),
                        "claimed": m.group("g").strip(),
                    }
                },
            },
            confidence=0.85,
            template="math.derivative",
        )
    # Equality / simplification: "X = Y" or "X simplifies to Y" or "X equals Y"
    m = re.search(
        r"(?P<lhs>[^=]{2,}?)\s*(?:=|simplifies\s*to|equals)\s*(?P<rhs>[^=.,;?\n]+)",
        text,
    )
    if m:
        lhs = m.group("lhs").strip()
        rhs = m.group("rhs").strip()
        # Avoid trivial captures and stat fields like "n = 30"
        if (len(lhs) >= 2 and len(rhs) >= 2
                and not re.fullmatch(r"[a-zA-Z_]\w*", lhs)
                and not re.search(r"\b(?:p|n|mean|sd|mu0|alpha)\b", lhs, re.I)):
            return ParseResult(
                domain="mathematics",
                packet={
                    "domain": "mathematics",
                    "id": "nl-math-002",
                    "scope": "adapter",
                    "created_epoch": 1,
                    "required_witnesses": 0,
                    "witness_count": 0,
                    "MATH_VERIFY": {
                        "equality": {
                            "left": lhs,
                            "right": rhs,
                        }
                    },
                },
                confidence=0.6,
                template="math.equality",
                notes="Parsed as symbolic equality; engine will verify with SymPy.",
            )
    return None


# ---------------------------------------------------------------------------
# Template: CS complexity claim
# Examples that match:
#   "binary search is O(log n)"
#   "merge sort runs in O(n log n)"
#   "the algorithm is O(n^2)"

_CS_BIG_O = re.compile(
    r"\bO\s*\(\s*(?P<expr>[^)]{1,40})\s*\)",
    re.I,
)


def _try_cs_complexity(text: str) -> Optional[ParseResult]:
    m = _CS_BIG_O.search(text)
    if not m:
        return None
    return ParseResult(
        domain="computer_science",
        packet={
            "domain": "computer_science",
            "id": "nl-cs-001",
            "scope": "adapter",
            "created_epoch": 1,
            "required_witnesses": 0,
            "witness_count": 0,
            "CS_VERIFY": {
                "complexity": {
                    "claimed": f"O({m.group('expr').strip()})",
                }
            },
        },
        confidence=0.5,
        template="cs.complexity",
        notes="Complexity attestation only — provide a code/timing artifact for live verification.",
    )


# ---------------------------------------------------------------------------
# Dispatcher

_TEMPLATES: List[Callable[[str], Optional[ParseResult]]] = [
    _try_chemistry,
    _try_stat_one_sample_t,
    _try_physics_dimensional,
    _try_math,
    _try_cs_complexity,
]


def parse(text: str) -> Optional[ParseResult]:
    """Try each deterministic template; return the first match.

    Returns None if no template matches. An MCP host that wraps this
    function should treat None as an invitation to do an LLM-driven
    NL→packet conversion and re-submit.
    """
    if not text or not text.strip():
        return None
    for fn in _TEMPLATES:
        try:
            r = fn(text)
        except Exception:
            r = None
        if r is not None:
            return r
    return None


# ---------------------------------------------------------------------------
# Convenience: wrap parse + engine in one call

def parse_and_validate(text: str, *, now_epoch: int = 9999999999):
    """Parse a natural-language claim and run the engine on the resulting packet.

    Returns a tuple (parse_result, engine_result).
    If parse fails, returns (None, None).
    """
    parsed = parse(text)
    if parsed is None:
        return None, None
    # Lazy imports so this module stays standalone-importable.
    from .engine import validate_packet, EngineConfig  # type: ignore
    cfg = EngineConfig(schema_path="", run_verifiers=True)
    eng = validate_packet(parsed.packet, now_epoch=now_epoch, config=cfg)
    return parsed, eng


def parse_and_seal(text: str, *, now_epoch: int = 9999999999, anchors=(),
                   closest_case=None):
    """Parse a natural-language claim and return a sealed WitnessRecord.

    The new canonical entry point that produces the same object both
    audiences consume — agents serialize it, humans render it via
    `walkthrough.render_walkthrough(record)`. If parse fails, returns
    None; an MCP host can then do its own NL→packet conversion and call
    the engine directly.
    """
    parsed = parse(text)
    if parsed is None:
        return None
    from .engine import validate_and_seal, EngineConfig  # type: ignore
    cfg = EngineConfig(schema_path="", run_verifiers=True)
    return validate_and_seal(
        parsed.packet,
        now_epoch=now_epoch,
        config=cfg,
        anchors=anchors,
        closest_case=closest_case,
        packet_id=parsed.packet.get("id"),
    )


__all__ = ["ParseResult", "parse", "parse_and_validate", "parse_and_seal"]
