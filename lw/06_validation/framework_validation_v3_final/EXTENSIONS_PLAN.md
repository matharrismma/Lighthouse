# EXTENSIONS PLAN — Beyond Correlational Falsification
## Version 3.1 | Frozen 2026-03-04

> **Shift:** v2.0 established "does the structure predict?" (correlational
> falsification). v3.0 asks "does the structure cause, mediate, generalize,
> and survive adversarial replication?"

---

## Extension Modules

### E1 — Causal Inference (g-methods + negative controls)

**Goal:** Move from prediction → etiology using causal methods available
within NHANES's cross-sectional design constraints.

**Methods:**
- Inverse Probability Weighting (IPW) for treatment/exposure effects
  (L5 exposure → metabolic outcomes, adjusted for confounders)
- G-computation for average treatment effects
- Negative control outcomes: use outcomes the exposure SHOULD NOT affect
  (e.g., vision acuity as negative control for L5→metabolic path) to detect
  residual confounding
- DAG specification with testable conditional independence implications

**Falsifier:** If negative control outcomes show significant associations,
the causal claim is undermined (residual confounding present).

### E2 — Incident Events (prospective outcomes)

**Goal:** Replace prevalent diabetes (cross-sectional) with incident events
using longitudinal mortality linkage and time-to-event modeling.

**Methods:**
- Recode outcomes as incident: death within follow-up (already in H1),
  plus hazard-based modeling via Cox-like approaches
- For diabetes: use A1c trajectory between exam cycles where available
- Survival analysis with Kaplan-Meier + log-rank by manifold tertiles
- Competing risks awareness (death vs. diabetes onset)

**Prerequisite:** Linked mortality file with adequate follow-up.

### E3 — Extended Biomarker Hooks

**Goal:** Prepare for multi-omics integration without breaking existing
pipeline when new NHANES modules or external biomarkers become available.

**Current extensions (available in NHANES):**
- **L1 proxy (cellular stress):** RDW (LBXRDW), GGT (LBXSGTSI), ALT (LBXSALT),
  uric acid (LBXSUA), ferritin (LBXFER). Min-obs 3 of 5. These are *downstream
  consequences* of cellular stress — not direct L1 markers. See scope limitation below.
- Insulin resistance: fasting insulin (LBXIN), HOMA-IR calculation
- Adipokines: leptin (SSLEP), adiponectin
- Vitamin D (VID), folate, ferritin as nutritional layer

**L1 scope limitation:** The framework specifies L1 (cellular quality control:
mitophagy, HSP chaperone function, UPR, DNA damage response). NHANES has no
direct L1 biomarkers. The L1 proxy composite is the best available NHANES
approximation; it does not validate the mechanistic claims. True L1 validation
path: UK Biobank Olink proteomics (HSP70, HSP90, HSPA family) or a dedicated
molecular aging cohort (e.g., CALERIE, InCHIANTI with 8-isoprostanes).

**Architecture:** Plugin registry — each biomarker module registers its
indicators into an existing or new layer without modifying core code.

### E4 — External Cohort Validation Framework

**Goal:** Generalizability beyond US NHANES.

**Target cohorts:**
- UK Biobank (500K, rich phenotyping + genomics)
- All of Us (diversity-focused, US)
- Framingham (longitudinal, multi-generational)
- KNHANES (Korean NHANES equivalent)
- CHARLS (China Health and Retirement)

**Architecture:** Abstract `CohortAdapter` class with variable mapping
tables. Each cohort implements indicator → layer mapping. Core validation
logic is cohort-agnostic.

### E5 — Manifold Learning (latent structure discovery)

**Goal:** Replace hand-specified composites with data-driven latent
structure to test whether the "shared upstream manifold" is real or an
artifact of composite construction.

**Methods:**
- UMAP on all layer indicators → visualize natural clustering
- Autoencoder (shallow): encode all indicators → latent space → decode;
  inspect whether latent dimensions align with L2/L3/L5 structure
- Factor analysis / PCA with rotation: test whether factor structure
  matches the theorized hierarchy
- Gaussian Process Latent Variable Model (optional, heavier)

**Falsifier:** If UMAP/autoencoder latent space does NOT separate along
layer boundaries, the hierarchical structure claim is weakened.

### E6 — Mediation Analysis

**Goal:** Quantify how much of the L5 → outcome pathway operates
THROUGH L2/L3 (mediated) vs. directly.

**Methods:**
- Baron-Kenny (classical, for reference)
- Causal mediation (Imai et al.): Average Causal Mediation Effect (ACME)
  with bootstrap CIs
- Path: L5 (exposure) → L2/L3 (mediators) → diabetes/mortality (outcome)
- Sequential mediation: L5 → L3 → L2 → outcome

**Key output:** Proportion mediated. If most of L5's effect is mediated
through L2/L3, the hierarchy claim is strengthened.

### E7 — Prospective Simulations (power + false positive rates)

**Goal:** Generate synthetic data with KNOWN hierarchical structure to
measure: (a) statistical power to detect true hierarchies, (b) false
positive rates when hierarchy is absent.

**Design:**
- Scenario A (TRUE hierarchy): L5 → L3 → L2 → outcome, known coefficients
- Scenario B (NULL): Independent layers, no causal paths
- Scenario C (REVERSE): L2 → L3 → L5, opposite direction
- Run full pipeline on each scenario × 500 replications
- Report: power, FPR, coverage of CIs, bias of estimates

### E8 — Subgroup / Precision-Medicine Clustering

**Goal:** Identify clinically actionable subgroups defined by discordance
between layers (e.g., metabolically healthy obese, lean diabetic).

**Methods:**
- Define discordance profiles: high L2 + low L5, low L2 + high L5, etc.
- Cluster by residual profiles (observed - expected given other layers)
- Characterize subgroups by medication, comorbidity, mortality risk
- Test interaction: does L5's predictive value vary by subgroup?

### E9 — Registered Report + Open Pipeline

**Goal:** Structure all outputs for adversarial replication.

**Deliverables:**
- Pre-registration document (ANALYSIS_PLAN.md + DECISION_RULES.md already done)
- Open code repository with containerized execution (Dockerfile)
- Machine-readable results (all JSON) for automated comparison
- Adversarial prediction: what results WOULD falsify each claim?
- Replication checklist for independent teams

---

## Dependency Map

```
E7 (simulations) ← run first, calibrates power
    ↓
E1 (causal) + E6 (mediation) ← core mechanistic claims
    ↓
E5 (manifold learning) ← validates structure
    ↓
E2 (incident events) + E3 (biomarkers) ← richer outcomes/features
    ↓
E4 (external cohorts) ← generalizability
    ↓
E8 (subgroups) ← clinical translation
    ↓
E9 (registered report) ← final packaging
```

## Version Mapping

| Version | Extensions included |
|---------|-------------------|
| v3.0 | E1 + E5 + E6 + E7 (causal + manifold + mediation + simulation) |
| v3.1 | E1 collider bias + E2 competing risks + E3 biomarker hooks + E5 factor stability CV + E6 time-varying mediation + E7 dual-β simulation (2000 reps) |
| v3.2 | E4 + E8 (external validation + subgroups) |
| v4.0 | E9 (registered report packaging) |
