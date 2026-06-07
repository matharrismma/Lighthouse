# Dispatch spec drift — the deterministic-coverage backlog

The deterministic dispatcher (`src/concordance_engine/agent/dispatch.py`) routes
a matched natural-language claim to a `(domain, spec)` with **no oracle call**.
An audit on 2026-06-06 drove every rule's own extractor through its verifier and
found:

- **43 rules verify cleanly** — the rule fires and the verifier returns a real
  verdict (CONFIRMED/MISMATCH). Zero-oracle and correct.
- **~33 rules drift** — the rule fires, but the verifier returns only
  NOT_APPLICABLE / ERROR, because the rule's spec keys no longer match what the
  verifier reads. Example: `phys_force` emits `{mass_kg, acceleration_ms2}`, but
  `verify_physics` doesn't read those keys → silent NOT_APPLICABLE.

## Why it mattered (now fixed systemically)
Deterministic-first dispatch would route these claims to a verifier that can't
use the spec → the claim comes back **unverified**, when the oracle would have
classified it correctly. A silent false-negative — the worst kind for a floor.

**Systemic fix (shipped 2026-06-06):** `poly_agent._rule_dispatch_verifies()`.
Deterministic-first now trusts a rule **only when its verifier returns a real
verdict**; a drifted rule transparently falls through to the oracle. The drift
is therefore non-harmful, and any *future* drift self-heals to the oracle.

## The backlog (incremental floor-widening)
Each drifted rule, once its extractor's spec is reconciled to the verifier's
expected keys, moves a class of claims from **oracle → deterministic** — which
lowers the oracle-dependence ratio (`/innovation`). This is steady, low-risk
floor work.

**Method per rule:** feed it a *realistic* example (not a generated one — some
ERROR entries below are test-noise from random generated input, not true
drift), capture the spec it produces, read the verifier's `spec.get(...)` keys,
and align the extractor's keys to the verifier. Re-run the audit to confirm it
flips to a real verdict.

### Likely real drift (verifier returned NOT_APPLICABLE on sane input)
phys_force, phys_ke, nutr_calories, acous_wave_relation, acous_harmonic,
geo_haversine, geo_mohs, geo_richter, info_entropy, met_dew_point,
mus_interval_semitones, num_prime, opt_thin_lens, elec_ohms_law, fin_compound,
fin_accounting_identity, energy_solar_yield, sport_pythagorean, sport_elo,
mfg_cpk, agri_hardiness_zone, logic_tautology, logic_satisfiable,
bio_hardy_weinberg, gen_codon, chem_balance (returned no checks)

### Needs confirmation (ERROR — may be generated-input noise, not real drift)
cyber_subnet, cal_day_of_week, comb_choose, comb_permute, gen_complement,
info_hamming, net_subnet_hosts, net_cidr_member

## Re-run the audit
The audit is ad-hoc (uses `exrex` to generate matching examples). To reproduce:
drive each `dispatch._RULES` entry's extractor on a matching example, call
`ALL_TOOLS["verify_{domain}"]` with `_run_cluster`'s calling convention, and
flag any rule whose `checks[]` contains no CONFIRMED/MISMATCH status.
