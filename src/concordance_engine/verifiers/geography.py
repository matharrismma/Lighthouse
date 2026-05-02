"""Geography verifier (physical-substance / standalone).

Lat/lon validity, haversine distance, initial bearing, UTM zone.
Public-domain spherical Earth approximation; mean radius 6371 km
(IUGG-recommended).

Checks:
  * geography.lat_lon_validity   — lat in [-90,90], lon in [-180,180]
  * geography.haversine_distance — great-circle distance on R=6371 km
  * geography.initial_bearing    — forward azimuth (0–360°)
  * geography.utm_zone           — UTM zone number from longitude

GEO_LOC_VERIFY shape:
    {
      "lat": 35.0, "lon": -85.0,
      "claimed_coords_valid": true,

      "lat1": 35.0, "lon1": -85.0,
      "lat2": 33.74, "lon2": -84.39,
      "claimed_distance_km": 175.0,

      "claimed_bearing_deg": 145.0,

      "longitude_for_utm": -85.0,
      "claimed_utm_zone": 16,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_EARTH_RADIUS_KM = 6371.0


def _coord_valid(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def verify_lat_lon_validity(spec: Dict[str, Any]) -> VerifierResult:
    name = "geography.lat_lon_validity"
    lat = spec.get("lat")
    lon = spec.get("lon")
    claimed = spec.get("claimed_coords_valid")
    if lat is None or lon is None or claimed is None:
        return na(name)
    try:
        latf, lonf = float(lat), float(lon)
    except (TypeError, ValueError):
        return error(name, "lat and lon must be numeric")
    actual = _coord_valid(latf, lonf)
    data = {"lat": latf, "lon": lonf, "actual_valid": actual,
            "claimed_valid": bool(claimed),
            "rule": "lat ∈ [-90, 90], lon ∈ [-180, 180]"}
    if actual == bool(claimed):
        return confirm(name, f"({latf}, {lonf}) valid={actual} (matches claim)", data)
    return mismatch(name, f"({latf}, {lonf}) valid={actual}, claimed {bool(claimed)}", data)


def verify_haversine_distance(spec: Dict[str, Any]) -> VerifierResult:
    name = "geography.haversine_distance"
    lat1 = spec.get("lat1"); lon1 = spec.get("lon1")
    lat2 = spec.get("lat2"); lon2 = spec.get("lon2")
    claimed = spec.get("claimed_distance_km")
    if any(v is None for v in (lat1, lon1, lat2, lon2, claimed)):
        return na(name)
    try:
        a1, o1, a2, o2, c = float(lat1), float(lon1), float(lat2), float(lon2), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all coordinates and claimed_distance_km must be numeric")
    if not (_coord_valid(a1, o1) and _coord_valid(a2, o2)):
        return error(name, f"coordinates out of range")
    # Haversine.
    phi1 = math.radians(a1)
    phi2 = math.radians(a2)
    dphi = math.radians(a2 - a1)
    dlam = math.radians(o2 - o1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    actual = 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))
    rel_tol = float(spec.get("tolerance_relative", 0.01))  # 1% default
    diff = abs(actual - c)
    threshold = max(0.5, rel_tol * actual)  # absolute floor 0.5 km
    data = {"lat1": a1, "lon1": o1, "lat2": a2, "lon2": o2,
            "actual_distance_km": actual, "claimed_distance_km": c,
            "diff_km": diff, "earth_radius_km": _EARTH_RADIUS_KM,
            "formula": "haversine on spherical Earth"}
    if diff <= threshold:
        return confirm(name,
                       f"haversine({a1},{o1} → {a2},{o2}) = {actual:.2f} km (matches claim {c})",
                       data)
    return mismatch(name,
                    f"haversine = {actual:.2f} km, claimed {c} (diff {diff:.2f})",
                    data)


def verify_initial_bearing(spec: Dict[str, Any]) -> VerifierResult:
    """Forward azimuth from (lat1, lon1) to (lat2, lon2), 0=N, 90=E."""
    name = "geography.initial_bearing"
    lat1 = spec.get("lat1"); lon1 = spec.get("lon1")
    lat2 = spec.get("lat2"); lon2 = spec.get("lon2")
    claimed = spec.get("claimed_bearing_deg")
    if any(v is None for v in (lat1, lon1, lat2, lon2, claimed)):
        return na(name)
    try:
        a1, o1, a2, o2, c = float(lat1), float(lon1), float(lat2), float(lon2), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    phi1 = math.radians(a1)
    phi2 = math.radians(a2)
    dlam = math.radians(o2 - o1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    actual = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    diff = min(abs(actual - c), 360.0 - abs(actual - c))  # circular diff
    tol = float(spec.get("tolerance_deg", 1.0))
    data = {"lat1": a1, "lon1": o1, "lat2": a2, "lon2": o2,
            "actual_bearing_deg": actual, "claimed_bearing_deg": c,
            "diff_deg": diff, "tolerance_deg": tol,
            "formula": "θ = atan2(sin Δλ · cos φ₂, cos φ₁·sin φ₂ − sin φ₁·cos φ₂·cos Δλ)"}
    if diff <= tol:
        return confirm(name,
                       f"bearing = {actual:.2f}° (matches claim {c}, diff {diff:.2f})",
                       data)
    return mismatch(name,
                    f"bearing = {actual:.2f}°, claimed {c} (diff {diff:.2f})",
                    data)


def verify_utm_zone(spec: Dict[str, Any]) -> VerifierResult:
    """UTM zone = floor((lon + 180) / 6) + 1, in [1, 60]."""
    name = "geography.utm_zone"
    lon = spec.get("longitude_for_utm")
    claimed = spec.get("claimed_utm_zone")
    if lon is None or claimed is None:
        return na(name)
    try:
        lf = float(lon)
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "longitude must be numeric, claimed_utm_zone integer")
    if not (-180.0 <= lf <= 180.0):
        return error(name, f"longitude out of range, got {lf}")
    actual = int(((lf + 180.0) // 6) + 1)
    if actual > 60:
        actual = 60  # exactly +180° edge case
    data = {"longitude": lf, "actual_utm_zone": actual, "claimed_utm_zone": c,
            "formula": "zone = floor((lon + 180) / 6) + 1"}
    if actual == c:
        return confirm(name, f"longitude {lf}° → UTM zone {actual} (matches claim)", data)
    return mismatch(name, f"longitude {lf}° → UTM zone {actual}, claimed {c}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    gv = packet.get("GEO_LOC_VERIFY") or {}
    if all(k in gv for k in ("lat", "lon", "claimed_coords_valid")):
        results.append(verify_lat_lon_validity(gv))
    if all(k in gv for k in ("lat1", "lon1", "lat2", "lon2", "claimed_distance_km")):
        results.append(verify_haversine_distance(gv))
    if all(k in gv for k in ("lat1", "lon1", "lat2", "lon2", "claimed_bearing_deg")):
        results.append(verify_initial_bearing(gv))
    if all(k in gv for k in ("longitude_for_utm", "claimed_utm_zone")):
        results.append(verify_utm_zone(gv))
    if not results:
        results.append(na("geography", "no GEO_LOC_VERIFY artifacts present"))
    return results
