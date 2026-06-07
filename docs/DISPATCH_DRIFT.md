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

### Widen + reconcile batch 2 (2026-06-07, verified + decoy-clean)
Same method, plus one genuine correctness fix. All keys were already aligned to
the verifier; the failures were trigger-too-narrow (NO_MATCH) or a normalization
mismatch. 5 rules moved oracle -> deterministic:
- **gen_codon (REAL HARMFUL DRIFT FIXED):** `verify_genetics` translates on DNA
  (rejects RNA `U` as ERROR) and reports **single-letter** codes, so a *true*
  claim ("codon AUG codes for Methionine") came back ERROR/MISMATCH. The
  extractor now normalizes RNA->DNA (`U`->`T`, coding-strand equivalence) and maps
  amino-acid names / 3-letter / single-letter -> the single letter the verifier
  emits (`_AA_TO_LETTER`/`_AA_SINGLE`). Guard: a bare lowercase single letter
  ("...for a protein") is NOT treated as a code. CONFIRMED on AUG/ATG x name/Met/M;
  MISMATCH on a wrong AA; NO_MATCH on codon-prose.
- **info_entropy:** keys matched, verifier CONFIRMS; only the trigger was rigid.
  Now `(?=.*entropy)(?=.*bits)` (any order). The extractor still requires explicit
  decimal probabilities (`0.\d+`), so entropy-prose without probs -> None (safe).
- **geo_haversine:** keys matched, verifier CONFIRMS. New trigger fires on a
  decimal `lat, lon` pair + km. Extractor rewritten to read explicit coordinate
  PAIRS (order-independent; ignores the distance number) and the N/S/E/W fallback
  now REQUIRES the hemisphere letter (was optional -> grabbed stray numbers).
  Decoys (recipe "2.5, 1.5 cups", "drove 300 km") correctly NO_MATCH.
- **cal_day_of_week (coverage):** matched "is a <day>" but not the dominant
  historical phrasing **"was a / fell on a <day>"**. Connector widened; extractor
  re-derives date+day independently (safe). CONFIRMED/MISMATCH both verified.
- **comb_permute (dead branch fixed):** the natural-language trigger branch existed
  but the extractor only handled `P(n,k)` notation, so "permutations of 5 taken 2
  is 20" triggered then returned None -> NO_MATCH. Added the natural-language
  extractor branch + `is`/`equals` connector. CONFIRMED/MISMATCH verified; P(n,k)
  still works.

Decoy audit after the batch: 0 false-confirms. (Two inputs in the trap list were
actually TRUE claims — "Strong G2316 is theos" and "C4 to G4 is 7 semitones" —
correctly CONFIRMED by ling_strongs / mus_interval_semitones; not false-confirms.)

### Reconcile batch 3 (2026-06-07) — a SYSTEMIC gate fix + 3 rules + 2 dead confirmed
**Systemic (the big one): the gate couldn't read a whole class of verifier
output.** `_rule_dispatch_verifies` (poly_agent.py) only recognized a real verdict
in `checks[]`, `results[]`, or a top-level `status`. But some verifiers return
per-aspect verdicts as dict VALUES — e.g. `verify_chemistry` -> `{"equation":
{"status": ...}}`. The gate saw no verdict there and **leaked every such claim to
the oracle even though a deterministic verdict existed**. Fix: the gate now also
recognizes `CONFIRMED`/`MISMATCH` in any dict value. Additive + safe (only ever
recognizes MORE real verdicts, never fewer). This un-leaks chemistry and any other
nested-shape verifier at once.
- **chem_balance (REAL HARMFUL DRIFT FIXED + un-leaked):** two bugs. (1) The old
  trigger `(.+?)(?:->|...)` truncated the equation at the FIRST arrow -> only the
  LHS. (2) Even fixed, capturing the surrounding prose ("Is ... balanced") made the
  atom-counter read "Is"/"is" as ELEMENTS -> a *balanced* equation came back
  MISMATCH (false negative on a true claim). New `_CHEM_EQ` regex captures only the
  `LHS -> RHS` species (coefficients + element/paren groups), guarded by a real-
  formula check. Verified: balanced -> CONFIRMED, unbalanced -> MISMATCH; decoys
  ("Team A -> Team B ... balanced", "step 1 -> step 2 ... reaction") NO_MATCH.
