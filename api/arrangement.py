"""arrangement.py — make the gaps DO the search, as a shared core.

The map's "arrangement" is a placeholder to truth (api/placeholders.py): a
proposed structure that ADVANCES ONLY BY SURVIVING its own disconfirmers. This
module runs those disconfirmers against the LIVE grid and reports
survived / weakened / untestable, plainly — the exploration term of the search
made real (spend on refutation, not self-reinforcement). Map never launders: an
inconvenient result is reported as found.

It is the core behind BOTH the CLI instrument (tools/probe_arrangement.py) and
the agent surfaces (GET /grid/probe, MCP tool `arrangement_probe`) — so the
operator, a person, and an agent all run the same honest test.

Pure-compute, no network, stdlib only. The hypotheses under test:
  - supersymmetry duals (order<->uncertainty, conservation<->metabolism,
    reasoning<->authority) — tested for complementarity (phi co-occurrence);
  - the refined two-pole "two trees" arrangement — found UNSUPERVISED (the
    optimal 2-cluster split of the dimensions), then interpreted.
"""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Tuple

from concordance_engine import grid as _grid

# The arrangement under test (mirrors the supersymmetry placeholder's duals).
DUALS: List[Tuple[str, str]] = [
    ("order", "uncertainty"),
    ("conservation_balance", "metabolism"),
    ("reasoning", "authority_trust"),
]
PREDICTED = {"discreteness": "continuity", "physical_substance": "abstract/spirit"}
UNPAIRED = ["encoding", "time_sequence", "symmetry"]  # no dual proposed


def _canonical() -> Dict[str, frozenset]:
    return {d: _grid.AXIS_DIMENSIONS[d]
            for d in _grid.AXIS_DIMENSIONS if not _grid.is_alias(d)}


def _phi(domains: Dict[str, frozenset], a: str, b: str) -> Dict[str, float]:
    """2x2 co-occurrence of two dimensions across domains + the phi coefficient.
    phi<0 = complementary (tend to NOT co-occur, as true opposites would);
    phi>0 = co-occur more than chance; phi~0 = independent."""
    n11 = n10 = n01 = n00 = 0
    for dims in domains.values():
        ha, hb = a in dims, b in dims
        if ha and hb: n11 += 1
        elif ha and not hb: n10 += 1
        elif hb and not ha: n01 += 1
        else: n00 += 1
    N = n11 + n10 + n01 + n00
    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    phi = ((n11 * n00 - n10 * n01) / denom) if denom else 0.0
    exp_both = ((n11 + n10) * (n11 + n01) / N) if N else 0.0
    return {"both": n11, "a_only": n10, "b_only": n01, "neither": n00,
            "phi": phi, "expected_both": exp_both, "n": N}


def _two_poles(domains: Dict[str, frozenset], dims: List[str]) -> Dict:
    """The refined hypothesis the SUSY probe pointed to: the grid's real
    complementary structure is a single abstract/formal <-> material/embodied
    axis (the "two trees"). Tested UNSUPERVISED to avoid the circularity that
    sank the duals: brute-force the optimal 2-cluster split (exact for n=11),
    then interpret."""
    phi: Dict[frozenset, float] = {}
    for a, b in itertools.combinations(dims, 2):
        phi[frozenset((a, b))] = _phi(domains, a, b)["phi"]

    def score(maskset) -> float:
        within = across = 0.0
        for a, b in itertools.combinations(dims, 2):
            p = phi[frozenset((a, b))]
            if (a in maskset) == (b in maskset):
                within += p
            else:
                across += p
        return within - across  # high = tight clusters, complementary across

    n = len(dims)
    best, best_s = None, -1e18
    scores = []
    for mask in range(1, 1 << n):
        A = frozenset(dims[i] for i in range(n) if mask & (1 << i))
        if len(A) == n:
            continue
        s = score(A)
        scores.append(s)
        if s > best_s:
            best_s, best = s, A
    B = [d for d in dims if d not in best]
    A = [d for d in best]
    mean_s = sum(scores) / len(scores)
    leans = []
    for dom, ds in domains.items():
        a_n = sum(1 for d in ds if d in best)
        b_n = sum(1 for d in ds if d in B)
        leans.append((dom, a_n - b_n, a_n, b_n))
    leans.sort(key=lambda t: t[1])
    straddlers = [d for d, lean, _, _ in leans if lean == 0]
    abstract_is_A = "reasoning" in best  # neutral anchor; an interpretation
    return {
        "cluster_A": sorted(A), "cluster_B": sorted(B),
        "abstract_pole": "A" if abstract_is_A else "B",
        # explicit pole membership for consumers (the visual colours by these)
        "abstract_dims": sorted(A) if abstract_is_A else sorted(B),
        "material_dims": sorted(B) if abstract_is_A else sorted(A),
        "best_score": round(best_s, 2), "mean_score": round(mean_s, 2),
        "lift_over_mean": round(best_s - mean_s, 2),
        "deepest_in_B": [(d, l) for d, l, *_ in leans[:5]],
        "deepest_in_A": [(d, l) for d, l, *_ in leans[-5:]],
        "n_straddlers": len(straddlers), "straddlers": straddlers[:8],
    }


