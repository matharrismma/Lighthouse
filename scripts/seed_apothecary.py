#!/usr/bin/env python
"""Seed 15 apothecary-substrate entries — natural remedies and herbal
preparations, with verdicts honest about evidence quality.

This batch feeds the existing /apothecary.html lens, which compounds
across Scripture + protocol + mind + parable + body + philosopher + father
+ almanac for a stated condition. More substrate = better compounds.

Verdict mix (chosen intentionally):
  - 8 CONFIRMED (real, well-evidenced — strong RCT or meta-analytic support)
  - 5 MIXED (works in part, overstated in part — the keeping is honest
            about where the rubber meets the road)
  - 2 MISMATCH (popularly believed but evidence shows otherwise — the
              engine refuses to launder folk medicine that has been tested
              and found wanting)

Each entry carries the same medical caveat: the Shepherd is not a doctor.
Drug interactions are flagged. Threshold for professional consultation is
explicit in `make_it.scale`.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── 1 ─ Aloe vera for minor burns ─────────────────────────────────
    {
        "id": "practical_aloe_vera_burns",
        "kind": "practical",
        "title": "Aloe vera gel — cooling + mild anti-inflammatory for minor burns and sunburn",
        "vertical": "medicine",
        "source": {"publication": "Cochrane Burns Review + dermatology RCT literature", "year": 2020},
        "situation": "Aloe vera gel (from Aloe barbadensis leaves) applied to minor first-degree and small second-degree burns reduces pain and accelerates re-epithelialization. Active components: acemannan (polysaccharide, anti-inflammatory), glucomannan (mucilage, cooling/occlusive), low concentrations of salicylates. Mechanism: surface cooling + anti-inflammatory cytokine modulation + occlusive barrier that retains moisture during healing.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Multiple small RCTs show 1–2 days faster healing time for minor burns vs petroleum-jelly control. Effect size modest but consistent.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Acemannan + glucomannan polysaccharides with documented anti-inflammatory cell-culture effects", "data": {}},
                {"domain": "medicine",  "verdict": "CONFIRMED", "detail": "Cochrane meta-analyses + clinical practice guidelines recognize aloe for minor (1st-degree, small 2nd-degree) burns", "data": {"effect_size": "modest but consistent"}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fresh aloe leaf (gel scraped out) OR commercial 99%+ pure aloe gel (no added fragrance/alcohol)", "clean cloth for application"],
            "tools": ["knife (to harvest leaf gel)"],
            "steps": ["COOL THE BURN FIRST: 10–20 min cool (not ice) water — this matters more than any topical", "harvest aloe: cut a thick leaf, slit lengthwise, scrape clear gel with a spoon", "apply thin layer to clean dry burn 3–4 times daily", "cover loosely with non-stick gauze if abrasion-prone", "discard unused gel after 1 week (refrigerated); fresh always better"],
            "time": "minor burn: 3–7 days healing",
            "cost_usd_2026": "$0 if you grow aloe; $5–10 for commercial gel",
            "scale": "first-degree and small (<3 cm) second-degree burns. **SEE A DOCTOR** for: any burn larger than user's palm, any deep/full-thickness burn (white/leathery), burns on face/hands/genitals/joints, electrical or chemical burns, infection signs (red streaking, fever, increasing pain after day 2)",
        },
        "wisdom": "Aloe is one of the cleanest folk remedies: a real plant, a real mechanism, modest but consistent effect. The Shepherd brings this for minor sun, kitchen, and friction burns — and notes that COOLING THE BURN with water for 20 minutes does more than any topical that comes later. The plant is the dressing, not the cure.",
        "triggers": {"keywords": ["aloe vera", "minor burns", "sunburn treatment", "first aid burns"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 2 ─ Honey for wound dressing ──────────────────────────────────
    {
        "id": "practical_medical_honey_wound",
        "kind": "practical",
        "title": "Honey wound dressing — osmotic + glucose-oxidase H₂O₂ + (Manuka) methylglyoxal",
        "vertical": "medicine",
        "source": {"publication": "Cochrane Wounds Group + WHO essential medicines (medical-grade honey)", "year": 2020},
        "situation": "Honey applied to wounds (minor burns, chronic ulcers, infected surgical wounds) acts as an antibacterial dressing via three mechanisms: (1) high osmotic pressure dehydrates bacteria; (2) glucose oxidase enzyme in honey produces low-level hydrogen peroxide on dilution with wound exudate; (3) Manuka honey specifically contains methylglyoxal (MGO) at antibacterial concentrations. Medical-grade (gamma-irradiated) honey is the form used in hospital wound care; raw honey carries Clostridium botulinum spore risk and should NOT be used in infants <12 months or in deep penetrating wounds.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "authority_trust"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Triple-mechanism antibacterial. Hospital wound-care products (Medihoney, others) are gamma-sterilized Manuka honey + supporting dressing. Effective against MRSA in vitro and many chronic wounds in vivo.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Glucose oxidase: glucose + O₂ + H₂O → gluconic acid + H₂O₂; the H₂O₂ is the antibacterial. Manuka MGO from precursor dihydroxyacetone in nectar.", "data": {"mechanism": "osmotic + H2O2 + MGO"}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "Antibacterial activity demonstrated against S. aureus including MRSA, P. aeruginosa, others", "data": {}},
                {"domain": "medicine","verdict": "CONFIRMED", "detail": "Medical-grade honey on chronic wounds: similar or better healing rates vs conventional dressings (Cochrane 2015)", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["medical-grade honey (Medihoney or equivalent) for hospital-quality care — OR raw monofloral honey (Manuka UMF 10+ preferred) for general home first-aid on shallow wounds", "non-adherent dressing (Telfa pad)", "tape or bandage", "saline for cleaning"],
            "tools": ["clean (preferably sterile) scissors + tweezers"],
            "steps": ["clean wound with saline or potable water + mild soap; pat dry", "apply 1–3 mm layer of honey directly on wound (or saturate gauze with honey, place gauze-side down)", "cover with non-adherent dressing + secondary dressing", "change daily initially; less frequently as wound improves", "discard if wound smells foul or develops cellulitis"],
            "time": "daily dressing changes; healing days to weeks depending on wound",
            "cost_usd_2026": "$15–30 small jar Manuka; $30–60 medical-grade",
            "scale": "minor wounds, ulcers (with primary care follow-up), pressure injuries. **DO NOT USE in: infants <12 months (botulism risk), deep penetrating wounds, diabetic foot ulcers without medical supervision, animal bites.** **SEE A DOCTOR** for: any wound deeper than skin, any wound with red streaking, fever, foul drainage, diabetic patient, on the face",
        },
        "wisdom": "Honey on wounds is one of the oldest medical practices we have evidence for — Egyptian papyri document it, modern hospitals use it. The Shepherd brings this for minor burns, scrapes, and clean superficial wounds; the formal medical-grade product matters for chronic wounds and hospital settings. **Never** in infants under 12 months — the spores survive in honey and can colonize the immature infant gut.",
        "triggers": {"keywords": ["honey wound", "Manuka", "Medihoney", "wound dressing", "diabetic ulcer"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 3 ─ Saline nasal irrigation ───────────────────────────────────
    {
        "id": "practical_saline_nasal_irrigation",
        "kind": "practical",
        "title": "Saline nasal irrigation — neti pot or squeeze bottle, evidence-based for rhinosinusitis",
        "vertical": "medicine",
        "source": {"publication": "Cochrane reviews on chronic rhinosinusitis + allergic rhinitis", "year": 2018},
        "situation": "Isotonic (0.9%) or hypertonic (2–3%) saline solution flushed through the nasal cavity using a neti pot or squeeze bottle physically removes mucus, allergens, and inflammatory mediators. Cochrane meta-analyses show meaningful symptom improvement in chronic rhinosinusitis and allergic rhinitis. Hypertonic provides slightly stronger anti-edema effect but more burning. Critical safety: water MUST be distilled, previously boiled, or specifically filtered (≤1 micron) — untreated tap water has caused fatal Naegleria fowleri amoebic infections.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Mechanical clearance + mucosal hydration + dilution of inflammatory mediators. Effect size moderate; benefit/cost ratio one of the highest in respiratory medicine.",
            "domain_results": [
                {"domain": "medicine","verdict": "CONFIRMED", "detail": "Cochrane: saline irrigation reduces symptoms and antibiotic use in chronic rhinosinusitis", "data": {}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "**WARNING**: Naegleria fowleri brain-eating amoeba can be in tap water; uses untreated tap water = serious risk", "data": {"safe_water": ["distilled", "boiled+cooled", "≤1µm filtered"]}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["neti pot OR squeeze bottle (NeilMed Sinus Rinse, similar)", "non-iodized salt", "baking soda (optional, buffers)", "**SAFE WATER**: distilled / previously boiled and cooled / ≤1 micron filtered — NEVER raw tap water"],
            "tools": ["mixing cup, measuring spoon"],
            "steps": ["mix isotonic solution: 1 tsp (5g) salt + ½ tsp (2.5g) baking soda in 1 cup (240 mL) safe water; or use pre-packaged saline sachets", "warm to body temperature (cold water hurts)", "tilt head sideways over sink, pour or squeeze through upper nostril; water flows out the lower nostril", "repeat other side", "blow nose gently after; do not pinch one nostril and blow forcefully (drives water into ears)", "rinse and air-dry device between uses; replace every 3 months"],
            "time": "1–2 minutes per session, 1–2 times daily for chronic symptoms",
            "cost_usd_2026": "$10–25 device + $5 saline supplies for months",
            "scale": "all ages above ~5 years (with adult help in children). **SEE A DOCTOR** for: persistent symptoms >12 weeks (chronic rhinosinusitis evaluation), unilateral nasal obstruction (rule out polyp/tumor), fever + facial pain (bacterial sinusitis vs viral), severe headache or neurologic symptoms",
        },
        "wisdom": "Nasal irrigation is one of the most underused effective remedies in modern medicine — the evidence is strong, the cost is nearly zero, the side effects are minimal. The Shepherd brings this for allergic rhinitis, post-nasal drip, chronic sinusitis, and the cold-stage where everything is congested. **Water safety is non-negotiable**: use only safe water sources.",
        "triggers": {"keywords": ["neti pot", "nasal rinse", "saline irrigation", "sinus rinse", "rhinosinusitis"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 4 ─ Peppermint oil for IBS ────────────────────────────────────
    {
        "id": "practical_peppermint_oil_ibs",
        "kind": "practical",
        "title": "Peppermint oil (enteric-coated) — menthol smooth-muscle relaxant for IBS",
        "vertical": "medicine",
        "source": {"publication": "Cochrane IBS review + American College of Gastroenterology guidelines", "year": 2021},
        "situation": "Enteric-coated peppermint oil capsules (180–225 mg) taken 3× daily reduce overall IBS symptoms in 60–70% of patients vs ~40% placebo. Active compound is menthol, which blocks L-type calcium channels in intestinal smooth muscle and provides direct relaxation. Enteric coating is essential — uncoated peppermint oil releases in the stomach (heartburn) instead of the small intestine. ACG guidelines include peppermint oil as a recommended treatment for IBS.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "L-type calcium channel block in intestinal smooth muscle → reduced spasm and pain. Mechanism shared with prescription antispasmodics (hyoscyamine, dicyclomine).",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Menthol acts at L-type Ca channels and on TRPM8 receptors; smooth-muscle relaxation predominates clinically", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Meta-analyses + ACG 2021 guidelines: peppermint oil recommended for IBS pain and global symptoms", "data": {"NNT": 3}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["enteric-coated peppermint oil capsules (IBgard, IBSure, generic brands available)"],
            "tools": [],
            "steps": ["take 180–225 mg enteric-coated capsule 30 min before each meal (3× daily)", "trial period: 4 weeks", "if heartburn occurs: confirm enteric coating intact; if persisting, peppermint may not be right", "common interactions: cyclosporine (peppermint slightly raises levels); proton pump inhibitors (omeprazole etc. may dissolve enteric coating prematurely — take 2h apart)"],
            "time": "trial: 4 weeks. Ongoing if effective.",
            "cost_usd_2026": "$15–30 per month",
            "scale": "adults with IBS diagnosis. **SEE A DOCTOR FIRST** for: any new GI symptoms before assuming IBS; red flags (bleeding, weight loss, age >50 with new symptoms, family history of colon cancer) need colonoscopy not peppermint",
        },
        "wisdom": "One of the cleanest plant medicines: a specific compound (menthol) hitting a specific target (intestinal smooth-muscle Ca channels) with measurable benefit. The Shepherd brings this when the user has IBS diagnosis and is looking for non-pharmaceutical first-line. Note: 'IBS' is a diagnosis of exclusion — don't self-treat undiagnosed abdominal symptoms.",
        "triggers": {"keywords": ["peppermint oil", "IBS", "irritable bowel", "menthol", "enteric coated"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 5 ─ Ginger for nausea ─────────────────────────────────────────
    {
        "id": "practical_ginger_nausea",
        "kind": "practical",
        "title": "Ginger — 1g/day for nausea (pregnancy, chemo, motion, post-op)",
        "vertical": "medicine",
        "source": {"publication": "Cochrane Pregnancy Group + ACOG + multiple oncology guidelines", "year": 2020},
        "situation": "Ginger (Zingiber officinale) root, taken at 1–1.5 grams per day in divided doses, reduces nausea and vomiting in pregnancy (NVP), chemotherapy-induced nausea, motion sickness, and post-operative nausea. Multiple RCTs and meta-analyses converge on efficacy. Active compounds: gingerols (fresh) and shogaols (dried) act on 5-HT3 serotonin receptors (the same target as ondansetron) and on gastric motility. Bioavailable from capsule, tea, candied ginger, or fresh ginger eaten directly.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology", "nutrition"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "5-HT3 antagonism + prokinetic effect on stomach + central anti-nausea. ACOG endorses for first-line NVP treatment.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Gingerols and shogaols antagonize 5-HT3 receptors (same target as ondansetron); also inhibit prostaglandin synthesis", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "ACOG: ginger first-line for NVP. Cochrane: effective for nausea in pregnancy, chemo, motion sickness, post-op", "data": {"effective_dose_g_per_day": 1.0}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fresh ginger root (most cost-effective) OR ginger capsules (250 mg, take 4 daily) OR ginger tea OR crystallized ginger"],
            "tools": ["grater or knife (fresh)"],
            "steps": ["FRESH: peel and grate 1 tsp (~3-5g, of which ~1g is active ginger compounds); steep in hot water 5–10 min, sip", "CAPSULES: 250 mg × 4 daily (1 g total)", "PREGNANCY: split into smaller more frequent doses; with food", "DRUG INTERACTIONS: ginger at high doses (>3 g) modestly increases anticoagulant effect of warfarin; standard doses unlikely to be clinically significant"],
            "time": "onset 30–60 min; effect 4–6 hours per dose",
            "cost_usd_2026": "$2–4 fresh ginger root; $8–15 ginger capsules",
            "scale": "general adult use. **CAUTION**: ginger >1g/day in pregnancy was historically debated; current ACOG / SOGC view: 1 g/day safe and effective. **SEE A DOCTOR** for: severe vomiting unable to keep fluids down (hyperemesis), chemo-induced nausea not responding to ginger + prescribed antiemetics, any new persistent nausea (rule out other causes)",
        },
        "wisdom": "Ginger is among the best-evidenced plant medicines — multiple RCTs, multiple meta-analyses, multiple guideline endorsements. The Shepherd brings this for nausea across most causes (pregnancy, motion, post-op, chemo). Tea is the cheapest form; capsules are the most consistent dose; fresh root works fine if chewed for the small amount needed.",
        "triggers": {"keywords": ["ginger", "nausea", "morning sickness", "motion sickness", "anti-nausea"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 6 ─ Capsaicin topical for neuropathic pain ────────────────────
    {
        "id": "practical_capsaicin_topical_pain",
        "kind": "practical",
        "title": "Capsaicin topical 0.025–0.075% — TRPV1 desensitization for neuropathic pain",
        "vertical": "medicine",
        "source": {"publication": "Cochrane chronic pain reviews; capsaicin patch (Qutenza 8%) Rx", "year": 2020},
        "situation": "Capsaicin (8-methyl-N-vanillyl-6-nonenamide, the active in chili peppers) applied topically 4× daily for 4+ weeks reduces pain from post-herpetic neuralgia, diabetic neuropathy, and localized musculoskeletal pain. Mechanism: capsaicin binds TRPV1 receptors on small C-fiber nociceptors; initial activation (burning sensation) is followed by desensitization and ultimately reversible nerve-fiber retraction. OTC creams (0.025% Zostrix, 0.075% Capzasin-P) require weeks of consistent use; prescription 8% patch (Qutenza) is single-application, much stronger effect.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Repeated TRPV1 activation → receptor desensitization + Substance P depletion → reduced pain signaling. Initial burning sensation is part of the mechanism, not a side effect.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Capsaicin: vanilloid receptor agonist; selective TRPV1 binding", "data": {}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "Repeated application depletes Substance P and desensitizes nociceptors; reversible defunctionalization", "data": {}},
                {"domain": "medicine","verdict": "CONFIRMED", "detail": "NICE + Cochrane: topical capsaicin recommended for post-herpetic neuralgia and diabetic neuropathy", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["capsaicin cream 0.025% (Zostrix) or 0.075% (Capzasin-P) — OTC", "disposable gloves OR thorough handwashing"],
            "tools": [],
            "steps": ["apply pea-sized amount to painful area 4× daily", "MUST be consistent — the desensitization develops over 1–4 weeks", "WEAR GLOVES or wash hands immediately and thoroughly after application — capsaicin in eyes, nose, or genitals burns intensely", "do NOT apply to broken skin or open wounds", "expect burning for first 1–2 weeks; this is the mechanism, not a side effect", "if burning intolerable, try 0.025% before 0.075%"],
            "time": "trial: 4 weeks minimum. Ongoing as needed.",
            "cost_usd_2026": "$10–25 per tube",
            "scale": "adults with localized chronic pain. **SEE A DOCTOR** for: any new pain (diagnosis first), pain with neurologic symptoms (weakness, numbness with no clear cause), no improvement after 6 weeks of consistent use, severe widespread pain (suggests systemic process)",
        },
        "wisdom": "Capsaicin uses pain to defeat pain — the desensitization is the point. The Shepherd brings this for post-herpetic neuralgia, diabetic neuropathy, localized osteoarthritis pain. The burning is uncomfortable; many users quit before the mechanism kicks in at week 2–3.",
        "triggers": {"keywords": ["capsaicin", "chili topical", "neuropathic pain", "TRPV1", "shingles pain"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 7 ─ Willow bark / salicin ─────────────────────────────────────
    {
        "id": "practical_willow_bark_salicin",
        "kind": "practical",
        "title": "Willow bark — salicin → salicylic acid; the original aspirin, same effects + risks",
        "vertical": "medicine",
        "source": {"publication": "Pharmacognosy texts; modern reviews of Salix alba", "year": 2015},
        "situation": "Willow bark (Salix alba and related species) contains salicin, a glycoside that is metabolized in the body to salicylic acid — the active metabolite that aspirin (acetylsalicylic acid) is acetylated for. 240 mg salicin (~120–240 mg salicylic acid in vivo) provides analgesic and anti-inflammatory effect comparable to ~50–100 mg aspirin. Same mechanism (COX-1 + COX-2 inhibition), same gastric irritation risk, same Reye's syndrome risk in children with viral illness — willow bark is NOT a 'safer aspirin', it IS pre-aspirin with the same warnings.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Plant prodrug → identical active metabolite as the pharmaceutical version. Hippocrates used willow bark; Hoffmann (Bayer 1897) acetylated the active to reduce gastric irritation and was awarded the aspirin patent.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Salicin → saligenin → salicylic acid (hepatic). Acetylsalicylic acid (aspirin) is acetylated SA with shorter onset, less GI irritation", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Willow bark 240 mg salicin daily ≈ low-dose aspirin for back pain (Schmid 2001 RCT)", "data": {"effective_salicin_mg_daily": 240}},
            ],
            "axis_overlaps": [{"axis": "physical_substance", "with": ["medicine"], "note": "Direct lineage to the aspirin gem in the kingdom-gems / pipeline candidates batch"}],
        },
        "make_it": {
            "materials": ["willow bark capsules or tincture (standardized to 15% salicin for predictable dose) — OR bark of white willow (Salix alba) for tea (less precise dose)"],
            "tools": [],
            "steps": ["CAPSULE: 240 mg salicin per day (often 120 mg × 2)", "TEA: 1 tsp dried bark in hot water, steep 10 min, 2–3 cups daily", "WITH FOOD to reduce gastric irritation", "STOP if: stomach pain, dark/tarry stools, ringing in ears (salicylate toxicity sign)", "NEVER give to children <16 with viral illness (Reye's syndrome risk — same as aspirin)", "AVOID with: bleeding disorders, anticoagulant therapy, NSAIDs, pregnancy (especially third trimester)"],
            "time": "onset 30–90 min; longer than aspirin",
            "cost_usd_2026": "$10–20 per month",
            "scale": "adults with mild-to-moderate pain (headache, back pain, osteoarthritis). **DOSE NOT TO EXCEED label** to avoid salicylate toxicity. **SEE A DOCTOR** for: any chronic pain (diagnosis first), GI bleeding signs, kidney disease, before any surgery (stop 1 week prior), pregnancy, breastfeeding",
        },
        "wisdom": "Willow bark is aspirin's grandfather, and the warning is the same — the active metabolite is identical to what aspirin becomes in the body. The Shepherd carries this with explicit non-romanticization: a plant medicine that works is a real medicine with real warnings. The aspirin gem and this willow gem are different doors into the same house.",
        "triggers": {"keywords": ["willow bark", "salicin", "natural aspirin", "Salix alba", "herbal pain"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 8 ─ Witch hazel astringent ────────────────────────────────────
    {
        "id": "practical_witch_hazel_astringent",
        "kind": "practical",
        "title": "Witch hazel — tannins astringent for minor skin, hemorrhoids, insect bites",
        "vertical": "medicine",
        "source": {"publication": "USP monograph + AAD external skincare guidance", "year": 2015},
        "situation": "Witch hazel extract (Hamamelis virginiana) contains 4–10% tannins (gallic acid derivatives) that precipitate skin proteins, causing tissue tightening and reducing minor inflammation, oozing, and itching. Topical application is well-tolerated and broadly safe. Indicated uses: minor skin irritation, insect bites, hemorrhoids (witch hazel pads = Tucks-style products), mild post-shave skin, oily skin toning. USP monograph established for over a century.",
        "category": "medicine",
        "domains": ["medicine", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONFIRMED",
        "pre_run": {
            "summary": "Tannin astringents: protein-precipitation chemistry → tissue tightening, reduced secretions, mild surface antibacterial. Effect is real but modest; primary value is broad safety + cheap availability.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Hamamelitannin + gallic acid derivatives bind protein side-chains, cross-linking surface tissue", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "USP and BP monographs; topical astringent and anti-inflammatory; safe for adults and children", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["witch hazel extract (USP, OTC; typically 14% alcohol or alcohol-free)", "cotton balls or pads"],
            "tools": [],
            "steps": ["apply with cotton ball to clean skin", "for hemorrhoids: pre-soaked pads (Tucks-style) used after bowel movements; cool sensation soothes", "for insect bites: dab on after washing to reduce itch and swelling", "for skin toner: apply after washing, before moisturizer", "do NOT apply to open wounds or broken skin (alcohol stings)"],
            "time": "instant relief; reapply as needed",
            "cost_usd_2026": "$3–6 per 16 oz bottle",
            "scale": "general topical use. **SEE A DOCTOR** for: hemorrhoids with bleeding (rule out other causes), skin lesions that don't heal in 2 weeks, severe insect bite reactions",
        },
        "wisdom": "Witch hazel is the workhorse of mild skincare and minor itch — one of those products with a USP monograph, a 19th-century pedigree, and modern dermatology endorsement. The Shepherd brings this for mosquito bites, mild rashes, hemorrhoids, post-shave. Cheap, broadly safe, modest-but-real effect.",
        "triggers": {"keywords": ["witch hazel", "Hamamelis", "tannin astringent", "hemorrhoid", "skin toner"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 9 ─ Chamomile (MIXED) ─────────────────────────────────────────
    {
        "id": "practical_chamomile_mild_sedative",
        "kind": "practical",
        "title": "Chamomile — apigenin GABA-A binding; mild sedative + GI antispasmodic",
        "vertical": "medicine",
        "source": {"publication": "AHRQ + herbal medicine review literature", "year": 2018},
        "situation": "Chamomile (Matricaria chamomilla = German chamomile; Chamaemelum nobile = Roman) contains apigenin, a flavonoid that binds GABA-A receptor benzodiazepine site (the same site as Valium-class drugs) with weak affinity. Also contains bisabolol and chamazulene (anti-inflammatory). RCTs show modest benefit for generalized anxiety (Amsterdam 2009: 220 mg apigenin equiv × 8 weeks), mild insomnia, and infantile colic. Effect size is small; comparison to placebo statistically detectable but unlikely to substitute for proper treatment of moderate-severe anxiety.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "MIXED",
        "pre_run": {
            "summary": "Real mechanism, real effect, modest magnitude. Tea form delivers low apigenin doses; standardized capsules deliver enough to measure but still modest compared to pharmaceutical anxiolytics.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Apigenin partial agonist at GABA-A benzodiazepine binding site", "data": {}},
                {"domain": "medicine", "verdict": "MIXED", "detail": "RCT support for GAD (modest effect size), insomnia (mixed), colic (modest); not substitute for evidence-based anxiety treatment", "data": {"effect_size": "small"}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["chamomile tea bags OR loose flowers OR standardized capsules (220 mg apigenin equivalent)"],
            "tools": ["mug + hot water"],
            "steps": ["TEA: 1–2 tsp dried flowers in 8 oz hot water, steep 5–10 min covered (covering retains volatile oils), 1–3 cups daily", "CAPSULE: 220 mg standardized apigenin × 1–3 daily", "WARNINGS: allergy possible (ragweed family — Asteraceae cross-reactivity), interacts with warfarin (modest CYP inhibition), avoid in pregnancy at therapeutic doses"],
            "time": "onset within hour; mild and cumulative",
            "cost_usd_2026": "$3–8 box of tea bags; $15–25 standardized capsule month",
            "scale": "adults with mild anxiety, sleep onset issues, or stomach upset. **SEE A DOCTOR** for: moderate-severe anxiety, suicidal ideation, panic disorder, insomnia >3 weeks, allergic reactions to ragweed family",
        },
        "wisdom": "Chamomile works — modestly. The Shepherd brings this for mild anxiety, occasional sleep onset trouble, and stomach upset, with the honest caveat that it is NOT a substitute for evidence-based treatment of moderate depression, anxiety, or sleep disorders. The grandmother's tea before bed has real chemistry behind it; the dose is small.",
        "triggers": {"keywords": ["chamomile", "apigenin", "mild anxiety", "sleep tea", "herbal sedative"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 10 ─ Garlic for BP (MIXED) ────────────────────────────────────
    {
        "id": "practical_garlic_blood_pressure",
        "kind": "practical",
        "title": "Garlic — allicin chemistry, modest BP effect (~5 mmHg), oversold in food culture",
        "vertical": "medicine",
        "source": {"publication": "Cochrane hypertension reviews + meta-analyses 2013–2020", "year": 2020},
        "situation": "Garlic (Allium sativum) preparations standardized to allicin yield ~5–10 mmHg reduction in systolic blood pressure and ~3–5 mmHg in diastolic, on average, in patients with hypertension. Mechanism: allicin and downstream sulfur compounds increase nitric oxide bioavailability and inhibit ACE modestly. The effect is real and clinically meaningful at the population level, but small compared to standard antihypertensives. Antibacterial activity is strong IN VITRO but minimal at dietary doses in vivo. Significant drug interaction: garlic enhances anticoagulant effect of warfarin.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "nutrition"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "MIXED",
        "pre_run": {
            "summary": "Real but modest cardiovascular benefit at high standardized doses. Cultural folk-medicine claims (cures all infections, prevents cancer, lowers cholesterol dramatically) outrun the data.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Alliin → allicin (alliinase enzyme on crushing) → H₂S → vasodilation via nitric oxide pathway", "data": {}},
                {"domain": "medicine", "verdict": "MIXED", "detail": "Meta-analyses: garlic supplements 600–1200 mg/day reduce SBP ~5–8 mmHg in hypertensive patients; null effect in normotensive", "data": {"SBP_drop_mmHg": 5.5}},
                {"domain": "nutrition","verdict": "MIXED", "detail": "Dietary garlic (1–2 cloves daily): minimal measurable cardiovascular effect; cultural use far outruns the data", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["garlic supplement standardized to 1.3% allicin (Kyolic, Garlinase, generic), 600–1200 mg/day — OR raw or freshly-crushed garlic in food"],
            "tools": ["pill organizer if using supplement"],
            "steps": ["FOR BP: 600–1200 mg standardized supplement daily, divided dose, with food", "FOR FOOD: crush garlic and let stand 10 min before cooking (activates alliinase); cooked garlic loses some activity", "AVOID HIGH-DOSE SUPPLEMENT before surgery (1 week withdrawal) — bleeding risk", "DRUG INTERACTIONS: enhances warfarin/anticoagulant effect; potential interaction with HIV protease inhibitors"],
            "time": "BP effect after 4–8 weeks consistent use",
            "cost_usd_2026": "$10–20/month supplement; pennies for raw garlic",
            "scale": "complement to lifestyle in mild hypertension. **NOT A REPLACEMENT** for prescribed antihypertensives. **SEE A DOCTOR** for: any BP consistently ≥140/90, before stopping prescribed medications, before surgery, anticoagulant use",
        },
        "wisdom": "Garlic helps a bit; it doesn't replace ramipril. The Shepherd brings this for the user looking to complement (not replace) standard cardiovascular care — and pushes back honestly on the folk-medicine maximalism that has garlic curing everything. Real chemistry, real effect, real warnings.",
        "triggers": {"keywords": ["garlic", "allicin", "blood pressure", "Allium sativum", "natural BP"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 11 ─ Turmeric / curcumin (MIXED — bioavailability) ───────────
    {
        "id": "practical_turmeric_curcumin_bioavailability",
        "kind": "practical",
        "title": "Turmeric / curcumin — strong in cell culture, weak orally; piperine enhances absorption 20×",
        "vertical": "medicine",
        "source": {"publication": "Pharmacokinetic + meta-analysis literature 2015–2021", "year": 2020},
        "situation": "Curcumin (the major curcuminoid in turmeric, Curcuma longa) demonstrates potent anti-inflammatory effects in vitro and modest anti-inflammatory and anti-arthritic effects in vivo when delivered in bioavailability-enhanced formulations. Plain curcumin has oral bioavailability of <1% — most is destroyed by stomach acid or rapidly metabolized. Black pepper extract (piperine, 5–20 mg per dose) inhibits curcumin glucuronidation and increases bioavailability ~20×. Specialized formulations (Meriva phytosome, BCM-95, Theracurmin) achieve 10–30× the absorption of plain curcumin. RCT data: modest pain reduction in osteoarthritis (comparable to ibuprofen at 8 weeks in some studies).",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "MIXED",
        "pre_run": {
            "summary": "Spectacular in vitro, modest in vivo unless bioavailability-enhanced. Most cheap turmeric supplements have minimal effect; specific formulations do produce measurable effects.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Curcumin: inhibits NF-κB, COX-2, multiple inflammatory cytokines in cell culture; rapid glucuronidation in vivo limits exposure", "data": {"oral_bioavailability_plain_pct": 1}},
                {"domain": "medicine", "verdict": "MIXED", "detail": "Osteoarthritis RCTs (Meriva, BCM-95): modest pain reduction comparable to ibuprofen at high doses; plain turmeric powder ineffective at dietary doses", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["curcumin supplement WITH bioavailability enhancement: black pepper extract (piperine) OR phytosomal formulation (Meriva) OR BCM-95"],
            "tools": [],
            "steps": ["DOSE: 500–1000 mg curcumin (in a bioavailability-enhanced form) × 2 daily with food", "ANTI-INFLAMMATORY EFFECT requires 4–8 weeks of consistent use", "DIETARY TURMERIC alone (sprinkled on food): negligible effect at typical culinary amounts", "DRUG INTERACTIONS: anticoagulants (modest effect), some chemotherapy drugs"],
            "time": "trial period: 8 weeks for arthritis pain",
            "cost_usd_2026": "$15–30/month for quality enhanced supplements",
            "scale": "adults considering complementary anti-inflammatory. **NOT A REPLACEMENT** for proper inflammation diagnosis and treatment. **SEE A DOCTOR** for: chronic joint pain (diagnosis first), anticoagulation, before surgery, gallbladder disease (stimulates contraction)",
        },
        "wisdom": "Curcumin is a perfect example of the bioavailability problem: a molecule that works in a Petri dish but rarely reaches blood concentrations in the body. The Shepherd brings this with the engineering caveat — plain turmeric is mostly food coloring + flavor; bioavailability-enhanced supplements have real effects. The 'turmeric milk' or sprinkled-on-food approach delivers cultural pleasure, not clinical anti-inflammation.",
        "triggers": {"keywords": ["turmeric", "curcumin", "bioavailability", "piperine", "Meriva", "anti-inflammatory"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 12 ─ Echinacea for cold (MIXED) ────────────────────────────────
    {
        "id": "practical_echinacea_cold",
        "kind": "practical",
        "title": "Echinacea — modest cold-duration reduction, depends on species/preparation",
        "vertical": "medicine",
        "source": {"publication": "Cochrane Acute Respiratory Infections Group", "year": 2014},
        "situation": "Echinacea preparations (most studied: E. purpurea root and herb) taken at the first signs of common cold may shorten illness duration by 0.5–1.5 days and reduce symptom severity modestly in some — but not all — meta-analyses. Variability is huge: extracts differ in plant part, species, preparation method, and active phytochemical profile (alkamides, polysaccharides, caffeic acid derivatives). Standardized preparations (e.g., Echinaforce / E. purpurea fresh-pressed juice) show clearer benefit; many cheap supplements show none.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "authority_trust"],
        "verdict": "MIXED",
        "pre_run": {
            "summary": "Real but small effect that depends heavily on preparation. The Shepherd treats variability as the central message: not all 'echinacea' is the same product.",
            "domain_results": [
                {"domain": "biology",  "verdict": "MIXED", "detail": "Alkamides and polysaccharides have demonstrable in vitro immunomodulatory effects; in vivo translation modest", "data": {}},
                {"domain": "medicine", "verdict": "MIXED", "detail": "Cochrane 2014: weak overall evidence; some standardized products show ~1 day shortening; many do not", "data": {"duration_reduction_days": 1.0}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["standardized echinacea product (Echinaforce, EchinaGuard, or A. Vogel formulations preferred for evidence base)"],
            "tools": [],
            "steps": ["START AT FIRST SYMPTOM: scratchy throat / first sneezes; later starts have less effect", "DOSE: per product label (typically 5–10 mL fresh-pressed juice 3× daily for 7–10 days)", "PREVENTIVE USE: no clear evidence; if taken, limit to 8 weeks then break", "AVOID in: autoimmune disease, immunosuppression, allergy to Asteraceae family"],
            "time": "during cold episodes (5–10 days)",
            "cost_usd_2026": "$15–25 per bottle (1–3 episodes)",
            "scale": "adults with otherwise-healthy immune system. **NOT FOR**: autoimmune disease, transplant patients, ongoing chemo, ragweed allergy. **SEE A DOCTOR** for: fever >3 days, productive purulent cough, severe sore throat (rule out strep), shortness of breath, symptoms >10 days",
        },
        "wisdom": "Echinacea is the classic 'maybe' of the apothecary — a real plant with real chemistry, modest evidence, and huge product-quality variability. The Shepherd brings this for the user with the first cold tickle who wants something with a plausible mechanism — and notes that brand choice matters more than the herb name on the label.",
        "triggers": {"keywords": ["echinacea", "cold remedy", "immune support", "Echinaforce"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 13 ─ Activated charcoal (MIXED — emergency vs detox) ─────────
    {
        "id": "practical_activated_charcoal_poisoning",
        "kind": "practical",
        "title": "Activated charcoal — emergency poisoning only; 'detox' uses are MISMATCH",
        "vertical": "medicine",
        "source": {"publication": "American Academy of Clinical Toxicology + AAPCC poison control guidance", "year": 2020},
        "situation": "Activated charcoal (highly porous carbon, ~1000 m²/g surface area) adsorbs many drugs and toxins via van der Waals forces. Clinical use is well-established: oral activated charcoal 1 g/kg within 1 hour of acute ingestion of certain poisons (acetaminophen, aspirin, tricyclic antidepressants, many others) reduces systemic absorption. Outside this narrow window, activated charcoal as a general 'detox' or daily wellness supplement is **MISMATCH** — there are no documented circulating toxins it removes through the gut wall in healthy people, and daily use risks malabsorption of nutrients and prescription drugs.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "MIXED",
        "pre_run": {
            "summary": "CONFIRMED for acute oral poisoning within 1 hour. MISMATCH for daily detox/wellness use. The mechanism (gut-lumen adsorption) cannot reach circulating toxins; the body's actual detoxification is liver + kidneys, not charcoal.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "High surface area (~1000 m²/g) adsorbs many small organic molecules in gut lumen", "data": {"surface_area_m2_per_g": 1000}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Standard ER intervention for many acute oral overdoses if ingestion within 1 hour; not effective for alcohols, heavy metals, lithium, iron", "data": {"effective_window_hours": 1}},
                {"domain": "biology",  "verdict": "MISMATCH", "detail": "No demonstrated removal of 'systemic toxins' through gut adsorption in non-overdose context; daily use can adsorb prescription medications and nutrients", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["activated charcoal capsules (USP) — keep in home first-aid kit"],
            "tools": ["poison control phone number visible at home (US: 1-800-222-1222)"],
            "steps": ["**ANY SUSPECTED POISONING**: call poison control FIRST. Do NOT administer charcoal without instruction — wrong drugs to charcoal can worsen outcomes", "if directed by poison control: 1 g/kg adult dose orally", "DO NOT use for: alkali / acid ingestion (worsens), petroleum ingestion (aspiration risk), unconscious patient (aspiration risk)", "DO NOT use as daily supplement, in 'detox teas', or for 'gut cleansing' — risks include drug interactions, malabsorption"],
            "time": "single emergency dose; do not use chronically",
            "cost_usd_2026": "$10 for first-aid bottle (one-time)",
            "scale": "emergency-kit item. **ALWAYS CALL POISON CONTROL FIRST** for any suspected poisoning",
        },
        "wisdom": "Activated charcoal is a real emergency-medicine tool with a narrow window and a specific use. It is NOT a daily wellness aid. The Shepherd brings this with the sharp distinction: keep it in your first-aid kit AND call poison control before using; ignore the daily-detox-charcoal marketing entirely.",
        "triggers": {"keywords": ["activated charcoal", "poisoning", "overdose", "detox supplement", "gut cleanse"], "axes": ["metabolism", "physical_substance"]},
    },

    # ── 14 ─ Vitamin C for cold prevention (MISMATCH) ─────────────────
    {
        "id": "practical_vitamin_c_cold_prevention",
        "kind": "practical",
        "title": "Vitamin C for cold prevention — MISMATCH for general population (some effect for athletes/cold climate)",
        "vertical": "medicine",
        "source": {"publication": "Cochrane Acute Respiratory Infections Group meta-analyses", "year": 2013},
        "situation": "Regular vitamin C supplementation (200 mg–1 g/day) in the general adult population does NOT reduce cold incidence. Cochrane meta-analysis of 29 trials and 11,306 participants: no significant reduction in cold occurrence. Specific subpopulations show effect: people under heavy physical stress (marathon runners, soldiers in subarctic conditions) — incidence halved. Treatment dosing (taking vitamin C only when cold starts) shows minimal effect. Duration of cold reduced ~8% in adults, ~14% in children — small but consistent.",
        "category": "medicine",
        "domains": ["medicine", "nutrition", "statistics"],
        "axes": ["metabolism", "authority_trust"],
        "verdict": "MISMATCH",
        "pre_run": {
            "summary": "The 'vitamin C prevents colds' belief is popularly held but unsupported by meta-analytic evidence in the general population. Linus Pauling's 1970s mega-dose advocacy was influential; the data did not bear it out.",
            "domain_results": [
                {"domain": "medicine",  "verdict": "MISMATCH", "detail": "Cochrane 2013: no reduction in cold incidence in general population. Subgroups (extreme physical stress) show effect", "data": {"general_population_RR": 0.97}},
                {"domain": "statistics","verdict": "CONFIRMED", "detail": "Modest reduction in cold duration (8% adults, 14% children) but not incidence", "data": {"duration_reduction_pct": 8}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["dietary sources: citrus, peppers, broccoli, kiwi (75 mg/day adequate)", "supplement (250–500 mg) if dietary intake is poor"],
            "tools": [],
            "steps": ["adequate dietary intake (75 mg women / 90 mg men / 120 mg pregnancy) does prevent scurvy and supports collagen synthesis — these are the real reasons vitamin C matters", "for cold PREVENTION in general population: don't expect benefit; routine supplementation is unnecessary", "for cold DURATION reduction: modest benefit if started before symptoms; minimal once cold is established", "MEGA-DOSES (>2g/day): may cause GI symptoms, kidney stone risk in susceptible individuals"],
            "time": "if effective for duration: continuous use",
            "cost_usd_2026": "$0 from diet; $3–10/month supplement",
            "scale": "adequate intake matters; mega-doses do not deliver the promised cold prevention. **SEE A DOCTOR** for: recurring infections (immune workup), kidney stones, persistent cold symptoms",
        },
        "wisdom": "The vitamin C story is a case study in how a Nobel laureate's enthusiasm outran the data — Linus Pauling's mega-dose advocacy in the 1970s shaped a generation of cultural belief that doesn't survive meta-analysis. The Shepherd carries this honest correction: vitamin C is essential (you need ~90 mg/day); it does not prevent colds in the general population.",
        "triggers": {"keywords": ["vitamin C", "ascorbic acid", "cold prevention", "Linus Pauling", "mega-dose"], "axes": ["metabolism", "authority_trust"]},
    },

    # ── 15 ─ Ear candling (MISMATCH — actively harmful) ──────────────
    {
        "id": "practical_ear_candling_mismatch",
        "kind": "practical",
        "title": "Ear candling — MISMATCH; no wax removed, real injury risk, the engine refuses",
        "vertical": "medicine",
        "source": {"publication": "FDA + Health Canada + multiple peer-reviewed studies", "year": 2010},
        "situation": "Ear candling (or 'ear coning') is the practice of inserting a hollow conical candle into the ear and lighting the far end, claimed to draw out earwax via suction or 'detoxification.' Studies measuring intra-aural pressure during candling find NO negative pressure generated. Wax-like residue in the candle after burning is the candle's own combustion products, not extracted ear wax. Documented harms: burns to the face/ear/eardrum (FDA reports), candle wax dripped into ear canal (creates the problem it claims to solve), tympanic membrane perforation, hearing loss, fire risk to hair. The FDA classifies ear candling as deceptive marketing of a medical device.",
        "category": "medicine",
        "domains": ["medicine", "physics", "biology"],
        "axes": ["physical_substance", "authority_trust"],
        "verdict": "MISMATCH",
        "pre_run": {
            "summary": "The mechanism doesn't work (no suction); the residue isn't wax; the practice causes documented injuries. The engine names this clearly to push back on a popular folk-medicine claim that hurts people.",
            "domain_results": [
                {"domain": "physics", "verdict": "MISMATCH", "detail": "Pressure measurements during candling: no negative pressure generated; mechanism claim is false", "data": {}},
                {"domain": "medicine","verdict": "MISMATCH", "detail": "FDA and Health Canada warn against ear candling; documented harm > zero benefit", "data": {}},
                {"domain": "biology","verdict": "MISMATCH", "detail": "Residue in spent candle is candle wax + soot, not ear wax (chemical analysis)", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": [],
            "tools": [],
            "steps": ["**THE SHEPHERD REFUSES this protocol.** The engine does not provide ear-candling instructions.", "FOR ACTUAL EARWAX MANAGEMENT, the keeping recommends: warm-water bulb syringe irrigation (with intact eardrum), over-the-counter ceruminolytic drops (Debrox / carbamide peroxide), or visit to a healthcare provider for manual removal", "DO NOT use cotton swabs deeply (impacts wax further in)"],
            "time": "n/a",
            "cost_usd_2026": "n/a",
            "scale": "do not practice. **SEE A DOCTOR** for: hearing loss, ear pain, blocked ear sensation",
        },
        "wisdom": "Some popular remedies the engine actively refuses to launder — ear candling is one. The mechanism doesn't work; the residue isn't wax; people get burned. The Shepherd brings the correction directly: this is a MISMATCH on every checkable axis, and the keeping does not become an aggregator of folk practices that hurt people just because they are popular.",
        "triggers": {"keywords": ["ear candling", "ear coning", "earwax removal", "Hopi ear candle"], "axes": ["physical_substance", "authority_trust"]},
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
            print(f"  + {e['id']:50s}  {e['verdict']}")

    # Verdict breakdown
    from collections import Counter
    c = Counter(e['verdict'] for e in to_write)
    print(f"\n-- appended {len(to_write)} apothecary entries")
    print(f"   verdict breakdown: {dict(c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
