"""Tests for the networking verifier."""
from __future__ import annotations

from concordance_engine.verifiers import networking as net


# ── IP format ──────────────────────────────────────────────────────────

def test_ipv4_valid():
    r = net.verify_ip_format({"address": "192.168.1.1", "claimed_format_valid": True})
    assert r.status == "CONFIRMED"


def test_ipv6_valid():
    r = net.verify_ip_format({"address": "2001:0db8::1", "claimed_format_valid": True})
    assert r.status == "CONFIRMED"


def test_ipv4_too_many_octets():
    r = net.verify_ip_format({"address": "192.168.1.1.5", "claimed_format_valid": False})
    assert r.status == "CONFIRMED"


def test_ipv4_wrong_claim():
    r = net.verify_ip_format({"address": "garbage", "claimed_format_valid": True})
    assert r.status == "MISMATCH"


# ── CIDR membership ────────────────────────────────────────────────────

def test_cidr_membership_yes():
    r = net.verify_cidr_membership({
        "cidr": "192.168.1.0/24",
        "ip_to_check": "192.168.1.42",
        "claimed_in_subnet": True,
    })
    assert r.status == "CONFIRMED"


def test_cidr_membership_no():
    r = net.verify_cidr_membership({
        "cidr": "192.168.1.0/24",
        "ip_to_check": "10.0.0.1",
        "claimed_in_subnet": False,
    })
    assert r.status == "CONFIRMED"


def test_cidr_membership_wrong_claim():
    r = net.verify_cidr_membership({
        "cidr": "192.168.1.0/24",
        "ip_to_check": "10.0.0.1",
        "claimed_in_subnet": True,
    })
    assert r.status == "MISMATCH"


def test_cidr_membership_invalid_cidr_error():
    r = net.verify_cidr_membership({
        "cidr": "not-a-cidr",
        "ip_to_check": "192.168.1.1",
        "claimed_in_subnet": False,
    })
    assert r.status == "ERROR"


def test_cidr_membership_v4_v6_mismatch():
    # IPv6 address vs IPv4 CIDR → family mismatch
    r = net.verify_cidr_membership({
        "cidr": "192.168.1.0/24",
        "ip_to_check": "2001:db8::1",
        "claimed_in_subnet": False,
    })
    assert r.status == "MISMATCH"


# ── subnet host count ──────────────────────────────────────────────────

def test_subnet_24_has_254_hosts():
    r = net.verify_subnet_host_count({
        "subnet_prefix": 24, "claimed_usable_hosts": 254,
    })
    assert r.status == "CONFIRMED"


def test_subnet_30_has_2_hosts():
    # /30 = 2^2 - 2 = 2
    r = net.verify_subnet_host_count({
        "subnet_prefix": 30, "claimed_usable_hosts": 2,
    })
    assert r.status == "CONFIRMED"


def test_subnet_31_rfc3021_2_hosts():
    # /31 is point-to-point, RFC 3021 says 2 hosts (no network/broadcast)
    r = net.verify_subnet_host_count({
        "subnet_prefix": 31, "claimed_usable_hosts": 2,
    })
    assert r.status == "CONFIRMED"


def test_subnet_32_host_route_1_host():
    r = net.verify_subnet_host_count({
        "subnet_prefix": 32, "claimed_usable_hosts": 1,
    })
    assert r.status == "CONFIRMED"


def test_subnet_wrong_claim():
    r = net.verify_subnet_host_count({
        "subnet_prefix": 24, "claimed_usable_hosts": 256,
    })
    assert r.status == "MISMATCH"


def test_subnet_out_of_range_error():
    r = net.verify_subnet_host_count({
        "subnet_prefix": 99, "claimed_usable_hosts": 0,
    })
    assert r.status == "ERROR"


# ── MAC format ─────────────────────────────────────────────────────────

def test_mac_colon_format():
    r = net.verify_mac_format({"mac": "00:1A:2B:3C:4D:5E", "claimed_mac_valid": True})
    assert r.status == "CONFIRMED"


def test_mac_hyphen_format():
    r = net.verify_mac_format({"mac": "00-1A-2B-3C-4D-5E", "claimed_mac_valid": True})
    assert r.status == "CONFIRMED"


def test_mac_cisco_format():
    r = net.verify_mac_format({"mac": "001A.2B3C.4D5E", "claimed_mac_valid": True})
    assert r.status == "CONFIRMED"


def test_mac_bare_hex():
    r = net.verify_mac_format({"mac": "001A2B3C4D5E", "claimed_mac_valid": True})
    assert r.status == "CONFIRMED"


def test_mac_wrong_format():
    r = net.verify_mac_format({"mac": "not.a.mac", "claimed_mac_valid": False})
    assert r.status == "CONFIRMED"


def test_mac_wrong_claim():
    r = net.verify_mac_format({"mac": "00:1A:2B:3C:4D", "claimed_mac_valid": True})
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_run_no_artifacts_returns_na():
    r = net.run({"domain": "networking"})
    assert len(r) == 1 and r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all():
    packet = {
        "domain": "networking",
        "NET_VERIFY": {
            "address": "192.168.1.1", "claimed_format_valid": True,
            "cidr": "192.168.1.0/24", "ip_to_check": "192.168.1.42", "claimed_in_subnet": True,
            "subnet_prefix": 24, "claimed_usable_hosts": 254,
            "mac": "00:1A:2B:3C:4D:5E", "claimed_mac_valid": True,
        },
    }
    results = net.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)