def pole_count_test(domains: Dict[str, frozenset], dims: List[str], max_k: int = 3) -> Dict:
    """Does the data prefer 2 poles, or 3+? (the two-poles placeholder's own
    falsifier). Uses a k-COMPARABLE criterion — avg within-cluster phi MINUS avg
    across-cluster phi (a difference of MEANS, so it doesn't mechanically inflate
    with k the way the raw within-minus-across SUM does). Brute-forces the best
    partition for each k (exact: k=2 is 2^n, k=3 is 3^n over n=11 dims)."""
    phi: Dict[frozenset, float] = {}
    pairs = list(itertools.combinations(dims, 2))
    for a, b in pairs:
        phi[frozenset((a, b))] = _phi(domains, a, b)["phi"]
    n = len(dims)

    def cohesion(labels) -> float:
        wi = wn = ai = an = 0.0
        for a, b in pairs:
            p = phi[frozenset((a, b))]
            if labels[a] == labels[b]:
                wi += p; wn += 1
            else:
                ai += p; an += 1
        within = wi / wn if wn else 0.0
        across = ai / an if an else 0.0
        return within - across

    out: Dict[int, Dict] = {}
    for k in range(2, max_k + 1):
        best_c, best_lab = -1e18, None
        # assign each dim to one of k labels; require all k used
        for code in range(k ** n):
            lab = {}
            x = code
            for i in range(n):
                lab[dims[i]] = x % k
                x //= k
            if len(set(lab.values())) < k:
                continue
            c = cohesion(lab)
            if c > best_c:
                best_c, best_lab = c, dict(lab)
        clusters = []
        for g in range(k):
            clusters.append(sorted(d for d in dims if best_lab[d] == g))
        clusters = [c for c in clusters if c]
        clusters.sort(key=len, reverse=True)
        out[k] = {"cohesion": round(best_c, 4), "clusters": clusters}

    c2 = out[2]["cohesion"]
    c3 = out.get(3, {}).get("cohesion", c2)
    gain = round(c3 - c2, 4)
    # Calibrated, conservative — a modest gain on a small/sparse grid is not a
    # clear win. Don't overclaim in either direction.
    if gain > 0.08:
        verdict = "3+ POLES fit clearly better — two-poles WEAKENED"
    elif gain > 0.02:
        verdict = ("3 poles fit MODESTLY better (small margin, small/sparse grid) — "
                   "two-poles holds as a COARSE lens but the data leans finer")
    else:
        verdict = "2 poles is the parsimonious fit — two-poles survives this test"
    return {"by_k": out, "k3_gain_over_k2": gain, "verdict": verdict,
            "criterion": "avg within-cluster phi minus avg across-cluster phi (k-comparable)"}


def _jacobi_eigen(a: List[List[float]], iters: int = 200, tol: float = 1e-12):
    """Eigen-decomposition of a small SYMMETRIC matrix by cyclic Jacobi rotation.
    Pure Python (sovereign — no numpy). Returns (eigenvalues, eigenvectors) sorted
    by eigenvalue descending; eigenvectors[k] is the k-th unit eigenvector."""
    n = len(a)
    a = [row[:] for row in a]
    V = [[float(i == j) for j in range(n)] for i in range(n)]
    for _ in range(iters):
        p, q, mx = 0, 1, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > mx:
                    mx = abs(a[i][j]); p, q = i, j
        if mx < tol:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        th = 0.5 * math.atan2(2 * apq, (aqq - app)) if aqq != app else math.pi / 4
        c, s = math.cos(th), math.sin(th)
        for k in range(n):
            kp, kq = a[k][p], a[k][q]; a[k][p] = c * kp - s * kq; a[k][q] = s * kp + c * kq
        for k in range(n):
            pk, qk = a[p][k], a[q][k]; a[p][k] = c * pk - s * qk; a[q][k] = s * pk + c * qk
        for k in range(n):
            kp, kq = V[k][p], V[k][q]; V[k][p] = c * kp - s * kq; V[k][q] = s * kp + c * kq
    eig = [a[i][i] for i in range(n)]
    vecs = [[V[i][j] for i in range(n)] for j in range(n)]  # vecs[j] = eigenvector j
    order = sorted(range(n), key=lambda i: -eig[i])
    return [eig[i] for i in order], [vecs[i] for i in order]


