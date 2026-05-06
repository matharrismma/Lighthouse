"""LoRa-compatible compact packet serialization.

LoRa radios (Meshtastic, sub-GHz mesh) have a maximum payload of
~255 bytes per frame. A full WitnessRecord or PolymathicRecord JSON
is orders of magnitude larger and cannot be transmitted directly.

This module solves that by producing a minimal binary frame that:
  1. Fits in a single LoRa frame (28–72 bytes typical)
  2. Contains enough to identify and retrieve the full record by hash
  3. Can be decoded by any peer to determine verdict without fetching

The full record is retrieved by hash once connectivity is restored.
The frame is the beacon; the CAS is the well.

Frame format (binary, big-endian):
  Offset  Bytes  Field
  0       1      type: 0x01=WitnessRecord, 0x02=PolymathicRecord
  1       1      version: 0x01
  2       2      seq_lo: uint16 (low 16 bits of hash as sequence hint)
  4       4      timestamp: uint32 unix epoch
  8       16     hash_bytes: first 16 bytes of SHA-256 (enough to identify)
  24      1      verdict_byte: see VERDICT_CODES
  25      1      domain_count: uint8 (poly: total domains; witness: 1)
  26      1      confirmed_count: uint8
  27      1      flags: bit0=has_precedent, bit1=has_quarantine, bit2=subject_bound
  28      N      summary_utf8: situation/claim prefix, up to min(budget, 227) bytes

Maximum safe summary: 255 − 28 = 227 bytes → ~56–100 UTF-8 chars

Text relay format (SMS / e-ink / serial):
  [TYPE:hash7|VERDICT|confirmed/total|dim1+dim2]
  e.g. [POLY:2d3b835|CONCORDANT|3/3|authority_trust+time_seq]
       [WIT:a1b2c3d|CONFIRMED|1/1|labor]

No external dependencies. Pure stdlib struct + bytes.
Works offline. No oracle calls.
"""
from __future__ import annotations

import struct
import time
from typing import Any, Dict, List, Optional, Tuple

# ── Verdict encoding ────────────────────────────────────────────────────

VERDICT_CODES: Dict[str, int] = {
    "CONFIRMED":      0x00,
    "CONCORDANT":     0x01,
    "MISMATCH":       0x02,
    "DISCORDANT":     0x03,
    "MIXED":          0x04,
    "QUARANTINE":     0x05,
    "OUT_OF_SCOPE":   0x06,
    "NOT_APPLICABLE": 0x07,
    "ERROR":          0xFF,
    "UNKNOWN":        0xFE,
}
VERDICT_NAMES: Dict[int, str] = {v: k for k, v in VERDICT_CODES.items()}

FRAME_TYPE_WITNESS    = 0x01
FRAME_TYPE_POLYMATHIC = 0x02
FRAME_VERSION         = 0x01
FRAME_HEADER_SIZE     = 28   # bytes before optional summary
LORA_MAX_PAYLOAD      = 255  # bytes, conservative LoRa limit

# Flag bits
FLAG_HAS_PRECEDENT  = 0x01
FLAG_HAS_QUARANTINE = 0x02
FLAG_SUBJECT_BOUND  = 0x04


# ── Encoder ─────────────────────────────────────────────────────────────

