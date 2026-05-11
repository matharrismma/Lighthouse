"""Periodic table verifier.

IUPAC standard atomic weights (2021) and element identity.
Values are public domain. Elements 1-118.

Checks:
  * periodic_table.atomic_number — symbol ↔ atomic number
  * periodic_table.atomic_mass   — claimed atomic mass vs IUPAC standard
  * periodic_table.element_name  — symbol ↔ name

PT_VERIFY shape (any subset):
    {
      "symbol": "Fe",
      "claimed_atomic_number": 26,
      "claimed_atomic_mass": 55.845,
      "claimed_name": "iron",
      "mass_rel_tol": 0.01,
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch


# (atomic_number, symbol, name, standard_atomic_weight)
# Atomic weights are IUPAC 2021 conventional values. For elements with
# no stable isotope, the mass of the most stable / longest-lived isotope
# is used and marked as such in the note field at lookup time.
_ELEMENTS: List[Tuple[int, str, str, float]] = [
    (1,   "H",  "hydrogen",       1.008),
    (2,   "He", "helium",         4.002602),
    (3,   "Li", "lithium",        6.94),
    (4,   "Be", "beryllium",      9.0121831),
    (5,   "B",  "boron",          10.81),
    (6,   "C",  "carbon",         12.011),
    (7,   "N",  "nitrogen",       14.007),
    (8,   "O",  "oxygen",         15.999),
    (9,   "F",  "fluorine",       18.998403163),
    (10,  "Ne", "neon",           20.1797),
    (11,  "Na", "sodium",         22.98976928),
    (12,  "Mg", "magnesium",      24.305),
    (13,  "Al", "aluminum",       26.9815385),
    (14,  "Si", "silicon",        28.085),
    (15,  "P",  "phosphorus",     30.973761998),
    (16,  "S",  "sulfur",         32.06),
    (17,  "Cl", "chlorine",       35.45),
    (18,  "Ar", "argon",          39.948),
    (19,  "K",  "potassium",      39.0983),
    (20,  "Ca", "calcium",        40.078),
    (21,  "Sc", "scandium",       44.955908),
    (22,  "Ti", "titanium",       47.867),
    (23,  "V",  "vanadium",       50.9415),
    (24,  "Cr", "chromium",       51.9961),
    (25,  "Mn", "manganese",      54.938044),
    (26,  "Fe", "iron",           55.845),
    (27,  "Co", "cobalt",         58.933194),
    (28,  "Ni", "nickel",         58.6934),
    (29,  "Cu", "copper",         63.546),
    (30,  "Zn", "zinc",           65.38),
    (31,  "Ga", "gallium",        69.723),
    (32,  "Ge", "germanium",      72.630),
    (33,  "As", "arsenic",        74.921595),
    (34,  "Se", "selenium",       78.971),
    (35,  "Br", "bromine",        79.904),
    (36,  "Kr", "krypton",        83.798),
    (37,  "Rb", "rubidium",       85.4678),
    (38,  "Sr", "strontium",      87.62),
    (39,  "Y",  "yttrium",        88.90584),
    (40,  "Zr", "zirconium",      91.224),
    (41,  "Nb", "niobium",        92.90637),
    (42,  "Mo", "molybdenum",     95.95),
    (43,  "Tc", "technetium",     98.0),
    (44,  "Ru", "ruthenium",      101.07),
    (45,  "Rh", "rhodium",        102.90550),
    (46,  "Pd", "palladium",      106.42),
    (47,  "Ag", "silver",         107.8682),
    (48,  "Cd", "cadmium",        112.414),
    (49,  "In", "indium",         114.818),
    (50,  "Sn", "tin",            118.710),
    (51,  "Sb", "antimony",       121.760),
    (52,  "Te", "tellurium",      127.60),
    (53,  "I",  "iodine",         126.90447),
    (54,  "Xe", "xenon",          131.293),
    (55,  "Cs", "cesium",         132.90545196),
    (56,  "Ba", "barium",         137.327),
    (57,  "La", "lanthanum",      138.90547),
    (58,  "Ce", "cerium",         140.116),
    (59,  "Pr", "praseodymium",   140.90766),
    (60,  "Nd", "neodymium",      144.242),
    (61,  "Pm", "promethium",     145.0),
    (62,  "Sm", "samarium",       150.36),
    (63,  "Eu", "europium",       151.964),
    (64,  "Gd", "gadolinium",     157.25),
    (65,  "Tb", "terbium",        158.92535),
    (66,  "Dy", "dysprosium",     162.500),
    (67,  "Ho", "holmium",        164.93033),
    (68,  "Er", "erbium",         167.259),
    (69,  "Tm", "thulium",        168.93422),
    (70,  "Yb", "ytterbium",      173.054),
    (71,  "Lu", "lutetium",       174.9668),
    (72,  "Hf", "hafnium",        178.49),
    (73,  "Ta", "tantalum",       180.94788),
    (74,  "W",  "tungsten",       183.84),
    (75,  "Re", "rhenium",        186.207),
    (76,  "Os", "osmium",         190.23),
    (77,  "Ir", "iridium",        192.217),
    (78,  "Pt", "platinum",       195.084),
    (79,  "Au", "gold",           196.966569),
    (80,  "Hg", "mercury",        200.592),
    (81,  "Tl", "thallium",       204.38),
    (82,  "Pb", "lead",           207.2),
    (83,  "Bi", "bismuth",        208.98040),
    (84,  "Po", "polonium",       209.0),
    (85,  "At", "astatine",       210.0),
    (86,  "Rn", "radon",          222.0),
    (87,  "Fr", "francium",       223.0),
    (88,  "Ra", "radium",         226.0),
    (89,  "Ac", "actinium",       227.0),
    (90,  "Th", "thorium",        232.0377),
    (91,  "Pa", "protactinium",   231.03588),
    (92,  "U",  "uranium",        238.02891),
    (93,  "Np", "neptunium",      237.0),
    (94,  "Pu", "plutonium",      244.0),
    (95,  "Am", "americium",      243.0),
    (96,  "Cm", "curium",         247.0),
    (97,  "Bk", "berkelium",      247.0),
    (98,  "Cf", "californium",    251.0),
    (99,  "Es", "einsteinium",    252.0),
    (100, "Fm", "fermium",        257.0),
    (101, "Md", "mendelevium",    258.0),
    (102, "No", "nobelium",       259.0),
    (103, "Lr", "lawrencium",     266.0),
    (104, "Rf", "rutherfordium",  267.0),
    (105, "Db", "dubnium",        268.0),
    (106, "Sg", "seaborgium",     269.0),
    (107, "Bh", "bohrium",        270.0),
    (108, "Hs", "hassium",        277.0),
    (109, "Mt", "meitnerium",     278.0),
    (110, "Ds", "darmstadtium",   281.0),
    (111, "Rg", "roentgenium",    282.0),
    (112, "Cn", "copernicium",    285.0),
    (113, "Nh", "nihonium",       286.0),
    (114, "Fl", "flerovium",      289.0),
    (115, "Mc", "moscovium",      290.0),
    (116, "Lv", "livermorium",    293.0),
    (117, "Ts", "tennessine",     294.0),
    (118, "Og", "oganesson",      294.0),
]

# Stable isotope availability — when False, the listed atomic mass is the
# longest-lived isotope's mass and exactness is lower.
_NO_STABLE_ISOTOPE = frozenset({
    "Tc", "Pm",
    "Po", "At", "Rn", "Fr", "Ra", "Ac",
    "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr",
    "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn",
    "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
})

_BY_SYMBOL: Dict[str, Dict[str, Any]] = {
    s: {"atomic_number": z, "symbol": s, "name": n, "atomic_mass": m,
        "stable": s not in _NO_STABLE_ISOTOPE}
    for z, s, n, m in _ELEMENTS
}
_BY_NAME: Dict[str, Dict[str, Any]] = {
    n.lower(): v for v, n in zip(_BY_SYMBOL.values(), (e[2] for e in _ELEMENTS))
}
_BY_NUMBER: Dict[int, Dict[str, Any]] = {
    z: _BY_SYMBOL[s] for z, s, _, _ in _ELEMENTS
}


def _lookup(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Identify an element from any of: symbol, name, or atomic_number."""
    sym = (spec.get("symbol") or "").strip()
    if sym:
        # IUPAC symbols are case-sensitive (Fe, not FE). Normalize first
        # letter cap, second lower, for the common case.
        if len(sym) == 1:
            sym = sym.upper()
        elif len(sym) == 2:
            sym = sym[0].upper() + sym[1].lower()
        elif len(sym) == 3:
            sym = sym[0].upper() + sym[1:].lower()
        if sym in _BY_SYMBOL:
            return _BY_SYMBOL[sym]
    name = (spec.get("name") or "").strip().lower()
    if name and name in _BY_NAME:
        return _BY_NAME[name]
    z = spec.get("atomic_number")
    if z is not None:
        try:
            zi = int(z)
            if zi in _BY_NUMBER:
                return _BY_NUMBER[zi]
        except (TypeError, ValueError):
            pass
    return None


