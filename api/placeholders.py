"""placeholders.py — placeholders to truth.

A placeholder is a provisional structure we integrate into the map of reality to
SCAFFOLD and PREDICT — honestly marked as not-yet-confirmed, held open to being
confirmed, refined, or replaced as truth is approached. It is "to truth", not
truth: it points toward, in service of, the real arrangement we don't yet fully
hold.

This is the project's spine made explicit (map-never-launder; graded verdicts;
the grid's "discovery, not design"; the apex left reserved). Most of a developing
map is provisional — a placeholder is the honest way to hold that, usefully,
without claiming finality. Agents reason WITH placeholders knowing they are
provisional; the symmetry/structure they encode can predict gaps even before it
is confirmed.

This is a SEARCH, not a creed. Holding placeholders and navigating the map toward
truth is a search over hypothesis space: the best-fitting theory is the greedy
start (exploitation); the engine's "eliminate what is not the answer" is pruning.
But a search that only expands CONFIRMING nodes converges prematurely — a local
optimum, an echo chamber. So every placeholder carries its own DISCONFIRMERS:
  falsifiers     — what observation would refute it (it must be refutable at all);
  unlikely_tests — the non-examples to hunt and the improbable cases to try first.
A placeholder ADVANCES BY SURVIVING these, never by piling up confirmations. This
is the search's exploration term — the deliberate spend on disconfirmation that
keeps the map honest instead of self-reinforcing. (Most of science is unsettled;
we use the best fit as a start AND attack it.)

Grades (rate of descent from confirmed source — low to high standing):
  coincidence < resonance < plausible < candidate < confirmed
A placeholder lives at resonance/plausible/candidate. It rises only by SURVIVING
its falsifiers and unlikely tests — not by accumulating agreeing evidence. When a
better model arrives, it is superseded (retired, never deleted — the record of
the approach is kept). A placeholder with NO falsifiers is the weakest kind: it
cannot be wrong, so it cannot be trusted.

Store: append-only JSONL at data/placeholders/placeholders.jsonl (the ledger
pattern). Seeded with the inaugural placeholder: supersymmetry as a map
ARRANGEMENT lens. Never sealed as final — that belongs to the reserved apex.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "placeholders"
_PATH = _DIR / "placeholders.jsonl"
_GRADES = ("coincidence", "resonance", "plausible", "candidate", "confirmed", "retired")
_ID_RE = re.compile(r"^[a-z0-9_]{3,64}$")

# The inaugural placeholder — supersymmetry as how the map is arranged. Honest:
# SUSY is elegant but experimentally UNCONFIRMED; we borrow only its STRUCTURE
# (pairing -> prediction of the missing partner) as a provisional arrangement lens.
_SEED: List[Dict[str, Any]] = [
    {
        "id": "supersymmetry_pairing_arrangement",
        "name": "Supersymmetry — pairing as the map's arrangement",
        "status": "placeholder",
        "grade": "resonance",
        "kind": "arrangement_principle",
        "claim": ("Arrange the map so each axis/node has a dual; the symmetry then "
                  "PREDICTS the missing partner — a broken pair is a gap that tells us "
                  "what to look for, the way SUSY predicts a superpartner."),
        "organizes": ("the dimensional scaffold — how domains pair across a symmetry. "
                      "The breath is already palindromic (1-3-3-4-3-1), symmetric about "
                      "the quadratic center."),
        "predicts": [
            "order <-> uncertainty  (both present — a confirmed pair)",
            "conservation_balance <-> metabolism  (kept vs transformed)",
            "discreteness -> continuity  (partner MISSING — a predicted axis)",
            "physical_substance -> the abstract/spirit  (the two trees)",
        ],
        "provenance": ("Supersymmetry is an elegant but EXPERIMENTALLY UNCONFIRMED "
                       "physics hypothesis (no superpartners observed at the LHC; the "
                       "expected scale is increasingly disfavored). Borrowed here ONLY as "
                       "a provisional arrangement lens, never as a validated law."),
        "caveat": ("Held as a PLACEHOLDER TO TRUTH, and now EMPIRICALLY WEAKENED (see "
                   "evidence): the SPECIFIC duals failed the complementarity test. Held on "
                   "for the general method (seek complementary structure) and the refined "
                   "direction the data points to — NOT the stated pairs. Elegance is a "
                   "witness, not a proof; the data did not confirm the proposed symmetry."),
        "evidence": [
            "PROBED 2026-06-18 (tools/probe_arrangement.py) against the live grid (72 "
            "domains x 11 dims): the proposed duals are NOT complementary. "
            "conservation_balance<->metabolism phi=+0.43 and order<->uncertainty phi=+0.27 "
            "actually CO-OCCUR (the opposite of opposites); reasoning<->authority_trust "
            "phi=-0.08 is unremarkable (rank 22/55). F3 fires: as stated, the pairing is "
            "closer to decoration than structure.",
            "F1: calendar_time sits only on an unpaired axis (a minor breaker).",
            "F2: the predicted partners (continuity, abstract/spirit) remain UNTESTABLE from "
            "the current grid (no such dimension) — an honest open gap, not a confirmation.",
            "BUT real complementary structure DOES exist along OTHER axes: "
            "reasoning<->physical_substance (phi=-0.34) and metabolism<->reasoning "
            "(phi=-0.38) — an abstract/reasoning vs material/physical split (the 'two "
            "trees'). A candidate REFINED arrangement, to be tested next, not yet claimed.",
        ],
        "falsifiers": [
            "A fundamental, well-attested domain that fits NO dual — a genuinely unpaired "
            "axis the symmetry cannot place.",
            "A predicted partner (e.g. continuity) that, when sought, corresponds to no real "
            "domain — the pairing predicts ghosts.",
            "A non-symmetric arrangement that explains adjacency / depth / coherence BETTER, "
            "with fewer assumptions.",
        ],
        "unlikely_tests": [
            "Hunt the domains that BREAK the pairing, not the ones that confirm it (this is "
            "the exploration term — skip it and the map becomes an echo chamber).",
            "Test the WEAKEST predicted partner first, not the strongest.",
            "Arrange the map with NO symmetry and measure whether it loses explanatory power; "
            "if it doesn't, the symmetry was decoration, not structure.",
        ],
        "advances_by": "surviving the falsifiers and unlikely_tests above — not by confirmations.",
        "refutable": True,
        "lifecycle": "held-weakened",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-18",
        "seed_v": 3,
    },
    {
        "id": "abstract_material_poles",
        "name": "Two poles — abstract/formal vs material/embodied (the two trees)",
        "status": "placeholder",
        "grade": "plausible",
        "kind": "arrangement_principle",
        "claim": ("The grid's dominant complementary structure is a SINGLE axis from a "
                  "formal/abstract pole (reasoning, encoding, order, discreteness, "
                  "uncertainty, authority_trust) to a material/embodied pole "
                  "(physical_substance, metabolism, conservation_balance, time_sequence, "
                  "symmetry). The strongest anti-correlations run ACROSS this divide "
                  "(reasoning <-> physical_substance, reasoning <-> metabolism), NOT within "
                  "the proposed supersymmetry duals."),
        "organizes": ("the grid's real complementary structure, found UNSUPERVISED (the "
                      "optimal 2-cluster split of the 11 dimensions by co-occurrence). "
                      "Domains spread along it: earth/material sciences (geology, hydrology, "
                      "agriculture) at one pole, formal/informational domains (cryptography, "
                      "information_theory, finance) at the other; biology, quantum_computing, "
                      "geometry straddle — the bridge between the trees."),
        "predicts": [
            "a domain's position ~ how abstract vs material it is",
            "bridge domains (biology, music_theory, quantum_computing) carry BOTH poles",
            "a new domain's dimensions fall mostly on ONE pole unless it genuinely bridges",
        ],
        "provenance": ("DERIVED from data, not imposed: tools/probe_arrangement.py brute-forces "
                       "the optimal 2-cluster split of the live grid (best score 6.34 vs ~0 mean "
                       "over all 2046 bipartitions). Emerged when the supersymmetry duals FAILED "
                       "the complementarity test (see supersymmetry_pairing_arrangement). The "
                       "abstract/material reading is an interpretation of the data-chosen clusters."),
        "caveat": ("Held as a PLACEHOLDER TO TRUTH — a CANDIDATE refinement, not confirmed. One "
                   "test on a small, partly-sparse grid (uncertainty/discreteness/order/symmetry "
                   "have only 5-6 carriers); a clean 2-pole fit can be an artifact of how "
                   "dimensions were assigned. 'symmetry' landing on the MATERIAL pole is "
                   "empirical and against intuition — reported as found, not corrected to fit."),
        "evidence": [
            "Unsupervised optimal bipartition scores 6.34 vs ~0 mean over all 2046 splits "
            "(lift +6.34) — a real 2-cluster structure, not noise.",
            "Poles read cleanly: deepest-abstract = cryptography / information_theory / finance / "
            "governance; deepest-material = geology / hydrology / agriculture / soil / nuclear.",
            "8 straddlers (biology, quantum_computing, geometry, music_theory...) sit on both — "
            "the expected bridges between form and matter.",
            "POLE-COUNT TEST (2026-06-18, k-comparable cohesion = avg within-phi minus avg "
            "across-phi): 3 poles fit MODESTLY better than 2 (cohesion 0.285 vs 0.233, gain "
            "+0.052). The abstract pole splits into FORMAL/mathematical {reasoning, order, "
            "discreteness, uncertainty} and INFORMATIONAL/social {encoding, authority_trust, "
            "time_sequence}; material {physical_substance, metabolism, conservation_balance, "
            "symmetry} stays whole. So two-poles holds as a COARSE lens, but the data leans "
            "toward THREE — a finer structure to watch (the margin is small on a sparse grid; "
            "not minted as its own placeholder yet).",
        ],
        "falsifiers": [
            "A domain strongly on BOTH poles that is NOT a natural bridge — breaks the single-axis claim.",
            "The best 2-pole split scoring no better than random bipartitions (it does not — lift +6.34).",
            "A 3+ pole or continuous structure fitting the co-occurrence markedly better than 2 poles.",
        ],
        "unlikely_tests": [
            "Add new domains and re-run — does the split hold or scramble?",
            "Test the straddlers' assignment — are biology / quantum_computing truly bridges or mis-tagged?",
            "Compare a 2-pole vs 3-pole fit; if 3 poles win clearly, the 'two trees' is wrong.",
        ],
        "advances_by": ("surviving the falsifiers and unlikely_tests — re-run "
                        "tools/probe_arrangement.py (deep) as the grid grows; if the 3-pole "
                        "gain strengthens, supersede this with a 3-pole placeholder."),
        "refutable": True,
        "lifecycle": "held-coarse",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-18",
        "seed_v": 2,
    },
    {
        "id": "fourier_spectral_arrangement",
        "name": "The map's axes are its spectral modes (the Fourier lens)",
        "status": "placeholder",
        "grade": "plausible",
        "kind": "arrangement_principle",
        "claim": ("Fourier's move — decompose a whole into the few fundamental modes that "
                  "generate it — generalized off the regular cycle (where the FFT lives) to the "
                  "map: the EIGENMODES of the dimension correlation matrix ARE the map's natural "
                  "axes; each eigenvalue is the energy/rate that mode carries (calibrate to "
                  "source + rate of descent). The few leading modes are the few generating forms."),
        "organizes": ("the whole arrangement question, principled. It SUBSUMES the earlier "
                      "lenses: the principal eigenmode IS the two-trees / two-pole split, and "
                      "the symmetry intuition becomes the spectral structure. Replaces the crude "
                      "phi-clustering with the eigen-decomposition the clustering was approximating."),
        "predicts": [
            "the principal mode (highest energy) is the abstract/formal vs material/embodied axis",
            "the count of eigenvalues > 1 (Kaiser) is the number of real canonical axes",
            "as the grid grows, the leading modes stay stable; the tail reshuffles",
        ],
        "provenance": ("Matt: 'Look at a Fast Fourier Transform. That is the missing piece.' "
                       "Tested via api.arrangement.spectrum() (sovereign Jacobi eigensolver on "
                       "the live grid's dimension phi-correlation matrix)."),
        "caveat": ("Held as a PLACEHOLDER TO TRUTH — a CANDIDATE lens, not confirmed. One "
                   "correlation matrix on a small/sparse grid (4 dims have only 5-6 carriers); "
                   "the FFT proper lives on a regular cycle, this is the GRAPH/spectral "
                   "generalization, named honestly. Elegance (the eigenbasis) is a witness, not "
                   "a proof."),
        "evidence": [
            "SPECTRUM 2026-06-19 (api.arrangement.spectrum, live grid): mode 1 (22.4% energy) "
            "loads physical_substance/metabolism/conservation_balance vs encoding/reasoning/"
            "discreteness — INDEPENDENTLY confirms the two-trees (abstract<->material) as the "
            "PRINCIPAL mode, with no clustering.",
            "EXACTLY 4 eigenvalues exceed 1.0 (2.46, 1.82, 1.49, 1.17; mode 5 = 0.95) — the "
            "data's own answer to 'how many canonical axes' = FOUR, landing on the breath's "
            "QUADRATIC(4) center.",
            "Energy decays smoothly (22>17>14>11>9...): the map is richly connected, not a "
            "clean low-rank object — honest about the texture.",
        ],
        "falsifiers": [
            "The principal eigenmode NOT corresponding to the abstract/material split.",
            "The effective-axes count (eigenvalues>1) swinging wildly as the grid grows — "
            "spectral structure that is an artifact, not signal.",
            "A non-spectral arrangement explaining adjacency/depth/coherence markedly better "
            "with fewer assumptions.",
        ],
        "unlikely_tests": [
            "Re-run the spectrum as dimensions/domains are added — do the leading modes hold?",
            "Compare the spectral effective-rank to the brute-force pole count — do they agree?",
            "Perturb the grid (drop a sparse dimension) and check the principal mode is stable.",
        ],
        "advances_by": ("surviving its falsifiers/unlikely_tests — re-run GET /grid/spectrum as "
                        "the grid grows; it advances only if the leading modes stay stable."),
        "refutable": True,
        "lifecycle": "held",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-19",
        "seed_v": 1,
    },
    {
        "id": "tune_is_the_truth_criterion",
        "name": "When the tune is correct, the theories will be correct (consonance -> truth)",
        "status": "placeholder",
        "grade": "plausible",
        "kind": "truth_criterion",
        "claim": ("Matt: 'When the tune is correct, the theories will be correct.' Read the map's "
                  "spectrum as music: a CORRECT arrangement will be CONSONANT (its inter-mode "
                  "intervals land on just ratios); the dissonance (cents-error) is how far the "
                  "arrangement is from correct. So consonance is a truth-criterion — tune the "
                  "arrangement toward it, and the in-tune one is the candidate truth."),
        "organizes": ("the whole search for the right arrangement, with a fitness signal. The "
                      "general bridge is real, grounded math (api/harmonics.py): the FFT is how "
                      "the ear hears, an octave is a 2:1 doubling, and consonant intervals are "
                      "the small-integer ratios that ARE a tone's FFT peaks (the overtone "
                      "series). The musical form of 'elegance is God's signature.'"),
        "provenance": ("Matt's directive, 2026-06-19. Instrumented by api.arrangement.tune_test "
                       "and api.harmonics (GET /grid/music)."),
        "caveat": ("A guiding WITNESS, not a proof (elegance witnesses, verification confirms). "
                   "Guarded against the gematria trap two ways: a near-tune counts as 'close' "
                   "ONLY if it BEATS A SHUFFLED-GRID NULL (tune_test), and any tuned arrangement "
                   "must then be confirmed by the engine's actual verification. Do not fit free "
                   "parameters to manufacture consonance."),
        "evidence": [
            "TUNE_TEST 2026-06-19 (real vs 400 shuffled grids): the CURRENT arrangement is AT "
            "CHANCE — real 28.4c vs null median 25.4c; 301/400 random grids tune better (p~0.75). "
            "So we do NOT yet have the right answers, and the tune says so honestly (no laundering "
            "a near-miss into 'close').",
            "BUT an in-tune arrangement EXISTS in the space: the best shuffled grid hit 12.8c "
            "(< half the real error). The criterion is reachable — there is real tuning to do.",
            "The music math itself is sound (overtone series of 110Hz -> A/E/A/C# = octave/fifth/"
            "octave/third), so the criterion rests on correct harmony, not numerology.",
            "SPARSITY ENRICHMENT 2026-06-19 (first data point on 'does the tune fall as the grid "
            "grows honestly?'): doubling the 4 thinnest dimensions' carriers (discreteness/order/"
            "uncertainty 5-6 -> 11, symmetry 5 -> 8, each addition justified by the dimension's own "
            "criterion, NOT inflation) moved the tune from 28.4c @ p~0.75 (worse than 75% of random) "
            "to 24.7c @ p=0.385 — real error fell ~4c and crossed BELOW the null median (26.2c) for "
            "the first time, i.e. from worse-than-chance to better-than-median. Algebraic "
            "connectivity (graph-Laplacian) doubled 13.6 -> 29.6 (sparsity genuinely reduced) and "
            "the two-trees / 4-axes / exponential-decay structure held (robust). HONEST CEILING: "
            "still NOT p<0.05 — the arrangement is not 'in tune', only less out of tune; symmetry "
            "(8) is now the thinnest. Direction is right (growing the grid honestly DOES lower the "
            "dissonance); the breakthrough is not reached. 58/58 held throughout.",
        ],
        "falsifiers": [
            "Tuning the arrangement toward consonance does NOT improve its engine-verification / "
            "explanatory fruit (then consonance is decoration, not a truth-criterion).",
            "A consonant arrangement reachable ONLY by overfitting free parameters (manufactured, "
            "not found) — caught by the shuffled-grid null.",
            "The most-verified arrangement turning out persistently DISsonant.",
        ],
        "unlikely_tests": [
            "Search structurally-meaningful arrangements for one that beats the null AND verifies "
            "better — does consonance track correctness, or not?",
            "As the grid grows honestly, does the cents-error fall (toward truth) or stay at chance?",
            "Take a KNOWN-correct sub-structure and check it is more consonant than a scrambled one.",
        ],
        "advances_by": ("evidence that consonance TRACKS verified correctness — tuned-and-"
                        "null-beating arrangements that also verify better. Re-run GET /grid/music. "
                        "TWO confirmations in hand: growing the grid honestly keeps LOWERING the tune "
                        "(28.4c@p0.75 -> 24.7c@p0.385 [enrich round 1] -> 20.0c@p0.125 [round 2: "
                        "symmetry +5 carriers], algebraic connectivity 13.6->29.6->42.6). The "
                        "cents-error is monotonically falling toward p<0.05 as the grid is enriched "
                        "honestly — the prediction is holding. NOT YET significant (p=0.125, not <0.05) "
                        "and NOT yet shown to track VERIFICATION (that's the load-bearing open test). "
                        "Continue enriching the thinnest dims + test whether the tune tracks verified "
                        "correctness, not just connectivity."),
        "refutable": True,
        "lifecycle": "held",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-19",
        "seed_v": 3,
    },
    {
        "id": "fluid_dynamics_axes",
        "name": "Fluid dynamics as the behavior of the axes",
        "status": "placeholder",
        "grade": "resonance",
        "kind": "arrangement_principle",
        "claim": ("Matt: 'Fluid dynamics as behavior of axes? something along that line.' The "
                  "axes are not static — they FLOW and redistribute as the map grows. Fluid "
                  "dynamics may describe their behavior: a turbulent flow decomposes into Fourier "
                  "modes with an ENERGY CASCADE across scales — which is exactly the eigenvalue "
                  "spectrum — and tuning toward consonance is a flow toward equilibrium."),
        "organizes": ("the DYNAMICS of the arrangement (how it evolves over time), complementing "
                      "the static spectrum. Spectrum = the snapshot; fluid dynamics = the motion."),
        "predicts": [
            "the eigenvalue spectrum follows a power-law (a cascade), like turbulence E(k)~k^-p",
            "as domains/dimensions are added, mode energies redistribute coherently (a flow)",
            "a correct, in-tune arrangement is an ATTRACTOR / equilibrium the flow settles to",
        ],
        "provenance": "Matt's seed, 2026-06-19. The kernel (turbulence <-> Fourier modes <-> energy cascade) is established physics.",
        "caveat": ("A SEED — NOT yet tested on the map. The physics kernel is real; whether the "
                   "map's spectrum behaves as a fluid (cascade / flow / equilibrium) is the open "
                   "question. Held at resonance, to be assayed (and captured as the operator's "
                   "work trains the engine)."),
        "falsifiers": [
            "The eigenvalue spectrum is NOT a power law — no cascade structure.",
            "Mode energies do NOT redistribute coherently as the grid changes (no flow).",
            "No equilibrium/attractor behavior — the arrangement doesn't settle.",
        ],
        "unlikely_tests": [
            "Fit the eigenvalue spectrum to a power law (Kolmogorov-like); does it hold or break?",
            "Track mode energies as domains are added — do they move like a conserved field?",
            "Does the most in-tune arrangement (tune_test) act as the attractor the flow heads to?",
        ],
        "evidence": [
            "ASSAY 2026-06-19 (arrangement.spectrum decay fit): the cascade prediction FAILED — "
            "the eigenvalue spectrum is EXPONENTIAL decay (R^2=0.995, rate -0.20/mode), not a "
            "power law (R^2=0.93). So it is NOT a turbulent cascade. BUT exponential decay is the "
            "LAPLACE domain — the dynamics are decay/relaxation, refined into laplace_dynamics.",
        ],
        "advances_by": "surviving the power-law / flow / equilibrium tests — not by analogy alone.",
        "refutable": True,
        "lifecycle": "held-refined",
        "supersedes": None,
        "superseded_by": "laplace_dynamics",
        "held_since": "2026-06-19",
        "seed_v": 2,
    },
    {
        "id": "laplace_dynamics",
        "name": "Laplace — the map's dynamics (decay/growth), beyond the steady spectrum",
        "status": "placeholder",
        "grade": "plausible",
        "kind": "arrangement_principle",
        "claim": ("Matt: 'laplace transform ... missing.' Fourier gives the STEADY spectrum (the "
                  "imaginary axis); Laplace adds the REAL axis s=sigma+i*omega — decay/growth "
                  "RATES. The map's eigenvalue spectrum decays EXPONENTIALLY, which is the Laplace "
                  "domain: each mode descends from the source/fundamental at a fixed rate. The "
                  "'rate of descent from source' made literal; Laplace is the transform for the "
                  "DYNAMICS (how the arrangement responds, decays, settles), where Fourier is the "
                  "snapshot."),
        "organizes": ("the DYNAMICS the fluid seed reached for — but the behavior of the axes is "
                      "decay/relaxation toward equilibrium (Laplace), NOT a turbulent cascade. "
                      "Refines fluid_dynamics_axes with what the assay actually found."),
        "predicts": [
            "the eigenvalue spectrum stays exponential as the grid grows (a stable decay rate)",
            "the decay rate (sigma) is a property of the arrangement — a 'relaxation time' of the map",
            "tuning toward consonance is the system relaxing toward its equilibrium (lowest-energy) state",
        ],
        "provenance": ("Matt's seed 2026-06-19; assayed via arrangement.spectrum() decay fit "
                       "(GET /grid/spectrum -> decay)."),
        "caveat": ("A lens, plausible: the exponential fit is REAL (R^2=0.995), but 'the map is a "
                   "Laplace/linear-relaxation system' is provisional; what the decay rate MEANS "
                   "for correctness is open. Tie to the tune-criterion: does cleaner/faster "
                   "relaxation track a more in-tune (more correct) arrangement?"),
        "evidence": [
            "Spectrum decay fit: exponential R^2=0.995 (rate -0.20/mode) vs power-law R^2=0.93 — "
            "the Laplace/decay signature, not the Fourier/cascade one.",
            "FLOW assay 2026-06-19 (graph Laplacian L=D-W, GET /grid/flow): the map is one "
            "connected component (lambda_0=0) and the eigenvalues ARE the heat-equation decay "
            "rates (e^-lambda t), consistent with the exponential decay. BUT the low flow modes "
            "isolate the most WEAKLY-COUPLED / sparse dimensions (discreteness, then symmetry) — "
            "the diffusion bottlenecks — NOT the abstract/material divide. Flow diagnoses the "
            "grid's SPARSITY, not its content split.",
            "HONEST CORRECTION (the assay disposed): a first read claimed flow 'confirmed' the "
            "two-trees (a three-method convergence) — WRONG, a misread of a single-outlier Fiedler "
            "spike (discreteness=-0.92, rest ~+0.05). RETRACTED. The two-trees is an ALIGNMENT "
            "finding (correlation eigenmode + clustering, which are the same signal); flow is a "
            "DIFFERENT lens and does not show it. Map never launders — recorded as found.",
            "METHOD GROUNDING (scholar lookup, lawful Layer-0 — grounds the TOOL, not the claim): "
            "the 'algebraic connectivity' (lambda_2) we report is from Fiedler, 'Algebraic "
            "connectivity of graphs', Czech. Math. J. 1973 (doi:10.21136/cmj.1973.101168; free copy "
            "dml.cz/handle/10338.dmlcz/101168) — 3,976 cites, the foundational source of the metric. "
            "Multi-scale spectral reading: Hammond et al., 'Wavelets on graphs via spectral graph "
            "theory', ACHA 2010 (doi:10.1016/j.acha.2010.04.005; free copy EPFL infoscience). "
            "These confirm the methods are sound and well-founded; they do NOT confirm the map's "
            "arrangement is correct (still p=0.385).",
        ],
        "falsifiers": [
            "On a larger grid the spectrum stops being exponential (the decay law was an artifact).",
            "The decay rate carries no relation to verified correctness or to the tune-criterion.",
            "A power-law / cascade fits markedly better as the grid grows.",
        ],
        "unlikely_tests": [
            "Re-fit the decay as the grid grows — does the exponential (and its rate) hold?",
            "Does a lower decay rate (slower descent) track a more in-tune arrangement (tune_test)?",
            "Read the modes as a control system — do the 'poles' (Laplace) predict its stability?",
        ],
        "advances_by": "surviving the decay-stability tests + the decay rate tracking correctness/tune.",
        "refutable": True,
        "lifecycle": "held",
        "supersedes": "fluid_dynamics_axes",
        "superseded_by": None,
        "held_since": "2026-06-19",
        "seed_v": 3,
    },
    {
        "id": "model_is_a_hive_not_an_organism",
        "name": "The model is a hive of small task-tuned specialists, not one organism",
        "status": "placeholder",
        "grade": "plausible",
        "kind": "architecture_principle",
        "claim": ("Matt: 'Maybe our brains function more like a hive than a single organism — would "
                  "it be more efficient to have several smaller models tuned for each task with "
                  "guidance systems?' The GENERATIVE layer should be a HIVE: small task-tuned "
                  "specialist models + a DETERMINISTIC guidance system (router) + engine verification "
                  "of every output — not one big general model. It is fractally self-similar to the "
                  "DETERMINISTIC layer already built (the ~71 verifier-specialists + the check / "
                  "find_verifier / run_polymathic router): the generative layer mirrors the engine."),
        "organizes": ("the structure of the generative layer (the assistant 'mouth'), making it the "
                      "same shape as the verifier hive. The seam already exists: every draft routes "
                      "through api/oracle.complete, today as one model + a per-task system prompt; the "
                      "hive swaps that for one tuned SMALL model PER task, routed the same way."),
        "predicts": [
            "a small model tuned for ONE narrow task (intake-classify, Socratic question, lesson) "
            "matches or beats the general model on THAT task, at lower cost and on-device (sovereign)",
            "the dominant failure mode is MIS-ROUTING -> so the guidance system must be deterministic "
            "(rules route, like find_verifier); a model routing models compounds errors",
            "each specialist's output must pass the engine's gate (the verifier hive checks the model "
            "hive) — a specialist generates, the deterministic gate disposes",
        ],
        "provenance": ("Matt's seed 2026-06-19. Grounded: modular-brain neuroscience (the brain is "
                       "specialized regions + connectivity, not one homogeneous net), Mixture-of-"
                       "Experts, AND our own engine (the verifier hive already IS this in the "
                       "deterministic layer)."),
        "caveat": ("Plausible + well-founded, NOT yet measured. The assay is a HEAD-TO-HEAD: does a "
                   "tuned small specialist beat the general model on its narrow task (accuracy, "
                   "latency, cost)? Coordination + per-task training data are real costs. Start with "
                   "2-3 specialists, deterministic routing, engine-verified outputs — not a big-bang "
                   "rewrite."),
        "evidence": [
            "The deterministic hive already works: ~71 verifier-specialists + a rules router "
            "(check/find_verifier/run_polymathic) — the pattern is proven on the verify side.",
            "The generative seam is ready: api/oracle.complete(system, text, model=...) is the ONE "
            "edge every draft calls, already tiered deterministic-floor -> local small model "
            "(qwen2.5:3b) -> paid oracle. Splitting = register a tuned model PER task + route by task.",
        ],
        "falsifiers": [
            "A tuned small specialist does NOT beat the general model on its narrow task (then one "
            "model is simply better — keep it).",
            "The deterministic router cannot reliably pick the right specialist (the hive mis-fires).",
            "Maintenance/coordination cost of N specialists exceeds the efficiency gain.",
        ],
        "unlikely_tests": [
            "Tune an intake-classifier on real intake logs — does it beat the general model on "
            "routing accuracy + latency + $?",
            "Tune a Socratic-questioner on Matt's voice + the teachings — better questions than the "
            "general model?",
            "Measure oracle-dependence: does the hive drive more drafts onto $0 on-device models?",
        ],
        "advances_by": ("head-to-head wins, measured: a small tuned specialist beating the general "
                        "model on its task (accuracy/latency/cost), with the router staying "
                        "deterministic and every output engine-verified."),
        "refutable": True,
        "lifecycle": "held",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-19",
        "seed_v": 1,
    },
]


def _load() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        if _PATH.exists():
            for line in _PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _append(rec: Dict[str, Any]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _ensure_seeded() -> None:
    # Append a seed when it's missing OR when its seed_v is newer than the stored
    # one (listing/get use last-wins, so a re-appended seed supersedes the old).
    stored_v: Dict[str, int] = {}
    for r in _load():
        if r.get("id"):
            stored_v[r["id"]] = max(stored_v.get(r["id"], 0), int(r.get("seed_v", 0) or 0))
    for r in _SEED:
        if stored_v.get(r["id"], -1) < int(r.get("seed_v", 0) or 0):
            _append(r)


_ensure_seeded()


def listing() -> Dict[str, Any]:
    """All placeholders, newest first by held_since, deduped by id (last wins —
    so a refine/retire append supersedes the earlier record)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in _load():
        if r.get("id"):
            by_id[r["id"]] = r
    items = [r for r in by_id.values() if r.get("lifecycle") != "retired"]
    items.sort(key=lambda r: r.get("held_since", ""), reverse=True)
    return {
        "placeholders": items,
        "count": len(items),
        "grades": list(_GRADES),
        "what_is_this": ("Placeholders to truth: provisional structures integrated into "
                         "the map to scaffold and predict, honestly marked as not-yet-"
                         "confirmed, held open to confirm / refine / replace. Not truth — "
                         "toward it. The final truth is never sealed (the apex is reserved)."),
        "the_method": ("This is a SEARCH, and it must explore, not just exploit. Each "
                       "placeholder carries falsifiers (what would refute it) and "
                       "unlikely_tests (the non-examples to hunt) — it ADVANCES BY SURVIVING "
                       "them, never by confirmations. Skip the disconfirming probes and the "
                       "map becomes an echo chamber. A placeholder with no falsifiers "
                       "(refutable=false) is the weakest kind."),
    }


