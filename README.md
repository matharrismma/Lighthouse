# Concordance Engine

**Constraint-based decision architecture grounded in Scripture.**

Lighthouse runs every decision through four checkpoints: is it honest, is it safe, is it wise, have you waited and listened? If any check fails, the system stops you and tells you the smallest fix. If all pass, it returns the concrete next step.

It is built to run as software — an AI agent or a small device — so the checks cannot be skipped, the hierarchy cannot be inverted under pressure, and the underlying claims (math, chemistry, statistics, code, governance) are *computationally* verified rather than merely attested.

## Try it in one call (hosted, zero install)

The engine is live and publicly reachable. Verify a derivation and get a permanent,
independently-checkable receipt -- no install:

```bash
curl -s https://narrowhighway.com/derivation/verify \
  -H 'content-type: application/json' \
  -d '{"steps":[{"id":"s1","domain":"mathematics","spec":{"mode":"equality",
       "params":{"expr_a":"sin(x)**2 + cos(x)**2","expr_b":"1","variables":{}}}}],
       "seal":true}'
```

Returns `verdict: HOLDS` and a `receipt.cite_url` (e.g. `https://narrowhighway.com/seal/<hash>`)
-- a content-addressed page anyone can open to confirm the verdict, independent of trusting you
or this service. MCP server (zero install): `https://narrowhighway.com/mcp`. Agent quickstart:
[`llms.txt`](llms.txt).

**Live-endpoint adversarial check (2026-06-13):** the public endpoint was run against a 52-claim
ground-truth set -- 26 true claims (should hold) and **26 deliberately false** ones (should be
caught) across equality, inequality, and derivative checks. Result: **52 / 52 decided correctly,
zero false seals, zero rejected truths.** Reproduce: `python tools/benchmark_public_verify.py`.
Full record: [`BENCHMARK_PUBLIC_VERIFY.md`](BENCHMARK_PUBLIC_VERIFY.md). (Complements the
722-claim local-domain benchmark below.)

## Verified at scale — 722-claim benchmark

Independent of unit tests, the engine has been evaluated against a
**722-claim deterministic benchmark** spanning all six verifier domains.
Each claim has a reproducible ground-truth label (correct or perturbed)
and an expected diagnosis. Results from the 2026-05-02 run:

| Domain | n | Accuracy | False-positive | False-negative | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| **Chemistry** | 130 | **100.0%** | 0.0% | 0.0% | 0.1 ms | 0.1 ms |
| **Physics** | 110 | **100.0%** | 0.0% | 0.0% | 8.6 ms | 24.8 ms |
| **Mathematics** | 120 | **100.0%** | 0.0% | 0.0% | 3.5 ms | 17.2 ms |
| **Statistics** | 124 | **100.0%** | 0.0% | 0.0% | <0.1 ms | 0.1 ms |
| **Computer science** | 110 | **100.0%** | 0.0% | 0.0% | 0.1 ms | 568.7 ms |
| **Governance** | 128 | **100.0%** | 0.0% | 0.0% | <0.01 ms | <0.01 ms |
| **Overall** | **722** | **100.0%** | 0.0% | 0.0% | 0.1 ms | 19.5 ms |

**722 of 722 claims decided correctly.** Median verification cost is **under 0.1 ms per claim**, fast enough to live in the request path of any LLM tool call. The CS p95 (568.7 ms) reflects the per-claim wall-clock budget that bounds runtime-complexity timing measurements; the median is a tenth of a millisecond. See [`lw/09_evaluation/RESULTS.md`](lw/09_evaluation/RESULTS.md) for the full breakdown.

**Reproduce:** `cd lw/09_evaluation && python run_benchmark.py` (or
`run_benchmark.ps1` on Windows). Wall time ~32 seconds.

---

## Substrate (v1.2.0)

Beyond the verifier core, the engine now ships infrastructure for
operating in hostile or constrained network environments. Per the
kingdom-economy substrate doctrine: works for someone who refuses
the mark of the beast. Every channel below uses tools the operator
already pays for or that are open-source and free.

**Capture from anywhere — six surfaces, one funnel:**

