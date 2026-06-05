"""Nested Control Systems — the cross-domain pattern, brought into the engine.

The second orphan. The Nested Control Systems Framework for Chronic Disease
(M.R. Harris, public domain) showed that chronic diseases are not separate
conditions but failures in a nested control architecture: a layer fails when
its LOAD exceeds its CAPACITY (which is exactly Calibre.shadow). This module
makes that pattern callable so any health-domain tool — the Apothecary first —
can stand on it instead of guessing in isolation.

The pattern is fractal: the same five-layer "load vs capacity" shape that
describes a failing body also describes a failing household, org, or region.
Here it is encoded for the body (its first, falsifiable instantiation); the
mapper is deliberately general so other domains can reuse the shape.
"""
from __future__ import annotations
from typing import Dict, List, Optional

# The five nested control layers, cellular → systemic. Each fails when load
# outruns capacity; the phenotype depends on WHICH layer was the entry point.
LAYERS: List[Dict] = [
    {
        "n": 1, "name": "Cellular Stress Response",
        "function": "Protein quality control, DNA repair, mitophagy, apoptosis-vs-repair decisions",
        "phenotypes": ["neurodegenerative disease", "cancer (failed apoptosis)", "accelerated aging", "protein aggregation"],
        "markers": ["elevated HSP", "oxidative markers", "mtDNA damage"],
        "interventions": ["heat shock (sauna)", "time-restricted feeding (mitophagy)", "sleep 7-9h", "antioxidant support"],
        "keywords": ["fatigue", "aging", "cancer", "neurodegener", "alzheimer", "parkinson", "cellular", "mitochond", "dna"],
    },
    {
        "n": 2, "name": "Metabolic Regulation",
        "function": "Energy allocation, fuel switching, insulin/mTOR/AMPK signaling",
        "phenotypes": ["type 2 diabetes", "obesity", "NAFLD/NASH", "metabolic syndrome", "chronic fatigue"],
        "markers": ["HOMA-IR > 2", "elevated TG/HDL", "poor fuel switching", "high fasting glucose"],
        "interventions": ["low-carb/keto", "time-restricted feeding", "Zone 2 exercise", "resistance training", "NAD+ support"],
        "keywords": ["diabetes", "blood sugar", "glucose", "insulin", "weight", "obes", "fatty liver", "metabolic", "energy", "tired"],
    },
    {
        "n": 3, "name": "Immune Surveillance",
        "function": "Self/non-self distinction, inflammation resolution, tolerance, clearance",
        "phenotypes": ["autoimmune disease", "chronic low-grade inflammation", "type 1 diabetes", "IBD", "MS", "RA"],
        "markers": ["hsCRP > 3", "elevated cytokines", "autoantibodies"],
        "interventions": ["vagal tone (HRV biofeedback)", "cold exposure", "omega-3 (EPA+DHA)", "elimination diet", "gut support"],
        "keywords": ["autoimmune", "inflammation", "arthritis", "allerg", "ibd", "crohn", "colitis", "lupus", "thyroid", "immune", "infection"],
    },
    {
        "n": 4, "name": "Tissue Homeostasis",
        "function": "Structural integrity, angiogenesis, ECM remodeling, stem-cell activation",
        "phenotypes": ["organ-specific damage", "atherosclerosis", "osteoporosis", "sarcopenia", "fibrosis"],
        "markers": ["structural damage on imaging", "organ-specific biomarkers"],
        "interventions": ["Zone 2 training (angiogenesis)", "vitamin C / glycine / collagen", "tissue-specific loading"],
        "keywords": ["heart disease", "atheroscler", "bone", "osteo", "muscle", "sarcopenia", "fibrosis", "joint", "tissue", "wound", "skin"],
    },
    {
        "n": 5, "name": "Systemic Coordination",
        "function": "ANS regulation (vagal brake), HPA axis, circadian gating, allostatic load",
        "phenotypes": ["dysautonomia", "chronic pain", "sleep disorders", "stress-related conditions"],
        "markers": ["low HRV (< 20 RMSSD)", "dysregulated cortisol", "poor sleep"],
        "interventions": ["circadian alignment (morning light)", "sleep hygiene 7-9h", "breath work", "HRV monitoring"],
        "keywords": ["anxiety", "stress", "sleep", "insomnia", "pain", "chronic pain", "fatigue", "burnout", "depress", "nervous", "panic", "exhaust"],
    },
]

# Exit gates the framework names — the referral discipline. A tool standing on
# this floor MUST surface these, never overrun them. This is the medical
# "patterns, not people / never stand between the sick and a physician" line.
EXIT_CRITERIA = [
    "Framework not applicable to this presentation.",
    "Graduated to maintenance.",
    "Requires medical intervention — refer to a licensed clinician.",
]

REFERRAL_NOTE = (
    "This is a control-systems map, not a diagnosis. It augments and measures; "
    "it never replaces a physician. Acute, severe, or worsening symptoms → seek care."
)


def identify_layers(text: str) -> List[Dict]:
    """Map a condition / description to the control layer(s) most likely failing.

    Keyword match across the five layers. Returns matched layers, most-signals
    first. Deliberately conservative — returns [] when nothing matches rather
    than guessing, so the tool can say 'no layer identified' honestly.
    """
    t = (text or "").lower()
    hits = []
    for layer in LAYERS:
        score = sum(1 for kw in layer["keywords"] if kw in t)
        if score:
            hits.append((score, layer))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [layer for _score, layer in hits]


def layer_view(text: str, *, load: Optional[float] = None, capacity: Optional[float] = None) -> Dict:
    """The full nested-control reading for a condition, including the shadow
    (load vs capacity) when those signals are provided. This is the bridge to
    Calibre: the same max(0, load - capacity) that casts the shadow.
    """
    matched = identify_layers(text)
    out: Dict = {
        "matched_layers": [
            {"n": l["n"], "name": l["name"], "function": l["function"],
             "phenotypes": l["phenotypes"][:4], "interventions": l["interventions"],
             "markers": l["markers"]}
            for l in matched[:3]
        ],
        "primary_layer": (matched[0]["name"] if matched else None),
        "exit_criteria": EXIT_CRITERIA,
        "referral_note": REFERRAL_NOTE,
    }
    if load is not None and capacity is not None:
        try:
            from api import calibre as _cal
            out["shadow"] = round(_cal.shadow(1.0, capacity, load), 4)
            out["overloaded"] = bool(load > capacity)
        except Exception:
            pass
    return out
