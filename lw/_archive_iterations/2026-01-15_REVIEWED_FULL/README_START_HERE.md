# Lighthouse - Current Iteration (2026-01-15)

This folder is the **current, consolidated working set** for Lighthouse as of **January 15, 2026**.

## Contents
- `00_CANON/` - authority order, primary ruleset, and governing constraints (current)
- `01_SEEDS/` - Seed ledger (current) in both Markdown and JSON
- `02_SPECS/` - deterministic specs (LSP pages, Investment Packet v1.1)
- `03_ARCH/` - architecture notes (quarantine/airlock, roles/voices, naming)
- `04_CODE/` - **all computation work** in one file: `lighthouse_all.py`
- `05_TESTS/` - minimal tests that validate hashing, chunking, packet signing/verification
- `06_EXPORTS/` - human-friendly PDF export + zip
- `seed/` - the original Lighthouse Seed Package v1 (kept verbatim)

## Non-negotiables (current)
- **Source hierarchy**: Jesus' words (RED) are primary; all else is secondary and cannot override RED.
- **No forced agreement**: reflection over affirmation; truth over consensus.
- **No ledger**: once confessed within relationship, ledger cannot be reintroduced.
- **Past artifacts are source-only**: historical reference, not governing.
- **New work rule**: only new information may be introduced going forward, and it must integrate cleanly before release.

## Quick start (code)
Run any of these from this folder:

```bash
python3 04_CODE/lighthouse_all.py --help
python3 04_CODE/lighthouse_all.py build-lsp --input my_text.txt --out 06_EXPORTS/lsp.json
python3 04_CODE/lighthouse_all.py sign-packet --packet 02_SPECS/investment_packet_v1_1_example.json --out 06_EXPORTS/signed_packet.json
python3 04_CODE/lighthouse_all.py verify-packet --signed 06_EXPORTS/signed_packet.json
```

If you want everything as one archive, use the zip in `06_EXPORTS/`.
