# Investment Packet Spec (LOCKED v1.1)

Purpose: a cryptographically signed, time-bound, revocable, privacy-preserving eligibility credential.

## Core properties
- Raw financial data stays local
- Only derived bands + proof hashes leave the Node
- Packet is **supplemental signal**, not sole decision source
- Enums and stability gates are canonical

## Cryptography
- Ed25519 signature over all fields **except** signature

## Fields (minimum)
- packet_version
- issued_at, expires_at
- issuer_id
- subject_id (pseudonymous)
- derived_bands (e.g., income_band, debt_band, cashflow_band)
- proof_hashes (hashes of local proofs)
- revocation (revocable handle)
- signature