def encode_polymathic(record_dict: Dict[str, Any], seq: int = 0) -> bytes:
    """Encode a PolymathicRecord dict into a LoRa frame.

    The full record is referenced by content_hash; this frame carries
    only what a receiving peer needs to:
      - identify the record (hash prefix)
      - know the verdict without fetching
      - decide whether to request the full record
    """
    content_hash = record_dict.get("content_hash") or record_dict.get("permanent_ref") or ""
    verdict_str  = record_dict.get("composite_verdict", "UNKNOWN")
    dr_list      = record_dict.get("domain_results", [])
    timestamp    = int(record_dict.get("sealed_at", time.time()))
    situation    = record_dict.get("situation", "")
    has_prec     = record_dict.get("closest_precedent") is not None
    has_quar     = bool(record_dict.get("quarantined_claims"))
    has_key      = bool(record_dict.get("subject_pubkey"))

    domain_count    = len(dr_list)
    confirmed_count = sum(1 for dr in dr_list if dr.get("verdict") == "CONFIRMED")
    verdict_byte    = VERDICT_CODES.get(verdict_str, 0xFE)
    flags           = (
        (FLAG_HAS_PRECEDENT  if has_prec else 0) |
        (FLAG_HAS_QUARANTINE if has_quar else 0) |
        (FLAG_SUBJECT_BOUND  if has_key  else 0)
    )

    hash_bytes  = _hash_prefix(content_hash)
    seq_lo      = seq & 0xFFFF

    header = struct.pack(
        ">BBHl16sBBBB",
        FRAME_TYPE_POLYMATHIC,
        FRAME_VERSION,
        seq_lo,
        timestamp,
        hash_bytes,
        verdict_byte,
        min(domain_count,    255),
        min(confirmed_count, 255),
        flags,
    )

    summary_bytes = _trim_utf8(situation, LORA_MAX_PAYLOAD - FRAME_HEADER_SIZE)
    return header + summary_bytes


def encode_witness(record_dict: Dict[str, Any], seq: int = 0) -> bytes:
    """Encode a WitnessRecord dict into a LoRa frame."""
    content_hash = record_dict.get("content_hash") or ""
    verdict_str  = record_dict.get("overall", record_dict.get("verdict", "UNKNOWN"))
    domain       = record_dict.get("domain", "")
    timestamp    = int(record_dict.get("timestamp_epoch", time.time()))
    claim        = record_dict.get("claim", domain)
    has_key      = bool(record_dict.get("subject_pubkey"))

    verdict_byte = VERDICT_CODES.get(verdict_str, 0xFE)
    flags        = FLAG_SUBJECT_BOUND if has_key else 0
    hash_bytes   = _hash_prefix(content_hash)
    seq_lo       = seq & 0xFFFF

    header = struct.pack(
        ">BBHl16sBBBB",
        FRAME_TYPE_WITNESS,
        FRAME_VERSION,
        seq_lo,
        timestamp,
        hash_bytes,
        verdict_byte,
        1,    # domain_count
        1 if verdict_str == "CONFIRMED" else 0,
        flags,
    )

    summary = _trim_utf8(claim or domain, LORA_MAX_PAYLOAD - FRAME_HEADER_SIZE)
    return header + summary


# ── Decoder ─────────────────────────────────────────────────────────────

def decode(frame: bytes) -> Dict[str, Any]:
    """Decode a LoRa frame back to a minimal summary dict.

    The returned dict contains enough to identify the record by
    hash_prefix and retrieve the full content via GET /cas/{hash}.
    """
    if len(frame) < FRAME_HEADER_SIZE:
        raise ValueError(f"frame too short: {len(frame)} < {FRAME_HEADER_SIZE}")

    frame_type, version, seq_lo, timestamp, hash_bytes, verdict_byte, \
        domain_count, confirmed_count, flags = struct.unpack(
        ">BBHl16sBBBB", frame[:FRAME_HEADER_SIZE]
    )

    summary_bytes = frame[FRAME_HEADER_SIZE:]
    try:
        summary = summary_bytes.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        summary = ""

    return {
        "frame_type":      "POLYMATHIC" if frame_type == FRAME_TYPE_POLYMATHIC else "WITNESS",
        "version":         version,
        "seq_lo":          seq_lo,
        "timestamp":       timestamp,
        "hash_prefix":     hash_bytes.hex(),
        "verdict":         VERDICT_NAMES.get(verdict_byte, "UNKNOWN"),
        "domain_count":    domain_count,
        "confirmed_count": confirmed_count,
        "has_precedent":   bool(flags & FLAG_HAS_PRECEDENT),
        "has_quarantine":  bool(flags & FLAG_HAS_QUARANTINE),
        "subject_bound":   bool(flags & FLAG_SUBJECT_BOUND),
        "summary":         summary,
        "frame_size":      len(frame),
    }


