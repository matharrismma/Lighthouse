"""Networking verifier (information/encoding grid axis sibling to
genetics, cryptography, computer_science).

Deterministic checks against canonical IP addressing rules: IPv4/IPv6
format validity, CIDR subnet arithmetic, host counts, and MAC address
format. All checks use Python stdlib `ipaddress`; no external
dependency.

Public-domain references: RFC 791 (IPv4), RFC 4291 (IPv6 addressing
architecture), IEEE 802.

Checks performed:

  * networking.ip_format_validity
      Address parses as valid IPv4 (dotted-quad) or IPv6 (colon-hex).
  * networking.cidr_membership
      Given a CIDR network and an address, the address is/isn't a
      member of the network.
  * networking.subnet_host_count
      For /N IPv4: usable host count = 2^(32-N) - 2 (network +
      broadcast reserved). Special cases: /31 = 2 (RFC 3021 point-to-
      point), /32 = 1 (host route).
  * networking.mac_format_validity
      MAC matches AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, or AABB.CCDD.EEFF
      (Cisco) format. Hex chars, 12 nibbles total.

NET_VERIFY packet shape (any subset of fields):
    {
      "address": "192.168.1.1",
      "claimed_format_valid": true,

      "cidr": "192.168.1.0/24",
      "ip_to_check": "192.168.1.42",
      "claimed_in_subnet": true,

      "subnet_prefix": 24,
      "claimed_usable_hosts": 254,

      "mac": "00:1A:2B:3C:4D:5E",
      "claimed_mac_valid": true,
    }
"""
from __future__ import annotations
import ipaddress
import re
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# Three common MAC formats: colon, hyphen, and Cisco dot-quad nibble.
_MAC_PATTERNS = [
    re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"),     # 6-byte colon/hyphen
    re.compile(r"^([0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}$"),       # Cisco AABB.CCDD.EEFF
    re.compile(r"^[0-9A-Fa-f]{12}$"),                            # bare 12 hex chars
]


def verify_ip_format(spec: Dict[str, Any]) -> VerifierResult:
    name = "networking.ip_format_validity"
    addr = spec.get("address")
    claimed = spec.get("claimed_format_valid")
    if addr is None or claimed is None:
        return na(name)
    try:
        parsed = ipaddress.ip_address(str(addr))
        actual = True
        family = "IPv4" if parsed.version == 4 else "IPv6"
    except (ValueError, TypeError):
        actual = False
        family = None
    data = {"address": addr, "actual_valid": actual, "claimed_valid": bool(claimed),
            "family": family}
    if actual == bool(claimed):
        return confirm(name,
                       f"{addr!r} valid={actual}{f' ({family})' if family else ''} (matches claim)",
                       data)
    return mismatch(name,
                    f"{addr!r} valid={actual}, claimed {bool(claimed)}",
                    data)


def verify_cidr_membership(spec: Dict[str, Any]) -> VerifierResult:
    name = "networking.cidr_membership"
    cidr = spec.get("cidr")
    ip = spec.get("ip_to_check")
    claimed = spec.get("claimed_in_subnet")
    if cidr is None or ip is None or claimed is None:
        return na(name)
    try:
        net = ipaddress.ip_network(str(cidr), strict=False)
    except (ValueError, TypeError) as e:
        return error(name, f"invalid CIDR {cidr!r}: {e}")
    try:
        addr = ipaddress.ip_address(str(ip))
    except (ValueError, TypeError) as e:
        return error(name, f"invalid IP {ip!r}: {e}")
    if net.version != addr.version:
        return mismatch(name,
                        f"address family mismatch: CIDR is IPv{net.version}, address is IPv{addr.version}",
                        {"cidr": str(net), "address": str(addr)})
    actual = addr in net
    data = {"cidr": str(net), "address": str(addr),
            "actual_in_subnet": actual, "claimed_in_subnet": bool(claimed),
            "network_address": str(net.network_address),
            "broadcast_address": str(net.broadcast_address) if net.version == 4 else None}
    if actual == bool(claimed):
        return confirm(name,
                       f"{addr} in {net} = {actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"{addr} in {net} = {actual}, claimed {bool(claimed)}",
                    data)


def verify_subnet_host_count(spec: Dict[str, Any]) -> VerifierResult:
    """Usable host count for an IPv4 /N subnet (network + broadcast reserved)."""
    name = "networking.subnet_host_count"
    prefix = spec.get("subnet_prefix")
    claimed = spec.get("claimed_usable_hosts")
    if prefix is None or claimed is None:
        return na(name)
    try:
        n = int(prefix)
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "subnet_prefix and claimed_usable_hosts must be integers")
    if not (0 <= n <= 32):
        return error(name, f"subnet_prefix must be 0-32 for IPv4, got {n}")
    # /32 = 1 host (host route); /31 = 2 (RFC 3021); else 2^(32-n) - 2
    if n == 32:
        actual = 1
    elif n == 31:
        actual = 2
    else:
        actual = (1 << (32 - n)) - 2
    data = {"subnet_prefix": n, "actual_usable_hosts": actual,
            "claimed_usable_hosts": c,
            "rule": "/32→1; /31→2 (RFC 3021); else 2^(32-N) - 2"}
    if actual == c:
        return confirm(name,
                       f"/{n} has {actual} usable hosts (matches claim)",
                       data)
    return mismatch(name,
                    f"/{n} has {actual} usable hosts, claimed {c}",
                    data)


def verify_mac_format(spec: Dict[str, Any]) -> VerifierResult:
    name = "networking.mac_format_validity"
    mac = spec.get("mac")
    claimed = spec.get("claimed_mac_valid")
    if mac is None or claimed is None:
        return na(name)
    s = str(mac).strip()
    actual = any(p.match(s) for p in _MAC_PATTERNS)
    data = {"mac": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "accepted_formats": ["AA:BB:CC:DD:EE:FF", "AA-BB-CC-DD-EE-FF",
                                 "AABB.CCDD.EEFF", "AABBCCDDEEFF"]}
    if actual == bool(claimed):
        return confirm(name,
                       f"MAC {s!r} valid={actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"MAC {s!r} valid={actual}, claimed {bool(claimed)}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    nv = packet.get("NET_VERIFY") or {}

    if "address" in nv and "claimed_format_valid" in nv:
        results.append(verify_ip_format(nv))
    if all(k in nv for k in ("cidr", "ip_to_check", "claimed_in_subnet")):
        results.append(verify_cidr_membership(nv))
    if "subnet_prefix" in nv and "claimed_usable_hosts" in nv:
        results.append(verify_subnet_host_count(nv))
    if "mac" in nv and "claimed_mac_valid" in nv:
        results.append(verify_mac_format(nv))

    if not results:
        results.append(na("networking", "no NET_VERIFY artifacts present"))
    return results
