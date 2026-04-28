# Nested Control Systems Framework — NHANES Validation Pipeline

Pre-registered falsification study with causal, manifold, and mediation extensions.

## Quick Start

```bash
pip install -r requirements.txt

# 1. Base validation (correlational falsification)
python nhanes_validate.py --mode prereg       # locked, unweighted
python nhanes_validate.py --mode sensitivity  # + survey weights
python nhanes_validate.py --mode full         # + design bootstrap

# 2. Extensions (causal + mechanistic)
python nhanes_extensions.py --extensions all
python nhanes_extensions.py --extensions e7 --sim-reps 500   # simulations only
python nhanes_extensions.py --extensions e1,e6               # causal + mediation
```

## Architecture

```
nhanes_validate.py          v3.1 base pipeline (1483 lines)
nhanes_extensions.py        v3.1 extensions (2075 lines)
ANALYSIS_PLAN.md            Pre-registered definitions (frozen)
DECISION_RULES.md           Three-outcome verdict rubric
EXTENSIONS_PLAN.md          Extension roadmap + dependency map
CHANGELOG.md                Version history
requirements.txt            Python dependencies
```

## Hypotheses

| ID | Claim | Falsifier |
|----|-------|-----------|
| H1 | Upstream manifold predicts 10y mortality | AUC < 0.60 OR delta <= 0 |
| H2 | Hyperglycemia clusters by mechanism | k < 2 OR med p > 0.05 OR ARI < 0.40 |
| H3 | Layer 5 adds predictive lift for diabetes | delta < 0.01 OR negative in any cycle |

## Extensions

| ID | Module | What it adds |
|----|--------|-------------|
| E1 | Causal inference | IPW, g-computation, negative controls |
| E2 | Survival analysis | KM curves, hazard by layer |
| E3 | Biomarker hooks | HOMA-IR, GGT, adipokines, vitamins |
| E4 | External cohorts | UK Biobank, All of Us adapters |
| E5 | Manifold learning | Factor analysis, UMAP, autoencoder |
| E6 | Mediation | ACME/ADE with bootstrap CIs |
| E7 | Simulations | Power/FPR calibration (true/null/reverse) |
| E8 | Subgroups | Discordance profiles, interaction tests |
| E9 | Registered report | Replication package, Dockerfile |

## Decision Rubric

- **SUPPORTED**: Primary prereg passes + sensitivity/stability aligned
- **FALSIFIED**: Primary prereg fails + sensitivity does not rescue
- **INCONCLUSIVE**: Insufficient data, unstable, or conflicting signals

## L1 (Cellular Stress): Proxy Composite + Validation Gap

The theoretical framework specifies five layers (L1–L5). The pre-registered
hypotheses (H1/H2/H3) are specified entirely within the L2–L5 measurable
domain — this is by design, not a gap.

**What's implemented (E3 extension):** An `L1_proxy` composite using five
NHANES-available downstream stress markers: RDW, GGT, ALT, uric acid, and
ferritin (min-obs 3 of 5). This is an *indirect* approximation — it captures
consequences of cellular stress, not the mechanism itself.

**What remains a true gap:** Direct L1 markers — HSP70/72, γ-H2AX (DNA
damage), mitophagy flux, UPR activation — are not in NHANES. The L1 proxy
does not test the framework's mechanistic L1 claims.

**True L1 validation path:** UK Biobank Olink proteomics contains HSP family
members; the E4 UK Biobank adapter is the recommended next step. Alternatively,
CALERIE or InCHIANTI for oxidative stress markers (8-isoprostanes). See
EXTENSIONS_PLAN E3 and E4.

NHANES 2011-2018 public-use files download automatically from CDC.
Optional: place linked_mortality.csv in nhanes_data/ for H1.

## License

Code: MIT. Data: Public domain (CDC/NCHS).
