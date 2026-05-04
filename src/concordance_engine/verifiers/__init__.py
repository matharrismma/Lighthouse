"""Verifier registry — lazy domain → module mapping.

Cold-start optimization: verifier modules are imported on first use,
not at package load. This matters because some modules pull heavy
scientific libraries (scipy.stats ≈ 1s, sympy ≈ 0.5s) that aren't
needed unless a packet actually exercises those domains.

Public API is unchanged for the only known consumer (`run_for_domain`).
The `VERIFIERS` dict's values are now module-path strings rather than
module objects; the resolver in `_get_module()` imports them lazily and
caches the result. Direct submodule imports (`from concordance_engine
.verifiers import chemistry`) still work — they just trigger that
module's load on demand.
"""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Dict, Optional

# Cross-cutting verifiers run on every packet and are small enough that
# eager loading costs nothing meaningful. Scripture's no-anchor short-
# circuit makes per-call overhead negligible. Phase classifier is also
# cheap (a single lookup + classification) and keeps phase metadata
# visible whether or not a domain validator is registered.
from . import scripture, phase
from .base import VerifierResult, VerifierStatus, na, confirm, mismatch, error


# Domain name (canonical or alias) → fully qualified module path.
# Modules are imported on demand by `_get_module`.
VERIFIERS: Dict[str, str] = {
    "chemistry":            "concordance_engine.verifiers.chemistry",
    "physics":              "concordance_engine.verifiers.physics",
    "statistics":           "concordance_engine.verifiers.statistics",
    "mathematics":          "concordance_engine.verifiers.mathematics",
    "computer_science":     "concordance_engine.verifiers.computer_science",
    "cs":                   "concordance_engine.verifiers.computer_science",
    "biology":              "concordance_engine.verifiers.biology",
    "governance":           "concordance_engine.verifiers.governance",
    "business":             "concordance_engine.verifiers.governance",
    "household":            "concordance_engine.verifiers.governance",
    "education":            "concordance_engine.verifiers.governance",
    "church":               "concordance_engine.verifiers.governance",
    "linguistics":          "concordance_engine.verifiers.linguistics",
    "genetics":             "concordance_engine.verifiers.genetics",
    "agriculture":          "concordance_engine.verifiers.agriculture",
    "formal_logic":         "concordance_engine.verifiers.formal_logic",
    "logic":                "concordance_engine.verifiers.formal_logic",
    "nutrition":            "concordance_engine.verifiers.nutrition",
    "cryptography":         "concordance_engine.verifiers.cryptography",
    "cryptology":           "concordance_engine.verifiers.cryptography",
    "exercise_science":     "concordance_engine.verifiers.exercise_science",
    "exercise":             "concordance_engine.verifiers.exercise_science",
    "manufacturing":        "concordance_engine.verifiers.manufacturing",
    "finance":              "concordance_engine.verifiers.finance",
    "astronomy":            "concordance_engine.verifiers.astronomy",
    "calendar_time":        "concordance_engine.verifiers.calendar_time",
    "calendar":             "concordance_engine.verifiers.calendar_time",
    "time":                 "concordance_engine.verifiers.calendar_time",
    "networking":           "concordance_engine.verifiers.networking",
    "network":              "concordance_engine.verifiers.networking",
    "electrical":           "concordance_engine.verifiers.electrical",
    "electrical_engineering": "concordance_engine.verifiers.electrical",
    "energy":               "concordance_engine.verifiers.energy",
    "power":                "concordance_engine.verifiers.energy",
    "off_grid":             "concordance_engine.verifiers.energy",
    "acoustics":            "concordance_engine.verifiers.acoustics",
    "optics":               "concordance_engine.verifiers.optics",
    "geology":              "concordance_engine.verifiers.geology",
    "earth_science":        "concordance_engine.verifiers.geology",
    "information_theory":   "concordance_engine.verifiers.information_theory",
    "info_theory":          "concordance_engine.verifiers.information_theory",
    "document_validation":  "concordance_engine.verifiers.document_validation",
    "doc_validation":       "concordance_engine.verifiers.document_validation",
    "music_theory":         "concordance_engine.verifiers.music_theory",
    "music":                "concordance_engine.verifiers.music_theory",
    "number_theory":        "concordance_engine.verifiers.number_theory",
    "geography":            "concordance_engine.verifiers.geography",
    "combinatorics":        "concordance_engine.verifiers.combinatorics",
    "geometry":             "concordance_engine.verifiers.geometry",
    "meteorology":          "concordance_engine.verifiers.meteorology",
    "weather":              "concordance_engine.verifiers.meteorology",
    "hydrology":            "concordance_engine.verifiers.hydrology",
    "water":                "concordance_engine.verifiers.hydrology",
    "photography":          "concordance_engine.verifiers.photography",
    "photo":                "concordance_engine.verifiers.photography",
    "sports_analytics":     "concordance_engine.verifiers.sports_analytics",
    "sports":               "concordance_engine.verifiers.sports_analytics",
    "witness":              "concordance_engine.verifiers.witness",
    "testimony":            "concordance_engine.verifiers.witness",
}


_LOADED_MODULES: Dict[str, ModuleType] = {}


def _get_module(domain: str) -> Optional[ModuleType]:
    """Resolve a domain name to its verifier module, importing on first
    use. Returns None for unknown domains."""
    mod_path = VERIFIERS.get(domain)
    if mod_path is None:
        return None
    cached = _LOADED_MODULES.get(mod_path)
    if cached is not None:
        return cached
    cached = importlib.import_module(mod_path)
    _LOADED_MODULES[mod_path] = cached
    return cached


# Cross-cutting verifiers run on EVERY packet regardless of domain.
# Scripture handles anchor verification (no-ops if no refs present);
# phase classifies the packet's position in the Setup → Positioning
# → Conversion lifecycle (NA if no phase declared). Both are safe
# defaults — they degrade gracefully on packets that don't carry
# the relevant fields.
CROSS_CUTTING_VERIFIERS = (scripture, phase)


def run_for_domain(domain: str, packet):
    """Run all verifiers registered for this domain plus any cross-cutting
    verifiers. Returns list[VerifierResult].

    Cross-cutting verifiers (currently: scripture anchors) run on every
    packet because their inputs can appear in any domain. They short-circuit
    to a no-op when the packet doesn't carry the relevant fields.
    """
    results = []
    mod = _get_module((domain or "").lower())
    if mod is not None:
        results.extend(mod.run(packet))
    for cross in CROSS_CUTTING_VERIFIERS:
        results.extend(cross.run(packet))
    return results


__all__ = [
    "VerifierResult", "VerifierStatus", "na", "confirm", "mismatch", "error",
    "run_for_domain", "VERIFIERS", "CROSS_CUTTING_VERIFIERS",
]
