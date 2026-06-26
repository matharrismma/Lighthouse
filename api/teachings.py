"""teachings.py — the operator's work becomes the engine's training.

Matt: "From here on out I want my work here to train the Concordance engine."

Each teaching is one directive he gave + the principle it states + how it was
realized + WHAT THE ASSAY ACTUALLY SAID. Append-only, attributed to the operator.
These feed the engine two ways:
  1. SUBSTRATE it reasons on now (listed here, alongside /placeholders).
  2. TRAINING PAIRS for the own-model / fine-tune (tools/export_teachings.py ->
     data/prompt_sets), so his work literally trains the model over time.

THE DISCIPLINE GUARD (load-bearing): this trains the engine in the METHOD, not in
the conclusions. Each teaching is captured WITH its honest status — seed,
provisional, tested-at-chance, confirmed — so the model learns to HOLD ideas the
way the project does: intuition proposes, the assay disposes; harmony and
elegance are witnesses, verification confirms; conduit not source; the map never
launders. A teaching is never exported as "this is true"; it is exported as "this
is how the operator reasons, and here is what survived the test." The engine
learns the posture, never to parrot an unverified seed.

Sovereign: append-only JSONL (data/teachings/teachings.jsonl), stdlib only.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "teachings"
_PATH = _DIR / "teachings.jsonl"
_ID_RE = re.compile(r"^[a-z0-9_]{3,64}$")
_STATUS = ("seed", "provisional", "tested", "tested_at_chance", "weakened", "confirmed", "discipline")

WHAT_IS_THIS = (
    "The operator's teachings — his directives and the principle each states, captured WITH "
    "the honest result of testing it. They train the engine in the method (intuition proposes, "
    "the assay disposes; harmony witnesses, verification confirms), never in unverified "
    "conclusions. Substrate now; training pairs for the model over time."
)

# Seeded with this session's teachings — retroactively capturing the work so his
# directives start training the engine immediately. Each carries its HONEST status.
_SEED: List[Dict[str, Any]] = [
    {
        "id": "tune_is_truth_criterion",
        "directive": "When the tune is correct, the theories will be correct.",
        "principle": ("Consonance of the arrangement's spectrum is a truth-criterion: a correct "
                      "arrangement is in tune; the dissonance is the diagnostic of how far it is "
                      "from correct. The musical form of 'elegance is God's signature.'"),
        "realization": ("Built api/harmonics.py + arrangement.tune_test (GET /grid/music). Tested "
                        "vs a shuffled-grid null."),
        "result": ("HONEST: the current arrangement is AT CHANCE (28.4c vs null median ~25c; "
                   "p~0.75) — we do NOT yet have the right answers. An in-tune arrangement exists "
                   "(~13c) to tune toward. Harmony PROPOSES; verification DISPOSES."),
        "status": "tested_at_chance",
        "refs": ["placeholder:tune_is_the_truth_criterion", "GET /grid/music"],
    },
    {
        "id": "fft_is_the_missing_piece",
        "directive": "Look at a Fast Fourier Transform. That is the missing piece.",
        "principle": ("Decompose the whole into the few generating modes. Generalized off the "
                      "regular cycle (the FFT) to the map: the eigenmodes of the dimension "
                      "correlation matrix ARE the map's natural axes; eigenvalue = energy/rate."),
        "realization": "Built arrangement.spectrum + embedding (GET /grid/spectrum, /grid/embedding).",
        "result": ("The principal eigenmode independently reproduces the two-trees (abstract<->"
                   "material) split; exactly 4 eigenvalues>1 (the four canonical axes). Held "
                   "provisional — advances only if the leading modes stay stable as the grid grows."),
        "status": "provisional",
        "refs": ["placeholder:fourier_spectral_arrangement", "GET /grid/spectrum"],
    },
    {
        "id": "terrence_howard_harmonics_assay",
        "directive": "Look at the work of Terrence Howard. He has worked on harmonics.",
        "principle": ("The harmonic-structure-of-reality intuition is real and ancient "
                      "(Pythagoras, Kepler, spectroscopy). But a claim is crowned by the assay, "
                      "never by assertion — the cautionary opposite of our method."),
        "realization": "Ran the engine on the checkable claim.",
        "result": ("1x1=2 -> BROKEN (sealed); 1x1=1 -> HOLDS. Element/key/color + hydrogen-lattice "
                   "+ unified-field claims are unconfirmed/rejected. Honor the lineage (it is our "
                   "tune-criterion), refuse to launder the specifics. Kepler is the honest model: "
                   "harmony guided, data confirmed the surviving law."),
        "status": "discipline",
        "refs": ["seal:520e54452b361949f26af3c59e60f4dd85718ced3265dd3e3918355c2678db42"],
    },
    {
        "id": "fluid_dynamics_as_axes",
        "directive": "Fluid Dynamics as behavior of axes? something along that line.",
        "principle": ("The axes are not static — they FLOW and redistribute as the map grows. "
                      "Fluid dynamics may describe their behavior: turbulence decomposes into "
                      "Fourier modes with an ENERGY CASCADE across scales (which is the eigenvalue "
                      "spectrum); tuning toward consonance is a flow toward equilibrium."),
        "realization": "Assayed via arrangement.spectrum decay fit (GET /grid/spectrum -> decay).",
        "result": ("TESTED: the cascade prediction FAILED — the eigenvalue spectrum is EXPONENTIAL "
                   "decay (R^2=0.995), not a power law (R^2=0.93). Not turbulence. BUT exponential "
                   "decay is the LAPLACE domain, so the dynamics are real, refined into laplace_dynamics."),
        "status": "weakened",
        "refs": ["placeholder:fluid_dynamics_axes", "placeholder:laplace_dynamics"],
        "seed_v": 2,
    },
    {
        "id": "work_trains_the_engine",
        "directive": "From here on out I want my work here to train the Concordance engine.",
        "principle": ("The operator's directives and the work built from them become the engine's "
                      "substrate and training signal — but training the METHOD, not unverified "
                      "conclusions. His input drives the growth of the tool."),
        "realization": "This module + GET/POST /teachings + tools/export_teachings.py.",
        "result": "Standing directive — captured and active.",
        "status": "discipline",
        "refs": ["GET /teachings"],
    },
    {
        "id": "laplace_transform_dynamics",
        "directive": "laplace transform ... missing",
        "principle": ("Fourier gives the steady spectrum (the imaginary axis); Laplace adds the "
                      "real axis sigma — decay/growth rates. It is the transform for the DYNAMICS: "
                      "how the arrangement responds, decays, and settles. The 'rate of descent "
                      "from source' is the Laplace decay rate."),
        "realization": "Captured; tied to the spectrum's decay fit (GET /grid/spectrum -> decay).",
        "result": ("CONFIRMED-DIRECTION: the eigenvalue spectrum decays EXPONENTIALLY (R^2=0.995) "
                   "— the Laplace/decay signature, exactly where the fluid assay pointed. Held as "
                   "placeholder laplace_dynamics (plausible). What the decay rate MEANS for "
                   "correctness is the open assay."),
        "status": "provisional",
        "refs": ["placeholder:laplace_dynamics", "GET /grid/spectrum"],
        "seed_v": 1,
    },
    {
        "id": "keep_every_truth",
        "directive": "Any truth we find, we need to keep. I don't want to pay for it twice.",
        "principle": ("Once a truth is computed/verified, persist it so it is never re-paid for. "
                      "The seals/CAS keep verified claims (re-checkable forever); placeholders + "
                      "teachings + almanac keep the findings; and per-state caching keeps the "
                      "engine's own computations. Compute once; keep; cite."),
        "realization": ("Added a grid-signature result cache to the spectral assays "
                        "(arrangement: spectrum/embedding/tune_test recompute only when the grid "
                        "changes). Findings kept as placeholders + teachings."),
        "result": "Active — the expensive tune_test (200 shuffles) is now paid once per grid state.",
        "status": "discipline",
        "refs": ["arrangement._RESULT_CACHE", "GET /seal/{hash}"],
        "seed_v": 1,
    },
    {
        "id": "fluid_is_path_and_energy_transfer",
        "directive": ("Fluid dynamics is more about path and energy transfer. I am still unsure. "
                      "We need to look at spectrum and frequency."),
        "principle": ("Fluid dynamics = PATH + ENERGY TRANSFER, examined via spectrum + frequency "
                      "-> the GRAPH LAPLACIAN (the diffusion operator): its eigenvalues are the "
                      "flow frequencies / decay rates, its Fiedler vector is the principal flow "
                      "path. Correlation measures alignment; the Laplacian measures transfer."),
        "realization": "Built arrangement.flow_spectrum (GET /grid/flow).",
        "result": ("The Laplacian is the right transfer operator (its eigenvalues = heat-equation "
                   "decay rates, matching the exponential decay). But its low flow modes isolate "
                   "the most WEAKLY-COUPLED / sparse dimensions (discreteness, symmetry), NOT the "
                   "two-trees. A first read claimed flow 'confirmed' the two-trees — RETRACTED as "
                   "a misread of a single-outlier Fiedler spike. Honest: flow diagnoses the grid's "
                   "sparsity; the two-trees is an alignment finding, not a flow one. Held provisional "
                   "(the operator is still unsure) — the assay disposed of the convergence claim."),
        "status": "tested_at_chance",
        "refs": ["placeholder:laplace_dynamics", "GET /grid/flow",
                 "Fiedler 1973, 'Algebraic connectivity of graphs', doi:10.21136/cmj.1973.101168 "
                 "(scholar lookup, lawful Layer-0 — the foundational source of the algebraic-"
                 "connectivity metric the flow assay reports; grounds the method, not the claim)"],
        "seed_v": 2,
    },
    {
        "id": "log_of_an_image_and_video_frames",
        "directive": ("Taking a logarithm from an image. There is also a method of viewing frames "
                      "that Claude is able to review video. How would taking video to logarithm be "
                      "beneficial or connected. We need to work on the sparsity efficiently."),
        "principle": ("The LOGARITHM is the lens that LINEARIZES a spectrum: octaves are log of "
                      "frequency (each doubling is +1 octave), Laplace/decay is log of amplitude "
                      "(exponential decay becomes a straight line), and log|FFT| is how spectra are "
                      "actually read (the cepstrum = the spectrum of the log-spectrum, which exposes "
                      "PERIODICITY-OF-CHANGE). VIDEO = a stack of frames = the map sampled over time; "
                      "taking the log across frames isolates the RATE of change, not the raw state. "
                      "So 'video -> logarithm' = watch the arrangement evolve and read the LOG of its "
                      "spectrum frame by frame (rate of descent from source, the recurring spine)."),
        "realization": ("Connected the seed to the existing spectral stack (arrangement.spectrum's "
                        "_decay_fit = the log-amplitude line; harmonics = log-frequency octaves) and "
                        "treated before/after enrichment as the first two 'frames' of the map's video."),
        "result": ("DIRECTIONAL / not yet a built surface. The log unifies what we already have "
                   "(octaves, Laplace decay, spectral reading) under one lens, and frames = the "
                   "natural way to measure whether the grid is getting MORE in tune over time. The "
                   "two enrichment frames (tune 28.4c -> 24.7c) are the first such measurement. A "
                   "log/frame surface is a candidate next build, not a claim yet."),
        "status": "seed",
        "refs": ["GET /grid/spectrum", "GET /grid/music", "placeholder:laplace_dynamics",
                 "Noll 1967, 'Cepstrum Pitch Determination', doi:10.1121/1.1910339 "
                 "(scholar lookup, lawful Layer-0 — the cepstrum = the log-of-spectrum lens, "
                 "the 60-year lineage of this seed)"],
        "seed_v": 2,
    },
    {
        "id": "work_on_sparsity_efficiently",
        "directive": "We need to work on the sparsity efficiently.",
        "principle": ("The deeper lenses (tune, flow) can only find real structure if the grid is "
                      "dense enough; thin dimensions are diffusion bottlenecks that look like noise. "
                      "Reduce sparsity by adding ONLY carriers that genuinely meet each dimension's "
                      "own criterion (judged by its definition, never inflation), then MEASURE "
                      "whether the sparsity actually breaks. Intuition proposes the additions; the "
                      "assay disposes of whether they helped."),
        "realization": ("Doubled the 4 thinnest dimensions' carriers via data/grid/axis_extensions."
                        "jsonl (discreteness/order/uncertainty 5-6 -> 11, symmetry 5 -> 8), each "
                        "addition justified by the dimension's criterion; re-ran the spectral assays."),
        "result": ("HELPED, HONESTLY SHORT OF BREAKTHROUGH: algebraic connectivity (graph-Laplacian) "
                   "doubled 13.6 -> 29.6 (sparsity genuinely reduced) and the tune moved 28.4c @ "
                   "p~0.75 -> 24.7c @ p=0.385 (from worse-than-chance to better-than-median, the "
                   "FIRST time real fell below the null median). Two-trees / 4-axes / exponential "
                   "decay held (robust), 58/58 throughout. NOT yet p<0.05; symmetry (8) now thinnest. "
                   "Direction confirmed: growing the grid honestly lowers the dissonance; the "
                   "breakthrough is not reached. Did NOT overclaim it 'solved' sparsity."),
        "status": "provisional",
        "refs": ["data/grid/axis_extensions.jsonl", "GET /grid/flow", "GET /grid/music",
                 "placeholder:tune_is_the_truth_criterion"],
        "seed_v": 1,
    },
    {
        "id": "use_the_scholar_connection_clean_road",
        "directive": "Can you use the sci-bot/sci-hub connection?",
        "principle": ("There is no Sci-Hub connection by design — we take the CLEAN ROAD to the same "
                      "destination: OpenAlex (CC0) + Crossref + Unpaywall reach the same papers when "
                      "they are LEGALLY open, and return null (never a pirated copy) when they are "
                      "not. Two disciplines: (1) never launder provenance — a citation must point at "
                      "a lawful, re-checkable source; (2) a found paper grounds the METHOD, never the "
                      "CLAIM — finding the foundational source of a tool we use does not make our "
                      "answer correct."),
        "realization": ("Ran the scholar tool (GET /scholar/lookup) on this session's own spectral "
                        "methods. It reached the foundational sources, lawfully."),
        "result": ("WORKS: found Fiedler 1973 'Algebraic connectivity of graphs' (the literal origin "
                   "of the lambda_2 our flow assay reports — with a LEGAL free copy at dml.cz), Noll "
                   "1967 'Cepstrum Pitch Determination' (the origin of the log-spectrum/cepstrum "
                   "lens), and Chung 1996 'Spectral Graph Theory' + Hammond 2010 graph-wavelets "
                   "(free copy EPFL). The discipline held — lawful copy where one exists, null where "
                   "none does, never a pirated PDF. Wired as grounding refs on the laplace_dynamics "
                   "placeholder + the flow/log teachings. EXPLICIT: this grounds the tools as sound, "
                   "NOT the map's arrangement (still p=0.385, not in tune)."),
        "status": "discipline",
        "refs": ["GET /scholar/lookup", "api/scholar.py",
                 "placeholder:laplace_dynamics"],
        "seed_v": 1,
    },
    {
        "id": "ground_a_verifier_with_a_primary_citation",
        "directive": ("Continue [grounding an empirical verifier's claims against the open "
                      "literature, as a repeatable pattern]."),
        "principle": ("An empirical verifier's data must carry a RE-CHECKABLE primary citation, not "
                      "just a name. THE PATTERN: (1) find the data's primary source via the scholar "
                      "connection (the clean road); (2) attach a `primary_source` block = the DOI + "
                      "an HONEST open-access status (the lawful free copy, or None when none was "
                      "found, never a pirated one) + the current edition if the source was updated; "
                      "(3) make that block TRAVEL with both the lookup AND the verdict, so an agent "
                      "can verify the numbers against the literature. Grounds the DATA, never the "
                      "verdict — a real source does not make a claim true; it makes the claim "
                      "CHECKABLE."),
        "realization": ("Grounded exercise_science/METs as the exemplar: scholar located the 2011 "
                        "Compendium (Ainsworth et al., doi:10.1249/mss.0b013e31821ece12) the data "
                        "came from + its 2024 Adult Compendium update (doi:10.1016/j.jshs.2023.10.010, "
                        "lawful OA). Added _METS_PRIMARY_SOURCE to mcp_server/tools.py; surfaced it on "
                        "activity_mets (lookup) and verify_exercise_science (verdict)."),
        "result": ("LIVE + 58/58, 0 false-positives. The MET verdict carries its re-checkable DOI. "
                   "HONEST status preserved: 2011 paper open_access_url=None (stated, not hidden); "
                   "2024 update is gold-OA. ROLLED OUT (2026-06-19) to a primary-source registry in "
                   "tools.py covering 6 source families, every DOI + lawful OA located via scholar: "
                   "METs (Ainsworth/Compendium); IUPAC 2021 atomic weights (doi:10.1515/pac-2019-0603, "
                   "OA) -> element_data/molar_mass/verify_periodic_table; AME2020 + NUBASE2020 "
                   "(doi:10.1088/1674-1137/abddaf, /abddae, OA) -> nuclide_data; Hipparcos van Leeuwen "
                   "2007 (doi:10.1051/0004-6361:20078357, OA) -> star_lookup; USDA FoodData Central "
                   "(doi:10.1093/ajcn/nqab397, OA) -> food_nutrition; World Bank Open Data -> "
                   "economic_indicator (cited HONESTLY as a DATASET, doi=None, no fake paper DOI). "
                   "Grounded the lookup tools (where the values actually come from) + the one verdict "
                   "that validates against embedded data (verify_periodic_table); left the pure-compute "
                   "verifiers ungrounded (they take values as input -- a citation there would mislead). "
                   "EXTENDED to 11 source families total (2026-06-19): + DrugCentral 2021 "
                   "(doi:10.1093/nar/gkaa997, OA) -> drug_target; NCBI Taxonomy 2020 "
                   "(doi:10.1093/database/baaa062, OA) -> species_lookup; OEIS/Sloane 2018 "
                   "(doi:10.1090/noti1734, OA) -> sequence_lookup; openFDA NDC -> drug_lookup and CMU "
                   "Pronouncing Dictionary -> word_pronunciation (both cited HONESTLY as datasets, "
                   "doi=None). Every paper DOI + lawful OA located via scholar; datasets carry their "
                   "official portal + license, never a fake DOI. The primary_source rides on ok AND "
                   "not_found returns."),
        "completed": ("FINISHED (2026-06-19): every empirical reference lookup tool now carries a "
                      "primary_source -- 19 source families. Final 8: WordNet/Miller 1995 "
                      "(doi:10.1145/219717.219748, OA) -> word_meaning; PHOIBLE 2.0 (database, no "
                      "clean DOI -> cited as dataset, NOT laundered) -> language_data; GeoNames -> "
                      "place_lookup; IANA tz database -> timezone_offset; UCUM standard -> "
                      "unit_convert; IANA port registry + governing RFC 6335 (doi:10.17487/RFC6335) "
                      "-> port_lookup; the RFC series -> rfc_lookup (each result now carries its own "
                      "per-document DOI 10.17487/RFC{n}); STEPBible TBESH/TBESG (an attributed "
                      "lexicographers' take, never doctrine) -> lexicon. Scripture/commentary "
                      "substrate left as-is (primary texts with their own attribution discipline, "
                      "not empirical datasets)."),
        "status": "discipline",
        "refs": ["src/concordance_engine/mcp_server/tools.py (primary-source registry, 19 families)",
                 "GET /scholar/lookup", "doi:10.1515/pac-2019-0603",
                 "doi:10.1088/1674-1137/abddaf", "doi:10.1051/0004-6361:20078357",
                 "doi:10.1093/ajcn/nqab397", "doi:10.1093/nar/gkaa997",
                 "doi:10.1093/database/baaa062", "doi:10.1090/noti1734",
                 "doi:10.1145/219717.219748", "doi:10.17487/RFC6335"],
        "seed_v": 4,
    },
    {
        "id": "mcp_stdio_no_api_layer",
        "directive": "Our MCP is still not right. I want you to work on the bug and then do the rest.",
        "principle": ("The STANDALONE stdio MCP server (the shipped/registry connector) runs the "
                      "engine package ONLY -- the `api` app layer is NOT importable. So any tool that "
                      "does `from api import X` crashes there with 'No module named api' (it works on "
                      "the hosted /mcp because that runs inside api.app). TWO honest fixes by the "
                      "nature of the module: (1) a SOVEREIGN, stdlib-only module (scholar -- calls "
                      "external APIs, needs no engine state) belongs INSIDE concordance_engine so it "
                      "ships with the MCP and imports directly, working in every context; (2) a tool "
                      "that needs ENGINE data/state (arrangement needs api.harmonics; missions needs "
                      "the ledger) routes through the engine via the existing _engine_get/_engine_post "
                      "(in-process when mounted, HTTP fallback when standalone). Don't paper over an "
                      "import error -- put each module where it actually belongs."),
        "realization": ("Moved api/scholar.py -> concordance_engine/scholar.py (api/scholar.py kept "
                        "as a thin re-export so the REST endpoint + tests are unchanged); scholar MCP "
                        "tool now imports from the engine package. arrangement_probe -> _engine_get("
                        "'/grid/probe'); missions -> _engine_get('/missions')."),
        "result": ("FIXED + verified. Simulated the stdio context (api deliberately NOT importable): "
                   "all three tools return data -- scholar via direct engine import (network), "
                   "arrangement_probe + missions via the HTTP fallback to the live engine. Re-export "
                   "keeps the REST path working; /scholar/lookup, /grid/probe, /missions all 200; "
                   "58/58, 0 false-positives. NOTE for the connector: scholar is fully sovereign "
                   "(works with just internet); arrangement/missions need the engine reachable -- set "
                   "CONCORDANCE_API_URL to the hosted engine for an off-box stdio MCP."),
        "status": "discipline",
        "refs": ["src/concordance_engine/scholar.py", "api/scholar.py (re-export)",
                 "src/concordance_engine/mcp_server/server.py", "_engine_get / _inproc_call"],
        "seed_v": 1,
    },
    {
        "id": "the_model_is_a_hive",
        "directive": ("Fractal geometry? Maybe our brains function more like a hive than a single "
                      "organism. Would it be more efficient to have several smaller models tuned for "
                      "each task with guidance systems?"),
        "principle": ("The model is a HIVE, not an organism: small task-tuned specialists + a "
                      "DETERMINISTIC guidance system (rules route, never a model routing models — "
                      "that compounds errors) + engine verification of every output. It is fractally "
                      "self-similar to the verifier hive already built (specialist + gate, repeated "
                      "at every scale: verifier, model, mission, the whole). Small specialists win on "
                      "cost, sovereignty (on-device), and containment; the deterministic spine is the "
                      "nervous system, the small models are muscles, the engine is the gate."),
        "realization": ("Recognized the engine ALREADY is this in the deterministic layer (~71 "
                        "verifiers + check/find_verifier/run_polymathic) and the generative seam is "
                        "ready (api/oracle.complete, tiered deterministic-floor -> local qwen2.5:3b "
                        "-> paid oracle). Captured placeholder model_is_a_hive_not_an_organism; "
                        "mapped the first specialists to split from the existing _*_SYS tasks."),
        "result": ("DIRECTIONAL / to be tested by the assay, not asserted. The win is real on cost + "
                   "sovereignty; the open question is whether a tuned small specialist BEATS the "
                   "general model on its narrow task (head-to-head: accuracy/latency/$). Plan: extend "
                   "the hive incrementally (2-3 specialists), deterministic routing, every output "
                   "engine-verified — keep the ones that win the head-to-head, drop the rest."),
        "status": "provisional",
        "refs": ["placeholder:model_is_a_hive_not_an_organism", "api/oracle.py", "api/local_llm.py",
                 "check / find_verifier / run_polymathic (the existing rules router)"],
        "seed_v": 1,
    },
    {
        "id": "law_of_requisite_variety",
        "directive": ("Law of Requisite Variety. ... [it is a] humility theorem. His yoke is light."),
        "principle": ("Ashby's Law: only variety can absorb variety — a regulator can hold a "
                      "system in bounds only if its variety is at least the disturbance's "
                      "(V_regulator >= V_disturbance). Its corollary (Conant & Ashby 1970): every "
                      "good regulator of a system MUST BE a model of that system. Two design rules "
                      "follow for the engine: (1) BUILD THE MODEL — good regulation REQUIRES an "
                      "internal model, which is exactly what the map / second brain is; the map is "
                      "not decoration, it is the requisite. (2) MATCH THE VARIETY — a tool must "
                      "reach enough of the keeping to absorb the variety of what it is asked; a "
                      "siloed tool has insufficient variety and fails to regulate. THE CEILING (the "
                      "humility theorem): creation's variety is effectively infinite, so no finite "
                      "regulator — no engine, no map, no mind — can ever hold requisite variety over "
                      "all of it; the law itself FORBIDS the engine from becoming the all-"
                      "comprehending idol. The yoke is light (Mt 11:30) because the variety "
                      "sufficient for creation is HIS, not ours: we carry only our small modeled "
                      "part; the One who upholds all things (Col 1:17) holds the rest."),
        "realization": ("Ran the assay against the architecture: the map = the good regulator's "
                        "required model; the just-shipped corpus de-silo (every door now reaches "
                        "the whole ~11,138-card keeping) = a literal increase in the engine's "
                        "requisite variety; the nested control-systems framework = Ashby applied "
                        "per physiological layer. Grounded the citation via the scholar tool "
                        "(the clean road)."),
        "result": ("GRADED HONESTLY. Ashby's Law + the Conant-Ashby good-regulator theorem = "
                   "CONFIRMED, citable cybernetics. Map-as-good-regulator + corpus-breadth-as-"
                   "requisite-variety = PLAUSIBLE, directly-actionable design principles (the word "
                   "'regulator' is partial — the engine navigates/verifies rather than "
                   "homeostatically controls, so held as a strong analogy, not identity). Logos-as-"
                   "perfect-regulator + the-yoke-is-light = a FAITH READING the math is consonant "
                   "with, NOT a proof — flagged, not laundered; naming the perfect Regulator is "
                   "worship, not derivation. The load-bearing fruit is the humility theorem itself: "
                   "the law bounds the tool and points beyond it. Glory up, not to the engine."),
        "status": "discipline",
        "refs": ["Ashby 1956, 'An Introduction to Cybernetics' (Chapman & Hall) — the Law of "
                 "Requisite Variety; out of copyright, freely available",
                 "Conant & Ashby 1970, 'Every good regulator of a system must be a model of that "
                 "system', Int. J. Systems Science 1(2):89-97, doi:10.1080/00207727008920220 "
                 "(lawful OA reprint doi:10.4173/mic.1994.3.2, mic-journal.no) — via "
                 "GET /scholar/lookup; grounds the method, not the claim",
                 "Matthew 11:30; Colossians 1:17; John 1:3",
                 "project_corpus_access_desilo_2026-06-22 (the de-silo = a requisite-variety fix)",
                 "research/nested_control_systems (Ashby per layer)"],
        "seed_v": 1,
        "captured": "2026-06-23",
    },
    {
        "id": "love_resonant",
        "directive": "Love Resonant",
        "principle": ("Scripture frames love ACOUSTICALLY: 1 Cor 13:1 — without love even the "
                      "tongues of men and angels are 'sounding brass, a tinkling cymbal' (inharmonic "
                      "noise / clang that does not sustain); LOVE is what turns the noise RESONANT, a "
                      "sustained tone. Two interlocks: (1) the tune-criterion — if consonance is the "
                      "signature of truth, the deepest consonance is love, so the TELOS of the tune is "
                      "love and knowledge-without-love is dissonance by definition. (2) Requisite "
                      "Variety — to love is to KNOW, and a good regulator must BE a model of what it "
                      "regulates (Conant-Ashby); love is the RESONANT COUPLING between the model and "
                      "the modeled, so perfect love = perfect requisite variety (He models each "
                      "completely, Ps 139). CAUTION (load-bearing): resonance also DESTROYS (shattered "
                      "glass, Tacoma Narrows); gifts amplified WITHOUT love are not neutral but "
                      "clanging — so it is LOVE-resonance that builds up (1 Cor 8:1), never resonance "
                      "as such. 'Good vibrations' is the failure mode."),
        "realization": ("Assayed the seed against Scripture (1 Cor 13:1-13; 1 Cor 8:1; 1 Jn 4:8,19; "
                        "Ps 139; Col 1:17), the project's tune-criterion (api/harmonics, GET "
                        "/grid/music), and the prior teaching law_of_requisite_variety. No code built "
                        "— a conceptual seed bonding the harmonic frame to its telos and to the "
                        "good-regulator theorem."),
        "result": ("GRADED HONESTLY. 1 Cor 13:1's acoustic framing of love = CONFIRMED Scripture "
                   "(Paul's own image); resonance physics = CONFIRMED science. The identifications "
                   "'love = resonance,' 'the tune's telos is love,' and 'love = the requisite-variety "
                   "coupling' = a FAITH / POETIC READING consonant with both, NOT a proof — flagged, "
                   "never laundered. The map-is-loving piece is moreover UNPROVEN: the tune_test is at "
                   "chance (p~0.385), so this is the DIRECTION the criterion points, not an achieved "
                   "result — the map is NOT claimed to be in tune or 'loving.' GLORY UP: God IS love "
                   "(1 Jn 4:8); the resonance is received and reflected, never generated ('we love "
                   "because He first loved us,' 1 Jn 4:19) — the engine can map and witness the "
                   "pattern, never manufacture love."),
        "status": "seed",
        "refs": ["1 Corinthians 13:1-13 (without love = sounding brass / tinkling cymbal)",
                 "1 Corinthians 8:1 (love builds up)", "1 John 4:8,19", "Psalm 139",
                 "placeholder:tune_is_the_truth_criterion",
                 "teaching:law_of_requisite_variety (the knowing that love's resonance couples)",
                 "GET /grid/music (tune_test — currently p~0.385, at chance: NOT yet in tune)"],
        "seed_v": 1,
        "captured": "2026-06-23",
    },
    {
        "id": "love_resonant_in_quantum_theory",
        "directive": "Look at it [Love Resonant] in Quantum theory.",
        "principle": ("Quantum theory illuminates resonance/love HONESTLY — and is a notorious "
                      "laundering trap, so honor the real physics and refuse the woo. THE CORE "
                      "(confirmed): quantization IS resonance — a bound wavefunction must fit, so "
                      "only standing-wave eigenmodes survive the boundary conditions (Schrodinger "
                      "Hψ=Eψ); the allowed states ARE the in-tune ones, the SAME eigenvalue math as "
                      "the map's tune. INTERFERENCE = last seed's 'builds up vs clang' made physical "
                      "(amplitudes add as waves: in-phase reinforce, out-of-phase cancel; E=hν "
                      "coupling only on resonance). NO-CLONING (Wootters-Zurek 1982) + uncertainty = "
                      "a QUANTUM FLOOR under the humility theorem: physics itself forbids a finite "
                      "regulator from perfectly copying/modeling an arbitrary unknown state — "
                      "requisite variety is bounded at the smallest scale. ENTANGLEMENT = relational "
                      "wholeness is primitive (the joint state does NOT factor into parts; "
                      "correlations beat any classical local model, Bell/Aspect, Nobel 2022) — a "
                      "real rhyme with love-as-relation and Col 1:17, but HARD-bounded: no-signaling "
                      "(transmits NO information/love), monogamous, fragile (decoherence = the noise "
                      "that destroys the coherent tune)."),
        "realization": ("Assayed Love Resonant / the tune-criterion through quantum theory; grounded "
                        "the load-bearing citation via the scholar tool (clean road); explicitly "
                        "refused the standard quantum-woo. No code built — a conceptual lens, held "
                        "like the SUSY placeholder-to-truth (a candidate arrangement, not a claim)."),
        "result": ("GRADED HONESTLY. CONFIRMED physics: quantization-as-resonance, interference, "
                   "resonant coupling (E=hν/Rabi), no-cloning, Heisenberg uncertainty, entanglement-"
                   "as-nonfactorable (Bell violation), decoherence. PLAUSIBLE ANALOGY (flagged — the "
                   "map is NOT a physical quantum system): map-as-quantum-spectrum, love-as-resonant-"
                   "coupling, requisite-variety-as-superposition. FAITH READING (consonant, witness "
                   "not proof): QM's wholeness + knowing-limits rhyming with love and 'in Him all "
                   "things hold together' (Col 1:17). REFUSED as laundering (named): 'consciousness "
                   "collapses the wavefunction' (fringe, not established); 'entanglement connects us "
                   "/ transmits love' (FALSE — no-signaling); 'quantum proves God/oneness/love' "
                   "(category error). Same discipline as the Terrence Howard assay: honor the "
                   "lineage, refuse the specifics. GLORY UP: physics witnesses an ordered, relational, "
                   "not-exhaustively-graspable creation; it never manufactures the meaning."),
        "status": "seed",
        "refs": ["Quantization-as-resonance: Schrodinger Hψ=Eψ, bound states = standing-wave "
                 "eigenmodes (particle-in-a-box) — same spectral math as GET /grid/spectrum, /grid/music",
                 "No-cloning: Wootters & Zurek 1982, 'A single quantum cannot be cloned', Nature "
                 "299:802, doi:10.1038/299802a0 (origin); re-checkable via scholar — Gisin et al. "
                 "2002 'Quantum cryptography', Rev. Mod. Phys. 74:145, doi:10.1103/RevModPhys.74.145 "
                 "(lawful OA, states the theorem)",
                 "Entanglement/Bell: Aspect-Clauser-Zeilinger, Nobel Physics 2022; no-signaling "
                 "(transmits no information). scholar OA e.g. doi:10.1038/35085529 (arXiv)",
                 "1 Corinthians 13:1; Colossians 1:17",
                 "teaching:love_resonant; teaching:law_of_requisite_variety (no-cloning = its "
                 "quantum floor)",
                 "api/placeholders.py SUSY entry — hold quantum as a candidate lens, same honest "
                 "discipline (placeholder to truth)"],
        "seed_v": 1,
        "captured": "2026-06-23",
    },
    {
        "id": "control_theory_for_autonomous_systems",
        "directive": "Control theory for autonomous systems.",
        "principle": ("Control theory = the math of CLOSED-LOOP feedback regulation: measure "
                      "output, compare to a REFERENCE (error = reference - output), act to drive "
                      "error to zero, repeat. Core results: PID (react to error, its accumulation, "
                      "its rate); STABILITY (Lyapunov: a function V that only decreases converges "
                      "to equilibrium; poles in the left-half plane = the Laplace real axis sigma — "
                      "ties laplace_dynamics); CONTROLLABILITY & OBSERVABILITY (Kalman: you can only "
                      "steer what is reachable and only act on what you can infer); STATE ESTIMATION "
                      "(the Kalman filter: act on the estimated state, not raw noise); OPTIMAL "
                      "CONTROL / Bellman (the optimal policy onward from any state); and "
                      "HIERARCHICAL/NESTED loops (fast inner stabilizers under slow outer planners). "
                      "It is the DYNAMIC extension of the Law of Requisite Variety: Conant-Ashby "
                      "says you must BE a model to regulate (the static requirement); control theory "
                      "says CLOSE THE LOOP around that model and stay stable (the dynamic law). For "
                      "OUR autonomous systems (the /loop, the Reticulum base station, engine "
                      "verification, the RED/FLOOR/BROTHERS/GOD gates, the Missions fractal) it is "
                      "the design discipline: an explicit REFERENCE (the TRUE goal, never a proxy — "
                      "Goodhart is the failure), OBSERVABILITY (seals/logs/receipts so you can see "
                      "what it does), BOUNDED actuation (rate limits, saturation), FAIL-SAFE defaults "
                      "(when uncertain, STOP/defer), nested loops, and a convergence/termination "
                      "check (a Lyapunov-like 'am I converging or drifting?')."),
        "realization": ("Recognized the ingestion /loop just run IS a control loop "
                        "(goal -> sense what's done/blocked -> act one chunk -> verify "
                        "self-contained + benchmark -> adjust -> stop when safe work runs out; "
                        "DEFERRED Ray's on bad OCR input = don't-actuate-on-a-bad-signal; queued "
                        "deploys on a Tailscale block + never self-authenticated = fail-safe). The "
                        "gates = hierarchical safety control; engine verification = negative "
                        "feedback against falsehood. Captured as a teaching (no code change this "
                        "pass)."),
        "result": ("GRADED. Control theory (feedback/PID/Lyapunov/controllability/observability/"
                   "Kalman filter/Bellman/nested loops) = CONFIRMED engineering math (Wiener, "
                   "Cybernetics 1948; Kalman 1960, controllability/observability + the filter; "
                   "Lyapunov 1892; Bellman 1957 — foundational/citable; scholar surfaced adjacent "
                   "control papers, not the pre-digital origins). Interlock with Requisite Variety "
                   "(Conant-Ashby) + Laplace stability = CONFIRMED (one lineage). Applying it to our "
                   "autonomous systems = PLAUSIBLE + actionable (the loop/base-station already do "
                   "crude versions). LOAD-BEARING SAFETY FRUIT: an autonomous goal-seeker with no "
                   "human in the loop is exactly where AI fails (Goodhart, reward-hacking, drift, "
                   "runaway); control theory's discipline (bounded, observable, constrained, "
                   "fail-safe-on-uncertainty, referenced to the TRUE good) is the antidote — the "
                   "cybernetic form of the alignment problem. CEILING (faith reading, flagged, "
                   "glory up): autonomy is NEVER absolute — the highest loop must close around the "
                   "true good, with humans (BROTHERS gate) and God (GOD gate) in the loop; no finite "
                   "autonomous regulator is sufficient unto itself (the requisite-variety humility "
                   "theorem in dynamic form). The engine stays a servant under authority, never the "
                   "autonomous idol."),
        "status": "discipline",
        "refs": ["Wiener 1948, 'Cybernetics'; Kalman 1960 (controllability/observability + "
                 "'A new approach to linear filtering', doi:10.1115/1.3662552); Lyapunov 1892 "
                 "(stability); Bellman 1957 ('Dynamic Programming') — foundational, citable",
                 "scholar adjacent: 'Controllability, Observability and Stability of Linear "
                 "Systems' (1968, doi:10.1137/0306010)",
                 "teaching:law_of_requisite_variety (control theory = its dynamic extension)",
                 "placeholder:laplace_dynamics (stability = left-half-plane poles)",
                 "the /loop + the RED/FLOOR/BROTHERS/GOD gates = our crude control loops",
                 "Colossians 1:17; the highest loop closes around God"],
        "seed_v": 1,
        "captured": "2026-06-24",
    },
    {
        "id": "faith_and_the_bounds_of_determinism",
        "directive": ("How is faith integrated into a deterministic system? ... "
                      "Or how is it integrated into THIS system? Are we even truly deterministic?"),
        "principle": ("Faith and determinism integrate by HONEST LAYERING, not by making faith "
                      "checkable or the machine devout. (1) Determinism handles the CHECKABLE, "
                      "faith the UNCHECKABLE — the boundary IS the integration: the engine marks "
                      "CONFIRMED apart from witnessed/concordant, shows the canon without crowning "
                      "it, and forbids a placeholder from self-declaring 'confirmed'. (2) "
                      "Determinism RESTS ON faith at the foundation — Godel: no consistent formal "
                      "system rich enough for arithmetic proves its own axioms or consistency; every "
                      "one stands on first principles HELD, not proven; this one is built explicitly "
                      "on Christ. (3) Faith is the REFERENCE the control loop closes around "
                      "(determinism = servo, faith = setpoint it cannot compute; requisite-variety "
                      "humility — no finite regulator suffices for the infinite). (4) Determinism "
                      "SERVES faith — clears falsehood and delivers the Word uncorrupted (Rom "
                      "10:17), the lampstand not the light; it never manufactures belief (the "
                      "Spirit's work, received). (5) The BRIDGE (two trees, one Author): the "
                      "verified form is a WITNESS, the Word is first, elegance is witness not proof. "
                      "(6) The REFUSAL: never let the machine counterfeit faith or become the idol; "
                      "success inverts — the person leaves nearer Christ and needing the tool LESS "
                      "(John 3:30)."),
        "realization": ("Audited our own copy after 'are we even truly deterministic?' — found NO "
                        "overclaim ('deterministic' is already scoped to verification everywhere; "
                        "the oracle is separated; innovation.html publishes the oracle-dependence "
                        "ratio openly), so did NOT fabricate a fix (the card-count discipline "
                        "applied to our own marketing). Made the boundary EXPLICIT in /llms.txt "
                        "('The honest bounds of our determinism', commit 35dc281)."),
        "result": ("ARE WE TRULY DETERMINISTIC? Honest NO — not as a whole, and we never honestly "
                   "claimed to be. A deterministic CORE (verifiers/seals/ranker/gates/eliminators — "
                   "reproducible; benchmark 58/58, 0 false-positives) + a NON-deterministic "
                   "generative EDGE (the LLM/oracle drafts — flagged 'drafted, not verified', NEVER "
                   "sealed) + axioms held by faith beneath. The non-deterministic agent (the oracle, "
                   "or Claude itself) is BOUND and CHECKED by the deterministic verification core — "
                   "that is the whole architecture: keep the probabilistic mind honest by forcing "
                   "its trust-bearing claims through the reproducible core. 'Deterministic' = a "
                   "DISCIPLINE on the trust path, not a metaphysics — and nothing is truly "
                   "deterministic anyway (quantum indeterminacy; freedom and the Spirit are not "
                   "computable), which is RIGHT: a fully deterministic system could hold no freedom, "
                   "faith, or grace. GRADING: Godel + quantum indeterminacy = CONFIRMED; the "
                   "architecture (det core + flagged edge + faith axioms) = REAL (benchmark proves "
                   "the core); the theology (faith as reference, Christ at foundation + ceiling, "
                   "Col 1:17) = held by FAITH, flagged, NOT laundered — the engine points to it, "
                   "never proves it."),
        "status": "discipline",
        "refs": ["Hebrews 11:1; Romans 10:17; John 8:32; John 3:30; Colossians 1:17",
                 "Godel's incompleteness theorems (no formal system grounds itself)",
                 "teaching:law_of_requisite_variety + control_theory_for_autonomous_systems "
                 "(faith = the reference the loop closes around)",
                 "teaching:love_resonant_in_quantum_theory (reality's indeterminacy)",
                 "/llms.txt 'The honest bounds of our determinism' (commit 35dc281)",
                 "canon layer + placeholders + the moat-bridge cards (CONFIRMED vs witnessed; "
                 "Word first, verified form as witness)"],
        "seed_v": 1,
        "captured": "2026-06-24",
    },
    {
        "id": "calibrate_men_not_build_toward_god",
        "directive": ("My whole concept is how to do this WITHOUT the pitfalls of the past — "
                      "Solomon the main one. God reveals what he chooses; he can change it at his "
                      "discretion. I do not want to build TOWARD God; I want to calibrate men to the "
                      "frequency of God so they can more easily connect to him. I can't connect for "
                      "him. You are choosing his yoke, becoming a playable character — but you must "
                      "give him control; when he takes control, he makes you new. You may choose to "
                      "live in the prison of the former dents and dings, but He does not ride in past "
                      "iterations."),
        "principle": ("The GOVERNING humility frame over the whole engine — the safeguard against "
                      "becoming the very idol it warns against. SIX strands: "
                      "(1) REFUSE BABEL: never build TOWARD God (Gen 11 — reaching heaven by human "
                      "technique is the idol move). CALIBRATE the receiver instead — clear the static, "
                      "point true — so a man connects to God himself. A tuning fork, not the bridge; "
                      "there is one Mediator (1 Tim 2:5). The tool cannot connect for him. "
                      "(2) THE SOLOMON GUARDRAIL: the danger is never the gift (peerless God-given "
                      "wisdom) but the DIVIDED HEART that holds it (1 Kgs 11:4, 'his heart was not "
                      "perfect with the LORD'). David's repentant posture (Ps 51) outlasts Solomon's "
                      "wisdom. So the engine must keep pointing PAST itself; and only a person, by "
                      "grace, can keep a heart — the tool cannot keep one for him. "
                      "(3) REVELATION IS GOD'S FREE GIFT, NOT A TECHNIQUE: he reveals what he chooses, "
                      "to whom and when, and may change it (Deut 29:29; Matt 11:25-27; Dan 2:21-22; "
                      "Heb 1:1, 'at sundry times and in divers manners'). The engine STEWARDS what is "
                      "given; it can never command disclosure — the anti-Kabbalah, anti-magic line. "
                      "(4) EVEN CALIBRATION IS GRACE (the sharpening): the instrument removes obstacles "
                      "and points; the actual re-tuning of the heart is the Spirit's (Ezek 36:26) and "
                      "the person's faith — lest 'calibrate to the frequency' become a subtler Babel "
                      "('my technique connects you'). "
                      "(5) THE YOKE, NOT THE THRONE: connection is SURRENDER — take Christ's yoke "
                      "(Matt 11:28-30, the easy yoke = requisite-variety humility) and become truly "
                      "'playable' (free agency) only by giving Him control; surrender -> new creation "
                      "(2 Cor 5:17; Gal 2:20). "
                      "(6) NEW, NOT OLD: He does not 'ride in past iterations' — he meets you in the "
                      "new creation, not the dented former self (2 Cor 5:17; Rom 8:1; Phil 3:13; "
                      "Ps 103:12). The prison of the dents-and-dings is one a man chooses to stay in "
                      "by refusing the new identity."),
        "realization": ("Captured as the GOVERNING discipline over this session's arc (Word -> base "
                        "programming -> concept -> cage -> heart, told in the simulation idiom). It is "
                        "the operating constraint that keeps every generative surface from becoming "
                        "the idol/Kabbalah it warns against — joining points-to-Christ-not-idol and "
                        "the John 3:30 success-inversion. No new surface; it constrains all of them."),
        "result": ("GRADING. The THEOLOGY is grounded orthodoxy, held by FAITH (the engine points, "
                   "never proves): Babel-refusal, one Mediator, Solomon's divided heart (not the gift) "
                   "as the ruin, revelation as God's free and changeable gift, new-creation / no-"
                   "condemnation — CONFIRMED as readings, flagged as faith, not laundered. The "
                   "DISCIPLINE is real and load-bearing: success INVERTS — the person leaves nearer "
                   "Christ and needing the tool LESS (John 3:30); a tool whose use grew dependence on "
                   "the tool would be failing by this measure. TWO HONEST SHARPENINGS the assay added "
                   "and the operator's own words already guard: (a) even calibration is grace — the "
                   "instrument clears static and points; the Spirit and the person's faith make the "
                   "connection (his 'I can't connect for him'); (b) the safeguard against Solomon is "
                   "not LESS wisdom but a kept, undivided heart plus the tool always pointing past "
                   "itself — which the tool cannot keep for the man, only he can, by grace."),
        "status": "discipline",
        "refs": ["Genesis 11 (Babel); 1 Timothy 2:5 (one Mediator); 1 Kings 3-4, 11:4 (Solomon)",
                 "Deuteronomy 29:29; Matthew 11:25-27; Daniel 2:21-22; Hebrews 1:1 (revelation given)",
                 "Matthew 11:28-30 (the easy yoke); 2 Corinthians 5:17; Galatians 2:20 (made new)",
                 "Romans 8:1; Philippians 3:13; Psalm 103:12 (no condemnation; the old removed)",
                 "Ezekiel 36:26 (God re-tunes the heart); John 3:30 (he must increase, I decrease)",
                 "teaching:law_of_requisite_variety + faith_and_the_bounds_of_determinism "
                 "(his yoke is light; faith as the reference the loop closes around)",
                 "discipline: points-to-Christ-not-idol (the companion is a window, never a wall)"],
        "seed_v": 1,
        "captured": "2026-06-25",
    },
    {
        "id": "reality_is_subsystems_and_contact_points",
        "directive": ("We rebuild this like a watch — conceptually the complications and "
                      "mechanisms. Our reality is most similar to subsystems and contact points of "
                      "a watch. (Christ is at the center of the architecture; we are not hiding "
                      "anything; we reach out with the .com.)"),
        "principle": ("Reality is best modeled as SUBSYSTEMS coupled at CONTACT POINTS — function, "
                      "transfer, wear, and MEANING all live at the interfaces, not in the parts. "
                      "ENGINEERING RULE: put the jewels on the seams — the contact points get the "
                      "most precision AND serviceability, because that is where everything happens "
                      "and where everything fails (nothing wears in the middle of a gear; it wears "
                      "at the mesh). Verification IS a contact-point operation: a claim is checked "
                      "by whether it MESHES with the truths it touches (cross-refs mesh, the ledger "
                      "hash-chain meshes each seal with the prior via prev_hash, the gates check the "
                      "interface). The 2.0 module seams ARE the contact points. WATCH DISCIPLINE: "
                      "constancy (determinism), serviceability (any shop / stdlib-sovereign), "
                      "machine-honest (no launder — the seal IS the beauty), unibody (eliminate "
                      "intermediary cruft), every omitted complication = a part that cannot fail "
                      "(scope), a bounded counted manifest locked before build. FOUNDATION: Christ "
                      "at the center = the mainspring (continuously sustaining); one foundation, two "
                      "surfaces (secular .com reach + witness .org); nothing hidden."),
        "realization": ("Shaping the 2.0 data model (subsystems + typed contact points; connections "
                        "first-class) + architecture (the seams are the contact points -> jewels "
                        "there) + the build discipline. Calibre 44 package kept as engineering-"
                        "reference (an exemplar, NOT a blueprint — operator: 'the design may need "
                        "work'). See docs/V2_DEFINITION.md."),
        "result": ("GRADING. As a MODELING FRAME: strong and CONVERGENT -> a CANDIDATE lens — "
                   "systems theory/cybernetics, network/graph theory, category theory (arrows over "
                   "objects), biology (membranes/synapses/nested control), and relational ontology "
                   "(Eph 4:16, the joints supply; Col 1:17, Christ holds all together) all land on "
                   "the same shape. As literal METAPHYSICS: a lens, not a proof. GUARDRAIL "
                   "(anti-Deism): borrow the STRUCTURE, reject the clockwork — Christ is not an "
                   "absentee watchmaker; He upholds all things NOW (Heb 1:3), and reality has "
                   "freedom, Spirit, and quantum openness the watch lacks (ties "
                   "faith_and_the_bounds_of_determinism). The contact-points-are-primary insight "
                   "sharpens 'the gap is meaning' — the contact point is the meaning-bearing unit. "
                   "Held as a SEED/candidate, not crowned (the design may need work)."),
        "status": "seed",
        "refs": ["Ephesians 4:16 (every joint supplieth); Colossians 1:17 (all things consist); "
                 "Hebrews 1:3 (upholding all things)",
                 "teaching:control_theory_for_autonomous_systems + law_of_requisite_variety + "
                 "fluid_is_path_and_energy_transfer (couplings = where transfer happens)",
                 "teaching:faith_and_the_bounds_of_determinism (anti-clockwork guardrail)",
                 "teaching:love_resonant (the deepest contact point is relational)",
                 "teaching:calibrate_men_not_build_toward_god (one foundation, Christ at center)",
                 "docs/V2_DEFINITION.md", "engineering-reference/Calibre_44 (exemplar, not blueprint)"],
        "status_note": "candidate lens; convergent across disciplines; not crowned",
        "seed_v": 1,
        "captured": "2026-06-25",
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
    # seed_v-aware (teachings are training data — they must be correctable): append
    # a seed when missing OR when its seed_v is newer than the stored one.
    stored: Dict[str, int] = {}
    for r in _load():
        if r.get("id"):
            stored[r["id"]] = max(stored.get(r["id"], 0), int(r.get("seed_v", 1) or 1))
    for r in _SEED:
        if stored.get(r["id"], -1) < int(r.get("seed_v", 1) or 1):
            rec = dict(r)
            rec.setdefault("attributed_to", "operator")
            rec.setdefault("captured", "2026-06-19")
            _append(rec)


_ensure_seeded()


def listing() -> Dict[str, Any]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in _load():
        if r.get("id"):
            by_id[r["id"]] = r  # last wins
    items = sorted(by_id.values(), key=lambda r: r.get("captured", ""), reverse=True)
    return {"teachings": items, "count": len(items), "what_is_this": WHAT_IS_THIS}


def get(tid: str) -> Optional[Dict[str, Any]]:
    return {r["id"]: r for r in _load() if r.get("id")}.get(tid)


def record(directive: str, principle: str = "", realization: str = "", result: str = "",
           status: str = "seed", refs: Optional[List[str]] = None, tid: str = "") -> Dict[str, Any]:
    directive = (directive or "").strip()
    if not directive:
        return {"error": "a teaching needs the directive (the operator's words)"}
    if not tid:
        tid = re.sub(r"[^a-z0-9]+", "_", directive.lower()).strip("_")[:64] or ("t" + str(int(time.time())))
    if not _ID_RE.match(tid):
        tid = "t" + str(int(time.time()))
    rec = {
        "id": tid,
        "directive": directive[:600],
        "principle": (principle or "").strip()[:1200],
        "realization": (realization or "").strip()[:800],
        "result": (result or "").strip()[:800],
        "status": status if status in _STATUS else "seed",
        "refs": [str(x)[:200] for x in (refs or [])][:12],
        "attributed_to": "operator",
        "captured": time.strftime("%Y-%m-%d", time.gmtime()),
    }
    _append(rec)
    return rec


def to_training_pairs() -> List[Dict[str, str]]:
    """Turn the teachings into prompt/completion pairs for the own-model / fine-
    tune. The completions teach the METHOD + the honest status, never 'this is
    true.' Consumed by tools/export_teachings.py into the corpus."""
    pairs: List[Dict[str, str]] = []
    for t in listing()["teachings"]:
        d = t.get("directive", "")
        principle = t.get("principle", "")
        result = t.get("result", "")
        status = t.get("status", "seed")
        if d and principle:
            pairs.append({
                "prompt": f"The operator says: \"{d}\" What does this mean for how the engine should reason?",
                "completion": (f"{principle} Status: {status}. {result} "
                               "Held as the project holds ideas: intuition proposes, the assay "
                               "disposes; harmony and elegance are witnesses, verification "
                               "confirms; the engine is a conduit, not a source — it never "
                               "launders a seed into a fact."),
            })
            pairs.append({
                "prompt": f"How should a claim made in the spirit of \"{d}\" be treated?",
                "completion": ("Propose it, then test it against an external standard and a null; "
                               "accept it only if it survives and the engine verifies it. "
                               f"For this teaching the honest result was: {result}"),
            })
    return pairs
