# Provenance & integration note

**Source:** dropped by Matt 2026-06-15 (`framework_validation_complete.zip`).
PUBLIC DOMAIN framework + MIT pipeline + CDC public-domain data ("Use freely... no
attribution required" -- we attribute anyway, as a matter of the concordance discipline).

**What this is.** The *Nested Control Systems Framework* -- a cited (20 peer-reviewed
references), falsifiable, public-domain mechanistic architecture for chronic disease.
Its thesis: chronic diseases are not separate conditions but different phenotypes of
failures in a 5-layer **nested** control system --

- **L1 Cellular Stress** (HSP/UPR, DNA-damage response, mitophagy, apoptosis-vs-repair)
- **L2 Metabolic Regulation** (insulin/mTOR/AMPK, fuel switching, mitochondrial function)
- **L3 Immune Surveillance** (self/non-self, inflammation resolution, tolerance)
- **L4 Tissue Homeostasis** (structural integrity, angiogenesis, ECM, stem-cell activation)
- **L5 Systemic Coordination** (ANS/vagal brake, HPA axis, circadian gating, allostatic load)

Plus `nhanes_validate.py` / `nhanes_extensions.py`: a **pre-registered FALSIFICATION
pipeline** validating it against NHANES 2011-2018 with a three-outcome verdict
(SUPPORTED / FALSIFIED / INCONCLUSIVE), causal/mediation/manifold/simulation extensions,
and explicit falsifiers per hypothesis (H1 mortality manifold, H2 hyperglycemia
heterogeneity, H3 L5 predictive lift).

**Why it belongs here -- the concordance's scientific / body-systems arm.**

- It *is* the **body-systems map** (see the body-systems memory) done to publication rigor.
- Nested control systems = the **fractal applied to physiology**; the *matrix* view of the
  *organic* body (the two trees, concording not competing).
- Its **claim -> evidence appendix** (`CLM_xxxx` -> a peer-reviewed citation) *is* the
  concordance discipline itself -- every claim bound to its source (vine-validity for
  medical claims).
- DECISION_RULES: *"Truth determines... no hypothesis may be labeled SUPPORTED without
  surviving its full truth-suite"* = the engine's method (crown only the survivor;
  falsifiers stated before the data are seen; honest 3-outcome verdicts).
- **NHANES** = the empirical / inductive grounding the gap analysis named as *the* bottleneck.
- Ties the **Apothecary** (serve the sick) and the **food system** (ultra-processed food ->
  metabolic dysregulation) -- straight into the Acts 2 telos (tie the food system together).

**STATUS / HONESTY.** This is the framework + the validation *pipeline*, **not run
results.** Whether H1/H2/H3 come back SUPPORTED, FALSIFIED, or INCONCLUSIVE depends on an
actual run (auto-downloads CDC NHANES files; needs `pip install -r requirements.txt`).
Do **not** claim the framework is empirically validated until a run emits `summary.json`
verdicts. The framework's own honest gap is documented: NHANES lacks direct L1 markers
(HSP70/72, gamma-H2AX, mitophagy flux, UPR) -- the L1_proxy is an indirect approximation;
true L1 validation needs UK Biobank Olink proteomics.

**Uses (status):**
1. DONE -- ingested the framework's cited claims as 13 ATTRIBUTED almanac entries
   (verdict CONCORDANT-to-literature). See commit 428a58c.
2. TODO -- wire NHANES as a ground source for the health/medicine/nutrition verifiers.
3. DONE (honestly) -- ran the validation pipeline (--mode prereg) on real CDC data
   (39,156 participants). Verdicts: all three INCONCLUSIVE, for DOCUMENTED data-
   availability reasons (no mortality linkage for H1; hs-CRP absent 2011-2014 -> L3
   empty -> H2/H3). NOT a falsification or validation -- the rubric correctly refused
   to over-claim. Required a downloader URL fix (CDC 2024 reorg). Full writeup +
   follow-ups in VALIDATION_NOTE.md.
