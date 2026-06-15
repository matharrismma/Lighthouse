#!/usr/bin/env python3
"""Build the UCUM (Unified Code for Units of Measure) Layer-0 index.

Source: ucum-essence.xml from the official UCUM repository
https://github.com/ucum-org/ucum (raw: .../main/ucum-essence.xml).
License: UCUM is (c) Regenstrief Institute, Inc. and the UCUM Organization;
the code system is provided ROYALTY-FREE for use, with attribution. We store
the essence table offline and read unit definitions from it; we do not author it.

UCUM is the machine-readable vocabulary of units of measure -- the substrate
under every dimensional/unit check. This index lets the engine resolve any unit
to its base-unit dimension + magnitude, and so convert deterministically.

Output: lw/00_source/ucum/ucum.json
  meta        -- source, license, version, url, attribution
  prefixes    -- {code: factor}            e.g. "k": 1000.0
  base_units  -- ["m","s","g","rad","K","C","cd"]  (the 7 UCUM base units)
  units       -- {code: {...}} each either a base unit ({base:true, dim}) or a
                 derived unit ({value, unit}) or a special/affine unit
                 ({special:true, func:{name,value,unit}}).

Usage:
  python tools/build_ucum_index.py --src _tmp_ucum/ucum-essence.xml
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def _tag(e):
    return e.tag.split("}")[-1]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    root = ET.parse(str(src)).getroot()
    version = root.attrib.get("version", "unknown")
    rev_date = root.attrib.get("revision-date", "")

    prefixes = {}
    base_units = []
    units = {}

    for e in root:
        k = _tag(e)
        if k == "prefix":
            code = e.attrib.get("Code")
            val = None
            for c in e:
                if _tag(c) == "value":
                    val = _f(c.attrib.get("value"))
            if code and val is not None:
                prefixes[code] = val
        elif k == "base-unit":
            code = e.attrib.get("Code")
            dim = e.attrib.get("dim")
            name = "".join(c.text or "" for c in e if _tag(c) == "name").strip()
            if code:
                base_units.append(code)
                # base units are metric -- they take SI prefixes (km, mg, mK)
                units[code] = {"name": name, "base": True, "dim": dim,
                               "property": "base", "metric": True}
        elif k == "unit":
            code = e.attrib.get("Code")
            if not code:
                continue
            name = "".join(c.text or "" for c in e if _tag(c) == "name").strip()
            prop = "".join(c.text or "" for c in e if _tag(c) == "property").strip()
            metric = e.attrib.get("isMetric") == "yes"
            special = e.attrib.get("isSpecial") == "yes"
            rec = {"name": name, "property": prop, "metric": metric}
            valnode = None
            for c in e:
                if _tag(c) == "value":
                    valnode = c
            if special and valnode is not None:
                fn = None
                for c in valnode:
                    if _tag(c) == "function":
                        fn = {"name": c.attrib.get("name"),
                              "value": _f(c.attrib.get("value")),
                              "unit": c.attrib.get("Unit")}
                rec["special"] = True
                rec["func"] = fn
            elif valnode is not None:
                rec["value"] = _f(valnode.attrib.get("value"))
                rec["unit"] = valnode.attrib.get("Unit")
            units[code] = rec

    meta = {
        "source": "UCUM (Unified Code for Units of Measure) ucum-essence.xml",
        "license": "Royalty-free, attribution required -- (c) Regenstrief "
                   "Institute & the UCUM Organization",
        "version": version,
        "revision_date": rev_date,
        "url": "https://ucum.org -- data https://github.com/ucum-org/ucum",
        "attribution": "Units of measure per UCUM, (c) Regenstrief Institute "
                       "and the UCUM Organization; used royalty-free.",
    }
    doc = {"meta": meta, "prefixes": prefixes, "base_units": base_units,
           "units": units}
    if out.exists():
        out.unlink()
    out.write_text(json.dumps(doc, ensure_ascii=True), encoding="utf-8")
    return {"prefixes": len(prefixes), "base_units": len(base_units),
            "units": len(units), "version": version,
            "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_ucum/ucum-essence.xml")
    ap.add_argument("--out", default="lw/00_source/ucum/ucum.json")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("ucum.json built: %s" % out)
    print("  UCUM %s  prefixes=%d base=%d units=%d  (%.0f KB)" % (
        r["version"], r["prefixes"], r["base_units"], r["units"],
        r["size"] / 1024))


if __name__ == "__main__":
    main()
