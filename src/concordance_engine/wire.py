"""wire — compact binary wire format for LoRa-mesh transport.

LoRa packets are 50-230 bytes. The engine's normal JSON envelope
exceeds that. This module defines a binary format compact enough
for radio: a typed envelope, TLV (tag-length-value) fields, and a
pre-shared dictionary of common Scripture anchors that compresses
"Mt 5:37" from 8 bytes (UTF-8) to 2 bytes (dict index).

Stdlib-only — no external dependencies. Deterministic encode/
decode. Symmetric (encode then decode reproduces the input).

## Envelope layout

```
[1 byte: VERSION ][1 byte: TYPE  ][N bytes: TLV fields ...]
```

- VERSION: 0x01 currently. Bumping is reserved for breaking changes.
- TYPE: one of WIRE_TYPE_* (seed, witness, precedent, ack).
- Fields are TLV-encoded; order is irrelevant; unknown tags are
  preserved on decode in `extra` for forward compatibility.

## Field encoding (TLV)

```
[1 byte: TAG ][1 byte: LEN ][LEN bytes: VALUE ...]
```

LEN > 255 is encoded as TAG | 0x80 (high bit set), then a 2-byte
big-endian length, then VALUE. This lets a single field carry up
to 65535 bytes if absolutely necessary (rare; most fields are
short).

## Pre-shared dictionary

`SCRIPTURE_DICT` maps common anchor strings to small integer
indices. Both ends of the wire MUST agree on the dictionary
version (carried in the version byte's upper nibble in v2+; for
v1, dict is frozen). Adding entries in v1 is forbidden;
extending the dict requires a versioned upgrade.

## Sizing

A typical seed (50-100 chars of text + 1-2 anchors via dict +
epoch + author hash) fits comfortably in 130-180 bytes, leaving
headroom for one Schnorr-compressed signature. Verified by
tests in test_wire.py.

## Connection to the doctrine

This format exists for the LoRa-mesh substrate (per the
project_lora_mesh_substrate.md memory). Today's engine uses JSON
end-to-end; the wire format is the translation layer between the
local (verbose, human-readable) representation and the on-air
(compact, binary) representation. JSON remains the format of
record on disk; the wire format is a transport encoding.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Versioning ──────────────────────────────────────────────────────

WIRE_VERSION = 0x01


# ── Envelope types ──────────────────────────────────────────────────

WIRE_TYPE_SEED       = 0x01  # journal seed (text + categorization)
WIRE_TYPE_WITNESS    = 0x02  # witness signature on a packet
WIRE_TYPE_PRECEDENT  = 0x03  # sealed precedent (audit-chain entry)
WIRE_TYPE_ACK        = 0x04  # acknowledgment of receipt by hash


# ── Field tags ──────────────────────────────────────────────────────
#
# Tag values are stable; do not reuse. New tags get new numbers.

TAG_TEXT           = 0x01  # UTF-8 text body
TAG_ANCHOR_TOKEN   = 0x02  # 2-byte big-endian dict index
TAG_ANCHOR_LITERAL = 0x03  # UTF-8 anchor string (used when not in dict)
TAG_SCOPE          = 0x04  # 1-byte enum (see SCOPE_* below)
TAG_ACTION_SHAPE   = 0x05  # 1-byte enum (see ACTION_* below)
TAG_SOURCE         = 0x06  # 1-byte enum (see SOURCE_* below)
TAG_AUTHOR_HASH    = 0x07  # 4-byte fingerprint (truncated SHA-256)
TAG_EPOCH          = 0x08  # 4-byte uint32 unix epoch (rolls in 2106)
TAG_PRECEDENT_ID   = 0x09  # short id of a referenced precedent
TAG_AXIS           = 0x0A  # 1-byte enum (see AXIS_* below)
TAG_SUMMARY        = 0x0B  # UTF-8 short summary
TAG_PACKET_HASH    = 0x0C  # 16-byte truncated SHA-256 of the source packet
TAG_SIGNATURE      = 0x0D  # signature bytes (variable: Ed25519 = 64, Schnorr ~64, BLS ~48)
TAG_WITNESS_ROLE   = 0x0E  # 1-byte enum (see ROLE_* below)
TAG_FRUIT_SCORE    = 0x0F  # 1-byte uint (0..255 mapped to 0.0..1.0)


# ── Enum tables ─────────────────────────────────────────────────────

# Scope enum — common scopes get small ids. "personal" = 0 since it's
# the default for most journal seeds.
_SCOPE_TABLE = (
    "personal",      # 0
    "household",     # 1
    "community",     # 2
    "canon",         # 3
    "regional",      # 4
    "global",        # 5
    "adapter",       # 6
)
SCOPE_BY_NAME = {n: i for i, n in enumerate(_SCOPE_TABLE)}

# Action shape enum — compact id for the common categorizer outputs.
_ACTION_TABLE = (
    "build",        # 0
    "wait",         # 1
    "discern",      # 2
    "witness",      # 3
    "warn",         # 4
    "release",      # 5
    "keep",         # 6
    "abide",        # 7
    "share",        # 8
    "seek",         # 9
)
ACTION_BY_NAME = {n: i for i, n in enumerate(_ACTION_TABLE)}

# Source enum — where the seed came from (matches tags from /capture).
_SOURCE_TABLE = (
    "unknown",         # 0
    "watch_folder",    # 1
    "email",           # 2
    "telegram",        # 3
    "apple_shortcut",  # 4
    "web_share",       # 5
    "cli",             # 6
    "mcp",             # 7
    "lora_mesh",       # 8
    "manual",          # 9
)
SOURCE_BY_NAME = {n: i for i, n in enumerate(_SOURCE_TABLE)}

# Domain axis enum — the verifier domain.
_AXIS_TABLE = (
    "governance",     # 0
    "chemistry",      # 1
    "physics",        # 2
    "mathematics",    # 3
    "statistics",     # 4
    "cs",             # 5
    "biology",        # 6
    "linguistics",    # 7
    "scripture",      # 8
    "doctrine",       # 9
)
AXIS_BY_NAME = {n: i for i, n in enumerate(_AXIS_TABLE)}

# Witness role enum — who signed.
_ROLE_TABLE = (
    "elder",          # 0
    "brother",        # 1
    "sister",         # 2
    "deacon",         # 3
    "operator",       # 4
    "agent",          # 5
)
ROLE_BY_NAME = {n: i for i, n in enumerate(_ROLE_TABLE)}


def _enum_lookup(name: Optional[str], table: Tuple[str, ...]) -> int:
    """Return the index of `name` in `table`, or 0 ('unknown') if absent."""
    if not name:
        return 0
    try:
        return table.index(name)
    except ValueError:
        return 0


def _enum_resolve(idx: int, table: Tuple[str, ...]) -> str:
    if 0 <= idx < len(table):
        return table[idx]
    return ""


# ── Pre-shared Scripture dictionary ─────────────────────────────────
#
# The most-cited anchors get small indices. Adding entries breaks
# wire compatibility — bump WIRE_VERSION if you must. The list is
# ordered: position == dict index. Up to 65535 entries (2 bytes).
#
# This list is intentionally short and Bible-citation-shaped. If a
# user references an anchor not in the dict, it falls back to a
# literal UTF-8 encoding (TAG_ANCHOR_LITERAL).

SCRIPTURE_DICT: Tuple[str, ...] = (
    # Old Testament — most-quoted
    "Gen 1:1",       # 0
    "Gen 2:7",
    "Gen 8:7",
    "Gen 8:11",
    "Ex 20:3",
    "Ex 20:13",
    "Lev 25:10",
    "Deut 6:4",
    "Deut 6:5",
    "Ps 1:1",
    "Ps 23:1",
    "Ps 117:1",
    "Ps 118:22",
    "Ps 119:105",
    "Prov 2:6",
    "Prov 3:5",
    "Prov 9:10",
    "Eccl 1:9",
    "Isa 40:31",
    "Isa 53:5",
    "Jer 17:9",
    "Hab 2:3",
    # Gospels — Sermon on the Mount + key teachings
    "Mt 5:14",       # 22
    "Mt 5:16",
    "Mt 5:37",
    "Mt 6:24",
    "Mt 6:33",
    "Mt 7:1",
    "Mt 7:7",
    "Mt 7:16",
    "Mt 10:8",
    "Mt 10:16",
    "Mt 13:31",
    "Mt 13:33",
    "Mt 14:13",
    "Mt 18:15",
    "Mt 22:37",
    "Mt 24:15",
    "Mt 25:14",
    "Mt 28:19",
    "Mark 4:8",
    "Mark 12:30",
    "Lk 9:23",
    "Lk 16:10",
    "Lk 22:42",
    "Jn 1:1",
    "Jn 3:16",
    "Jn 10:10",
    "Jn 12:24",
    "Jn 14:6",
    "Jn 15:5",
    # Acts + Epistles
    "Acts 2:42",
    "Acts 4:32",
    "Rom 8:28",
    "Rom 12:1",
    "Rom 12:2",
    "1 Cor 6:19",
    "1 Cor 9:25",
    "1 Cor 12:8",
    "1 Cor 13:13",
    "1 Cor 15:31",
    "2 Cor 5:17",
    "Gal 2:20",
    "Gal 5:22",
    "Eph 5:8",
    "Eph 6:11",
    "Phil 4:6",
    "Phil 4:13",
    "Col 2:3",
    "1 Thess 5:17",
    "2 Tim 3:16",
    "Heb 11:1",
    "Heb 12:1",
    "James 1:5",
    "James 1:22",
    "1 Pet 5:8",
    "2 Pet 3:9",
    "1 Jn 1:9",
    "1 Jn 4:8",
    "Rev 13:16",
    "Rev 22:17",
)

ANCHOR_BY_NAME: Dict[str, int] = {ref: i for i, ref in enumerate(SCRIPTURE_DICT)}


def dict_token(anchor: str) -> Optional[int]:
    """Return the 2-byte dict index for an anchor, or None if not in dict."""
    return ANCHOR_BY_NAME.get(anchor)


def dict_resolve(idx: int) -> Optional[str]:
    """Return the anchor for a dict index, or None if out of range."""
    if 0 <= idx < len(SCRIPTURE_DICT):
        return SCRIPTURE_DICT[idx]
    return None


# ── Encoding / decoding ─────────────────────────────────────────────


def _encode_field(tag: int, value: bytes) -> bytes:
    """Encode a single TLV field. Length must fit in 16 bits."""
    n = len(value)
    if n > 0xFFFF:
        raise ValueError(f"field {tag} too long ({n} bytes)")
    if n <= 255:
        return bytes([tag, n]) + value
    # Long form: high bit set on tag, 2-byte big-endian length.
    return bytes([tag | 0x80, (n >> 8) & 0xFF, n & 0xFF]) + value


def _decode_fields(buf: bytes, offset: int) -> List[Tuple[int, bytes]]:
    """Decode all TLV fields from `buf[offset:]`. Returns (tag, value) pairs."""
    out: List[Tuple[int, bytes]] = []
    i = offset
    n = len(buf)
    while i < n:
        tag = buf[i]
        i += 1
        if i >= n:
            raise ValueError(f"truncated field header at offset {i-1}")
        if tag & 0x80:
            # Long form length.
            real_tag = tag & 0x7F
            if i + 1 >= n:
                raise ValueError(f"truncated long-length at offset {i}")
            length = (buf[i] << 8) | buf[i+1]
            i += 2
        else:
            real_tag = tag
            length = buf[i]
            i += 1
        if i + length > n:
            raise ValueError(
                f"field {real_tag} declares {length} bytes, only {n-i} remain"
            )
        out.append((real_tag, bytes(buf[i:i+length])))
        i += length
    return out


def _author_hash(author_id: str) -> bytes:
    """Compute a stable 4-byte fingerprint for an author identifier."""
    return hashlib.sha256(author_id.encode("utf-8")).digest()[:4]


def _packet_hash(*parts: bytes) -> bytes:
    """Compute a 16-byte truncated SHA-256 over the concatenated parts."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()[:16]


