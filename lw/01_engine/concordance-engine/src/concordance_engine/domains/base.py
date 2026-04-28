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
    return None
