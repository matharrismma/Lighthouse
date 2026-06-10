"""Axis coverage audit -- where the hand-set 7-axis grid loses resolution.

Matt: "there are more axes; we can use this to find them." Finding (empirical):
the verifiers' invariants are domain-PRIVATE -- every confirm/error sub-operation
tag (mathematics.equality, physics.dimensional, statistics.pvalue_calibration...)
is used by exactly ONE domain. So new axes cannot be found by matching names; a
cross-domain axis is only established by CO-CONFIRMATION (the discovery loop: when
one claim confirms across two domains, the invariants they used are the same axis).

What CAN be derived deterministically, and is the honest "propose candidate
dimensions" step: each domain checks N distinct invariants but the grid collapses
them into A coarse axes. Where N >> A, the grid is under-resolved -- those collapsed
invariants are candidate finer axes for the operator to NAME (and then verify by
co-confirmation across domains). This audit surfaces that gap from verifier
structure. It invents nothing; it shows what the engine already measures.

Read-only. Runs on the box (imports grid, scans verifiers/). No writes.
"""
from __future__ import annotations
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_VDIR = os.path.join(_REPO, "src", "concordance_engine", "verifiers")
# Two tag forms in the wild: inline -- confirm("mathematics.equality") -- and
# variable-assigned -- name = "formal_logic.tautology"; confirm(name, ...). The
# second form is used by formal_logic/number_theory/combinatorics/geometry/
# information_theory/quantum_computing; matching only the inline form under-counts
# the real invariant inventory (~48 in the formal cluster, not 34). Match both.
_TAG = re.compile(
    r"""(?:(?:confirm|error|mismatch|na)\(\s*|name\s*=\s*)['"]([a-z_]+)\.([a-z_]+)['"]"""
)


def _domain_invariants():
    """domain (verifier FILE stem) -> sorted distinct sub-operations it checks.

    Keyed by FILE STEM, not the tag prefix: a verifier abbreviates its own tags
    (computer_science.py writes confirm("cs.determinism")), and "cs" is NOT a real
    domain -- keying by the tag prefix invents phantom domains with 0 axes. The
    file stem is the real domain (computer_science.py -> computer_science)."""
    out = {}
    for fn in sorted(os.listdir(_VDIR)):
        if not fn.endswith(".py") or fn.startswith("_") or fn == "base.py":
            continue
        try:
            src = open(os.path.join(_VDIR, fn), encoding="utf-8").read()
        except OSError:
            continue
        subs = {sub for _pref, sub in _TAG.findall(src)}
        if subs:
            out[fn[:-3]] = sorted(subs)
    return out


def _axes_for(domain, axis_dims):
    """Resolve a tag-domain to its declared 7-axis signature (umbrella prefix)."""
    if domain in axis_dims:
        return sorted(axis_dims[domain])
    cands = [k for k in axis_dims if domain.startswith(k) or k.startswith(domain)]
    if cands:
        return sorted(axis_dims[max(cands, key=len)])
    return []


def main() -> int:
    from concordance_engine.grid import AXIS_DIMENSIONS, DIMENSIONS
    axis_dims = {d: set(a or []) for d, a in AXIS_DIMENSIONS.items()}
    inv = _domain_invariants()

    all_invariants = sorted({s for subs in inv.values() for s in subs})
    n_axes = len(DIMENSIONS)
    print("=== AXIS COVERAGE AUDIT ===")
    print(f"hand-set axes: {n_axes}   |   distinct verifier invariants measured: "
          f"{len(all_invariants)}   |   resolution gap: ~{len(all_invariants)/max(n_axes,1):.1f}x coarser\n")

    rows = []
    for dom in sorted(inv):
        invs = inv[dom]
        axes = _axes_for(dom, axis_dims)
        gap = len(invs) - len(axes)
        rows.append((gap, dom, invs, axes))
    rows.sort(key=lambda r: -r[0])

    print("Domains where the grid collapses the most resolution (candidate finer axes):")
    print(f"{'domain':22} {'invar':>5} {'axes':>4}  invariants collapsed into the axes")
    for gap, dom, invs, axes in rows[:14]:
        if len(invs) <= 1:
            continue
        print(f"{dom:22} {len(invs):>5} {len(axes):>4}  {', '.join(invs)[:84]}")
        print(f"{'':22} {'':>5} {'':>4}  -> currently all under: {axes}")

    print("\nNOTE: a candidate finer axis becomes a REAL axis only when >=2 INDEPENDENT")
    print("domains' invariants CO-CONFIRM one claim on it (witnesses). That is the next")
    print("step -- the discovery loop run across domains. This sheet proposes; co-")
    print("confirmation establishes; the operator names. Nothing here is invented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