# ── Seed envelope ───────────────────────────────────────────────────


@dataclass
class SeedWire:
    """A journal seed in compact wire form. Round-trips with `to_bytes`
    and `SeedWire.from_bytes`."""
    text: str
    anchors: List[str] = field(default_factory=list)
    scope: str = "personal"
    action_shape: str = ""
    source: str = "lora_mesh"
    author_id: str = ""
    epoch: int = 0
    extra: Dict[int, bytes] = field(default_factory=dict)  # forward-compat unknown tags

    def to_bytes(self) -> bytes:
        fields: List[bytes] = []

        # Required: text. Truncated to 65535 bytes by encoder.
        fields.append(_encode_field(TAG_TEXT, self.text.encode("utf-8")))

        # Anchors: prefer dict tokens; fall back to literals.
        for a in self.anchors:
            idx = dict_token(a)
            if idx is not None:
                fields.append(_encode_field(
                    TAG_ANCHOR_TOKEN,
                    struct.pack(">H", idx),
                ))
            else:
                fields.append(_encode_field(
                    TAG_ANCHOR_LITERAL,
                    a.encode("utf-8"),
                ))

        # Scope, action, source as 1-byte enums.
        fields.append(_encode_field(
            TAG_SCOPE,
            bytes([_enum_lookup(self.scope, _SCOPE_TABLE)]),
        ))
        if self.action_shape:
            fields.append(_encode_field(
                TAG_ACTION_SHAPE,
                bytes([_enum_lookup(self.action_shape, _ACTION_TABLE)]),
            ))
        fields.append(_encode_field(
            TAG_SOURCE,
            bytes([_enum_lookup(self.source, _SOURCE_TABLE)]),
        ))

        # Author hash + epoch — every seed should carry these.
        if self.author_id:
            fields.append(_encode_field(
                TAG_AUTHOR_HASH,
                _author_hash(self.author_id),
            ))
        if self.epoch:
            fields.append(_encode_field(
                TAG_EPOCH,
                struct.pack(">I", self.epoch & 0xFFFFFFFF),
            ))

        # Forward-compatible unknowns.
        for tag, value in self.extra.items():
            fields.append(_encode_field(tag, value))

        body = b"".join(fields)
        return bytes([WIRE_VERSION, WIRE_TYPE_SEED]) + body

    @classmethod
    def from_bytes(cls, buf: bytes) -> "SeedWire":
        if len(buf) < 2:
            raise ValueError("buffer too short for envelope header")
        version, type_byte = buf[0], buf[1]
        if version != WIRE_VERSION:
            raise ValueError(f"unsupported wire version {version}")
        if type_byte != WIRE_TYPE_SEED:
            raise ValueError(
                f"expected seed envelope (0x{WIRE_TYPE_SEED:02x}), got 0x{type_byte:02x}"
            )

        text = ""
        anchors: List[str] = []
        scope = "personal"
        action_shape = ""
        source = "lora_mesh"
        author_hash: Optional[bytes] = None
        epoch = 0
        extra: Dict[int, bytes] = {}

        for tag, value in _decode_fields(buf, 2):
            if tag == TAG_TEXT:
                text = value.decode("utf-8", errors="replace")
            elif tag == TAG_ANCHOR_TOKEN:
                if len(value) != 2:
                    continue
                idx = struct.unpack(">H", value)[0]
                resolved = dict_resolve(idx)
                if resolved:
                    anchors.append(resolved)
            elif tag == TAG_ANCHOR_LITERAL:
                anchors.append(value.decode("utf-8", errors="replace"))
            elif tag == TAG_SCOPE:
                if len(value) >= 1:
                    scope = _enum_resolve(value[0], _SCOPE_TABLE) or "personal"
            elif tag == TAG_ACTION_SHAPE:
                if len(value) >= 1:
                    action_shape = _enum_resolve(value[0], _ACTION_TABLE)
            elif tag == TAG_SOURCE:
                if len(value) >= 1:
                    source = _enum_resolve(value[0], _SOURCE_TABLE) or "lora_mesh"
            elif tag == TAG_AUTHOR_HASH:
                author_hash = value
            elif tag == TAG_EPOCH:
                if len(value) == 4:
                    epoch = struct.unpack(">I", value)[0]
            else:
                extra[tag] = value

        # Note: `author_hash` is the compressed form. The receiver
        # has to map back to a known author_id externally; we record
        # the hex for the caller's convenience but do not synthesize
        # the original string.
        wire = cls(
            text=text,
            anchors=anchors,
            scope=scope,
            action_shape=action_shape,
            source=source,
            author_id=author_hash.hex() if author_hash else "",
            epoch=epoch,
            extra=extra,
        )
        return wire


