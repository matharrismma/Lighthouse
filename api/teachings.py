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
