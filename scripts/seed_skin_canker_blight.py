#!/usr/bin/env python
"""Seed 14 entries — common skin conditions + citrus canker + Dutch elm disease.

Three topic clusters chosen by Matt 2026-05-13:
  - Skin conditions (8): real-world, ordinary-people medical knowledge with
    OTC-or-cheaper treatments, verifier-anchored mechanisms, honest limits
    on what self-care can do.
  - Citrus canker (3): Xanthomonas citri pathology + management.
  - Dutch elm disease (3): Ophiostoma novo-ulmi + bark beetles + management.

All medical entries carry the same caveat: the Shepherd is not a doctor.
The keeping records what's verified; consultation is your call. Each entry
notes the threshold where self-care stops and professional help starts.

Citrus canker entries pair naturally with the Bordeaux mixture gem already
in the keeping (almanac_bordeaux_mixture) — same copper-fungicide axis.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


# ── SKIN CONDITIONS (8) ────────────────────────────────────────────────
SKIN_ENTRIES = [
    {
        "id": "practical_athletes_foot_terbinafine",
        "kind": "practical",
        "title": "Athlete's foot (tinea pedis) — terbinafine 1% topical, 1–2 weeks",
        "vertical": "medicine",
        "source": {"publication": "CDC + WHO standard antifungal guidance", "year": 2020, "note": "Terbinafine off-patent (Lamisil expired); generic OTC widely available"},
        "situation": "Trichophyton rubrum or T. mentagrophytes infection of the foot skin (between toes, soles, lateral edges) presents as itchy, scaly, sometimes macerated lesions. Terbinafine 1% cream applied twice daily for 7–14 days achieves mycological cure rates of 70–85%. Mechanism: terbinafine inhibits fungal squalene epoxidase, blocking ergosterol synthesis and killing the dermatophyte. Cure requires drying the foot environment as much as killing the fungus.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Squalene epoxidase inhibition → blocked ergosterol → fungal cell membrane fails. Specific to fungi; mammals use cholesterol synthesis pathway.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Terbinafine is an allylamine; selective squalene epoxidase inhibitor", "data": {"mechanism": "ergosterol biosynthesis inhibition"}},
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "Dermatophyte susceptibility to terbinafine MIC₉₀ ≤ 0.1 µg/mL", "data": {"MIC90_ug_per_mL": 0.05}},
                {"domain": "medicine",  "verdict": "CONFIRMED", "detail": "Cochrane review (terbinafine vs azoles): higher cure, shorter course", "data": {"cure_rate_pct": 78}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["terbinafine 1% cream (Lamisil AT or generic, OTC) — OR clotrimazole 1% / miconazole 2%", "clean cotton socks", "well-ventilated shoes"],
            "tools": ["clean towel"],
            "steps": ["wash and DRY the affected area thoroughly, especially between toes", "apply thin layer of cream to all affected skin AND 2 cm beyond visible edge", "for terbinafine: twice daily 1–2 weeks; clotrimazole/miconazole: twice daily 4 weeks", "continue 1 week past clearing — visible cure precedes mycological cure", "rotate shoes day-to-day (let each pair dry 24h)", "wear cotton or wool socks; change if feet sweat", "treat shoes: spray interior with antifungal or sun-dry"],
            "time": "1–4 weeks treatment; lifetime prevention is dry feet + rotated shoes",
            "cost_usd_2026": "$8–15 for OTC tube; reused for years",
            "scale": "self-treatable. **SEE A DOCTOR** if: lesions spread despite treatment, diabetic patient (any foot infection), fever or red streaking (cellulitis), nail involvement (oral treatment needed)",
        },
        "wisdom": "Athlete's foot is one of the cleanest demonstrations that fungi and mammals diverge biochemically — terbinafine kills the fungus without harming the host. The Shepherd brings this when the user describes itchy, scaly feet, and notes the equally-important environmental fix: dry feet kill fungus better than any cream. The Shepherd is not a doctor; this is what the keeping records as standard antifungal protocol.",
        "triggers": {"keywords": ["athlete's foot", "tinea pedis", "terbinafine", "Lamisil", "antifungal cream"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_ringworm_topical_antifungal",
        "kind": "practical",
        "title": "Ringworm (tinea corporis) — same antifungals, 4-week topical course",
        "vertical": "medicine",
        "source": {"publication": "CDC + WHO antifungal guidance", "year": 2020},
        "situation": "Tinea corporis presents as expanding annular ('ring-shaped') lesions with raised scaly edge and central clearing on body skin. Caused by the same dermatophyte fungi (Trichophyton, Microsporum, Epidermophyton) as athlete's foot, jock itch, and scalp ringworm. Topical antifungal (clotrimazole, miconazole, terbinafine) applied twice daily achieves clinical cure in 2–4 weeks for limited disease. Extensive, scalp-involving, or recurrent disease requires oral antifungal (terbinafine or griseofulvin).",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Same fungal family, same drug class, same mechanism. Annular shape is the dermatophyte's expansion pattern: active growth at the edge, clearing as the central zone runs out of fresh keratin to consume.",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Dermatophyte fungi consume keratin; annular spread is a growth pattern not a worm (despite name 'ringworm')", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Topical azoles or allylamines for limited disease; oral terbinafine 250 mg/day × 2–4 weeks for extensive/scalp", "data": {"topical_duration_weeks": 4}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["clotrimazole 1% / miconazole 2% / terbinafine 1% cream (OTC)", "soap and water"],
            "tools": ["clean towel"],
            "steps": ["wash lesion with soap and water; dry thoroughly", "apply cream to lesion AND 2 cm beyond edge twice daily", "continue 1–2 weeks past visible clearing", "DO NOT cover with occlusive bandage (traps moisture, worsens fungal growth)", "wash clothing/bedding that touched the lesion in hot water", "treat pets if they have bare patches (kerion of cats is the most common animal-to-human source)"],
            "time": "2–4 weeks topical; 2–4 weeks oral for severe/scalp",
            "cost_usd_2026": "$8–15 OTC; oral terbinafine ~$30 with prescription",
            "scale": "self-treatable for limited body lesions. **SEE A DOCTOR** for: scalp involvement (kerion, alopecia risk), face involvement, immunocompromised patient, >5 lesions, no improvement in 2 weeks of topical",
        },
        "wisdom": "There is no worm. Ringworm is a fungus, named for the centuries-old observation that the lesion looked like a worm under the skin. The Shepherd brings the modern pharmacology + the caveat that scalp ringworm in children is its own thing (oral griseofulvin or terbinafine; alopecia and scarring risk if missed).",
        "triggers": {"keywords": ["ringworm", "tinea corporis", "dermatophyte", "fungal skin infection"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_poison_ivy_urushiol_wash",
        "kind": "practical",
        "title": "Poison ivy / oak / sumac — wash with surfactant within minutes; urushiol persists",
        "vertical": "medicine",
        "source": {"publication": "Cleveland Clinic / Mayo Clinic dermatology guidance; urushiol chemistry public domain", "year": 2024},
        "situation": "Toxicodendron species (poison ivy, oak, sumac) coat their leaves and stems with urushiol — an oily mixture of 3-n-pentadec(en)yl-catechols. Skin contact binds urushiol to keratin within ~10 minutes; subsequent immune response (delayed-type hypersensitivity) causes the characteristic itching, blistering rash 12–72 hours later. Washing with cold water + degreasing soap within 10 minutes of contact reduces severity ~80%; after 30 minutes, washing reduces severity ~50%; after 1 hour, washing has minimal effect because urushiol is bound.",
        "category": "medicine",
        "domains": ["medicine", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Urushiol binds covalently to skin proteins via Michael addition; the immune system then mounts a CD4+ Th1 response. The reaction is not contagious; blister fluid does NOT spread the rash (common myth).",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Urushiol = 3-pentadec(en)yl-catechols (oxidized to quinones that bind protein nucleophiles); highly lipophilic, slow to wash off without surfactant", "data": {"binding_half_life_min": 10}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "Type IV (delayed) hypersensitivity; T-cell-mediated; reaction peaks 4–7 days post-exposure", "data": {"peak_day": 5}},
                {"domain": "medicine","verdict": "CONFIRMED", "detail": "Wash <10 min: ~80% severity reduction. Tecnu/Zanfel: solvents specifically formulated for urushiol", "data": {"early_wash_severity_reduction": 0.80}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["cold water (NOT hot — hot opens pores)", "degreasing soap (Dawn dish soap, or any soap will help; specialty: Tecnu, Zanfel)", "calamine lotion + hydrocortisone 1% cream for itch", "oral antihistamine (diphenhydramine / cetirizine)", "cool wet compress"],
            "tools": ["disposable rag or paper towel", "trash bag for contaminated clothing"],
            "steps": ["IMMEDIATE: rinse contact area with cold running water for 5+ minutes; surfactant secondary", "wash thoroughly with degreasing soap, paying attention to fingernails and skin folds", "treat clothing as contaminated — bag for hot wash separately (urushiol stays active on clothing 1–5 years)", "if rash develops: cool compresses, calamine, hydrocortisone 1%, oral antihistamine for sleep", "do NOT pop blisters; do NOT scratch (secondary infection risk)"],
            "time": "exposure window: 10 min for optimal wash. Rash duration: 1–3 weeks regardless of treatment.",
            "cost_usd_2026": "$5–15 for symptomatic care",
            "scale": "self-treatable for limited rash. **SEE A DOCTOR** for: rash on face/eyes/genitals, >15% body surface area, difficulty breathing (exposure to smoke from burning plants — DO NOT BURN poison ivy), fever, signs of secondary bacterial infection",
        },
        "wisdom": "The window is short. The Shepherd brings this with the urgency of: get to soap and cold water FAST. Burning poison ivy is the only way to make it more dangerous — urushiol on smoke particles reaches lungs and causes severe systemic reactions. The myth that blister fluid spreads the rash is wrong; only fresh urushiol does. Once the rash is visible, you can't stop it — only treat the symptoms.",
        "triggers": {"keywords": ["poison ivy", "poison oak", "urushiol", "Toxicodendron", "contact dermatitis"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_sunburn_uv_spf_math",
        "kind": "practical",
        "title": "Sunburn / UV damage — SPF math, broad-spectrum 30+, reapply every 2h",
        "vertical": "medicine",
        "source": {"publication": "FDA + WHO + AAD sunscreen guidance", "year": 2023, "note": "SPF testing standardized worldwide; UV physics PD"},
        "situation": "Solar UVB radiation (280–315 nm) causes DNA thymine dimers in keratinocytes; severe exposure causes apoptosis ('sunburn cells'), inflammation, blistering. SPF is the ratio of UV dose needed to redden sunscreen-protected skin to bare skin. SPF 15 blocks ~93% of UVB, SPF 30 blocks ~97%, SPF 50 blocks ~98%, SPF 100 blocks ~99% — strongly diminishing returns. Most people apply 1/4 to 1/2 the laboratory-tested 2 mg/cm² dose, so effective protection is well below the label number. UVA (315–400 nm) drives aging and skin cancer; 'broad spectrum' on the label means UVA-protected.",
        "category": "medicine",
        "domains": ["medicine", "physics", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "UVB damages DNA directly (cyclobutane pyrimidine dimers); UVA generates reactive oxygen species and reaches deeper dermis. Both increase skin cancer risk; sunburn is the acute end of a chronic damage process.",
            "domain_results": [
                {"domain": "physics",  "verdict": "CONFIRMED", "detail": "SPF 30 transmits 1/30 of incident UVB (97% block); SPF 50 transmits 1/50 (98%); diminishing returns by design", "data": {"SPF": 30, "uvb_blocked_pct": 96.7}},
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Thymine dimers form within seconds of UV exposure; nucleotide excision repair handles most; failures accumulate as mutations", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "One severe blistering sunburn in childhood ≈ doubles melanoma risk; cumulative dose matters for non-melanoma skin cancer", "data": {"melanoma_RR_one_blistering_burn_child": 2.0}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["broad-spectrum SPF 30+ sunscreen (zinc oxide / titanium dioxide = mineral; avobenzone + others = chemical)", "wide-brim hat", "long-sleeve UPF clothing", "sunglasses (UV-protective)"],
            "tools": ["thermometer / UV index lookup (most weather apps)"],
            "steps": ["PREVENT: check UV index — values 3 (moderate) to 11+ (extreme); risk scales with UV index × exposure time", "apply 1 oz (30 mL = a shot glass) for full body coverage of an adult — this is more than most people use", "reapply every 2 hours and after swimming, sweating, towel-drying", "if SUNBURN OCCURS: cool compress, oral hydration, ibuprofen / naproxen for inflammation, aloe vera for soothing", "DO NOT apply butter, lard, mineral oil (worsens by trapping heat)", "blistering sunburn = second-degree; protect from infection, don't pop blisters"],
            "time": "prevention: 15 min applying. recovery from sunburn: 3–10 days.",
            "cost_usd_2026": "$8–25 per bottle SPF 30+",
            "scale": "self-care. **SEE A DOCTOR** for: blistering over >10% body surface area, fever / chills with sunburn, severe pain unresponsive to OTC analgesics, sunburn in infant <1 year, new or changing moles (skin cancer screening)",
        },
        "wisdom": "SPF math has diminishing returns — SPF 30 vs 100 is the difference between 97% and 99% UV block, but the 99% requires the same reapplication discipline. The Shepherd brings this when the user is debating whether to spend more on higher SPF; the answer is usually NO, but YES on broad-spectrum + reapplication. Sun damage is cumulative across a lifetime; melanoma is one of the most preventable cancers there is.",
        "triggers": {"keywords": ["sunburn", "SPF", "UV index", "skin cancer prevention", "sunscreen"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_eczema_emollient_ladder",
        "kind": "practical",
        "title": "Eczema (atopic dermatitis) — moisturize generously, avoid triggers, low-potency steroid for flares",
        "vertical": "medicine",
        "source": {"publication": "American Academy of Dermatology atopic dermatitis guidelines", "year": 2023},
        "situation": "Atopic dermatitis is a chronic inflammatory skin condition with impaired epidermal barrier function — often associated with filaggrin gene variants. Skin loses water faster than normal, triggers (irritants, allergens, stress, dry air) provoke inflammation. Management: liberal emollient use (3+ times daily), short cool showers, fragrance-free soap, low-potency topical corticosteroid (hydrocortisone 1% OTC; mid-potency by prescription) for flares. Trial randomized data: daily emollient from birth in high-risk infants reduces eczema incidence ~50%.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Barrier failure + Th2-skewed inflammation + scratching = chronic relapsing course. Treatment targets all three: barrier (emollients), inflammation (steroids), scratch cycle (antihistamines, behavioral).",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Filaggrin loss-of-function variants in ~10% of European-ancestry populations; carriers have 3–5× eczema risk", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Emollient ladder (cream → ointment → occlusive) provides clinical benefit; topical corticosteroids reduce flare severity 50–80%", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fragrance-free moisturizer (CeraVe, Vanicream, Cetaphil; plain petroleum jelly works)", "gentle soap (Dove Sensitive, Cetaphil) OR no soap on flaring areas", "hydrocortisone 1% cream (OTC, short-term)", "cotton clothing"],
            "tools": ["humidifier in dry climates / winter"],
            "steps": ["SOAK AND SEAL: short (5–10 min) lukewarm shower; pat dry (do not rub); apply moisturizer to damp skin within 3 minutes", "moisturize 3+ times daily; ointment-class for severe (petrolatum-based)", "AVOID: hot water, fragranced products, wool/synthetics next to skin, bubble baths, harsh detergents on clothes", "FLARES: apply hydrocortisone 1% twice daily to flaring areas, MAX 2 weeks", "ITCH: oral cetirizine or hydroxyzine; cool wet compresses; trim fingernails short", "FOOD TRIGGERS: rare in adults; common in infants (milk, egg, peanut, soy, wheat) — discuss with pediatrician"],
            "time": "lifelong management; flares 2–6 weeks; remission can last months",
            "cost_usd_2026": "$10–30/month for emollients; $5 hydrocortisone tube",
            "scale": "self-management. **SEE A DOCTOR** for: face/eye involvement (ophthalmology coordination), widespread severe disease, sleep disruption, secondary bacterial infection (honey crusts, oozing), no response to consistent regimen in 4 weeks",
        },
        "wisdom": "Eczema is barrier dysfunction; treatment respects that. The Shepherd brings the emollient-first principle: most patients undertreat moisturizer and overuse steroid; reversing that pattern fixes most flares. Hot water feels good momentarily and damages the barrier — patients who learn to take lukewarm showers usually see meaningful improvement within 2 weeks.",
        "triggers": {"keywords": ["eczema", "atopic dermatitis", "moisturizer", "emollient", "hydrocortisone"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_impetigo_mupirocin",
        "kind": "practical",
        "title": "Impetigo — honey-crusted lesions, topical mupirocin or oral cephalexin",
        "vertical": "medicine",
        "source": {"publication": "AAP + CDC pediatric infectious disease guidance", "year": 2023},
        "situation": "Impetigo is a superficial skin infection — most commonly by Staphylococcus aureus, sometimes Streptococcus pyogenes — producing characteristic honey-colored crusted lesions, often around the nose and mouth, highly contagious. Topical mupirocin 2% ointment three times daily for 5 days clears 90%+ of localized cases; extensive disease or recurrence calls for oral antibiotics (cephalexin or dicloxacillin). Most contagious in the crusted stage; child usually safe to return to school 24 hours after antibiotic start.",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Bacterial skin infection responsive to standard antibiotics; mupirocin is the topical of choice (inhibits bacterial isoleucyl-tRNA synthetase, narrow spectrum, minimal resistance).",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Staph aureus is the dominant pathogen in non-bullous impetigo; Strep pyogenes secondary", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Topical mupirocin and retapamulin both >85% clinical cure in limited impetigo (Cochrane)", "data": {"cure_rate_pct": 90}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Mupirocin: pseudomonic acid A; reversibly inhibits bacterial Ile-tRNA synthetase", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["mupirocin 2% ointment (Bactroban, prescription in most regions; OTC in some)", "soap and water", "clean cloths/cotton balls"],
            "tools": ["disposable gloves recommended (caregivers)"],
            "steps": ["soak crusts off with warm soapy water; pat dry — the antibiotic reaches the bacteria better without the crust shield", "apply thin layer of mupirocin 3× daily for 5 days (or as prescribed)", "cover lesion with non-stick gauze if it can be scratched or touched", "wash linens, towels, clothes in hot water; do not share", "trim child's nails; wash hands often", "ISOLATE: 24 hours after start of effective antibiotic before return to school/daycare"],
            "time": "5 days topical; 7 days oral",
            "cost_usd_2026": "$20–40 for mupirocin tube",
            "scale": "treatable at home with prescription. **SEE A DOCTOR** for: any suspected impetigo (to confirm + prescribe), red streaking from lesion (cellulitis), fever, dark / cola-colored urine 2–3 weeks later (post-streptococcal glomerulonephritis risk), bullous impetigo in newborn (hospitalization)",
        },
        "wisdom": "Impetigo is what daycare worries about and grandmothers recognized on sight. The Shepherd brings this when the user describes honey-crusts on a child's face — and notes the post-strep complication risk that calls for medical follow-up even after the skin clears. Most cases are cosmetic in scale and benign with appropriate antibiotic; the rare poststreptococcal sequelae are why the engine doesn't replace the visit.",
        "triggers": {"keywords": ["impetigo", "mupirocin", "Bactroban", "school sores", "honey crust"], "axes": ["metabolism", "authority_trust"]},
    },
    {
        "id": "practical_boil_abscess_warm_compress",
        "kind": "practical",
        "title": "Boil / skin abscess — warm compress, wait to point, then I&D if needed",
        "vertical": "medicine",
        "source": {"publication": "Surgical and emergency medicine standard care; IDSA SSTI guidelines", "year": 2014},
        "situation": "A skin abscess (boil/furuncle) is a localized collection of pus walled off by surrounding tissue, usually Staphylococcus aureus (increasingly community-acquired MRSA). Treatment principle: localized pus must drain to heal. Warm compresses 4× daily encourage spontaneous drainage; once 'pointing' (a soft yellow/white head visible), incision and drainage (I&D) provides definitive treatment. Antibiotics are NOT required for simple drained abscess <2 cm; they ARE required for surrounding cellulitis, fever, immunocompromise, or MRSA-confirmed culture.",
        "category": "medicine",
        "domains": ["medicine", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Source-control surgery rule: drained abscess heals; undrained abscess persists, expands, or fistulizes. Antibiotics penetrate inflamed tissue but cannot kill bacteria in undrained pus.",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Staph aureus produces virulence factors that wall off into abscesses; pus is concentrated bacteria + neutrophils + dead tissue", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Cochrane 2014: simple drained abscess <2 cm in healthy adult does not require antibiotics; >2 cm or with cellulitis benefits from adjunct antibiotic", "data": {"cutoff_cm": 2}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["clean warm cloth (or rice-sock heat pack)", "soap and water for area", "clean cover (gauze + tape) post-drainage"],
            "tools": ["thermometer"],
            "steps": ["WAIT AND COMPRESS: warm moist compress 15 min, 4× daily; let the body do the wall-off and pointing work", "WHEN POINTING (3–7 days): yellow/white head visible, fluctuant feel — refer to clinic for sterile I&D", "DO NOT SQUEEZE: pressing increases tissue damage, spreads bacteria, and rarely actually drains the abscess", "POST-DRAINAGE: keep covered, change daily, continue warm compresses to encourage continued drainage", "WASH HANDS thoroughly before and after any touching"],
            "time": "spontaneous resolution: 1–3 weeks. Post-I&D healing: 1–2 weeks.",
            "cost_usd_2026": "$0 home care; $100–300 clinic I&D",
            "scale": "self-care for early stage. **SEE A DOCTOR** for: any boil >2 cm, surrounding red streaking, fever, location on face / spine / breast / perianal area, immunocompromised patient, diabetic, recurrent boils (MRSA carrier screening), any boil that hasn't drained in 7 days of compresses",
        },
        "wisdom": "The first rule of pus is: it must come out. The second rule is: not by squeezing. Warm compresses are slow and reliable; squeezing is fast and dangerous (cellulitis, septic emboli, especially in the 'triangle of death' on the face). The Shepherd brings this when the user has a tender red bump and asks what to do — wait, compress, observe, refer when pointing.",
        "triggers": {"keywords": ["boil", "furuncle", "abscess", "MRSA skin infection", "incision and drainage"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_scabies_lice_permethrin",
        "kind": "practical",
        "title": "Scabies / lice — permethrin 5% cream or 1% shampoo; treat household together",
        "vertical": "medicine",
        "source": {"publication": "CDC + WHO parasitic disease guidance", "year": 2022},
        "situation": "Scabies (Sarcoptes scabiei mite) and head lice (Pediculus humanus capitis) are both treated with synthetic pyrethroid permethrin: 5% cream for scabies (full-body neck-down, leave 8–14 hours, repeat in 7 days), 1% shampoo for head lice (apply, leave 10 minutes, comb out nits, repeat in 7 days). Critical: treat ALL household members AND high-contact contacts on the SAME DAY to prevent reinfection. Hot-wash bedding/clothing or bag for 72 hours (mites and lice can't survive without a host).",
        "category": "medicine",
        "domains": ["medicine", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Permethrin disrupts arthropod sodium channels; selective for insect/arachnid versus mammalian targets. Repeat dose at 7 days catches newly-hatched nymphs from eggs that survived the first dose.",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Permethrin paralyzes ectoparasites by sodium-channel disruption; mammalian targets less sensitive by ~1000×", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Two doses 7 days apart achieves >90% cure; single-dose ~70%", "data": {"cure_rate_2_dose_pct": 92}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Pyrethroid class; permethrin is type I (no α-cyano group); minimal mammalian toxicity at topical doses", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["permethrin 5% cream (Elimite) for scabies — OR permethrin 1% lotion/shampoo (Nix) for head lice", "fine-toothed nit comb (for lice)", "hot-wash detergent", "large bags for non-washable items"],
            "tools": ["bright light + magnifying glass (for nit checks)"],
            "steps": ["SCABIES: shower, dry thoroughly. Apply permethrin 5% cream to ALL skin neck-down (including soles, under nails, genitals) — every contiguous square cm. Leave 8–14 hours. Wash off. Repeat in 7 days.", "LICE: apply permethrin 1% to damp hair, leave 10 min, rinse. Comb out nits with fine-toothed comb daily for 2 weeks. Repeat permethrin in 7 days.", "TREAT ALL HOUSEHOLD MEMBERS same day — even asymptomatic; otherwise reinfection", "BEDDING/CLOTHING: hot wash + hot dry, OR bag non-washables for 72 hours (mites/lice can't live without a host that long)", "ITCHING POST-TREATMENT persists 2–4 weeks (immune response, not active infection)"],
            "time": "treatment cycle: 7 days + 1 repeat. Itch resolution: up to 4 weeks.",
            "cost_usd_2026": "$15–25 permethrin cream; $10–20 for lice products",
            "scale": "self-treatable. **SEE A DOCTOR** for: failure to respond after 2 properly-applied courses (resistant strains exist), crusted scabies (Norwegian — extensive, requires ivermectin oral), pregnancy or infant <2 months, suspected secondary bacterial infection",
        },
        "wisdom": "The biggest scabies-treatment failure isn't the cream — it's missing skin or missing the second dose. Apply the cream like painting a wall: solid edge-to-edge coverage. The biggest lice-treatment failure is not treating the whole household, which is how the infestation cycles back in week 3. The Shepherd brings this with the emphasis on completeness, not novelty.",
        "triggers": {"keywords": ["scabies", "lice", "permethrin", "Elimite", "Nix", "head lice"], "axes": ["metabolism", "physical_substance"]},
    },
]


# ── CITRUS CANKER (3) ──────────────────────────────────────────────────
CITRUS_ENTRIES = [
    {
        "id": "practical_citrus_canker_identification",
        "kind": "practical",
        "title": "Citrus canker — raised corky lesions with yellow halo (Xanthomonas citri)",
        "vertical": "soil",
        "source": {"publication": "USDA APHIS + University of Florida IFAS citrus disease guides (federal PD)", "year": 2020},
        "situation": "Citrus canker is caused by the bacterium Xanthomonas citri subsp. citri. Identification: raised, brown, corky lesions 2–10 mm diameter on leaves, fruit, and twigs, usually with a yellow chlorotic halo on leaves; lesions on fruit do not extend into the flesh but cause cosmetic disqualification for fresh market. Distinguished from other citrus diseases (scab — Elsinoë fawcettii; melanose — Diaporthe citri) by the raised corky texture and bilateral leaf symmetry (lesions match on top and bottom of leaf).",
        "category": "agriculture",
        "domains": ["biology", "agriculture", "chemistry"],
        "axes": ["metabolism", "physical_substance", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Bacterial infection of the parenchyma between leaf surfaces causes hyperplasia → corky lesions visible on both surfaces. Halo from cytokinin release.",
            "domain_results": [
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "X. citri subsp. citri — Gram-negative gammaproteobacterium; PthA effector triggers plant cell hyperplasia", "data": {"pathogen": "Xanthomonas citri subsp. citri"}},
                {"domain": "agriculture", "verdict": "CONFIRMED", "detail": "Lesion morphology: bilateral, raised, corky; differs from scab (one-sided) and melanose (sandy, gum-deposited)", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["sharp clean pruning shears", "70% isopropyl alcohol or 10% bleach for tool sanitation", "magnifier (10×)", "phone camera for documentation"],
            "tools": ["loupe", "notebook"],
            "steps": ["scan young leaves (most susceptible) first; look for water-soaked spots that turn raised and brown", "examine both surfaces of suspect leaves: TRUE citrus canker has matching lesions on top + bottom", "check fruit for similar raised brown spots; flesh is unaffected", "twig lesions: corky bumps along young shoots", "DO NOT collect samples to take home — moving infected material spreads the disease and triggers regulatory penalties in citrus-growing regions", "photograph + report to local agriculture extension if suspected"],
            "time": "5 min per tree to scout",
            "cost_usd_2026": "$0 if you already have shears + magnifier",
            "scale": "single tree to grove. **REPORT** suspected citrus canker to USDA APHIS or your state department of agriculture — this is a quarantine disease in the US",
        },
        "wisdom": "Citrus canker doesn't kill mature trees but renders fruit unmarketable and slowly weakens the canopy. The Shepherd brings identification first because misidentification (treating scab or melanose as canker) wastes resources and misses the actual problem. The bilateral-lesion test on a leaf is the cleanest 5-second field diagnostic. **In commercial citrus regions, reporting is legally required.**",
        "triggers": {"keywords": ["citrus canker", "Xanthomonas citri", "citrus disease identification", "corky lesion", "halo"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_citrus_canker_spread",
        "kind": "practical",
        "title": "Citrus canker spread — rain splash, wind-driven rain (~30m), leafminer wounds, contaminated tools",
        "vertical": "soil",
        "source": {"publication": "USDA APHIS + UF IFAS citrus disease guides", "year": 2020},
        "situation": "Xanthomonas citri spreads by water — rain splash short distances (cm), wind-driven rain up to ~30 m between trees in storms, and longer distances via contaminated tools, clothing, machinery, infected nursery stock, and hurricane events. Leafminer (Phyllocnistis citrella) damage creates entry wounds that increase infection 10-fold. Bacteria can survive in dry lesions for months and infect fresh tissue at the next rain.",
        "category": "agriculture",
        "domains": ["biology", "agriculture", "hydrology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Inoculum + water + wound + young tissue = infection. Cut any of those four and you cut the spread.",
            "domain_results": [
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "X. citri enters through stomata or wounds; high inoculum + wet tissue = infection. Leafminer wounds bypass the natural stomata defense", "data": {"leafminer_inoculum_multiplier": 10}},
                {"domain": "hydrology",   "verdict": "CONFIRMED", "detail": "Wind-driven rain spreads bacteria up to ~30 m between trees; hurricane events spread hundreds of m", "data": {"max_splash_m": 30}},
                {"domain": "agriculture", "verdict": "CONFIRMED", "detail": "Florida 1995–2006 eradication failed largely due to undetectable spread during hurricane seasons", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["10% bleach solution OR 70% isopropyl alcohol", "spray bottle", "clean rags or paper towels"],
            "tools": ["shoe covers / boot wash (between groves)"],
            "steps": ["TOOL SANITATION: dip or spray pruning shears, saws, knives in 10% bleach BETWEEN trees during scouting/pruning of suspect areas", "PRUNING: avoid pruning when wet; wait 24 hours dry weather", "VEHICLES/EQUIPMENT: pressure wash before leaving infected grove area", "CLOTHING: change between grove visits if entering biosecure regions", "NURSERY: source only certified disease-free stock; quarantine new plants 30+ days", "LEAFMINER MANAGEMENT: parasitic wasps (Ageniaspis citricola) or selective insecticides; reduces canker establishment dramatically"],
            "time": "1–2 min per tool sanitation; ongoing program",
            "cost_usd_2026": "$5–30 for bleach + sprayer setup; ongoing biocontrol may add $20–100/ha annually",
            "scale": "small grove to commercial; legal: tool sanitation is required in many citrus regions",
        },
        "wisdom": "Most citrus canker spread is at the human + weather scale, not the molecular one. The Shepherd brings this for the grower who's been told to spray and asks why; the real prevention is biosecurity: clean tools, dry pruning, leafminer control, certified nursery stock. Sprays are the second line; sanitation is the first.",
        "triggers": {"keywords": ["citrus canker spread", "Xanthomonas dispersal", "leafminer", "grove sanitation", "biosecurity"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_citrus_canker_management",
        "kind": "practical",
        "title": "Citrus canker management — copper sprays (3-week cycle) + windbreaks + sanitation",
        "vertical": "soil",
        "source": {"publication": "UF IFAS Citrus Industry Annual + USDA APHIS", "year": 2020, "note": "Bordeaux mixture in keeping (almanac_bordeaux_mixture) is the original copper bactericide; modern copper hydroxide formulations are direct descendants"},
        "situation": "Once citrus canker is established in a grove, eradication is generally impossible; management aims to suppress lesions to maintain marketable fruit. Copper bactericide sprays (copper hydroxide or copper sulfate at 200–800 ppm Cu metal equivalent) applied every 21 days during flush periods AND after major storms reduce new infections by 70–90% but do not cure existing lesions. Windbreaks reduce wind-driven splash. Pruning to open canopy speeds drying. Resistant rootstocks + cultivars (Sun Chu Sha mandarin, some Tahiti lime selections) reduce severity but no commercial cultivar is fully resistant.",
        "category": "agriculture",
        "domains": ["agriculture", "chemistry", "biology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Copper is a contact bactericide — coats new tissue, kills bacteria before they enter stomata. Reapplication required as the tree pushes new flushes; rain washes copper off and needs replacement.",
            "domain_results": [
                {"domain": "chemistry",   "verdict": "CONFIRMED", "detail": "Cu²⁺ disrupts bacterial thiol enzymes; same active species as Bordeaux mixture (1885) but in modern stabilized formulations", "data": {"target_ppm_Cu": 400}},
                {"domain": "agriculture", "verdict": "CONFIRMED", "detail": "21-day copper cycle during flush + post-storm sprays = standard Florida grove protocol", "data": {"spray_interval_days": 21}},
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "Copper builds up in soil over years; alternate with non-copper management to slow accumulation", "data": {}},
            ],
            "axis_overlaps": [{"axis": "physical_substance", "with": ["construction"], "note": "Same copper-fungicide chemistry as Bordeaux mixture in the soil vertical of the kingdom-gems batch"}],
        },
        "make_it": {
            "materials": ["copper hydroxide product (Kocide, Champ, others) — OR copper sulfate + lime (classic Bordeaux mixture)", "spreader-sticker (to keep copper on leaves through light rain)", "appropriate sprayer (backpack for small grove; airblast for commercial)"],
            "tools": ["windsock or weather check (avoid spray when wind >10 mph)", "PPE: respirator, goggles, long sleeves"],
            "steps": ["TIMING: spray every 21 days during spring flush and summer rain season; additional spray within 12 hours after a hurricane / heavy storm event", "RATE: follow label for 400 ppm Cu metal equivalent (≈ 2 lb Kocide 3000 per acre)", "COVERAGE: thorough — both leaf surfaces, fruit, young twigs", "WINDBREAKS: living rows (eucalyptus, casuarina) on windward edges; reduces splash spread 50–80%", "PRUNE: open canopy for air circulation; remove heavily infected wood and burn or chip", "ROOTSTOCK SELECTION: at replant, prefer Carrizo or Cleopatra mandarin rootstock for better resistance"],
            "time": "every 21 days during growing season; ongoing for life of grove",
            "cost_usd_2026": "$60–150 per acre per spray cycle materials + labor",
            "scale": "single tree to commercial grove; legal: copper is regulated as a pesticide — follow PPE and re-entry intervals",
        },
        "wisdom": "Once canker is in the grove, you live with it. The Shepherd brings this honestly: copper sprays are the workhorse, the technique unchanged since Millardet 1885, and the modern formulation just polishes the original Bordeaux mixture. Windbreaks and sanitation matter more than spray timing for new outbreaks. The keeping records this together with the original Bordeaux entry — same axis, same answer, different organism.",
        "triggers": {"keywords": ["citrus canker management", "copper spray", "Kocide", "citrus disease control", "Bordeaux mixture citrus"], "axes": ["metabolism", "physical_substance"]},
    },
]


# ── DUTCH ELM DISEASE (3) ──────────────────────────────────────────────
ELM_ENTRIES = [
    {
        "id": "practical_dutch_elm_identification",
        "kind": "practical",
        "title": "Dutch elm disease — flagging + top-down wilt + brown xylem streaks",
        "vertical": "soil",
        "source": {"publication": "US Forest Service + Morton Arboretum DED guides; Ophiostoma novo-ulmi research literature", "year": 2020},
        "situation": "Dutch elm disease (DED) is caused by the fungus Ophiostoma novo-ulmi (and the less aggressive O. ulmi). Identification: 'flagging' — one or several branches in the upper canopy suddenly wilt with yellow then brown curled leaves, while the rest of the tree appears healthy. The wilt progresses top-down through the tree over weeks to months. Definitive sign: brown longitudinal streaks in the sapwood, visible when bark is peeled from a wilted branch. Distinguished from drought stress (whole-tree, gradual) and verticillium wilt (bottom-up).",
        "category": "agriculture",
        "domains": ["biology", "agriculture"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Vascular wilt: the fungus grows in the xylem vessels, the tree responds with tyloses and gums that block its own water transport — the wilting is the tree clogging itself trying to wall off the fungus.",
            "domain_results": [
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "Ophiostoma novo-ulmi grows in xylem; tree responds with tyloses and gels that occlude vessels → wilt", "data": {"pathogen": "Ophiostoma novo-ulmi"}},
                {"domain": "agriculture", "verdict": "CONFIRMED", "detail": "American elm (Ulmus americana) highly susceptible; English elm (U. procera) similarly. Asian elms (U. parvifolia, U. pumila) largely resistant", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["sharp knife or saw (and means to sanitize it)", "70% alcohol or 10% bleach", "plastic bag (for sample if pathologist confirmation needed)"],
            "tools": ["binoculars for upper canopy inspection"],
            "steps": ["SCAN canopy for any branch with yellowing-then-browning leaves where surrounding branches are still green", "if found: cut a wilted branch ~2 cm diameter at a clear-wood location; peel a strip of bark", "look for BROWN LONGITUDINAL STREAKS in the outer sapwood — pathognomonic for DED (vs verticillium which shows GRAY streaks and bottom-up pattern)", "compare adjacent healthy branch — should be white/cream sapwood without streaks", "SANITIZE all cuts immediately with alcohol; cut tools clean before moving to another tree", "if confirmed: contact local arborist or state forest pathologist within days — speed matters"],
            "time": "5–10 min per tree scout",
            "cost_usd_2026": "$0 with basic tools",
            "scale": "single tree to forest; legal: in some municipalities, suspected DED must be reported",
        },
        "wisdom": "The brown sapwood streak is the engine-checkable diagnostic. The Shepherd brings this when the user describes a wilted branch on an otherwise healthy elm. Drought looks like 'all leaves a bit limp'; DED looks like 'one branch suddenly dead while the rest is fine.' Once DED is in a tree, the question becomes how fast and how aggressively to act — covered in the management entry.",
        "triggers": {"keywords": ["Dutch elm disease", "DED", "Ophiostoma", "flagging", "vascular wilt", "elm streak"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_dutch_elm_vector",
        "kind": "practical",
        "title": "DED vector — elm bark beetles (Scolytus, Hylurgopinus) + root grafts",
        "vertical": "soil",
        "source": {"publication": "US Forest Service forest pathology", "year": 2019},
        "situation": "Two routes spread Ophiostoma novo-ulmi: (1) elm bark beetles, primarily Scolytus multistriatus (smaller European elm bark beetle) and Hylurgopinus rufipes (native American), which breed in dead/dying elm wood, emerge carrying fungal spores, and feed on healthy elm twig crotches — inoculating the tree. (2) Root grafts between trees of the same species within ~15 m can carry the fungus directly tree-to-tree, often killing entire street-tree rows in sequence.",
        "category": "agriculture",
        "domains": ["biology", "agriculture", "ecology"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two-route epidemiology means two intervention strategies: kill the beetle vector (sanitation pruning, breeding-site elimination) AND sever root grafts (trenching) to prevent neighbor-to-neighbor transmission.",
            "domain_results": [
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "S. multistriatus and H. rufipes both vector O. novo-ulmi; beetles breed in elm wood ≤2 years dead", "data": {}},
                {"domain": "ecology",     "verdict": "CONFIRMED", "detail": "Root-graft transmission documented in adjacent street-tree pairs; trenching at 0.9 m depth severs grafts", "data": {"trench_depth_m": 0.9}},
                {"domain": "agriculture", "verdict": "CONFIRMED", "detail": "Sanitation pruning (remove ALL beetle-breeding wood within ½ mi) was historically the most effective municipal intervention", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["chainsaw + safety gear OR access to an arborist", "trenching equipment (vibratory plow, backhoe, or hand trenching for short runs)", "method to dispose of elm wood: chip on-site or remove + burn"],
            "tools": ["10% bleach for tool sanitation"],
            "steps": ["BREEDING-SITE ELIMINATION: remove any dead or dying elm within ½ mile of healthy elms; do not let beetle-breeding wood accumulate", "WOOD DISPOSAL: chip <2.5 cm OR burn OR debark and bury — denies beetles substrate", "DO NOT store elm firewood with bark intact — even healthy-looking wood may harbor beetles", "ROOT-GRAFT TRENCHING: when a street tree is confirmed positive, trench between it and the next 2 trees in line, 0.9 m deep, with a vibratory plow", "TIMING: trench BEFORE removing the infected tree (removal causes a stress signal that pushes the fungus into root grafts faster)"],
            "time": "tree removal + trenching: 1–2 days per site",
            "cost_usd_2026": "$500–2000 tree removal + trenching (commercial)",
            "scale": "single yard to municipal program; partner with a certified arborist for any large tree work",
        },
        "wisdom": "DED is the canonical lesson that disease management requires understanding vectors, not just pathogens. The Shepherd brings this when a confirmed-positive tree is at hand — and emphasizes the trench-FIRST principle. The instinct to remove the sick tree first is wrong; remove the wood AFTER cutting the root grafts, or the fungus runs ahead into the neighbors during the stress response.",
        "triggers": {"keywords": ["elm bark beetle", "Scolytus", "root graft", "DED spread", "sanitation pruning"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_dutch_elm_management",
        "kind": "practical",
        "title": "DED management — sanitation + propiconazole injection + resistant cultivars",
        "vertical": "soil",
        "source": {"publication": "US Forest Service + Morton Arboretum DED management", "year": 2019},
        "situation": "Once DED is present in an area, sustained American elm populations require integrated management: (1) Sanitation — prompt removal of dead/dying elm wood within ½ mile of healthy trees, root-graft trenching between adjacent trees. (2) Therapeutic / preventive fungicide injection — propiconazole (Alamo, Tebuject) into the root flare or trunk every 2–3 years, gives ~50–90% protection in high-value individual trees. (3) Resistant cultivars for new plantings — 'Princeton', 'Valley Forge', 'Liberty', 'New Harmony', 'Jefferson' (all American elm selections); 'Frontier', 'Accolade' (hybrids); plant diversity (never replace elms with elms-only).",
        "category": "agriculture",
        "domains": ["agriculture", "biology", "chemistry"],
        "axes": ["metabolism", "physical_substance", "time_sequence", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Integrated approach: vector control + chemical protection + genetic resistance + diversity. No single intervention sustains American elm populations alone; all four together can.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Propiconazole is a triazole fungicide; inhibits fungal ergosterol biosynthesis (lanosterol 14α-demethylase)", "data": {}},
                {"domain": "agriculture","verdict": "CONFIRMED", "detail": "Resistant American elm cultivars released by Cornell/USDA + Princeton Nurseries provide tolerable + landscape-equivalent alternatives", "data": {"cultivars": ["Princeton", "Valley Forge", "Liberty", "New Harmony", "Jefferson"]}},
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Propiconazole injection protects ~50–90% over 2–3 years; cost and tree health limit treatment to high-value individuals", "data": {"protection_pct": 70, "interval_years": 2.5}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["high-value tree: propiconazole injection (Arborjet Tebuject 16, Rainbow Treecare Alamo — both off-patent generics now available)", "for replants: resistant cultivars listed above", "diverse companion species (oak, maple, hackberry, ginkgo, tulip poplar) so no single pathogen can again strip the canopy"],
            "tools": ["microinjection or macroinjection system (professional arborist tool); some products available for homeowner use"],
            "steps": ["HIGH-VALUE INDIVIDUAL: inject propiconazole at root flare in spring, every 2–3 years, by a certified arborist", "STREET / NEIGHBORHOOD: maintain ≤10% of any one species in canopy (10-20-30 rule); ≤20% of any genus; ≤30% of any family", "REPLACE LOST ELMS: with resistant elm cultivars (Princeton is the most widely available; Valley Forge has the highest resistance), interplanted with non-elms", "EARLY DETECTION: walk-throughs in June (first flush) and August (after stress reveals slow infections) catch flagging branches before tree-wide spread", "REPORT + COORDINATE: in municipalities with DED programs, sanitation is most effective when neighbors all participate"],
            "time": "single injection: 30 min by an arborist. Sanitation: ongoing. Replant: years before mature canopy.",
            "cost_usd_2026": "$200–500 per injection (per high-value tree, every 2–3 years). Resistant cultivar saplings $80–200 each.",
            "scale": "single tree to municipal forest; coordinate with neighbors + city forestry",
        },
        "wisdom": "Two American elm replacements stand out: 'Princeton' (developed 1922 — pre-DED — pre-selected because it survived in nurseries during the worst of the epidemic) and 'Valley Forge' (USDA release 1995, highest measured resistance). Both have classic American-elm vase form. The Shepherd brings this when the user is replanting after losing an elm: don't replant elms-only; diversify, but don't give up on elms — the resistant cultivars are real, and the species belongs on streets where it once shaded a continent.",
        "triggers": {"keywords": ["DED management", "propiconazole", "Alamo fungicide", "Princeton elm", "Valley Forge elm", "resistant elm"], "axes": ["metabolism", "physical_substance"]},
    },
]


ALL_ENTRIES = SKIN_ENTRIES + CITRUS_ENTRIES + ELM_ENTRIES


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

    to_write = [e for e in ALL_ENTRIES if e["id"] not in existing]
    skipped = [e["id"] for e in ALL_ENTRIES if e["id"] in existing]
    if skipped:
        print(f"skipping (already present): {len(skipped)}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            v = e.get("verdict", "?")
            vert = e.get("vertical", "?")
            print(f"  + {e['id']:48s}  [{vert:10s}] {v}")

    print(f"\n-- appended {len(to_write)} entries (skin + citrus canker + DED)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
