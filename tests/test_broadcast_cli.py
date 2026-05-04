"""Tests for the `concordance broadcast` CLI subcommand and the
LoRa-mesh wire transport plumbing it exposes.

The actual radio is not exercised here (it requires hardware). What
is verified:
- encode reads stdin/file → emits hex
- decode reads hex/file → emits structured JSON
- size reports byte budget
- max-size enforcement fails loudly when budget exceeded
- roundtrip: encode → decode → equivalent payload
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


CLI = [sys.executable, "-m", "concordance_engine.cli"]


def run(args, stdin: str = "", check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + args,
        input=stdin,
        capture_output=True,
        text=True,
        check=check,
    )


SAMPLE_JSON = json.dumps({
    "text": "Mt 5:37 — let your yes be yes.",
    "categorization": {
        "detected_anchors": ["Mt 5:37"],
        "detected_scope": "personal",
        "detected_action_shapes": ["abide"],
    },
    "source": "manual",
    "author_id": "matt",
    "written_at": 1730000000,
})


def test_broadcast_size_reports_budget():
    r = run(["broadcast", "size"], stdin=SAMPLE_JSON)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["wire_bytes"] > 0
    assert out["fits_lora_sf7"] is True
    assert out["anchors_in_dict"] == 1
    assert out["anchors_total"] == 1


def test_broadcast_encode_emits_hex():
    r = run(["broadcast", "encode"], stdin=SAMPLE_JSON)
    assert r.returncode == 0, r.stderr
    hex_str = r.stdout.strip()
    # Must be valid hex starting with the wire envelope (0x01 0x01).
    assert hex_str.startswith("0101")
    # And decode back to bytes that begin the same.
    raw = bytes.fromhex(hex_str)
    assert raw[0] == 0x01  # WIRE_VERSION
    assert raw[1] == 0x01  # WIRE_TYPE_SEED


def test_broadcast_encode_decode_roundtrip():
    r1 = run(["broadcast", "encode"], stdin=SAMPLE_JSON)
    assert r1.returncode == 0
    hex_str = r1.stdout.strip()

    r2 = run(["broadcast", "decode"], stdin=hex_str)
    assert r2.returncode == 0, r2.stderr
    decoded = json.loads(r2.stdout)
    assert decoded["text"] == "Mt 5:37 — let your yes be yes."
    assert decoded["identity_acknowledged"] is True
    assert decoded["source_meta"]["wire_anchors"] == ["Mt 5:37"]
    assert decoded["source_meta"]["wire_scope"] == "personal"
    assert decoded["source_meta"]["wire_action_shape"] == "abide"


def test_broadcast_encode_max_size_enforced():
    big_payload = json.dumps({
        "text": "x" * 5000,  # way too big for 230B SF7
        "source": "manual",
    })
    r = run(["broadcast", "encode"], stdin=big_payload)
    assert r.returncode == 1
    assert "exceeds" in r.stderr


def test_broadcast_encode_to_file(tmp_path):
    out = tmp_path / "wire.bin"
    r = run(["broadcast", "encode", "--out", str(out)], stdin=SAMPLE_JSON)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    raw = out.read_bytes()
    assert raw[0] == 0x01 and raw[1] == 0x01

    # Decode the file back.
    r2 = run(["broadcast", "decode", "--file", str(out)])
    assert r2.returncode == 0, r2.stderr
    decoded = json.loads(r2.stdout)
    assert "Mt 5:37" in decoded["text"]


def test_broadcast_decode_invalid_hex():
    r = run(["broadcast", "decode"], stdin="not hex at all")
    assert r.returncode == 4
    assert "hex" in r.stderr.lower()