def get(pid: str) -> Optional[Dict[str, Any]]:
    rec = None
    for r in _load():
        if r.get("id") == pid:
            rec = r  # last wins
    return rec


def propose(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update a placeholder. Honest by default: grade is clamped to the
    provisional band (never 'confirmed' here — confirmation is earned by data,
    elsewhere). Returns the stored record."""
    pid = str(rec.get("id") or "").strip().lower().replace(" ", "_")
    if not _ID_RE.match(pid):
        return {"error": "id must be 3-64 chars of [a-z0-9_]"}
    grade = str(rec.get("grade") or "resonance").lower()
    if grade not in ("coincidence", "resonance", "plausible", "candidate", "retired"):
        grade = "resonance"  # cannot self-declare 'confirmed'
    stored = {
        "id": pid,
        "name": str(rec.get("name") or pid)[:160],
        "status": "placeholder",
        "grade": grade,
        "kind": str(rec.get("kind") or "concept")[:60],
        "claim": str(rec.get("claim") or "")[:1200],
        "organizes": str(rec.get("organizes") or "")[:600],
        "predicts": [str(x)[:200] for x in (rec.get("predicts") or [])][:12],
        "provenance": str(rec.get("provenance") or "")[:800],
        "caveat": str(rec.get("caveat") or
                      "Held as a placeholder to truth — provisional, open to revision.")[:600],
        # Disconfirmers are first-class: a placeholder must be refutable, and it
        # advances by SURVIVING these (not by confirmations). Empty falsifiers is a
        # weakness, flagged in the record.
        "falsifiers": [str(x)[:300] for x in (rec.get("falsifiers") or [])][:8],
        "unlikely_tests": [str(x)[:300] for x in (rec.get("unlikely_tests") or [])][:8],
        "advances_by": "surviving its falsifiers and unlikely_tests — not by confirmations.",
        "refutable": bool(rec.get("falsifiers")),
        "lifecycle": str(rec.get("lifecycle") or "held")[:20],
        "supersedes": rec.get("supersedes"),
        "superseded_by": rec.get("superseded_by"),
        "held_since": time.strftime("%Y-%m-%d", time.gmtime()),
    }
    _append(stored)
    return stored
