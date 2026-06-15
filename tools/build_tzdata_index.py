#!/usr/bin/env python3
"""Build the IANA Time Zone Database Layer-0 index (offline, reproducible).

Source: the IANA Time Zone Database (tzdb / "Olson" database) -- the
authoritative record of every named time zone's UTC offset and daylight-saving
rules through history. https://www.iana.org/time-zones .
License: PUBLIC DOMAIN (the maintainers explicitly place tzdb in the public
domain).

We obtain the compiled release via the public-domain `tzdata` PyPI distribution
(which packages the official IANA release as compiled TZif files), so no `zic`
compiler is needed and the build is cross-platform. The exact IANA release is
recorded in meta.json for reproducibility + attribution.

This is EXTERNAL, ATTRIBUTED data -- a Layer-0 source, never engine-authored.
The engine stores it offline and reads an offset from it; it does not invent it.

Output: lw/00_source/tzdata/tzdata.zip  (a single ~350KB artifact)
  <Zone/Name>   -> compiled TZif bytes for each IANA zone (e.g. "Asia/Tokyo")
  zones         -> newline list of canonical zone names (if available)
  meta.json     -> {source, license, iana_version, package_version, url, ...}

Usage:
  python tools/build_tzdata_index.py            # pip-downloads tzdata if needed
  python tools/build_tzdata_index.py --wheel _tmp_tzdata/tzdata-XXXX.whl
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _find_or_download_wheel(wheel: str | None) -> Path:
    if wheel:
        p = Path(wheel)
        if not p.is_file():
            raise SystemExit("wheel not found: %s" % wheel)
        return p
    tmp = Path(tempfile.mkdtemp(prefix="tzdl_"))
    subprocess.check_call([sys.executable, "-m", "pip", "download", "tzdata",
                           "--no-deps", "--dest", str(tmp), "-q"])
    whls = sorted(tmp.glob("tzdata-*.whl"))
    if not whls:
        raise SystemExit("pip did not produce a tzdata wheel")
    return whls[0]


def build(wheel: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    zin = zipfile.ZipFile(wheel)
    names = zin.namelist()

    iana_version = "unknown"
    for n in names:
        if n.endswith("__init__.py"):
            for ln in zin.read(n).decode("utf-8", "replace").splitlines():
                if "IANA_VERSION" in ln and "=" in ln:
                    iana_version = ln.split("=", 1)[1].strip().strip('"\'')
    pkg_version = wheel.name.split("-")[1] if "-" in wheel.name else "unknown"

    zone_entries = []   # (arcname, bytes)
    zones_list = None
    for n in names:
        if "/zoneinfo/" in n and not n.endswith("/"):
            arc = n.split("/zoneinfo/", 1)[1]
            zone_entries.append((arc, zin.read(n)))
        elif n.endswith("/zones"):
            zones_list = zin.read(n)

    if out.exists():
        out.unlink()
    n_tzif = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for arc, data in zone_entries:
            zout.writestr(arc, data)
            if data[:4] == b"TZif":
                n_tzif += 1
        if zones_list is not None:
            zout.writestr("zones", zones_list)
        meta = {
            "source": "IANA Time Zone Database (tzdb)",
            "license": "Public Domain",
            "iana_version": iana_version,
            "package": "tzdata (PyPI)",
            "package_version": pkg_version,
            "url": "https://www.iana.org/time-zones",
            "attribution": "IANA Time Zone Database, public domain.",
            "zone_count": str(n_tzif),
        }
        zout.writestr("meta.json", json.dumps(meta, indent=2))
    zin.close()
    return {"iana_version": iana_version, "zones": n_tzif,
            "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", default=None,
                    help="path to a tzdata-*.whl (else pip-download)")
    ap.add_argument("--out", default="lw/00_source/tzdata/tzdata.zip")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = (root / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    wheel = _find_or_download_wheel(args.wheel)
    r = build(wheel, out)
    print("tzdata.zip built: %s" % out)
    print("  IANA %s  zones=%d  (%.0f KB)" % (
        r["iana_version"], r["zones"], r["size"] / 1024))


if __name__ == "__main__":
    main()
