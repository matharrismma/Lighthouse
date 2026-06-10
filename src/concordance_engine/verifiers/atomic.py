"""Atomic-structure verifier — the electron layer of the atomic model.

The atom is the supreme cross-domain intersection: chemistry (electron
configuration -> valence -> bonding -> the periodic table), quantum (quantized
shells + quantum numbers), physics (energy levels), and DISCRETENESS (shells are
integer-quantized; capacity = 2n²). The engine already verifies element data
(periodic_table) and the constants (physical_constants: Rydberg, Bohr radius);
this supplies the missing ELECTRON STRUCTURE that ties them together. It is the
generator beneath molecular geometry (configuration -> valence -> VSEPR shape).

All checks are EXACT and deterministic (Principle B — a wrong verifier is worse
than none):

  * atomic.quantum_numbers   — (n, l, m_l, m_s) is a valid quantum-number set:
        n >= 1 integer; 0 <= l <= n-1; -l <= m_l <= l; m_s in {+1/2, -1/2}.
  * atomic.shell_capacity    — max electrons in shell n = 2n²; in a subshell of
        azimuthal number l = 2(2l+1) = 4l+2.
  * atomic.electron_configuration — ground-state configuration for atomic number
        Z (1-118) by the Madelung (n+l) order, WITH the standard ground-state
        exceptions (Cr, Cu, Nb, Mo, Ru, Rh, Pd, Ag, La, Ce, Gd, Pt, Au, Ac, Th,
        Pa, U, Np, Cm, Lr). Compared as a multiset of subshell populations, so it
        is robust to writing order (3d-vs-4s) and accepts noble-gas shorthand.

ATOM_VERIFY packet shape (any subset of fields):
    {"n": 3, "l": 2, "m_l": -1, "m_s": 0.5, "claimed_valid_quantum_numbers": true,
     "shell_n": 3, "claimed_shell_capacity": 18,
     "subshell_l": 2, "claimed_subshell_capacity": 10,
     "atomic_number": 24, "claimed_configuration": "[Ar] 3d5 4s1"}
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error

# Madelung (n+l, then n) fill order, covering Z = 1..118.
_MADELUNG = [
    (1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0), (3, 2), (4, 1), (5, 0),
    (4, 2), (5, 1), (6, 0), (4, 3), (5, 2), (6, 1), (7, 0), (5, 3), (6, 2), (7, 1),
]
_CAP = {0: 2, 1: 6, 2: 10, 3: 14}          # s p d f
_LSYM = {0: "s", 1: "p", 2: "d", 3: "f"}
_LNUM = {"s": 0, "p": 1, "d": 2, "f": 3}
_NOBLE_Z = {"He": 2, "Ne": 10, "Ar": 18, "Kr": 36, "Xe": 54, "Rn": 86, "Og": 118}

# Ground-state exceptions to the Madelung prediction, as deltas (subshell -> change).
# Standard textbook set. Each moves electron(s) to a half/fully-filled d/f subshell
# (or, for Lr, into 7p). Keys are atomic numbers; values map (n, l) -> delta.
_EXCEPTIONS: Dict[int, Dict[tuple, int]] = {
    24: {(4, 0): -1, (3, 2): +1},   # Cr  [Ar] 3d5 4s1
    29: {(4, 0): -1, (3, 2): +1},   # Cu  [Ar] 3d10 4s1
    41: {(5, 0): -1, (4, 2): +1},   # Nb  [Kr] 4d4 5s1
    42: {(5, 0): -1, (4, 2): +1},   # Mo  [Kr] 4d5 5s1
    44: {(5, 0): -1, (4, 2): +1},   # Ru  [Kr] 4d7 5s1
    45: {(5, 0): -1, (4, 2): +1},   # Rh  [Kr] 4d8 5s1
    46: {(5, 0): -2, (4, 2): +2},   # Pd  [Kr] 4d10
    47: {(5, 0): -1, (4, 2): +1},   # Ag  [Kr] 4d10 5s1
    57: {(4, 3): -1, (5, 2): +1},   # La  [Xe] 5d1 6s2
    58: {(4, 3): -1, (5, 2): +1},   # Ce  [Xe] 4f1 5d1 6s2
    64: {(4, 3): -1, (5, 2): +1},   # Gd  [Xe] 4f7 5d1 6s2
    78: {(6, 0): -1, (5, 2): +1},   # Pt  [Xe] 4f14 5d9 6s1
    79: {(6, 0): -1, (5, 2): +1},   # Au  [Xe] 4f14 5d10 6s1
    89: {(5, 3): -1, (6, 2): +1},   # Ac  [Rn] 6d1 7s2
    90: {(5, 3): -2, (6, 2): +2},   # Th  [Rn] 6d2 7s2
    91: {(5, 3): -1, (6, 2): +1},   # Pa  [Rn] 5f2 6d1 7s2
    92: {(5, 3): -1, (6, 2): +1},   # U   [Rn] 5f3 6d1 7s2
    93: {(5, 3): -1, (6, 2): +1},   # Np  [Rn] 5f4 6d1 7s2
    96: {(5, 3): -1, (6, 2): +1},   # Cm  [Rn] 5f7 6d1 7s2
    103: {(6, 2): -1, (7, 1): +1},  # Lr  [Rn] 5f14 7s2 7p1
}


def _ground_config(z: int) -> Optional[Dict[tuple, int]]:
    """Ground-state configuration of element Z as {(n, l): electrons}."""
    if not isinstance(z, int) or z < 1 or z > 118:
        return None
    cfg: Dict[tuple, int] = {}
    remaining = z
    for (n, l) in _MADELUNG:
        if remaining <= 0:
            break
        c = min(_CAP[l], remaining)
        cfg[(n, l)] = c
        remaining -= c
    for key, delta in _EXCEPTIONS.get(z, {}).items():
        cfg[key] = cfg.get(key, 0) + delta
        if cfg[key] <= 0:
            cfg.pop(key, None)
    return cfg


def _fmt(cfg: Dict[tuple, int]) -> str:
    return " ".join(f"{n}{_LSYM[l]}{cfg[(n, l)]}"
                    for (n, l) in sorted(cfg, key=lambda k: (k[0], k[1])))


def _parse_config(s: str) -> Optional[Dict[tuple, int]]:
    """Parse a configuration string into {(n, l): electrons}. Accepts noble-gas
    shorthand ([Ar]...) and is order-independent."""
    if not isinstance(s, str) or not s.strip():
        return None
    out: Dict[tuple, int] = {}
    s = s.strip()
    m = re.match(r"\[([A-Z][a-z]?)\]", s)
    if m:
        corez = _NOBLE_Z.get(m.group(1))
        if corez is None:
            return None
        core = _ground_config(corez)
        if core:
            for k, v in core.items():
                out[k] = out.get(k, 0) + v
        s = s[m.end():]
    found = re.findall(r"(\d+)\s*([spdfSPDF])\s*(\d+)", s)
    if not found and not m:
        return None
    for n_s, l_c, c_s in found:
        l = _LNUM[l_c.lower()]
        out[(int(n_s), l)] = out.get((int(n_s), l), 0) + int(c_s)
    return out


def verify_quantum_numbers(spec: Dict[str, Any]) -> VerifierResult:
    name = "atomic.quantum_numbers"
    if "n" not in spec or "l" not in spec:
        return na(name)
    try:
        n = int(spec["n"]); l = int(spec["l"])
        m_l = spec.get("m_l", spec.get("ml"))
        m_s = spec.get("m_s", spec.get("ms"))
        claimed = spec.get("claimed_valid_quantum_numbers")
    except (TypeError, ValueError) as e:
        return error(name, f"non-integer quantum number: {e}")
    reasons: List[str] = []
    if n < 1:
        reasons.append(f"n={n} must be >= 1")
    if not (0 <= l <= n - 1):
        reasons.append(f"l={l} must satisfy 0 <= l <= n-1 ({n - 1})")
    if m_l is not None:
        try:
            if not (-l <= int(m_l) <= l):
                reasons.append(f"m_l={m_l} must satisfy -l..+l ({-l}..{l})")
        except (TypeError, ValueError):
            reasons.append(f"m_l={m_l!r} not an integer")
    if m_s is not None:
        try:
            if abs(abs(float(m_s)) - 0.5) > 1e-9:
                reasons.append(f"m_s={m_s} must be +1/2 or -1/2")
        except (TypeError, ValueError):
            reasons.append(f"m_s={m_s!r} not numeric")
    valid = not reasons
    detail = "valid quantum-number set" if valid else "; ".join(reasons)
    if claimed is None:
        return confirm(name, detail) if valid else mismatch(name, detail)
    if bool(claimed) == valid:
        return confirm(name, f"validity {valid} matches claim; {detail}")
    return mismatch(name, f"claimed valid={claimed} but set is {'valid' if valid else 'invalid'}: {detail}")


def verify_shell_capacity(spec: Dict[str, Any]) -> VerifierResult:
    name = "atomic.shell_capacity"
    if "shell_n" in spec and "claimed_shell_capacity" in spec:
        try:
            n = int(spec["shell_n"]); claimed = int(spec["claimed_shell_capacity"])
        except (TypeError, ValueError) as e:
            return error(name, f"non-integer: {e}")
        if n < 1:
            return error(name, f"shell_n={n} must be >= 1")
        actual = 2 * n * n
        if actual == claimed:
            return confirm(name, f"shell n={n} holds 2n² = {actual} electrons")
        return mismatch(name, f"shell n={n} holds 2n² = {actual}, not {claimed}")
    if "subshell_l" in spec and "claimed_subshell_capacity" in spec:
        try:
            l = int(spec["subshell_l"]); claimed = int(spec["claimed_subshell_capacity"])
        except (TypeError, ValueError) as e:
            return error(name, f"non-integer: {e}")
        if l < 0:
            return error(name, f"subshell_l={l} must be >= 0")
        actual = 2 * (2 * l + 1)
        if actual == claimed:
            return confirm(name, f"subshell l={l} ({_LSYM.get(l, '?')}) holds 2(2l+1) = {actual}")
        return mismatch(name, f"subshell l={l} holds 2(2l+1) = {actual}, not {claimed}")
    return na(name)


def verify_electron_configuration(spec: Dict[str, Any]) -> VerifierResult:
    name = "atomic.electron_configuration"
    z = spec.get("atomic_number", spec.get("Z"))
    claimed = spec.get("claimed_configuration")
    if z is None or claimed is None:
        return na(name)
    try:
        z = int(z)
    except (TypeError, ValueError):
        return error(name, f"atomic_number {z!r} not an integer")
    truth = _ground_config(z)
    if truth is None:
        return error(name, f"atomic_number {z} out of range (1-118)")
    parsed = _parse_config(str(claimed))
    if parsed is None:
        return na(name, f"cannot parse claimed configuration {claimed!r}")
    if sum(parsed.values()) != z:
        return mismatch(name, f"claimed config has {sum(parsed.values())} electrons, Z={z} needs {z}",
                        {"ground_state": _fmt(truth)})
    if parsed == truth:
        note = " (ground-state exception)" if z in _EXCEPTIONS else ""
        return confirm(name, f"Z={z} ground state = {_fmt(truth)}{note}")
    return mismatch(name, f"Z={z} ground state is {_fmt(truth)}, not {_fmt(parsed)}",
                    {"ground_state": _fmt(truth), "claimed": _fmt(parsed)})


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    av = packet.get("ATOM_VERIFY") or {}
    results: List[VerifierResult] = []
    if "n" in av and "l" in av:
        results.append(verify_quantum_numbers(av))
    if ("shell_n" in av and "claimed_shell_capacity" in av) or \
       ("subshell_l" in av and "claimed_subshell_capacity" in av):
        results.append(verify_shell_capacity(av))
    if ("atomic_number" in av or "Z" in av) and "claimed_configuration" in av:
        results.append(verify_electron_configuration(av))
    if not results:
        results.append(na("atomic", "no ATOM_VERIFY artifacts present"))
    return results