# ── Text relay format ────────────────────────────────────────────────────

def text_frame_polymathic(record_dict: Dict[str, Any]) -> str:
    """One-line text relay for SMS / serial / e-ink display.

    Format: [POLY:hash7|verdict|confirmed/total|dim1+dim2]
    Always ≤ 80 chars. Safe to send as a single SMS segment.
    """
    content_hash   = record_dict.get("content_hash") or ""
    verdict        = record_dict.get("composite_verdict", "?")
    dr_list        = record_dict.get("domain_results", [])
    overlaps       = record_dict.get("axis_overlaps", [])
    confirmed      = sum(1 for dr in dr_list if dr.get("verdict") == "CONFIRMED")
    total          = len(dr_list)
    hash7          = (content_hash[:7] if content_hash else "???????")
    dims           = "+".join(
        ao.get("dimension", "")[:8] for ao in overlaps[:3]
        if ao.get("dimension")
    )
    dims_part = f"|{dims}" if dims else ""
    return f"[POLY:{hash7}|{verdict}|{confirmed}/{total}{dims_part}]"


def text_frame_witness(record_dict: Dict[str, Any]) -> str:
    """One-line text relay for a WitnessRecord.

    Format: [WIT:hash7|verdict|domain]
    """
    content_hash = record_dict.get("content_hash") or ""
    verdict      = record_dict.get("overall", record_dict.get("verdict", "?"))
    domain       = record_dict.get("domain", "?")
    hash7        = (content_hash[:7] if content_hash else "???????")
    return f"[WIT:{hash7}|{verdict}|{domain}]"


def parse_text_frame(text: str) -> Optional[Dict[str, Any]]:
    """Parse a text relay frame back to a minimal dict. Returns None on failure."""
    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return None
    inner = text[1:-1]
    parts = inner.split("|")
    if len(parts) < 3:
        return None
    type_hash = parts[0]
    if ":" not in type_hash:
        return None
    ftype, hash7 = type_hash.split(":", 1)
    ftype = ftype.upper()
    verdict = parts[1]

    if ftype == "POLY" and len(parts) >= 3:
        count_part = parts[2]
        confirmed, _, total = count_part.partition("/")
        dims = parts[3].split("+") if len(parts) > 3 else []
        return {
            "frame_type": "POLYMATHIC",
            "hash_prefix": hash7,
            "verdict": verdict,
            "confirmed_count": int(confirmed) if confirmed.isdigit() else 0,
            "domain_count": int(total) if total.isdigit() else 0,
            "dims_hint": [d for d in dims if d],
        }
    if ftype == "WIT":
        return {
            "frame_type": "WITNESS",
            "hash_prefix": hash7,
            "verdict": verdict,
            "domain": parts[2] if len(parts) > 2 else "?",
        }
    return None


# ── Helpers ─────────────────────────────────────────────────────────────

def _hash_prefix(content_hash: str) -> bytes:
    """Return the first 16 bytes of a hex SHA-256 hash as raw bytes.
    Pads with zeros if hash is shorter (shouldn't happen in practice).
    """
    try:
        raw = bytes.fromhex(content_hash[:32])
        return raw.ljust(16, b"\x00")
    except (ValueError, TypeError):
        return b"\x00" * 16


def _trim_utf8(text: str, max_bytes: int) -> bytes:
    """Encode text to UTF-8 and truncate to max_bytes without splitting a char."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return encoded
    # Truncate at a clean UTF-8 boundary
    truncated = encoded[:max_bytes]
    # Back off until we have a valid UTF-8 prefix
    while truncated:
        try:
            truncated.decode("utf-8")
            return truncated
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return b""


__all__ = [
    "encode_polymathic", "encode_witness", "decode",
    "text_frame_polymathic", "text_frame_witness", "parse_text_frame",
    "VERDICT_CODES", "VERDICT_NAMES",
    "FRAME_HEADER_SIZE", "LORA_MAX_PAYLOAD",
]
