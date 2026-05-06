"""Cybersecurity verifier.

Deterministic checks on security claims: password entropy, TLS version
classification, CVSS base score, subnet sizing, and port classification.
All formulas and thresholds are from public standards (NIST, IETF, FIRST).

Checks:
  * cybersecurity.password_entropy  — H = L * log2(N) bits
  * cybersecurity.tls_version       — classify TLS 1.0/1.1/1.2/1.3
  * cybersecurity.cvss_severity     — CVSS v3 base score → severity label
  * cybersecurity.subnet_hosts      — CIDR prefix → host count (2^(32-prefix) - 2)
  * cybersecurity.port_class        — well-known / registered / dynamic

CYBER_VERIFY packet shape (any subset):
    {
      "password_length": 16, "charset_size": 94,
      "claimed_entropy_bits": 104.9,

      "tls_version": "1.2", "claimed_tls_status": "current",

      "cvss_base_score": 9.1, "claimed_cvss_severity": "critical",

      "cidr_prefix": 24, "claimed_host_count": 254,

      "port_number": 443, "claimed_port_class": "well_known",
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# ── Password entropy ──────────────────────────────────────────────────────────

_CHARSET_SIZES = {
    "lowercase": 26,
    "uppercase": 26,
    "digits": 10,
    "special": 32,
    "printable_ascii": 94,
    "alphanumeric": 62,
    "hex": 16,
    "base64": 64,
}


def verify_password_entropy(spec: Dict[str, Any]) -> VerifierResult:
    """Shannon entropy H = L * log2(N) where L=length, N=charset size."""
    name = "cybersecurity.password_entropy"
    length = spec.get("password_length")
    charset = spec.get("charset_size")
    claimed = spec.get("claimed_entropy_bits")
    if length is None or claimed is None:
        return na(name)
    if charset is None:
        return na(name, "charset_size required (or use a key from CHARSET_SIZES)")
    try:
        L = int(length)
        N = int(_CHARSET_SIZES.get(str(charset), charset))
        c = float(claimed)
    except (TypeError, ValueError, KeyError):
        return error(name, "password_length, charset_size, claimed_entropy_bits must be numeric")
    if N < 2:
        return error(name, f"charset_size must be >= 2, got {N}")
    actual = L * math.log2(N)
    tol = float(spec.get("tolerance_bits", 0.5))
    diff = abs(actual - c)
    data = {"length": L, "charset_size": N,
            "actual_entropy_bits": round(actual, 2), "claimed_entropy_bits": c,
            "formula": "H = L * log2(N)"}
    if diff <= tol:
        return confirm(name, f"H = {actual:.2f} bits (matches claim)", data)
    return mismatch(name, f"H = {actual:.2f} bits, claimed {c} (diff {diff:.2f})", data)


# ── TLS version classification ────────────────────────────────────────────────

_TLS_STATUS = {
    "1.0": "deprecated",   # RFC 8996 (2021)
    "1.1": "deprecated",   # RFC 8996 (2021)
    "1.2": "current",      # widely deployed, still acceptable
    "1.3": "recommended",  # RFC 8446 (2018)
    "ssl3": "insecure",
    "ssl2": "insecure",
}


def verify_tls_version(spec: Dict[str, Any]) -> VerifierResult:
    name = "cybersecurity.tls_version"
    version = spec.get("tls_version")
    claimed_status = spec.get("claimed_tls_status")
    if version is None or claimed_status is None:
        return na(name)
    v = str(version).lower().strip()
    actual_status = _TLS_STATUS.get(v)
    if actual_status is None:
        return mismatch(name, f"unknown TLS version {v!r}",
                        {"version": v, "known": list(_TLS_STATUS.keys())})
    data = {"tls_version": v, "status": actual_status, "standard": "RFC 8996 / RFC 8446"}
    if str(claimed_status).lower() == actual_status:
        return confirm(name, f"TLS {v} is '{actual_status}' (matches claim)", data)
    return mismatch(name, f"TLS {v} is '{actual_status}', claimed '{claimed_status}'", data)


# ── CVSS v3 severity label ────────────────────────────────────────────────────

_CVSS_SEVERITY = [
    (0.0, "none"),
    (0.1, "low"),
    (4.0, "medium"),
    (7.0, "high"),
    (9.0, "critical"),
]


def _cvss_label(score: float) -> str:
    label = "none"
    for threshold, sev in _CVSS_SEVERITY:
        if score >= threshold:
            label = sev
    return label


def verify_cvss_severity(spec: Dict[str, Any]) -> VerifierResult:
    """CVSS v3 base score to severity: none/low/medium/high/critical (FIRST)."""
    name = "cybersecurity.cvss_severity"
    score = spec.get("cvss_base_score")
    claimed = spec.get("claimed_cvss_severity")
    if score is None or claimed is None:
        return na(name)
    try:
        sf = float(score)
    except (TypeError, ValueError):
        return error(name, "cvss_base_score must be numeric")
    if not (0.0 <= sf <= 10.0):
        return error(name, f"CVSS base score must be 0.0–10.0, got {sf}")
    actual = _cvss_label(sf)
    data = {"cvss_base_score": sf, "severity": actual, "standard": "CVSS v3.1 (FIRST)"}
    if str(claimed).lower() == actual:
        return confirm(name, f"CVSS {sf} → '{actual}' (matches claim)", data)
    return mismatch(name, f"CVSS {sf} severity is '{actual}', claimed '{claimed}'", data)


# ── Subnet host count (IPv4 CIDR) ─────────────────────────────────────────────

def verify_subnet_hosts(spec: Dict[str, Any]) -> VerifierResult:
    """Usable hosts = 2^(32 - prefix) - 2 (subtract network + broadcast)."""
    name = "cybersecurity.subnet_hosts"
    prefix = spec.get("cidr_prefix")
    claimed = spec.get("claimed_host_count")
    if prefix is None or claimed is None:
        return na(name)
    try:
        p = int(prefix)
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "cidr_prefix and claimed_host_count must be integers")
    if not (0 <= p <= 32):
        return error(name, f"CIDR prefix must be 0–32, got {p}")
    total = 2 ** (32 - p)
    usable = max(0, total - 2)  # /31 and /32 are special cases
    if p >= 31:
        usable = total  # point-to-point and host routes
    data = {"cidr_prefix": p, "total_addresses": total,
            "usable_hosts": usable, "claimed_host_count": c,
            "formula": "2^(32-prefix) - 2 (usable)"}
    if usable == c:
        return confirm(name, f"/{p} → {usable} usable hosts (matches claim)", data)
    return mismatch(name, f"/{p} → {usable} hosts, claimed {c}", data)


# ── Port classification ───────────────────────────────────────────────────────

def verify_port_class(spec: Dict[str, Any]) -> VerifierResult:
    """IANA port classes: well_known (0-1023), registered (1024-49151), dynamic (49152-65535)."""
    name = "cybersecurity.port_class"
    port = spec.get("port_number")
    claimed = spec.get("claimed_port_class")
    if port is None or claimed is None:
        return na(name)
    try:
        p = int(port)
    except (TypeError, ValueError):
        return error(name, "port_number must be an integer")
    if not (0 <= p <= 65535):
        return error(name, f"port must be 0–65535, got {p}")
    if p < 1024:
        actual = "well_known"
    elif p < 49152:
        actual = "registered"
    else:
        actual = "dynamic"
    data = {"port": p, "class": actual, "standard": "IANA port number registry"}
    if str(claimed).lower() == actual:
        return confirm(name, f"port {p} is '{actual}' (matches claim)", data)
    return mismatch(name, f"port {p} is '{actual}', claimed '{claimed}'", data)


# ── run ───────────────────────────────────────────────────────────────────────

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CYBER_VERIFY") or {}
    if "password_length" in cv and "claimed_entropy_bits" in cv:
        results.append(verify_password_entropy(cv))
    if "tls_version" in cv and "claimed_tls_status" in cv:
        results.append(verify_tls_version(cv))
    if "cvss_base_score" in cv and "claimed_cvss_severity" in cv:
        results.append(verify_cvss_severity(cv))
    if "cidr_prefix" in cv and "claimed_host_count" in cv:
        results.append(verify_subnet_hosts(cv))
    if "port_number" in cv and "claimed_port_class" in cv:
        results.append(verify_port_class(cv))
    if not results:
        results.append(na("cybersecurity", "no CYBER_VERIFY artifacts present"))
    return results
