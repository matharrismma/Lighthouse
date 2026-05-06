"""Tests for LoRa compact packet serialization.

Covers:
  - encode_polymathic / encode_witness: frame size ≤ 255 bytes
  - decode: round-trip field recovery
  - VERDICT_CODES / VERDICT_NAMES symmetry
  - text_frame_polymathic / text_frame_witness format
  - parse_text_frame: POLY and WIT round-trips
  - parse_text_frame: malformed inputs return None
  - _trim_utf8: stays within budget, no split-char truncation
  - _hash_prefix: 16-byte output, zero-padded for short hashes

No network calls. No oracle calls. Pure stdlib.
"""
from __future__ import annotations

import struct
import time

import pytest

from concordance_engine.lora_packet import (
    FRAME_HEADER_SIZE,
    FRAME_TYPE_POLYMATHIC,
    FRAME_TYPE_WITNESS,
    FRAME_VERSION,
    LORA_MAX_PAYLOAD,
    VERDICT_CODES,
    VERDICT_NAMES,
    decode,
    encode_polymathic,
    encode_witness,
    parse_text_frame,
    text_frame_polymathic,
    text_frame_witness,
    _hash_prefix,
    _trim_utf8,
)


# ── VERDICT symmetry ──────────────────────────────────────────────────────────

def test_verdict_codes_and_names_are_symmetric():
    for name, code in VERDICT_CODES.items():
        assert VERDICT_NAMES[code] == name


def test_verdict_codes_all_unique():
    codes = list(VERDICT_CODES.values())
    assert len(codes) == len(set(codes))


# ── encode_polymathic ─────────────────────────────────────────────────────────

def _poly_record(**kw):
    base = dict(
        content_hash="a" * 64,
        composite_verdict="CONCORDANT",
        domain_results=[{"verdict": "CONFIRMED"}, {"verdict": "MISMATCH"}],
        sealed_at=int(time.time()),
        situation="This is a test situation for the polymathic engine.",
        closest_precedent=None,
        quarantined_claims=[],
        subject_pubkey=None,
        axis_overlaps=[
            {"dimension": "authority_trust"},
            {"dimension": "time_sequence"},
        ],
    )
    base.update(kw)
    return base


def test_encode_polymathic_fits_in_lora_payload():
    frame = encode_polymathic(_poly_record())
    assert len(frame) <= LORA_MAX_PAYLOAD


def test_encode_polymathic_minimum_size_is_header():
    rec = _poly_record(situation="")
    frame = encode_polymathic(rec)
    assert len(frame) >= FRAME_HEADER_SIZE


def test_encode_polymathic_long_situation_is_truncated():
    long_sit = "X" * 1000
    frame = encode_polymathic(_poly_record(situation=long_sit))
    assert len(frame) <= LORA_MAX_PAYLOAD


def test_encode_polymathic_frame_type_byte():
    frame = encode_polymathic(_poly_record())
    assert frame[0] == FRAME_TYPE_POLYMATHIC


def test_encode_polymathic_version_byte():
    frame = encode_polymathic(_poly_record())
    assert frame[1] == FRAME_VERSION


# ── encode_witness ────────────────────────────────────────────────────────────

def _wit_record(**kw):
    base = dict(
        content_hash="b" * 64,
        overall="CONFIRMED",
        domain="labor",
        timestamp_epoch=int(time.time()),
        claim="Worker completed task on schedule",
        subject_pubkey=None,
    )
    base.update(kw)
    return base


def test_encode_witness_fits_in_lora_payload():
    frame = encode_witness(_wit_record())
    assert len(frame) <= LORA_MAX_PAYLOAD


def test_encode_witness_frame_type_byte():
    frame = encode_witness(_wit_record())
    assert frame[0] == FRAME_TYPE_WITNESS


def test_encode_witness_confirmed_count_one_when_confirmed():
    frame = encode_witness(_wit_record(overall="CONFIRMED"))
    decoded = decode(frame)
    assert decoded["confirmed_count"] == 1


