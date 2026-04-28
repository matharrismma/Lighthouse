#!/usr/bin/env python3
"""
NHANES Framework Extensions: Beyond Correlational Falsification
================================================================
Version 3.0

Extends v2.0 validation pipeline with:
  E1  Causal inference (IPW, g-computation, negative controls)
  E2  Incident events / survival analysis
  E3  Extended biomarker hooks (adipokines, oxidative stress, HOMA-IR)
  E4  External cohort validation framework
  E5  Manifold learning (UMAP, autoencoder, factor analysis)
  E6  Mediation analysis (L5 → L2/L3 → outcome)
  E7  Prospective simulations (power + FPR calibration)
  E8  Subgroup / precision-medicine clustering
  E9  Registered report + open pipeline structure

Usage:
  python nhanes_extensions.py --extensions e1,e5,e6,e7   # selected extensions
  python nhanes_extensions.py --extensions all             # everything
  python nhanes_extensions.py --extensions e7 --sim-reps 500  # simulation tuning

Requires: nhanes_validate.py v2.0 in the same directory.
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Import the v2.0 base
from nhanes_validate import (
    Config, FrameworkValidator, LayerProxyBuilder, NHANESDownloader,
    MortalityMerger, recode_special_codes, make_binary,
    build_run_manifest, PIPELINE_VERSION,
)

EXTENSIONS_VERSION = "3.1"


# ============================================================================
# EXTENDED CONFIG
# ============================================================================

class ExtendedConfig(Config):
    """Config with extension-specific parameters."""

    def __init__(self, mode: str = "full", extensions: Optional[List[str]] = None):
        super().__init__(mode=mode)
        self.extensions = extensions or []

        # E1: Causal inference
        self.CAUSAL_BOOTSTRAP_REPS = 500
        self.NEGATIVE_CONTROL_OUTCOMES = ["LBXVIE", "LBXVIC"]  # Vitamin E, C (shouldn't cause metabolic outcomes)
        self.NEGATIVE_CONTROL_FALLBACKS = ["LBXSAL"]  # Albumin as proxy if vitamins unavailable
        self.IPW_TRIM_QUANTILE = 0.01  # Trim extreme weights

        # E2: Incident / survival
        self.SURVIVAL_TERTILE_LABELS = ["low", "mid", "high"]

        # E3: Biomarker extensions
        # L1_PROXY: NHANES lacks direct cellular stress markers (HSP70, gamma-H2AX,
        # mitophagy flux, UPR). This composite uses downstream *consequences* of
        # cellular stress validated in large cohort studies. It is NOT a test of
        # the framework's mechanistic L1 claims — it is the best available NHANES
        # approximation. True L1 validation requires UK Biobank Olink proteomics
        # (HSP family) or a dedicated molecular cohort. See EXTENSIONS_PLAN E4.
        self.L1_PROXY_MIN_OBS = 3
        self.EXTENDED_BIOMARKERS = {
            "L1_proxy": {
                "indicators": ["LBXRDW", "LBXSGTSI", "LBXSALT", "LBXSUA", "LBXFER"],
                "min_obs": 3,
                "nhanes_modules": ["CBC", "BIOPRO", "FERTIN"],
                "label": "L1 cellular stress proxy (indirect — downstream biomarkers only)",
            },
            "L2_extended": {
                "indicators": ["LBXIN", "HOMA_IR"],  # Fasting insulin, HOMA-IR
                "nhanes_modules": ["INS"],
            },
            "L3_extended": {
                "indicators": ["LBXSGTSI"],  # GGT (oxidative stress proxy)
                "nhanes_modules": ["BIOPRO"],
            },
            "L_nutritional": {
                "indicators": ["LBXVIDMS", "LBXFOLSI", "LBXFER"],  # Vit D, folate, ferritin
                "nhanes_modules": ["VID", "FOLATE", "FERTIN"],
            },
        }

        # E5: Manifold learning
        self.UMAP_N_NEIGHBORS = 15
        self.UMAP_MIN_DIST = 0.1
        self.UMAP_N_COMPONENTS = 3
        self.AUTOENCODER_LATENT_DIM = 3
        self.AUTOENCODER_EPOCHS = 100
        self.N_FACTORS = 4  # Factor analysis components

        # E6: Mediation
        self.MEDIATION_BOOTSTRAP = 1000
        self.MEDIATION_PATHS = [
            {"exposure": "L5_systemic", "mediator": "L2_metabolic", "outcome": "diabetes_lab"},
            {"exposure": "L5_systemic", "mediator": "L3_immune", "outcome": "diabetes_lab"},
            {"exposure": "L5_systemic", "mediators": ["L3_immune", "L2_metabolic"], "outcome": "diabetes_lab"},
        ]

        # E7: Simulations
        self.SIM_REPS = 2000
        self.SIM_N_PER_REP = 5000
        self.SIM_SCENARIOS = ["true_hierarchy", "true_hierarchy_weak", "null", "reverse"]
        self.SIM_L5_BETAS = {"true_hierarchy": 0.3, "true_hierarchy_weak": 0.2}

        # E8: Subgroups
        self.DISCORDANCE_THRESHOLD_SD = 1.0
        self.SUBGROUP_MIN_N = 50

        # Paths
        self.EXT_RESULTS_DIR = Path("results/extensions")
        self.EXT_FIGURES_DIR = Path("figures/extensions")
        for d in [self.EXT_RESULTS_DIR, self.EXT_FIGURES_DIR]:
            d.mkdir(parents=True, exist_ok=True)


# ============================================================================
# E1: CAUSAL INFERENCE (IPW + g-computation + negative controls)
# ============================================================================

class CausalInference:
    """
    Causal methods within NHANES cross-sectional constraints.

    Key insight: we can't observe counterfactuals, but we CAN:
    1. Estimate treatment effects via IPW/g-computation
    2. Detect residual confounding via negative control outcomes
    3. Specify and test DAG implications
    """

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def _compute_propensity_scores(self, df: pd.DataFrame,
                                    exposure: str,
                                    confounders: List[str]) -> pd.Series:
        """P(exposure=high | confounders) via logistic regression."""
        from sklearn.linear_model import LogisticRegression

        dfa = df.dropna(subset=[exposure] + confounders).copy()
        median_exp = dfa[exposure].median()
        dfa["_exposed"] = (dfa[exposure] >= median_exp).astype(int)

        X = dfa[confounders].astype(float).values
        y = dfa["_exposed"].values

        m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        m.fit(X, y)
        ps = m.predict_proba(X)[:, 1]

        # Trim extreme propensity scores
        lo = np.quantile(ps, self.config.IPW_TRIM_QUANTILE)
        hi = np.quantile(ps, 1 - self.config.IPW_TRIM_QUANTILE)
        ps = np.clip(ps, lo, hi)

        return pd.Series(ps, index=dfa.index), dfa

    def ipw_ate(self, df: pd.DataFrame, exposure: str, outcome: str,
                confounders: List[str]) -> Dict:
        """Inverse Probability Weighted Average Treatment Effect."""
        print(f"\n  [IPW] {exposure} -> {outcome}")

        ps, dfa = self._compute_propensity_scores(df, exposure, confounders)
        dfa = dfa.dropna(subset=[outcome])
        ps = ps.loc[dfa.index]

        median_exp = dfa[exposure].median()
        exposed = (dfa[exposure] >= median_exp).astype(int).values
        y = dfa[outcome].astype(float).values
        ps_vals = ps.values

        # IPW estimator
        w1 = exposed / ps_vals
        w0 = (1 - exposed) / (1 - ps_vals)

        # Normalize weights
        w1 = w1 / w1.sum() * len(w1)
        w0 = w0 / w0.sum() * len(w0)

        mu1 = np.average(y, weights=w1)
        mu0 = np.average(y, weights=w0)
        ate = mu1 - mu0

        # Bootstrap CI
        rng = np.random.RandomState(self.config.RANDOM_SEED)
        boot_ates = []
        for _ in range(min(self.config.CAUSAL_BOOTSTRAP_REPS, 200)):
            idx = rng.choice(len(y), size=len(y), replace=True)
            yb, eb, pb = y[idx], exposed[idx], ps_vals[idx]
            w1b = eb / pb
            w0b = (1 - eb) / (1 - pb)
            w1b = w1b / (w1b.sum() + 1e-10) * len(w1b)
            w0b = w0b / (w0b.sum() + 1e-10) * len(w0b)
            boot_ates.append(np.average(yb, weights=w1b) - np.average(yb, weights=w0b))

        boot_arr = np.array(boot_ates)
        ci = [float(np.percentile(boot_arr, 2.5)), float(np.percentile(boot_arr, 97.5))]

        return {
            "method": "IPW",
            "exposure": exposure,
            "outcome": outcome,
            "confounders": confounders,
            "n": int(len(dfa)),
            "ate": round(float(ate), 6),
            "mu_exposed": round(float(mu1), 6),
            "mu_unexposed": round(float(mu0), 6),
            "bootstrap_ci_95": [round(c, 6) for c in ci],
            "significant": bool(ci[0] > 0 or ci[1] < 0),
        }

    def g_computation(self, df: pd.DataFrame, exposure: str, outcome: str,
                      confounders: List[str]) -> Dict:
        """G-computation (standardization) for ATE."""
        print(f"\n  [G-COMP] {exposure} -> {outcome}")
        from sklearn.linear_model import LogisticRegression

        dfa = df.dropna(subset=[exposure, outcome] + confounders).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        median_exp = dfa[exposure].median()
        X = dfa[confounders + [exposure]].astype(float)
        y = (dfa[outcome] >= 0.5).astype(int).values if dfa[outcome].nunique() > 2 else dfa[outcome].astype(int).values

        if len(np.unique(y)) < 2:
            return {"status": "INSUFFICIENT_VARIATION"}

        m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        m.fit(X, y)

        # Counterfactual: everyone exposed vs everyone unexposed
        X1 = X.copy()
        X1[exposure] = X[exposure].quantile(0.75)
        X0 = X.copy()
        X0[exposure] = X[exposure].quantile(0.25)

        mu1 = m.predict_proba(X1)[:, 1].mean()
        mu0 = m.predict_proba(X0)[:, 1].mean()
        ate = mu1 - mu0

        # Bootstrap
        rng = np.random.RandomState(self.config.RANDOM_SEED)
        boot_ates = []
        for _ in range(min(self.config.CAUSAL_BOOTSTRAP_REPS, 200)):
            idx = rng.choice(len(X), size=len(X), replace=True)
            mb = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            mb.fit(X.iloc[idx], y[idx])
            boot_ates.append(mb.predict_proba(X1.iloc[idx])[:, 1].mean() -
                             mb.predict_proba(X0.iloc[idx])[:, 1].mean())

        ci = [float(np.percentile(boot_ates, 2.5)), float(np.percentile(boot_ates, 97.5))]

        return {
            "method": "g_computation",
            "exposure": exposure, "outcome": outcome,
            "n": int(len(dfa)),
            "ate": round(float(ate), 6),
            "bootstrap_ci_95": [round(c, 6) for c in ci],
            "significant": bool(ci[0] > 0 or ci[1] < 0),
        }

    def negative_control_test(self, df: pd.DataFrame, exposure: str,
                               confounders: List[str]) -> Dict:
        """
        Test exposure against outcomes it SHOULD NOT affect.
        If significant → residual confounding detected.
        """
        print(f"\n  [NEG CONTROL] Testing {exposure} against control outcomes")

        nc_outcomes = self.config.NEGATIVE_CONTROL_OUTCOMES + self.config.NEGATIVE_CONTROL_FALLBACKS
        results = {}
        confounding_detected = False

        for nc in nc_outcomes:
            if nc not in df.columns or df[nc].isna().mean() > 0.9:
                continue
            try:
                res = self.ipw_ate(df, exposure, nc, confounders)
                results[nc] = res
                if res.get("significant", False):
                    confounding_detected = True
            except Exception as e:
                results[nc] = {"status": "ERROR", "error": str(e)}

        return {
            "exposure": exposure,
            "negative_control_results": results,
            "confounding_detected": confounding_detected,
            "interpretation": (
                "CAUTION: Residual confounding likely" if confounding_detected
                else "No evidence of residual confounding from negative controls"
            ),
        }

    def collider_bias_check(self, df: pd.DataFrame) -> Dict:
        """
        Test for collider bias: conditioning on a common effect of
        exposure and outcome can induce spurious associations.

        Strategy: L2 is a plausible collider (affected by both L5 and
        disease status). If the L5→outcome association REVERSES or
        INFLATES when conditioning on L2, collider bias is present.
        """
        print(f"\n  [COLLIDER CHECK] Testing L5→outcome with/without L2 conditioning")

        from sklearn.linear_model import LogisticRegression

        needed = ["RIDAGEYR", "RIAGENDR", "L5_systemic", "L2_metabolic", "LBXGLU", "LBXGH"]
        dfa = df.dropna(subset=needed).copy()

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        glu = pd.to_numeric(dfa["LBXGLU"], errors="coerce")
        a1c = pd.to_numeric(dfa["LBXGH"], errors="coerce")
        y = ((glu >= 126) | (a1c >= 6.5)).astype(int).values

        if len(np.unique(y)) < 2:
            return {"status": "INSUFFICIENT_VARIATION"}

        # Model 1: L5 → outcome (NOT conditioning on L2)
        X_uncond = dfa[["RIDAGEYR", "RIAGENDR", "L5_systemic"]].astype(float).values
        m1 = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        m1.fit(X_uncond, y)
        coef_uncond = float(m1.coef_[0, 2])  # L5 coefficient

        # Model 2: L5 → outcome CONDITIONING on L2 (potential collider)
        X_cond = dfa[["RIDAGEYR", "RIAGENDR", "L5_systemic", "L2_metabolic"]].astype(float).values
        m2 = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        m2.fit(X_cond, y)
        coef_cond = float(m2.coef_[0, 2])  # L5 coefficient when conditioned

        # Diagnostics
        sign_change = (coef_uncond > 0) != (coef_cond > 0)
        inflation = abs(coef_cond) > 2 * abs(coef_uncond) if abs(coef_uncond) > 0.001 else False
        collider_risk = sign_change or inflation

        result = {
            "status": "OK",
            "n": int(len(dfa)),
            "L5_coef_unconditional": round(coef_uncond, 6),
            "L5_coef_conditional_on_L2": round(coef_cond, 6),
            "sign_change": bool(sign_change),
            "coefficient_inflation_2x": bool(inflation),
            "collider_bias_risk": bool(collider_risk),
            "interpretation": (
                "WARNING: Collider bias detected — L5 coefficient changes substantially "
                "when conditioning on L2. Interpret L5→outcome claims with caution."
                if collider_risk else
                "No evidence of collider bias from L2 conditioning."
            ),
        }

        print(f"    L5 coef uncond: {coef_uncond:.4f}")
        print(f"    L5 coef cond|L2: {coef_cond:.4f}")
        print(f"    Sign change: {sign_change}  Inflation: {inflation}")
        print(f"    Collider risk: {collider_risk}")
        return result

    def run_all(self, df: pd.DataFrame) -> Dict:
        """Run full causal suite: IPW + g-comp + negative controls."""
        print(f"\n{'='*70}\nE1: CAUSAL INFERENCE SUITE\n{'='*70}")

        confounders = ["RIDAGEYR", "RIAGENDR"]
        results = {}

        # L5 -> metabolic outcomes (causal claim of the hierarchy)
        for method_fn, method_name in [(self.ipw_ate, "ipw"), (self.g_computation, "g_comp")]:
            for outcome in ["L2_metabolic", "L3_immune"]:
                key = f"{method_name}_L5_to_{outcome}"
                try:
                    results[key] = method_fn(df, "L5_systemic", outcome, confounders)
                except Exception as e:
                    results[key] = {"status": "ERROR", "error": str(e)}

        # Negative controls
        results["negative_controls"] = self.negative_control_test(
            df, "L5_systemic", confounders)

        # Collider bias check
        results["collider_bias"] = self.collider_bias_check(df)

        # Summary
        causal_effects = {k: v.get("ate") for k, v in results.items()
                         if isinstance(v, dict) and "ate" in v}
        nc_clean = not results.get("negative_controls", {}).get("confounding_detected", True)
        no_collider = not results.get("collider_bias", {}).get("collider_bias_risk", True)

        results["summary"] = {
            "all_effects_positive": all(v > 0 for v in causal_effects.values() if v is not None),
            "negative_controls_clean": nc_clean,
            "no_collider_bias": no_collider,
            "causal_claim_credible": (
                all(v > 0 for v in causal_effects.values() if v is not None)
                and nc_clean and no_collider
            ),
        }

        print(f"  Causal effects: {causal_effects}")
        print(f"  Negative controls clean: {nc_clean}")
        return results


# ============================================================================
# E2: INCIDENT EVENTS / SURVIVAL ANALYSIS
# ============================================================================

class IncidentEventAnalysis:
    """Survival analysis for prospective outcomes."""

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def kaplan_meier_by_manifold(self, df: pd.DataFrame) -> Dict:
        """KM curves stratified by upstream manifold tertiles."""
        print(f"\n{'='*70}\nE2: SURVIVAL ANALYSIS\n{'='*70}")

        if "mortstat" not in df.columns or "permth_int" not in df.columns:
            return {"status": "NO_MORTALITY_DATA"}

        needed = ["mortstat", "permth_int", "upstream_manifold"]
        dfa = df.dropna(subset=needed).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        mort = pd.to_numeric(dfa["mortstat"], errors="coerce")
        fu = pd.to_numeric(dfa["permth_int"], errors="coerce")
        event = (mort == 1).astype(int).values
        time = fu.values

        # Tertiles of upstream manifold
        tertiles = pd.qcut(dfa["upstream_manifold"], 3, labels=self.config.SURVIVAL_TERTILE_LABELS)
        dfa["manifold_tertile"] = tertiles

        # Simple KM calculation per tertile
        km_results = {}
        for tert in self.config.SURVIVAL_TERTILE_LABELS:
            mask = dfa["manifold_tertile"] == tert
            t_g, e_g = time[mask.values], event[mask.values]
            n = int(len(t_g))
            events = int(e_g.sum())

            # Compute KM survival at key timepoints
            sorted_times = np.sort(np.unique(t_g[e_g == 1]))
            surv = 1.0
            survival_curve = []
            for st in sorted_times:
                at_risk = int((t_g >= st).sum())
                deaths = int(((t_g == st) & (e_g == 1)).sum())
                if at_risk > 0:
                    surv *= (1 - deaths / at_risk)
                survival_curve.append({"time": float(st), "survival": round(float(surv), 6)})

            # 5-year and 10-year survival
            s_60 = next((s["survival"] for s in reversed(survival_curve) if s["time"] <= 60), None)
            s_120 = next((s["survival"] for s in reversed(survival_curve) if s["time"] <= 120), None)

            km_results[tert] = {
                "n": n, "events": events,
                "survival_5y": round(float(s_60), 4) if s_60 else None,
                "survival_10y": round(float(s_120), 4) if s_120 else None,
                "median_followup": round(float(np.median(t_g)), 1),
            }

        # Log-rank test (simplified via chi-square on events per tertile)
        from scipy.stats import chi2_contingency
        obs_events = [km_results[t]["events"] for t in self.config.SURVIVAL_TERTILE_LABELS]
        obs_n = [km_results[t]["n"] for t in self.config.SURVIVAL_TERTILE_LABELS]
        total_rate = sum(obs_events) / sum(obs_n)
        expected = [n * total_rate for n in obs_n]

        logrank_chi2 = sum((o - e) ** 2 / (e + 1e-10) for o, e in zip(obs_events, expected))
        from scipy.stats import chi2
        logrank_p = float(1 - chi2.cdf(logrank_chi2, df=2))

        # Plot KM curves
        self._plot_km(dfa, time, event)

        # Gradient check: does risk increase monotonically with manifold?
        gradient = (km_results["high"]["events"] / km_results["high"]["n"] >
                    km_results["mid"]["events"] / km_results["mid"]["n"] >
                    km_results["low"]["events"] / km_results["low"]["n"])

        result = {
            "status": "OK",
            "n": int(len(dfa)),
            "tertile_results": km_results,
            "logrank_chi2": round(logrank_chi2, 4),
            "logrank_p": round(logrank_p, 6),
            "dose_response_gradient": bool(gradient),
        }

        print(f"  N={len(dfa):,}")
        for t in self.config.SURVIVAL_TERTILE_LABELS:
            r = km_results[t]
            print(f"  {t}: n={r['n']:,} events={r['events']} S(10y)={r.get('survival_10y')}")
        print(f"  Log-rank p={logrank_p:.4f}  Gradient: {gradient}")
        return result

    def _plot_km(self, df, time, event):
        """Plot Kaplan-Meier curves by manifold tertile."""
        fig, ax = plt.subplots(figsize=(8, 6))
        colors = {"low": "#2ecc71", "mid": "#f39c12", "high": "#e74c3c"}

        for tert in self.config.SURVIVAL_TERTILE_LABELS:
            mask = (df["manifold_tertile"] == tert).values
            t_g, e_g = time[mask], event[mask]

            sorted_times = np.sort(np.unique(t_g))
            surv = 1.0
            times_plot, surv_plot = [0], [1.0]
            for st in sorted_times:
                at_risk = (t_g >= st).sum()
                deaths = ((t_g == st) & (e_g == 1)).sum()
                if at_risk > 0:
                    surv *= (1 - deaths / at_risk)
                times_plot.append(st)
                surv_plot.append(surv)

            ax.step(times_plot, surv_plot, where="post", label=f"{tert} manifold",
                    color=colors[tert], linewidth=2)

        ax.set_xlabel("Follow-up (months)")
        ax.set_ylabel("Survival Probability")
        ax.set_title("Kaplan-Meier by Upstream Manifold Tertile")
        ax.legend()
        ax.set_ylim(0, 1.05)
        out = self.config.EXT_FIGURES_DIR / "km_by_manifold.png"
        plt.tight_layout()
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  [SAVED] {out}")

    def hazard_by_layer(self, df: pd.DataFrame) -> Dict:
        """Per-layer hazard ratios using simple logistic approximation."""
        print(f"\n  [HAZARD] Per-layer associations with mortality")

        if "mortstat" not in df.columns:
            return {"status": "NO_MORTALITY_DATA"}

        from sklearn.linear_model import LogisticRegression

        needed = ["mortstat", "permth_int", "RIDAGEYR", "RIAGENDR"]
        layers = ["L5_systemic", "L3_immune", "L2_metabolic", "L4_tissue"]
        dfa = df.dropna(subset=needed).copy()

        mort = pd.to_numeric(dfa["mortstat"], errors="coerce")
        fu = pd.to_numeric(dfa["permth_int"], errors="coerce")
        y = ((mort == 1) & (fu <= self.config.MORT_10Y_MONTHS)).astype(int).values

        results = {}
        for layer in layers:
            sub = dfa.dropna(subset=[layer])
            y_sub = y[sub.index.isin(dfa.index)]
            if len(sub) < self.config.MIN_SAMPLE_SIZE or len(np.unique(y_sub)) < 2:
                results[layer] = {"status": "INSUFFICIENT"}
                continue

            X = sub[["RIDAGEYR", "RIAGENDR", layer]].astype(float).values
            try:
                m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
                mask = sub.index.isin(dfa.index)
                y_l = y[dfa.index.isin(sub.index)]
                m.fit(X, y_l)
                coef = float(m.coef_[0, 2])
                odds_ratio = float(np.exp(coef))
                results[layer] = {
                    "log_or": round(coef, 4),
                    "odds_ratio": round(odds_ratio, 4),
                    "n": int(len(sub)),
                    "direction": "risk" if coef > 0 else "protective",
                }
            except Exception as e:
                results[layer] = {"status": "ERROR", "error": str(e)}

        return {"status": "OK", "layer_hazards": results}

    def competing_risks_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Competing-risks awareness: separate CVD mortality from other causes.
        Uses cause-specific hazard approach (treat competing events as censoring).

        ucod_leading codes (from LMF documentation):
        1 = Heart disease, 2 = Cancer, 3 = Chronic lower respiratory,
        4 = Accidents, 5 = Cerebrovascular, 9 = All other causes
        """
        print(f"\n  [COMPETING RISKS] Cause-specific mortality by manifold")

        if "mortstat" not in df.columns or "ucod_leading" not in df.columns:
            return {"status": "NO_CAUSE_DATA",
                    "note": "Requires ucod_leading from LMF"}

        from sklearn.linear_model import LogisticRegression

        needed = ["mortstat", "permth_int", "ucod_leading",
                  "RIDAGEYR", "RIAGENDR", "upstream_manifold"]
        dfa = df.dropna(subset=needed).copy()

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        mort = pd.to_numeric(dfa["mortstat"], errors="coerce")
        fu = pd.to_numeric(dfa["permth_int"], errors="coerce")
        ucod = pd.to_numeric(dfa["ucod_leading"], errors="coerce")

        # Define cause-specific events
        cause_map = {
            "cardiovascular": [1, 5],    # heart disease + cerebrovascular
            "cancer": [2],
            "other": [3, 4, 9],
        }

        results = {}
        for cause_name, codes in cause_map.items():
            # Cause-specific: event if died of this cause within 10y,
            # censored if alive OR died of other cause
            y_cs = ((mort == 1) & (fu <= self.config.MORT_10Y_MONTHS) &
                    (ucod.isin(codes))).astype(int).values

            if y_cs.sum() < 20:
                results[cause_name] = {"status": "TOO_FEW_EVENTS", "events": int(y_cs.sum())}
                continue

            X = dfa[["RIDAGEYR", "RIAGENDR", "upstream_manifold"]].astype(float).values
            m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            m.fit(X, y_cs)
            coef = float(m.coef_[0, 2])  # manifold coefficient

            results[cause_name] = {
                "events": int(y_cs.sum()),
                "n": int(len(dfa)),
                "manifold_log_or": round(coef, 4),
                "manifold_or": round(float(np.exp(coef)), 4),
                "direction": "risk" if coef > 0 else "protective",
            }

            print(f"    {cause_name}: events={y_cs.sum()} OR={np.exp(coef):.3f} ({results[cause_name]['direction']})")

        # Key finding: is the manifold more predictive of CVD than other causes?
        cvd_or = results.get("cardiovascular", {}).get("manifold_or")
        other_or = results.get("other", {}).get("manifold_or")
        cvd_specificity = (cvd_or is not None and other_or is not None and
                          cvd_or > other_or)

        results["summary"] = {
            "cvd_specificity": bool(cvd_specificity) if cvd_or is not None else None,
            "interpretation": (
                "Manifold shows stronger association with CVD than other causes"
                if cvd_specificity else
                "No CVD-specific signal detected" if cvd_or is not None else
                "Insufficient cause-of-death data"
            ),
        }

        return {"status": "OK", "cause_specific": results}


