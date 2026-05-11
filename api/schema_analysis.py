"""Schema-level structural analysis of the engine's verifier inventory.

The engine has 63 verifier modules. Each has an input schema — the fields
it accepts. Those fields are data, not metadata. They carry the verifier's
implicit dimensions.

This module reads the manifest, extracts field names and unit suffixes,
and computes structural variation across canonical domains. When two
domains carry the same axis signature but very different input schemas,
the schemas reveal a dimension the axes don't yet name.

No oracle. No LLM. Pure analysis of what the engine has already written
about its own work-shape.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Set, Tuple

# Common SI / engineering unit suffixes that show up at the end of field
# names: mass_kg, half_life_seconds, slope_ratio. The list is descriptive,
# not normative — the engine extracts what's present.
_UNIT_SUFFIXES: Set[str] = {
    # time
    "s", "sec", "seconds", "minute", "minutes", "hours", "days", "years",
    # length
    "m", "meter", "meters", "cm", "mm", "km", "nm", "angstrom",
    # mass
    "g", "kg", "kilograms", "grams", "tons",
    # area / volume
    "hectares", "acres", "liter", "litres", "m2", "m3",
    # force / pressure / energy
    "n", "newtons", "j", "joules", "pa", "pascal", "bar", "atm",
    "ev", "mev", "gev", "amu",
    # electrical
    "v", "volts", "a", "amps", "ohms", "watts", "w",
    # radioactivity / count
    "bq", "becquerels", "count", "counts",
    # frequency / rate
    "hz", "mhz", "ghz", "khz", "rpm", "fps",
    # temperature
    "k", "kelvin", "c", "celsius", "f", "fahrenheit",
    # chemistry
    "mol", "mole", "molar", "ph", "ppm", "ppb",
    # statistics / probability
    "ratio", "percent", "pct", "p", "alpha", "beta",
    # finance / valuation
    "usd", "dollars", "cents", "bps",
    # categorical hints
    "name", "type", "class", "category", "kind", "crop", "zone",
    "law", "method", "test", "tail", "metric",
}


def _extract_fields_from_text(text: str) -> Set[str]:
    """Pull bare JSON keys out of any JSON-like text. Conservative — only
    keys that look like Python identifiers."""
    return set(re.findall(r'"([a-z][a-z0-9_]+)"\s*:', text))


# OpenAPI scaffolding keys that show up in every tool definition and would
# pollute similarity scoring if treated as content fields.
_SCAFFOLDING_KEYS: Set[str] = {
    "description", "properties", "required", "type", "spec",
    "items", "enum", "default", "format", "minimum", "maximum",
    "additionalproperties", "$ref", "anyof", "oneof", "allof",
}


def extract_schema(name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """For one verifier, extract its field signature from manifest data.

    The engine's manifest stores actual field names inside spec.description
    as JSON example strings (e.g. '{"equation": "...", "symbols": {...}}').
    Pull fields ONLY from those example strings — not from the OpenAPI
    scaffolding ('type', 'properties', etc.) which is identical for every
    tool and would drown the signal.

    Then split each field name by underscore and isolate trailing
    unit suffixes (mass_kg → unit kg, bare name mass).
    """
    # Locate spec.description if present (this is where the examples live)
    example_text = description or ""
    if isinstance(parameters, dict):
        props = parameters.get("properties", {}) or {}
        spec_block = props.get("spec", {}) or {}
        if isinstance(spec_block, dict):
            example_text = (spec_block.get("description", "") or "") + "\n" + example_text

    fields: Set[str] = _extract_fields_from_text(example_text)
    # Drop OpenAPI scaffolding so only content fields remain
    fields = {f for f in fields if f.lower() not in _SCAFFOLDING_KEYS}

    bare_names: Set[str] = set()
    units: Set[str] = set()
    for f in fields:
        parts = f.split("_")
        last = parts[-1].lower()
        if last in _UNIT_SUFFIXES and len(parts) > 1:
            units.add(last)
            bare = "_".join(parts[:-1])
            bare_names.add(bare)
        else:
            bare_names.add(f)
            # Some bare names ARE units (e.g. just "ph")
            if last in _UNIT_SUFFIXES:
                units.add(last)

    return {
        "name": name,
        "all_fields": sorted(fields),
        "bare_names": sorted(bare_names),
        "units": sorted(units),
        "field_count": len(fields),
    }


def jaccard(a: Set[Any], b: Set[Any]) -> float:
    """Standard Jaccard similarity. Returns 1.0 when both sets empty."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyze_cluster(member_schemas: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """For one ambiguity cluster, compute what the schemas reveal.

    Returns:
      - common_fields_across_all: bare names present in every member
      - common_units_across_all: units present in every member
      - per-pair Jaccard similarity (which pairs are closer in schema)
      - per-member unique fields (what makes each member distinct)
      - distinct unit signatures (which members use different physical
        quantity spaces)
      - interpretation: an engine-side reading of what the variation
        means, based on shared-fraction thresholds
    """
    names = sorted(member_schemas.keys())
    if not names:
        return {"empty": True}

    all_bare = {n: set(s.get("bare_names", [])) for n, s in member_schemas.items()}
    all_units = {n: set(s.get("units", [])) for n, s in member_schemas.items()}

    sets_bare = list(all_bare.values())
    sets_units = list(all_units.values())

    common_bare = set.intersection(*sets_bare) if sets_bare else set()
    common_units = set.intersection(*sets_units) if sets_units else set()
    union_bare = set.union(*sets_bare) if sets_bare else set()

    pair_similarities: List[Dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name, b_name = names[i], names[j]
            a, b = all_bare[a_name], all_bare[b_name]
            sim = jaccard(a, b)
            pair_similarities.append({
                "pair": [a_name, b_name],
                "jaccard": round(sim, 3),
                "shared_bare_names": sorted(a & b),
            })
    pair_similarities.sort(key=lambda p: -p["jaccard"])

    avg_jaccard = (sum(p["jaccard"] for p in pair_similarities) /
                   len(pair_similarities)) if pair_similarities else 0.0

    unique_per_member: Dict[str, List[str]] = {}
    for n in names:
        others: Set[str] = set()
        for m in names:
            if m != n:
                others |= all_bare[m]
        unique_per_member[n] = sorted(all_bare[n] - others)

    distinct_unit_signatures: Dict[str, List[str]] = {
        n: sorted(all_units[n] - common_units) for n in names
    }

    # Engine-side interpretation: pure thresholding, no claim of truth
    if avg_jaccard >= 0.4:
        interp = "near_alias_or_honest"  # high overlap; the axes are sufficient
    elif avg_jaccard <= 0.15:
        interp = "implicit_dimension_present"  # low overlap; a dimension exists the axes don't name
    else:
        interp = "mixed"  # partial overlap; some shared, some implicit

    return {
        "member_count": len(names),
        "common_bare_names_across_all": sorted(common_bare),
        "common_units_across_all": sorted(common_units),
        "union_field_count": len(union_bare),
        "avg_pair_jaccard": round(avg_jaccard, 3),
        "pair_similarities": pair_similarities,
        "unique_per_member": unique_per_member,
        "distinct_unit_signatures": distinct_unit_signatures,
        "interpretation": interp,
    }


def build_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Walk the engine's manifest. Returns canonical_domain → schema dict."""
    try:
        from api.agent_manifest import _MANIFEST
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for tool_def in _MANIFEST:
        fn = (tool_def or {}).get("function") or {}
        name = fn.get("name") or ""
        if not name.startswith("verify_"):
            continue
        canonical = name[len("verify_"):]
        out[canonical] = extract_schema(
            name=canonical,
            description=fn.get("description", "") or "",
            parameters=fn.get("parameters", {}) or {},
        )
    return out
