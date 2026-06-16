#!/usr/bin/env python3
"""
NHANES Framework Validation: Nested Control Systems for Chronic Disease
=======================================================================
Version 3.1

PRE-REGISTERED HYPOTHESES (see ANALYSIS_PLAN.md)
-------------------------------------------------
H1 (Shared Manifold): Upstream layers (L5+L3+L2) predict 10-year mortality
H2 (Multi-Path): Hyperglycemia cases cluster by mechanism
H3 (Hierarchy): Adding L5 to L2+L3 improves diabetes prediction

DECISION RUBRIC (see DECISION_RULES.md)
----------------------------------------
SUPPORTED / FALSIFIED / INCONCLUSIVE — three-outcome with gate-by-gate audit

DATA: NHANES 2011-2018 (public XPT) + optional Linked Mortality CSV
LICENSE: Public Domain (CC0)

Usage:
  pip install -r requirements.txt
  python nhanes_validate.py                      # prereg mode (unweighted, locked)
  python nhanes_validate.py --mode sensitivity   # adds weighted analysis
  python nhanes_validate.py --mode full          # adds design-consistent uncertainty
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
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

PIPELINE_VERSION = "3.1"
ANALYSIS_PLAN_VERSION = "3.1"


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Central configuration — all tunable parameters in one place."""

    def __init__(self, mode: str = "prereg"):
        self.mode = mode  # prereg | sensitivity | full

        # NHANES cycles
        self.CYCLES: List[Tuple[str, str]] = [
            ("2011-2012", "G"),
            ("2013-2014", "H"),
            ("2015-2016", "I"),
            ("2017-2018", "J"),
        ]
        self.N_CYCLES = len(self.CYCLES)

        # Logical modules -> candidate NHANES base filenames
        self.MODULE_CANDIDATES: Dict[str, List[str]] = {
            "DEMO":   ["DEMO"],
            "BMX":    ["BMX"],
            "BPX":    ["BPX"],
            "HDL":    ["HDL"],
            "TRIGLY": ["TRIGLY"],
            "GHB":    ["GHB"],
            "GLU":    ["GLU"],
            "CRP":    ["CRP", "HSCRP"],
            "CBC":    ["CBC"],        # LBXRDW (RDW) for L1_proxy
            "FERTIN": ["FERTIN"],     # LBXFER (ferritin) for L1_proxy; fasting subsample
            "INS":    ["INS"],        # LBXIN (fasting insulin) for HOMA-IR
            "BIOPRO": ["BIOPRO"],
            "SLQ":    ["SLQ"],
            "DPQ":    ["DPQ"],
            "DIQ":    ["DIQ"],
            "MCQ":    ["MCQ"],
            "BPQ":    ["BPQ"],
            "SMQ":    ["SMQ"],
        }

        # ----- Minimum-observed gating (Chunk 1) -----
        self.LAYER_DEFINITIONS: Dict[str, Dict] = {
            "L2_metabolic": {
                "indicators": ["LBXGLU", "LBXGH", "BMXBMI", "BMXWAIST", "TG_HDL_ratio"],
                "min_obs": 3,
            },
            "L3_immune": {
                "indicators": ["LBXCRP", "LBXWBCSI"],
                "min_obs": 2,
            },
            "L4_tissue": {
                "indicators": ["SBP_mean", "DBP_mean", "LBXSATSI", "LBXSASSI", "LBXSCR", "LBXSAL"],
                "min_obs": 3,
            },
            "L5_systemic": {
                "indicators": ["BPXPLS", "short_sleep", "depression_score", "smoker_ever"],
                "min_obs": 2,
            },
        }
        self.MANIFOLD_COMPONENTS = ["L5_systemic", "L3_immune", "L2_metabolic"]
        self.MANIFOLD_MIN_OBS = 2

        # ----- Sample size thresholds -----
        self.MIN_SAMPLE_SIZE = 500
        self.MIN_EVENTS_H1 = 50
        self.MIN_CYCLE_N_H3 = 300

        # ----- Glycemia thresholds -----
        self.HYPERGLYCEMIA_GLUCOSE = 100
        self.HYPERGLYCEMIA_A1C = 5.7
        self.DIABETES_GLUCOSE = 126
        self.DIABETES_A1C = 6.5

        # ----- Modeling -----
        self.CV_FOLDS = 5
        self.TEST_SIZE = 0.30
        self.RANDOM_SEED = 42

        # ----- H1 -----
        self.MORT_10Y_MONTHS = 120

        # ----- H3 thresholds -----
        self.CLINICAL_AUC_DELTA = 0.02   # Required for SUPPORTED verdict
        self.PREREG_AUC_DELTA = 0.015    # Minimum for non-FALSIFIED

        # ----- H2 stability (Chunk 5) -----
        self.H2_BOOTSTRAP_N = 50
        self.H2_ARI_THRESHOLD = 0.40
        self.H2_MULTI_SEEDS = [42, 123, 456, 789, 1024]

        # ----- Design uncertainty (Chunk 4) -----
        self.BOOTSTRAP_REPS = 200

        # ----- Paths -----
        self.DATA_DIR = Path("nhanes_data")
        self.RESULTS_DIR = Path("results")
        self.FIGURES_DIR = Path("figures")
        for d in [self.DATA_DIR, self.RESULTS_DIR, self.FIGURES_DIR]:
            d.mkdir(exist_ok=True)


# ============================================================================
# NHANES SPECIAL CODE RECODING (Chunk 1)
# ============================================================================

NHANES_RECODE_RULES: Dict[str, Dict] = {
    "SMQ020":   {"valid": {1, 2}},
    "DPQ020":   {"valid": {0, 1, 2, 3}},
    "DPQ030":   {"valid": {0, 1, 2, 3}},
    "DIQ010":   {"valid": {1, 2, 3}},
    "DIQ050":   {"valid": {1, 2}},
    "DIQ070":   {"valid": {1, 2}},
    "MCQ160E":  {"valid": {1, 2}},
    "MCQ160F":  {"valid": {1, 2}},
    "BPQ020":   {"valid": {1, 2}},
}


