# Concordance Canons

Constraints-first, AI-parseable (YAML) domain canons that the Concordance Engine consumes. Each canon defines its own primitives, RED / FLOOR rules, modules, schemas, and example packets, plus a parallel structural validator under `tools/` so the canon can be forked without dragging in the engine package.

## Domains

| Canon | Path | Verifier (in engine) |
|---|---|---|
| Biology | [`biology/`](biology/README.md) | `verifiers/biology.py` (`BIO_VERIFY`) |
| Chemistry | [`chemistry_full/`](chemistry_full/README.md) | `verifiers/chemistry.py` (`CHEM_VERIFY`) |
| Computer Science | [`computer_science/`](computer_science/README.md) | `verifiers/computer_science.py` (`CS_VERIFY`) |
| Mathematics | [`mathematics/`](mathematics/README.md) | `verifiers/mathematics.py` (`MATH_VERIFY`) |
| Physics | [`physics/`](physics/README.md) | `verifiers/physics.py` (`PHYS_VERIFY`) |
| Statistics | [`statistics/`](statistics/README.md) | `verifiers/statistics.py` (`STAT_VERIFY`) |

## Shared

- `tools/` — structural validators (`validator_<domain>.py`), one per canon
- `packet_manifest.yaml` — SHA-256 manifest of all canon files
- `AUTHORITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`

## Smoke test

```bash
PYTHONPATH=src python tests/test_canon_validators.py    # 5 smoke tests, run from lw/01_engine layout
```

This confirms each canon's `tools/validator_<domain>.py` imports cleanly and runs against a representative packet. It does *not* check that the canon validator and the engine validator agree exactly — that is a separate equivalence proof.