def test_encode_witness_confirmed_count_zero_when_not_confirmed():
    frame = encode_witness(_wit_record(overall="MISMATCH"))
    decoded = decode(frame)
    assert decoded["confirmed_count"] == 0


# ── decode round-trip ─────────────────────────────────────────────────────────

def test_decode_polymathic_round_trip():
    rec = _poly_record(
        composite_verdict="CONCORDANT",
        domain_results=[{"verdict": "CONFIRMED"}, {"verdict": "CONFIRMED"}, {"verdict": "MISMATCH"}],
        situation="Round-trip situation",
    )
    frame = encode_polymathic(rec, seq=42)
    d = decode(frame)
    assert d["frame_type"] == "POLYMATHIC"
    assert d["verdict"] == "CONCORDANT"
    assert d["domain_count"] == 3
    assert d["confirmed_count"] == 2
    assert d["seq_lo"] == 42
    assert d["summary"] == "Round-trip situation"
    assert d["hash_prefix"] == ("a" * 32)  # first 16 bytes of 'aaa...' hash
    assert d["frame_size"] == len(frame)


def test_decode_witness_round_trip():
    rec = _wit_record(overall="CONFIRMED", domain="labor", claim="Completed task")
    frame = encode_witness(rec, seq=7)
    d = decode(frame)
    assert d["frame_type"] == "WITNESS"
    assert d["verdict"] == "CONFIRMED"
    assert d["domain_count"] == 1
    assert d["confirmed_count"] == 1
    assert d["seq_lo"] == 7
    assert "Completed task" in d["summary"]


def test_decode_raises_on_short_frame():
    with pytest.raises(ValueError, match="frame too short"):
        decode(b"\x01\x02\x03")


def test_decode_hash_prefix_field():
    rec = _poly_record(content_hash="deadbeef" + "0" * 56)
    frame = encode_polymathic(rec)
    d = decode(frame)
    # First 16 bytes of 'deadbeef000...' decoded as hex → 'deadbeef00000000'
    assert d["hash_prefix"].startswith("deadbeef")


def test_decode_flags_has_precedent():
    rec = _poly_record(closest_precedent={"hash": "prec1"})
    frame = encode_polymathic(rec)
    d = decode(frame)
    assert d["has_precedent"] is True


def test_decode_flags_no_precedent():
    rec = _poly_record(closest_precedent=None)
    frame = encode_polymathic(rec)
    d = decode(frame)
    assert d["has_precedent"] is False


def test_decode_flags_has_quarantine():
    rec = _poly_record(quarantined_claims=[{"claim": "orphan"}])
    frame = encode_polymathic(rec)
    d = decode(frame)
    assert d["has_quarantine"] is True


def test_decode_flags_subject_bound():
    rec = _poly_record(subject_pubkey="ed25519pubkeydata")
    frame = encode_polymathic(rec)
    d = decode(frame)
    assert d["subject_bound"] is True


def test_decode_unknown_verdict_byte():
    rec = _poly_record(composite_verdict="NOT_IN_DICT_XYZ")
    # encode will use 0xFE for unknown
    frame = encode_polymathic(rec)
    d = decode(frame)
    assert d["verdict"] == "UNKNOWN"


# ── text frame ────────────────────────────────────────────────────────────────

def test_text_frame_polymathic_format():
    rec = _poly_record(
        content_hash="2d3b835" + "0" * 57,
        composite_verdict="CONCORDANT",
        domain_results=[{"verdict": "CONFIRMED"}] * 3,
        axis_overlaps=[
            {"dimension": "authority_trust"},
            {"dimension": "time_sequence"},
        ],
    )
    t = text_frame_polymathic(rec)
    assert t.startswith("[POLY:")
    assert t.endswith("]")
    assert "CONCORDANT" in t
    assert "3/3" in t
    assert len(t) <= 80


def test_text_frame_witness_format():
    rec = _wit_record(
        content_hash="a1b2c3d" + "0" * 57,
        overall="CONFIRMED",
        domain="labor",
    )
    t = text_frame_witness(rec)
    assert t.startswith("[WIT:")
    assert t.endswith("]")
    assert "CONFIRMED" in t
    assert "labor" in t