def verify_element(spec: Dict[str, Any]) -> VerifierResult:
    """Verify any claim that ties together symbol/name/number/mass."""
    name = "periodic_table.element"
    el = _lookup(spec)
    if not el:
        return na(name)
    mismatches: List[str] = []
    data: Dict[str, Any] = {
        "looked_up": el,
        "source": "IUPAC 2021 standard atomic weights",
    }
    claimed_z = spec.get("claimed_atomic_number")
    if claimed_z is not None:
        try:
            cz = int(claimed_z)
            data["claimed_atomic_number"] = cz
            if cz != el["atomic_number"]:
                mismatches.append(f"atomic number: actual Z={el['atomic_number']}, claimed {cz}")
        except (TypeError, ValueError):
            pass
    claimed_name = (spec.get("claimed_name") or "").strip().lower()
    if claimed_name:
        data["claimed_name"] = claimed_name
        if claimed_name != el["name"]:
            mismatches.append(f"name: actual {el['name']}, claimed {claimed_name}")
    claimed_symbol = (spec.get("claimed_symbol") or "").strip()
    if claimed_symbol:
        # Normalize for comparison
        norm = claimed_symbol
        if len(norm) == 1: norm = norm.upper()
        elif len(norm) >= 2: norm = norm[0].upper() + norm[1:].lower()
        data["claimed_symbol"] = norm
        if norm != el["symbol"]:
            mismatches.append(f"symbol: actual {el['symbol']}, claimed {norm}")
    claimed_mass = spec.get("claimed_atomic_mass")
    if claimed_mass is not None:
        try:
            cm = float(claimed_mass)
            data["claimed_atomic_mass"] = cm
            rel_tol = float(spec.get("mass_rel_tol") or 0.01)
            threshold = abs(el["atomic_mass"]) * rel_tol
            diff = abs(el["atomic_mass"] - cm)
            data["actual_atomic_mass"] = el["atomic_mass"]
            data["mass_diff"] = diff
            if diff > threshold:
                mismatches.append(
                    f"atomic mass: actual {el['atomic_mass']}, claimed {cm} (tol {rel_tol})"
                )
        except (TypeError, ValueError):
            pass
    # Did the caller actually claim anything? If not, NA.
    if not any(k in spec for k in (
        "claimed_atomic_number", "claimed_name", "claimed_symbol", "claimed_atomic_mass",
    )):
        return na(name)
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(
        name,
        f"{el['symbol']} ({el['name']}, Z={el['atomic_number']}, m={el['atomic_mass']}) — claims match",
        data,
    )


def list_elements() -> List[Dict[str, Any]]:
    return [
        {"atomic_number": z, "symbol": s, "name": n, "atomic_mass": m,
         "stable": s not in _NO_STABLE_ISOTOPE}
        for z, s, n, m in _ELEMENTS
    ]


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    pv = packet.get("PT_VERIFY") or {}
    if pv:
        results.append(verify_element(pv))
    if not results:
        results.append(na("periodic_table"))
    return results
