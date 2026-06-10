#!/usr/bin/env python
"""Seed 15 supplement reviews using the engine's Review Framework v1.

Framework defined in pipeline/REVIEW_FRAMEWORK.md. Each review carries:
  - 4 independent grades (evidence / mechanism / quality / value)
  - composite verdict (CONFIRMED / MIXED / MISMATCH / OBSOLETE)
  - claims_audit (marketing claim → verdict map)
  - honest what-it-does + what-it-doesn't
  - drug interactions + see-a-doctor thresholds

Verdict distribution chosen to honestly reflect the supplement market:
  CONFIRMED  3  (creatine, melatonin for specific use, magnesium with form caveat)
  CONFIRMED-with-caveat  2  (vitamin D for deficient, iron for deficient)
  MIXED      9  (the bulk — works in part, marketed beyond evidence)
  MISMATCH   1  (saw palmetto — large RCTs show null)

The Shepherd is not a doctor. Each review notes when professional consultation
is required. Drug interactions are flagged. Self-care thresholds are explicit.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── 1 ─ Multivitamins (MIXED) ──────────────────────────────────────
    {
        "id": "review_multivitamin_general",
        "kind": "review",
        "title": "Multivitamin (general daily) — modest cancer signal, null cardiovascular, healthy diet still primary",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Daily multivitamin / multimineral (general adult formulation)",
        "grades": {
            "evidence": "B",
            "mechanism": "B",
            "quality": "B",
            "value": "$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "A daily multivitamin/multimineral provides 50–200% RDA of major nutrients in one pill. Best evidence base: Physicians' Health Study II (n=14,641, 11-year follow-up, JAMA 2012) showed modest reduction in total cancer incidence (~8% RR reduction, 0.92, p=0.04) but no benefit for cardiovascular events or all-cause mortality. COSMOS-Mind (2022) showed cognitive function benefit in older adults. For nutritionally adequate adults, marginal effect on hard endpoints; for adults with poor diet, more useful. The label promises far exceed the data.",
        "category": "medicine",
        "domains": ["medicine", "nutrition", "statistics"],
        "axes": ["metabolism", "authority_trust"],
        "claims_audit": [
            {"marketing_claim": "Fills nutritional gaps", "verdict": "MIXED", "note": "True if your diet has gaps; many users have adequate intake from diet alone"},
            {"marketing_claim": "Boosts energy", "verdict": "MISMATCH", "note": "No energy effect in non-deficient adults"},
            {"marketing_claim": "Prevents cancer", "verdict": "MIXED", "note": "PHS-II showed ~8% relative reduction in total cancer; effect modest, not preventive in strong sense"},
            {"marketing_claim": "Supports immune system", "verdict": "MIXED", "note": "Plausible for specific nutrients (vitamin D, zinc) in deficiency states; vague claim otherwise"},
        ],
        "what_it_does": "Provides a baseline of micronutrients that meets RDA. Modest cancer reduction (PHS-II); cognitive function benefit in older adults (COSMOS). Particularly relevant for: restrictive diets, elderly, pregnancy (prenatal-specific formulation), bariatric surgery patients.",
        "what_it_doesnt": "Does not provide an energy boost in non-deficient adults. Does not prevent cardiovascular events (multiple RCTs null). Does not replace a varied diet. High-dose mega-vitamin marketing claims are not supported.",
        "better_alternatives": "Varied diet with fruit, vegetables, whole grains, legumes, fish. Targeted supplementation (vitamin D, B12 if vegan, iron if deficient, folic acid in pregnancy) often makes more sense than blanket multivitamins.",
        "pre_run": {
            "summary": "Modest benefit detected at population scale (PHS-II) for cancer; null for cardiovascular. Individual variation huge.",
            "domain_results": [
                {"domain": "medicine",   "verdict": "MIXED", "detail": "PHS-II: total cancer RR 0.92 (p=0.04); cardiovascular RR null. COSMOS-Mind: cognitive benefit in 60+", "data": {"PHSII_cancer_RR": 0.92, "PHSII_CV_RR": 1.01}},
                {"domain": "nutrition",  "verdict": "CONFIRMED", "detail": "Provides RDA of major micronutrients in one pill (chemistry is reliable)", "data": {}},
                {"domain": "statistics", "verdict": "CONFIRMED", "detail": "Effect sizes detected only in well-powered trials; individual user cannot detect benefit", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["multivitamin (Centrum Adult, Kirkland, Rainbow Light, or any USP-Verified mark)"],
            "tools": [],
            "steps": ["take 1 tablet daily with food (fat-soluble vitamins absorbed better with meal)", "avoid mega-dose formulations (>200% RDA of fat-soluble vitamins can accumulate; high-dose vitamin E showed harm in some trials)", "if pregnant: use prenatal formulation with adequate folic acid (400-800 mcg)"],
            "time": "ongoing if poor diet; episodic if good diet",
            "cost_usd_2026": "$8–25/month",
            "scale": "general adults with poor diet, restrictive diets, elderly. **SEE A DOCTOR** before supplementing if: pregnancy (specific prenatal needed), kidney disease (fat-soluble vitamin accumulation risk), on warfarin (vitamin K interactions), kidney stones (calcium considerations)",
        },
        "wisdom": "A multivitamin is insurance, not treatment. The Shepherd brings this when the user has dietary gaps or restrictions — and notes that a varied diet is the keeping's first recommendation. Healthy adults with adequate diet get marginal benefit; mega-dose formulations show occasional harm (vitamin E HOPE-TOO).",
        "triggers": {"keywords": ["multivitamin", "Centrum", "daily vitamin", "supplement", "micronutrient"], "axes": ["metabolism", "authority_trust"]},
    },

    # ── 2 ─ Vitamin D (CONFIRMED for deficient, MIXED for general) ────
    {
        "id": "review_vitamin_d_supplementation",
        "kind": "review",
        "title": "Vitamin D — CONFIRMED for deficiency (25-OH <20 ng/mL); MIXED for healthy populations",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Vitamin D3 (cholecalciferol) 1000–4000 IU daily",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "A",
            "value": "$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Vitamin D3 supplementation at 1000–4000 IU/day raises serum 25-hydroxyvitamin D. CONFIRMED benefits in deficient populations: rickets (children), osteomalacia (adults), reduced fracture risk in elderly with low baseline. MIXED in healthy populations with adequate baseline: VITAL trial (n=25,871, NEJM 2019) was largely null for cancer prevention, cardiovascular events, and depression in non-deficient adults. The 'vitamin D fixes everything' marketing outruns the data; correcting actual deficiency does benefit health.",
        "category": "medicine",
        "domains": ["medicine", "nutrition", "chemistry", "statistics"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Boosts immune system", "verdict": "MIXED", "note": "Plausible for deficient individuals; meta-analyses show small reduction in respiratory infections at population level"},
            {"marketing_claim": "Prevents cancer", "verdict": "MISMATCH", "note": "VITAL trial null for cancer incidence; subgroup analysis hints at lower cancer mortality but not primary endpoint"},
            {"marketing_claim": "Prevents falls/fractures", "verdict": "CONFIRMED", "note": "In deficient elderly; not in vitamin-D-replete populations"},
            {"marketing_claim": "Improves mood / depression", "verdict": "MIXED", "note": "VITAL-DEP null in non-deficient; possibly helpful in seasonal affective with deficiency"},
        ],
        "what_it_does": "Raises serum 25-OH-D when below 20 ng/mL. Essential for calcium absorption, bone mineralization, immune regulation. Deficient populations (winter latitudes, dark skin in low-sun environments, elderly, obese, malabsorption) see clear clinical benefit from correction.",
        "what_it_doesnt": "Does not cure non-deficient adults of anything VITAL measured. Mega-doses (>10,000 IU/day chronic) carry hypercalcemia risk. The 'vitamin D pandemic prevention' claims of 2020–2021 were not borne out in subsequent trials.",
        "better_alternatives": "Test 25-OH-D level first (most doctors will order this). If ≥30 ng/mL: supplementation probably unnecessary. If <20 ng/mL: 2000–4000 IU/day for 8 weeks, retest. Sun exposure (10–30 min on arms/face, midday, 3×/week) produces vitamin D for those who can.",
        "pre_run": {
            "summary": "Test first, treat the deficient, leave the rest alone. Mechanism is clean (steroid hormone, VDR, calcium homeostasis); benefit windows are population-specific.",
            "domain_results": [
                {"domain": "medicine",   "verdict": "CONFIRMED", "detail": "Deficiency causes rickets/osteomalacia; supplementation corrects (Cochrane)", "data": {"target_25OH_D_ng_per_mL": 30}},
                {"domain": "medicine",   "verdict": "MIXED", "detail": "VITAL trial null for cancer, cardiovascular, fractures in non-deficient adults", "data": {"n": 25871}},
                {"domain": "chemistry",  "verdict": "CONFIRMED", "detail": "Cholecalciferol → 25-OH-D (liver) → 1,25-(OH)2-D (kidney) → VDR transcription", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["vitamin D3 (cholecalciferol) 1000-4000 IU softgels or drops", "blood test (25-OH-D) before/after"],
            "tools": [],
            "steps": ["TEST 25-OH-D BLOOD LEVEL first; if ≥30 ng/mL, generally adequate", "if 20-29 ng/mL: 1000-2000 IU/day with fat-containing meal", "if <20 ng/mL: 2000-4000 IU/day with food, retest in 8 weeks", "take with fat (egg yolk, avocado, nut butter) for absorption", "vitamin D3 (cholecalciferol) preferred over D2 (ergocalciferol) — 3× more potent at raising serum levels"],
            "time": "8 weeks to retest after starting; ongoing if deficient",
            "cost_usd_2026": "$5–15 for several months",
            "scale": "deficient or at-risk adults. **SEE A DOCTOR** for: testing 25-OH-D, sarcoidosis (hypercalcemia risk), kidney disease, parathyroid disease, pregnancy",
        },
        "wisdom": "Vitamin D was the supplement story of the 2010s — observational data suggested it prevented everything; RCTs subsequently showed it prevents the things it was originally for (bone disease, deficiency states) but not the additional 30 claims that grew up around it. The Shepherd brings this with the testing-first principle: cheap blood test, then targeted action.",
        "triggers": {"keywords": ["vitamin D", "cholecalciferol", "D3", "25-OH-D", "rickets", "VITAL trial"], "axes": ["metabolism"]},
    },

    # ── 3 ─ Magnesium (CONFIRMED with form caveat) ─────────────────────
    {
        "id": "review_magnesium_form_matters",
        "kind": "review",
        "title": "Magnesium — CONFIRMED for deficiency; form matters (glycinate/citrate >> oxide for absorption)",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Magnesium glycinate / citrate / malate (200–400 mg elemental Mg/day)",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "B",
            "value": "$",
        },
        "composite_verdict": "CONFIRMED",
        "verdict": "CONFIRMED",
        "situation": "Magnesium is essential for ~300 enzymatic reactions including ATP synthesis, muscle contraction, nerve transmission. CONFIRMED benefits: leg cramps (multiple RCTs), migraine prophylaxis (400-600 mg/day, AAN guideline recommendation), constipation (osmotic effect), mild blood pressure reduction (~2-4 mmHg). Form matters enormously: magnesium oxide is poorly absorbed (~4% bioavailable); magnesium glycinate, citrate, malate, and threonate are 30–60% bioavailable. Many cheap supplements use oxide; consumers pay for magnesium they don't absorb.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "nutrition"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Better sleep", "verdict": "MIXED", "note": "Magnesium glycinate has some sleep-quality data; not as strong as advertising suggests"},
            {"marketing_claim": "Reduces muscle cramps", "verdict": "CONFIRMED", "note": "Multiple RCTs in pregnancy and idiopathic; meta-analyses positive"},
            {"marketing_claim": "Migraine prevention", "verdict": "CONFIRMED", "note": "American Academy of Neurology Level B recommendation"},
            {"marketing_claim": "Lowers blood pressure", "verdict": "MIXED", "note": "Real but small (~2-4 mmHg); not a replacement for antihypertensives"},
            {"marketing_claim": "Cures anxiety", "verdict": "MIXED", "note": "Modest effect in deficient individuals; popular claim outruns specific data"},
        ],
        "what_it_does": "Replenishes magnesium when intake is inadequate (common in modern diets — only ~50% of Americans meet RDA). Specifically effective for: leg cramps, migraine prophylaxis, constipation, mild BP reduction. Glycinate form is best tolerated; citrate has mild laxative effect; oxide is mostly laxative (poor absorption otherwise).",
        "what_it_doesnt": "Magnesium oxide tablets are mostly a placebo for systemic magnesium repletion (laxative only). 'Sleep magnesium' claims oversold beyond the data. Calm/stress-relief claims rely on placebo + mild GABA-A activity at high tissue levels.",
        "better_alternatives": "Dietary: pumpkin seeds, almonds, dark chocolate, leafy greens, whole grains. If supplementing, pick glycinate or citrate; avoid oxide unless laxative effect desired.",
        "pre_run": {
            "summary": "Real clinical effects + clear mechanism + bioavailability depends on form. The form question is the single most useful piece of information for a magnesium supplement.",
            "domain_results": [
                {"domain": "chemistry",  "verdict": "CONFIRMED", "detail": "Mg²⁺ cofactor for ~300 enzymes; ATP requires Mg-ATP complex", "data": {}},
                {"domain": "medicine",   "verdict": "CONFIRMED", "detail": "Migraine prophylaxis (AAN Level B), leg cramps (Cochrane), constipation (osmotic)", "data": {}},
                {"domain": "nutrition",  "verdict": "CONFIRMED", "detail": "Bioavailability: glycinate ~40%, citrate ~30%, oxide ~4%", "data": {"oxide_bioavail_pct": 4, "glycinate_bioavail_pct": 40}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["magnesium glycinate or citrate (NOT oxide), 200-400 mg elemental Mg/day"],
            "tools": [],
            "steps": ["take with food to reduce GI symptoms", "start with 200 mg and titrate up if needed", "if BM frequency increases (citrate especially): reduce dose or switch form", "for migraine prevention: 400-600 mg/day standard"],
            "time": "ongoing if effective; trial 4-8 weeks for migraine endpoint",
            "cost_usd_2026": "$10-20/month for quality form",
            "scale": "general adults with low dietary Mg. **SEE A DOCTOR** for: kidney disease (excretion impaired, accumulation risk), heart block (Mg lowers HR), pregnancy at high doses",
        },
        "wisdom": "The form question saves money and improves outcomes. The Shepherd brings glycinate or citrate to the user asking about magnesium — and notes that 'magnesium oxide' tablets sold by the bottle are mostly inert from a systemic-Mg perspective. The chemistry doesn't care about marketing; absorption is what reaches the cell.",
        "triggers": {"keywords": ["magnesium", "Mg glycinate", "Mg citrate", "Mg oxide", "migraine prevention", "leg cramps"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 4 ─ Fish oil / Omega-3 (MIXED) ─────────────────────────────────
    {
        "id": "review_fish_oil_omega3",
        "kind": "review",
        "title": "Fish oil (EPA/DHA) — MIXED for general cardiovascular; CONFIRMED for hypertriglyceridemia at prescription dose",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Fish oil / Omega-3 EPA + DHA (1–4 g/day)",
        "grades": {
            "evidence": "B",
            "mechanism": "A",
            "quality": "C",
            "value": "$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Omega-3 polyunsaturated fatty acids (EPA + DHA) are essential structural components of cell membranes and precursors of anti-inflammatory eicosanoids. Cardiovascular outcomes from supplementation have been revised downward repeatedly: VITAL (n=25,871, 2019), ASCEND (n=15,480, 2018), and STRENGTH (n=13,078, 2020) all null for major cardiac events at general supplement doses. REDUCE-IT (icosapent ethyl 4 g/day, prescription) showed 25% reduction in major adverse cardiovascular events in high-risk patients. Triglyceride lowering is CONFIRMED at 2-4 g/day. General-public 'fish oil for heart health' marketing is not supported.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "nutrition", "statistics"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Heart health", "verdict": "MIXED", "note": "Multiple large RCTs null for primary prevention; prescription icosapent ethyl effective in specific high-risk patients"},
            {"marketing_claim": "Lowers triglycerides", "verdict": "CONFIRMED", "note": "2-4 g/day reduces TG ~20-30%"},
            {"marketing_claim": "Reduces inflammation", "verdict": "MIXED", "note": "Plausible mechanism, modest clinical effect; rheumatoid arthritis: small benefit"},
            {"marketing_claim": "Brain / cognitive function", "verdict": "MIXED", "note": "Modest effect on some cognitive measures in elderly; cognitive dementia prevention null in RCTs"},
            {"marketing_claim": "Joint pain reduction", "verdict": "MIXED", "note": "Modest effect in RA (high-dose); generic 'joint health' claims weak"},
        ],
        "what_it_does": "Triglyceride-lowering at 2-4 g EPA+DHA daily (CONFIRMED). Cell-membrane incorporation, eicosanoid balance shift. Specific high-risk cardiovascular populations benefit from prescription icosapent ethyl (Vascepa).",
        "what_it_doesnt": "Does not prevent first cardiovascular events in healthy adults at typical supplement doses (1g/day combined EPA+DHA). 'Smart pill' / cognitive-enhancement claims unsupported. General anti-inflammatory claims overrun the data.",
        "better_alternatives": "Fatty fish 2× weekly (salmon, sardines, mackerel) — provides similar EPA/DHA at lower cost with whole-food benefits. For hypertriglyceridemia: discuss prescription icosapent ethyl with doctor.",
        "pre_run": {
            "summary": "Cardiovascular benefit at population scale was overstated by early observational data and not confirmed in modern RCTs. Specific subgroup (high-risk patients on prescription EPA) does benefit.",
            "domain_results": [
                {"domain": "chemistry",  "verdict": "CONFIRMED", "detail": "EPA + DHA: essential, structural, eicosanoid precursors", "data": {}},
                {"domain": "medicine",   "verdict": "MIXED", "detail": "VITAL/ASCEND/STRENGTH null for general CV; REDUCE-IT positive for high-risk at high dose", "data": {"REDUCE_IT_MACE_RR": 0.75}},
                {"domain": "statistics", "verdict": "CONFIRMED", "detail": "Multiple large RCTs converge on null for primary prevention; subgroups have signal", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fish oil capsules (look for IFOS or USP certification) — OR algae-based omega-3 (vegan)"],
            "tools": [],
            "steps": ["if for general health: 1 g combined EPA+DHA/day with food", "if for triglyceride lowering: 2-4 g/day (discuss with doctor)", "take with fat-containing meal for absorption", "if high-risk CV with elevated triglycerides: ask doctor about prescription icosapent ethyl (Vascepa)"],
            "time": "trial 8-12 weeks for triglyceride endpoint",
            "cost_usd_2026": "$15-40/month for quality fish oil",
            "scale": "high-triglyceride patients (under medical care), pregnant women (DHA for fetal brain), people who don't eat fatty fish. **SEE A DOCTOR** for: anticoagulant interaction (fish oil thins blood mildly), pre-surgery (stop 1 week), atrial fibrillation (some signal of increased AF risk at high dose)",
        },
        "wisdom": "Fish oil is the case study in how observational data gets overturned by RCTs. The Shepherd brings the honest 2026 view: real for triglycerides, real for specific high-risk patients, weaker than marketed for general cardiovascular health. Fatty fish on the dinner plate often makes more sense than capsules.",
        "triggers": {"keywords": ["fish oil", "omega-3", "EPA DHA", "Vascepa", "icosapent ethyl", "VITAL trial"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 5 ─ Probiotics (MIXED) ─────────────────────────────────────────
    {
        "id": "review_probiotics_strain_specific",
        "kind": "review",
        "title": "Probiotics — MIXED; CONFIRMED for antibiotic-associated diarrhea; strain-specific effects elsewhere",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Probiotic supplements (multi-strain or single-strain)",
        "grades": {
            "evidence": "B",
            "mechanism": "B",
            "quality": "C",
            "value": "$$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Probiotics are live microorganisms (Lactobacillus, Bifidobacterium, Saccharomyces, others) intended to confer health benefit when consumed. Effects are highly strain-specific — 'probiotics work for X' is not a meaningful claim because Lactobacillus rhamnosus GG, L. plantarum 299v, and L. acidophilus DDS-1 are different organisms with different effects. CONFIRMED: antibiotic-associated diarrhea prevention (Cochrane: NNT ~13). MIXED to MISMATCH: general gut health, mood, immunity claims at consumer marketing scale.",
        "category": "medicine",
        "domains": ["medicine", "biology", "nutrition"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Improves gut health", "verdict": "MIXED", "note": "Vague claim; specific strains have specific effects (e.g. C. difficile prevention with S. boulardii)"},
            {"marketing_claim": "Boosts immunity", "verdict": "MIXED", "note": "Some strains reduce respiratory infections in children/elderly; effect modest"},
            {"marketing_claim": "Prevents antibiotic diarrhea", "verdict": "CONFIRMED", "note": "Cochrane: probiotics during antibiotics reduce AAD; S. boulardii and L. rhamnosus GG strongest"},
            {"marketing_claim": "Improves mood", "verdict": "MIXED", "note": "Emerging 'psychobiotic' field; small RCTs positive for some strains; not ready for clinical recommendation"},
            {"marketing_claim": "IBS treatment", "verdict": "MIXED", "note": "Bifidobacterium infantis 35624 has best IBS data; others variable"},
            {"marketing_claim": "Replaces healthy gut bacteria after antibiotics", "verdict": "MISMATCH", "note": "Israeli study (Cell, 2018) showed probiotics may DELAY return to baseline microbiome after antibiotics"},
        ],
        "what_it_does": "Specific strains have specific effects: S. boulardii prevents AAD and C. diff recurrence. L. rhamnosus GG reduces AAD and pediatric infectious diarrhea duration. B. infantis 35624 reduces IBS symptoms. Strain + dose specificity matters more than 'probiotic'.",
        "what_it_doesnt": "Generic 'probiotic' supplements with proprietary blends often don't disclose strains. Many products show poor viability by end of shelf life. Healthy gut microbiomes don't require ongoing probiotic input.",
        "better_alternatives": "Fermented foods (yogurt with live cultures, kefir, kimchi, sauerkraut, miso) provide live cultures with food-matrix benefit. For specific medical use, ask doctor about strain-specific products (Florastor = S. boulardii; Culturelle = L. rhamnosus GG; Align = B. infantis 35624).",
        "pre_run": {
            "summary": "Specific strains for specific indications: yes. Daily 'gut health' insurance: weak. Read the strain on the label or you're buying anonymity.",
            "domain_results": [
                {"domain": "biology",    "verdict": "MIXED", "detail": "Strain-level specificity essential; species-level claims misleading", "data": {}},
                {"domain": "medicine",   "verdict": "CONFIRMED", "detail": "AAD prevention NNT ~13 with S. boulardii or L. rhamnosus GG (Cochrane)", "data": {"AAD_NNT": 13}},
                {"domain": "nutrition",  "verdict": "MIXED", "detail": "Viability degrades on shelf; live colony counts at consumption may be < label", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["specific strain-labeled probiotic matched to indication — OR fermented foods with live cultures"],
            "tools": [],
            "steps": ["DURING ANTIBIOTICS: take S. boulardii (Florastor) or L. rhamnosus GG (Culturelle) 2 hours apart from antibiotic dose", "FOR IBS: trial B. infantis 35624 (Align) 4-8 weeks", "FOR DAILY GUT: fermented food is the keeping's first recommendation; targeted probiotic if specific need", "refrigerate per label; viability matters", "AVOID in: immunocompromised (rare bacteremia risk), central lines, severe pancreatitis"],
            "time": "during antibiotic course; 4-8 week trial for IBS",
            "cost_usd_2026": "$20-50/month for branded strain-specific products",
            "scale": "specific indications. **SEE A DOCTOR** for: ongoing GI symptoms (rule out other causes), immunocompromised state, central venous catheters, recurrent C. difficile (specific treatment protocols)",
        },
        "wisdom": "The probiotic market sells 'good bacteria' the way the early-2000s sold 'antioxidants' — vaguely and well. The Shepherd brings the strain-specific reality: if the label doesn't tell you the strain at the level of letters and numbers (e.g. L. rhamnosus *GG*), you don't know what you're buying. Fermented foods are the cheaper, broader-coverage option.",
        "triggers": {"keywords": ["probiotics", "Lactobacillus", "Bifidobacterium", "Saccharomyces boulardii", "Florastor", "Align", "Culturelle"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 6 ─ Melatonin (CONFIRMED with specificity) ─────────────────────
    {
        "id": "review_melatonin_circadian",
        "kind": "review",
        "title": "Melatonin — CONFIRMED for circadian disorders (jet lag, shift work, DSPS); MIXED for general insomnia",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Melatonin 0.3–5 mg (typically taken 30–60 min before desired sleep)",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "C",
            "value": "$",
        },
        "composite_verdict": "CONFIRMED",
        "verdict": "CONFIRMED",
        "situation": "Melatonin is a pineal-gland hormone that signals 'biological night' to circadian-cycling tissues. Exogenous melatonin (0.3–5 mg, timed appropriately) effectively shifts circadian phase — CONFIRMED for jet lag, shift work disorder, delayed sleep phase syndrome (DSPS), and circadian rhythm disorders in blind people and ASD. MIXED for general primary insomnia (modest effect — sleep onset reduced ~7 min, total sleep time +8 min in meta-analyses). Quality concerns: a major study (Erland & Saxena 2017) found 71% of US melatonin products were >10% off label dose; some up to 478% higher.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "time_sequence", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Cures insomnia", "verdict": "MIXED", "note": "Modest effect on sleep onset (~7 min); not substitute for sleep hygiene or CBT-I"},
            {"marketing_claim": "Fixes jet lag", "verdict": "CONFIRMED", "note": "Cochrane: clear benefit for eastward travel ≥5 time zones"},
            {"marketing_claim": "Shift work sleep", "verdict": "CONFIRMED", "note": "Improves daytime sleep duration in night-shift workers"},
            {"marketing_claim": "Children's sleep", "verdict": "MIXED", "note": "Effective for ASD and DSPS; AAP cautions against routine use in neurotypical children"},
            {"marketing_claim": "Anti-aging / antioxidant", "verdict": "MISMATCH", "note": "In vitro antioxidant claims do not translate to clinical benefit"},
        ],
        "what_it_does": "Phase-shifts circadian rhythm. Best for: jet lag (eastward travel especially), shift work, delayed sleep phase syndrome, blind people without light cues, ASD-related sleep onset issues. Modest sleep-onset assistance for general insomnia.",
        "what_it_doesnt": "Not a sedative. Does not reliably cause sleep in everyone. Tolerance and dependence less of a concern than benzodiazepines, but rebound circadian disruption can occur with abrupt cessation. High doses (>5 mg) often counterproductive.",
        "better_alternatives": "For general insomnia: CBT-I (cognitive behavioral therapy for insomnia) is first-line and outperforms all sleep medications including melatonin. Sleep hygiene basics (consistent bedtime, dark room, no screens 1h before bed, limited caffeine after noon) are higher-leverage than any pill.",
        "pre_run": {
            "summary": "Real hormone, real mechanism, real but specific indications. Most users could benefit from a lower dose (0.3-0.5 mg) than the typical OTC 3-5 mg.",
            "domain_results": [
                {"domain": "chemistry",  "verdict": "CONFIRMED", "detail": "N-acetyl-5-methoxytryptamine; MT1 and MT2 receptor agonist", "data": {}},
                {"domain": "biology",    "verdict": "CONFIRMED", "detail": "Phase-shifts circadian clock; advance shift if taken in afternoon/evening; delay if morning", "data": {}},
                {"domain": "medicine",   "verdict": "CONFIRMED", "detail": "AASM 2018 guidelines: melatonin recommended for shift work disorder, delayed sleep phase, jet lag", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["melatonin 0.3-1 mg (lower doses often more effective) — NSF or USP-Verified preferred given supply chain quality issues"],
            "tools": [],
            "steps": ["FOR JET LAG (eastward): 0.5-3 mg at local bedtime in destination, for 3-5 days", "FOR SHIFT WORK: 1-3 mg before daytime sleep period", "FOR DSPS: 0.5 mg, 3-6 hours BEFORE current sleep onset, slowly walk bedtime earlier", "FOR GENERAL INSOMNIA: 0.3-1 mg, 30 min before desired bedtime (start low; more is not better)", "AVOID heavy meals immediately after; alcohol interferes"],
            "time": "as needed (jet lag) or short course (5-14 days)",
            "cost_usd_2026": "$5-15 per bottle (often months supply)",
            "scale": "adults with circadian disorders or short-term sleep needs. **NOT FOR**: pregnancy/breastfeeding (insufficient data), autoimmune disease (theoretical immune stimulation), seizure disorders. **SEE A DOCTOR** for: chronic insomnia (CBT-I, sleep study to rule out apnea), depression, anxiety affecting sleep, in children before regular use",
        },
        "wisdom": "Melatonin is the most underdosed effective supplement on the market — most people take 3-10× too much. The Shepherd brings the lower-dose, timed-correctly principle. The quality-control problem is real; pick USP or NSF-verified brands until that gets fixed at industry scale.",
        "triggers": {"keywords": ["melatonin", "jet lag", "shift work", "DSPS", "circadian", "sleep aid"], "axes": ["metabolism", "time_sequence"]},
    },

    # ── 7 ─ Creatine monohydrate (CONFIRMED) ───────────────────────────
    {
        "id": "review_creatine_monohydrate",
        "kind": "review",
        "title": "Creatine monohydrate — CONFIRMED for strength + power; emerging cognition data; safest sports supplement",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Creatine monohydrate (5 g/day, no loading required)",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "A",
            "value": "$",
        },
        "composite_verdict": "CONFIRMED",
        "verdict": "CONFIRMED",
        "situation": "Creatine monohydrate is the most-studied sports supplement in history with >500 RCTs. 5 g/day raises muscle phosphocreatine ~20%, providing more rapid ATP regeneration during high-intensity exercise. CONFIRMED outcomes: 5-15% improvement in strength gains, 1-3 kg additional lean mass over training period (largely water + new muscle), faster recovery between sets. Emerging cognition data: improvement on memory and executive function tasks, particularly in older adults and vegetarians (who have lower baseline creatine). Safety profile excellent over decades of study; no harm at recommended doses.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology", "exercise_science"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "claims_audit": [
            {"marketing_claim": "Increases strength + power", "verdict": "CONFIRMED", "note": "Multiple meta-analyses; effect size ~5-15% on strength endpoints"},
            {"marketing_claim": "Builds muscle", "verdict": "CONFIRMED", "note": "1-3 kg lean mass over typical training cycle"},
            {"marketing_claim": "Improves cognition", "verdict": "MIXED", "note": "Emerging evidence; effect strongest in vegetarians and elderly with lower baseline"},
            {"marketing_claim": "Damages kidneys", "verdict": "MISMATCH", "note": "Decades of safety data; no kidney harm in people without pre-existing renal disease"},
            {"marketing_claim": "Causes bloating / weight gain", "verdict": "MIXED", "note": "Initial 1-2 kg water weight is real; not bloating in clinical sense"},
            {"marketing_claim": "Loading phase necessary", "verdict": "MISMATCH", "note": "5 g/day reaches saturation in 2-4 weeks; loading shortens but isn't required"},
        ],
        "what_it_does": "Saturates muscle phosphocreatine stores. Improves work output in short-duration high-intensity exercise (sets <30 sec, sprints, heavy lifts). Modest benefits in repetitive bouts requiring rapid ATP regeneration. Emerging cognitive benefits, especially in low-baseline populations.",
        "what_it_doesnt": "Does not improve endurance sports (>2 min sustained efforts). Does not 'damage kidneys' or 'cause hair loss' — common myths refuted in literature. Does not require loading phase or cycling.",
        "better_alternatives": "Dietary creatine: red meat and fish (~1 g per 200 g serving). Vegetarians/vegans have lower baseline and may see larger effect from supplementation than omnivores.",
        "pre_run": {
            "summary": "Cleanest evidence base in supplement world. Highest benefit-per-dollar in sports nutrition.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Creatine + phosphate → phosphocreatine → rapid ATP regeneration via creatine kinase", "data": {}},
                {"domain": "exercise_science", "verdict": "CONFIRMED", "detail": "Effect on 1RM strength ~5-10%; on lean mass +1-3 kg; on sprint repeated-bout performance", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Safety in healthy populations established over 30+ years; do not use in pre-existing kidney disease without medical supervision", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["creatine monohydrate powder (Creapure or any micronized brand) — avoid 'creatine HCl', 'kre-alkalyn' — same effects, much higher price"],
            "tools": ["measuring scoop (5 g typical)"],
            "steps": ["take 5 g daily (with water, juice, or in smoothie); timing of day doesn't matter", "consistency matters; effect builds over 2-4 weeks", "loading (20 g/day for 5-7 days then 5 g maintenance) optional — speeds saturation but unnecessary", "drink adequate water (creatine osmotically pulls water into muscle)", "no cycling required — long-term continuous use safe"],
            "time": "saturation in 2-4 weeks; ongoing for sustained benefit",
            "cost_usd_2026": "$0.15-0.30 per day ($15-30 per 6 months)",
            "scale": "training individuals, vegetarians, elderly. **SEE A DOCTOR** for: known kidney disease, single kidney, on nephrotoxic drugs",
        },
        "wisdom": "Creatine is the supplement market's biggest evidence-to-marketing-mismatch in the opposite direction: cheap, well-evidenced, often dismissed as 'just for bodybuilders' when it benefits anyone training for strength/power, plus emerging cognitive benefits in older adults. The Shepherd brings this when the user asks about athletic performance or aging-related strength loss.",
        "triggers": {"keywords": ["creatine", "monohydrate", "Creapure", "muscle building", "strength training"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 8 ─ Whey protein (MIXED) ───────────────────────────────────────
    {
        "id": "review_whey_protein",
        "kind": "review",
        "title": "Whey protein — CONFIRMED for convenience and protein adequacy; MIXED for hypertrophy beyond dietary protein",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Whey protein concentrate / isolate (20-40 g per serving)",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "B",
            "value": "$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Whey protein is a high-bioavailability complete protein (~24 g protein per scoop) extracted from milk. CONFIRMED utility: meeting daily protein targets (~1.6-2.2 g/kg for resistance trainees), post-workout convenience, fast leucine absorption. MIXED claim: that whey protein per se produces hypertrophy beyond simply meeting dietary protein adequacy. Meta-analyses (Morton 2018, n=1863) show modest additive effect ~0.3 kg additional muscle mass beyond protein-adequate diet alone. The 'magic protein powder' marketing outruns the modest incremental benefit.",
        "category": "medicine",
        "domains": ["medicine", "nutrition", "chemistry", "exercise_science"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Builds muscle", "verdict": "MIXED", "note": "Helps meet protein target; modest additional effect beyond dietary protein in resistance-trained"},
            {"marketing_claim": "Aids recovery", "verdict": "CONFIRMED", "note": "Fast-absorbing protein post-workout supports muscle protein synthesis"},
            {"marketing_claim": "Weight loss", "verdict": "MIXED", "note": "High protein intake aids satiety + lean mass preservation in calorie deficit; whey specifically not magic"},
            {"marketing_claim": "Better than food", "verdict": "MISMATCH", "note": "Whole food protein (eggs, dairy, lean meat, fish) gives equivalent results with broader nutrition"},
        ],
        "what_it_does": "Convenient high-bioavailability protein delivery. Useful when whole-food protein hard to fit (post-workout, busy mornings, elderly with poor appetite). Leucine content (~2.5 g per 25 g whey) is at the threshold needed to maximally stimulate muscle protein synthesis.",
        "what_it_doesnt": "Whey is not magic; it's protein in a powder. People meeting protein targets through whole food (1.6-2.2 g/kg) see minimal additional benefit from whey. Quality varies hugely; some products have spiked amino acid profiles ('protein spiking' with cheap amino acids).",
        "better_alternatives": "Whole food protein: eggs, Greek yogurt, cottage cheese, lean meats, fish, legumes. Cheaper per gram, more nutritionally complete. Whey for convenience only.",
        "pre_run": {
            "summary": "Real but modest incremental benefit over protein-adequate diet. Convenient delivery, not magic substance.",
            "domain_results": [
                {"domain": "nutrition",        "verdict": "CONFIRMED", "detail": "Complete protein with high BCAA content; leucine triggers mTOR pathway for muscle synthesis", "data": {"leucine_g_per_scoop": 2.5}},
                {"domain": "exercise_science", "verdict": "MIXED", "detail": "Morton 2018 meta-analysis: ~0.3 kg additional muscle mass beyond protein-adequate control", "data": {"effect_size_kg": 0.3}},
                {"domain": "chemistry",        "verdict": "CONFIRMED", "detail": "Whey protein concentrate ~80% protein; isolate ~90%; hydrolysate pre-digested for faster absorption", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["whey protein concentrate (cheapest, ~80% protein) OR isolate (~90% protein, better for lactose intolerance) — Informed-Sport or NSF Certified for Sport for athletes"],
            "tools": ["shaker bottle"],
            "steps": ["20-40 g whey within 0-2 hours post-workout (timing window broader than once believed)", "OR with breakfast to hit protein target", "mix with water, milk, or in smoothies", "for general protein goals: hit 1.6 g/kg/day from whole food first, supplement only the gap"],
            "time": "ongoing as needed to meet protein target",
            "cost_usd_2026": "$25-50/lb (15-30 servings); $0.80-1.50 per serving",
            "scale": "training individuals, elderly with low appetite, anyone struggling to hit protein target via food. **SEE A DOCTOR** for: kidney disease (excess protein burden), pancreatitis history, severe dairy allergy",
        },
        "wisdom": "Whey is protein, in convenient form. The Shepherd brings this for the user who can't get adequate dietary protein — and notes that 4 eggs cost less than a scoop and bring more nutrition. The 'protein industry' fed on a kernel of truth (protein matters for muscle) and grew claims well past the data.",
        "triggers": {"keywords": ["whey protein", "protein powder", "isolate", "muscle building", "post-workout"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 9 ─ Glucosamine + chondroitin (MIXED) ──────────────────────────
    {
        "id": "review_glucosamine_chondroitin",
        "kind": "review",
        "title": "Glucosamine + chondroitin — MIXED; large RCTs largely null for OA pain; modest subgroup signal",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Glucosamine sulfate + chondroitin sulfate (1500 mg + 1200 mg daily typical)",
        "grades": {
            "evidence": "B",
            "mechanism": "C",
            "quality": "C",
            "value": "$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Glucosamine and chondroitin are precursors to glycosaminoglycans in cartilage. Theory: oral supplementation supports cartilage repair in osteoarthritis. NIH-funded GAIT trial (n=1583, NEJM 2006) showed no overall benefit vs placebo; subgroup with moderate-severe OA showed modest pain reduction with combination. Crystalline glucosamine sulfate (prescription in Europe — Rotta formulation) has stronger evidence than US OTC products. Quality varies widely; many OTC products use glucosamine hydrochloride which has different and weaker evidence base.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Rebuilds cartilage", "verdict": "MISMATCH", "note": "Imaging studies do not show consistent cartilage volume gain"},
            {"marketing_claim": "Reduces joint pain", "verdict": "MIXED", "note": "GAIT subgroup with moderate-severe OA showed modest benefit; mild cases largely null"},
            {"marketing_claim": "Slows OA progression", "verdict": "MIXED", "note": "Some imaging evidence for joint-space preservation with crystalline glucosamine sulfate (European prescription form); US OTC products less studied"},
        ],
        "what_it_does": "Modest pain reduction in moderate-severe knee osteoarthritis at adequate dose (1500 mg/day crystalline glucosamine sulfate). Possible structure-modifying effect over years.",
        "what_it_doesnt": "Does not regrow cartilage. Mild OA cases largely null in RCTs. Effect onset slow (8-16 weeks); patients often abandon before potential benefit.",
        "better_alternatives": "Weight management (every 1 lb lost ≈ 4 lb pressure off knee per step). Quadriceps strengthening (RCT-supported for knee OA). NSAID topical (diclofenac gel — guideline-recommended). Capsaicin topical (entry in apothecary).",
        "pre_run": {
            "summary": "Modest effect in moderate-severe OA at correct dose and form; cartilage-regrowth claims oversold. Reasonable trial for the right patient subgroup.",
            "domain_results": [
                {"domain": "medicine",  "verdict": "MIXED", "detail": "GAIT (NEJM 2006): overall null; moderate-severe OA subgroup showed pain reduction with combination", "data": {"n": 1583}},
                {"domain": "biology",   "verdict": "MIXED", "detail": "Glycosaminoglycan synthesis precursors; oral bioavailability and tissue penetration debated", "data": {}},
                {"domain": "chemistry", "verdict": "MIXED", "detail": "Crystalline glucosamine sulfate (Rotta formulation, EU prescription) outperforms generic OTC sulfate or HCl forms", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["glucosamine sulfate 1500 mg + chondroitin sulfate 1200 mg daily — preferably crystalline glucosamine sulfate if available"],
            "tools": [],
            "steps": ["trial 8-16 weeks before judging effect", "take with food", "if no improvement at 16 weeks: discontinue", "INTERACTIONS: glucosamine has modest effect on blood glucose (theoretical) — diabetic patients should monitor"],
            "time": "8-16 week trial; ongoing if effective",
            "cost_usd_2026": "$15-30/month for quality dose",
            "scale": "adults with moderate-severe knee OA. **SEE A DOCTOR** for: any joint pain (rule out other diagnoses), shellfish allergy (some glucosamine derived from shrimp/crab shells), anticoagulant therapy (chondroitin theoretical interaction), diabetes (glucose monitoring)",
        },
        "wisdom": "Glucosamine + chondroitin is the '70-80% of OA patients have tried it' supplement, with modest evidence and large marketing. The Shepherd brings the honest version: try it for 16 weeks if you have moderate-severe knee OA at correct dose; if no benefit, discard; do not expect cartilage to regrow. The weight loss + quadriceps strengthening combination has better evidence than the pill.",
        "triggers": {"keywords": ["glucosamine", "chondroitin", "joint supplement", "osteoarthritis", "knee pain"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 10 ─ CoQ10 (MIXED) ─────────────────────────────────────────────
    {
        "id": "review_coq10_ubiquinone",
        "kind": "review",
        "title": "CoQ10 — MIXED; CONFIRMED for heart failure (Q-SYMBIO); statin myalgia evidence mixed; anti-aging claims unsupported",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Coenzyme Q10 (ubiquinone) or ubiquinol (reduced form), 100–300 mg/day",
        "grades": {
            "evidence": "B",
            "mechanism": "A",
            "quality": "C",
            "value": "$$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Coenzyme Q10 is an electron carrier in the mitochondrial respiratory chain, essential for ATP production. Endogenously produced; levels decline with age and in some disease states. CONFIRMED: Q-SYMBIO trial (n=420, JACC 2014) showed 43% reduction in major cardiac events at 100 mg × 3 daily in chronic heart failure. MIXED: statin-induced myalgia (small trials variable; most rigorous trials null but plausible mechanism). Antioxidant / anti-aging / general wellness claims: D evidence.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Heart health", "verdict": "MIXED", "note": "Q-SYMBIO positive for heart failure specifically; not preventive cardiology for healthy adults"},
            {"marketing_claim": "Prevents statin muscle pain", "verdict": "MIXED", "note": "Mechanistically plausible (statins reduce CoQ10); most rigorous trials show no clinical benefit"},
            {"marketing_claim": "Anti-aging / energy", "verdict": "MISMATCH", "note": "Endogenous decline with age does not translate to clinical effect of supplementation in healthy adults"},
            {"marketing_claim": "Migraine prevention", "verdict": "MIXED", "note": "Modest evidence (AHS Level C recommendation)"},
        ],
        "what_it_does": "Restores CoQ10 levels in deficient states. Specific clinical benefit demonstrated in chronic heart failure (Q-SYMBIO). Mechanism strong; clinical-end-point evidence narrower than mechanism suggests.",
        "what_it_doesnt": "Does not 'boost energy' in healthy adults. Does not prevent aging. Does not reliably prevent statin myalgia in rigorous trials. Ubiquinol vs ubiquinone debate: ubiquinol may be slightly better absorbed but evidence is preliminary; price differential is large.",
        "better_alternatives": "For heart failure: prescribed therapy (ARBs, beta-blockers, SGLT2 inhibitors). For statin myalgia: switch to a different statin, reduce dose, or use ezetimibe. For migraine: magnesium, riboflavin, butterbur have more evidence.",
        "pre_run": {
            "summary": "Real mechanism (mitochondrial electron transport). Narrow clinical-evidence base; most popular uses overstate the data.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Electron carrier in mitochondrial Complex III; essential for oxidative phosphorylation", "data": {}},
                {"domain": "medicine",  "verdict": "CONFIRMED", "detail": "Q-SYMBIO: 43% reduction in MACE in chronic heart failure with 300 mg/day", "data": {"MACE_RR_reduction_pct": 43, "n": 420}},
                {"domain": "biology",   "verdict": "MIXED", "detail": "Endogenous synthesis adequate in healthy adults; supplementation benefit narrow to specific conditions", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["ubiquinone (cheaper) OR ubiquinol (more expensive, marginally better absorbed), 100-300 mg/day"],
            "tools": [],
            "steps": ["take with fatty meal — CoQ10 is fat-soluble", "if for heart failure: 100 mg × 3 daily (under medical supervision)", "if statin trial: 100 mg/day × 8 weeks before judging", "if migraine: 100-300 mg/day × 12 weeks before judging"],
            "time": "8-12 weeks for trial periods; ongoing if for heart failure",
            "cost_usd_2026": "$15-40/month for quality dose",
            "scale": "specific clinical indications. **SEE A DOCTOR** for: heart failure (real prescribed therapy is primary), statin myalgia (often dose/drug change is the answer), anticoagulant therapy (theoretical warfarin interaction)",
        },
        "wisdom": "CoQ10 is a clean mechanism with a narrow clinical-evidence base. The Shepherd brings this for heart failure (with prescribed care) and migraine prevention (modest signal); pushes back on the general-energy / anti-aging claims that dominate the marketing.",
        "triggers": {"keywords": ["CoQ10", "ubiquinone", "ubiquinol", "coenzyme Q10", "heart failure supplement", "statin myalgia"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 11 ─ Iron (CONFIRMED for deficient; HARMFUL for non-deficient) ─
    {
        "id": "review_iron_deficient_only",
        "kind": "review",
        "title": "Iron — CONFIRMED for iron-deficiency anemia; HARMFUL if supplementing without deficiency",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Iron (ferrous sulfate / gluconate / bisglycinate)",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "B",
            "value": "$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Iron supplementation is CONFIRMED for treatment of iron-deficiency anemia (low ferritin + low Hb): hemoglobin recovers, fatigue resolves, cognitive function improves. Adults need 8 mg/day (men) or 18 mg/day (premenopausal women); typical supplements provide 18-65 mg elemental iron. CONFIRMED benefit in: heavy menstrual bleeding, pregnancy, GI blood loss (after the source is investigated), restrictive diets. HARMFUL when not deficient: iron has no excretion mechanism; excess accumulates as ferritin → free iron → oxidative damage. Routine 'iron for energy' marketing to non-deficient adults is a MISMATCH and can be dangerous (hereditary hemochromatosis affects ~1 in 250 in European-ancestry populations).",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "claims_audit": [
            {"marketing_claim": "Boosts energy", "verdict": "MIXED", "note": "Yes if iron-deficient; no if not; can be harmful if not"},
            {"marketing_claim": "Better blood / hemoglobin", "verdict": "CONFIRMED", "note": "In iron-deficient individuals"},
            {"marketing_claim": "Daily supplementation for general health", "verdict": "MISMATCH", "note": "No iron excretion mechanism; excess accumulates and causes oxidative damage"},
        ],
        "what_it_does": "Treats iron-deficiency anemia. Restores hemoglobin synthesis, oxygen-carrying capacity, brain function (iron required for dopamine synthesis), immune function.",
        "what_it_doesnt": "Does not benefit non-deficient individuals. Cannot be excreted — accumulates indefinitely. Cause of iron deficiency must be investigated (especially in men, post-menopausal women, or unexpected): GI blood loss can indicate cancer.",
        "better_alternatives": "Dietary iron: red meat (heme iron, highly absorbed), legumes + vitamin C (non-heme iron, less absorbed). Avoid iron-fortified everything if not deficient.",
        "pre_run": {
            "summary": "TEST BEFORE TREATING. Iron deficiency is common and treatable; iron OVERLOAD is also common (especially hemochromatosis) and harmful. The Shepherd insists on the ferritin test.",
            "domain_results": [
                {"domain": "medicine",  "verdict": "CONFIRMED", "detail": "Iron-deficiency anemia treatment (Hb normalization in 6-8 weeks at 60-200 mg elemental Fe/day)", "data": {}},
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "No physiologic excretion of iron; uptake regulated at gut; surplus stored as ferritin → free iron → ROS damage", "data": {}},
                {"domain": "medicine",  "verdict": "MISMATCH", "detail": "Routine supplementation in non-deficient populations: 1 in 250 European-ancestry adults have HFE mutations risking iron overload", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["ferritin blood test FIRST", "if deficient: ferrous sulfate 325 mg (65 mg elemental Fe) OR ferrous bisglycinate (better tolerated) — vitamin C 100 mg co-administered to boost absorption"],
            "tools": [],
            "steps": ["TEST ferritin (and complete iron studies) BEFORE starting iron", "if ferritin <30 ng/mL: investigate cause AND treat (women: menstrual loss / pregnancy; men or postmenopausal women: ALWAYS investigate GI source)", "take on empty stomach with vitamin C for absorption; with food if GI side effects unacceptable", "expect dark/tarry stools (normal); constipation common", "retest in 8-12 weeks", "STOP and reassess if ferritin > 100 ng/mL"],
            "time": "6-12 weeks for treatment course; ongoing only as long as cause persists",
            "cost_usd_2026": "$3-15/month",
            "scale": "iron-deficient individuals ONLY. **DO NOT supplement iron without confirmed deficiency**. **SEE A DOCTOR** for: any iron deficiency (cause investigation required), any unexpected anemia, family history of hemochromatosis, signs of iron overload (joint pain + diabetes + skin bronzing)",
        },
        "wisdom": "Iron is a clean case of 'test before treating' — supplementation without confirmed deficiency is potentially harmful, not just wasteful. The Shepherd refuses to recommend iron without the ferritin number. In a healthy diet, iron deficiency in men or post-menopausal women is a clinical red flag for hidden blood loss, not a 'take supplement' problem.",
        "triggers": {"keywords": ["iron", "ferrous sulfate", "iron deficiency", "anemia", "ferritin", "hemochromatosis"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 12 ─ B12 (CONFIRMED for deficient; MISMATCH for non-deficient) ─
    {
        "id": "review_b12_cyanocobalamin",
        "kind": "review",
        "title": "Vitamin B12 — CONFIRMED for deficiency (pernicious anemia, vegan, elderly); MISMATCH for 'energy' in non-deficient",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "B12 (cyanocobalamin or methylcobalamin), 250 µg–1000 µg daily oral",
        "grades": {
            "evidence": "A",
            "mechanism": "A",
            "quality": "A",
            "value": "$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Vitamin B12 (cobalamin) is essential for DNA synthesis, neurologic function, red blood cell production. Deficiency causes megaloblastic anemia and progressive neuropathy — both reversible if caught early, irreversible if neglected. CONFIRMED treatment population: vegans (B12 is essentially absent in plant foods), elderly (atrophic gastritis → reduced intrinsic factor and absorption), pernicious anemia, post-bariatric surgery, metformin users (long-term Mg + B12 depletion), proton-pump inhibitor users. MISMATCH in non-deficient population: B12 'energy shots' and IV B12 'wellness' drips show no benefit in non-deficient adults.",
        "category": "medicine",
        "domains": ["medicine", "nutrition", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Boosts energy", "verdict": "MIXED", "note": "TRUE in deficient; FALSE in non-deficient — the famous 'B12 shot' wellness routine"},
            {"marketing_claim": "Improves cognition", "verdict": "MIXED", "note": "TRUE if deficient (deficiency causes cognitive impairment); FALSE if not"},
            {"marketing_claim": "Prevents nerve damage", "verdict": "CONFIRMED", "note": "Untreated B12 deficiency causes subacute combined degeneration (irreversible)"},
            {"marketing_claim": "Vegans need B12 supplementation", "verdict": "CONFIRMED", "note": "B12 is bacterial; plant foods do not contain meaningful B12"},
        ],
        "what_it_does": "Cofactor for methionine synthase and methylmalonyl-CoA mutase. Essential for: DNA synthesis (methyl group transfers), myelin maintenance, red blood cell maturation, dopamine/serotonin synthesis pathways.",
        "what_it_doesnt": "Does not produce energy or wellness in non-deficient adults. The 'B12 shot' / 'B12 IV drip' wellness industry sells injection theater to people whose levels are normal.",
        "better_alternatives": "Diet: meat, fish, eggs, dairy. Fortified foods (nutritional yeast, plant milks). For confirmed deficiency: oral B12 1000-2000 µg daily as effective as injection in most cases (Cochrane).",
        "pre_run": {
            "summary": "Critical for at-risk populations; useless theater for the rest. Cheap test (serum B12, methylmalonic acid) settles the question.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Cobalt-containing essential micronutrient; cofactor for two enzymes", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Deficiency causes megaloblastic anemia + neuropathy; supplementation reverses (early)", "data": {}},
                {"domain": "nutrition","verdict": "CONFIRMED", "detail": "Plant foods do not contain meaningful B12; vegans require supplementation or fortified food", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["B12 (cyanocobalamin 1000 µg sublingual or oral) — cyanocobalamin is the standard, well-absorbed, cheapest, equivalent to fancier methylcobalamin in most users"],
            "tools": [],
            "steps": ["TEST B12 level (serum B12, optional methylmalonic acid for borderline) before assuming need", "if vegan: routine 250-1000 µg/day or 2500 µg/week", "if deficient: 1000-2000 µg/day oral × 1-3 months (Cochrane: oral as effective as injection in most cases)", "if pernicious anemia / malabsorption: injection or high-dose sublingual"],
            "time": "1-3 months for repletion; ongoing in at-risk populations",
            "cost_usd_2026": "$5-15/year for routine vegan supplementation",
            "scale": "vegans, elderly, metformin/PPI users, after bariatric surgery. **SEE A DOCTOR** for: any neurologic symptoms (numbness, tingling, balance), unexplained anemia, confirmed deficiency cause investigation",
        },
        "wisdom": "B12 is essential and cheap; deficiency is serious and often missed. The Shepherd brings this with the test-first principle for symptomatic adults and routine-supplementation principle for vegans. The 'B12 wellness shot' culture is selling the wrong thing to the wrong audience.",
        "triggers": {"keywords": ["B12", "cyanocobalamin", "methylcobalamin", "vegan B12", "B12 deficiency", "energy shot"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 13 ─ Collagen peptides (MIXED) ─────────────────────────────────
    {
        "id": "review_collagen_peptides",
        "kind": "review",
        "title": "Collagen peptides — MIXED; modest skin/joint signal in trials; cheaper protein sources hit same target",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Hydrolyzed collagen peptides (10-25 g/day)",
        "grades": {
            "evidence": "B",
            "mechanism": "B",
            "quality": "B",
            "value": "$$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Hydrolyzed collagen is bovine/porcine/marine collagen enzymatically broken into small peptides. Some specific dipeptides (proline-hydroxyproline, glycine-proline) appear in blood after oral collagen, suggesting incomplete digestion. Multiple small RCTs show modest improvements in: skin elasticity / hydration (~5-15% improvement metrics), joint pain (especially exercise-related), nail strength. Effect sizes modest; control comparisons sometimes generic protein (whey) which has shown similar effects in some trials — suggesting amino acid supply may be the active mechanism rather than collagen-specific.",
        "category": "medicine",
        "domains": ["medicine", "biology", "nutrition", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Improves skin", "verdict": "MIXED", "note": "Multiple RCTs show modest elasticity/hydration improvements; mechanism may be amino acid supply"},
            {"marketing_claim": "Reduces joint pain", "verdict": "MIXED", "note": "Modest effect on exercise-related knee pain; not specific to collagen"},
            {"marketing_claim": "Stronger nails / hair", "verdict": "MIXED", "note": "Small RCTs suggest nail growth/strength improvement; hair evidence weaker"},
            {"marketing_claim": "Builds bone density", "verdict": "MIXED", "note": "One RCT positive; not yet replicated at scale"},
            {"marketing_claim": "Reverses aging", "verdict": "MISMATCH", "note": "Marketing language; not what trials measure"},
        ],
        "what_it_does": "Provides high glycine + proline + hydroxyproline content. Some specific collagen-derived peptides reach systemic circulation. Modest effects on skin and joint endpoints in trials.",
        "what_it_doesnt": "Does not 'go to your skin' as collagen — proteins are digested to amino acids and small peptides. Effect is modest and may not be collagen-specific (whey shows similar in some trials).",
        "better_alternatives": "Bone broth (cheaper, with same amino acids + whole-food nutrition). Adequate dietary protein (1.0-1.6 g/kg/day). Vitamin C cofactor for endogenous collagen synthesis matters at least as much.",
        "pre_run": {
            "summary": "Real but modest; possibly not collagen-specific. The Shepherd brings this as 'mostly amino-acid protein in expensive form'.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Hydrolyzed collagen yields specific dipeptides detectable in blood post-ingestion", "data": {}},
                {"domain": "medicine",  "verdict": "MIXED", "detail": "Multiple small RCTs show modest skin and joint improvements; effect sizes small to moderate", "data": {}},
                {"domain": "biology",   "verdict": "MIXED", "detail": "Mechanism likely amino acid supply + small peptide signaling; not direct collagen integration", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["hydrolyzed collagen peptides (Vital Proteins, Great Lakes, generic) - look for 'hydrolyzed' or 'peptides' for solubility"],
            "tools": ["scoop or scale"],
            "steps": ["10-20 g daily in coffee, smoothie, or water (dissolves cold or hot)", "with vitamin C-rich food (100 mg) for cofactor", "trial 8-12 weeks for skin/joint endpoints", "for budget: bone broth provides similar amino acid profile at lower cost"],
            "time": "8-12 week trial for skin/joint endpoints",
            "cost_usd_2026": "$25-50/month for quality powder",
            "scale": "general adults willing to pay premium for modest effects. **SEE A DOCTOR** for: serious skin/joint concerns (rule out causes; collagen is supportive, not curative)",
        },
        "wisdom": "Collagen is real protein with real but modest effects, sold at a premium that may not be justified vs whey or bone broth. The Shepherd brings this for the user willing to spend on a modest cosmetic/joint benefit — and notes that the same amino acids in bone broth cost a quarter as much.",
        "triggers": {"keywords": ["collagen peptides", "hydrolyzed collagen", "Vital Proteins", "skin supplement", "joint pain"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 14 ─ Ashwagandha (MIXED) ───────────────────────────────────────
    {
        "id": "review_ashwagandha_stress",
        "kind": "review",
        "title": "Ashwagandha — MIXED; modest stress/anxiety reduction in RCTs; testosterone/muscle claims oversold",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Withania somnifera extract (KSM-66 or Sensoril, 300-600 mg/day)",
        "grades": {
            "evidence": "B",
            "mechanism": "B",
            "quality": "B",
            "value": "$$",
        },
        "composite_verdict": "MIXED",
        "verdict": "MIXED",
        "situation": "Ashwagandha (Withania somnifera) is an Ayurvedic adaptogen containing withanolides. Multiple small RCTs (KSM-66 extract typically) show modest reductions in perceived stress, cortisol (~15-30%), and anxiety scores over 8-12 weeks. Sleep improvements also reported. Testosterone (~15-20% increase) and muscle strength effects in resistance-trained men found in small trials, but effect sizes inconsistent and replication mixed. Generally well-tolerated; rare liver injury cases reported (especially with high doses or proprietary blends).",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "claims_audit": [
            {"marketing_claim": "Reduces stress / cortisol", "verdict": "MIXED", "note": "Real effect on perceived stress and cortisol in trials; modest effect size"},
            {"marketing_claim": "Improves sleep", "verdict": "MIXED", "note": "Multiple small RCTs positive; not as strong as melatonin for specific circadian indications"},
            {"marketing_claim": "Boosts testosterone", "verdict": "MIXED", "note": "Small studies positive; not consistent across replications; effect size modest"},
            {"marketing_claim": "Builds muscle / strength", "verdict": "MIXED", "note": "Small RCT signals; not robust"},
            {"marketing_claim": "Anti-anxiety", "verdict": "MIXED", "note": "Modest effect, not substitute for evidence-based anxiety treatment"},
        ],
        "what_it_does": "Modest reductions in perceived stress, cortisol, and anxiety scores in 8-12 week trials. Withanolides interact with GABA-A and serotonergic systems. Standardized extracts (KSM-66, Sensoril) have most consistent trial data.",
        "what_it_doesnt": "Does not 'rebalance hormones' as marketed. Testosterone/muscle benefits modest and inconsistent. Not a replacement for stress management, sleep hygiene, exercise, or evidence-based mental health care.",
        "better_alternatives": "Exercise (most evidence-based stress reduction). Sleep adequacy. Meditation / mindfulness (CONFIRMED for anxiety, depression). For clinical anxiety: CBT, SSRI/SNRI if appropriate.",
        "pre_run": {
            "summary": "Modest real effect on stress/anxiety; testosterone and muscle marketing claims outrun the data. Watch for liver-injury rare-but-real signal.",
            "domain_results": [
                {"domain": "medicine",  "verdict": "MIXED", "detail": "Stress and anxiety reduction in multiple small RCTs; effect modest, replication variable", "data": {"cortisol_reduction_pct": 20}},
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Withanolides; bioactive compounds with GABAergic and serotonergic activity", "data": {}},
                {"domain": "biology",   "verdict": "MIXED", "detail": "Adaptogen activity (HPA-axis modulation) in animal models; clinical translation modest", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["KSM-66 or Sensoril standardized extract, 300-600 mg/day"],
            "tools": [],
            "steps": ["take with food, divided dose AM and evening", "trial 8-12 weeks for stress/anxiety endpoints", "AVOID in: pregnancy (uterine stimulant in animal data), thyroid disease (may increase thyroid hormone), autoimmune disease (immunostimulant), upcoming surgery (anesthesia interactions), liver disease"],
            "time": "8-12 week trial",
            "cost_usd_2026": "$20-40/month for standardized extract",
            "scale": "adults with mild-moderate stress / anxiety. **SEE A DOCTOR** for: clinical anxiety or depression, before/during pregnancy, on hormonal therapy, with liver disease history",
        },
        "wisdom": "Ashwagandha is the current 'every podcaster's favorite' supplement and the trials do show modest effects. The Shepherd brings this with realistic expectations and clear safety caveats — it is a mild adaptogenic herb with measurable effects on stress, not a hormonal enhancer despite marketing.",
        "triggers": {"keywords": ["ashwagandha", "Withania somnifera", "adaptogen", "KSM-66", "stress supplement", "cortisol"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 15 ─ Saw palmetto (MISMATCH) ───────────────────────────────────
    {
        "id": "review_saw_palmetto_mismatch",
        "kind": "review",
        "title": "Saw palmetto for BPH — MISMATCH; large rigorous RCTs (STEP, CAMUS) show no clinical effect",
        "vertical": "medicine",
        "product_category": "supplement",
        "product_or_class": "Saw palmetto (Serenoa repens) extract, 320 mg/day",
        "grades": {
            "evidence": "F",
            "mechanism": "B",
            "quality": "B",
            "value": "$$$$",
        },
        "composite_verdict": "MISMATCH",
        "verdict": "MISMATCH",
        "situation": "Saw palmetto (Serenoa repens) extract was traditionally and is currently marketed for benign prostatic hyperplasia (BPH) symptoms in men. The hypothesis: phytosterols inhibit 5α-reductase, similar to finasteride. Two large rigorous NIH-funded trials definitively answered the question: STEP trial (Bent et al. NEJM 2006, n=225) showed no benefit over placebo on AUASI symptom score or urinary flow. CAMUS trial (Barry et al. JAMA 2011, n=369) confirmed null at doses up to 3× standard. The keeping records: standard-dose saw palmetto does not work for BPH.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry", "statistics"],
        "axes": ["metabolism", "authority_trust"],
        "claims_audit": [
            {"marketing_claim": "Reduces BPH symptoms", "verdict": "MISMATCH", "note": "Two large NIH-funded RCTs (STEP, CAMUS) showed no benefit at standard or 3× standard dose"},
            {"marketing_claim": "Improves urinary flow", "verdict": "MISMATCH", "note": "Null in objective uroflowmetry measurements"},
            {"marketing_claim": "Natural prostate support", "verdict": "MISMATCH", "note": "Vague claim; specific outcomes that have been tested are null"},
        ],
        "what_it_does": "Phytosterols + fatty acids; minimal 5α-reductase inhibition at oral doses; no clinically meaningful effect on BPH symptoms or urinary flow demonstrated in rigorous trials.",
        "what_it_doesnt": "Does not reduce BPH symptoms in well-powered trials. Older positive trials had methodological problems (placebo run-in, inadequate masking, lower-quality extracts) that the NIH trials specifically addressed.",
        "better_alternatives": "For BPH: lifestyle (limit fluid before bed, avoid caffeine/alcohol). Prescribed therapy: α-blockers (tamsulosin, alfuzosin — symptom relief), 5α-reductase inhibitors (finasteride, dutasteride — actual prostate volume reduction over 6-12 months), combination if severe.",
        "pre_run": {
            "summary": "Classic case of supplement marketing surviving definitive negative RCTs. The Shepherd records the MISMATCH explicitly so users stop paying for it.",
            "domain_results": [
                {"domain": "medicine",  "verdict": "MISMATCH", "detail": "STEP (NEJM 2006) and CAMUS (JAMA 2011): null for BPH symptoms and uroflowmetry", "data": {"STEP_AUASI_difference": 0.04, "CAMUS_AUASI_difference": 0.79}},
                {"domain": "statistics","verdict": "CONFIRMED", "detail": "n=594 total across two NIH-funded high-quality trials; adequately powered to detect modest effects", "data": {"combined_n": 594}},
                {"domain": "chemistry", "verdict": "MIXED", "detail": "Phytosterol content real; oral bioavailability + tissue penetration insufficient at standard doses", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": [],
            "tools": [],
            "steps": ["**The Shepherd does not recommend saw palmetto for BPH symptoms.** The evidence-based answer is to discuss prescription options with a urologist if symptoms warrant.", "FOR ACTUAL BPH: AUA + EAU guidelines recommend α-blockers and/or 5α-reductase inhibitors; both are well-evidenced and inexpensive generic medications"],
            "time": "n/a",
            "cost_usd_2026": "if avoiding ineffective supplement: $200-500/year saved",
            "scale": "if you have BPH symptoms, see a urologist; if you don't, you don't need the supplement",
        },
        "wisdom": "Saw palmetto is a supplement-market test case: definitive negative trials have not removed the product from shelves or affected consumer demand. The Shepherd records the MISMATCH explicitly, refuses to launder folk-medicine momentum after the data has come in, and points users to prescribed therapy that actually works.",
        "triggers": {"keywords": ["saw palmetto", "Serenoa repens", "BPH supplement", "prostate supplement", "STEP trial"], "axes": ["metabolism", "authority_trust"]},
    },
]


def main() -> int:
    if not ALMANAC.exists():
        print(f"ERROR: almanac file not found at {ALMANAC}")
        return 1

    existing: set[str] = set()
    with ALMANAC.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass

    to_write = [e for e in ENTRIES if e["id"] not in existing]
    skipped = [e["id"] for e in ENTRIES if e["id"] in existing]
    if skipped:
        print(f"skipping (already present): {len(skipped)}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            g = e["grades"]
            grade_summary = f"E:{g['evidence']} M:{g['mechanism']} Q:{g['quality']} V:{g['value']}"
            print(f"  + {e['id']:40s}  {e['verdict']:10s} | {grade_summary}")

    from collections import Counter
    c = Counter(e["verdict"] for e in to_write)
    print(f"\n-- appended {len(to_write)} reviews")
    print(f"   verdict mix: {dict(c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