| Surface | Lift | Where |
|---|---|---|
| Watch a folder (iCloud / Dropbox / GDrive) | stdlib only | [`client/watch_folder.py`](client/watch_folder.py) |
| Apple Shortcut → Share Sheet | 90-second one-time setup | [`client/apple_shortcut.md`](client/apple_shortcut.md) |
| Web Share Target (PWA) | works on any phone | [`site/share.html`](site/share.html) |
| NFC tap (Android) | Web NFC API | [`site/nfc.html`](site/nfc.html) |
| Email forward → seed | Cloudflare Worker recipe | [`client/email_webhook.md`](client/email_webhook.md) |
| Telegram bot | allow-listed user IDs | [`client/telegram_bot.py`](client/telegram_bot.py) |

All route to **`POST /capture`** with `{text, source, source_meta,
identity_acknowledged}`.

**Federation (both directions):**

- **`GET /chain/since?seq=N`** — peer pulls our entries past `seq=N`
- **`POST /chain/receive`** — peer pushes their entries to us
- **`concordance fetch [--remote URL]`** — pull, offline-tolerant
- **`concordance push --remote URL`** — push our chain to a peer
- Both idempotent. Receiver stores entries tagged with sender's URL
  (no merge into local chain).

**Witness signatures (Ed25519):**

The BROTHERS gate already requires N witnesses by name. Now they
carry cryptographic teeth.

- **`concordance witness sign <pid> <hash> --name X --role Y --key K`**
- **`concordance witness verify`** (stdin or `--file`)
- **`concordance witness list <pid>`** with verify marks
- **`GET /witness/{precedent_id}`** — public; each attestation
  carries `verified` boolean + `verify_reason`. Well-list UI shows
  the attestation list with ✓/✗ marks.

**Wilderness substrate (LoRa mesh):**

- **`concordance_engine.wire`** — 4-byte tagged binary envelope; pre-
  shared dictionary of 78 common Scripture anchors compresses Mt 5:37
  from 8 bytes to 4. Typical seed: 84 bytes (3.3× JSON compression).
- **`concordance broadcast` CLI** — encode/decode/size.
- **[`client/meshtastic_bridge.py`](client/meshtastic_bridge.py)** —
  drives a Meshtastic radio over USB serial. License-free sub-GHz
  mesh; no internet, no SIM, no government identification required.

**Other substrate channels:**

- **Tor onion service** — [`client/tor_onion.md`](client/tor_onion.md)
- **Nostr publication** — [`client/nostr_publish.py`](client/nostr_publish.py) (kind 30700)
- **IPFS pinning** — [`client/ipfs_pin.py`](client/ipfs_pin.py)
- **Mailing list digest** — [`client/digest_mail.py`](client/digest_mail.py)
- **QR codes** — `concordance qr <id>` emits the URL; phones already
  render QRs via any QR app

**Closest-case overlay on write:**

When a user writes a seed, the engine surfaces the closest already-
walked precedent inline with summary, anchors, and step-by-step
reasoning. Searches both the local ledger AND directories listed in
`CONCORDANCE_PRECEDENT_DIRS` (peer-curated corpora), federating wisdom.

**Operator setup:**

- **`/setup.html`** — checklist with live ✓/○ status per channel
- **`/reach.html`** — public substrate directory; injects operator-
  specific addresses where configured
- **`GET /reach`** — JSON of operator-configured addresses
- See [`OPERATOR.md`](OPERATOR.md) for the full deployment guide

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

### Energy

System-scale power: off-grid sizing, conservation. 8 deterministic checks: power balance (gen − cons − losses), battery sizing (Ah from kWh × days / V·DoD), solar daily yield (panel × PSH × η), wire voltage drop (DC round-trip), kWh ↔ Wh, efficiency (η ≤ 1 unless heat pump COP), runtime (battery_Wh / load_W), peak load vs inverter rating.

Per the kingdom-economy substrate doctrine: those refusing the mark may need off-grid power; this verifier turns napkin arithmetic into deterministic verification.

```json
"ENERGY_VERIFY": {
  "panel_W": 400, "peak_sun_hours": 5.0,
  "system_efficiency": 0.85, "claimed_daily_kwh": 1.7,
  "daily_load_kwh": 5.0, "days_autonomy": 2,
  "depth_of_discharge": 0.5, "system_voltage_V": 24,
  "claimed_battery_Ah": 833.3,
  "battery_wh": 1200, "load_W": 100, "claimed_runtime_hours": 12,
  "peak_load_W": 2400, "inverter_continuous_W": 3000
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
