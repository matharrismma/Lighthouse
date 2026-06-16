# Validation run -- honest verdicts (2026-06-15)

Ran `nhanes_validate.py --mode prereg` on **real CDC NHANES 2011-2018 data**
(39,156 participants processed, 67/72 module files downloaded).

**Downloader fix required first (I/O only, analysis untouched).** CDC's 2024 site
reorg had moved the data files; the pipeline's hardcoded URLs returned HTTP-200
HTML "Page Not Found" pages, so the *first* run silently ingested garbage. Patched
`xpt_url` -> the current path `Nchs/Data/Nhanes/Public/{beginyear}/DataFiles/{file}.xpt`
and added a guard in `_download` that only saves genuine SAS-transport files (checks
the `HEADER RECORD` signature) so a soft-404 can never poison a run again. These are
download-source / robustness changes; the pre-registered analysis definitions in
ANALYSIS_PLAN.md are NOT changed.

## Verdicts (results/summary.json)

| Hypothesis | Decision | Honest reason |
|---|---|---|
| H1 manifold -> 10y mortality | **INCONCLUSIVE** | No NCHS Linked Mortality File. It is an optional input; CDC moved the linkage files in the same reorg (ftp + doc page both gone) -- a separate fetch + fixed-width parse. |
| H2 hyperglycemia heterogeneity | **INCONCLUSIVE** | Failed *eligibility*: the L3 immune layer is EMPTY (0 eligible) because hs-CRP (LBXCRP) was not measured by NHANES in 2011-2014 (it resumed 2015-2016). The pre-registered L3 + H2 feature set require it. |
| H3 layer-5 predictive lift | **INCONCLUSIVE** | Same root cause -- depends on the CRP-containing L3 layer. |

Layer eligibility (results/missingness_by_layer.json): **L2 metabolic 24,437 / 62%
eligible** (healthy); **L3 immune 0 / 0% eligible** (CRP absent 2 of 4 cycles).

## What this means -- read honestly

This is **NOT a falsification and NOT a validation.** It is the framework's own
DECISION_RULES working *exactly as designed*: "no hypothesis may be labeled
SUPPORTED without surviving its full truth-suite," and INCONCLUSIVE when the data
cannot even mount the suite. The engine **refused to claim what the data could not
support** -- which is the honesty the whole project is built on. The framework
remains UNTESTED on this run, blocked by NHANES data availability, not by evidence
for or against it.

## To get real verdicts (documented follow-ups -- not done)

1. **H1 (marquee):** locate the post-reorg NCHS public-use Linked Mortality Files,
   parse the fixed-width `.dat` -> `linked_mortality.csv` (SEQN, mortstat,
   permth_int), place in `nhanes_data/`, re-run. Unlocks the central hypothesis
   (does the nested-control manifold predict mortality).
2. **H2 / H3:** hs-CRP exists only 2015-2018 in NHANES. Testing L3-dependent
   hypotheses requires a PROTOCOL AMENDMENT (version bump per ANALYSIS_PLAN) to
   restrict to those cycles, OR an alternate L3 immune marker available across all
   four cycles. Do not change the analysis silently -- that would break the
   pre-registration.
