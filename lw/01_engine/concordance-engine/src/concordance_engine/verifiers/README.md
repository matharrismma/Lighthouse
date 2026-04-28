# concordance_engine.verifiers

Computational checks on submitted artifacts. Each domain validator in `domains/` checks attestation flags ("did the author affirm"). The verifier here checks artifacts ("does the math actually balance").

## Adding a verifier

1. Create `verifiers/<domain>.py` with a `run(packet) -> list[VerifierResult]` function. Use the helpers `na`, `confirm`, `mismatch`, `error` from `verifiers.base` to construct results.
2. Register the module in `verifiers/__init__.py`'s `VERIFIERS` dict, mapping the domain string (matching the packet's `domain` field) to the module.
3. Add the corresponding `*_VERIFY` block schema entry in `schema/packet.schema.json`.
4. Add tests in `tests/test_verifiers.py` (unit) and `tests/test_engine.py` (integration through the engine).
5. Add an example packet in `examples/sample_packet_<domain>_verify.json`.

## Result semantics

| Status | Engine effect | Meaning |
|---|---|---|
| CONFIRMED | recorded as RED pass detail | artifact verified |
| MISMATCH | RED REJECT | artifact contradicts the claim |
| ERROR | RED REJECT | artifact malformed (parse failure, missing fields) |
| NOT_APPLICABLE | silent | verifier had no artifact to check |

## What's here

| Module | Recognized block | What it checks |
|---|---|---|
| `chemistry.py` | `CHEM_VERIFY` | equation balance, charge balance, T > 0 K |
| `physics.py` | `PHYS_VERIFY` | dimensional consistency, conservation arithmetic |
| `mathematics.py` | `MATH_VERIFY` | equality, derivative, integral, limit, solve |
| `statistics.py` | `STAT_VERIFY` | p-value, significance, multiple comparisons, CI |
| `computer_science.py` | `CS_VERIFY` | static termination, correctness, runtime complexity |
| `biology.py` | `BIO_VERIFY` | replicates, orthogonal assays, dose-response, power |
| `governance.py` | `DECISION_PACKET` | structural completeness, witness count consistency |

## Running

```bash
PYTHONPATH=src python tests/test_verifiers.py    # unit tests
PYTHONPATH=src python tests/test_engine.py       # integration tests
```

## Constraints

- Verifiers must be deterministic (no network, no time-dependent results except the runtime-complexity verifier which measures wall time deliberately).
- Code execution in `computer_science.py` runs in a restricted namespace (`_SAFE_BUILTINS`) — no `__import__`, `open`, `eval`, `exec`, `compile`. Snippets are intended for user-controlled code, not untrusted input.
- Numerical comparisons should expose tolerances as parameters (`tolerance_relative`, `tolerance_absolute`, etc.) and document the default.
