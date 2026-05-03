"""Investment Packet v1.1 — signed, time-bound, revocable credential.

Per canonical 02_SPECS/INVESTMENT_PACKET_SPEC_v1_1.md:

  > A cryptographically signed, time-bound, revocable, privacy-
  > preserving eligibility credential.
  >
  > Goals:
  >   - Raw financial data stays local.
  >   - Only derived bands + proof hashes leave Node.
  >   - Packet is verifiable by recipients without revealing raw data.

Design constraints (canonical):
  * **Ed25519 signature** covers all fields except `signature`.
  * **Privacy-preserving**: raw values never leave Node. Only
    enumerated bands (income_band, liquidity_band, debt_band,
    stability_band) plus SHA-256 proof hashes that prove the local
    computation existed at issuance time.
  * **Revocable**: every packet carries a `revocation_key_id` that
    points at an issuer-maintained revocation list. Verifiers check
    the revocation list before honoring the packet.
  * **Time-bound**: every packet has `expires_at`; recipients refuse
    expired packets even if the signature is still valid.
  * **Supplemental**: per spec, "Packets are supplemental signals,
    not sole authority."

Packet shape (canonical fields, v1.1):
    {
      "packet_version": "1.1",
      "issuer": "node://hdven/2026-05-03",
      "issuer_public_key": "<b64u>",
      "subject_id": "<sha256 hash; no raw PII>",
      "issued_at": "2026-05-03T13:00:00+00:00",
      "expires_at": "2027-05-03T13:00:00+00:00",
      "revocation_key_id": "rl-2026-05",
      "derived_bands": {
        "income_band": "B3",
        "liquidity_band": "B2",
        "debt_band": "B1",
        "stability_band": "B4"
      },
      "proof_hashes": ["<sha256>", "<sha256>", ...],
      "constraints": {
        "income_band_definition": "B1=<25k, B2=25-50k, ...",
        "stability_band_definition": "..."
      },
      "signature": "<b64u>"
    }
"""
from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .signing import sign_packet, verify_packet


PACKET_VERSION = "1.1"

REQUIRED_FIELDS = (
    "packet_version",
    "issuer",
    "issuer_public_key",
    "subject_id",
    "issued_at",
    "expires_at",
    "revocation_key_id",
    "derived_bands",
    "proof_hashes",
    "constraints",
)

