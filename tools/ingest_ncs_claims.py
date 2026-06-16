#!/usr/bin/env python3
"""ingest_ncs_claims.py -- bring the Nested Control Systems Framework's
claim->evidence appendix into the almanac as ATTRIBUTED entries.

Source: research/nested_control_systems/ (public domain; 20 peer-reviewed refs).
Each framework claim is appended to data/almanac/entries.jsonl as a verified-by-
CITATION entry. Verdict = CONCORDANT (concordant with the cited peer-reviewed
literature, ATTRIBUTED to it) -- NOT CONFIRMED/HOLDS: the engine did not re-derive
these; they are bound to their source, which is exactly the concordance discipline
(a claim is valid by a chain to its source). The framework's own NHANES falsification
verdicts remain pending a run -- this ingests the cited mechanistic claims, not a
validation result.

Idempotent + re-runnable: skips any id already present. Pure ASCII.
Usage:  python tools/ingest_ncs_claims.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"

ANCHOR = "nested_control_systems_framework"
LIFE = "connection_life_runs_on_a_few_mappable_laws"
REAL = "connection_reality_is_mappable"
BODY = "almanac_the_body_is_held_by_a_pattern_not_just_parts"
DNA = "connection_dna_is_the_language_of_life"
PROV = "connection_practical_provision_for_the_least"


def _e(id, title, domains, axes, verification, wisdom, kw, bonds, category="health"):
    return {
        "id": id, "kind": "almanac", "title": title, "category": category,
        "domains": domains, "axes": axes, "verdict": "CONCORDANT",
        "verification": verification, "wisdom": wisdom,
        "triggers": {"keywords": kw, "axes": axes}, "bonds": bonds,
    }


ENTRIES = [
    _e(ANCHOR,
       "Chronic disease is the failure of a nested control system, not a set of separate diseases.",
       ["medicine", "biology"], ["conservation_balance", "authority_trust", "metabolism"],
       "The Nested Control Systems Framework (public domain) holds that chronic diseases are not "
       "separate conditions but different phenotypes of failures in a FIVE-LAYER nested control "
       "architecture: L1 cellular stress (HSP/UPR, mitophagy, DNA-damage response), L2 metabolic "
       "regulation (insulin/mTOR/AMPK), L3 immune surveillance (inflammation resolution), L4 tissue "
       "homeostasis (ECM, angiogenesis), L5 systemic coordination (ANS, HPA, circadian, allostatic "
       "load). The layers NEST -- theories once thought to compete are functional levels of one "
       "system. Attributed to: Barabasi, Gulbahce, Loscalzo (2011), Network medicine, Nat Rev Genet "
       "12:56-68; framework staged at research/nested_control_systems (20 peer-reviewed refs).",
       "Concordant with network-medicine and the cited mechanistic literature; NOT engine-sealed. "
       "The framework is falsifiable -- a pre-registered NHANES pipeline exists; its verdicts pend a "
       "run. Honest gap: NHANES lacks direct L1 markers (HSP70, gamma-H2AX, UPR), so the L1 layer is "
       "not yet empirically tested. Same phenotype from many mechanisms (e.g. hyperglycemia via "
       "autoimmune, insulin-resistant, genetic, or structural pathways) is discern-and-catalog "
       "applied to disease.",
       ["nested control systems", "chronic disease", "network medicine", "phenotype", "mechanism",
        "homeostasis", "L1", "L2", "L3", "L4", "L5", "body systems"],
       [LIFE, REAL, BODY], category="cross_domain"),

    _e("ncs_l5_neurovisceral_integration",
       "Autonomic regulation is linked to emotion and behavior via brain-heart (neurovisceral) networks.",
       ["medicine", "biology"], ["authority_trust", "conservation_balance"],
       "Layer 5 (systemic coordination). The neurovisceral integration model: ANS function and "
       "emotional/behavioral regulation are coupled through brain-heart pathways. Attributed to: "
       "Thayer & Lane (2000), J Affect Disord 61:201-216; Thayer & Lane (2009), Neurosci Biobehav "
       "Rev 33:81-88.",
       "A well-supported integrative model; attributed, not engine-derived. The vagal brake (HRV) is "
       "its most measurable handle (see ncs_l5_hrv_standards).",
       ["neurovisceral", "autonomic", "vagal", "heart-brain", "HRV", "emotion regulation", "layer 5"],
       [ANCHOR, LIFE]),

    _e("ncs_l5_hrv_standards",
       "Heart rate variability (HRV) has defined measurement standards for tracking autonomic function.",
       ["medicine", "statistics"], ["authority_trust", "conservation_balance"],
       "Layer 5. HRV metrics index ANS function and have standardized measurement/interpretation "
       "conventions; recovery dynamics (baseline -> perturbation -> recovery) carry more information "
       "than static baseline. Attributed to: Task Force ESC/NASPE (1996), Eur Heart J 17:354-381; "
       "Shaffer & Ginsberg (2017), Front Public Health 5:258.",
       "Measurement standard, well-established; attributed. HRV is a cheap, non-invasive window on "
       "the L5 vagal brake -- useful for the apothecary's reference layer.",
       ["heart rate variability", "HRV", "autonomic", "vagal tone", "measurement standard", "layer 5"],
       [ANCHOR, LIFE], category="health"),

    _e("ncs_l5_lcne_adaptive_gain",
       "The LC-NE system provides adaptive gain, controlling arousal and precision-weighting.",
       ["biology", "medicine"], ["authority_trust", "conservation_balance"],
       "Layer 5. Locus coeruleus-norepinephrine adaptive gain modulates arousal and the precision "
       "(gain) of cognitive processing. Attributed to: Aston-Jones & Cohen (2005), Annu Rev Neurosci "
       "28:403-450.",
       "A control-theoretic account of arousal; attributed. Gain control is the same idea as the "
       "engine's weighting of which signals to trust -- a recurring nested-control form.",
       ["LC-NE", "locus coeruleus", "norepinephrine", "adaptive gain", "arousal", "precision", "layer 5"],
       [ANCHOR, LIFE], category="biology"),

    _e("ncs_l5_predictive_processing",
       "Predictive processing: the brain minimizes hierarchical prediction error as a computational principle.",
       ["biology", "computer_science"], ["authority_trust", "conservation_balance"],
       "Layer 5 / cross-cutting. The brain is modeled as a hierarchy minimizing prediction error "
       "(free-energy / predictive coding). Attributed to: Friston (2005), Phil Trans R Soc B "
       "360:815-836.",
       "An influential computational framework; attributed, and itself still debated at the edges. "
       "Hierarchical error-minimization is the nested-control architecture in the brain.",
       ["predictive processing", "prediction error", "free energy", "Friston", "hierarchy", "layer 5"],
       [ANCHOR, REAL], category="biology"),

    _e("ncs_l5_interoception_allostasis",
       "Interoceptive predictions are the brain's anticipatory model of bodily states (allostatic regulation).",
       ["biology", "medicine"], ["authority_trust", "conservation_balance"],
       "Layer 5. Interoception = the brain's predictive model of internal bodily states; allostasis "
       "= regulation by anticipation rather than reaction. Attributed to: Barrett & Simmons (2015), "
       "Nat Rev Neurosci 16:419-429; Stephan et al. (2023), Front Hum Neurosci 16:1032319.",
       "Attributed; the allostatic-load idea links chronic stress to systemic dysregulation -- the "
       "L5 failure mode (dysautonomia, chronic pain, sleep, stress conditions).",
       ["interoception", "allostasis", "allostatic load", "predictive", "bodily states", "layer 5"],
       [ANCHOR, LIFE], category="biology"),

    _e("ncs_l5_autism_hrv",
       "Altered HRV patterns in autism indicate autonomic dysregulation.",
       ["medicine", "statistics"], ["authority_trust", "conservation_balance"],
       "Layer 5. Meta-analytic evidence of altered HRV (autonomic dysregulation) in autism spectrum "
       "disorders. Attributed to: Cheng, Huang & Huang (2020), Neurosci Biobehav Rev 118:463-471; "
       "Bast, Poustka & Freitag (2019), Autism Res 12:1680-1692.",
       "Association/meta-analysis -- attributed, NOT a causal or diagnostic claim. An example of an "
       "L5 systemic-coordination signal observable downstream.",
       ["autism", "HRV", "autonomic dysregulation", "ASD", "meta-analysis", "layer 5"],
       [ANCHOR, LIFE], category="health"),

    _e("ncs_l3_inflammation_metabolic",
       "Chronic low-grade inflammation is implicated in metabolic disorders (obesity-linked insulin resistance).",
       ["medicine", "biology"], ["metabolism", "conservation_balance"],
       "Layer 3 (immune surveillance) <-> Layer 2 coupling. Chronic low-grade inflammation is "
       "centrally implicated in metabolic disease and ages-related disease. Attributed to: "
       "Hotamisligil (2006), Nature 444:860-867; Furman, Campisi, Verdin et al. (2019), Nat Med "
       "25:1822-1832.",
       "Strongly supported in the literature; attributed. Cross-layer coupling (immune <-> metabolic) "
       "is the point -- the layers nest, they do not act alone.",
       ["inflammation", "metabolic", "insulin resistance", "obesity", "inflammaging", "layer 3"],
       [ANCHOR, BODY], category="medicine"),

    _e("ncs_l2_insulin_resistance_hetero",
       "Insulin resistance involves heterogeneous mechanisms (signaling disruption and substrate flux).",
       ["medicine", "biology"], ["metabolism", "conservation_balance"],
       "Layer 2 (metabolic regulation). Insulin resistance is not one mechanism but several "
       "(signaling-pathway disruptions, altered substrate flux), so it needs assessment beyond "
       "fasting glucose. Attributed to: Samuel & Shulman (2016), J Clin Invest 126:12-22; Samuel & "
       "Shulman (2012), Cell 148:852-871.",
       "Attributed. The heterogeneity is the multi-path insight applied to L2 -- same clinical "
       "presentation, several mechanistic routes.",
       ["insulin resistance", "substrate flux", "metabolic", "Shulman", "heterogeneity", "layer 2"],
       [ANCHOR, LIFE], category="medicine"),

    _e("ncs_l2_fasting_adaptive",
       "Fasting triggers conserved adaptive cellular responses (oxidative stress, inflammation, energy metabolism).",
       ["medicine", "biology", "nutrition"], ["metabolism", "conservation_balance"],
       "Layer 2 / Layer 1 coupling. Fasting induces conserved molecular adaptations affecting "
       "cellular stress, inflammation, and metabolic pathways; fuel-switching capacity "
       "(glucose <-> fat <-> ketones) is assessable by dietary challenge. Attributed to: Longo & "
       "Mattson (2014), Cell Metab 19:181-192.",
       "Attributed; mechanism well-characterized. Actionable for the apothecary's reference layer "
       "(fasting as a metabolic-flexibility lever) -- reference, not medical advice.",
       ["fasting", "metabolic flexibility", "ketones", "autophagy", "fuel switching", "layer 2"],
       [ANCHOR, LIFE], category="health"),

    _e("ncs_l2_ultraprocessed_intake",
       "Ultra-processed food increases ad libitum energy intake versus minimally processed diets (RCT).",
       ["nutrition", "medicine"], ["metabolism", "conservation_balance"],
       "Layer 2. In a controlled inpatient RCT, ultra-processed diets caused excess calorie intake "
       "and weight gain versus minimally processed diets matched for macronutrients -- composition "
       "affects metabolic regulation independent of macros. Attributed to: Hall, Ayuketah, Brychta "
       "et al. (2019), Cell Metab 30:67-77.",
       "A randomized controlled trial (strong design); attributed. This is the bridge from the food "
       "system to L2 dysregulation -- the empirical root under 'tie the food system together'.",
       ["ultra-processed food", "calorie intake", "diet", "metabolic", "RCT", "food system", "layer 2"],
       [ANCHOR, PROV], category="agriculture"),

    _e("ncs_l1_mitophagy",
       "Mitophagy (selective autophagy of mitochondria) is critical for cellular homeostasis and quality control.",
       ["biology", "medicine"], ["metabolism", "conservation_balance"],
       "Layer 1 (cellular stress response). Mitophagy clears damaged mitochondria and maintains "
       "cellular homeostasis; its failure contributes to aging and disease. Attributed to: Palikaras, "
       "Lionaki & Tavernarakis (2018), Nat Cell Biol 20:1013-1022.",
       "Attributed; mechanistically central. NHANES cannot measure L1 directly -- this is the layer "
       "whose true validation needs molecular proteomics (UK Biobank Olink). Honest gap named.",
       ["mitophagy", "autophagy", "mitochondria", "cellular stress", "quality control", "layer 1"],
       [ANCHOR, DNA], category="biology"),

    _e("ncs_l1_nad_metabolism",
       "NAD+ metabolism is central to cellular energy production, stress response, and longevity pathways.",
       ["biology", "medicine", "chemistry"], ["metabolism", "conservation_balance"],
       "Layer 1. NAD+ is a hub of cellular energy metabolism and stress-response/longevity signaling "
       "(sirtuins, PARPs). Attributed to: Belenky, Bogan & Brenner (2007), Trends Biochem Sci "
       "32:12-19; Longo & Mattson (2014), Cell Metab 19:181-192.",
       "Attributed; a genuine cellular hub. Like mitophagy, an L1 mechanism NHANES does not measure "
       "-- part of the framework's honestly-flagged validation gap.",
       ["NAD", "cellular energy", "sirtuins", "longevity", "stress response", "layer 1"],
       [ANCHOR, DNA], category="biology"),
]


def main():
    existing = set()
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    added, skipped = [], []
    with OUT.open("a", encoding="utf-8") as f:
        for e in ENTRIES:
            if e["id"] in existing:
                skipped.append(e["id"])
                continue
            # guard: pure ASCII
            blob = json.dumps(e, ensure_ascii=True)
            f.write(blob + "\n")
            added.append(e["id"])
    print(json.dumps({"added": added, "skipped": skipped,
                      "n_added": len(added), "n_skipped": len(skipped)}, indent=2))


if __name__ == "__main__":
    main()
