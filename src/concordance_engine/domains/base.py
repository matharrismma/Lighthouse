from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Tuple, Type, runtime_checkable, Optional, List

from ..packet import GateResult


@runtime_checkable
class DomainValidator(Protocol):
    domain: str
    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]: ...
    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]: ...


# Domain name (canonical or alias) → (module path, class name).
# Replaces the previous if/elif chain — O(1) dict lookup, same lazy
# import semantics (Python's import machinery caches modules anyway).
_DOMAIN_VALIDATOR_REGISTRY: Dict[str, Tuple[str, str]] = {
    "mathematics":            ("concordance_engine.domains.mathematics", "MathematicsValidator"),
    "physics":                ("concordance_engine.domains.physics", "PhysicsValidator"),
    "chemistry":              ("concordance_engine.domains.chemistry", "ChemistryValidator"),
    "biology":                ("concordance_engine.domains.biology", "BiologyValidator"),
    "computer_science":       ("concordance_engine.domains.computer_science", "ComputerScienceValidator"),
    "cs":                     ("concordance_engine.domains.computer_science", "ComputerScienceValidator"),
    "statistics":             ("concordance_engine.domains.statistics", "StatisticsValidator"),
    "governance":             ("concordance_engine.domains.governance", "GovernanceValidator"),
    "business":               ("concordance_engine.domains.governance", "GovernanceValidator"),
    "household":              ("concordance_engine.domains.governance", "GovernanceValidator"),
    "education":              ("concordance_engine.domains.governance", "GovernanceValidator"),
    "church":                 ("concordance_engine.domains.governance", "GovernanceValidator"),
    "linguistics":            ("concordance_engine.domains.linguistics", "LinguisticsValidator"),
    "genetics":               ("concordance_engine.domains.genetics", "GeneticsValidator"),
    "agriculture":            ("concordance_engine.domains.agriculture", "AgricultureValidator"),
    "formal_logic":           ("concordance_engine.domains.formal_logic", "FormalLogicValidator"),
    "logic":                  ("concordance_engine.domains.formal_logic", "FormalLogicValidator"),
    "nutrition":              ("concordance_engine.domains.nutrition", "NutritionValidator"),
    "cryptography":           ("concordance_engine.domains.cryptography", "CryptographyValidator"),
    "cryptology":             ("concordance_engine.domains.cryptography", "CryptographyValidator"),
    "exercise_science":       ("concordance_engine.domains.exercise_science", "ExerciseScienceValidator"),
    "exercise":               ("concordance_engine.domains.exercise_science", "ExerciseScienceValidator"),
    "manufacturing":          ("concordance_engine.domains.manufacturing", "ManufacturingValidator"),
    "finance":                ("concordance_engine.domains.finance", "FinanceValidator"),
    "astronomy":              ("concordance_engine.domains.astronomy", "AstronomyValidator"),
    "calendar_time":          ("concordance_engine.domains.calendar_time", "CalendarTimeValidator"),
    "calendar":               ("concordance_engine.domains.calendar_time", "CalendarTimeValidator"),
    "time":                   ("concordance_engine.domains.calendar_time", "CalendarTimeValidator"),
    "networking":             ("concordance_engine.domains.networking", "NetworkingValidator"),
    "network":                ("concordance_engine.domains.networking", "NetworkingValidator"),
    "electrical":             ("concordance_engine.domains.electrical", "ElectricalValidator"),
    "electrical_engineering": ("concordance_engine.domains.electrical", "ElectricalValidator"),
    "acoustics":              ("concordance_engine.domains.acoustics", "AcousticsValidator"),
    "optics":                 ("concordance_engine.domains.optics", "OpticsValidator"),
    "geology":                ("concordance_engine.domains.geology", "GeologyValidator"),
    "earth_science":          ("concordance_engine.domains.geology", "GeologyValidator"),
    "information_theory":     ("concordance_engine.domains.information_theory", "InformationTheoryValidator"),
    "info_theory":            ("concordance_engine.domains.information_theory", "InformationTheoryValidator"),
    "document_validation":    ("concordance_engine.domains.document_validation", "DocumentValidationValidator"),
    "doc_validation":         ("concordance_engine.domains.document_validation", "DocumentValidationValidator"),
    "music_theory":           ("concordance_engine.domains.music_theory", "MusicTheoryValidator"),
    "music":                  ("concordance_engine.domains.music_theory", "MusicTheoryValidator"),
    "number_theory":          ("concordance_engine.domains.number_theory", "NumberTheoryValidator"),
    "geography":              ("concordance_engine.domains.geography", "GeographyValidator"),
    "combinatorics":          ("concordance_engine.domains.combinatorics", "CombinatoricsValidator"),
    "geometry":               ("concordance_engine.domains.geometry", "GeometryValidator"),
    "meteorology":            ("concordance_engine.domains.meteorology", "MeteorologyValidator"),
    "weather":                ("concordance_engine.domains.meteorology", "MeteorologyValidator"),
    "hydrology":              ("concordance_engine.domains.hydrology", "HydrologyValidator"),
    "water":                  ("concordance_engine.domains.hydrology", "HydrologyValidator"),
    "photography":            ("concordance_engine.domains.photography", "PhotographyValidator"),
    "photo":                  ("concordance_engine.domains.photography", "PhotographyValidator"),
    "sports_analytics":       ("concordance_engine.domains.sports_analytics", "SportsAnalyticsValidator"),
    "sports":                 ("concordance_engine.domains.sports_analytics", "SportsAnalyticsValidator"),
    "witness":                ("concordance_engine.domains.witness", "WitnessValidator"),
    "testimony":              ("concordance_engine.domains.witness", "WitnessValidator"),
}


# Resolved validator-class cache. After first lookup for a given domain
# we keep the class object (not an instance) so subsequent calls skip
# both the dict lookup chain and the importlib hop.
_LOADED_VALIDATOR_CLASSES: Dict[str, Type] = {}


def load_domain_validator(domain: str) -> DomainValidator | None:
    """Resolve a domain name to a fresh validator instance.

    O(1) dict lookup, lazy import on first hit, class cached thereafter.
    Returns None for unknown domains.
    """
    domain = (domain or "").lower()
    cls = _LOADED_VALIDATOR_CLASSES.get(domain)
    if cls is not None:
        return cls()
    entry = _DOMAIN_VALIDATOR_REGISTRY.get(domain)
    if entry is None:
        return None
    module_path, class_name = entry
    cls = getattr(importlib.import_module(module_path), class_name)
    _LOADED_VALIDATOR_CLASSES[domain] = cls
    return cls()
