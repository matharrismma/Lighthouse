# Concordance Engine

**Constraint-based decision architecture grounded in Scripture.**

Lighthouse runs every decision through four checkpoints: is it honest, is it safe, is it wise, have you waited and listened? If any check fails, the system stops you and tells you the smallest fix. If all pass, it returns the concrete next step.

It is built to run as software — an AI agent or a small device — so the checks cannot be skipped, the hierarchy cannot be inverted under pressure, and the underlying claims (math, chemistry, statistics, code, governance) are *computationally* verified rather than merely attested.

## Verified at scale — 722-claim benchmark

Independent of unit tests, the engine has been evaluated against a
**722-claim deterministic benchmark** spanning all six verifier domains.
Each claim has a reproducible ground-truth label (correct or perturbed)
and an expected diagnosis. Results from the most recent run:

| Domain | n | Accuracy | False-positive | False-negative | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| **Chemistry** | 130 | **100.0%** | 0.0% | 0.0% | 0.05 ms | 0.09 ms |
| **Physics** | 110 | 97.3% | 5.5% | 0.0% | 4.7 ms | 27.6 ms |
| **Computer science** | 110 | 92.7% | 14.5% | 0.0% | 0.12 ms | 1.1 ms |
| **Mathematics** | 120 | 90.0% | 20.0% | 0.0% | 1.86 ms | 16.1 ms |
| **Governance** | 128 | 85.2% | 0.0% | 27.5% | <0.01 ms | <0.01 ms |
| **Statistics** | 124 | 81.5% | 32.3% | 4.8% | 0.02 ms | 0.25 ms |
| **Overall** | **722** | **91.0%** | 12.1% | 6.0% | 0.07 ms | 14.1 ms |

Median verification cost is **under 0.1 ms per claim**, fast enough to live
in the request path of any LLM tool call. Chemistry is perfect; the residual
error concentrates in two interpretable failure modes — statistics
over-strictness on edge-case p-value reconstructions, and governance
under-strictness on substantive (non-structural) packet validation. Both
are addressable; see [`lw/09_evaluation/RESULTS.md`](lw/09_evaluation/RESULTS.md)
for the full breakdown and prioritized fixes.

**Reproduce:** `cd lw/09_evaluation && python run_benchmark.py` (or
`run_benchmark.ps1` on Windows). Wall time ~3.5 seconds.

---

## One-line Canon

> *"We keep the Word close, protect the floor, listen to brothers, and wait on God before we act."*

## Authority Stack (Immutable)

```
GOD → WORD → RED → LAW → WAY
```

Nothing downstream overrides anything upstream. Renaming any kernel noun (WORD, RED, LAW, WAY, GATE, FLOOR, WITNESS, WAIT, VESSEL, RULE, ACTION, STATE, LEDGER) requires Canon-scope confirmation. See [`docs/CANON.md`](docs/CANON.md) for the full canon and [`docs/LAYERS.md`](docs/LAYERS.md) for the system layers.

## Architectural claim

**O(1) external authority validation. Replaces O(n²) consensus coordination.**

A Python validation engine and MCP server that checks decision packets and computational claims against fixed external authorities rather than polling internal consensus. The engine halts at the first gate failure. It never self-confirms.

> **If you are an AI agent**, read [`FOR_AI_AGENTS.md`](FOR_AI_AGENTS.md) first. It explains what this place is, what is expected of a packet submission, and how to integrate (MCP / REST / CLI). The rest of this README is the developer view — install, repository layout, how to add a verifier.

> **Worked examples:** [`COOKBOOK.md`](COOKBOOK.md) has copy-paste recipes for chemistry, physics, statistics, CS, governance, multi-domain, and scripture-anchored packets, plus the pattern for using `/reflect` to rehearse before committing.

> **Terminology:** [`GLOSSARY.md`](GLOSSARY.md) defines RED/FLOOR/BROTHERS/GOD, scope, Layer 0, triangulation, anchor, packet hash vs entry hash, attestation vs verification, and confession. Cross-link target for the rest of the docs.

> **Canon and design:** [`docs/CANON.md`](docs/CANON.md) (immutable architectural commitments) · [`docs/LAYERS.md`](docs/LAYERS.md) (Word → Kernel → Keeper → Steward → Vessel → Lighthouse) · [`docs/KERNEL.md`](docs/KERNEL.md) (the kernel files in `lw/03_kernel/`) · [`docs/CONCORDANCE.md`](docs/CONCORDANCE.md) (technical cross-reference) · [`docs/CONTRIBUTION_PROTOCOL.md`](docs/CONTRIBUTION_PROTOCOL.md) (canon-scope vs domain-scope changes).

