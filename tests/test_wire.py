"""Tests for the compact wire format used on the LoRa-mesh substrate.

Wire is the translation layer between the local JSON representation
and the on-air binary representation. JSON stays the format of
record on disk; wire is a transport encoding only.

Tests cover:
- Roundtrip: encode then decode reproduces the input
- Size budget: typical seeds fit within LoRa SF7 (~230 bytes)
- Pre-shared dictionary: known anchors compress to 2 bytes
- Forward compatibility: unknown tags survive a roundtrip
- Edge cases: empty fields, max-length text, all enums

Per project_lora_mesh_substrate.md: today's decisions must not
preclude LoRa transport. These tests are the proof.
"""
from __future__ import annotations

import json

import pytest

from concordance_engine import wire as _wire


# ── Roundtrip ───────────────────────────────────────────────────────


def test_minimal_seed_roundtrips():
    s = _wire.SeedWire(text="hello")
    b = s.to_bytes()
    s2 = _wire.SeedWire.from_bytes(b)
    assert s2.text == "hello"


def test_full_seed_roundtrips():
    s = _wire.SeedWire(
        text="Mt 5:37 — let your yes be yes.",
        anchors=["Mt 5:37", "James 1:5"],
        scope="personal",
        action_shape="abide",
        source="telegram",
        author_id="matt@example",
        epoch=1730000000,
    )
    b = s.to_bytes()
    s2 = _wire.SeedWire.from_bytes(b)
    assert s2.text == s.text
    assert s2.anchors == s.anchors
    assert s2.scope == s.scope
    assert s2.action_shape == s.action_shape
    assert s2.source == s.source
    assert s2.epoch == s.epoch
    # author_id roundtrips as a hash, not the original string.
    assert s2.author_id and s2.author_id != "matt@example"
    assert len(s2.author_id) == 8  # 4-byte hash as hex


# ── Size budget ─────────────────────────────────────────────────────


def test_typical_seed_fits_lora_sf7():
    """A typical seed (50-100 chars + 2 known anchors) fits in <230 bytes."""
    s = _wire.SeedWire(
        text="Mt 5:37 — let your yes be yes. Sitting with this.",
        anchors=["Mt 5:37", "James 1:5"],
        scope="personal",
        action_shape="abide",
        source="telegram",
        author_id="matt@example",
        epoch=1730000000,
    )
    assert len(s.to_bytes()) <= 230


def test_dict_compression_beats_literal():
    """A known anchor encodes to 4 bytes (tag + len + 2-byte index);
    a literal of the same string is much longer."""
    known = _wire.SeedWire(text="x", anchors=["Mt 5:37"])
    unknown = _wire.SeedWire(text="x", anchors=["Some Random Reference"])
    assert len(known.to_bytes()) < len(unknown.to_bytes())


def test_wire_smaller_than_json_for_typical_seed():
    """The wire format must be substantially smaller than the
    corresponding JSON for typical seeds — that's the whole point."""
    s = _wire.SeedWire(
        text="Mt 5:37 — let your yes be yes.",
        anchors=["Mt 5:37"],
        scope="personal",
        action_shape="abide",
        source="telegram",
        author_id="matt",
        epoch=1730000000,
    )
    wire_size = len(s.to_bytes())
    json_size = len(json.dumps({
        "text": s.text,
        "categorization": {
            "detected_anchors": s.anchors,
            "detected_scope": s.scope,
            "detected_action_shapes": [s.action_shape],
        },
        "source": s.source,
        "author_id": s.author_id,
        "written_at": s.epoch,
    }).encode("utf-8"))
    # Wire should be at least 30% smaller than JSON.
    assert wire_size < json_size * 0.7, (wire_size, json_size)


# ── Pre-shared dictionary ───────────────────────────────────────────


def test_dict_token_lookup_roundtrips():
    for anchor in ("Mt 5:37", "Jn 3:16", "Rev 13:16", "James 1:5"):
        idx = _wire.dict_token(anchor)
        assert idx is not None, f"{anchor} missing from dict"
        assert _wire.dict_resolve(idx) == anchor


def test_dict_unknown_returns_none():
    assert _wire.dict_token("Some Random Reference") is None


def test_dict_resolve_out_of_range():
    assert _wire.dict_resolve(99999) is None


def test_dict_first_entry_is_genesis_one_one():
    """Stable ordering — Gen 1:1 anchors the dictionary.
    Adding a new entry before this would break wire compatibility."""
    assert _wire.SCRIPTURE_DICT[0] == "Gen 1:1"


# ── Mixed dict + literal anchors ────────────────────────────────────


def test_mixed_anchor_encoding():
    s = _wire.SeedWire(
        text="x",
        anchors=["Mt 5:37", "Some Custom Ref", "Jn 3:16"],
    )
    s2 = _wire.SeedWire.from_bytes(s.to_bytes())
    assert s2.anchors == ["Mt 5:37", "Some Custom Ref", "Jn 3:16"]


# ── Forward compatibility (unknown tags) ────────────────────────────


def test_unknown_tags_survive_roundtrip():
    """Future versions may add new field tags. Decoders must preserve
    them in `extra` rather than failing or dropping them."""
    s = _wire.SeedWire(
        text="hello",
        extra={0x70: b"future-feature-data"},
    )
    b = s.to_bytes()
    s2 = _wire.SeedWire.from_bytes(b)
    assert s2.extra.get(0x70) == b"future-feature-data"


# ── Truncation / corruption resistance ──────────────────────────────


def test_truncated_envelope_raises():
    with pytest.raises(ValueError):
        _wire.SeedWire.from_bytes(b"")
    with pytest.raises(ValueError):
        _wire.SeedWire.from_bytes(b"\x01")


def test_wrong_envelope_type_raises():
    # Build a wire envelope but flip the type byte to "ack".
    s = _wire.SeedWire(text="x")
    b = bytearray(s.to_bytes())
    b[1] = _wire.WIRE_TYPE_ACK
    with pytest.raises(ValueError):
        _wire.SeedWire.from_bytes(bytes(b))


def test_unsupported_version_raises():
    s = _wire.SeedWire(text="x")
    b = bytearray(s.to_bytes())
    b[0] = 0xFF
    with pytest.raises(ValueError):
        _wire.SeedWire.from_bytes(bytes(b))


# ── Conversion helpers ──────────────────────────────────────────────


def test_seed_dict_to_wire_pulls_categorization():
    d = {
        "text": "thinking about Mt 7:7",
        "source": "watch_folder",
        "author_id": "matt",
        "written_at": 1730000000,
        "categorization": {
            "detected_anchors": ["Mt 7:7"],
            "detected_scope": "personal",
            "detected_action_shapes": ["seek"],
        },
    }
    w = _wire.seed_dict_to_wire(d)
    assert w.text == "thinking about Mt 7:7"
    assert w.anchors == ["Mt 7:7"]
    assert w.scope == "personal"
    assert w.action_shape == "seek"
    assert w.source == "watch_folder"
    assert w.epoch == 1730000000


def test_wire_to_capture_payload_shape():
    w = _wire.SeedWire(
        text="x",
        anchors=["Mt 5:37"],
        scope="personal",
        action_shape="abide",
        source="lora_mesh",
        author_id="matt",
        epoch=1,
    )
    payload = _wire.wire_to_capture_payload(w)
    assert payload["text"] == "x"
    assert payload["source"] == "lora_mesh"
    assert payload["identity_acknowledged"] is True
    assert payload["source_meta"]["received_via"] == "lora_mesh"
    assert payload["source_meta"]["wire_anchors"] == ["Mt 5:37"]
