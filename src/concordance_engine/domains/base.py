from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol, runtime_checkable, Optional, List

from ..packet import GateResult

@runtime_checkable
class DomainValidator(Protocol):
    domain: str
    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]: ...
    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]: ...

def load_domain_validator(domain: str) -> DomainValidator | None:
    """
    Registry loader for domain validators.
    """
    domain = (domain or "").lower()
    if domain == "mathematics":
        from .mathematics import MathematicsValidator
        return MathematicsValidator()
    if domain == "physics":
        from .physics import PhysicsValidator
        return PhysicsValidator()
    if domain == "chemistry":
        from .chemistry import ChemistryValidator
        return ChemistryValidator()
    if domain == "biology":
        from .biology import BiologyValidator
        return BiologyValidator()
    if domain in ("computer_science", "cs"):
        from .computer_science import ComputerScienceValidator
        return ComputerScienceValidator()
    if domain == "statistics":
        from .statistics import StatisticsValidator
        return StatisticsValidator()
    if domain in ("governance", "business", "household", "education", "church"):
        from .governance import GovernanceValidator
        return GovernanceValidator()
    if domain == "linguistics":
        from .linguistics import LinguisticsValidator
        return LinguisticsValidator()
    if domain == "genetics":
        from .genetics import GeneticsValidator
        return GeneticsValidator()
    if domain == "agriculture":
        from .agriculture import AgricultureValidator
        return AgricultureValidator()
    if domain in ("formal_logic", "logic"):
        from .formal_logic import FormalLogicValidator
        return FormalLogicValidator()
    if domain == "nutrition":
        from .nutrition import NutritionValidator
        return NutritionValidator()
    if domain in ("cryptography", "cryptology"):
        from .cryptography import CryptographyValidator
        return CryptographyValidator()
    if domain in ("exercise_science", "exercise"):
        from .exercise_science import ExerciseScienceValidator
        return ExerciseScienceValidator()
    if domain == "manufacturing":
        from .manufacturing import ManufacturingValidator
        return ManufacturingValidator()
    if domain == "finance":
        from .finance import FinanceValidator
        return FinanceValidator()
    if domain == "astronomy":
        from .astronomy import AstronomyValidator
        return AstronomyValidator()
    if domain in ("calendar_time", "calendar", "time"):
        from .calendar_time import CalendarTimeValidator
        return CalendarTimeValidator()
    if domain in ("networking", "network"):
        from .networking import NetworkingValidator
        return NetworkingValidator()
    if domain in ("electrical", "electrical_engineering"):
        from .electrical import ElectricalValidator
        return ElectricalValidator()
    if domain == "acoustics":
        from .acoustics import AcousticsValidator
        return AcousticsValidator()
    if domain == "optics":
        from .optics import OpticsValidator
        return OpticsValidator()
    if domain in ("geology", "earth_science"):
        from .geology import GeologyValidator
        return GeologyValidator()
    if domain in ("information_theory", "info_theory"):
        from .information_theory import InformationTheoryValidator
        return InformationTheoryValidator()
    if domain in ("document_validation", "doc_validation"):
        from .document_validation import DocumentValidationValidator
        return DocumentValidationValidator()
    return None
