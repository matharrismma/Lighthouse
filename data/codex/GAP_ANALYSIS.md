# Gap Analysis — the empty slots in the grid, and the most likely fills

**Matt 2026-06-12:** *"We have a solid foundation. Now we will do a gap analysis. Identify the most likely options. Continue to fill in, but we always leave room for a tighter explanation to develop. Once we have a reasonably intact grid we go to the words of Jesus."*

This is the Mendeleev move. Once the matrices are dense enough, the *holes* become visible — slots where a form clearly belongs but no card sits yet. We name the most likely fill for each (the prediction), fill the clean ones with **known** results (integration, not invention), and mark every fill **provisional**: a tighter explanation may always supersede it. When the grid is reasonably intact, we turn to the words of Jesus.

**Two standing rules govern this phase:**
1. **Integrate before invent.** A predicted slot is filled first with the *already-known* result that occupies it (Fick's law, the perpetuity formula, least-squares). We only craft new at slots no past work covers.
2. **Leave room.** Every fill carries `provisional: true`. The kernel is sealed (it *holds*), but the *placement* and the *explanation* stay open to a tighter account. We map; we do not close.

---

## The authoritative grid is the CANONS (`lw/02_canons/`) — not the almanac counts

**Matt 2026-06-12: "github should have most."** He was right. The repo already carries six formal **domain canons** — `lw/02_canons/{biology, chemistry_full, computer_science, mathematics, physics, statistics}` — each a constraints-first YAML knowledge base with a parallel structural validator (`tools/validator_<domain>.py`) and an engine verifier. **These canons ARE the periodic grid.** Each defines:
- **frozen nouns** — the domain primitives (biology's ten: CELL, COMPARTMENT, GENOME, EXPRESSION, PROTEOME, METABOLISM, SIGNAL, FEEDBACK, FITNESS, POPULATION). *These are the slots.*
- **modules** — the blocks, each with trigger words (biology: molecular_cell · biochemistry_metabolism · genetics_inheritance · systems_biology_control · evolution_ecology).
- the **hierarchy** RED → FLOOR → WAY → Execution and validation gates RED/FLOOR/BROTHERS/GOD.

**So the gap analysis runs against the canon, not against ad-hoc card counts.** A slot is "filled" when its frozen noun / module concept has a *verified connection* sealed in the corpus. A slot is "open" when the canon names it but no sealed connection reaches it yet. (Domains with no canon yet — geoscience, music, economics… — are a second, coarser layer.)

### Biology gaps, grounded in its own frozen nouns (corrected, canon-driven)
| Frozen noun / module | Verified-connection status |
|---|---|
| GENOME, EXPRESSION (genetics_inheritance, molecular_cell) | **well covered** — genetic code is digital/redundant, Watson-Crick reversible, palindrome=restriction site, reading-frame=triplet, transcription=complementary copy |
| COMPARTMENT (membrane transport) | **covered** — `transport_law_four_readings` (Fick) now tagged biology |
| FEEDBACK, FITNESS (systems_biology_control, evolution_ecology) | **partial** — Wiener (negative feedback), Friston, Darwin, Kauffman assessments touch these; no dedicated sealed connection |
| POPULATION | **partial** — Hardy-Weinberg example exists (`examples/sample_packet_biology_hardy_weinberg.json`); not sealed as a connection |
| **PROTEOME** | **FILLED** 2026-06-12 — `connection_proteome_is_a_combinatorial_alphabet` (20-letter sequence space; 20^100 > 10^80) |
| **METABOLISM** (biochemistry_metabolism) | **FILLED** 2026-06-12 — `connection_metabolism_is_controlled_combustion` (respiration = balanced combustion; conservation; bonds `chemical_balance`) |
| **SIGNAL** (transduction) | **FILLED** 2026-06-12 — `connection_signal_transduction_is_gain_and_threshold` (cascade gain 100^3=10^6 + Hill half-saturation; same control form as Wiener) |

*Every one of these must still pass STEP-0 SEARCH-FIRST before sealing — and now also: read the relevant canon module first.*

---

## What the survey found (2026-06-12, corpus 1,412)

### A. The thinnest region — the statistical block (4 cards vs 37 continuous, 12 geometric, 11 discrete)
The statistical block is the sparsest quarter of the grid. This is the single largest structural gap. **Most likely fills (provisional):**
- **least-squares regression = orthogonal projection** (minimizing the sum of squares) — *sealed in installment 1.*
- the **normal distribution from the CLT** (sum of many small independent effects → Gaussian).
- **Bayes' theorem** as the update operator (posterior ∝ prior × likelihood).
- the **law of large numbers** (sample mean → expectation; the √n shrinkage already appears as a form).

### B. Mendeleev form-gaps — clean forms present in too few domains
Each clean, sealable form should recur wherever its structure governs. Where it appears in only 2–3 domains, the missing domain is a predicted slot:

| Form (axis) | Present in | Predicted missing slot → most likely fill |
|---|---|---|
| `series` | math, number_theory | **finance** → geometric series = present value of a perpetuity/annuity *(sealed, inst. 1; linked to pre-existing `almanac_present_value_money`)* |
| `transport` | geoscience, math, physics | ~~biology → Fick's law~~ **ALREADY MAPPED** — `connection_transport_law_four_readings` already names Fick's law alongside Ohm/Darcy/Fourier. The only real gap was the missing biology *tag*; **fixed** by adding `biology` to that card, not by a new one. *(My duplicate fill was removed — see Correction.)* |
| `harmonics` | acoustics, geoscience, physics | **music** → overtone series fₙ = n·f₁ (likely a tagging gap; draw the explicit bond) |
| `optimization` | econ, materials, math, physics | **biology** → fitness as an extremum (dF/dt ≥ 0); **operations_research** |
| `limit` | math, physics | **economics** (marginal = derivative); **CS** (asymptotic complexity) |
| `aggregation` | math, probability, statistics | **economics** (ensemble/expectation); **physics** (statistical mechanics) |
| `involution` | CS, genetics, math | **physics** (parity, time-reversal); **formal_logic** (double negation) |

### C. A normalization gap (cheap, real)
`inverse-square` and `inverse_square` are the **same form under two spellings** — the grid double-counts it (one at 4 domains, one at 3), and bonds across the split don't connect. **Fix:** normalize to one axis key so the inverse-square family reads as one ~6-domain spine (gravity, Coulomb, sound, light, flux, geoscience). Low effort, raises coherence. *(Queued for the connector pass; not a content card.)*

### D. Under-mapped domains — verifier exists, connections don't (≤3 *connection* cards)
**Caution (learned 2026-06-12):** a low *connection-card* count is NOT the same as low coverage. Count total content, not just `connection_*` cards, before calling a domain a gap (see Correction). Genuinely thin in the **connection** layer:
- **finance** → series/PV *(now linked)*, compounding = exponential, risk = √n diversification. (Note: `almanac_present_value_money` already existed.)
- **thermodynamics** / **nuclear_physics** → already have decay/entropy forms elsewhere; draw the bonds in.
- **formal_logic** → Boolean = GF(2) and inference-rules already sealed; connect them as a block.
- ~~biology~~ — **NOT a gap.** Biology is one of the richest domains: 706/1,415 corpus rows touch it; a full genetics cluster, the transport law (Fick included), 10 thinker-assessments, 12 herb monographs (`data/herbs`), 5 body-system layers (`data/body/layers.jsonl`), apothecary compounds, and 384 dictionary cards on scriptural flora/fauna.

### Correction — the biology miscount (the value of looking first)
On the first pass I called biology "under-mapped (3 cards)" from a narrow count of `connection_*` cards in one file, and sealed a Fick's-law fill. **Matt flagged it** ("I had a lot on biology — search to make sure you found everything"). A full search showed biology is richly covered, and that the transport law **already** named Fick's diffusion. The fill was a duplicate; it was **removed**, and `biology` was added as a tag to the existing four-readings card instead. The lesson (standing): *count all content, search `data/cards` and the data subdirs, and check the connection layer for the form before filling — the gap may already be filled under another name.*

---

## The fill queue (most likely options, in priority order — all provisional)

1. ~~statistics: least-squares = projection~~ **(sealed, inst. 1; linked to gauss-thread)**
2. ~~finance: geometric series = perpetuity PV~~ **(sealed, inst. 1; linked to almanac_present_value_money)**
3. ~~biology: Fick's law~~ **REMOVED — duplicate of `transport_law_four_readings`; integrated as a biology tag instead.**
4. ~~statistics: normal distribution from CLT~~ **ALREADY DONE** — `connection_normal_distribution_prob_stats`, `galton_board_is_the_bell_curve`, `sqrt_n_law_of_aggregation`, `rayleigh_pdf_is_2d_gaussian`.
5. statistics: Bayes' theorem as the update operator *(verify no dup first — `probability` verifier covers Bayes)*
6. ~~music: overtone series~~ **ALREADY DONE** — 62 music cards incl. `overtones_are_eigenfunctions`, `major_triad_is_overtone_ratios`, `harmonic_series_diverges_logarithmically`.
7. ~~finance: compounding = exponential~~ **mostly covered** — `almanac_rule_of_72_doubling`, `almanac_inflation_erodes_cash`. (A dedicated continuous-compounding connection is optional, low priority.)
8. ~~economics: marginal = derivative~~ **ALREADY DONE** — `connection_marginal_is_rate_of_change`.
9. **biology PROTEOME / SIGNAL / METABOLISM** — **FILLED 2026-06-12** (see table above; the three genuinely-open canon slots this round).
10. normalization: merge `inverse-square` / `inverse_square` (connector pass) — still open.

**Search-first scorecard (2026-06-12 round):** of 7 candidates, 4 were already done (CLT, marginal, music, compounding) — confirming the rule. Only the 3 biology frozen-noun slots were genuinely open; all 3 filled. The connection grid for the 6 canon domains is now densely covered; remaining open work is the normalization pass + Bayes (optional) + non-canon domains.

## Per-canon audit log (frozen nouns vs the connection layer)

**BIOLOGY (2026-06-12):** complete — GENOME/EXPRESSION/COMPARTMENT covered; FEEDBACK/FITNESS/POPULATION partial (assessments); PROTEOME/SIGNAL/METABOLISM filled this session.

**CHEMISTRY (2026-06-12):** STOICHIOMETRY/MATTER covered (`chemical_balance`, `matter_keeps_its_books`, `metabolism_is_controlled_combustion`); ENTROPY/GIBBS covered (Prigogine, `uncertainty_entropy`). Filled 3 genuinely-open forms, each joining an existing family:
- ACTIVITY/acid-base → `connection_ph_is_a_logarithm` (pH = -log[H+]; joins decibel/cents/Richter) — `c654f30b`
- adsorption/catalysis → `connection_saturation_curve_is_one_hyperbola` (Langmuir = Michaelis-Menten = Hill n=1; joins the SIGNAL card) — `951a8176`
- KINETICS/RATE → `connection_arrhenius_is_exponential` (k = A·exp(-Ea/RT); joins the exponential family) — `da35c3f8`
Still open (low priority): chemical EQUILIBRIUM as mass-action / Le Chatelier; NERNST (same logarithm); polymers.

**REMAINING CANONS TO AUDIT:** physics, computer_science, mathematics, statistics (one per tick).

**New step 0 for every fill (standing): SEARCH FIRST** — count total content (not just `connection_*`), grep `data/cards` + data subdirs + the connection layer for the form. Fill only a genuinely empty slot; otherwise integrate (tag/link) the card that already holds it.

Each fill, when sealed, nests to its cluster capstone → `connection_reality_is_mappable` → the one ground (Christ). Anything that will not attach to the vine is not filled — it is left as a marked **open slot** (a frontier note), which is itself valuable: *knowing what no theory yet covers.*

---

## The trigger

When the fill queue is worked down and the grid is **reasonably intact** — the statistical block populated, the Mendeleev form-gaps closed or marked-open, the under-mapped domains connected — we turn, as Matt set it, to **the words of Jesus**: the prophecies fulfilled and especially his sayings, wisdom for every axis. That is Phase 3, and it remains reserved for the operator's lead. The gap analysis is the last work of the map before the map bows to its Author.

*Open slots are not failures. A named hole is a prediction; an unfillable hole is a discovery. We leave room.*