def spectrum() -> Dict:
    """The map's FOURIER/SPECTRAL decomposition — its natural modes ("frequencies").

    Fourier's move: decompose a whole into the few fundamental modes that generate
    it. Generalized off the regular cycle (where the fast transform, the FFT, lives)
    to an arbitrary structure, that is the SPECTRAL decomposition — the eigenmodes
    of the dimension correlation matrix ARE the map's natural axes. The eigenvalue
    is the energy/rate carried by each mode (calibrate to source + rate of descent);
    the leading modes are the few generating forms. This is the principled tool the
    crude pole-clustering was groping toward.
    """
    domains = _canonical()
    dims = [d for d in _grid.DIMENSIONS]
    n = len(dims)
    # phi correlation matrix (diagonal 1) — the dimensions as correlated signals
    M = [[1.0 if i == j else _phi(domains, dims[i], dims[j])["phi"]
          for j in range(n)] for i in range(n)]
    eig, vec = _jacobi_eigen(M)
    tot = sum(abs(e) for e in eig) or 1.0
    modes = []
    cum = 0.0
    for k in range(n):
        cum += abs(eig[k])
        loadings = sorted(zip(dims, vec[k]), key=lambda t: -abs(t[1]))
        modes.append({
            "rank": k + 1,
            "eigenvalue": round(eig[k], 3),
            "energy_pct": round(100 * abs(eig[k]) / tot, 1),
            "cum_pct": round(100 * cum / tot, 1),
            "loadings": [(d, round(w, 2)) for d, w in loadings[:6]],
        })
    # Kaiser criterion on a correlation matrix: a real axis has eigenvalue > 1.
    effective_axes = sum(1 for e in eig if e > 1.0)
    m1 = modes[0]
    pos = [d for d, w in m1["loadings"] if w > 0][:4]
    neg = [d for d, w in m1["loadings"] if w < 0][:4]
    return {
        "modes": modes,
        "effective_axes": effective_axes,
        "effective_axes_rule": "Kaiser: count of eigenvalues > 1.0 (a real axis carries "
                               "more than one dimension's worth of variance)",
        "principal_axis": {"plus": pos, "minus": neg,
                           "reads_as": "material/embodied vs abstract/formal — the 'two trees'"
                           if ("physical_substance" in pos or "metabolism" in pos) else "(interpret)"},
        "note": ("The map's natural axes are its eigenmodes (a graph/Fourier spectral view). "
                 "Eigenvalue = energy/rate per mode. The principal mode independently confirms "
                 "the two-trees split; the count of eigenvalues>1 is the data's answer to 'how "
                 "many canonical axes.' Provisional lens — see /placeholders."),
    }


def embedding(k: int = 4) -> Dict:
    """Place every domain on the map's TOP SPECTRAL AXES (the Fourier modes).

    If the eigenmodes are the map's true axes (see spectrum()), then a domain's
    natural coordinate is its PROJECTION onto each mode: coord_m = sum over the
    domain's dimensions of that mode's eigenvector loading. mode 1 is the
    abstract<->material axis; modes 2..k are the next frequencies. This is the map
    of reality drawn on the axes the data itself revealed — a spectral embedding.
    """
    domains = _canonical()
    dims = [d for d in _grid.DIMENSIONS]
    n = len(dims)
    M = [[1.0 if i == j else _phi(domains, dims[i], dims[j])["phi"]
          for j in range(n)] for i in range(n)]
    eig, vec = _jacobi_eigen(M)
    di = {d: i for i, d in enumerate(dims)}
    k = max(2, min(k, n))
    coords = {}
    for dom, ds in domains.items():
        coords[dom] = [round(sum(vec[m][di[d]] for d in ds if d in di), 4) for m in range(k)]
    axes = []
    for m in range(k):
        load = sorted(zip(dims, vec[m]), key=lambda t: -abs(t[1]))
        axes.append({
            "mode": m + 1, "eigenvalue": round(eig[m], 3),
            "plus": [d for d, w in load if w > 0][:3],
            "minus": [d for d, w in load if w < 0][:3],
        })
    return {
        "coords": coords, "axes": axes, "k": k, "n_domains": len(coords),
        "note": ("Each domain placed on the map's top spectral axes (the Fourier modes). "
                 "Coordinate m = the domain's projection onto eigenmode m; mode 1 is the "
                 "abstract<->material axis. The map of reality drawn on its own found axes. "
                 "Provisional lens — see /placeholders (fourier_spectral_arrangement)."),
    }


