"""Verifier registry — domain -> verifier module mapping."""
from . import chemistry, physics, statistics, mathematics, computer_science, biology, governance, scripture, linguistics, genetics, agriculture
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
    "linguistics": linguistics,
    "genetics": genetics,
    "agriculture": agriculture,
}


# Scripture is a cross-cutting verifier: it runs on EVERY packet (not just
# packets in a "scripture" domain) because scripture_anchors and refs can
# appear inside any domain's packet. The verifier no-ops on packets that
# don't carry references, so always running it is safe.
CROSS_CUTTING_VERIFIERS = (scripture,)


def run_for_domain(domain: str, packet):
    """Run all verifiers registered for this domain plus any cross-cutting
    verifiers. Returns list[VerifierResult].

    Cross-cutting verifiers (currently: scripture anchors) run on every
    packet because their inputs can appear in any domain. They short-circuit
    to a no-op when the packet doesn't carry the relevant fields.
    """
    results = []
    mod = VERIFIERS.get((domain or "").lower())
    if mod is not None:
        results.extend(mod.run(packet))
    for cross in CROSS_CUTTING_VERIFIERS:
        results.extend(cross.run(packet))
    return results


__all__ = [
    "VerifierResult", "VerifierStatus", "na", "confirm", "mismatch", "error",
    "run_for_domain", "VERIFIERS", "CROSS_CUTTING_VERIFIERS",
]