# Canonical band families per the spec; bands themselves are open
# strings (B1, B2, ...) — the spec doesn't pin specific labels, only
# requires the four families be present.
REQUIRED_BAND_FAMILIES = (
    "income_band",
    "liquidity_band",
    "debt_band",
    "stability_band",
)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def hash_subject_pii(*identifiers: str) -> str:
    """Build a stable subject_id from raw identifiers WITHOUT exposing
    them. SHA-256 over the concatenated lowercased identifiers; the
    result is what goes in the packet, never the identifiers themselves.

    Recipients can confirm a subject by re-hashing the same
    identifiers and comparing — no raw PII ever leaves the issuer.
    """
    if not identifiers:
        raise ValueError("at least one identifier required")
    joined = "|".join(s.strip().lower() for s in identifiers)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def make_packet(
    *,
    issuer: str,
    issuer_public_key: str,
    subject_id: str,
    derived_bands: Dict[str, str],
    proof_hashes: List[str],
    constraints: Optional[Dict[str, Any]] = None,
    revocation_key_id: str = "default-revocation-list",
    valid_for_days: int = 365,
    issued_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct an UNSIGNED Investment Packet. Caller signs separately
    via signing.sign_packet.

    Validates the canonical structure: required fields, four band
    families, non-empty proof_hashes, ISO8601 timestamps.
    """
    if not isinstance(derived_bands, dict):
        raise TypeError("derived_bands must be a dict")
    missing = [f for f in REQUIRED_BAND_FAMILIES if f not in derived_bands]
    if missing:
        raise ValueError(
            f"derived_bands missing required band families: {missing}"
        )
    if not proof_hashes or not isinstance(proof_hashes, list):
        raise ValueError("proof_hashes must be a non-empty list")
    for h in proof_hashes:
        if not isinstance(h, str) or len(h) != 64:
            raise ValueError(
                "proof_hashes entries must be 64-char SHA-256 hex strings"
            )

    issued = issued_at or _utc_now_iso()
    issued_dt = dt.datetime.fromisoformat(issued.replace("Z", "+00:00"))
    expires_dt = issued_dt + dt.timedelta(days=valid_for_days)

    return {
        "packet_version": PACKET_VERSION,
        "issuer": issuer,
        "issuer_public_key": issuer_public_key,
        "subject_id": subject_id,
        "issued_at": issued_dt.replace(microsecond=0).isoformat(),
        "expires_at": expires_dt.replace(microsecond=0).isoformat(),
        "revocation_key_id": revocation_key_id,
        "derived_bands": dict(derived_bands),
        "proof_hashes": list(proof_hashes),
        "constraints": dict(constraints or {}),
    }


def make_and_sign(
    *,
    private_key: str,
    issuer: str,
    issuer_public_key: str,
    subject_id: str,
    derived_bands: Dict[str, str],
    proof_hashes: List[str],
    constraints: Optional[Dict[str, Any]] = None,
    revocation_key_id: str = "default-revocation-list",
    valid_for_days: int = 365,
    issued_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a packet and sign it in one call. Convenience wrapper."""
    packet = make_packet(
        issuer=issuer,
        issuer_public_key=issuer_public_key,
        subject_id=subject_id,
        derived_bands=derived_bands,
        proof_hashes=proof_hashes,
        constraints=constraints,
        revocation_key_id=revocation_key_id,
        valid_for_days=valid_for_days,
        issued_at=issued_at,
    )
    return sign_packet(packet, private_key)


# ── Verification ──────────────────────────────────────────────────────

def verify_investment_packet(
    packet: Dict[str, Any],
    *,
    revoked_keys: Optional[List[str]] = None,
    now: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Verify a signed Investment Packet end-to-end.

    Checks (in order):
      1. Required fields present.
      2. packet_version matches.
      3. Signature valid against issuer_public_key.
      4. Not expired (expires_at > now).
      5. revocation_key_id not in the supplied revoked_keys list.

    Returns (ok, detail, data) where data is a structured report of
    every check's outcome.
    """
    report: Dict[str, Any] = {"checks": {}}

    # 1. Required fields
    missing = [f for f in REQUIRED_FIELDS if f not in packet]
    report["checks"]["required_fields"] = (
        "ok" if not missing else f"missing: {missing}"
    )
    if missing:
        return False, f"missing required fields: {missing}", report

    # 2. Version match
    if packet.get("packet_version") != PACKET_VERSION:
        report["checks"]["version"] = (
            f"got {packet.get('packet_version')!r}, expected {PACKET_VERSION!r}"
        )
        return (
            False,
            f"packet_version mismatch: {packet.get('packet_version')!r}",
            report,
        )
    report["checks"]["version"] = "ok"

    # 3. Signature
    sig_ok, sig_detail = verify_packet(packet)
    report["checks"]["signature"] = sig_detail
    if not sig_ok:
        return False, f"signature check failed: {sig_detail}", report

    # 4. Expiry
    expires_str = packet.get("expires_at", "")
    try:
        expires_dt = dt.datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
    except ValueError:
        report["checks"]["expiry"] = f"unparseable expires_at: {expires_str!r}"
        return False, "expires_at is not a valid ISO8601 timestamp", report
    now_dt = (
        dt.datetime.fromisoformat(now.replace("Z", "+00:00"))
        if now else dt.datetime.now(dt.timezone.utc)
    )
    if now_dt >= expires_dt:
        report["checks"]["expiry"] = f"expired at {expires_str}"
        return False, f"packet expired at {expires_str}", report
    report["checks"]["expiry"] = f"valid until {expires_str}"

    # 5. Revocation
    rev_id = packet.get("revocation_key_id")
    if revoked_keys and rev_id in revoked_keys:
        report["checks"]["revocation"] = f"revoked: {rev_id}"
        return False, f"revocation_key_id is on revocation list: {rev_id}", report
    report["checks"]["revocation"] = (
        "not on supplied revocation list" if revoked_keys else
        "revocation list not supplied (revocation check skipped)"
    )

    return True, "all checks passed", report


__all__ = [
    "PACKET_VERSION",
    "REQUIRED_FIELDS",
    "REQUIRED_BAND_FAMILIES",
    "hash_subject_pii",
    "make_packet",
    "make_and_sign",
    "verify_investment_packet",
]
