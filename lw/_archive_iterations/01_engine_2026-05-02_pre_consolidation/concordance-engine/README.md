# Concordance Engine

A Python reference implementation of a **Four-Gates validation engine** for decision/plan packets, with **cross-disciplinary computational verifiers** that check submitted artifacts (not just attestation flags).

The engine can deterministically return **REJECT** (RED/FLOOR violations or verifier failures) or **QUARANTINE** (BROTHERS/GOD pending), but never self-confirms a packet without external witness and elapsed wait.

## Two layers on RED

The engine enforces RED in two stages:

1. **Attestation** (domain validators in `domains/`). Did the author affirm the load-bearing constraints? `mass_conserved: true`, `termination_proven: true`, `effect_size: 0.5`. A checklist that the author owns.
2. **Verification** (verifiers in `verifiers/`). Does the artifact actually hold up under computation? Equation balanced? Units consistent? p-value matches the data? Code passes its tests? This is independent of what the author said.

Attestation lives on FLOOR-style structural rules. Verification lives on RED — when an artifact contradicts the claim, the underlying math is wrong, which is a stronger failure than a missing attestation. The verifier never overrides a passing attestation, but it can REJECT despite one.

## Four Gates

| Gate | Type | Automated | Output on fail |
|---|---|---:|---|
| RED | hard | attestation + verification | REJECT |
| FLOOR | hard | yes | REJECT |
| BROTHERS | soft | partially (witness count threshold) | QUARANTINE |
| GOD | soft | yes (wait-window math) | QUARANTINE |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=src python tests/test_engine.py            # 70 integration tests
PYTHONPATH=src python tests/test_verifiers.py         # 53 verifier unit tests
PYTHONPATH=src python tests/test_cli.py               # 16 CLI tests
PYTHONPATH=src python tests/test_canon_validators.py  # 5 canon-validator smoke tests
# tests/test_mcp_tools.py currently fails on import; see ../../KNOWN_ISSUES.md
concordance validate examples/sample_packet_chemistry_verify.json --now-epoch 9999999999
```

## MCP server (Claude / AI assistant integration)

The verifier layer is also exposed as an MCP server so Claude (and other MCP-capable assistants) can call the verifiers from inside a conversation. Install the optional dependency:

```bash
pip install -e ".[mcp]"
concordance-mcp    # runs over stdio
```

Connect Claude Desktop with this `claude_desktop_config.json` entry:
```json
{
  "mcpServers": {
    "concordance-engine": { "command": "concordance-mcp" }
  }
}
```

See `src/concordance_engine/mcp_server/README.md` for the full tool list, Claude Code setup, conversational examples, and limitations.

The CLI prints a human-readable summary by default:

```
✓ PASS  (examples/sample_packet_chemistry_verify.json)
    ✓ RED        PASS
          ✓ chemistry.equation: atoms and charge balanced under stated coefficients
          ✓ chemistry.temperature_K: 298.15 K positive
    ✓ FLOOR      PASS
    ✓ BROTHERS   PASS
    ✓ GOD        PASS
```

Corrupt the equation (change `5 O2` to `4 O2`) and the engine tells you the correct coefficients in the failure message:

```
✗ REJECT  (bad_chem.json)
    ✗ RED        REJECT
          • chemistry.equation: unbalanced under stated coefficients but balances as: C3H8 + 5 O2 -> 3 CO2 + 4 H2O
    FLOOR      (skipped)
    BROTHERS   (skipped)
    GOD        (skipped)