def recode_special_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Map NHANES special response codes (7, 9, 77, 99) to NaN."""
    df = df.copy()
    for var, rules in NHANES_RECODE_RULES.items():
        if var not in df.columns:
            continue
        col = pd.to_numeric(df[var], errors="coerce")
        col = col.where(col.isin(rules["valid"]), other=np.nan)
        df[var] = col
    # Sleep: SLD012 valid 0-24
    if "SLD012" in df.columns:
        sld = pd.to_numeric(df["SLD012"], errors="coerce")
        sld = sld.where((sld >= 0) & (sld <= 24), other=np.nan)
        df["SLD012"] = sld
    return df


def make_binary(df: pd.DataFrame, src: str, dst: str, yes_val: float = 1) -> pd.DataFrame:
    """Create 0/1 binary. NaN stays NaN."""
    if src not in df.columns:
        df[dst] = np.nan
        return df
    col = pd.to_numeric(df[src], errors="coerce")
    df[dst] = np.where(col == yes_val, 1, np.where(col.isna(), np.nan, 0))
    return df


# ============================================================================
# RUN MANIFEST (Chunk 0)
# ============================================================================

def compute_script_hash() -> str:
    try:
        with open(__file__, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "UNKNOWN"


def get_git_hash() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                      stderr=subprocess.DEVNULL, timeout=5)
        return out.decode().strip()
    except Exception:
        return "NOT_A_GIT_REPO"


def get_dependency_versions() -> Dict[str, str]:
    versions = {"python": sys.version}
    for pkg in ["numpy", "pandas", "matplotlib", "sklearn", "scipy", "pyreadstat"]:
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "NOT_INSTALLED"
    return versions


def build_run_manifest(config: Config) -> Dict:
    return {
        "pipeline_version": PIPELINE_VERSION,
        "analysis_plan_version": ANALYSIS_PLAN_VERSION,
        "run_timestamp": datetime.now().isoformat(),
        "mode": config.mode,
        "script_sha256": compute_script_hash(),
        "git_hash": get_git_hash(),
        "os": f"{platform.system()} {platform.release()}",
        "dependencies": get_dependency_versions(),
        "config_snapshot": {
            "cycles": config.CYCLES,
            "random_seed": config.RANDOM_SEED,
            "cv_folds": config.CV_FOLDS,
            "test_size": config.TEST_SIZE,
            "min_sample_size": config.MIN_SAMPLE_SIZE,
            "min_events_h1": config.MIN_EVENTS_H1,
            "min_cycle_n_h3": config.MIN_CYCLE_N_H3,
            "prereg_auc_delta": config.PREREG_AUC_DELTA,
            "clinical_auc_delta": config.CLINICAL_AUC_DELTA,
            "h2_ari_threshold": config.H2_ARI_THRESHOLD,
            "h2_bootstrap_n": config.H2_BOOTSTRAP_N,
            "bootstrap_reps": config.BOOTSTRAP_REPS,
            "layer_min_obs": {k: v["min_obs"] for k, v in config.LAYER_DEFINITIONS.items()},
        },
    }


# ============================================================================
# DATA ACQUISITION
# ============================================================================

class NHANESDownloader:
    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def cycle_year_range(suffix: str) -> str:
        return {"G": "2011-2012", "H": "2013-2014",
                "I": "2015-2016", "J": "2017-2018"}[suffix]

    def xpt_url(self, base: str, suffix: str) -> str:
        yr = self.cycle_year_range(suffix)
        return f"https://wwwn.cdc.gov/Nchs/Nhanes/{yr}/{base}_{suffix}.XPT"

    @staticmethod
    def _download(url: str, out: Path) -> bool:
        try:
            import requests
            r = requests.get(url, timeout=90)
            if r.status_code == 200:
                out.write_bytes(r.content)
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def _read_xpt(path: Path) -> Optional[pd.DataFrame]:
        try:
            import pyreadstat
            df, _ = pyreadstat.read_xport(str(path))
            return df
        except Exception:
            return None

    def _get_module_df(self, module_key: str, suffix: str) -> Optional[pd.DataFrame]:
        for base in self.config.MODULE_CANDIDATES.get(module_key, []):
            xpt_path = self.config.DATA_DIR / f"{base}_{suffix}.XPT"
            if not xpt_path.exists():
                if not self._download(self.xpt_url(base, suffix), xpt_path):
                    continue
            df = self._read_xpt(xpt_path)
            if df is not None and "SEQN" in df.columns:
                print(f"  [OK] {module_key}: {base}_{suffix}.XPT  (cols={len(df.columns)})")
                return df
        print(f"  [MISS] {module_key}: no candidate for suffix {suffix}")
        return None

    @staticmethod
    def _safe_merge(left, right):
        if left is None: return right
        if right is None: return left
        if "SEQN" not in left.columns or "SEQN" not in right.columns: return left
        dupes = set(left.columns) & set(right.columns) - {"SEQN"}
        if dupes:
            right = right.drop(columns=list(dupes), errors="ignore")
        return left.merge(right, on="SEQN", how="left")

    def download_all_cycles(self) -> Dict[str, pd.DataFrame]:
        print("\n" + "=" * 70)
        print("DOWNLOADING / LOADING NHANES DATA")
        print("=" * 70)
        cycle_dfs = {}
        for label, suffix in self.config.CYCLES:
            print(f"\nCycle: {label} (suffix: {suffix})")
            cycle_df = None
            for module_key in self.config.MODULE_CANDIDATES:
                df_mod = self._get_module_df(module_key, suffix)
                cycle_df = self._safe_merge(cycle_df, df_mod)
            if cycle_df is None:
                print(f"  [FAIL] No data for {label}")
                continue
            cycle_df["cycle_label"] = label
            cycle_df["cycle_suffix"] = suffix
            cycle_dfs[label] = cycle_df
            print(f"  [DONE] n={len(cycle_df):,}  vars={len(cycle_df.columns)}")
        if not cycle_dfs:
            raise RuntimeError("No NHANES cycles loaded.")
        return cycle_dfs

    @staticmethod
    def merge_cycles(cycle_dfs):
        df = pd.concat(cycle_dfs.values(), axis=0, ignore_index=True)
        print(f"\nMerged: {len(df):,} participants, {len(df.columns)} columns")
        return df


# ============================================================================
# MORTALITY MERGE (Chunk 2)
# ============================================================================

class MortalityMerger:
    def __init__(self, config: Config):
        self.config = config

    def load_mortality_file(self, filepath: Path) -> Optional[pd.DataFrame]:
        if not filepath.exists():
            print(f"\n[WARN] Mortality file not found: {filepath}")
            return None
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"[ERROR] Cannot read mortality CSV: {e}")
            return None
        required = {"SEQN", "mortstat", "permth_int"}
        if required - set(df.columns):
            print(f"[ERROR] Missing columns: {required - set(df.columns)}")
            return None
        cols = ["SEQN", "mortstat", "permth_int"]
        if "ucod_leading" in df.columns:
            cols.append("ucod_leading")
        print(f"[OK] Mortality: n={len(df):,}")
        return df[cols].copy()

    def merge(self, nhanes_df, mort_df):
        if mort_df is None: return nhanes_df
        merged = nhanes_df.merge(mort_df, on="SEQN", how="left")
        print(f"[MERGED] Mortality for n={int(merged['mortstat'].notna().sum()):,}")
        return merged


# ============================================================================
# LAYER PROXIES (Chunk 1: mean-of-z, min-obs gating, code recoding)
# ============================================================================

class LayerProxyBuilder:
    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def ensure_columns(df, cols):
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        return df

    @staticmethod
    def _cyclewise_z(df, col, cycle_col="cycle_label"):
        x = pd.to_numeric(df[col], errors="coerce")
        out = pd.Series(index=df.index, dtype=float)
        for _, idx in df.groupby(cycle_col).groups.items():
            vals = x.loc[idx]
            mu, sd = vals.mean(skipna=True), vals.std(ddof=0, skipna=True)
            if sd == 0 or np.isnan(sd):
                out.loc[idx] = np.nan
            else:
                out.loc[idx] = (vals - mu) / sd
        return out

    def z_mean_gated(self, df, indicators, min_obs):
        """Mean of observed z-scores, NaN if < min_obs present."""
        Z = pd.concat([self._cyclewise_z(df, c) for c in indicators], axis=1)
        n_valid = Z.notna().sum(axis=1)
        composite = Z.mean(axis=1, skipna=True)
        return composite.where(n_valid >= min_obs, other=np.nan)

    def build_all_proxies(self, df):
        print("\n" + "=" * 70)
        print("BUILDING LAYER PROXIES (v2.0: mean-of-z, min-obs gated)")
        print("=" * 70)

        all_needed = [
            "RIDAGEYR", "RIAGENDR", "BMXBMI", "BMXWAIST",
            "BPXSY1", "BPXSY2", "BPXSY3", "BPXDI1", "BPXDI2", "BPXDI3", "BPXPLS",
            "LBXTR", "LBDHDD", "LBXGLU", "LBXGH", "LBXCRP", "LBXWBCSI",
            "LBXSAL", "LBXSATSI", "LBXSASSI", "LBXSCR",
            "SLD012", "DPQ020", "DPQ030", "SMQ020",
            "DIQ010", "DIQ070", "DIQ050", "MCQ160E", "MCQ160F", "BPQ020",
            "WTMEC2YR", "WTSAF2YR", "SDMVSTRA", "SDMVPSU",
        ]
        df = self.ensure_columns(df, all_needed)

        # Recode special codes
        df = recode_special_codes(df)

        # BP means
        sys_v = df[["BPXSY1","BPXSY2","BPXSY3"]].apply(pd.to_numeric, errors="coerce").to_numpy()
        dia_v = df[["BPXDI1","BPXDI2","BPXDI3"]].apply(pd.to_numeric, errors="coerce").to_numpy()
        df["SBP_mean"] = np.nanmean(sys_v, axis=1)
        df["DBP_mean"] = np.nanmean(dia_v, axis=1)

        # TG/HDL
        hdl = pd.to_numeric(df["LBDHDD"], errors="coerce")
        tg = pd.to_numeric(df["LBXTR"], errors="coerce")
        df["TG_HDL_ratio"] = np.where(hdl > 0, tg / hdl, np.nan)

        # Sleep
        sld = pd.to_numeric(df["SLD012"], errors="coerce")
        df["short_sleep"] = np.where(sld < 6, 1, np.where(sld.isna(), np.nan, 0))

        # Depression (PHQ-2)
        df["depression_score"] = (pd.to_numeric(df["DPQ020"], errors="coerce") +
                                  pd.to_numeric(df["DPQ030"], errors="coerce"))

        # Smoking
        df = make_binary(df, "SMQ020", "smoker_ever", yes_val=1)

        # Disease flags
        df = make_binary(df, "DIQ010", "has_diabetes", yes_val=1)
        df["has_cvd"] = np.where(
            (pd.to_numeric(df["MCQ160E"], errors="coerce") == 1) |
            (pd.to_numeric(df["MCQ160F"], errors="coerce") == 1), 1,
            np.where(pd.to_numeric(df["MCQ160E"], errors="coerce").isna() &
                     pd.to_numeric(df["MCQ160F"], errors="coerce").isna(), np.nan, 0))
        df = make_binary(df, "BPQ020", "has_htn", yes_val=1)
        df = make_binary(df, "DIQ070", "on_insulin", yes_val=1)
        df = make_binary(df, "DIQ050", "on_diabetes_pills", yes_val=1)

        # Layer composites
        for layer_name, layer_def in self.config.LAYER_DEFINITIONS.items():
            df[layer_name] = self.z_mean_gated(df, layer_def["indicators"], layer_def["min_obs"])

        # Upstream manifold
        layer_z = pd.concat([self._cyclewise_z(df, c) for c in self.config.MANIFOLD_COMPONENTS], axis=1)
        n_valid = layer_z.notna().sum(axis=1)
        df["upstream_manifold"] = layer_z.mean(axis=1, skipna=True).where(
            n_valid >= self.config.MANIFOLD_MIN_OBS, other=np.nan)

        # Combined survey weights (Chunk 3)
        for wt2, wtc in [("WTMEC2YR", "WTMEC_COMB"), ("WTSAF2YR", "WTSAF_COMB")]:
            w = pd.to_numeric(df[wt2], errors="coerce")
            df[wtc] = w / self.config.N_CYCLES

        print(f"[DONE] Proxies built. n={len(df):,}")
        return df


# ============================================================================
# MISSINGNESS + ELIGIBILITY REPORTING
# ============================================================================

def missingness_report(df, cols, title):
    rep = {}
    print(f"\n{'-'*70}\nMISSINGNESS: {title}\n{'-'*70}")
    for c in cols:
        rep[c] = float(df[c].isna().mean()) if c in df.columns else 1.0
    for c, frac in sorted(rep.items(), key=lambda x: -x[1]):
        print(f"  {c:25s}: {frac*100:6.2f}% missing")
    print(f"  Total rows: {len(df):,}")
    return rep


def layer_eligibility_report(df, config):
    print(f"\n{'-'*70}\nLAYER ELIGIBILITY (min-obs gating)\n{'-'*70}")
    report = {}
    for layer_name, layer_def in config.LAYER_DEFINITIONS.items():
        inds = layer_def["indicators"]
        min_obs = layer_def["min_obs"]
        if all(c in df.columns for c in inds):
            n_obs = df[inds].notna().sum(axis=1)
        else:
            n_obs = pd.Series(0, index=df.index)
        dist = n_obs.value_counts().sort_index().to_dict()
        n_elig = int((n_obs >= min_obs).sum())
        pct = round(n_elig / len(df) * 100, 2) if len(df) > 0 else 0
        report[layer_name] = {
            "indicators": inds, "min_obs_required": min_obs,
            "n_obs_distribution": {str(k): int(v) for k, v in dist.items()},
            "n_eligible": n_elig, "pct_eligible": pct,
        }
        print(f"  {layer_name}: {n_elig:,} eligible ({pct}%) — min_obs={min_obs}")

    mc = config.MANIFOLD_COMPONENTS
    n_lv = df[mc].notna().sum(axis=1)
    n_m = int((n_lv >= config.MANIFOLD_MIN_OBS).sum())
    report["upstream_manifold"] = {
        "components": mc, "min_obs_required": config.MANIFOLD_MIN_OBS,
        "n_eligible": n_m,
        "pct_eligible": round(n_m / len(df) * 100, 2) if len(df) else 0,
    }
    print(f"  upstream_manifold: {n_m:,} eligible")
    return report


# ============================================================================
# H1 COHORT REPORT (Chunk 2)
# ============================================================================

def h1_cohort_report(df, config):
    print(f"\n{'-'*70}\nH1 COHORT REPORT\n{'-'*70}")
    if "mortstat" not in df.columns or "permth_int" not in df.columns:
        print("  No mortality data")
        return {"status": "NO_MORTALITY_DATA"}

    has_mort = df["mortstat"].notna() & df["permth_int"].notna()
    has_demo = df["RIDAGEYR"].notna() & df["RIAGENDR"].notna()
    has_man = df["upstream_manifold"].notna()
    eligible = has_mort & has_demo & has_man
    cohort = df[eligible]

    if len(cohort) == 0:
        return {"status": "NO_ELIGIBLE", "n_eligible": 0}

    fu = pd.to_numeric(cohort["permth_int"], errors="coerce")
    mort = pd.to_numeric(cohort["mortstat"], errors="coerce")
    events = int(((mort == 1) & (fu <= config.MORT_10Y_MONTHS)).sum())

    report = {
        "status": "OK",
        "n_total": int(len(df)),
        "n_with_mortality": int(has_mort.sum()),
        "n_with_manifold": int(has_man.sum()),
        "n_eligible": int(len(cohort)),
        "events_10y": events,
        "followup_months": {
            "median": round(float(fu.median()), 1),
            "p25": round(float(fu.quantile(0.25)), 1),
            "p75": round(float(fu.quantile(0.75)), 1),
        },
    }
    print(f"  N eligible: {report['n_eligible']:,}  Events(10y): {events}")
    print(f"  Follow-up: median={fu.median():.0f}mo")
    return report


# ============================================================================
# STRUCTURAL VALIDATION (H2 with stability suite — Chunk 5)
# ============================================================================

class StructuralValidator:
    def __init__(self, config):
        self.config = config

    def test_hierarchical_correlations(self, df):
        from scipy.stats import spearmanr
        print(f"\n{'='*70}\nTIER 2A: HIERARCHICAL CORRELATIONS\n{'='*70}")
        layers = ["L5_systemic", "L3_immune", "L2_metabolic"]
        dfa = df[layers].dropna()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa))}
        r53, p53 = spearmanr(dfa["L5_systemic"], dfa["L3_immune"])
        r32, p32 = spearmanr(dfa["L3_immune"], dfa["L2_metabolic"])
        r52, p52 = spearmanr(dfa["L5_systemic"], dfa["L2_metabolic"])
        print(f"  L5-L3 rho={r53:.3f}  L3-L2 rho={r32:.3f}  L5-L2 rho={r52:.3f}")
        return {
            "status": "OK", "n": int(len(dfa)),
            "rho": {"L5_L3": round(float(r53),4), "L3_L2": round(float(r32),4), "L5_L2": round(float(r52),4)},
            "p": {"L5_L3": float(p53), "L3_L2": float(p32), "L5_L2": float(p52)},
            "hierarchy_supported": bool(r53 > r32),
        }

    def test_multipath_clustering(self, df):
        """H2: GMM + stability + cycle consistency."""
        print(f"\n{'='*70}\nTIER 2C: H2 MULTI-PATH (GMM + stability)\n{'='*70}")

        from sklearn.preprocessing import StandardScaler
        from sklearn.mixture import GaussianMixture
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import adjusted_rand_score
        from scipy.stats import chi2_contingency, kruskal

        glu = pd.to_numeric(df["LBXGLU"], errors="coerce")
        a1c = pd.to_numeric(df["LBXGH"], errors="coerce")
        band = df[(glu >= self.config.HYPERGLYCEMIA_GLUCOSE) |
                  (a1c >= self.config.HYPERGLYCEMIA_A1C)].copy()

        feats = ["LBXCRP", "SBP_mean", "DBP_mean", "LBXSATSI", "LBXSASSI", "BMXBMI"]
        band = band.dropna(subset=feats + ["on_insulin", "on_diabetes_pills"])

        if len(band) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(band)),
                    "decision": "INCONCLUSIVE", "gates_passed": [], "gates_failed": ["eligibility"], "gates_skipped": []}

        train, test = train_test_split(band, test_size=self.config.TEST_SIZE, random_state=self.config.RANDOM_SEED)
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(train[feats].astype(float))
        Xte = scaler.transform(test[feats].astype(float))

        # BIC selection
        best = None
        for k in range(2, 6):
            gmm = GaussianMixture(n_components=k, covariance_type="full", random_state=self.config.RANDOM_SEED)
            gmm.fit(Xtr)
            bic = gmm.bic(Xtr)
            if best is None or bic < best["bic"]:
                best = {"k": k, "bic": bic, "model": gmm}

        train_labels = best["model"].predict(Xtr)
        test["cluster"] = best["model"].predict(Xte)

        # External: medication chi-sq
        p_ins = p_pil = np.nan
        ci = pd.crosstab(test["cluster"], test["on_insulin"])
        cp = pd.crosstab(test["cluster"], test["on_diabetes_pills"])
        if ci.shape[0] >= 2 and ci.shape[1] >= 2:
            _, p_ins, _, _ = chi2_contingency(ci)
        if cp.shape[0] >= 2 and cp.shape[1] >= 2:
            _, p_pil, _, _ = chi2_contingency(cp)
        external_valid = ((not np.isnan(p_ins) and p_ins <= 0.05) or
                          (not np.isnan(p_pil) and p_pil <= 0.05))

        # External: A1c separation
        a1c_groups = [pd.to_numeric(test.loc[test["cluster"]==c, "LBXGH"], errors="coerce").dropna()
                      for c in sorted(test["cluster"].unique())]
        a1c_p = np.nan
        if len(a1c_groups) >= 2 and all(len(g) >= 5 for g in a1c_groups):
            _, a1c_p = kruskal(*a1c_groups)

        # Bootstrap ARI stability
        rng = np.random.RandomState(self.config.RANDOM_SEED)
        ari_scores = []
        for _ in range(self.config.H2_BOOTSTRAP_N):
            idx = rng.choice(len(Xtr), size=len(Xtr), replace=True)
            gmm_b = GaussianMixture(n_components=best["k"], covariance_type="full", random_state=self.config.RANDOM_SEED)
            gmm_b.fit(Xtr[idx])
            ari_scores.append(adjusted_rand_score(train_labels, gmm_b.predict(Xtr)))
        ari_mean = float(np.mean(ari_scores))
        ari_stable = ari_mean >= self.config.H2_ARI_THRESHOLD

        # Multi-seed
        seed_labels = {}
        for seed in self.config.H2_MULTI_SEEDS:
            g = GaussianMixture(n_components=best["k"], covariance_type="full", random_state=seed)
            g.fit(Xtr)
            seed_labels[seed] = g.predict(Xtr)
        ref = seed_labels[self.config.H2_MULTI_SEEDS[0]]
        seed_aris = [adjusted_rand_score(ref, seed_labels[s]) for s in self.config.H2_MULTI_SEEDS[1:]]
        seed_ari_mean = float(np.mean(seed_aris)) if seed_aris else np.nan

        # Cycle consistency
        overall_profile = test.groupby("cluster")[feats].mean()
        cycle_consistent = True
        cycle_diffs = {}
        for cyc, g in test.groupby("cycle_label"):
            if len(g) < 30: continue
            cp = g.groupby("cluster")[feats].mean()
            if cp.shape[0] < best["k"]:
                cycle_consistent = False
                cycle_diffs[cyc] = "missing_clusters"
            else:
                cycle_diffs[cyc] = round(float((cp - overall_profile).abs().mean().mean()), 4)

        # Gates
        gp, gf, gs = [], [], []
        gp.append("eligibility")
        (gp if best["k"] >= 2 else gf).append("cluster_count")
        (gp if external_valid else gf).append("external_validity")
        (gp if ari_stable else gf).append("stability_ari")
        (gp if cycle_consistent else gf).append("cycle_consistency")

        primary_ok = best["k"] >= 2 and external_valid
        stability_ok = ari_stable and cycle_consistent
        if primary_ok and stability_ok:
            decision = "SUPPORTED"
        elif not primary_ok:
            decision = "FALSIFIED"
        else:
            decision = "INCONCLUSIVE"

        result = {
            "status": "OK", "decision": decision,
            "gates_passed": gp, "gates_failed": gf, "gates_skipped": gs,
            "n_total": int(len(band)), "n_train": int(len(train)), "n_test": int(len(test)),
            "best_k": int(best["k"]), "best_bic": round(float(best["bic"]), 1),
            "cluster_sizes_test": {str(k): int(v) for k,v in test["cluster"].value_counts().sort_index().items()},
            "medication_p_values": {
                "insulin": None if np.isnan(p_ins) else round(float(p_ins), 6),
                "pills": None if np.isnan(p_pil) else round(float(p_pil), 6),
            },
            "a1c_kruskal_p": None if np.isnan(a1c_p) else round(float(a1c_p), 6),
            "stability": {
                "bootstrap_ari_mean": round(ari_mean, 4),
                "ari_threshold": self.config.H2_ARI_THRESHOLD,
                "ari_passes": ari_stable,
                "multi_seed_ari_mean": round(seed_ari_mean, 4) if not np.isnan(seed_ari_mean) else None,
            },
            "cycle_consistency": {"consistent": cycle_consistent, "profile_diffs": cycle_diffs},
            "passes_preregister": primary_ok,
            "decision_basis": f"k={best['k']}, med_p=[{p_ins},{p_pil}], ARI={ari_mean:.3f}, cycle={cycle_consistent}",
        }
        print(f"  k={best['k']}  med_p: ins={p_ins} pil={p_pil}  ARI={ari_mean:.3f}  cycle={cycle_consistent}")
        print(f"  Decision: {decision}")
        return result

    def test_shared_markers_across_diseases(self, df):
        from scipy.stats import ttest_ind
        print(f"\n{'='*70}\nTIER 2D: SHARED UPSTREAM MARKERS\n{'='*70}")
        diseases = {"diabetes": "has_diabetes", "cvd": "has_cvd", "hypertension": "has_htn"}
        layers = ["L5_systemic", "L3_immune", "L2_metabolic"]
        out = {}
        for name, col in diseases.items():
            cases = df[df[col]==1].dropna(subset=layers)
            ctrls = df[df[col]==0].dropna(subset=layers)
            if len(cases) < 100 or len(ctrls) < 100: continue
            res = {}
            for L in layers:
                t, p = ttest_ind(cases[L], ctrls[L], equal_var=False)
                pooled = np.sqrt((cases[L].var(ddof=0) + ctrls[L].var(ddof=0))/2)
                d = (cases[L].mean() - ctrls[L].mean()) / pooled if pooled > 0 else np.nan
                res[L] = {"cohens_d": round(float(d),4), "p": float(p),
                          "n_cases": int(len(cases)), "n_ctrl": int(len(ctrls))}
            out[name] = res
        all_pos = all(out[d][L]["cohens_d"] > 0 for d in out for L in layers if L in out[d])
        return {"status": "OK", "effects": out, "all_effects_positive": bool(all_pos)}


# ============================================================================
# PREDICTIVE VALIDATION: H3 (Chunk 6) + H1 (Chunk 2)
# ============================================================================

class PredictiveValidator:
    def __init__(self, config):
        self.config = config

    def test_h3_hierarchy_auc(self, df):
        print(f"\n{'='*70}\nTIER 3A: H3 HIERARCHY (CV + robustness)\n{'='*70}")
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score

        needed = ["RIDAGEYR","RIAGENDR","LBXGLU","LBXGH","L2_metabolic","L3_immune","L5_systemic","cycle_label"]
        dfa = df.dropna(subset=needed).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "n": int(len(dfa)),
                    "decision": "INCONCLUSIVE", "gates_passed": [], "gates_failed": ["eligibility"], "gates_skipped": []}

        glu = pd.to_numeric(dfa["LBXGLU"], errors="coerce")
        a1c = pd.to_numeric(dfa["LBXGH"], errors="coerce")
        y = ((glu >= self.config.DIABETES_GLUCOSE) | (a1c >= self.config.DIABETES_A1C)).astype(int).values
        if len(np.unique(y)) < 2:
            return {"status": "INSUFFICIENT_VARIATION", "n": int(len(dfa)),
                    "decision": "INCONCLUSIVE", "gates_passed": [], "gates_failed": [], "gates_skipped": []}

        X_a = dfa[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune"]].astype(float)
        X_b = dfa[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune","L5_systemic"]].astype(float)
        cv = StratifiedKFold(n_splits=self.config.CV_FOLDS, shuffle=True, random_state=self.config.RANDOM_SEED)
        m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)

        auc_a = cross_val_score(m, X_a, y, cv=cv, scoring="roc_auc")
        auc_b = cross_val_score(m, X_b, y, cv=cv, scoring="roc_auc")
        delta = float(auc_b.mean() - auc_a.mean())

        # Brier score (lower = better calibration) and partial AUC (high-specificity)
        from sklearn.metrics import brier_score_loss, roc_auc_score
        brier_a_scores, brier_b_scores = [], []
        pauc_a_scores, pauc_b_scores = [], []
        cv2 = StratifiedKFold(n_splits=self.config.CV_FOLDS, shuffle=True, random_state=self.config.RANDOM_SEED)
        for train_idx, test_idx in cv2.split(X_a, y):
            m_a = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            m_b = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            m_a.fit(X_a.iloc[train_idx], y[train_idx])
            m_b.fit(X_b.iloc[train_idx], y[train_idx])
            pa = m_a.predict_proba(X_a.iloc[test_idx])[:,1]
            pb = m_b.predict_proba(X_b.iloc[test_idx])[:,1]
            brier_a_scores.append(brier_score_loss(y[test_idx], pa))
            brier_b_scores.append(brier_score_loss(y[test_idx], pb))
            try:
                pauc_a_scores.append(roc_auc_score(y[test_idx], pa, max_fpr=0.2))
                pauc_b_scores.append(roc_auc_score(y[test_idx], pb, max_fpr=0.2))
            except Exception:
                pass  # partial AUC can fail with small folds

        brier_a = float(np.mean(brier_a_scores)) if brier_a_scores else None
        brier_b = float(np.mean(brier_b_scores)) if brier_b_scores else None
        brier_delta = float(brier_a - brier_b) if brier_a is not None and brier_b is not None else None  # positive = L5 improves
        pauc_a = float(np.mean(pauc_a_scores)) if pauc_a_scores else None
        pauc_b = float(np.mean(pauc_b_scores)) if pauc_b_scores else None
        pauc_delta = float(pauc_b - pauc_a) if pauc_a is not None and pauc_b is not None else None

        # Cycle check (min N=300)
        negative_any = False
        cycle_check = {}
        for cyc, g in dfa.groupby("cycle_label"):
            gg = g.dropna(subset=["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune","L5_systemic","LBXGLU","LBXGH"])
            if len(gg) < self.config.MIN_CYCLE_N_H3:
                cycle_check[cyc] = {"status": "SKIPPED_LOW_N", "n": int(len(gg))}
                continue
            yy = ((pd.to_numeric(gg["LBXGLU"], errors="coerce") >= self.config.DIABETES_GLUCOSE) |
                  (pd.to_numeric(gg["LBXGH"], errors="coerce") >= self.config.DIABETES_A1C)).astype(int).values
            if len(np.unique(yy)) < 2:
                cycle_check[cyc] = {"status": "SKIPPED_NO_VARIATION", "n": int(len(gg))}
                continue
            cv3 = StratifiedKFold(n_splits=3, shuffle=True, random_state=self.config.RANDOM_SEED)
            a1 = cross_val_score(m, gg[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune"]].astype(float), yy, cv=cv3, scoring="roc_auc").mean()
            a2 = cross_val_score(m, gg[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune","L5_systemic"]].astype(float), yy, cv=cv3, scoring="roc_auc").mean()
            dc = float(a2-a1)
            cycle_check[cyc] = {"delta": round(dc,6), "n": int(len(gg)), "status": "OK"}
            if dc < 0: negative_any = True

        # Meta summary
        cds = [v["delta"] for v in cycle_check.values() if v.get("status")=="OK"]
        meta_mean = float(np.mean(cds)) if cds else None
        meta_std = float(np.std(cds, ddof=1)) if len(cds)>1 else None

        # Gates
        gp, gf, gs = ["eligibility"], [], []
        (gp if delta >= self.config.PREREG_AUC_DELTA else gf).append("primary_lift")
        if not cds:
            gs.append("cycle_sign")
        elif not negative_any:
            gp.append("cycle_sign")
        else:
            gf.append("cycle_sign")

        # Clinical bar gate: required for SUPPORTED (not just reported)
        meets_clinical = delta >= self.config.CLINICAL_AUC_DELTA
        (gp if meets_clinical else gf).append("clinical_bar")

        cycle_stable = True
        if len(cds) >= 2 and meta_std and meta_mean is not None:
            if negative_any and meta_std > abs(meta_mean):
                cycle_stable = False

        primary_ok = (delta >= self.config.PREREG_AUC_DELTA) and not negative_any
        if primary_ok and cycle_stable and meets_clinical:
            decision = "SUPPORTED"
        elif delta < self.config.PREREG_AUC_DELTA:
            decision = "FALSIFIED"
        elif negative_any and not cycle_stable:
            decision = "INCONCLUSIVE"
        elif negative_any:
            decision = "FALSIFIED"
        elif primary_ok and not meets_clinical:
            decision = "INCONCLUSIVE"  # passes prereg but below clinical bar
        else:
            decision = "INCONCLUSIVE"

        result = {
            "status": "OK", "decision": decision,
            "gates_passed": gp, "gates_failed": gf, "gates_skipped": gs,
            "n": int(len(dfa)),
            "auc_L2_L3_mean": round(float(auc_a.mean()),6), "auc_L2_L3_std": round(float(auc_a.std()),6),
            "auc_L2_L3_L5_mean": round(float(auc_b.mean()),6), "auc_L2_L3_L5_std": round(float(auc_b.std()),6),
            "delta_L5": round(delta,6),
            "brier_L2_L3": round(brier_a, 6) if brier_a is not None else None,
            "brier_L2_L3_L5": round(brier_b, 6) if brier_b is not None else None,
            "brier_delta": round(brier_delta, 6) if brier_delta is not None else None,
            "partial_auc_L2_L3": round(pauc_a, 6) if pauc_a is not None else None,
            "partial_auc_L2_L3_L5": round(pauc_b, 6) if pauc_b is not None else None,
            "partial_auc_delta": round(pauc_delta, 6) if pauc_delta is not None else None,
            "meets_clinical_bar": meets_clinical,
            "clinically_meaningful": meets_clinical,
            "cycle_check": cycle_check,
            "meta_cycle": {"mean_delta": meta_mean, "std_delta": meta_std, "n_cycles": len(cds)},
            "passes_preregister": primary_ok,
            "decision_basis": f"delta={delta:.4f}(threshold={self.config.PREREG_AUC_DELTA}), clinical={meets_clinical}(>={self.config.CLINICAL_AUC_DELTA}), neg_any={negative_any}, stable={cycle_stable}",
        }
        brier_str = f" Brier_delta={brier_delta:.4f}" if brier_delta is not None else ""
        pauc_str = f" pAUC_delta={pauc_delta:.4f}" if pauc_delta is not None else ""
        print(f"  AUC L2+L3: {auc_a.mean():.4f}  L2+L3+L5: {auc_b.mean():.4f}  delta: +{delta:.4f}{brier_str}{pauc_str}")
        print(f"  Clinical bar (>={self.config.CLINICAL_AUC_DELTA}): {meets_clinical}")
        print(f"  Decision: {decision}")
        return result

    def test_h1_mortality_auc_10y(self, df):
        print(f"\n{'='*70}\nTIER 3C: H1 MORTALITY\n{'='*70}")
        if "mortstat" not in df.columns:
            return {"status": "SKIPPED", "decision": "INCONCLUSIVE",
                    "decision_basis": "No mortality data",
                    "gates_passed": [], "gates_failed": [], "gates_skipped": ["eligibility"]}

        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score

        needed = ["mortstat","permth_int","RIDAGEYR","RIAGENDR","upstream_manifold"]
        dfa = df.dropna(subset=needed).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "decision": "INCONCLUSIVE", "n": int(len(dfa)),
                    "decision_basis": f"N={len(dfa)}", "gates_passed": [], "gates_failed": ["eligibility"], "gates_skipped": []}

        mort = pd.to_numeric(dfa["mortstat"], errors="coerce")
        fu = pd.to_numeric(dfa["permth_int"], errors="coerce")
        y = ((mort==1) & (fu <= self.config.MORT_10Y_MONTHS)).astype(int).values
        events = int(y.sum())
        if events < self.config.MIN_EVENTS_H1:
            return {"status": "INSUFFICIENT_EVENTS", "decision": "INCONCLUSIVE",
                    "n": int(len(dfa)), "events": events,
                    "decision_basis": f"Events={events}<{self.config.MIN_EVENTS_H1}",
                    "gates_passed": [], "gates_failed": ["eligibility_events"], "gates_skipped": []}

        X_base = dfa[["RIDAGEYR","RIAGENDR"]].astype(float)
        X_plus = dfa[["RIDAGEYR","RIAGENDR","upstream_manifold"]].astype(float)
        cv = StratifiedKFold(n_splits=self.config.CV_FOLDS, shuffle=True, random_state=self.config.RANDOM_SEED)
        m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        auc_base = cross_val_score(m, X_base, y, cv=cv, scoring="roc_auc")
        auc_plus = cross_val_score(m, X_plus, y, cv=cv, scoring="roc_auc")
        ab, ap = float(auc_base.mean()), float(auc_plus.mean())
        delta = ap - ab
        passes = (ap >= 0.60) and (delta > 0)

        # Brier score + partial AUC (high-specificity region)
        from sklearn.metrics import brier_score_loss, roc_auc_score
        brier_base_s, brier_plus_s, pauc_base_s, pauc_plus_s = [], [], [], []
        cv2 = StratifiedKFold(n_splits=self.config.CV_FOLDS, shuffle=True, random_state=self.config.RANDOM_SEED)
        for tr_idx, te_idx in cv2.split(X_base, y):
            mb = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            mp = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            mb.fit(X_base.iloc[tr_idx], y[tr_idx])
            mp.fit(X_plus.iloc[tr_idx], y[tr_idx])
            pb = mb.predict_proba(X_base.iloc[te_idx])[:,1]
            pp = mp.predict_proba(X_plus.iloc[te_idx])[:,1]
            brier_base_s.append(brier_score_loss(y[te_idx], pb))
            brier_plus_s.append(brier_score_loss(y[te_idx], pp))
            try:
                pauc_base_s.append(roc_auc_score(y[te_idx], pb, max_fpr=0.2))
                pauc_plus_s.append(roc_auc_score(y[te_idx], pp, max_fpr=0.2))
            except Exception:
                pass

        brier_base = float(np.mean(brier_base_s)) if brier_base_s else None
        brier_plus = float(np.mean(brier_plus_s)) if brier_plus_s else None
        brier_delta = float(brier_base - brier_plus) if brier_base is not None and brier_plus is not None else None
        pauc_base = float(np.mean(pauc_base_s)) if pauc_base_s else None
        pauc_plus = float(np.mean(pauc_plus_s)) if pauc_plus_s else None
        pauc_delta = float(pauc_plus - pauc_base) if pauc_base is not None and pauc_plus is not None else None

        gp, gf = ["eligibility"], []
        (gp if ap >= 0.60 else gf).append("primary_auc")
        (gp if delta > 0 else gf).append("primary_lift")
        decision = "SUPPORTED" if passes else "FALSIFIED"

        result = {
            "status": "OK", "decision": decision,
            "gates_passed": gp, "gates_failed": gf, "gates_skipped": [],
            "n": int(len(dfa)), "events_10y": events,
            "auc_base_mean": round(ab,6), "auc_plus_mean": round(ap,6), "delta_auc": round(delta,6),
            "brier_base": round(brier_base, 6) if brier_base is not None else None,
            "brier_manifold": round(brier_plus, 6) if brier_plus is not None else None,
            "brier_delta": round(brier_delta, 6) if brier_delta is not None else None,
            "partial_auc_base": round(pauc_base, 6) if pauc_base is not None else None,
            "partial_auc_manifold": round(pauc_plus, 6) if pauc_plus is not None else None,
            "partial_auc_delta": round(pauc_delta, 6) if pauc_delta is not None else None,
            "passes_preregister": bool(passes),
            "decision_basis": f"AUC={ap:.4f}, delta={delta:.4f}",
        }
        print(f"  N={len(dfa):,} Events={events} AUC_base={ab:.4f} AUC_man={ap:.4f} delta=+{delta:.4f}")
        print(f"  Decision: {decision}")
        return result


# ============================================================================
# WEIGHTED SENSITIVITY (Chunk 3)
# ============================================================================

class WeightedSensitivity:
    def __init__(self, config):
        self.config = config

    def _pick_weight(self, df, needs_fasting):
        if needs_fasting and "WTSAF_COMB" in df.columns:
            w = pd.to_numeric(df["WTSAF_COMB"], errors="coerce")
            if w.notna().sum() > 100:
                return "WTSAF_COMB", w
        if "WTMEC_COMB" in df.columns:
            w = pd.to_numeric(df["WTMEC_COMB"], errors="coerce")
            if w.notna().sum() > 100:
                return "WTMEC_COMB", w
        return "NONE", pd.Series(np.nan, index=df.index)

    def weighted_h3(self, df):
        print(f"\n{'='*70}\nSENSITIVITY: H3 WEIGHTED\n{'='*70}")
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score

        needed = ["RIDAGEYR","RIAGENDR","LBXGLU","LBXGH","L2_metabolic","L3_immune","L5_systemic"]
        wn, wt = self._pick_weight(df, needs_fasting=True)
        dfa = df.dropna(subset=needed).copy()
        dfa["_wt"] = wt.loc[dfa.index]
        dfa = dfa.dropna(subset=["_wt"])
        dfa = dfa[dfa["_wt"] > 0]

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "weight_used": wn}

        glu = pd.to_numeric(dfa["LBXGLU"], errors="coerce")
        a1c = pd.to_numeric(dfa["LBXGH"], errors="coerce")
        y = ((glu >= self.config.DIABETES_GLUCOSE) | (a1c >= self.config.DIABETES_A1C)).astype(int).values
        if len(np.unique(y)) < 2:
            return {"status": "INSUFFICIENT_VARIATION", "weight_used": wn}

        Xa = dfa[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune"]].astype(float).values
        Xb = dfa[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune","L5_systemic"]].astype(float).values
        sw = dfa["_wt"].values

        ma = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        ma.fit(Xa, y, sample_weight=sw)
        auc_a = roc_auc_score(y, ma.predict_proba(Xa)[:,1], sample_weight=sw)

        mb = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        mb.fit(Xb, y, sample_weight=sw)
        auc_b = roc_auc_score(y, mb.predict_proba(Xb)[:,1], sample_weight=sw)

        delta = auc_b - auc_a
        flips = delta < 0

        print(f"  Weight: {wn}  N: {len(dfa):,}  wAUC: {auc_a:.4f} -> {auc_b:.4f}  d=+{delta:.4f}  flips={flips}")
        return {"status": "OK", "weight_used": wn, "n_with_weight": int(len(dfa)),
                "weighted_auc_L2_L3": round(float(auc_a),6), "weighted_auc_L2_L3_L5": round(float(auc_b),6),
                "weighted_delta_L5": round(float(delta),6), "conclusion_flips_vs_prereg": bool(flips)}

    def weighted_h1(self, df):
        print(f"\n{'='*70}\nSENSITIVITY: H1 WEIGHTED\n{'='*70}")
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score

        if "mortstat" not in df.columns:
            return {"status": "SKIPPED"}

        needed = ["mortstat","permth_int","RIDAGEYR","RIAGENDR","upstream_manifold"]
        wn, wt = self._pick_weight(df, needs_fasting=False)
        dfa = df.dropna(subset=needed).copy()
        dfa["_wt"] = wt.loc[dfa.index]
        dfa = dfa.dropna(subset=["_wt"])
        dfa = dfa[dfa["_wt"] > 0]

        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA", "weight_used": wn}

        mort = pd.to_numeric(dfa["mortstat"], errors="coerce")
        fu = pd.to_numeric(dfa["permth_int"], errors="coerce")
        y = ((mort==1) & (fu <= self.config.MORT_10Y_MONTHS)).astype(int).values
        events = int(y.sum())
        if events < self.config.MIN_EVENTS_H1:
            return {"status": "INSUFFICIENT_EVENTS", "weight_used": wn, "events": events}

        Xb = dfa[["RIDAGEYR","RIAGENDR"]].astype(float).values
        Xp = dfa[["RIDAGEYR","RIAGENDR","upstream_manifold"]].astype(float).values
        sw = dfa["_wt"].values

        mb = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        mb.fit(Xb, y, sample_weight=sw)
        auc_b = roc_auc_score(y, mb.predict_proba(Xb)[:,1], sample_weight=sw)

        mp = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
        mp.fit(Xp, y, sample_weight=sw)
        auc_p = roc_auc_score(y, mp.predict_proba(Xp)[:,1], sample_weight=sw)

        delta = auc_p - auc_b
        flips = (delta <= 0) or (auc_p < 0.60)

        print(f"  Weight: {wn}  wAUC: {auc_b:.4f} -> {auc_p:.4f}  d=+{delta:.4f}  flips={flips}")
        return {"status": "OK", "weight_used": wn, "n_with_weight": int(len(dfa)),
                "events_10y": events, "weighted_auc_base": round(float(auc_b),6),
                "weighted_auc_manifold": round(float(auc_p),6), "weighted_delta": round(float(delta),6),
                "conclusion_flips_vs_prereg": bool(flips)}


# ============================================================================
# DESIGN BOOTSTRAP (Chunk 4)
# ============================================================================

class DesignBootstrap:
    def __init__(self, config):
        self.config = config

    def _cluster_resample(self, df, rng):
        if "SDMVSTRA" not in df.columns or "SDMVPSU" not in df.columns:
            return df.sample(n=len(df), replace=True, random_state=rng)
        frames = []
        for _, sdf in df.groupby("SDMVSTRA"):
            psus = sdf["SDMVPSU"].unique()
            if len(psus) < 2:
                frames.append(sdf)
                continue
            for psu in rng.choice(psus, size=len(psus), replace=True):
                frames.append(sdf[sdf["SDMVPSU"]==psu])
        return pd.concat(frames, ignore_index=True)

    def bootstrap_h3(self, df):
        print(f"\n{'='*70}\nDESIGN BOOTSTRAP: H3\n{'='*70}")
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score

        needed = ["RIDAGEYR","RIAGENDR","LBXGLU","LBXGH","L2_metabolic","L3_immune","L5_systemic"]
        dfa = df.dropna(subset=needed).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA"}

        rng = np.random.RandomState(self.config.RANDOM_SEED)
        deltas = []
        for _ in range(self.config.BOOTSTRAP_REPS):
            boot = self._cluster_resample(dfa, rng)
            yb = ((pd.to_numeric(boot["LBXGLU"], errors="coerce") >= self.config.DIABETES_GLUCOSE) |
                  (pd.to_numeric(boot["LBXGH"], errors="coerce") >= self.config.DIABETES_A1C)).astype(int).values
            if len(np.unique(yb)) < 2: continue
            m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=rng.randint(1,99999))
            try:
                a1 = cross_val_score(m, boot[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune"]].astype(float), yb, cv=cv, scoring="roc_auc").mean()
                a2 = cross_val_score(m, boot[["RIDAGEYR","RIAGENDR","L2_metabolic","L3_immune","L5_systemic"]].astype(float), yb, cv=cv, scoring="roc_auc").mean()
                deltas.append(a2-a1)
            except: continue

        if len(deltas) < 10:
            return {"status": "INSUFFICIENT_REPS", "n_reps": len(deltas)}

        arr = np.array(deltas)
        lo, hi = float(np.percentile(arr,2.5)), float(np.percentile(arr,97.5))
        pp = float(np.mean(arr >= self.config.PREREG_AUC_DELTA))
        print(f"  {len(deltas)} reps: mean={arr.mean():.4f} CI=[{lo:.4f},{hi:.4f}] P(pass)={pp:.3f}")
        return {"status": "OK", "n_reps": len(deltas), "delta_mean": round(float(arr.mean()),6),
                "ci_95": [round(lo,6), round(hi,6)], "pass_probability": round(pp,4),
                "ci_excludes_zero": bool(lo > 0)}

    def bootstrap_h1(self, df):
        print(f"\n{'='*70}\nDESIGN BOOTSTRAP: H1\n{'='*70}")
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score

        if "mortstat" not in df.columns:
            return {"status": "SKIPPED"}

        needed = ["mortstat","permth_int","RIDAGEYR","RIAGENDR","upstream_manifold"]
        dfa = df.dropna(subset=needed).copy()
        if len(dfa) < self.config.MIN_SAMPLE_SIZE:
            return {"status": "INSUFFICIENT_DATA"}

        rng = np.random.RandomState(self.config.RANDOM_SEED)
        deltas = []
        for _ in range(self.config.BOOTSTRAP_REPS):
            boot = self._cluster_resample(dfa, rng)
            mb = pd.to_numeric(boot["mortstat"], errors="coerce")
            fb = pd.to_numeric(boot["permth_int"], errors="coerce")
            yb = ((mb==1) & (fb <= self.config.MORT_10Y_MONTHS)).astype(int).values
            if yb.sum() < 10 or len(np.unique(yb)) < 2: continue
            m = LogisticRegression(max_iter=3000, random_state=self.config.RANDOM_SEED)
            cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=rng.randint(1,99999))
            try:
                a1 = cross_val_score(m, boot[["RIDAGEYR","RIAGENDR"]].astype(float), yb, cv=cv, scoring="roc_auc").mean()
                a2 = cross_val_score(m, boot[["RIDAGEYR","RIAGENDR","upstream_manifold"]].astype(float), yb, cv=cv, scoring="roc_auc").mean()
                deltas.append(a2-a1)
            except: continue

        if len(deltas) < 10:
            return {"status": "INSUFFICIENT_REPS", "n_reps": len(deltas)}

        arr = np.array(deltas)
        lo, hi = float(np.percentile(arr,2.5)), float(np.percentile(arr,97.5))
        pp = float(np.mean(arr > 0))
        print(f"  {len(deltas)} reps: mean={arr.mean():.4f} CI=[{lo:.4f},{hi:.4f}] P(>0)={pp:.3f}")
        return {"status": "OK", "n_reps": len(deltas), "delta_mean": round(float(arr.mean()),6),
                "ci_95": [round(lo,6), round(hi,6)], "pass_probability": round(pp,4),
                "ci_excludes_zero": bool(lo > 0)}


# ============================================================================
# VISUALIZATION
# ============================================================================

class ResultsVisualizer:
    def __init__(self, config):
        self.config = config

    def plot_layer_correlations(self, df):
        layers = ["L5_systemic", "L3_immune", "L2_metabolic"]
        dfa = df[layers].dropna()
        if len(dfa) < 200: return None
        corr = dfa.corr(method="spearman")
        fig, ax = plt.subplots(figsize=(7,5))
        try:
            import seaborn as sns
            sns.heatmap(corr, annot=True, fmt=".2f", center=0, vmin=-1, vmax=1, ax=ax)
        except ImportError:
            im = ax.imshow(corr.values, vmin=-1, vmax=1)
            ax.set_xticks(range(len(layers))); ax.set_yticks(range(len(layers)))
            ax.set_xticklabels(layers, rotation=25, ha="right"); ax.set_yticklabels(layers)
            for i in range(len(layers)):
                for j in range(len(layers)):
                    ax.text(j,i,f"{corr.values[i,j]:.2f}",ha="center",va="center")
            fig.colorbar(im, ax=ax)
        ax.set_title("Layer Correlation (Spearman) - v2.0")
        out = self.config.FIGURES_DIR / "layer_correlations.png"
        plt.tight_layout(); plt.savefig(out, dpi=300, bbox_inches="tight"); plt.close()
        print(f"[SAVED] {out}")
        return out

    def plot_h3_auc(self, h3):
        if h3.get("status") != "OK": return None
        means = [h3["auc_L2_L3_mean"], h3["auc_L2_L3_L5_mean"]]
        stds = [h3["auc_L2_L3_std"], h3["auc_L2_L3_L5_std"]]
        labels = ["L2+L3", "L2+L3+L5"]
        fig, ax = plt.subplots(figsize=(7,5))
        x = np.arange(len(labels))
        ax.bar(x, means, yerr=stds, capsize=6, color=["#4a90d9","#2ecc71"])
        ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("AUC (CV)")
        ax.set_title(f"H3: L5 Increment - dAUC={h3['delta_L5']:.4f} [{h3['decision']}]")
        for i, m in enumerate(means):
            ax.text(i, m+stds[i]+0.005, f"{m:.3f}", ha="center", va="bottom")
        out = self.config.FIGURES_DIR / "h3_auc_increment.png"
        plt.tight_layout(); plt.savefig(out, dpi=300, bbox_inches="tight"); plt.close()
        print(f"[SAVED] {out}")
        return out


# ============================================================================
# DECISION ENGINE (Chunk 7)
# ============================================================================

class DecisionEngine:
    def __init__(self, config):
        self.config = config

    def compute_final_verdicts(self, results):
        verdicts = {}
        # H1
        h1p = results.get("tier3_prediction",{}).get("h1_mortality_auc_10y",{})
        h1s = results.get("sensitivity",{}).get("h1_weighted",{})
        h1b = results.get("design_uncertainty",{}).get("h1_bootstrap",{})
        verdicts["H1_shared_manifold"] = self._resolve(h1p, h1s, h1b)
        # H2
        h2 = results.get("tier2_structure",{}).get("multipath_clustering",{})
        verdicts["H2_multipath"] = {"decision": h2.get("decision","INCONCLUSIVE"),
            "decision_basis": h2.get("decision_basis",""), "gates_passed": h2.get("gates_passed",[]),
            "gates_failed": h2.get("gates_failed",[]), "gates_skipped": h2.get("gates_skipped",[])}
        # H3
        h3p = results.get("tier3_prediction",{}).get("h3_hierarchy_auc",{})
        h3s = results.get("sensitivity",{}).get("h3_weighted",{})
        h3b = results.get("design_uncertainty",{}).get("h3_bootstrap",{})
        verdicts["H3_hierarchy"] = self._resolve(h3p, h3s, h3b)
        return verdicts

    def _resolve(self, primary, sensitivity, bootstrap):
        pd_ = primary.get("decision","INCONCLUSIVE")
        sf = sensitivity.get("conclusion_flips_vs_prereg", None)
        bci = bootstrap.get("ci_excludes_zero", None)
        bpp = bootstrap.get("pass_probability", None)
        clinical = primary.get("meets_clinical_bar", None)  # H3 clinical gate
        gp = list(primary.get("gates_passed",[]))
        gf = list(primary.get("gates_failed",[]))
        gs = list(primary.get("gates_skipped",[]))

        if sensitivity.get("status") == "OK":
            (gf if sf else gp).append("sensitivity_weighted")
        else:
            gs.append("sensitivity_weighted")
        if bootstrap.get("status") == "OK":
            (gp if bci else gf).append("bootstrap_ci")
        else:
            gs.append("bootstrap_ci")

        if pd_ == "SUPPORTED":
            if sf:
                final, basis = "INCONCLUSIVE", "Primary passed but weighted reverses"
            elif bci is False and bpp is not None and bpp < 0.5:
                final, basis = "INCONCLUSIVE", "Primary passed but bootstrap unstable"
            else:
                final, basis = "SUPPORTED", "Primary+sensitivity+stability aligned"
        elif pd_ == "FALSIFIED":
            if sf is False and sensitivity.get("status") == "OK":
                final, basis = "INCONCLUSIVE", "Primary failed but weighted rescues"
            else:
                final, basis = "FALSIFIED", "Primary failed, sensitivity does not rescue"
        else:
            final, basis = "INCONCLUSIVE", primary.get("decision_basis","Insufficient data")

        return {"decision": final, "decision_basis": basis, "primary_decision": pd_,
                "sensitivity_flips": sf, "bootstrap_ci_excludes_zero": bci,
                "bootstrap_pass_probability": bpp,
                "meets_clinical_bar": clinical,
                "gates_passed": gp, "gates_failed": gf, "gates_skipped": gs}


# ============================================================================
# SUMMARY (Chunk 7)
# ============================================================================

def write_summary_md(verdicts, results, config):
    lines = [
        "# Validation Summary - Nested Control Systems Framework",
        f"## Pipeline v{PIPELINE_VERSION} | Mode: {config.mode}",
        f"**Run:** {results['metadata']['run_timestamp']}", "", "---", "",
    ]
    for hk, v in verdicts.items():
        dec = v["decision"]
        em = {"SUPPORTED": "PASS", "FALSIFIED": "FAIL", "INCONCLUSIVE": "INCONCLUSIVE"}.get(dec, "?")
        lines.append(f"### {hk}: [{em}] {dec}")
        lines.append(f"**Basis:** {v['decision_basis']}")
        if v.get("gates_passed"): lines.append(f"**Passed:** {', '.join(v['gates_passed'])}")
        if v.get("gates_failed"): lines.append(f"**Failed:** {', '.join(v['gates_failed'])}")
        if v.get("gates_skipped"): lines.append(f"**Skipped:** {', '.join(v['gates_skipped'])}")
        lines.extend(["", "---", ""])

    lines.extend([
        "## Interpretation",
        "- SUPPORTED = prereg passes AND sensitivity/stability do not overturn",
        "- FALSIFIED = prereg fails AND sensitivity does not rescue",
        "- INCONCLUSIVE = insufficient data, unstable, or conflicting signals",
    ])
    out = config.RESULTS_DIR / "summary.md"
    out.write_text("\n".join(lines))
    print(f"[SAVED] {out}")
    return out


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class FrameworkValidator:
    def __init__(self, config):
        self.config = config
        self.results = {
            "metadata": build_run_manifest(config),
            "missingness": {}, "layer_eligibility": {}, "h1_cohort": {},
            "tier2_structure": {}, "tier3_prediction": {},
            "sensitivity": {}, "design_uncertainty": {}, "verdicts": {},
        }

    def run(self):
        print(f"""
{'='*70}
  NHANES Framework Validation v{PIPELINE_VERSION}
  Mode: {self.config.mode}
{'='*70}
""")
        # Data
        dl = NHANESDownloader(self.config)
        cycle_dfs = dl.download_all_cycles()
        df = dl.merge_cycles(cycle_dfs)

        # Mortality
        mm = MortalityMerger(self.config)
        mort = mm.load_mortality_file(self.config.DATA_DIR / "linked_mortality.csv")
        df = mm.merge(df, mort)

        # Proxies
        builder = LayerProxyBuilder(self.config)
        df = builder.build_all_proxies(df)

        # Save processed
        df.to_csv(self.config.DATA_DIR / "nhanes_processed.csv", index=False)

        # Missingness + eligibility
        key_cols = [
            "RIDAGEYR","RIAGENDR","LBXGLU","LBXGH","LBXCRP","LBXWBCSI",
            "BMXBMI","BMXWAIST","LBXTR","LBDHDD","SBP_mean","DBP_mean",
            "LBXSATSI","LBXSASSI","LBXSCR","LBXSAL","SLD012","DPQ020","DPQ030","SMQ020",
            "L2_metabolic","L3_immune","L4_tissue","L5_systemic","upstream_manifold",
            "mortstat","permth_int","WTMEC2YR","WTSAF2YR","SDMVSTRA","SDMVPSU",
        ]
        self.results["missingness"] = missingness_report(df, key_cols, "Key variables")
        self.results["layer_eligibility"] = layer_eligibility_report(df, self.config)

        # Save layer eligibility
        with open(self.config.RESULTS_DIR / "missingness_by_layer.json", "w") as f:
            json.dump(self.results["layer_eligibility"], f, indent=2)

        # H1 cohort report
        self.results["h1_cohort"] = h1_cohort_report(df, self.config)
        with open(self.config.RESULTS_DIR / "h1_cohort_report.json", "w") as f:
            json.dump(self.results["h1_cohort"], f, indent=2)

        # Tier 2
        t2 = StructuralValidator(self.config)
        self.results["tier2_structure"]["hierarchical_correlations"] = t2.test_hierarchical_correlations(df)
        self.results["tier2_structure"]["multipath_clustering"] = t2.test_multipath_clustering(df)
        self.results["tier2_structure"]["shared_markers"] = t2.test_shared_markers_across_diseases(df)

        with open(self.config.RESULTS_DIR / "h2_stability.json", "w") as f:
            json.dump(self.results["tier2_structure"]["multipath_clustering"], f, indent=2, default=str)

        # Tier 3
        t3 = PredictiveValidator(self.config)
        self.results["tier3_prediction"]["h3_hierarchy_auc"] = t3.test_h3_hierarchy_auc(df)
        self.results["tier3_prediction"]["h1_mortality_auc_10y"] = t3.test_h1_mortality_auc_10y(df)

        with open(self.config.RESULTS_DIR / "h3_robustness.json", "w") as f:
            json.dump(self.results["tier3_prediction"]["h3_hierarchy_auc"], f, indent=2, default=str)

        # Sensitivity (Chunk 3)
        if self.config.mode in ("sensitivity", "full"):
            ws = WeightedSensitivity(self.config)
            self.results["sensitivity"]["h3_weighted"] = ws.weighted_h3(df)
            self.results["sensitivity"]["h1_weighted"] = ws.weighted_h1(df)
            with open(self.config.RESULTS_DIR / "sensitivity_weighted.json", "w") as f:
                json.dump(self.results["sensitivity"], f, indent=2, default=str)

        # Design bootstrap (Chunk 4)
        if self.config.mode == "full":
            db = DesignBootstrap(self.config)
            self.results["design_uncertainty"]["h3_bootstrap"] = db.bootstrap_h3(df)
            self.results["design_uncertainty"]["h1_bootstrap"] = db.bootstrap_h1(df)
            with open(self.config.RESULTS_DIR / "design_uncertainty.json", "w") as f:
                json.dump(self.results["design_uncertainty"], f, indent=2, default=str)

        # Visualizations
        viz = ResultsVisualizer(self.config)
        viz.plot_layer_correlations(df)
        viz.plot_h3_auc(self.results["tier3_prediction"]["h3_hierarchy_auc"])

        # Final verdicts (Chunk 7)
        engine = DecisionEngine(self.config)
        self.results["verdicts"] = engine.compute_final_verdicts(self.results)

        # Save all
        with open(self.config.RESULTS_DIR / "validation_results.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        with open(self.config.RESULTS_DIR / "run_manifest.json", "w") as f:
            json.dump(self.results["metadata"], f, indent=2)
        with open(self.config.RESULTS_DIR / "summary.json", "w") as f:
            json.dump(self.results["verdicts"], f, indent=2, default=str)
        write_summary_md(self.results["verdicts"], self.results, self.config)

        self._print_summary()
        return self.results

    def _print_summary(self):
        print(f"\n{'='*70}")
        print(f"VALIDATION SUMMARY v{PIPELINE_VERSION} - mode={self.config.mode}")
        print(f"{'='*70}")
        for hyp, v in self.results["verdicts"].items():
            sym = {"SUPPORTED":"Y","FALSIFIED":"X","INCONCLUSIVE":"?"}.get(v["decision"]," ")
            print(f"  [{sym}] {hyp}: {v['decision']}")
            print(f"      {v['decision_basis']}")
        print(f"{'='*70}")
        print(f"Results: {self.config.RESULTS_DIR.resolve()}")


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="NHANES Validation v2.0")
    parser.add_argument("--mode", choices=["prereg","sensitivity","full"],
                        default="prereg")
    args = parser.parse_args()
    config = Config(mode=args.mode)
    FrameworkValidator(config).run()
    print(f"\nDone (mode={args.mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