# ============================================================================
# E3: EXTENDED BIOMARKER HOOKS
# ============================================================================

class BiomarkerExtensions:
    """Plugin architecture for additional NHANES biomarkers."""

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def compute_homa_ir(self, df: pd.DataFrame) -> pd.DataFrame:
        """HOMA-IR = (fasting glucose mg/dL * fasting insulin uU/mL) / 405."""
        df = df.copy()
        glu = pd.to_numeric(df.get("LBXGLU", pd.Series(dtype=float)), errors="coerce")
        ins = pd.to_numeric(df.get("LBXIN", pd.Series(dtype=float)), errors="coerce")
        df["HOMA_IR"] = np.where(
            glu.notna() & ins.notna() & (ins > 0),
            (glu * ins) / 405.0,
            np.nan
        )
        n_valid = int(df["HOMA_IR"].notna().sum())
        print(f"  [HOMA-IR] Computed for {n_valid:,} participants")
        return df

    def compute_l1_proxy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build L1 cellular stress proxy composite from NHANES-available variables.

        IMPORTANT SCOPE CAVEAT: This composite does NOT test the framework's L1
        mechanistic claims (mitophagy, HSP chaperone function, UPR, DNA damage
        response). NHANES does not contain those biomarkers. This composite
        captures *downstream consequences* of cellular stress that are measurable
        in NHANES and have independent mortality/disease associations:

            LBXRDW   Red cell distribution width — oxidative RBC damage, cellular
                     aging stress marker; validated independent mortality predictor
                     in NHANES and multiple external cohorts (min_obs anchor).
            LBXSGTSI GGT — glutathione cycling, hepatic oxidative stress.
            LBXSALT  ALT — hepatocellular damage signal.
            LBXSUA   Uric acid — purine catabolism byproduct, oxidative load.
            LBXFER   Ferritin — iron-mediated oxidative stress; fasting subsample
                     only, so coverage is lower than the other four indicators.

        Composite: cycle-wise z-scored mean, gated at min_obs=3 of 5.
        All variables are direction-aligned so higher = more stress
        (RDW high = more variation = more damage; GGT/ALT/uric acid/ferritin all
        increase with oxidative/cellular burden).

        True L1 validation path: UK Biobank Olink proteomics (HSP family members)
        or dedicated molecular cohort. See EXTENSIONS_PLAN.md E4.
        """
        df = df.copy()
        indicators = ["LBXRDW", "LBXSGTSI", "LBXSALT", "LBXSUA", "LBXFER"]
        available = [c for c in indicators if c in df.columns]
        missing = [c for c in indicators if c not in df.columns]

        print(f"\n  [L1_proxy] Building cellular stress proxy composite")
        print(f"    Available: {available}")
        if missing:
            print(f"    Missing (will be excluded): {missing}")
        print(f"    NOTE: Indirect proxy only — downstream biomarkers, not direct L1 markers")

        if len(available) < self.config.L1_PROXY_MIN_OBS:
            print(f"    SKIP: Fewer than {self.config.L1_PROXY_MIN_OBS} indicators available")
            df["L1_proxy"] = np.nan
            return df

        builder = LayerProxyBuilder(self.config)
        composite = builder.z_mean_gated(df, available, min_obs=self.config.L1_PROXY_MIN_OBS)
        df["L1_proxy"] = composite

        n_valid = int(composite.notna().sum())
        pct = round(n_valid / len(df) * 100, 1)
        # Coverage drop-off from ferritin (fasting subsample)
        n_without_ferritin = int(df[available].drop(columns=["LBXFER"], errors="ignore")
                                 .notna().sum(axis=1).ge(self.config.L1_PROXY_MIN_OBS).sum())
        print(f"    Valid composite: {n_valid:,} ({pct}% of sample)")
        if "LBXFER" in available:
            print(f"    Without ferritin constraint: ~{n_without_ferritin:,} would qualify")
            print(f"    Ferritin reduces coverage — expected given fasting-subsample design")
        return df

    def register_extended_indicators(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Add extended biomarker composites to existing layers."""
        print(f"\n{'='*70}\nE3: EXTENDED BIOMARKER REGISTRATION\n{'='*70}")

        report = {}
        df = self.compute_homa_ir(df)
        df = self.compute_l1_proxy(df)

        # Record L1 proxy coverage in report
        n_l1 = int(df["L1_proxy"].notna().sum()) if "L1_proxy" in df.columns else 0
        report["L1_proxy"] = {
            "status": "OK" if n_l1 > 0 else "NO_DATA",
            "composite_type": "indirect_downstream_proxy",
            "true_l1_gap": (
                "Direct L1 markers (HSP70, gamma-H2AX, mitophagy flux, UPR) are "
                "not available in NHANES. This composite reflects downstream cellular "
                "stress consequences. UK Biobank Olink proteomics is the recommended "
                "path for true L1 validation."
            ),
            "indicators_available": [c for c in ["LBXRDW","LBXSGTSI","LBXSALT","LBXSUA","LBXFER"]
                                      if c in df.columns],
            "n_valid": n_l1,
            "pct_valid": round(n_l1 / len(df) * 100, 2) if len(df) > 0 else 0,
        }

        builder = LayerProxyBuilder(self.config)

        for ext_name, ext_def in self.config.EXTENDED_BIOMARKERS.items():
            indicators = ext_def["indicators"]
            available = [c for c in indicators if c in df.columns and df[c].notna().mean() > 0.05]
            if not available:
                report[ext_name] = {"status": "NO_DATA", "indicators_needed": indicators}
                print(f"  [{ext_name}] No data available")
                continue

            # Compute composite for available indicators
            composite = builder.z_mean_gated(df, available, min_obs=max(1, len(available) // 2))
            df[ext_name] = composite
            n_valid = int(composite.notna().sum())
            report[ext_name] = {
                "status": "OK",
                "indicators_available": available,
                "indicators_missing": [c for c in indicators if c not in available],
                "n_valid": n_valid,
                "pct_valid": round(n_valid / len(df) * 100, 2),
            }
            print(f"  [{ext_name}] {n_valid:,} valid ({report[ext_name]['pct_valid']}%)")

        return df, report


# ============================================================================
# E4: EXTERNAL COHORT VALIDATION FRAMEWORK
# ============================================================================

class CohortAdapter:
    """
    Abstract adapter for external cohort validation.
    Each cohort implements its own variable mapping.
    """

    def __init__(self, cohort_name: str):
        self.cohort_name = cohort_name
        self.variable_map: Dict[str, str] = {}  # standard_name -> cohort_var
        self.available = False

    def map_variables(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename cohort variables to standard pipeline names."""
        rename = {v: k for k, v in self.variable_map.items() if v in df.columns}
        return df.rename(columns=rename)

    def validate_minimum_variables(self, df: pd.DataFrame) -> Dict:
        """Check which layer indicators are available."""
        required = {
            "L2": ["glucose", "hba1c", "bmi", "waist", "tg_hdl"],
            "L3": ["crp", "wbc"],
            "L5": ["pulse", "sleep", "depression", "smoking"],
        }
        report = {}
        for layer, vars_needed in required.items():
            available = [v for v in vars_needed if v in df.columns or
                        self.variable_map.get(v, "") in df.columns]
            report[layer] = {
                "needed": vars_needed,
                "available": available,
                "coverage": round(len(available) / len(vars_needed) * 100, 1),
            }
        return report


class UKBiobankAdapter(CohortAdapter):
    def __init__(self):
        super().__init__("UK Biobank")
        self.variable_map = {
            "LBXGLU": "p30740",    # Glucose
            "LBXGH": "p30750",     # HbA1c
            "BMXBMI": "p21001",    # BMI
            "BMXWAIST": "p48",     # Waist circumference
            "LBXCRP": "p30710",    # CRP
            "RIDAGEYR": "p21003",  # Age at recruitment
            "RIAGENDR": "p31",     # Sex
        }


class AllOfUsAdapter(CohortAdapter):
    def __init__(self):
        super().__init__("All of Us")
        self.variable_map = {
            "LBXGLU": "glucose_fasting",
            "LBXGH": "hemoglobin_a1c",
            "BMXBMI": "bmi",
            "LBXCRP": "crp",
            "RIDAGEYR": "age_at_enrollment",
            "RIAGENDR": "sex_at_birth",
        }


class ExternalValidationFramework:
    """Orchestrates validation across multiple cohorts."""

    def __init__(self, config: ExtendedConfig):
        self.config = config
        self.adapters = {
            "uk_biobank": UKBiobankAdapter(),
            "all_of_us": AllOfUsAdapter(),
        }

    def generate_mapping_report(self) -> Dict:
        """Report variable availability across target cohorts."""
        print(f"\n{'='*70}\nE4: EXTERNAL COHORT MAPPING\n{'='*70}")

        report = {}
        for name, adapter in self.adapters.items():
            report[name] = {
                "cohort": adapter.cohort_name,
                "variable_map": adapter.variable_map,
                "n_mapped": len(adapter.variable_map),
                "status": "READY_FOR_DATA" if adapter.variable_map else "NO_MAPPING",
            }
            print(f"  {adapter.cohort_name}: {len(adapter.variable_map)} variables mapped")

        report["replication_checklist"] = {
            "minimum_variables": ["glucose/HbA1c", "CRP/WBC", "BMI", "pulse/sleep/depression/smoking"],
            "minimum_n": self.config.MIN_SAMPLE_SIZE,
            "analysis_plan": "ANALYSIS_PLAN.md v2.0",
            "decision_rules": "DECISION_RULES.md v2.0",
        }

        return report


# ============================================================================
# E5: MANIFOLD LEARNING
# ============================================================================

class ManifoldLearning:
    """
    Data-driven latent structure discovery.
    Tests whether hand-specified layer composites match natural data structure.
    """

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def _get_indicator_matrix(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str], Dict[str, List[int]]]:
        """Build indicator matrix with layer membership tracking."""
        layer_indicators = {
            "L2": ["LBXGLU", "LBXGH", "BMXBMI", "BMXWAIST", "TG_HDL_ratio"],
            "L3": ["LBXCRP", "LBXWBCSI"],
            "L5": ["BPXPLS", "short_sleep", "depression_score", "smoker_ever"],
        }
        all_inds = []
        layer_membership = {}
        for layer, inds in layer_indicators.items():
            available = [c for c in inds if c in df.columns]
            start = len(all_inds)
            all_inds.extend(available)
            layer_membership[layer] = list(range(start, start + len(available)))

        dfa = df[all_inds].dropna()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return np.array([]), all_inds, layer_membership

        from sklearn.preprocessing import StandardScaler
        X = StandardScaler().fit_transform(dfa[all_inds].astype(float))
        return X, all_inds, layer_membership

    def factor_analysis(self, df: pd.DataFrame) -> Dict:
        """Factor analysis to test whether factor structure matches theorized layers."""
        print(f"\n{'='*70}\nE5a: FACTOR ANALYSIS\n{'='*70}")

        X, indicators, layer_mem = self._get_indicator_matrix(df)
        if len(X) == 0:
            return {"status": "INSUFFICIENT_DATA"}

        from sklearn.decomposition import FactorAnalysis

        n_factors = min(self.config.N_FACTORS, len(indicators) - 1)
        fa = FactorAnalysis(n_components=n_factors, random_state=self.config.RANDOM_SEED)
        fa.fit(X)

        loadings = fa.components_.T  # (n_indicators x n_factors)

        # Check alignment: does each factor load primarily on one layer?
        alignment = {}
        for f_idx in range(n_factors):
            factor_loadings = loadings[:, f_idx]
            layer_avg = {}
            for layer, indices in layer_mem.items():
                if indices:
                    layer_avg[layer] = float(np.mean(np.abs(factor_loadings[indices])))
            dominant = max(layer_avg, key=layer_avg.get) if layer_avg else "none"
            alignment[f"factor_{f_idx}"] = {
                "layer_loadings": {k: round(v, 4) for k, v in layer_avg.items()},
                "dominant_layer": dominant,
            }

        # Congruence: do factors clearly separate by layer?
        all_dominant = [v["dominant_layer"] for v in alignment.values()]
        layers_represented = len(set(all_dominant))
        clean_separation = layers_represented >= min(3, n_factors)

        result = {
            "status": "OK",
            "n_samples": int(len(X)),
            "n_indicators": len(indicators),
            "n_factors": n_factors,
            "explained_variance": [round(float(v), 4) for v in fa.noise_variance_],
            "factor_alignment": alignment,
            "layers_represented": layers_represented,
            "clean_separation": clean_separation,
            "interpretation": (
                "Factor structure aligns with theorized layers"
                if clean_separation else
                "Factor structure does NOT cleanly separate by layer"
            ),
        }

        print(f"  {n_factors} factors on {len(indicators)} indicators ({len(X)} samples)")
        for f, a in alignment.items():
            print(f"  {f}: dominant={a['dominant_layer']} {a['layer_loadings']}")
        print(f"  Clean separation: {clean_separation}")
        return result

    def umap_embedding(self, df: pd.DataFrame) -> Dict:
        """UMAP to visualize natural clustering vs. layer structure."""
        print(f"\n{'='*70}\nE5b: UMAP EMBEDDING\n{'='*70}")

        X, indicators, layer_mem = self._get_indicator_matrix(df)
        if len(X) == 0:
            return {"status": "INSUFFICIENT_DATA"}

        try:
            from sklearn.manifold import TSNE  # Fallback if UMAP not installed
            use_tsne = True
        except ImportError:
            return {"status": "NO_UMAP_OR_TSNE"}

        try:
            import umap
            reducer = umap.UMAP(n_components=2,
                               n_neighbors=self.config.UMAP_N_NEIGHBORS,
                               min_dist=self.config.UMAP_MIN_DIST,
                               random_state=self.config.RANDOM_SEED)
            embedding = reducer.fit_transform(X)
            method = "UMAP"
        except ImportError:
            reducer = TSNE(n_components=2, random_state=self.config.RANDOM_SEED, perplexity=30)
            embedding = reducer.fit_transform(X[:min(5000, len(X))])
            X = X[:min(5000, len(X))]
            method = "t-SNE"

        # Color by each layer composite to see if structure is visible
        dfa = df.dropna(subset=indicators)
        if len(dfa) > len(X):
            dfa = dfa.iloc[:len(X)]

        self._plot_embedding(embedding, dfa, indicators, method)

        # Quantify: silhouette of layer-based labels
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        # Cluster in embedding space
        km = KMeans(n_clusters=3, random_state=self.config.RANDOM_SEED, n_init=10)
        cluster_labels = km.fit_predict(embedding)
        sil = silhouette_score(embedding, cluster_labels)

        result = {
            "status": "OK",
            "method": method,
            "n_samples": int(len(X)),
            "n_indicators": len(indicators),
            "silhouette_3clusters": round(float(sil), 4),
            "interpretation": (
                "Clear structure in data (silhouette > 0.3)" if sil > 0.3
                else "Weak/no clear cluster structure in embedding"
            ),
        }

        print(f"  {method}: {len(X)} samples, silhouette={sil:.3f}")
        return result

    def _plot_embedding(self, embedding, dfa, indicators, method):
        layers = ["L2_metabolic", "L3_immune", "L5_systemic"]
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for ax, layer in zip(axes, layers):
            if layer in dfa.columns:
                vals = dfa[layer].values[:len(embedding)]
                valid = ~np.isnan(vals)
                sc = ax.scatter(embedding[valid, 0], embedding[valid, 1],
                               c=vals[valid], cmap="RdYlBu_r", s=2, alpha=0.5)
                plt.colorbar(sc, ax=ax)
            ax.set_title(f"{method} colored by {layer}")
            ax.set_xticks([])
            ax.set_yticks([])
        out = self.config.EXT_FIGURES_DIR / "manifold_embedding.png"
        plt.tight_layout()
        plt.savefig(out, dpi=200, bbox_inches="tight")
        plt.close()
        print(f"  [SAVED] {out}")

    def autoencoder_test(self, df: pd.DataFrame) -> Dict:
        """Shallow autoencoder: does latent space recover layer structure?"""
        print(f"\n{'='*70}\nE5c: AUTOENCODER LATENT SPACE\n{'='*70}")

        X, indicators, layer_mem = self._get_indicator_matrix(df)
        if len(X) == 0 or len(X) < 1000:
            return {"status": "INSUFFICIENT_DATA"}

        try:
            from sklearn.neural_network import MLPRegressor
        except ImportError:
            return {"status": "SKLEARN_MISSING"}

        # Shallow autoencoder via MLPRegressor: X -> latent -> X
        latent_dim = self.config.AUTOENCODER_LATENT_DIM
        n_features = X.shape[1]

        # Encoder: n_features -> latent_dim (we use hidden_layer_sizes)
        ae = MLPRegressor(
            hidden_layer_sizes=(latent_dim,),
            activation="relu",
            max_iter=self.config.AUTOENCODER_EPOCHS,
            random_state=self.config.RANDOM_SEED,
            early_stopping=True,
            validation_fraction=0.1,
        )
        ae.fit(X, X)  # Autoencoder: reconstruct input

        # Extract latent activations
        from sklearn.base import clone
        # Get hidden layer activations manually
        W1 = ae.coefs_[0]  # (n_features x latent_dim)
        b1 = ae.intercepts_[0]
        latent = np.maximum(0, X @ W1 + b1)  # ReLU activation

        # Correlate latent dims with layer composites
        dfa = df.dropna(subset=indicators)
        if len(dfa) > len(X):
            dfa = dfa.iloc[:len(X)]

        correlations = {}
        for d in range(latent_dim):
            dim_corrs = {}
            for layer in ["L2_metabolic", "L3_immune", "L5_systemic"]:
                if layer in dfa.columns:
                    vals = dfa[layer].values[:len(latent)]
                    valid = ~np.isnan(vals)
                    if valid.sum() > 100:
                        from scipy.stats import spearmanr
                        r, p = spearmanr(latent[valid, d], vals[valid])
                        dim_corrs[layer] = {"rho": round(float(r), 4), "p": float(p)}
            correlations[f"latent_{d}"] = dim_corrs

        recon_error = float(ae.loss_)

        result = {
            "status": "OK",
            "n_samples": int(len(X)),
            "latent_dim": latent_dim,
            "reconstruction_loss": round(recon_error, 6),
            "latent_layer_correlations": correlations,
        }

        print(f"  Reconstruction loss: {recon_error:.4f}")
        for d, corrs in correlations.items():
            print(f"  {d}: {corrs}")
        return result

    def run_all(self, df: pd.DataFrame) -> Dict:
        results = {}
        results["factor_analysis"] = self.factor_analysis(df)
        results["factor_stability"] = self.factor_stability_cv(df)
        results["umap_embedding"] = self.umap_embedding(df)
        results["autoencoder"] = self.autoencoder_test(df)
        return results

    def factor_stability_cv(self, df: pd.DataFrame) -> Dict:
        """
        Cross-validate factor analysis stability: do the same factors
        emerge across different subsets of the data?

        Uses split-half reliability + bootstrap congruence.
        """
        print(f"\n{'='*70}\nE5d: FACTOR ANALYSIS STABILITY (CV)\n{'='*70}")

        X, indicators, layer_mem = self._get_indicator_matrix(df)
        if len(X) < 1000:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(X))}

        from sklearn.decomposition import FactorAnalysis
        from scipy.stats import spearmanr

        n_factors = min(self.config.N_FACTORS, len(indicators) - 1)
        rng = np.random.RandomState(self.config.RANDOM_SEED)

        # 1. Split-half reliability: fit on two halves, compare loadings
        idx = rng.permutation(len(X))
        half = len(X) // 2
        X_a, X_b = X[idx[:half]], X[idx[half:2*half]]

        fa_a = FactorAnalysis(n_components=n_factors, random_state=self.config.RANDOM_SEED)
        fa_b = FactorAnalysis(n_components=n_factors, random_state=self.config.RANDOM_SEED)
        fa_a.fit(X_a)
        fa_b.fit(X_b)

        # Tucker's congruence coefficient between loading matrices
        L_a = fa_a.components_.T  # (indicators × factors)
        L_b = fa_b.components_.T

        congruence_coeffs = []
        for f in range(n_factors):
            num = np.dot(L_a[:, f], L_b[:, f])
            denom = np.sqrt(np.dot(L_a[:, f], L_a[:, f]) * np.dot(L_b[:, f], L_b[:, f]))
            cc = num / denom if denom > 0 else 0
            congruence_coeffs.append(abs(float(cc)))

        mean_congruence = float(np.mean(congruence_coeffs))
        # Tucker's congruence > 0.85 = "fair", > 0.95 = "good"
        stable_factors = int(sum(c >= 0.85 for c in congruence_coeffs))

        # 2. Bootstrap: fit on B resamples, measure loading consistency
        n_boot = 50
        boot_loadings = []
        fa_ref = FactorAnalysis(n_components=n_factors, random_state=self.config.RANDOM_SEED)
        fa_ref.fit(X)
        L_ref = fa_ref.components_.T

        boot_congruences = []
        for _ in range(n_boot):
            idx_b = rng.choice(len(X), size=len(X), replace=True)
            fa_b = FactorAnalysis(n_components=n_factors, random_state=self.config.RANDOM_SEED)
            fa_b.fit(X[idx_b])
            L_b = fa_b.components_.T

            boot_cc = []
            for f in range(n_factors):
                num = np.dot(L_ref[:, f], L_b[:, f])
                denom = np.sqrt(np.dot(L_ref[:, f], L_ref[:, f]) * np.dot(L_b[:, f], L_b[:, f]))
                boot_cc.append(abs(float(num / denom)) if denom > 0 else 0)
            boot_congruences.append(np.mean(boot_cc))

        boot_mean = float(np.mean(boot_congruences))
        boot_min = float(np.min(boot_congruences))

        # 3. Layer alignment stability: does dominant layer per factor stay same?
        alignment_stable = True
        for f in range(n_factors):
            ref_dominant = max(layer_mem.keys(),
                              key=lambda l: np.mean(np.abs(L_ref[layer_mem[l], f])) if layer_mem[l] else 0)
            alt_dominant = max(layer_mem.keys(),
                              key=lambda l: np.mean(np.abs(L_a[layer_mem[l], f])) if layer_mem[l] else 0)
            if ref_dominant != alt_dominant:
                alignment_stable = False

        result = {
            "status": "OK",
            "n_samples": int(len(X)),
            "n_factors": n_factors,
            "split_half_congruence": {
                "per_factor": [round(c, 4) for c in congruence_coeffs],
                "mean": round(mean_congruence, 4),
                "stable_factors_ge_085": stable_factors,
            },
            "bootstrap_congruence": {
                "mean": round(boot_mean, 4),
                "min": round(boot_min, 4),
                "n_reps": n_boot,
            },
            "layer_alignment_stable": bool(alignment_stable),
            "overall_stable": bool(mean_congruence >= 0.85 and boot_mean >= 0.85 and alignment_stable),
            "interpretation": (
                "Factor structure is stable across data splits and bootstrap"
                if mean_congruence >= 0.85 and boot_mean >= 0.85
                else "Factor structure is UNSTABLE — interpretation may be data-dependent"
            ),
        }

        print(f"  Split-half congruence: {congruence_coeffs} (mean={mean_congruence:.3f})")
        print(f"  Bootstrap congruence: mean={boot_mean:.3f} min={boot_min:.3f}")
        print(f"  Layer alignment stable: {alignment_stable}")
        print(f"  Overall stable: {result['overall_stable']}")
        return result


# ============================================================================
# E6: MEDIATION ANALYSIS
# ============================================================================

class MediationAnalysis:
    """
    Quantify indirect effects: L5 → L2/L3 → outcome.
    Uses bootstrap-based causal mediation (Imai et al. framework).
    """

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def _prepare_outcome(self, df: pd.DataFrame, outcome_name: str) -> pd.Series:
        if outcome_name == "diabetes_lab":
            glu = pd.to_numeric(df.get("LBXGLU", pd.Series(dtype=float)), errors="coerce")
            a1c = pd.to_numeric(df.get("LBXGH", pd.Series(dtype=float)), errors="coerce")
            return ((glu >= self.config.DIABETES_GLUCOSE) |
                    (a1c >= self.config.DIABETES_A1C)).astype(float)
        elif outcome_name == "mortality_10y":
            mort = pd.to_numeric(df.get("mortstat", pd.Series(dtype=float)), errors="coerce")
            fu = pd.to_numeric(df.get("permth_int", pd.Series(dtype=float)), errors="coerce")
            return ((mort == 1) & (fu <= self.config.MORT_10Y_MONTHS)).astype(float)
        else:
            return pd.to_numeric(df.get(outcome_name, pd.Series(dtype=float)), errors="coerce")

    def single_mediator(self, df: pd.DataFrame, exposure: str,
                        mediator: str, outcome: str,
                        covariates: List[str]) -> Dict:
        """
        Bootstrap causal mediation for single mediator.
        ACME = Average Causal Mediation Effect
        ADE = Average Direct Effect
        """
        print(f"\n  [MEDIATION] {exposure} -> {mediator} -> {outcome}")

        from sklearn.linear_model import LogisticRegression, LinearRegression

        y = self._prepare_outcome(df, outcome)
        needed = [exposure, mediator] + covariates
        dfa = df.dropna(subset=needed).copy()
        dfa["_y"] = y.loc[dfa.index]
        dfa = dfa.dropna(subset=["_y"])

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        X_cov = dfa[covariates].astype(float).values
        t = dfa[exposure].astype(float).values
        m = dfa[mediator].astype(float).values
        y_val = dfa["_y"].astype(float).values

        if len(np.unique(y_val)) < 2:
            return {"status": "INSUFFICIENT_VARIATION"}

        # Point estimates
        acme, ade, total, prop_med = self._compute_mediation(
            X_cov, t, m, y_val)

        # Bootstrap CIs
        rng = np.random.RandomState(self.config.RANDOM_SEED)
        boot_acme, boot_ade, boot_prop = [], [], []

        n_boot = min(self.config.MEDIATION_BOOTSTRAP, 500)
        for _ in range(n_boot):
            idx = rng.choice(len(t), size=len(t), replace=True)
            try:
                a, d, tot, p = self._compute_mediation(
                    X_cov[idx], t[idx], m[idx], y_val[idx])
                boot_acme.append(a)
                boot_ade.append(d)
                if not np.isnan(p):
                    boot_prop.append(p)
            except Exception:
                continue

        ci_acme = [float(np.percentile(boot_acme, 2.5)),
                   float(np.percentile(boot_acme, 97.5))] if boot_acme else [np.nan, np.nan]
        ci_ade = [float(np.percentile(boot_ade, 2.5)),
                  float(np.percentile(boot_ade, 97.5))] if boot_ade else [np.nan, np.nan]

        result = {
            "status": "OK",
            "exposure": exposure, "mediator": mediator, "outcome": outcome,
            "n": int(len(dfa)),
            "acme": round(float(acme), 6),
            "ade": round(float(ade), 6),
            "total_effect": round(float(total), 6),
            "proportion_mediated": round(float(prop_med), 4) if not np.isnan(prop_med) else None,
            "acme_ci_95": [round(c, 6) for c in ci_acme],
            "ade_ci_95": [round(c, 6) for c in ci_ade],
            "acme_significant": bool(ci_acme[0] > 0 or ci_acme[1] < 0),
        }

        print(f"    ACME={acme:.4f} [{ci_acme[0]:.4f}, {ci_acme[1]:.4f}]")
        print(f"    ADE={ade:.4f}  Total={total:.4f}  %Med={prop_med:.1%}" if not np.isnan(prop_med) else f"    ADE={ade:.4f}")
        return result

    def _compute_mediation(self, X_cov, t, m, y):
        """Single mediation computation: exposure t, mediator m, outcome y."""
        from sklearn.linear_model import LinearRegression, LogisticRegression

        n = len(t)

        # Step 1: Mediator model: M ~ T + covariates
        X_med = np.column_stack([t, X_cov])
        med_model = LinearRegression()
        med_model.fit(X_med, m)

        # Step 2: Outcome model: Y ~ T + M + covariates
        X_out = np.column_stack([t, m, X_cov])
        if len(np.unique(y)) == 2:
            out_model = LogisticRegression(max_iter=3000, random_state=42)
        else:
            out_model = LinearRegression()
        out_model.fit(X_out, y)

        # Step 3: Counterfactual predictions
        t_hi = np.percentile(t, 75)
        t_lo = np.percentile(t, 25)

        # M under T=hi and T=lo
        m_hi = med_model.predict(np.column_stack([np.full(n, t_hi), X_cov]))
        m_lo = med_model.predict(np.column_stack([np.full(n, t_lo), X_cov]))

        # Y predictions for ACME
        if hasattr(out_model, "predict_proba"):
            y_t1_m1 = out_model.predict_proba(np.column_stack([np.full(n, t_hi), m_hi, X_cov]))[:, 1]
            y_t1_m0 = out_model.predict_proba(np.column_stack([np.full(n, t_hi), m_lo, X_cov]))[:, 1]
            y_t0_m0 = out_model.predict_proba(np.column_stack([np.full(n, t_lo), m_lo, X_cov]))[:, 1]
        else:
            y_t1_m1 = out_model.predict(np.column_stack([np.full(n, t_hi), m_hi, X_cov]))
            y_t1_m0 = out_model.predict(np.column_stack([np.full(n, t_hi), m_lo, X_cov]))
            y_t0_m0 = out_model.predict(np.column_stack([np.full(n, t_lo), m_lo, X_cov]))

        acme = float(np.mean(y_t1_m1 - y_t1_m0))  # Indirect effect
        ade = float(np.mean(y_t1_m0 - y_t0_m0))    # Direct effect
        total = acme + ade
        prop = acme / total if abs(total) > 1e-10 else np.nan

        return acme, ade, total, prop

    def time_varying_mediation(self, df: pd.DataFrame) -> Dict:
        """
        Time-varying mediation stub for multi-wave longitudinal data.

        Current NHANES is cross-sectional, so this module:
        1. Simulates what time-varying mediation WOULD look like with
           repeated measures (using cycle-as-time proxy where possible)
        2. Tests whether mediation proportions are stable across cycles
           (a necessary condition for time-invariant mediation assumption)
        3. Provides the framework for future multi-wave integration
           (e.g., All of Us longitudinal, Framingham repeated exams)
        """
        print(f"\n  [TIME-VARYING MEDIATION] Cycle-stratified stability check")

        covariates = ["RIDAGEYR", "RIAGENDR"]
        cycles = df["cycle_label"].dropna().unique() if "cycle_label" in df.columns else []

        if len(cycles) < 2:
            return {
                "status": "INSUFFICIENT_WAVES",
                "note": "Need >=2 cycles for time-varying analysis; "
                        "framework ready for longitudinal cohorts",
                "n_cycles": int(len(cycles)),
            }

        # Run mediation within each cycle to test temporal stability
        cycle_results = {}
        for cyc in sorted(cycles):
            df_cyc = df[df["cycle_label"] == cyc]
            if len(df_cyc) < self.config.MIN_SAMPLE_SIZE:
                cycle_results[str(cyc)] = {"status": "TOO_SMALL", "n": int(len(df_cyc))}
                continue

            # Primary path: L5 → L2 → diabetes
            try:
                res = self.single_mediator(
                    df_cyc, "L5_systemic", "L2_metabolic", "diabetes_lab", covariates)
                cycle_results[str(cyc)] = {
                    "n": res.get("n"),
                    "acme": res.get("acme"),
                    "ade": res.get("ade"),
                    "proportion_mediated": res.get("proportion_mediated"),
                    "acme_significant": res.get("acme_significant"),
                }
            except Exception as e:
                cycle_results[str(cyc)] = {"status": "ERROR", "error": str(e)}

        # Stability: are mediation proportions consistent across cycles?
        valid_props = [v["proportion_mediated"] for v in cycle_results.values()
                       if isinstance(v, dict) and v.get("proportion_mediated") is not None]
        valid_acmes = [v["acme"] for v in cycle_results.values()
                       if isinstance(v, dict) and v.get("acme") is not None]

        if len(valid_props) >= 2:
            prop_std = float(np.std(valid_props, ddof=1))
            prop_mean = float(np.mean(valid_props))
            acme_std = float(np.std(valid_acmes, ddof=1))
            acme_mean = float(np.mean(valid_acmes))
            # Coefficient of variation (undefined if mean near zero)
            prop_cv = prop_std / abs(prop_mean) if abs(prop_mean) > 0.01 else float("inf")
            acme_cv = acme_std / abs(acme_mean) if abs(acme_mean) > 0.001 else None
            # Sign consistency: all ACMEs same direction
            signs_consistent = all(a >= 0 for a in valid_acmes) or all(a <= 0 for a in valid_acmes)
            # Stable if: (proportion CV low) OR (ACME CV low) AND signs agree
            # When ACME is near-zero, rely on proportion stability + sign consistency
            if acme_cv is not None:
                stable = (acme_cv < 0.5 or prop_cv < 0.5) and signs_consistent
            else:
                stable = prop_cv < 0.5 and signs_consistent
        else:
            prop_std = prop_mean = acme_std = acme_mean = prop_cv = acme_cv = None
            stable = None
            signs_consistent = None

        result = {
            "status": "OK",
            "n_cycles": int(len(cycles)),
            "cycle_results": cycle_results,
            "stability": {
                "acme_mean": round(acme_mean, 6) if acme_mean is not None else None,
                "acme_std": round(acme_std, 6) if acme_std is not None else None,
                "acme_cv": round(acme_cv, 4) if acme_cv is not None else None,
                "acme_signs_consistent": signs_consistent,
                "proportion_mean": round(prop_mean, 4) if prop_mean is not None else None,
                "proportion_std": round(prop_std, 4) if prop_std is not None else None,
                "proportion_cv": round(prop_cv, 4) if prop_cv is not None and prop_cv != float("inf") else None,
                "temporally_stable": stable,
            },
            "interpretation": (
                "Mediation proportions stable across cycles — time-invariant assumption plausible"
                if stable else
                "Mediation proportions VARY across cycles — time-varying mediation needed for longitudinal data"
                if stable is False else
                "Insufficient cycles for stability assessment"
            ),
            "longitudinal_readiness": {
                "framework": "Imai et al. sequential ignorability with time-indexed mediators",
                "required_data": "Repeated measures of L5, L2/L3, and outcome at >=3 time points",
                "target_cohorts": ["All of Us (longitudinal)", "Framingham (multi-generation)",
                                   "CHARLS (biennial)"],
            },
        }

        if stable is not None:
            acme_cv_str = f"{acme_cv:.2f}" if acme_cv is not None else "N/A (near-zero)"
            print(f"    ACME across cycles: mean={acme_mean:.4f} CV={acme_cv_str}")
            print(f"    Proportion mediated: mean={prop_mean:.2%} CV={prop_cv:.2f}" if prop_cv != float("inf") else f"    Proportion mediated: mean={prop_mean:.2%}")
            print(f"    Signs consistent: {signs_consistent}")
            print(f"    Temporally stable: {stable}")

        return result

    def run_all(self, df: pd.DataFrame) -> Dict:
        print(f"\n{'='*70}\nE6: MEDIATION ANALYSIS\n{'='*70}")

        covariates = ["RIDAGEYR", "RIAGENDR"]
        results = {}

        for path in self.config.MEDIATION_PATHS:
            if "mediators" in path:
                # Sequential mediation: L5 -> L3 -> L2 -> outcome
                key = f"{path['exposure']}_via_{'_'.join(path['mediators'])}_to_{path['outcome']}"
                # Run as chain: first mediator, then second
                for i, med in enumerate(path["mediators"]):
                    sub_key = f"{key}_step{i}_{med}"
                    results[sub_key] = self.single_mediator(
                        df, path["exposure"], med, path["outcome"], covariates)
            else:
                key = f"{path['exposure']}_via_{path['mediator']}_to_{path['outcome']}"
                results[key] = self.single_mediator(
                    df, path["exposure"], path["mediator"], path["outcome"], covariates)

        # Time-varying mediation stability
        results["time_varying"] = self.time_varying_mediation(df)

        # Summary
        significant_paths = [k for k, v in results.items()
                            if isinstance(v, dict) and v.get("acme_significant")]
        all_props = [v.get("proportion_mediated") for v in results.values()
                    if isinstance(v, dict) and v.get("proportion_mediated") is not None]

        tv = results.get("time_varying", {}).get("stability", {})
        results["summary"] = {
            "n_paths_tested": len([k for k in results if k not in ("summary", "time_varying")]),
            "n_significant": len(significant_paths),
            "significant_paths": significant_paths,
            "mean_proportion_mediated": round(float(np.mean(all_props)), 4) if all_props else None,
            "hierarchy_supported_by_mediation": len(significant_paths) > 0,
            "temporally_stable": tv.get("temporally_stable"),
        }

        return results


# ============================================================================
# E7: PROSPECTIVE SIMULATIONS
# ============================================================================

class ProspectiveSimulations:
    """
    Synthetic data with KNOWN hierarchical structure.
    Measures power, FPR, and CI coverage.
    """

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def generate_scenario(self, scenario: str, n: int,
                          rng: np.random.RandomState) -> pd.DataFrame:
        """Generate synthetic data for one scenario."""
        age = rng.normal(50, 15, n).clip(20, 85)
        sex = rng.binomial(1, 0.5, n)

        if scenario in ("true_hierarchy", "true_hierarchy_weak"):
            # L5 -> L3 -> L2 -> outcome (true causal chain)
            # L5 has both indirect (via L3/L2) AND meaningful direct effect
            beta_L5 = self.config.SIM_L5_BETAS.get(scenario, 0.3)
            L5 = rng.normal(0, 1, n)
            L3 = 0.4 * L5 + rng.normal(0, 0.8, n)
            L2 = 0.3 * L3 + 0.2 * L5 + rng.normal(0, 0.7, n)
            logit = -2.5 + 0.02 * age + 0.4 * L2 + 0.15 * L3 + beta_L5 * L5
            outcome = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-logit))).astype(float)

        elif scenario == "null":
            # Independent layers, L5 has zero effect on outcome
            L5 = rng.normal(0, 1, n)
            L3 = rng.normal(0, 1, n)
            L2 = rng.normal(0, 1, n)
            logit = -2.5 + 0.02 * age + 0.4 * L2 + 0.15 * L3  # NO L5 term
            outcome = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-logit))).astype(float)

        elif scenario == "reverse":
            # L2 -> L3 -> L5 (opposite direction); L5 is downstream, not causal
            L2 = rng.normal(0, 1, n)
            L3 = 0.4 * L2 + rng.normal(0, 0.8, n)
            L5 = 0.3 * L3 + 0.2 * L2 + rng.normal(0, 0.7, n)
            logit = -2.5 + 0.02 * age + 0.4 * L2 + 0.15 * L3  # L5 epiphenomenal
            outcome = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-logit))).astype(float)

        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        # Build synthetic indicators for each layer
        df = pd.DataFrame({
            "RIDAGEYR": age, "RIAGENDR": sex.astype(float),
            "L5_systemic": L5, "L3_immune": L3, "L2_metabolic": L2,
            "LBXGLU": 100 + 15 * L2 + rng.normal(0, 10, n),
            "LBXGH": 5.5 + 0.5 * L2 + rng.normal(0, 0.3, n),
            "diabetes_lab": outcome,
            "cycle_label": "sim",
        })

        return df

    def _run_h3_on_synthetic(self, df: pd.DataFrame) -> Dict:
        """Run simplified H3 test on synthetic data."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score

        y = df["diabetes_lab"].astype(int).values
        if len(np.unique(y)) < 2:
            return {"delta": 0, "passes": False}

        X_a = df[["RIDAGEYR", "RIAGENDR", "L2_metabolic", "L3_immune"]].astype(float)
        X_b = df[["RIDAGEYR", "RIAGENDR", "L2_metabolic", "L3_immune", "L5_systemic"]].astype(float)

        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        m = LogisticRegression(max_iter=3000, random_state=42)
        auc_a = cross_val_score(m, X_a, y, cv=cv, scoring="roc_auc").mean()
        auc_b = cross_val_score(m, X_b, y, cv=cv, scoring="roc_auc").mean()
        delta = auc_b - auc_a

        return {
            "delta": float(delta),
            "passes": bool(delta >= self.config.PREREG_AUC_DELTA),
            "auc_base": float(auc_a),
            "auc_plus": float(auc_b),
        }

    def run_simulation_study(self) -> Dict:
        """Run all scenarios × N replications."""
        print(f"\n{'='*70}\nE7: PROSPECTIVE SIMULATIONS\n{'='*70}")

        results = {}
        rng = np.random.RandomState(self.config.RANDOM_SEED)

        for scenario in self.config.SIM_SCENARIOS:
            print(f"\n  Scenario: {scenario} ({self.config.SIM_REPS} reps × {self.config.SIM_N_PER_REP})")
            passes = []
            deltas = []

            for rep in range(self.config.SIM_REPS):
                df_sim = self.generate_scenario(scenario, self.config.SIM_N_PER_REP, rng)
                res = self._run_h3_on_synthetic(df_sim)
                passes.append(res["passes"])
                deltas.append(res["delta"])

                if (rep + 1) % 100 == 0:
                    print(f"    Rep {rep+1}/{self.config.SIM_REPS}...")

            pass_rate = float(np.mean(passes))
            delta_arr = np.array(deltas)

            results[scenario] = {
                "n_reps": self.config.SIM_REPS,
                "n_per_rep": self.config.SIM_N_PER_REP,
                "pass_rate": round(pass_rate, 4),
                "delta_mean": round(float(delta_arr.mean()), 6),
                "delta_std": round(float(delta_arr.std()), 6),
                "delta_median": round(float(np.median(delta_arr)), 6),
                "delta_ci_95": [round(float(np.percentile(delta_arr, 2.5)), 6),
                                round(float(np.percentile(delta_arr, 97.5)), 6)],
            }

            print(f"    Pass rate: {pass_rate:.3f}")
            print(f"    Delta: mean={delta_arr.mean():.4f} std={delta_arr.std():.4f}")

        # Derive calibration metrics
        true_power = results.get("true_hierarchy", {}).get("pass_rate", 0)
        weak_power = results.get("true_hierarchy_weak", {}).get("pass_rate", 0)
        null_fpr = results.get("null", {}).get("pass_rate", 0)
        reverse_fpr = results.get("reverse", {}).get("pass_rate", 0)

        results["calibration"] = {
            "power_true_hierarchy_b03": round(true_power, 4),
            "power_true_hierarchy_b02": round(weak_power, 4),
            "fpr_null": round(null_fpr, 4),
            "fpr_reverse": round(reverse_fpr, 4),
            "well_calibrated": bool(true_power > 0.80 and null_fpr < 0.10),
            "interpretation": (
                f"Power(β=0.3)={true_power:.1%}, Power(β=0.2)={weak_power:.1%}, "
                f"FPR(null)={null_fpr:.1%}, FPR(reverse)={reverse_fpr:.1%}. "
                + ("Well-calibrated." if true_power > 0.80 and null_fpr < 0.10
                   else "Needs attention: " +
                   ("low power at β=0.3" if true_power <= 0.80 else "") +
                   (" high FPR" if null_fpr >= 0.10 else ""))
            ),
        }

        # Plot
        self._plot_simulation(results)
        return results

    def _plot_simulation(self, results):
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Left: delta distributions
        ax = axes[0]
        scenarios = self.config.SIM_SCENARIOS
        colors = {"true_hierarchy": "#2ecc71", "true_hierarchy_weak": "#27ae60",
                  "null": "#95a5a6", "reverse": "#e74c3c"}
        for sc in scenarios:
            r = results.get(sc, {})
            mu = r.get("delta_mean", 0)
            sd = r.get("delta_std", 0.01)
            x = np.linspace(mu - 3*sd, mu + 3*sd, 200)
            y = np.exp(-0.5 * ((x - mu) / sd)**2) / (sd * np.sqrt(2*np.pi))
            ax.plot(x, y, label=sc, color=colors.get(sc, "gray"), linewidth=2)
        ax.axvline(self.config.PREREG_AUC_DELTA, color="black", linestyle="--", label=f"threshold={self.config.PREREG_AUC_DELTA}")
        ax.set_xlabel("ΔAUC (L5)")
        ax.set_ylabel("Density")
        ax.set_title("Simulation: ΔAUC Distribution by Scenario")
        ax.legend()

        # Right: pass rates
        ax2 = axes[1]
        names = scenarios
        rates = [results.get(s, {}).get("pass_rate", 0) for s in scenarios]
        bars = ax2.bar(names, rates, color=[colors.get(s, "gray") for s in scenarios])
        ax2.axhline(0.05, color="red", linestyle="--", alpha=0.5, label="5% FPR target")
        ax2.axhline(0.80, color="green", linestyle="--", alpha=0.5, label="80% power target")
        ax2.set_ylabel("Pass Rate")
        ax2.set_title("Power / FPR by Scenario")
        ax2.legend()
        for bar, rate in zip(bars, rates):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                    f"{rate:.1%}", ha="center", fontsize=10)

        out = self.config.EXT_FIGURES_DIR / "simulation_calibration.png"
        plt.tight_layout()
        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  [SAVED] {out}")


# ============================================================================
# E8: SUBGROUP / PRECISION-MEDICINE CLUSTERING
# ============================================================================

class SubgroupAnalysis:
    """
    Identify clinically actionable subgroups by layer discordance.
    E.g., metabolically healthy obese, lean diabetic, etc.
    """

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def discordance_profiles(self, df: pd.DataFrame) -> Dict:
        """Classify participants by inter-layer discordance."""
        print(f"\n{'='*70}\nE8: SUBGROUP / DISCORDANCE ANALYSIS\n{'='*70}")

        layers = ["L2_metabolic", "L3_immune", "L5_systemic"]
        dfa = df.dropna(subset=layers + ["RIDAGEYR", "RIAGENDR"]).copy()

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}

        th = self.config.DISCORDANCE_THRESHOLD_SD

        # Define profiles by z-score thresholds
        profiles = {
            "concordant_high": (dfa["L5_systemic"] > th) & (dfa["L2_metabolic"] > th),
            "concordant_low": (dfa["L5_systemic"] < -th) & (dfa["L2_metabolic"] < -th),
            "L5_high_L2_low": (dfa["L5_systemic"] > th) & (dfa["L2_metabolic"] < -th),
            "L2_high_L5_low": (dfa["L2_metabolic"] > th) & (dfa["L5_systemic"] < -th),
            "mixed": ~((dfa["L5_systemic"].abs() > th) | (dfa["L2_metabolic"].abs() > th)),
        }

        profile_results = {}
        for name, mask in profiles.items():
            sub = dfa[mask]
            if len(sub) < self.config.SUBGROUP_MIN_N:
                profile_results[name] = {"n": int(len(sub)), "status": "TOO_SMALL"}
                continue

            # Characterize subgroup
            chars = {
                "n": int(len(sub)),
                "pct_of_total": round(len(sub) / len(dfa) * 100, 1),
                "mean_age": round(float(sub["RIDAGEYR"].mean()), 1),
                "pct_female": round(float((sub["RIAGENDR"] == 2).mean() * 100), 1),
                "mean_L2": round(float(sub["L2_metabolic"].mean()), 3),
                "mean_L3": round(float(sub["L3_immune"].mean()), 3),
                "mean_L5": round(float(sub["L5_systemic"].mean()), 3),
            }

            # Disease prevalence if available
            for disease, col in [("diabetes", "has_diabetes"), ("cvd", "has_cvd"), ("htn", "has_htn")]:
                if col in sub.columns:
                    chars[f"pct_{disease}"] = round(float(sub[col].mean() * 100), 1)

            # Mortality if available
            if "mortstat" in sub.columns:
                mort = pd.to_numeric(sub["mortstat"], errors="coerce")
                fu = pd.to_numeric(sub.get("permth_int", pd.Series(dtype=float)), errors="coerce")
                if mort.notna().sum() > 10:
                    chars["mortality_rate"] = round(float(mort.mean()), 4)

            profile_results[name] = chars

        # Test: does L5's predictive value vary by profile?
        interaction_results = self._test_profile_interactions(dfa, profiles)

        result = {
            "status": "OK",
            "n_total": int(len(dfa)),
            "threshold_sd": th,
            "profiles": profile_results,
            "interaction_test": interaction_results,
        }

        for name, r in profile_results.items():
            if "status" not in r:
                print(f"  {name}: n={r['n']} ({r['pct_of_total']}%) L2={r['mean_L2']:.2f} L5={r['mean_L5']:.2f}")

        return result

    def _test_profile_interactions(self, df, profiles) -> Dict:
        """Test whether L5's predictive lift varies by discordance profile."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score, StratifiedKFold

        results = {}
        for name, mask in profiles.items():
            sub = df[mask]
            if len(sub) < 200:
                continue

            glu = pd.to_numeric(sub.get("LBXGLU", pd.Series(dtype=float)), errors="coerce")
            a1c = pd.to_numeric(sub.get("LBXGH", pd.Series(dtype=float)), errors="coerce")

            if glu.isna().all() and a1c.isna().all():
                continue

            sub_clean = sub.dropna(subset=["RIDAGEYR", "RIAGENDR", "L2_metabolic", "L3_immune", "L5_systemic"])
            y = pd.Series(0, index=sub_clean.index)
            if "has_diabetes" in sub_clean.columns:
                y = sub_clean["has_diabetes"].fillna(0).astype(int)
            else:
                continue

            if len(np.unique(y.values)) < 2 or len(sub_clean) < 100:
                continue

            X_a = sub_clean[["RIDAGEYR", "RIAGENDR", "L2_metabolic", "L3_immune"]].astype(float)
            X_b = sub_clean[["RIDAGEYR", "RIAGENDR", "L2_metabolic", "L3_immune", "L5_systemic"]].astype(float)

            m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=self.config.RANDOM_SEED)

            try:
                auc_a = cross_val_score(m, X_a, y, cv=cv, scoring="roc_auc").mean()
                auc_b = cross_val_score(m, X_b, y, cv=cv, scoring="roc_auc").mean()
                results[name] = {
                    "n": int(len(sub_clean)),
                    "delta_L5": round(float(auc_b - auc_a), 6),
                    "L5_matters_more": bool(auc_b - auc_a > self.config.PREREG_AUC_DELTA),
                }
            except Exception:
                continue

        return results


# ============================================================================
# E9: REGISTERED REPORT STRUCTURE
# ============================================================================

class RegisteredReportBuilder:
    """Generate registered report skeleton + replication artifacts."""

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def generate_report_structure(self, all_results: Dict) -> Dict:
        """Build registered report metadata and replication package."""
        print(f"\n{'='*70}\nE9: REGISTERED REPORT PACKAGING\n{'='*70}")

        report = {
            "title": "Nested Control Systems Framework for Chronic Disease: "
                     "A Pre-Registered Falsification Study with Causal Extensions",
            "registration": {
                "analysis_plan": "ANALYSIS_PLAN.md v2.0",
                "decision_rules": "DECISION_RULES.md v2.0",
                "extensions_plan": "EXTENSIONS_PLAN.md v3.0",
                "frozen_before_data": True,
            },
            "data_sources": {
                "primary": "NHANES 2011-2018 (public use)",
                "mortality": "NCHS Public-Use Linked Mortality File",
                "availability": "https://wwwn.cdc.gov/nchs/nhanes/",
            },
            "reproducibility": {
                "code": "nhanes_validate.py + nhanes_extensions.py",
                "requirements": "requirements.txt",
                "execution": {
                    "prereg": "python nhanes_validate.py --mode prereg",
                    "full": "python nhanes_validate.py --mode full",
                    "extensions": "python nhanes_extensions.py --extensions all",
                },
                "outputs": {
                    "machine_readable": [
                        "results/validation_results.json",
                        "results/summary.json",
                        "results/extensions/*.json",
                    ],
                    "human_readable": [
                        "results/summary.md",
                    ],
                },
            },
            "adversarial_predictions": {
                "what_would_falsify_H1": (
                    "AUC < 0.60 OR delta <= 0 vs age+sex, confirmed by weighted analysis"
                ),
                "what_would_falsify_H2": (
                    "best_k < 2 OR medication p > 0.05, AND ARI < 0.40"
                ),
                "what_would_falsify_H3": (
                    "delta_L5 < 0.01 OR negative in any adequate cycle, confirmed by weighted"
                ),
                "what_would_undermine_causal_claims": (
                    "Negative control outcomes significant (residual confounding), "
                    "OR mediation proportion near zero, "
                    "OR factor structure doesn't align with layers"
                ),
            },
            "replication_checklist": [
                "1. Install dependencies from requirements.txt",
                "2. Run: python nhanes_validate.py --mode full",
                "3. Compare results/validation_results.json to published results",
                "4. Run: python nhanes_extensions.py --extensions all",
                "5. Compare results/extensions/ to published extension results",
                "6. Verify run_manifest.json matches expected script hash",
                "7. Report any discrepancies with exact reproduction steps",
            ],
        }

        # Include summary of actual results if available
        if "verdicts" in all_results:
            report["primary_results_summary"] = all_results["verdicts"]
        if "extensions" in all_results:
            ext = all_results["extensions"]
            report["extension_results_summary"] = {
                k: (v.get("summary", v.get("calibration", "see full results"))
                    if isinstance(v, dict) else str(v))
                for k, v in ext.items()
            }

        return report

    def write_dockerfile(self) -> Path:
        """Generate Dockerfile for containerized reproduction."""
        content = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nhanes_validate.py .
COPY nhanes_extensions.py .
COPY ANALYSIS_PLAN.md .
COPY DECISION_RULES.md .
COPY EXTENSIONS_PLAN.md .
COPY CHANGELOG.md .

RUN mkdir -p nhanes_data results figures results/extensions figures/extensions

# Default: run full validation + all extensions
CMD ["sh", "-c", "python nhanes_validate.py --mode full && python nhanes_extensions.py --extensions all"]
"""
        out = Path("Dockerfile")
        out.write_text(content)
        print(f"  [SAVED] {out}")
        return out


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class ExtendedValidator:
    """Orchestrates base v2.0 + all extensions."""

    def __init__(self, config: ExtendedConfig):
        self.config = config

    def run(self) -> Dict:
        print(f"""
{'='*70}
  NHANES Extended Validation v{EXTENSIONS_VERSION}
  Mode: {self.config.mode}
  Extensions: {', '.join(self.config.extensions) or 'none'}
{'='*70}
""")
        # Run base pipeline first
        base_validator = FrameworkValidator(self.config)
        base_results = base_validator.run()

        # Load processed data
        processed = self.config.DATA_DIR / "nhanes_processed.csv"
        if not processed.exists():
            print("[ERROR] No processed data. Base pipeline must run first.")
            return base_results

        df = pd.read_csv(processed)
        print(f"\n[LOADED] {len(df):,} rows from {processed}")

        ext_results = {}

        # E7: Simulations (run first — calibrates expectations)
        if "e7" in self.config.extensions or "all" in self.config.extensions:
            sim = ProspectiveSimulations(self.config)
            ext_results["e7_simulations"] = sim.run_simulation_study()
            self._save_ext("e7_simulations.json", ext_results["e7_simulations"])

        # E1: Causal inference
        if "e1" in self.config.extensions or "all" in self.config.extensions:
            causal = CausalInference(self.config)
            ext_results["e1_causal"] = causal.run_all(df)
            self._save_ext("e1_causal.json", ext_results["e1_causal"])

        # E5: Manifold learning
        if "e5" in self.config.extensions or "all" in self.config.extensions:
            manifold = ManifoldLearning(self.config)
            ext_results["e5_manifold"] = manifold.run_all(df)
            self._save_ext("e5_manifold.json", ext_results["e5_manifold"])

        # E6: Mediation
        if "e6" in self.config.extensions or "all" in self.config.extensions:
            mediation = MediationAnalysis(self.config)
            ext_results["e6_mediation"] = mediation.run_all(df)
            self._save_ext("e6_mediation.json", ext_results["e6_mediation"])

        # E2: Incident events / survival
        if "e2" in self.config.extensions or "all" in self.config.extensions:
            survival = IncidentEventAnalysis(self.config)
            ext_results["e2_survival"] = {}
            ext_results["e2_survival"]["km_by_manifold"] = survival.kaplan_meier_by_manifold(df)
            ext_results["e2_survival"]["hazard_by_layer"] = survival.hazard_by_layer(df)
            ext_results["e2_survival"]["competing_risks"] = survival.competing_risks_analysis(df)
            self._save_ext("e2_survival.json", ext_results["e2_survival"])

        # E3: Biomarker extensions
        if "e3" in self.config.extensions or "all" in self.config.extensions:
            bio = BiomarkerExtensions(self.config)
            df, bio_report = bio.register_extended_indicators(df)
            ext_results["e3_biomarkers"] = bio_report
            self._save_ext("e3_biomarkers.json", ext_results["e3_biomarkers"])

        # E4: External cohort framework
        if "e4" in self.config.extensions or "all" in self.config.extensions:
            ecv = ExternalValidationFramework(self.config)
            ext_results["e4_external_cohorts"] = ecv.generate_mapping_report()
            self._save_ext("e4_external_cohorts.json", ext_results["e4_external_cohorts"])

        # E8: Subgroup analysis
        if "e8" in self.config.extensions or "all" in self.config.extensions:
            sub = SubgroupAnalysis(self.config)
            ext_results["e8_subgroups"] = sub.discordance_profiles(df)
            self._save_ext("e8_subgroups.json", ext_results["e8_subgroups"])

        # E9: Registered report
        if "e9" in self.config.extensions or "all" in self.config.extensions:
            rr = RegisteredReportBuilder(self.config)
            all_results = {**base_results, "extensions": ext_results}
            ext_results["e9_registered_report"] = rr.generate_report_structure(all_results)
            rr.write_dockerfile()
            self._save_ext("e9_registered_report.json", ext_results["e9_registered_report"])

        # Save combined extension results
        combined = self.config.EXT_RESULTS_DIR / "all_extensions.json"
        with open(combined, "w") as f:
            json.dump(ext_results, f, indent=2, default=str)
        print(f"\n[SAVED] {combined}")

        self._print_summary(ext_results)
        return {**base_results, "extensions": ext_results}

    def _save_ext(self, filename: str, data: Dict):
        out = self.config.EXT_RESULTS_DIR / filename
        with open(out, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"[SAVED] {out}")

    def _print_summary(self, ext_results: Dict):
        print(f"\n{'='*70}")
        print(f"EXTENSION SUMMARY v{EXTENSIONS_VERSION}")
        print(f"{'='*70}")

        if "e7_simulations" in ext_results:
            cal = ext_results["e7_simulations"].get("calibration", {})
            print(f"  E7 Simulations: power(β=0.3)={cal.get('power_true_hierarchy_b03')}, "
                  f"power(β=0.2)={cal.get('power_true_hierarchy_b02')}, "
                  f"FPR(null)={cal.get('fpr_null')}, FPR(reverse)={cal.get('fpr_reverse')}")

        if "e1_causal" in ext_results:
            s = ext_results["e1_causal"].get("summary", {})
            print(f"  E1 Causal: credible={s.get('causal_claim_credible')}, "
                  f"neg_controls_clean={s.get('negative_controls_clean')}, "
                  f"no_collider={s.get('no_collider_bias')}")

        if "e5_manifold" in ext_results:
            fa = ext_results["e5_manifold"].get("factor_analysis", {})
            print(f"  E5 Manifold: factor separation={fa.get('clean_separation')}")

        if "e6_mediation" in ext_results:
            ms = ext_results["e6_mediation"].get("summary", {})
            print(f"  E6 Mediation: significant_paths={ms.get('n_significant')}, "
                  f"avg_proportion={ms.get('mean_proportion_mediated')}, "
                  f"temporally_stable={ms.get('temporally_stable')}")

        if "e8_subgroups" in ext_results:
            profiles = ext_results["e8_subgroups"].get("profiles", {})
            n_viable = sum(1 for v in profiles.values() if isinstance(v, dict) and "pct_of_total" in v)
            print(f"  E8 Subgroups: {n_viable} viable discordance profiles")

        print(f"{'='*70}")


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="NHANES Extensions v3.0")
    parser.add_argument("--mode", choices=["prereg", "sensitivity", "full"],
                        default="full")
    parser.add_argument("--extensions", type=str, default="all",
                        help="Comma-separated: e1,e2,...,e9 or 'all'")
    parser.add_argument("--sim-reps", type=int, default=2000,
                        help="Simulation replications (E7)")
    args = parser.parse_args()

    ext_list = [e.strip().lower() for e in args.extensions.split(",")]
    config = ExtendedConfig(mode=args.mode, extensions=ext_list)
    config.SIM_REPS = args.sim_reps

    validator = ExtendedValidator(config)
    validator.run()
    print(f"\nDone (extensions={args.extensions}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