```

Output formats: `--format summary` (default), `--format verbose` (full detail), `--format json` (machine-readable).

Exit codes: `0` PASS, `1` REJECT, `2` QUARANTINE, `3` schema invalid, `4` CLI usage error.

## Verifiers — what's checked

Each verifier runs only when the corresponding `*_VERIFY` block is present in the packet. Otherwise it reports NOT_APPLICABLE silently.

### Chemistry — `CHEM_VERIFY`
Parses chemical formulas with nested groups (Cu(OH)₂) and charges (Fe³⁺, MnO₄⁻). Verifies the stated coefficients balance atoms and charge, or — if coefficients are missing — solves for the smallest balancing coefficients via Fraction-based nullspace. Also verifies temperature_K > 0.

```json
"CHEM_VERIFY": { "equation": "C3H8 + 5 O2 -> 3 CO2 + 4 H2O", "temperature_K": 298.15 }
```

### Physics — `PHYS_VERIFY`
Substitutes unit expressions for symbols, converts both sides to base SI units (kg, m, s, A, K, mol, cd), and compares unit signatures. Plus per-quantity conservation arithmetic with relative+absolute tolerance.

```json
"PHYS_VERIFY": {
  "equation": "F = m * a",
  "symbols": {"F": "newton", "m": "kilogram", "a": "meter/second**2"}
}
```

### Mathematics — `MATH_VERIFY`
sympy-based verification of symbolic equality, derivative, integral (via differentiating the claimed antiderivative), limit, and solve.

```json
"MATH_VERIFY": { "expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1", "variables": ["x"] }
```

### Statistics — `STAT_VERIFY`
scipy.stats-based recomputation of p-values from supplied inputs (two-sample t / one-sample t / z / chi² / F). Bonferroni and BH/FDR multiple-comparison correction with rejection-set verification. Significance-claim consistency. Confidence-interval bounds.

```json
"STAT_VERIFY": {
  "test": "two_sample_t",
  "n1": 30, "n2": 30,
  "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
  "claimed_p": 0.0003
}
```

### Computer Science — `CS_VERIFY`
AST-based static termination scan (catches `while True:` without break and unguarded recursion, including ternary forms). Functional correctness via restricted-namespace execution. Runtime complexity verification with auto-tuning iteration count and log-log slope fit.

```json
"CS_VERIFY": {
  "code": "def lsum(a):\n    s = 0\n    for x in a: s += x\n    return s",
  "function_name": "lsum",
  "test_cases": [{"args": [[1,2,3]], "expected": 6}],
  "input_generator": "def gen(n):\n    return [list(range(n))]",
  "claimed_class": "O(n)"
}
```

### Biology — `BIO_VERIFY`
Replicate count >= minimum. Orthogonal assay diversity. Dose-response monotonicity (with optional expected_direction). Sample-size adequacy via two-sample t-test power calculation.

```json
"BIO_VERIFY": {
  "n_replicates": 4,
  "assay_classes": ["qPCR", "western_blot", "imaging"],
  "dose_response": {
    "doses": [0,1,5,25,125],
    "responses": [0.1,0.3,0.5,0.8,0.95],
    "expected_direction": "increasing"
  },
  "power_analysis": {"effect_size": 0.5, "alpha": 0.05, "n_per_group": 64}
}
```

### Governance / Business / Household / Education / Church — `DECISION_PACKET`
Structural verification that a decision packet has the required parts (title, scope, red_items, floor_items, way_path, execution_steps, witnesses) and that the witness count is internally consistent. Content judgement remains human; the existing keyword scanner runs alongside as triage.

```json
"DECISION_PACKET": {
  "title": "Approve workforce-development RFP",
  "scope": "canon",
  "red_items": ["no coercion", "no exploitation"],
  "floor_items": ["budget within tolerance"],
  "way_path": "Issue RFP through GNWTC partnership; scope limited to trades programs.",
  "execution_steps": ["Draft RFP", "Board review", "Issue", "Evaluate"],
  "witnesses": ["Board Chair", "GNWTC President", "County Commissioner"]
}
```

## Repository layout

```
concordance-engine/
├── src/concordance_engine/
│   ├── domains/              # attestation validators (RED/FLOOR flags)
│   ├── verifiers/            # computational checks (artifacts)
│   ├── engine.py             # gate orchestrator
│   ├── gates.py              # gate result types
│   ├── packet.py             # packet/result dataclasses
│   ├── validate.py           # schema validation (jsonschema optional)
│   └── cli.py                # `concordance validate ...`
├── schema/
│   ├── packet.schema.json              # engine-aligned (what the CLI runs)
│   └── packet.schema.aspirational.json # forward design target
├── examples/                 # sample packets exercising every verifier
├── tests/
│   ├── test_engine.py        # full integration tests (70 cases)
│   ├── test_verifiers.py     # verifier unit tests (53 cases)
│   ├── test_cli.py           # CLI wrapper tests (16 cases)
│   ├── test_mcp_tools.py     # MCP tool tests (currently broken — see KNOWN_ISSUES.md)
│   └── test_canon_validators.py  # canon-side validator smoke tests (5 cases)
└── packet_manifest.yaml      # SHA-256 of all files
```

## Dependencies

Required:
- `sympy>=1.12` (math + physics + chemistry)
- `numpy>=1.26` (statistics + biology power)
- `scipy>=1.11` (statistics + biology power)

Optional:
- `jsonschema>=4.21.0` — install via `pip install -e ".[schema]"` for full schema validation. Without it, the CLI falls back to a structural check (required fields, top-level type, recognized keys).

## Notes

- Domain validators in `domains/` are plugins. Adding a new domain means dropping in `<domain>.py` with a class exposing `validate_red(packet)` and `validate_floor(packet)`.
- Verifiers in `verifiers/` are also plugins. Adding a new verifier means dropping in `<domain>.py` with a `run(packet)` function returning `list[VerifierResult]`, and registering it in `verifiers/__init__.py`.
- BROTHERS attestations are represented as `witness_count` and `required_witnesses` in the packet; the structural verifier (governance) cross-checks named witnesses against the count.
- GOD gate is enforced via scope-specific minimum wait windows: adapter (1 hour), mesh (24 hours), canon (7 days).
- The engine never confirms a packet without external witness AND elapsed wait. PASS means all four gates cleared, including the human-time-and-witness component.
