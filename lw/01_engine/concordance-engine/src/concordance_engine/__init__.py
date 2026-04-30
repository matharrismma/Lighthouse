"""
concordance_engine — Four-gate decision validation engine.

    from concordance_engine.engine import EngineConfig, validate_packet
"""
from .engine import EngineConfig, validate_packet
from .packet import GateResult, ValidationResult

__all__ = ["EngineConfig", "validate_packet", "GateResult", "ValidationResult"]
__version__ = "1.0.0"