- **mfg_cpk:** extractor keys already correct (`process_mean`/`process_sigma`/
  `claimed_cp_capable`); only the trigger drifted (required Cpk-before-USL-before-
  LSL order). New order-independent lookahead trigger requiring USL+LSL+mean+sigma
  +a capability claim (so we never assert a capability the user didn't state).
  CONFIRMED verified.
- **agri_hardiness_zone:** verifier's reference table covers tomato/wheat/corn/
  apple/peach/strawberry/blueberry/soybean/cotton (CONFIRMS). Trigger widened to
  any "hardiness zone N" mention (extractor re-finds zone+crop) + "grows/thrives/
  hardy/cultivated in zone N" with up to 2 filler words; `maize`->`corn`. Crops not
  in the table (avocado/orange/grape) correctly NO_MATCH -> oracle.

**Confirmed DEAD (mark for removal; harmless NA/ERROR -> oracle):**
- **phys_ke** — DEAD: verify_physics recognizes kinematics (v0/a/t/displacement) +
  conservation, but has no kinetic-energy magnitude check. Like phys_force.
- **bio_hardy_weinberg** — DEAD: verify_biology's biology check is an integer-count
  chi-square (observed/expected); it has no Hardy-Weinberg p^2+2pq+q^2 check and
  ERRORs on allele frequencies. The rule emits a nested `{hardy_weinberg:{...}}`
  the verifier never reads.

Decoy audit after batch 3 (16 traps incl. the systemic-gate-relevant ones):
0 false-confirms.

### Still open
- **phys_force / phys_ke / bio_hardy_weinberg** — DEAD (no matching numeric check
  in the target verifier). Harmless (gate -> oracle); removal candidates. Leave
  until a numeric F=ma / KE / HW check exists, or delete the rules.
- **geo_mohs** — works for "X scratches Y"; "X (Mohs n) is harder than Y (Mohs m)"
  not handled (coverage). **geo_richter** — fine for ratio claims (not drifted).
- **logic_tautology / logic_satisfiable** — keys match + verifier CONFIRMS on the
  `>>`/`&`/`|`/`~` notation, but the trigger only fires on that exact notation.
  Widening to natural connectives ("P AND Q", "P -> Q", "implies") is higher-risk
  (prose "A and B" is everywhere); needs a careful normalize step. Low corpus
  frequency -> deferred, not dead.
- **sport_pythagorean** — keys match + verifier CONFIRMS, but the extractor needs
  "N runs scored ... N runs allowed ... win pct" in that order/phrasing. Niche;
  coverage-only.

### Reconcile batch 4 (2026-06-07) — signature-shape drift (the third drift class)
A third class beyond key-drift and trigger-rigidity: the verifier takes **named
params with a specific shape**, and the rule's flat spec doesn't fit. Found via
the nested-shape sweep (verify_mathematics / verify_computer_science).
- **math_derivative (FIXED):** `verify_mathematics(mode, params)` — derivative mode
  reads `params["function"]` + `params["claimed_derivative"]`. The rule emitted a
  flat `{expression, claimed_derivative}` -> TypeError (missing `mode`) -> leaked.
  Reshaped to `{mode:"derivative", params:{function, claimed_derivative, variable}}`
  + normalize for sympy ('^'->'**', implicit-mult "2x"->"2*x") + `\bis\b` word
  boundary (was matching "is" inside "his"). CONFIRMED on x^2=2x / sin(x)=cos(x) /
  3x^2=6x; MISMATCH on x^3=2x; junk expressions -> NOT_APPLICABLE (leak, harmless).
- **math_quadratic — left as-is:** "solve 1x^2+5x+6" is a *request* with no claimed
  roots, so there is nothing to verify (solve mode needs `claimed_solutions`). Not
  drift; would need a redesign to capture a claimed answer.
- **cs_complexity / cs_bit_ops — DEAD:** `verify_computer_science(code, ...)`
  benchmarks RUNNABLE code; it cannot verify "merge sort is O(n log n)" from an
  algorithm name, and has no bit-shift arithmetic check. Removal candidates.

The nested-shape sweep also confirmed: 5 verifiers use the `out[]` dict-value
shape (chemistry, computer_science, governance_decision_packet, mathematics,
statistics); 6 use a bare `_r()` top-level `status` (already handled); 58 use
`checks[]`. The batch-3 gate fix covers the nested 5.

Decoy audit after batch 4: 0 false-confirms.

DONE (batch 2, 2026-06-07): gen_codon, info_entropy, geo_haversine,
cal_day_of_week (was/fell-on), comb_permute (natural-language).
DONE (batch 3, 2026-06-07): SYSTEMIC gate value-dict fix, chem_balance, mfg_cpk,
agri_hardiness_zone; phys_ke + bio_hardy_weinberg confirmed DEAD.
DONE (batch 4, 2026-06-07): math_derivative (mode/params reshape); cs_complexity +
cs_bit_ops confirmed DEAD (code-benchmark verifier, name-only claim).
