"""Rhetoric verifier (grid axes: reasoning/authority-trust/information).

Deterministic checks on argumentation structure, fallacy classification,
syllogistic validity, and argument completeness. All criteria are drawn
from standard textbook rhetoric and logic (public-domain).

Checks:
  * rhetoric.fallacy_classification  — is the named fallacy formal or informal?
  * rhetoric.syllogism_validity      — does the AAA/AEE/etc. mood–figure hold?
  * rhetoric.argument_structure      — does the argument have premise + conclusion?

RHET_VERIFY packet shape (any subset):
    {
      "fallacy_name": "ad hominem",
      "claimed_is_formal_fallacy": false,

      "major_premise": "All M are P",
      "minor_premise": "All S are M",
      "conclusion": "All S are P",
      "claimed_valid": true,

      "has_premise": true,
      "has_conclusion": true,
      "has_warrant": false,
      "claimed_is_complete_argument": true,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error

# ---------------------------------------------------------------------------
# Fallacy catalogue
# ---------------------------------------------------------------------------

# Each entry: (is_formal_fallacy, short_definition)
_FALLACIES: Dict[str, Tuple[bool, str]] = {
    # --- formal fallacies (invalid logical form) ---
    "affirming the consequent":  (True,  "If P→Q and Q is asserted, P is wrongly inferred"),
    "denying the antecedent":    (True,  "If P→Q and ¬P is asserted, ¬Q is wrongly inferred"),
    "undistributed middle":      (True,  "Middle term not distributed in either premise of a syllogism"),
    # --- informal fallacies (bad content / relevance) ---
    "ad hominem":                (False, "Attacking the person rather than the argument"),
    "straw man":                 (False, "Misrepresenting someone's argument to attack it more easily"),
    "false dichotomy":           (False, "Presenting only two choices when more exist"),
    "slippery slope":            (False, "Claiming one event will inevitably lead to extreme consequences"),
    "appeal to authority":       (False, "Using an authority's opinion as evidence without supporting argument"),
    "hasty generalization":      (False, "Drawing a broad conclusion from a small or unrepresentative sample"),
    "circular reasoning":        (False, "The conclusion is used as a premise to support itself"),
    "red herring":               (False, "Introducing irrelevant material to distract from the issue"),
    "post hoc":                  (False, "Because B followed A, A caused B (correlation ≠ causation)"),
    "bandwagon":                 (False, "Something is true or good because many people believe or do it"),
    "appeal to nature":          (False, "Something is good because it is natural or bad because it is not"),
    "false equivalence":         (False, "Treating two things as equivalent when they are not"),
    "begging the question":      (False, "The argument's conclusion is assumed within the premise"),
    "tu quoque":                 (False, "Deflecting criticism by pointing to the critic's own faults"),
    "sunk cost":                 (False, "Continuing an endeavour because of past irrecoverable investment"),
}

# Normalise a lookup key (lower, strip).
def _norm_fallacy(name: str) -> str:
    return name.strip().lower()


def verify_fallacy_classification(spec: Dict[str, Any]) -> VerifierResult:
    """Classify whether the named fallacy is formal or informal."""
    name = "rhetoric.fallacy_classification"
    fallacy_name = spec.get("fallacy_name")
    claimed = spec.get("claimed_is_formal_fallacy")
    if fallacy_name is None or claimed is None:
        return na(name)
    key = _norm_fallacy(str(fallacy_name))
    entry = _FALLACIES.get(key)
    if entry is None:
        return na(name, f"fallacy {fallacy_name!r} not in known catalogue")
    actual_is_formal, definition = entry
    claimed_b = bool(claimed)
    data = {
        "fallacy_name": fallacy_name,
        "definition": definition,
        "actual_is_formal_fallacy": actual_is_formal,
        "claimed_is_formal_fallacy": claimed_b,
        "rule": "Formal fallacies have invalid logical form; informal fallacies have bad content/relevance",
    }
    if actual_is_formal == claimed_b:
        kind = "formal" if actual_is_formal else "informal"
        return confirm(name, f"{fallacy_name!r} is a {kind} fallacy (matches claim)", data)
    actual_kind = "formal" if actual_is_formal else "informal"
    return mismatch(name, f"{fallacy_name!r} is {actual_kind}, claimed {'formal' if claimed_b else 'informal'}", data)


# ---------------------------------------------------------------------------
# Syllogism validity
# ---------------------------------------------------------------------------

# Supported valid syllogistic moods per figure (Aristotelian tradition).
# Key: (figure, mood_string) where mood is major+minor+conclusion quantifiers.
# Quantifiers: A=All, E=No, I=Some, O=Some-not
#
# Figure 1: M-P, S-M ∴ S-P  (middle is subject of major, predicate of minor)
# Figure 2: P-M, S-M ∴ S-P  (middle is predicate of both)
# Figure 3: M-P, M-S ∴ S-P  (middle is subject of both)
# Figure 4: P-M, M-S ∴ S-P  (middle is predicate of major, subject of minor)

_VALID_SYLLOGISMS = {
    # Figure 1
    (1, "AAA"),  # Barbara
    (1, "EAE"),  # Celarent
    (1, "AII"),  # Darii
    (1, "EIO"),  # Ferio
    # Figure 2
    (2, "EAE"),  # Cesare
    (2, "AEE"),  # Camestres
    (2, "EIO"),  # Festino
    (2, "AOO"),  # Baroco
    # Figure 3
    (3, "AAI"),  # Darapti
    (3, "EAO"),  # Felapton
    (3, "IAI"),  # Disamis
    (3, "AII"),  # Datisi
    (3, "OAO"),  # Bocardo
    (3, "EIO"),  # Ferison
    # Figure 4
    (4, "AAI"),  # Bramantip
    (4, "AEE"),  # Camenes
    (4, "IAI"),  # Dimaris
    (4, "EAO"),  # Fesapo
    (4, "EIO"),  # Fresison
}

# Map quantifier-word + optional negation to letter code.
_QUANTIFIER_MAP = {
    ("all",  False): "A",
    ("no",   False): "E",
    ("some", False): "I",
    ("some", True):  "O",
}


def _parse_premise(text: str) -> Optional[Tuple[str, str, str, str]]:
    """Try to parse 'All/Some/No X are [not] Y' → (quantifier_letter, X, Y, negated).

    Returns (letter, subject, predicate, parsed_text) or None on failure.
    """
    import re
    t = text.strip().rstrip(".")
    # Pattern: <quantifier> <subject_phrase> are [not] <predicate_phrase>
    m = re.match(
        r"^(all|some|no)\s+(.+?)\s+are(\s+not)?\s+(.+)$",
        t, re.IGNORECASE
    )
    if not m:
        return None
    quant_word = m.group(1).lower()
    subj = m.group(2).strip()
    negated = bool(m.group(3))
    pred = m.group(4).strip()
    letter = _QUANTIFIER_MAP.get((quant_word, negated))
    if letter is None:
        return None
    return letter, subj, pred, text


def _infer_figure(major_s, major_p, minor_s, minor_p) -> Optional[int]:
    """Determine Aristotelian figure from subject/predicate roles.

    In a categorical syllogism the middle term (M) appears in both premises
    but not the conclusion.  We identify M by looking for the shared term.
    Figure depends on M's position:
      1: M is subject of major, predicate of minor
      2: M is predicate of major, predicate of minor
      3: M is subject of major, subject of minor
      4: M is predicate of major, subject of minor
    """
    # Collect all four terms (lower-case comparison)
    terms = {major_s.lower(), major_p.lower(), minor_s.lower(), minor_p.lower()}
    # The middle term appears in both premises (not in conclusion); because we
    # don't have the conclusion terms here, find terms common to both premises.
    major_terms = {major_s.lower(), major_p.lower()}
    minor_terms = {minor_s.lower(), minor_p.lower()}
    middle_candidates = major_terms & minor_terms
    if len(middle_candidates) != 1:
        return None
    M = next(iter(middle_candidates))
    in_major_subject   = (major_s.lower() == M)
    in_major_predicate = (major_p.lower() == M)
    in_minor_subject   = (minor_s.lower() == M)
    in_minor_predicate = (minor_p.lower() == M)
    if in_major_subject and in_minor_predicate:
        return 1
    if in_major_predicate and in_minor_predicate:
        return 2
    if in_major_subject and in_minor_subject:
        return 3
    if in_major_predicate and in_minor_subject:
        return 4
    return None


def verify_syllogism_validity(spec: Dict[str, Any]) -> VerifierResult:
    """Check if a categorical syllogism's mood–figure is classically valid."""
    name = "rhetoric.syllogism_validity"
    major_text = spec.get("major_premise")
    minor_text = spec.get("minor_premise")
    conc_text  = spec.get("conclusion")
    claimed    = spec.get("claimed_valid")
    if any(v is None for v in (major_text, minor_text, conc_text, claimed)):
        return na(name)

    parsed_major = _parse_premise(str(major_text))
    parsed_minor = _parse_premise(str(minor_text))
    parsed_conc  = _parse_premise(str(conc_text))

    if parsed_major is None or parsed_minor is None or parsed_conc is None:
        return na(name, "could not parse one or more premise/conclusion strings")

    maj_q, maj_s, maj_p, _ = parsed_major
    min_q, min_s, min_p, _ = parsed_minor
    con_q, con_s, con_p, _ = parsed_conc

    mood = maj_q + min_q + con_q
    figure = _infer_figure(maj_s, maj_p, min_s, min_p)

    if figure is None:
        return na(name, "could not determine syllogistic figure (no shared middle term found)")

    actual_valid = (figure, mood) in _VALID_SYLLOGISMS
    claimed_b = bool(claimed)
    data = {
        "major_premise": major_text,
        "minor_premise": minor_text,
        "conclusion":    conc_text,
        "parsed_major":  {"quantifier": maj_q, "subject": maj_s, "predicate": maj_p},
        "parsed_minor":  {"quantifier": min_q, "subject": min_s, "predicate": min_p},
        "parsed_conc":   {"quantifier": con_q, "subject": con_s, "predicate": con_p},
        "mood":          mood,
        "figure":        figure,
        "actual_valid":  actual_valid,
        "claimed_valid": claimed_b,
        "rule":          f"Figure {figure}, Mood {mood}: {'valid' if actual_valid else 'invalid'} per Aristotelian syllogistic",
    }
    if actual_valid == claimed_b:
        return confirm(name, f"Figure {figure} / Mood {mood} is {'valid' if actual_valid else 'invalid'} (matches claim)", data)
    return mismatch(name, f"Figure {figure} / Mood {mood} actual_valid={actual_valid}, claimed {claimed_b}", data)


