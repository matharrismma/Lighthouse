"""
concordance_engine.verifiers — Computational verification modules.

Each module exposes named verifier functions and a run(packet) helper
that the engine calls when the relevant fields are present.
"""
from . import chemistry, physics, mathematics, statistics, computer_science, biology, governance, scripture

__all__ = [
    "chemistry", "physics", "mathematics", "statistics",
    "computer_science", "biology", "governance", "scripture",
]