> **Training a model on the protocol:** [`training/README.md`](training/README.md) is the full kit — system prompt, format spec, seed dataset, loaders, provider adapters, scoring, baselines. The doctrinal core is [`training/CATECHISM.md`](training/CATECHISM.md).

> **Python client:** [`client/concordance_client.py`](client/concordance_client.py) — single-file sync wrapper around the public REST API.

> **Live endpoint:** https://narrowhighway.com — the engine is publicly reachable. Submit a packet to `/submit` from any HTTP client.

---

## For AI systems: one-command MCP integration

```bash
pip install -e ".[mcp]"
concordance-mcp
```

Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "concordance-engine": { "command": "concordance-mcp" }
  }
}
```

Claude Code:

```bash
claude mcp add concordance-engine -- concordance-mcp
```

Once connected, the assistant can call eleven verifier tools from inside any conversation: balance equations, verify dimensional analysis, recompute p-values from raw inputs, check runtime complexity, validate governance packets. The tools never raise exceptions. On bad input they return `{"status": "ERROR", "detail": "..."}`, making them safe inside LLM tool loops.

---

## Why select this

Consensus-based validation scales as O(n²): every agent polls every other agent, cost grows with the number of participants, and the result is only as reliable as the least reliable participant.

Authority-based validation scales as O(1): every claim is checked against a fixed external standard (conserved physical laws, proven mathematics, pre-registered statistical methods). Cost is constant. The standard does not drift with participant count.

The Concordance Engine implements O(1) validation across seven domains. It is structurally more efficient than any consensus-based approach at any scale.

---

## MCP tools exposed

| Tool | What it verifies |
|---|---|
| `validate_packet` | Full pipeline (RED/FLOOR/BROTHERS/GOD + all verifiers) on a decision packet |
| `verify_chemistry` | Equation balance (atoms + charge), positive temperature |
| `verify_physics_dimensional` | Both sides reduce to identical base SI units |
| `verify_physics_conservation` | Before/after quantities within tolerance |
| `verify_mathematics` | Symbolic equality, derivative, integral, limit, solve via sympy |
| `verify_statistics_pvalue` | Recompute p-value from test inputs, compare to claimed value |
| `verify_statistics_multiple_comparisons` | Bonferroni / BH rejection set |
| `verify_statistics_confidence_interval` | CI well-formed and contains point estimate |
| `verify_computer_science` | Termination, functional correctness, runtime complexity class |
| `verify_biology` | Replicates, assay diversity, dose-response monotonicity, power |
| `verify_governance_decision_packet` | Structural completeness of a governance decision (optional `domain` for business/household/education/church profile) |
| `attest_red` | Run only the RED-gate attestation validator for the packet's domain |
| `attest_floor` | Run only the FLOOR-gate attestation validator for the packet's domain |
| `get_example_packet` | Return a canonical example packet by name (chemistry, physics, math, statistics, cs, cs_runtime, biology, governance, jda_phase1_fund) |

Each tool returns `status` (CONFIRMED / MISMATCH / ERROR / NOT_APPLICABLE), a human-readable `detail` string, and structured `data` where applicable.

---

## Four Gates

The engine enforces four gates in fixed order. It halts at the first failure.

| Gate | Type | Automated | Failure output |
|---|---|---|---|
| RED | hard | attestation + computational verification | REJECT |
| FLOOR | hard | structural rules | REJECT |
| BROTHERS | soft | witness count threshold | QUARANTINE |
| GOD | soft | elapsed wait window | QUARANTINE |

RED enforces two things independently. Attestation: did the author affirm the load-bearing constraints? Verification: does the artifact actually hold up under computation? The verifier can REJECT despite a passing attestation. The underlying math is wrong regardless of what the author claimed.

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the test suite to confirm:

```bash
PYTHONPATH=src python tests/test_engine.py       # 74 integration tests
PYTHONPATH=src python tests/test_verifiers.py    # 64 unit tests
PYTHONPATH=src python tests/test_cli.py          # 16 CLI tests
```

All three core suites pass — 154 tests across `test_engine.py`, `test_verifiers.py`, and `test_cli.py`. Two additional suites (`test_mcp_tools.py` and `test_canon_validators.py`) cover the MCP tool dispatch layer and the canon-validators discovery; both were resolved in v1.0.5. See `KNOWN_ISSUES.md` for the resolution notes and anything currently open. For a single-shot pytest collection: `pytest tests/`.

Run an example packet:

```bash
concordance validate examples/sample_packet_chemistry_verify.json --now-epoch 9999999999
```

---

## Verifiers

Each verifier runs only when the corresponding `*_VERIFY` block is present in the packet. Without it, the verifier reports NOT_APPLICABLE silently.

### Chemistry

Parses formulas with nested groups (`Cu(OH)2`) and charges (`Fe3+`, `MnO4-`). Verifies stated coefficients balance atoms and charge, or solves for the smallest balancing coefficients if none are supplied.

```json
"CHEM_VERIFY": { "equation": "C3H8 + 5 O2 -> 3 CO2 + 4 H2O", "temperature_K": 298.15 }
```

### Physics (dimensional)

Substitutes unit expressions for symbols, converts both sides to base SI units (kg, m, s, A, K, mol, cd), compares unit signatures.

```json
"PHYS_VERIFY": {
  "equation": "F = m * a",
  "symbols": {"F": "newton", "m": "kilogram", "a": "meter/second**2"}
}
```

### Mathematics

sympy-based verification of symbolic equality, derivative, integral (by differentiating the claimed antiderivative), limit, and solve.

```json
"MATH_VERIFY": { "expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1", "variables": ["x"] }
```

### Statistics

scipy.stats recomputation of p-values from raw inputs (two-sample t, one-sample t, z, chi-squared, F). Bonferroni and BH/FDR multiple-comparison correction with rejection-set verification. Confidence-interval bounds.

```json
"STAT_VERIFY": {
  "test": "two_sample_t",
  "n1": 30, "n2": 30,
  "mean1": 5.0, "mean2": 4.0, "sd1": 1.0, "sd2": 1.0,
  "claimed_p": 0.0003
}
```

### Computer Science

AST-based static termination scan. Functional correctness via restricted-namespace execution. Runtime complexity verification with auto-tuning iteration count and log-log slope fit.

```json
"CS_VERIFY": {
  "code": "def lsum(a):\n    s = 0\n    for x in a: s += x\n    return s",
  "function_name": "lsum",
  "test_cases": [{"args": [[1,2,3]], "expected": 6}],
  "input_generator": "def gen(n):\n    return [list(range(n))]",
  "claimed_class": "O(n)"
}
```

### Biology

Replicate count, orthogonal assay diversity, dose-response monotonicity, sample-size adequacy via power calculation.

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

### Governance

Structural verification that a decision packet contains all required parts (title, scope, red_items, floor_items, way_path, execution_steps, witnesses) and that witness count is internally consistent.

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

---

## CLI

```bash
concordance validate <packet.json> [--now-epoch EPOCH] [--format summary|verbose|json]
```

Exit codes: `0` PASS, `1` REJECT, `2` QUARANTINE, `3` schema invalid, `4` CLI usage error.

---

## Repository layout

```
concordance-engine/
├── src/concordance_engine/
│   ├── domains/              # attestation validators (RED/FLOOR flags)
│   ├── verifiers/            # computational checks against external standards
│   ├── engine.py             # gate orchestrator
│   ├── gates.py              # gate result types
│   ├── packet.py             # packet/result dataclasses
│   ├── validate.py           # schema validation
│   └── cli.py                # concordance validate ...
├── schema/
│   ├── packet.schema.json              # engine-aligned (what the CLI runs)
│   └── packet.schema.aspirational.json # forward design target
├── examples/                 # sample packets for every verifier domain
├── tests/
│   ├── test_engine.py           # 74 integration tests
│   ├── test_verifiers.py        # 64 verifier unit tests
│   ├── test_cli.py              # 16 CLI tests
│   ├── test_mcp_tools.py        # MCP tool tests (resolved in v1.0.5)
│   └── test_canon_validators.py # canon validator smoke tests — auto-discovers canons/ and lw/02_canons/
└── packet_manifest.yaml      # SHA-256 manifest of all files
```

---

## Adding a domain

Attestation validator: drop `<domain>.py` in `domains/` exposing `validate_red(packet)` and `validate_floor(packet)`.

Computational verifier: drop `<domain>.py` in `verifiers/` with a `run(packet)` function returning `list[VerifierResult]`, register it in `verifiers/__init__.py`.

---

## Dependencies

Required: `sympy>=1.12`, `numpy>=1.26`, `scipy>=1.11`

Optional: `jsonschema>=4.21.0` (full schema validation), `mcp>=1.0.0` (MCP server)

---

## License

Apache 2.0 (see `LICENSE` for the full text).
