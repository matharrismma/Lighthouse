# Investment Packet - Spec LOCKED v1.1

A cryptographically signed, time-bound, revocable, privacy-preserving eligibility credential.

## Goals
- Raw financial data stays local.
- Only derived bands + proof hashes leave Node.
- Packet is verifiable by recipients without revealing raw data.

## Cryptography
- Signature: **Ed25519**
- Signature covers **all fields except `signature`**.

## Canonical fields (v1.1)
- `packet_version`: "1.1"
- `issuer`: identifier for the issuing Node/system
- `subject_id`: stable hashed identifier for the subject (no raw PII)
- `issued_at`: ISO8601
- `expires_at`: ISO8601
- `revocation_key_id`: key id for issuer revocation list
- `derived_bands`: enumerated bands (income_band, liquidity_band, debt_band, stability_band)
- `proof_hashes`: list of SHA-256 hashes proving local computations existed at issuance
- `constraints`: declared gates/enums used for derivation
- `signature`: Ed25519 signature (base64)

## Notes
- Bank Assist exists only inside StabilityOS with read-only regulated aggregator.
- Packets are **supplemental signals**, not sole authority.
