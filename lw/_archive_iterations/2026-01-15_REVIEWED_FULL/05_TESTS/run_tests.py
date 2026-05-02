#!/usr/bin/env python3
"""Minimal self-test runner (no external deps).

Run:
  python3 05_TESTS/run_tests.py
"""

import base64
import os
import sys

# Add 04_CODE to path
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "04_CODE"))

from lighthouse_all import build_lsp_export, generate_keypair, sign_packet, verify_packet, example_packet


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_lsp_deterministic() -> None:
    text = ("A B C D E F G H I J " * 1000).strip()
    a = build_lsp_export(text, words_per_page=250, version="1.0", source_label="LXX")
    b = build_lsp_export(text, words_per_page=250, version="1.0", source_label="LXX")
    assert_true(a["meta"]["manifest_sha256"] == b["meta"]["manifest_sha256"], "LSP manifest hash should match")
    assert_true(a["pages"][0]["sha256"] == b["pages"][0]["sha256"], "First page hash should match")


def test_packet_sign_verify() -> None:
    import nacl.signing

    kp = generate_keypair()
    pkt = example_packet()

    sk = nacl.signing.SigningKey(base64.b64decode(kp["private_key_b64"]))
    vk = nacl.signing.VerifyKey(base64.b64decode(kp["public_key_b64"]))

    signed = sign_packet(pkt, sk)
    ok, msg = verify_packet(signed, vk)
    assert_true(ok, f"Signature should verify: {msg}")

    # tamper
    signed["derived_bands"]["income_band"] = "B9"
    ok, msg = verify_packet(signed, vk)
    assert_true(not ok, "Tampered packet must fail verification")


def main() -> int:
    tests = [test_lsp_deterministic, test_packet_sign_verify]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
