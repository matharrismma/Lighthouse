# Walkthrough: Your First Verified Packet

This document takes you from zero to a packet that the engine validates AND verifies. It assumes you have Python 3.10+ and the package installed.

```bash
# from the repository root
pip install -e ".[dev]"
```

That installs `sympy`, `numpy`, `scipy`, and `jsonschema`. The verifier layer needs the first three. The CLI runs without `jsonschema` but with reduced schema validation.

## The shape of a packet

A packet is a JSON object. The minimum a packet needs is:

```json
{
  "domain": "chemistry",
  "scope": "adapter",
  "created_epoch": 1700000000
}
```

`domain` routes to a validator. `scope` (adapter/mesh/canon) determines the GOD-gate wait window (1 hour / 24 hours / 7 days). `created_epoch` is when the packet was created — the GOD gate checks elapsed time from this stamp.

Without anything else, this packet PASSes if you give it enough wall-clock time, because the validators have nothing to reject and there are no witness or wait requirements. That's not interesting. We want to actually check something.

## Adding attestation

The chemistry validator looks at `CHEM_RED` and `CHEM_SETUP`:

```json
{
  "domain": "chemistry",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "CHEM_RED": {
    "mass_conserved": true,
    "charge_balanced": true,
    "elements_consistent": true,
    "phases_specified": true
  },
  "CHEM_SETUP": {
    "reagents": ["C3H8", "O2"],
    "products": ["CO2", "H2O"],
    "temperature_K": 298.15,
    "phase": "gas"
  }
}
```

This passes RED (the author has affirmed conservation, charge balance, etc.) and FLOOR (CHEM_SETUP is present and nothing is contradicted). But notice: the engine has no way to know whether the author's affirmations are correct. It's a checklist.

## Adding verification

Now we add `CHEM_VERIFY`:

```json
{
  "domain": "chemistry",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "CHEM_RED": {
    "mass_conserved": true,
    "charge_balanced": true,
    "elements_consistent": true,
    "phases_specified": true
  },
  "CHEM_SETUP": {
    "reagents": ["C3H8", "O2"],
    "products": ["CO2", "H2O"],
    "temperature_K": 298.15
  },
  "CHEM_VERIFY": {
    "equation": "C3H8 + 5 O2 -> 3 CO2 + 4 H2O",
    "temperature_K": 298.15
  }
}
```

The verifier parses the equation, counts atoms on each side, checks charge balance, and verifies your stated coefficients balance. Save this as `propane.json` and run:

```bash
PYTHONPATH=src python -m concordance_engine.cli validate propane.json --now-epoch 9999999999
```

The `--now-epoch` flag lets the GOD-gate wait window pass instantly for testing. In production the engine uses real time.

You should see `"overall": "PASS"`. Now break the equation. Change `5 O2` to `4 O2` and re-run. The verifier rejects with:

```
unbalanced under stated coefficients but balances as: C3H8 + 5 O2 -> 3 CO2 + 4 H2O
```

That's the engine telling you what the correct coefficients are. Useful when balancing by hand.

Same for charge — try the redox reaction:

```json
"CHEM_VERIFY": {
  "equation": "MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O"
}
```

PASSes. The parser handles formula nesting (Cu(OH)₂), charge tags (Fe^2+, MnO4^-), and ionic dissolution.

## Cross-domain: the same idea in other languages

The engine has the same shape for every domain. Open these examples and see:

```bash
ls examples/sample_packet_*verify.json
```

- `sample_packet_chemistry_verify.json` — propane combustion
- `sample_packet_physics_verify.json` — F = ma dimensional check
- `sample_packet_math_verify.json` — symbolic equality
- `sample_packet_statistics_verify.json` — Welch's t-test recomputation
- `sample_packet_cs_verify.json` — Python function with test cases
- `sample_packet_cs_runtime_verify.json` — bubble sort O(n²) measured
- `sample_packet_biology_verify.json` — replicates + dose-response + power
- `sample_packet_governance_verify.json` — Hutcheson workforce-development RFP

Each has the same skeleton: domain, scope, created_epoch, the attestation block(s), and the *_VERIFY block. The verifier knows what to check based on which fields are present.

Run them all:

```bash
for f in examples/sample_packet_*verify.json; do
  echo "=== $f ==="
  PYTHONPATH=src python -m concordance_engine.cli validate "$f" --now-epoch 9999999999 | python -c "import json,sys; d=json.load(sys.stdin); print(d['overall'])"
done
```

All eight PASS. Corrupt any of them — change the units in the physics equation, alter the claimed p-value, claim O(n) for bubble sort, drop a witness from the governance packet — and you'll see the failure mode unique to that domain.

## Writing your own packet

Pick a domain. Look at the example. Copy it. Replace the contents with your case. Run.

If you're writing a math claim, what does your equation look like in sympy syntax?
- `(x+1)**2` not `(x+1)^2`
- `sin(x)` not `sin x`
- `1/(1+x**2)` not `\\frac{1}{1+x^2}`

If you're writing a physics equation, what units are involved?
- Use names sympy understands: `newton`, `kilogram`, `meter/second**2`. Or compose: `kilogram*meter**2/second**3` for watts.

If you're writing a stats claim, what test produced the p-value?
- Specify `test`: `two_sample_t`, `one_sample_t`, `z`, `chi2`, `f`. The fields needed depend on the test. See README.md.

If you're writing a governance decision, fill in every required field of `DECISION_PACKET`. The verifier rejects an empty packet on structural grounds. That's intentional — a decision without explicit RED items, FLOOR items, witnesses, and an executable path isn't a decision yet.

## What PASS means

PASS does not mean "Claude approved it." PASS means:

1. RED attestation gates passed (no forbidden categories declared violated)
2. RED computational verifiers passed (the artifacts you supplied actually hold up)
3. FLOOR gates passed (protective constraints satisfied)
4. BROTHERS gate passed (witness count threshold met, if required_witnesses > 0)
5. GOD gate passed (elapsed time since created_epoch ≥ wait window for this scope)

Notice what PASS does NOT mean:
- It does not mean the decision is wise. The verifiers check math, not wisdom.
- It does not mean the witnesses agree on the substance. They were counted, not surveyed.
- It does not mean the framework approves. It means the structural constraints were met.

The framework's job is to slow you down and make you write things down. The judgement is yours.

## Common rejections

- **MISMATCH from a verifier** — the artifact contradicts the claim. Fix the artifact or the claim.
- **REJECT on RED from a domain validator** — an attestation flag is False where the canon requires True. Look at the failure detail; it names the flag and cites the scriptural anchor where applicable.
- **REJECT on FLOOR** — protective constraints declared violated, or required FLOOR fields missing.
- **QUARANTINE on BROTHERS** — witness count below required threshold. Wait for more witnesses.
- **QUARANTINE on GOD** — wait window not yet elapsed. Adapter scope is 1 hour, mesh is 24 hours, canon is 7 days.

## Next

Read `verifiers/README.md` for the developer side — how to add a new verifier, what the result types mean, and what constraints apply (no network, no untrusted input, deterministic except runtime measurement).

Read `tests/test_engine.py` for the full set of cases the engine handles. The negation tests at the end show how the governance scanner handles "we will not exploit" vs "we exploit" correctly.

Read `08_docs/the_mechanism.pdf` for the honest analysis of what's real and what's not yet real in the broader framework.
