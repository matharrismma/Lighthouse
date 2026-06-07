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

## Floor pass 2026-06-07 (REALISTIC-example audit, not generated)
Lesson confirmed: the generated-input audit overstates drift. A realistic-example
pass found the real issues:
- **FALSE-CONFIRM killed (correctness):** `ling_strongs` matched "C4 to G4 is 7
  semitones" ("G4" is a Strong's number) and *confirmed* a lexicon lookup for a
  music claim. Fixed: it now requires genuine Strong's context (keyword / quoted
  gloss / WORD gloss — never a bare number).
- **`mus_interval_semitones`:** added a note-pair branch (note_a/note_b/
  claimed_semitones — the keys the verifier reads) so note-interval claims verify
  (CONFIRMED/MISMATCH); fixed the interval-name path to emit `claimed_interval`
  (was the unread `interval_name`).
- **`nutr_calories` reconciled:** emitted `claimed_protein_calories`/`carbs_g`
  (unread) and *computed* the calories (circular). Now extracts the CLAIMED
  calories + emits `calories_claimed`+`carb_g`/`protein_g`/`fat_g` → real verdict.
- **Decoy audit CLEAN:** 12 trap inputs (stray G/H codes, numbers, refs, a recipe,
  a prayer) → 0 false-confirms. The dispatcher correctly declines non-claims.

### Widen batch (2026-06-07, verified + decoy-clean)
6 rules moved oracle -> deterministic. Method: the trigger was too rigid while
the extractor re-validates, so broaden the trigger (over-trigger -> extractor
None / verifier NA — safe), then verify CONFIRMED+MISMATCH and re-run the decoy
audit:
- **num_prime** — "is 17 a prime number?" (both phrasings now).
- **comb_choose** — "N choose K is M" (not just "= M").
- **acous_harmonic** — harmonic + Hz any order.
- **fin_compound** — drop the required literal "interest".
- **elec_ohms_law** — order-independent (lookahead trigger) + extractor word-
  boundary fix. Verifier `verify_ohms_law` reads voltage_V/current_A/resistance_ohm
  (keys already matched; only the trigger drifted).
- **met_dew_point** — lookahead trigger + bare-temp extraction (no "temperature"
  word needed). CONFIRMED 25C/60%->16.7C; MISMATCH on a wrong dew point.

Decoy audits after each batch: 0 false-confirms.

### Still open
- **chem_balance** — emits `{equation}`; `verify_equation(eq, ...)` takes the eq
  string. Need to confirm the MCP `verify_chemistry` wrapper routes `spec["equation"]`
  -> verify_equation (the NA suggests a wrapper key mismatch). Check
  `mcp_server/tools.py`.
- **phys_force** — DEAD: verify_physics does dimensional / conservation / kinematics,
  but no numeric F=ma magnitude check. Harmless NA -> oracle; candidate for removal.
- **geo_mohs** — works for "X scratches Y"; "X (Mohs n) is harder than Y (Mohs m)"
  not handled (coverage). **geo_richter** — fine for ratio claims (not drifted).
- Remaining backlog domains untested this pass: phys_ke, geo_haversine, info_entropy,
  sport_*, mfg_cpk, agri_hardiness_zone, logic_*, bio_hardy_weinberg, gen_codon.
  Same method; decoy-audit each widen.
