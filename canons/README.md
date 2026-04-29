# Canons

Each canon directory holds a domain spec plus a parallel validator implementation that's intentionally independent of the engine package. The canon validator can be forked or reimplemented in another language without dragging in `concordance_engine.*`.

## Layout

```
canons/<domain>/
    spec.md             # human-readable canon (forbidden patterns, required fields)
    tools/
        validator_<domain>.py    # standalone validator: validate_<domain>_packet(packet) -> dict
```

The validator function returns a dict with keys: `passed: bool`, `errors: list[str]`, `warnings: list[str]`.

## Where the populated canons live today

The canonical `02_canons/` tree is kept under `lw/02_canons/` (mathematics, physics, chemistry_full, biology, computer_science, statistics). The smoke test at `tests/test_canon_validators.py` discovers canons by probing both `canons/` (this directory) and `lw/02_canons/` so either layout works.

## Adding a new canon

1. Create `canons/<domain>/spec.md` with the protected categories, required fields, and example packets.
2. Create `canons/<domain>/tools/validator_<domain>.py` with a `validate_<domain>_packet(packet)` function returning `{passed, errors, warnings}`.
3. Add a smoke-test entry in `tests/test_canon_validators.py`.
4. Drop the corresponding domain validator into `src/concordance_engine/domains/<domain>.py` and verifier (if applicable) into `src/concordance_engine/verifiers/<domain>.py`.

The engine and the canon are deliberately separate sources of truth. A future maintainer reimplementing the engine in Rust or Go can use `canons/<domain>/spec.md` and the validator there as the contract, ignoring the Python engine entirely.
