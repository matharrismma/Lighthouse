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
        "realization": "Captured as a seed; the honest kernel (turbulence<->Fourier modes<->energy cascade) noted.",
        "result": "NOT yet tested — a seed. To assay: is the eigenvalue spectrum a power-law cascade?",
        "status": "seed",
        "refs": ["placeholder:fluid_dynamics_axes"],
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
    have = {r.get("id") for r in _load()}
    for r in _SEED:
        if r["id"] not in have:
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