def test_text_frame_polymathic_no_crash_missing_fields():
    t = text_frame_polymathic({})
    assert t.startswith("[POLY:")
    assert t.endswith("]")


def test_text_frame_witness_no_crash_missing_fields():
    t = text_frame_witness({})
    assert t.startswith("[WIT:")
    assert t.endswith("]")


# ── parse_text_frame ──────────────────────────────────────────────────────────

def test_parse_text_frame_poly_round_trip():
    rec = _poly_record(
        content_hash="2d3b835" + "0" * 57,
        composite_verdict="CONCORDANT",
        domain_results=[{"verdict": "CONFIRMED"}] * 3,
        axis_overlaps=[{"dimension": "authority_trust"}, {"dimension": "time_seq"}],
    )
    text = text_frame_polymathic(rec)
    parsed = parse_text_frame(text)
    assert parsed is not None
    assert parsed["frame_type"] == "POLYMATHIC"
    assert parsed["verdict"] == "CONCORDANT"
    assert parsed["confirmed_count"] == 3
    assert parsed["domain_count"] == 3


def test_parse_text_frame_wit_round_trip():
    rec = _wit_record(content_hash="a1b2c3d" + "0" * 57, overall="CONFIRMED", domain="labor")
    text = text_frame_witness(rec)
    parsed = parse_text_frame(text)
    assert parsed is not None
    assert parsed["frame_type"] == "WITNESS"
    assert parsed["verdict"] == "CONFIRMED"
    assert parsed["domain"] == "labor"


def test_parse_text_frame_returns_none_on_garbage():
    assert parse_text_frame("this is not a frame") is None
    assert parse_text_frame("") is None
    assert parse_text_frame("[NOTYPE]") is None
    assert parse_text_frame("[X:abc]") is None


def test_parse_text_frame_missing_brackets():
    assert parse_text_frame("POLY:abc|CONCORDANT|1/1") is None


def test_parse_text_frame_poly_with_dims():
    text = "[POLY:2d3b835|CONCORDANT|3/3|authority_trust+time_seq]"
    parsed = parse_text_frame(text)
    assert parsed is not None
    assert "authority_trust" in parsed["dims_hint"]
    assert "time_seq" in parsed["dims_hint"]


# ── _trim_utf8 ────────────────────────────────────────────────────────────────

def test_trim_utf8_short_text_unchanged():
    b = _trim_utf8("hello", 100)
    assert b == b"hello"


def test_trim_utf8_respects_max_bytes():
    text = "A" * 300
    b = _trim_utf8(text, 100)
    assert len(b) <= 100


def test_trim_utf8_does_not_split_multibyte_char():
    text = "日本語テスト" * 20  # 3 bytes each in UTF-8
    b = _trim_utf8(text, 10)
    assert len(b) <= 10
    # Must decode cleanly
    b.decode("utf-8")


def test_trim_utf8_empty_input():
    assert _trim_utf8("", 100) == b""


def test_trim_utf8_zero_budget():
    assert _trim_utf8("hello", 0) == b""


# ── _hash_prefix ──────────────────────────────────────────────────────────────

def test_hash_prefix_returns_16_bytes():
    h = "a" * 64
    assert len(_hash_prefix(h)) == 16


def test_hash_prefix_short_hash_zero_padded():
    result = _hash_prefix("aabb")
    assert len(result) == 16
    assert result[:2] == bytes.fromhex("aabb")
    assert result[2:] == b"\x00" * 14


def test_hash_prefix_empty_returns_zeros():
    assert _hash_prefix("") == b"\x00" * 16


def test_hash_prefix_invalid_hex_returns_zeros():
    assert _hash_prefix("ZZZZ") == b"\x00" * 16


# ── FRAME_HEADER_SIZE constant ────────────────────────────────────────────────

def test_frame_header_size_matches_struct():
    # struct ">BBHl16sBBBB" = 1+1+2+4+16+1+1+1+1 = 28
    size = struct.calcsize(">BBHl16sBBBB")
    assert size == FRAME_HEADER_SIZE == 28