# ── Conversion helpers (JSON dict <-> SeedWire) ─────────────────────


def seed_dict_to_wire(d: Dict[str, Any]) -> SeedWire:
    """Convert a journal-shaped dict (as returned by /capture) to a SeedWire."""
    cat = d.get("categorization") or {}
    return SeedWire(
        text=d.get("text", "") or "",
        anchors=list(cat.get("detected_anchors") or []),
        scope=cat.get("detected_scope") or "personal",
        action_shape=(cat.get("detected_action_shapes") or [""])[0],
        source=d.get("source", "lora_mesh") or "lora_mesh",
        author_id=d.get("author_id", "") or "",
        epoch=int(d.get("written_at") or 0),
    )


def wire_to_capture_payload(w: SeedWire) -> Dict[str, Any]:
    """Convert a decoded SeedWire to a /capture POST payload."""
    return {
        "text": w.text,
        "source": w.source,
        "source_meta": {
            "received_via": "lora_mesh",
            "wire_version": WIRE_VERSION,
            "author_hash": w.author_id,        # already hex if author was set
            "wire_anchors": w.anchors,
            "wire_scope": w.scope,
            "wire_action_shape": w.action_shape,
            "wire_epoch": w.epoch,
        },
        "identity_acknowledged": True,
    }


# ── Public API ──────────────────────────────────────────────────────


__all__ = [
    "WIRE_VERSION",
    "WIRE_TYPE_SEED",
    "WIRE_TYPE_WITNESS",
    "WIRE_TYPE_PRECEDENT",
    "WIRE_TYPE_ACK",
    "SCRIPTURE_DICT",
    "SeedWire",
    "dict_token",
    "dict_resolve",
    "seed_dict_to_wire",
    "wire_to_capture_payload",
]
