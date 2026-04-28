"""Verifier registry — domain -> verifier module mapping."""
from . import chemistry, physics, statistics, mathematics, computer_science, biology, governance
from .base import VerifierResult, VerifierStatus, na, confirm, mismatch, error

VERIFIERS = {
    "chemistry": chemistry,
    "physics": physics,
    "statistics": statistics,
    "mathematics": mathematics,
    "computer_science": computer_science,
    "cs": computer_science,
    "biology": biology,
    "governance": governance,
    "business": governance,
    "household": governance,
    "education": governance,
    "church": governance,
}


def run_for_domain(domain: str, packet):
    """Run all verifiers registered for this domain. Returns list[VerifierResult]."""
    mod = VERIFIERS.get((domain or "").lower())
    if mod is None:
        return []
    return mod.run(packet)


__all__ = [
    "VerifierResult", "VerifierStatus", "na", "confirm", "mismatch", "error",
    "run_for_domain", "VERIFIERS",
]
