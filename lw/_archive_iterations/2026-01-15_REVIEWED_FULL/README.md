# Lighthouse - Current Iteration (as of 2026-01-15)

This package contains the **current, consolidated working set** for Lighthouse.

## Folder map
- `00_CANON/` - primary rules, source hierarchy, alignment protocol
- `01_SEEDS/` - seeds ledger (Markdown + JSON)
- `02_SPECS/` - deterministic specs (LSP + Investment Packet v1.1)
- `03_ARCH/` - quarantine/airlock + roles/voices + naming/structure
- `04_CODE/` - **all computation work** (single file): `lighthouse_all.py`
- `05_TESTS/` - minimal test runner to validate hashing + signing
- `06_EXPORTS/` - place for generated outputs
- `seed/` - original seed package v1 (kept verbatim)

## Quick start

```bash
# from the root of this folder
python3 05_TESTS/run_tests.py

python3 04_CODE/lighthouse_all.py build-lsp --input my_text.txt --out 06_EXPORTS/lsp.json
python3 04_CODE/lighthouse_all.py gen-keys --out-dir 06_EXPORTS/keys
python3 04_CODE/lighthouse_all.py sign-packet --packet 02_SPECS/investment_packet_v1_1_example.json --private-key-file 06_EXPORTS/keys/ed25519_private_key.b64 --out 06_EXPORTS/signed_packet.json
python3 04_CODE/lighthouse_all.py verify-packet --signed 06_EXPORTS/signed_packet.json --public-key-file 06_EXPORTS/keys/ed25519_public_key.b64
```

## Non-negotiables (current)
- **Source hierarchy**: Jesus' words (RED) are primary; all else is secondary and cannot override RED.
- **No forced agreement**: reflection over affirmation; truth over consensus.
- **No ledger**: once confessed within relationship, ledger cannot be reintroduced.
- **Past artifacts are source-only**: historical reference, not governing.
- **New work rule**: only new information may be introduced going forward, and it must integrate cleanly before release.