# ---------------------------------------------------------------------------
# Argument structure
# ---------------------------------------------------------------------------

def verify_argument_structure(spec: Dict[str, Any]) -> VerifierResult:
    """Check if has_premise + has_conclusion implies a complete argument."""
    name = "rhetoric.argument_structure"
    has_premise    = spec.get("has_premise")
    has_conclusion = spec.get("has_conclusion")
    claimed        = spec.get("claimed_is_complete_argument")
    if any(v is None for v in (has_premise, has_conclusion, claimed)):
        return na(name)

    hp = bool(has_premise)
    hc = bool(has_conclusion)
    hw = bool(spec.get("has_warrant", False))
    actual = hp and hc
    claimed_b = bool(claimed)

    data = {
        "has_premise":    hp,
        "has_conclusion": hc,
        "has_warrant":    hw,
        "actual_is_complete_argument":  actual,
        "claimed_is_complete_argument": claimed_b,
        "rule": "A complete argument requires at least one premise and one conclusion",
    }
    if actual == claimed_b:
        return confirm(name, f"is_complete_argument={actual} (matches claim)", data)
    return mismatch(name, f"is_complete_argument={actual}, claimed {claimed_b}", data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch all applicable rhetoric checks for the RHET_VERIFY block."""
    results: List[VerifierResult] = []
    rv = packet.get("RHET_VERIFY") or {}

    if "fallacy_name" in rv and "claimed_is_formal_fallacy" in rv:
        results.append(verify_fallacy_classification(rv))

    if ("major_premise" in rv and "minor_premise" in rv
            and "conclusion" in rv and "claimed_valid" in rv):
        results.append(verify_syllogism_validity(rv))

    if ("has_premise" in rv and "has_conclusion" in rv
            and "claimed_is_complete_argument" in rv):
        results.append(verify_argument_structure(rv))

    if not results:
        results.append(na("rhetoric", "no RHET_VERIFY artifacts present"))
    return results