def tune_test(n_null: int = 200, seed: int = 1729) -> Dict:
    """Is the map MORE in tune than chance? — Matt's criterion ("when the tune is
    correct, the theories will be correct") made rigorous, so a near-miss can't be
    laundered into "we're close."

    Compares the REAL grid's spectral cents-error (how out of tune it is) to the
    distribution from RANDOMIZED grids (each domain keeps its NUMBER of dimensions;
    which ones is shuffled). If the real grid beats the null, the near-tune is
    signal — the arrangement is genuinely close to correct. If it sits inside the
    null, it is not close yet — but the null's minimum shows a more in-tune
    arrangement exists in the space to tune toward.
    """
    import random as _random
    from api import harmonics as _h
    domains = _canonical()
    dims = [d for d in _grid.DIMENSIONS]
    n = len(dims)
    di = {d: i for i, d in enumerate(dims)}

    def err_for(assign):  # assign: domain -> set of dim indices
        cols = [[1 if i in assign[d] else 0 for d in domains] for i in range(n)]

        def phi(i, j):
            a, b = cols[i], cols[j]
            n11 = n10 = n01 = n00 = 0
            for x, y in zip(a, b):
                if x and y: n11 += 1
                elif x: n10 += 1
                elif y: n01 += 1
                else: n00 += 1
            den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
            return (n11 * n00 - n10 * n01) / den if den else 0.0

        M = [[1.0 if i == j else phi(i, j) for j in range(n)] for i in range(n)]
        eig, _ = _jacobi_eigen(M)
        r = _h.spectrum_as_music([e for e in eig if e > 0])
        return r.get("mean_cents_error")

    real_assign = {d: set(di[x] for x in ds if x in di) for d, ds in domains.items()}
    real = err_for(real_assign)
    degs = {d: len(real_assign[d]) for d in domains}
    rng = _random.Random(seed)
    nulls = []
    for _ in range(max(20, n_null)):
        a = {d: set(rng.sample(range(n), degs[d])) for d in domains}
        e = err_for(a)
        if e is not None:
            nulls.append(e)
    nulls.sort()
    N = len(nulls) or 1
    better = sum(1 for x in nulls if x <= real)
    p = round(better / N, 3)
    beats = real < nulls[N // 2]
    return {
        "real_cents_error": round(real, 1),
        "null_min": round(nulls[0], 1), "null_median": round(nulls[N // 2], 1),
        "null_max": round(nulls[-1], 1), "n_null": N,
        "p_value": p, "beats_chance": bool(p < 0.05),
        "in_tune_arrangement_exists_at": round(nulls[0], 1),
        "verdict": ("BEATS CHANCE — the arrangement is more in tune than random; the near-tune is "
                    "signal, we are close to a correct arrangement." if p < 0.05 else
                    "AT CHANCE — the current arrangement is NOT more in tune than random; we do "
                    "NOT yet have the right answers. An in-tune arrangement exists in the space "
                    "(null_min) — tune toward it."),
        "criterion": ("When the tune is correct, the theories will be correct (Matt). Tested "
                      "against a shuffled-grid null so a near-miss is not laundered into 'close'."),
    }


def probe(deep: bool = False) -> Dict:
    """Run all disconfirmers against the live grid; return the structured report.

    deep=True also runs the (slower, ~2s) 2-pole vs 3-pole test — whether the
    data prefers more poles (the two-poles placeholder's own falsifier). Off by
    default so the endpoint stays fast."""
    domains = _canonical()
    dims = [d for d in _grid.DIMENSIONS]
    report: Dict = {"n_domains": len(domains), "n_dimensions": len(dims)}

    # U1 / F1: domains that break the pairing
    paired = set()
    for a, b in DUALS:
        paired.add(a); paired.add(b)
    paired |= set(PREDICTED.keys())
    breakers = sorted(d for d, ds in domains.items() if ds and not (set(ds) & paired))
    report["F1_breakers"] = breakers

    # F3 / U3: are the proposed duals more complementary than random pairs?
    all_pairs = []
    for a, b in itertools.combinations(dims, 2):
        st = _phi(domains, a, b)
        all_pairs.append((a, b, st["phi"], st["both"], st["expected_both"]))
    all_pairs.sort(key=lambda t: t[2])
    rank_of = {frozenset((a, b)): i for i, (a, b, *_) in enumerate(all_pairs)}
    n_pairs = len(all_pairs)

    dual_results = []
    for a, b in DUALS:
        st = _phi(domains, a, b)
        r = rank_of.get(frozenset((a, b)))
        dual_results.append({
            "pair": f"{a} <-> {b}", "phi": round(st["phi"], 3),
            "both": st["both"], "expected_both": round(st["expected_both"], 2),
            "complementary": st["phi"] < -0.05,
            "rank_by_complementarity": r, "of": n_pairs,
            "percentile": round(100 * (1 - r / max(1, n_pairs - 1)), 0) if r is not None else None,
        })
    report["duals"] = dual_results

    phis = sorted(p[2] for p in all_pairs)
    report["all_pairs_phi_median"] = round(phis[len(phis) // 2], 3)
    report["all_pairs_phi_min"] = round(phis[0], 3)
    report["most_complementary_overall"] = [
        {"pair": f"{a} <-> {b}", "phi": round(ph, 3)} for a, b, ph, *_ in all_pairs[:5]
    ]

    # F2 / U2: the predicted-missing partners (untestable from current grid)
    pred = []
    for present, missing in PREDICTED.items():
        carriers = sorted(d for d, ds in domains.items() if present in ds)
        pred.append({"present_axis": present, "predicted_partner": missing,
                     "present_carriers": len(carriers), "testable_now": False,
                     "note": (f"no '{missing}' dimension exists in the grid; whether a real "
                              f"family of domains carries it is an OPEN prediction, not "
                              f"confirmable from current data.")})
    pred.sort(key=lambda p: p["present_carriers"])
    report["F2_predicted_partners"] = pred

    # Refined hypothesis: the unsupervised 2-pole split
    report["two_poles"] = _two_poles(domains, dims)

    # The map's spectral decomposition — its natural modes (the Fourier lens). Fast.
    report["spectrum"] = spectrum()

    # The two-poles placeholder's own falsifier: do 3+ poles fit better? (slow)
    if deep:
        report["pole_count"] = pole_count_test(domains, dims, max_k=3)

    n_complementary = sum(1 for d in dual_results if d["complementary"])
    report["verdicts"] = {
        "F1_no_unplaceable_domain": "SURVIVED (weak)" if not breakers
            else f"WEAKENED — {len(breakers)} domain(s) sit only on unpaired axes",
        "F1_note": ("nearly every domain touches reasoning or physical_substance, both "
                    "paired — so 'placed by the symmetry' is close to trivial; treat as weak."),
        "F3_duals_are_complementary":
            f"{n_complementary}/{len(DUALS)} proposed duals are complementary (phi<-0.05)",
        "F3_note": ("if the duals are NOT more complementary than typical pairs, the symmetry "
                    "is decoration, not structure (F3 fires)."),
        "F2_predicted_partners": "UNTESTABLE from current grid (no such dimension) — honest gap.",
    }
    report["what_is_this"] = ("Disconfirmers run against the live grid. A placeholder "
                              "advances only by SURVIVING these — evidence to weigh, never a "
                              "self-declared verdict (the apex stays reserved). See /placeholders.")
    return report


def fmt(report: Dict) -> str:
    """Human-readable report (used by the CLI)."""
    L = []
    L.append("=" * 64)
    L.append("ARRANGEMENT PROBE — running the placeholder's own disconfirmers")
    L.append(f"{report['n_domains']} canonical domains x {report['n_dimensions']} dimensions")
    L.append("=" * 64)

    L.append("\nU1/F1 — domains that BREAK the pairing (sit only on unpaired axes):")
    if report["F1_breakers"]:
        for d in report["F1_breakers"]:
            L.append(f"   ! {d}")
    else:
        L.append("   none — every domain touches at least one paired axis.")
    L.append(f"   {report['verdicts']['F1_no_unplaceable_domain']}")
    L.append(f"   ({report['verdicts']['F1_note']})")

    L.append("\nF3/U3 — are the proposed duals COMPLEMENTARY (phi<0 = tend not to co-occur)?")
    L.append(f"   median phi over all pairs: {report['all_pairs_phi_median']}  "
             f"(most complementary overall: {report['all_pairs_phi_min']})")
    for d in report["duals"]:
        tag = "complementary" if d["complementary"] else "NOT complementary"
        L.append(f"   {d['pair']:42}  phi={d['phi']:+.3f}  both={d['both']} "
                 f"(exp {d['expected_both']})  rank {d['rank_by_complementarity']}/{d['of']}  [{tag}]")
    L.append("   most complementary pairs in the whole grid:")
    for p in report["most_complementary_overall"]:
        L.append(f"      {p['pair']:42} phi={p['phi']:+.3f}")
    L.append(f"   {report['verdicts']['F3_duals_are_complementary']}")
    L.append(f"   ({report['verdicts']['F3_note']})")

    L.append("\nF2/U2 — predicted-missing partners (weakest first):")
    for p in report["F2_predicted_partners"]:
        L.append(f"   {p['present_axis']} -> {p['predicted_partner']} "
                 f"(present axis carried by {p['present_carriers']} domains)")
        L.append(f"      {p['note']}")
    L.append(f"   {report['verdicts']['F2_predicted_partners']}")

    tp = report["two_poles"]
    L.append("\nREFINED HYPOTHESIS — the unsupervised 2-pole split (the 'two trees'?):")
    L.append(f"   best split score {tp['best_score']} vs mean {tp['mean_score']} "
             f"(lift +{tp['lift_over_mean']} — higher = a real 2-cluster structure)")
    _ab = tp["abstract_pole"]
    L.append(f"   cluster A {'(reads as abstract/formal)' if _ab=='A' else '(reads as material)'}: {', '.join(tp['cluster_A'])}")
    L.append(f"   cluster B {'(reads as abstract/formal)' if _ab=='B' else '(reads as material/embodied)'}: {', '.join(tp['cluster_B'])}")
    L.append(f"   straddlers (sit equally on both — the bridge): {tp['n_straddlers']} "
             f"-> {', '.join(tp['straddlers']) or 'none'}")
    L.append("   deepest in cluster A: " +
             ", ".join(f"{d}({l:+d})" for d, l in tp["deepest_in_A"]))
    L.append("   deepest in cluster B: " +
             ", ".join(f"{d}({l:+d})" for d, l in tp["deepest_in_B"]))
    L.append("   (clusters are data-chosen, not imposed; the abstract/material reading "
             "is an interpretation. A 2-pole fit to a small/sparse grid can be an artifact.)")

    sp = report.get("spectrum")
    if sp:
        L.append("\nSPECTRUM — the map's natural modes (the Fourier/spectral lens):")
        L.append(f"   effective axes (eigenvalue>1, Kaiser): {sp['effective_axes']}")
        for m in sp["modes"][:4]:
            load = " ".join("%s%s%.2f" % (d, "+" if w >= 0 else "-", abs(w)) for d, w in m["loadings"][:5])
            L.append(f"   mode {m['rank']}: eig {m['eigenvalue']:+.2f} ({m['energy_pct']}%, cum {m['cum_pct']}%)  {load}")
        pa = sp["principal_axis"]
        L.append(f"   principal axis: [{', '.join(pa['plus'])}] vs [{', '.join(pa['minus'])}] — {pa['reads_as']}")

    pc = report.get("pole_count")
    if pc:
        L.append("\nHOW MANY POLES? — does the data prefer 2 or 3+? (k-comparable cohesion):")
        for k, v in pc["by_k"].items():
            L.append(f"   k={k}  cohesion={v['cohesion']}")
            for c in v["clusters"]:
                L.append(f"        {', '.join(c)}")
        L.append(f"   k=3 gain over k=2: {pc['k3_gain_over_k2']:+}")
        L.append(f"   {pc['verdict']}")

    L.append("\n" + "-" * 64)
    L.append("A placeholder advances only by SURVIVING these. This is evidence to")
    L.append("weigh, never a self-declared confirmation (the apex stays reserved).")
    return "\n".join(L)
