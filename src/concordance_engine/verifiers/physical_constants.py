"""Physical constants verifier.

CODATA 2018 recommended values for fundamental physical constants.
All values are public domain (US government via NIST). Where a value
is exact by SI definition (post-2019 redefinition), the constant is
marked accordingly.

Checks:
  * physical_constant.value — claim of a named constant's value matches
    CODATA within a stated tolerance

CONST_VERIFY shape:
    {
      "constant": "speed_of_light",   # see _CONSTANTS below for the keys
      "claimed_value": 299792458,
      "claimed_unit": "m/s",           # optional, must match if given
      "rel_tol": 1e-4,                 # optional, default 1e-4
    }
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch


# Each entry: (canonical_value, unit, is_exact, source_note)
# Aliases for common synonyms come below in _ALIASES.
_CONSTANTS: Dict[str, Dict[str, Any]] = {
    "speed_of_light":             {"value": 299_792_458.0,            "unit": "m/s",          "exact": True,  "note": "exact since 1983 SI"},
    "planck_constant":            {"value": 6.626_070_15e-34,         "unit": "J*s",          "exact": True,  "note": "exact since 2019 SI redefinition"},
    "reduced_planck_constant":    {"value": 1.054_571_817e-34,        "unit": "J*s",          "exact": False, "note": "derived"},
    "elementary_charge":          {"value": 1.602_176_634e-19,        "unit": "C",            "exact": True,  "note": "exact since 2019 SI"},
    "boltzmann_constant":         {"value": 1.380_649e-23,            "unit": "J/K",          "exact": True,  "note": "exact since 2019 SI"},
    "avogadro_constant":          {"value": 6.022_140_76e23,          "unit": "1/mol",        "exact": True,  "note": "exact since 2019 SI"},
    "gas_constant":               {"value": 8.314_462_618,            "unit": "J/(mol*K)",    "exact": True,  "note": "exact (N_A * k_B)"},
    "electron_mass":              {"value": 9.109_383_7015e-31,       "unit": "kg",           "exact": False},
    "proton_mass":                {"value": 1.672_621_923_69e-27,     "unit": "kg",           "exact": False},
    "neutron_mass":               {"value": 1.674_927_498_04e-27,     "unit": "kg",           "exact": False},
    "atomic_mass_unit":           {"value": 1.660_539_066_60e-27,     "unit": "kg",           "exact": False},
    "gravitational_constant":     {"value": 6.674_30e-11,             "unit": "m^3/(kg*s^2)", "exact": False, "note": "G; weakest-measured fundamental"},
    "vacuum_permittivity":        {"value": 8.854_187_8128e-12,       "unit": "F/m",          "exact": False, "note": "epsilon_0"},
    "vacuum_permeability":        {"value": 1.256_637_062_12e-6,      "unit": "N/A^2",        "exact": False, "note": "mu_0"},
    "fine_structure_constant":    {"value": 7.297_352_5693e-3,        "unit": "dimensionless","exact": False, "note": "alpha"},
    "rydberg_constant":           {"value": 1.097_373_156_8160e7,     "unit": "1/m",          "exact": False},
    "bohr_radius":                {"value": 5.291_772_109_03e-11,     "unit": "m",            "exact": False, "note": "a_0"},
    "stefan_boltzmann_constant":  {"value": 5.670_374_419e-8,         "unit": "W/(m^2*K^4)",  "exact": False, "note": "sigma"},
    "standard_gravity":           {"value": 9.806_65,                 "unit": "m/s^2",        "exact": True,  "note": "exact by definition"},
    "atmosphere":                 {"value": 101_325.0,                "unit": "Pa",           "exact": True,  "note": "1 atm; exact by definition"},
    "molar_volume_stp":           {"value": 0.022_413_969_54,         "unit": "m^3/mol",      "exact": False, "note": "ideal gas at 0°C, 100 kPa"},
    "wien_displacement_constant": {"value": 2.897_771_955e-3,         "unit": "m*K",          "exact": False},
    "faraday_constant":           {"value": 96_485.332_12,            "unit": "C/mol",        "exact": True,  "note": "exact (N_A * e)"},
}

# Common synonyms → canonical key. The classifier will hand us whatever
# Claude returned; this absorbs the variants without complaining.
_ALIASES: Dict[str, str] = {
    "c": "speed_of_light",
    "light_speed": "speed_of_light",
    "speed_of_light_in_vacuum": "speed_of_light",
    "h": "planck_constant",
    "planck": "planck_constant",
    "h_bar": "reduced_planck_constant",
    "hbar": "reduced_planck_constant",
    "e": "elementary_charge",
    "electron_charge": "elementary_charge",
    "k_b": "boltzmann_constant",
    "kb": "boltzmann_constant",
    "boltzmann": "boltzmann_constant",
    "n_a": "avogadro_constant",
    "na": "avogadro_constant",
    "avogadro": "avogadro_constant",
    "avogadro's_number": "avogadro_constant",
    "avogadros_number": "avogadro_constant",
    "avogadro_number": "avogadro_constant",
    "avogadro's_constant": "avogadro_constant",
    "avogadros_constant": "avogadro_constant",
    "r": "gas_constant",
    "universal_gas_constant": "gas_constant",
    "ideal_gas_constant": "gas_constant",
    "m_e": "electron_mass",
    "me": "electron_mass",
    "m_p": "proton_mass",
    "mp": "proton_mass",
    "m_n": "neutron_mass",
    "mn": "neutron_mass",
    "u": "atomic_mass_unit",
    "amu": "atomic_mass_unit",
    "dalton": "atomic_mass_unit",
    "g_newton": "gravitational_constant",
    "newton_constant": "gravitational_constant",
    "epsilon_0": "vacuum_permittivity",
    "permittivity": "vacuum_permittivity",
    "mu_0": "vacuum_permeability",
    "permeability": "vacuum_permeability",
    "alpha": "fine_structure_constant",
    "a_0": "bohr_radius",
    "sigma": "stefan_boltzmann_constant",
    "g": "standard_gravity",          # surface gravity, not G!
    "earth_gravity": "standard_gravity",
    "atm": "atmosphere",
    "1_atm": "atmosphere",
    "f": "faraday_constant",
    "faraday": "faraday_constant",
}


def _canonical(name: str) -> str:
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in _CONSTANTS:
        return key
    return _ALIASES.get(key, key)


# Unit-string normalizer: accept the common synonyms Claude is likely
# to produce ("meter/second" for "m/s", "J·s" for "J*s", etc.) so the
# verifier doesn't fail on cosmetic format differences.
_UNIT_ALIASES = {
    "meter/second": "m/s", "meters/second": "m/s", "metre/second": "m/s",
    "meters_per_second": "m/s", "meter_per_second": "m/s", "m_per_s": "m/s",
    "meter/second^2": "m/s^2", "meters/second^2": "m/s^2",
    "m/s2": "m/s^2", "m*s^-2": "m/s^2", "m·s^-2": "m/s^2",
    "j·s": "J*s", "j*s": "J*s", "joule·second": "J*s", "joule_second": "J*s",
    "joule/kelvin": "J/K", "j/k": "J/K", "j·k^-1": "J/K",
    "1/mol": "1/mol", "mol^-1": "1/mol", "per_mole": "1/mol",
    "permole": "1/mol",            # space-squashed "per mole"
    "permol": "1/mol",
    "permolecule": "1/mol",
    "particles/mole": "1/mol", "particles/mol": "1/mol",
    "atoms/mole": "1/mol", "atoms/mol": "1/mol",
    "entities/mole": "1/mol", "molecules/mole": "1/mol",
    "j/(mol·k)": "J/(mol*K)", "j/(mol*k)": "J/(mol*K)",
    "joule/(mole·kelvin)": "J/(mol*K)",
    "kilogram": "kg", "kilograms": "kg",
    "coulomb": "C", "coulombs": "C",
    "pascal": "Pa", "pascals": "Pa",
    "farad/meter": "F/m", "f/m": "F/m",
    "newton/ampere^2": "N/A^2", "n/a^2": "N/A^2", "n·a^-2": "N/A^2",
    "1/m": "1/m", "m^-1": "1/m", "per_meter": "1/m",
    "watt/(meter^2*kelvin^4)": "W/(m^2*K^4)", "w/(m^2*k^4)": "W/(m^2*K^4)",
    "coulomb/mol": "C/mol", "c/mol": "C/mol",
    "meter·kelvin": "m*K", "m*k": "m*K",
    "meter^3/(kilogram*second^2)": "m^3/(kg*s^2)",
    "m^3/(kg·s^2)": "m^3/(kg*s^2)",
    "dimensionless": "dimensionless", "unitless": "dimensionless", "": "dimensionless",
}


def _normalize_unit(u: str) -> str:
    if not u:
        return ""
    k = u.strip().lower().replace("·", "*").replace(" ", "")
    # Try exact alias hit on the normalized form
    if k in _UNIT_ALIASES:
        return _UNIT_ALIASES[k]
    # Best-effort: also strip case-folding from the canonical forms
    canonicals = {v.lower(): v for v in _UNIT_ALIASES.values()}
    if k in canonicals:
        return canonicals[k]
    # Fall through — caller compares strings as a last resort
    return u.strip()


def verify_physical_constant(spec: Dict[str, Any]) -> VerifierResult:
    """Check a claim about a named fundamental physical constant."""
    name = "physical_constants.value"
    raw_name = spec.get("constant", "")
    claimed = spec.get("claimed_value")
    if not raw_name or claimed is None:
        return na(name)
    canonical = _canonical(raw_name)
    record = _CONSTANTS.get(canonical)
    if not record:
        return na(name)
    try:
        claim = float(claimed)
    except (TypeError, ValueError):
        return na(name)
    actual = record["value"]
    rel_tol = float(spec.get("rel_tol") or 1e-4)
    if actual == 0:
        threshold = 1e-12
    else:
        threshold = abs(actual) * rel_tol
    diff = abs(actual - claim)
    data = {
        "constant": canonical,
        "actual_value": actual,
        "unit": record["unit"],
        "claimed_value": claim,
        "claimed_unit": spec.get("claimed_unit"),
        "diff": diff,
        "rel_tol": rel_tol,
        "exact": record.get("exact", False),
        "note": record.get("note", ""),
        "source": "CODATA 2018 / NIST",
    }
    # If a unit was provided and doesn't match after normalization, surface
    # that distinctly. We normalize common synonyms ("meter/second" → "m/s")
    # so the verifier doesn't fail on cosmetic format differences.
    claimed_unit_raw = (spec.get("claimed_unit") or "").strip()
    if claimed_unit_raw:
        claimed_norm = _normalize_unit(claimed_unit_raw)
        actual_norm = _normalize_unit(record["unit"])
        data["claimed_unit_normalized"] = claimed_norm
        if claimed_norm != actual_norm and claimed_unit_raw.lower() != record["unit"].lower():
            return mismatch(
                name,
                f"{canonical} unit mismatch: actual {record['unit']}, claimed {claimed_unit_raw}",
                data,
            )
    if diff <= threshold:
        return confirm(
            name,
            f"{canonical} = {actual} {record['unit']} (claim {claim} within {rel_tol:.0e})",
            data,
        )
    return mismatch(
        name,
        f"{canonical} actual {actual} {record['unit']}, claimed {claim}",
        data,
    )


def list_constants() -> List[Dict[str, Any]]:
    """Public listing — useful for /agents and for documentation pages."""
    out = []
    for key, rec in _CONSTANTS.items():
        out.append({
            "constant": key,
            "value": rec["value"],
            "unit": rec["unit"],
            "exact": rec.get("exact", False),
            "note": rec.get("note", ""),
        })
    return sorted(out, key=lambda x: x["constant"])


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CONST_VERIFY") or {}
    if cv.get("constant") and cv.get("claimed_value") is not None:
        results.append(verify_physical_constant(cv))
    if not results:
        results.append(na("physical_constants"))
    return results
