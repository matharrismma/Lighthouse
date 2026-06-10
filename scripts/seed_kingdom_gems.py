#!/usr/bin/env python
"""Seed 30 "kingdom gems" into the almanac — PD-clean, small-scale-reproducible,
high-life-impact patents and designs across 9 verticals.

Each entry carries:
  - `kind: "patent"` (new) — distinguishes from saying/protocol/almanac
  - `patent: {...}` — number (where confirmed), inventor, filed/expired, office
  - `situation` — a verifier-anchored claim the engine can score
  - `pre_run.domain_results[]` — what the verifiers WOULD say
  - `make_it: {materials, tools, steps, time, cost_usd_2026, scale}` —
    the reproducibility block, new with this batch
  - `wisdom` — Shepherd voice; ties to kingdom-economy posture
  - `triggers` — keyword + axis routing

Verticals (9):
  water, food_preservation, soil, medicine, energy, shelter,
  communication, hand_tools, sanitation

Notes on honesty:
  - Where a patent number is confirmed historical, it's cited.
  - Where a technology predates patents (Roman lime, fermentation, slow sand
    filtration), `patent.kind = "pd_by_age"` and number is null.
  - Where many overlapping expired patents exist (solar still, rocket stove),
    `patent.kind = "patent_family"` with the canonical originator.
  - Items with legal-use caveats (transmitting antennas, antibiotic production)
    are flagged in wisdom — knowledge is PD, certain *uses* still need
    licensing or are unsafe at amateur scale.

After running this script, restart the API server so the almanac re-reads
data/almanac/entries.jsonl.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


# ── 1 ─ WATER ─────────────────────────────────────────────────────────
ENTRIES_WATER = [
    {
        "id": "patent_slow_sand_filter",
        "kind": "patent",
        "title": "Slow sand filter — biological water purification (Paisley, 1804)",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "John Gibb (Paisley, Scotland)", "year": 1804, "office": None},
        "vertical": "water",
        "situation": "A bed of 0.15–0.30 mm fine sand 60–120 cm deep, fed water at 0.1–0.4 m/hr surface loading, develops a biological 'schmutzdecke' (1–2 cm gelatinous layer) on top that removes 99%+ of bacteria and turbidity by combined filtration + biofilm predation.",
        "category": "agriculture",
        "domains": ["hydrology", "biology", "chemistry"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Mechanically simple. Biological mechanism is the active filter; sand is only the substrate.",
            "domain_results": [
                {"domain": "hydrology", "verdict": "CONFIRMED", "detail": "0.1–0.4 m/hr surface loading is the validated design range (WHO, 1996)", "data": {"loading_rate_m_per_hr": 0.2}},
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "schmutzdecke removes E. coli at >2 log (99%) reliably; >4 log (99.99%) when mature", "data": {"log_reduction_e_coli": 2.0}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["clean sand 0.15–0.30 mm", "gravel underdrain 5–15 mm", "container (drum, tank, or built basin)", "outlet pipe with control valve"],
            "tools": ["sieve to grade sand", "shovel"],
            "steps": ["wash sand until rinse runs clear", "place gravel underdrain 10 cm deep", "place sand 80 cm deep on top", "fill from below with clean water to wet bed", "introduce raw water to 5 cm above sand", "run continuously at 0.2 m/hr; harvest filtered water from outlet", "after 2–6 weeks, schmutzdecke matures and pathogen removal jumps"],
            "time": "build: 1 day. maturation: 2–6 weeks before drinkable.",
            "cost_usd_2026": "$30–$80 for a household unit (drum + sand + plumbing)",
            "scale": "household to village; no electricity required",
        },
        "wisdom": "The schmutzdecke is the actual filter; the sand is just the bed. This is the oldest municipal-scale water treatment in continuous use — Paisley 1804, London 1829, still running in dozens of cities. The Shepherd brings this when the user asks about water without grid: it works without power, without consumables (no replaceable cartridges), without chemistry, and it scales from a 55-gallon drum to a city.",
        "triggers": {"keywords": ["slow sand filter", "water purification", "schmutzdecke", "biofilm filtration", "off-grid water"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_solar_still_single_effect",
        "kind": "patent",
        "title": "Solar still — single-effect (Telkes / Bjorksten, 1950s)",
        "patent": {"kind": "patent_family", "number": "US 2,490,659 (Telkes 1949, expired)", "inventor": "Maria Telkes et al.", "year": 1949, "office": "USPTO"},
        "vertical": "water",
        "situation": "A black-bottomed shallow water pan under a sloped transparent cover. Solar input evaporates water; vapor condenses on the cooler cover and runs down to a collection trough. At 6 kWh/m²/day insolation, single-effect yield is 3–4 L of distilled water per m² per day.",
        "category": "energy",
        "domains": ["thermodynamics", "physics", "hydrology"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Energy balance: 1 L water requires 2257 kJ latent heat at 100°C (less at lower T). At 6 kWh/m²/day = 21,600 kJ, with ~40% net thermal efficiency to evaporation, yield ≈ 3.8 L/m²/day.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "L_v(H2O) at 25°C = 2442 kJ/kg; 21.6 MJ × 0.40 / 2442 ≈ 3.5 L/m²/day", "data": {"insolation_MJ_per_m2_day": 21.6, "eta": 0.40, "L_v_kJ_per_kg": 2442, "yield_L_per_m2_day": 3.5}},
            ],
            "axis_overlaps": [{"axis": "conservation_balance", "with": ["energy"], "note": "First-law energy balance is the design constraint"}],
        },
        "make_it": {
            "materials": ["shallow black pan or basin liner", "glass or clear plastic sheet (4–6mm, sloped)", "frame (wood / metal)", "collection trough (gutter or PVC half-pipe)", "sealant"],
            "tools": ["saw", "drill", "sealant gun"],
            "steps": ["build insulated box, paint inside black", "fill pan with 2–3 cm of raw/salt/brackish water", "set glass cover at 10–30° slope so condensate runs to a trough", "seal joints to prevent vapor escape", "harvest from trough; refill pan as needed"],
            "time": "1–2 days build",
            "cost_usd_2026": "$40–$150 per m²",
            "scale": "household; multiple panels for a family",
        },
        "wisdom": "The single most important off-grid water tool for brackish / saline / contaminated supplies — the still doesn't filter, it distills. Everything in the input except pure water stays in the pan. Works on seawater, urine, swamp water, runoff. Energy is free; the only consumable is the pan getting scaled with whatever was dissolved. The Shepherd brings this when the source water is bad, not just murky.",
        "triggers": {"keywords": ["solar still", "distillation", "desalination", "off-grid water", "Telkes"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_chlorination_dose_math",
        "kind": "patent",
        "title": "Chlorination dosing — free chlorine residual ≥0.5 mg/L for safe water",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "Sims Woodhead (1897) / Major Carl Darnall (1910, US Army)", "year": 1910, "office": None},
        "vertical": "water",
        "situation": "Adding sodium hypochlorite (NaClO) to water at 2 mg/L active chlorine for 30 minutes contact time, holding a free chlorine residual of ≥0.5 mg/L, inactivates >99.99% of bacteria, viruses, and Giardia cysts. NaClO + H₂O ⇌ HClO + NaOH; HClO is the active germicide.",
        "category": "medicine",
        "domains": ["chemistry", "biology", "medicine"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "WHO CT (concentration × time) values: free chlorine at 0.5 mg/L × 30 min achieves 4-log inactivation of bacteria and viruses at pH 6–8, T ≥ 5°C.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "NaClO hydrolysis to HClO is pH-dependent; at pH 7, ~75% is HClO", "data": {"pH": 7, "hclo_fraction": 0.75}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "WHO drinking-water guideline: ≥0.5 mg/L free chlorine residual after 30 min contact", "data": {"residual_mg_per_L": 0.5, "contact_min": 30}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["unscented household bleach (5.25% NaClO) OR calcium hypochlorite tablets", "clean container"],
            "tools": ["dropper or syringe for dosing", "free-chlorine test strips ($0.10 each)"],
            "steps": ["measure water volume", "add 2 drops of 5.25% bleach per liter of clear water (4 drops if cloudy)", "stir, wait 30 minutes", "test with strip; should read ≥0.5 mg/L free chlorine", "if no residual after 30 min, double the dose and repeat"],
            "time": "30 minutes contact",
            "cost_usd_2026": "<$0.005 per liter treated",
            "scale": "individual to community",
        },
        "wisdom": "The cheapest, most-tested, most-deployed water disinfection in history — Major Darnall's 1910 work pulled chlorination from theory into universal practice and dropped waterborne disease mortality by orders of magnitude. The Shepherd brings this when the water is clear but suspect; pair with a sand filter if the water is also cloudy (chlorine doesn't penetrate turbidity well).",
        "triggers": {"keywords": ["chlorination", "bleach water", "hypochlorite", "water disinfection", "free chlorine residual"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_pasteurization",
        "kind": "patent",
        "title": "Pasteurization — heat-only pathogen kill (Pasteur, 1864)",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "Louis Pasteur", "year": 1864, "office": None},
        "vertical": "water",
        "situation": "Heating liquid food (milk, juice, water) to 63°C for 30 minutes (LTLT, vat) OR 72°C for 15 seconds (HTST, flash) inactivates vegetative bacterial pathogens including Salmonella, Listeria, E. coli, and Mycobacterium bovis to log-5+ reduction, without sterilizing (spores survive).",
        "category": "medicine",
        "domains": ["biology", "chemistry", "medicine"],
        "axes": ["metabolism", "time_sequence", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Time-temperature inactivation; D-value (decimal reduction time) for M. bovis at 63°C ≈ 5 minutes, so 30 min ≈ 6 log kill.",
            "domain_results": [
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "M. bovis pasteurization kinetics: D₆₃ ≈ 5 min; 30 min ≈ 6-log inactivation", "data": {"T_C": 63, "time_min": 30, "log_kill": 6}},
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Protein denaturation kinetics follow Arrhenius below boiling", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["liquid to pasteurize", "pot deep enough for water bath"],
            "tools": ["thermometer accurate ±1°C", "stove or fire", "timer"],
            "steps": ["put liquid in clean jars or container", "place in water bath", "heat to 63°C and hold 30 min (or 72°C × 15 sec for skilled operators)", "cool quickly to <4°C", "store cold"],
            "time": "45 min total per batch",
            "cost_usd_2026": "$0 (you already have the pot)",
            "scale": "household; commercial pasteurizers scale to thousands of liters",
        },
        "wisdom": "Pasteurization is not sterilization. Spore-formers (Clostridium, Bacillus) survive — that's why pasteurized milk still spoils, just slowly. The Shepherd uses this when the goal is *safe* not *eternal*: raw milk from a known cow becomes safe milk that keeps a week refrigerated. For shelf-stable, you need canning (separate gem).",
        "triggers": {"keywords": ["pasteurization", "milk safety", "Pasteur", "LTLT", "HTST", "vat pasteurization"], "axes": ["metabolism", "time_sequence"]},
    },
]


# ── 2 ─ FOOD PRESERVATION ─────────────────────────────────────────────
ENTRIES_FOOD = [
    {
        "id": "patent_mason_jar_canning",
        "kind": "patent",
        "title": "Mason jar home canning — US 22,186 (1858)",
        "patent": {"kind": "patent", "number": "US 22,186", "inventor": "John Landis Mason", "year": 1858, "office": "USPTO"},
        "vertical": "food_preservation",
        "situation": "Boiling-water-bath canning of high-acid food (pH ≤ 4.6) in a Mason-style glass jar with metal lid + rubber seal, processed at 100°C for 10–40 minutes (depending on jar size and food), produces shelf-stable food because heat kills vegetative pathogens and the cooling-vapor pressure differential creates a vacuum seal that prevents recontamination.",
        "category": "agriculture",
        "domains": ["biology", "chemistry", "agriculture", "nutrition"],
        "axes": ["physical_substance", "metabolism", "conservation_balance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Acid (pH ≤ 4.6) excludes C. botulinum; boiling kills the rest. Vacuum seal forms on cooling because internal water vapor (10–101 kPa) condenses and external atmosphere (101 kPa) compresses the lid.",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Vegetative pathogens inactivated at 100°C × 10+ min; C. botulinum requires pH ≤ 4.6 OR pressure canning (≥ 240°F / 116°C)", "data": {"safe_pH_max": 4.6, "T_C": 100}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Vacuum forms from vapor-pressure differential P_atm − P_vapor at cooled T", "data": {"P_atm_kPa": 101, "P_vapor_at_25C_kPa": 3.2}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["Mason jars with two-piece lids", "the food (pH ≤ 4.6: tomatoes, fruit, pickles, jams)", "water"],
            "tools": ["large pot deep enough to cover jars by 2.5 cm", "jar lifter", "thermometer (optional)"],
            "steps": ["sterilize jars in boiling water 10 min", "fill jars with hot food, leave 1.25 cm headspace", "wipe rim clean, apply lid finger-tight", "submerge in boiling water 10–40 min by recipe", "lift out, set on towel to cool", "lid should *ping* concave within an hour — that's the seal", "any jar that doesn't seal, refrigerate and use within 1 week"],
            "time": "30–90 min per batch",
            "cost_usd_2026": "$1.50 per jar amortized over many seasons (lids replace; jars don't)",
            "scale": "kitchen counter; 7 quart jars per batch typical",
        },
        "wisdom": "Conservation balance applied to time sequence. The Mason jar design is unchanged in 168 years because the physics doesn't drift: vapor pressure, atmospheric pressure, the same rubber seal principle. Low-acid foods (meat, beans, vegetables not pickled) need pressure canning — boiling-water bath alone is NOT safe for them; botulism is the failure mode. The Shepherd refuses to recommend boiling-bath canning for low-acid foods.",
        "triggers": {"keywords": ["canning", "Mason jar", "boiling water bath", "preserving", "shelf-stable food", "vacuum seal"], "axes": ["conservation_balance", "metabolism", "time_sequence"]},
    },
    {
        "id": "patent_lactic_fermentation",
        "kind": "patent",
        "title": "Lactic-acid fermentation — sauerkraut/kimchi/pickle preservation",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "predates record (likely Neolithic)", "year": None, "office": None},
        "vertical": "food_preservation",
        "situation": "Vegetables submerged in 2–3% salt brine under anaerobic conditions: Leuconostoc mesenteroides ferments sugars first, dropping pH; Lactobacillus plantarum takes over below pH 4.5 and continues to pH 3.4. Below pH 4.0 most pathogens cannot grow; vitamin C is preserved or increased.",
        "category": "agriculture",
        "domains": ["biology", "chemistry", "nutrition", "agriculture"],
        "axes": ["metabolism", "time_sequence", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Salt selects against putrefactive bacteria; LAB tolerate salt; their lactic-acid byproduct progressively lowers pH; below pH 4.0 the system becomes self-sterilizing.",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Two-stage LAB succession (Leuconostoc → Lactobacillus) is the canonical sauerkraut microbiology", "data": {"final_pH": 3.5}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "C₆H₁₂O₆ → 2 C₃H₆O₃ (homolactic) — atoms balance", "data": {"pathway": "homolactic"}},
                {"domain": "nutrition","verdict": "CONFIRMED", "detail": "Vitamin C preserved; B-vitamins increased by LAB synthesis", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["cabbage / cucumbers / mixed vegetables", "sea salt (non-iodized, 2–3% by weight)", "water if making brine pickles", "clean glass jar or crock"],
            "tools": ["weight to keep vegetables submerged (smaller jar of water works)", "loose lid or airlock"],
            "steps": ["shred or chop vegetables", "salt to 2% by weight (20g salt per kg veg) for kraut, or make 3% brine for cucumbers", "pack tightly in jar, releasing juice", "submerge all solids below liquid surface — exposure to air = mold", "loose lid (allow CO₂ out) at 18–22°C", "taste at day 3, 7, 14 — ready when sour enough", "move to cold storage to slow fermentation"],
            "time": "build: 15 min. fermentation: 1–6 weeks.",
            "cost_usd_2026": "<$0.50 per kg (salt + jar amortized)",
            "scale": "single jar to barrels",
        },
        "wisdom": "The microbes are the technology; you are only the substrate engineer. Salt + anaerobic = the niche LAB own; competitors lose. This is the only major preservation method that *adds* nutrition rather than removing it — B-vitamins, K2, probiotics all appear from the fermentation. The Shepherd brings this when the user has more vegetables than they can eat now and no refrigeration.",
        "triggers": {"keywords": ["fermentation", "sauerkraut", "kimchi", "lacto-fermentation", "pickling", "Lactobacillus"], "axes": ["metabolism", "time_sequence"]},
    },
    {
        "id": "patent_salt_curing_water_activity",
        "kind": "patent",
        "title": "Salt curing — water activity (a_w) ≤ 0.85 blocks pathogen growth",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "predates record", "year": None, "office": None},
        "vertical": "food_preservation",
        "situation": "Curing meat or fish with 8–15% salt by weight reduces water activity to a_w ≤ 0.85; below this threshold, Staphylococcus aureus growth is blocked, and below a_w 0.75 nearly all pathogenic bacteria are excluded. Salt-cured pork (~12% salt) reaches a_w ≈ 0.75–0.80 after equilibration.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "nutrition"],
        "axes": ["physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Water activity (not water content) is the operative variable. Salt lowers a_w by binding water osmotically. Microbial growth thresholds are well-characterized: most bacteria need a_w > 0.91; S. aureus = 0.86; halophiles = 0.75; most molds = 0.70.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "a_w = (mass-fraction-water in salt-water mixture); 12% NaCl reduces a_w to ~0.78", "data": {"salt_fraction": 0.12, "a_w": 0.78}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "S. aureus growth threshold a_w = 0.86; C. botulinum = 0.94; most molds = 0.70", "data": {"s_aureus_aw_min": 0.86}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["meat or fish", "non-iodized salt (8–15% by weight of meat)", "optional: sugar, spices, nitrite (Prague powder #1 for true 'curing' with color)"],
            "tools": ["scale", "container or vacuum bag", "refrigerator or cool cellar (≤ 4°C)"],
            "steps": ["weigh meat", "weigh salt: 3% for short-cure bacon (5–7 days), 5–10% for traditional dry-cure (weeks)", "rub salt evenly", "refrigerate or cellar 1–4 weeks depending on thickness", "rinse off excess salt", "for shelf-stable: hang in cool dry place to equilibrate further (prosciutto: 6–18 months)"],
            "time": "1 week to 18 months depending on product",
            "cost_usd_2026": "$1–2 per kg salt (the meat is the variable)",
            "scale": "household to commercial",
        },
        "wisdom": "Salt is the oldest preservative because it doesn't require fire, light, or cold. The Shepherd brings this when the user has more meat than they can use fresh and no freezer. Nitrite (Prague powder #1) adds anti-botulinum protection for whole-muscle cures — recommended for traditional methods; the historical 'saltpeter' (KNO₃) converts to nitrite during cure but is harder to dose safely.",
        "triggers": {"keywords": ["salt curing", "water activity", "a_w", "dry cure", "prosciutto", "bacon", "salted fish"], "axes": ["physical_substance", "conservation_balance"]},
    },
    {
        "id": "patent_solar_dehydrator",
        "kind": "patent",
        "title": "Solar dehydrator — natural-convection food drying",
        "patent": {"kind": "patent_family", "number": "US 2,888,008 (Telkes 1959) and many later, expired", "inventor": "Maria Telkes et al.", "year": 1959, "office": "USPTO"},
        "vertical": "food_preservation",
        "situation": "A black-painted solar collector heats air; the heated air rises through a chimney-stack drying chamber, removing moisture from food on racks. Inlet at solar absorber; food chamber above; vent at top creates draft. Target drying temperature 50–65°C; reduces food moisture to 10–20% (storage-safe at a_w < 0.6).",
        "category": "energy",
        "domains": ["thermodynamics", "physics", "agriculture"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Natural-convection draft from absorber + buoyancy difference; rate of water removal limited by air mass-flow × water-carrying capacity at exit temperature.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "Air at 60°C / 30% RH carries ~36 g water/kg air at saturation; typical drying air carries 10–20 g/kg above ambient", "data": {"T_C": 60, "delta_w_g_per_kg": 15}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["plywood / corrugated metal for box", "black paint or black absorber sheet", "clear glazing (glass or polycarbonate) for collector", "fine mesh / screen for racks", "duct sealant"],
            "tools": ["saw, drill, paint brush"],
            "steps": ["build inclined solar absorber 1–2 m² (slope ≈ local latitude), painted black behind glazing", "build drying chamber on top, 3–5 racks of mesh", "vent at top 5–10 cm diameter", "place sliced food on racks (single layer)", "in 6–8 hours of sun, most fruits/vegetables/jerky reach <20% moisture"],
            "time": "build: 1–2 days. drying: 1–3 sunny days per batch.",
            "cost_usd_2026": "$60–$200 depending on materials reused",
            "scale": "household; multiple units for a homestead",
        },
        "wisdom": "Drying is the oldest preservation method that survives in modern PD literature, and the most under-used. No salt, no sugar, no jars. The Shepherd brings this for fruits, jerky, herbs, mushrooms, anything that surrenders water without melting. Combine with vacuum-sealing or low-O₂ storage for years of shelf life.",
        "triggers": {"keywords": ["solar dehydrator", "food drying", "jerky", "dried fruit", "natural convection"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "patent_root_cellar",
        "kind": "patent",
        "title": "Root cellar — soil thermal mass + humidity for winter storage",
        "patent": {"kind": "pd_by_age", "number": "USDA Farmer's Bulletin 1572 (1939, federal PD)", "inventor": "USDA / agricultural extension", "year": 1939, "office": None},
        "vertical": "food_preservation",
        "situation": "An underground or earth-bermed chamber at 0.5–2 m depth holds 32–40°F (0–4°C) and 85–95% relative humidity year-round via soil thermal mass and ground-water-table coupling. Root vegetables (potatoes, carrots, beets, parsnips, cabbage) keep 3–6 months with no electricity.",
        "category": "agriculture",
        "domains": ["thermodynamics", "agriculture", "biology"],
        "axes": ["physical_substance", "time_sequence", "metabolism"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Below frost line, soil temperature converges to mean annual temperature (typically 4–10°C in temperate climates). Above ground vents allow CO₂/ethylene venting and humidity regulation.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "Soil temperature damping: amplitude halves every ~1 m depth; phase lags ~30 days per m", "data": {"depth_m": 1.5, "T_swing_C": 3}},
                {"domain": "biology",        "verdict": "CONFIRMED", "detail": "Respiration of stored roots slows ~half per 10°C drop (Q₁₀)", "data": {"Q10": 2}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["concrete blocks / poured concrete / stone for walls", "earth berm or excavation", "ventilation pipes (intake low, exhaust high)", "wood shelving / bins"],
            "tools": ["shovel / backhoe", "concrete tools", "rebar saw"],
            "steps": ["dig below frost line (varies: 1–2 m in temperate)", "build sturdy roof (load: earth above + snow)", "install two vent pipes — one low for cool intake, one high for warm exhaust", "earth-berm the exposed walls if any", "add humidity by leaving floor as dirt or by water bowl", "store roots in sand/sawdust boxes for best results"],
            "time": "build: 1–2 weeks (DIY); 1 week (with help/equipment)",
            "cost_usd_2026": "$500–$3000 depending on excavation and material reuse",
            "scale": "household; size for family annual root harvest",
        },
        "wisdom": "A working root cellar is independence from refrigeration for the entire root crop. The Shepherd brings this for people on land with the option to dig: the same hole gives you cold storage in winter and cool storage in summer, with zero ongoing input. Pairs with canning (high-acid + low-acid foods) and salt curing for full year-round storage.",
        "triggers": {"keywords": ["root cellar", "earth-bermed", "winter food storage", "off-grid storage", "soil thermal mass"], "axes": ["physical_substance", "time_sequence"]},
    },
]


# ── 3 ─ SOIL ──────────────────────────────────────────────────────────
ENTRIES_SOIL = [
    {
        "id": "patent_composting_c_n_ratio",
        "kind": "patent",
        "title": "Composting C:N ratio — 25–30:1 + moisture + air = thermophilic compost",
        "patent": {"kind": "pd_by_age", "number": "USDA Farmer's Bulletin 1856 (1940, federal PD)", "inventor": "USDA / extension service", "year": 1940, "office": None},
        "vertical": "soil",
        "situation": "A pile of organic matter with initial C:N ratio ~25–30:1, moisture 50–60%, and adequate aeration reaches thermophilic temperatures of 55–65°C within days; pathogens and weed seeds are killed at >55°C × 3 days; finished compost is produced in 4–8 weeks.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "agriculture", "soil_science"],
        "axes": ["metabolism", "conservation_balance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Microbial metabolism — bacteria, actinomycetes, fungi — release heat as they oxidize C. N-rich materials (greens) provide protein nitrogen; C-rich (browns) provide energy carbon.",
            "domain_results": [
                {"domain": "chemistry",   "verdict": "CONFIRMED", "detail": "Composting is aerobic oxidation: CₓHᵧNᵤOᵥ + O₂ → CO₂ + H₂O + NH₃ + heat; mass balance holds", "data": {"target_C_to_N": 27}},
                {"domain": "biology",     "verdict": "CONFIRMED", "detail": "Thermophilic phase 55–65°C inactivates Salmonella, E. coli, viable weed seeds", "data": {"T_C": 60, "kill_time_days": 3}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["greens (kitchen scraps, fresh manure, grass clippings)", "browns (straw, leaves, sawdust, paper)", "water"],
            "tools": ["pitchfork", "thermometer (long-stem, optional)", "bin or open pile"],
            "steps": ["aim for ~1 part green to 3 parts brown by volume", "build pile at least 1 m³ for thermal mass", "moisten so material is damp like a wrung-out sponge", "turn weekly (or whenever temp drops) to re-aerate", "finished in 4–8 weeks; smells like earth, not garbage"],
            "time": "ongoing; finished pile in 4–8 weeks",
            "cost_usd_2026": "$0 — all inputs are 'waste' streams",
            "scale": "any; backyard to farm",
        },
        "wisdom": "Compost converts the unusable into the irreplaceable: kitchen scraps + leaves become tilth that holds water, feeds plants, and rebuilds soil structure. The Shepherd brings this whenever the user asks about soil, garbage, or fertility — same answer, three doorways. The thermophilic phase is what separates compost from rot: cool piles smell bad and harbor pathogens; hot piles smell like earth.",
        "triggers": {"keywords": ["compost", "C:N ratio", "thermophilic", "soil amendment", "humus"], "axes": ["metabolism", "conservation_balance"]},
    },
    {
        "id": "patent_bordeaux_mixture",
        "kind": "patent",
        "title": "Bordeaux mixture — copper sulfate + lime fungicide (Millardet, 1885)",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "Pierre-Marie-Alexis Millardet", "year": 1885, "office": None},
        "vertical": "soil",
        "situation": "Mixing copper sulfate (CuSO₄·5H₂O) with hydrated lime (Ca(OH)₂) in water at the classic 1:1:100 ratio (1 kg CuSO₄ : 1 kg lime : 100 L water) produces a blue suspension of copper hydroxide (Cu(OH)₂) particles. Sprayed on plants, it controls fungal diseases including downy mildew, powdery mildew, and black spot. CuSO₄ + Ca(OH)₂ → Cu(OH)₂ + CaSO₄.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "agriculture"],
        "axes": ["physical_substance", "metabolism"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Lime precipitates the copper out as fine suspended Cu(OH)₂; this sticks to leaf surfaces and slowly releases Cu²⁺ ions on contact with fungal spores.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "CuSO₄ + Ca(OH)₂ → Cu(OH)₂↓ + CaSO₄; atoms and charge balance", "data": {"products": ["Cu(OH)2", "CaSO4"]}},
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "Cu²⁺ disrupts fungal enzyme thiol groups; classic broad-spectrum contact fungicide since 1885", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["copper sulfate pentahydrate (CuSO₄·5H₂O), garden grade", "hydrated lime (Ca(OH)₂)", "water", "sprayer"],
            "tools": ["two non-metal buckets (it dissolves galvanized metal!)", "wooden stir stick", "scale or measuring cup"],
            "steps": ["dissolve 10 g CuSO₄ in 5 L water in bucket A (plastic / ceramic)", "stir 10 g lime into 5 L water in bucket B", "slowly pour A into B (NEVER reverse) while stirring", "use within 24 hours — formulation degrades", "spray on plants at first signs of fungal disease; reapply after rain"],
            "time": "30 min to mix; spray as needed in season",
            "cost_usd_2026": "<$10 for a year's supply for a household garden",
            "scale": "garden to vineyard (still used on certified-organic vineyards)",
        },
        "wisdom": "Bordeaux mixture saved European vineyards from downy mildew in the 1880s and is still on the certified-organic list. Copper is a heavy metal — overuse builds up in soil. Use sparingly, target the disease, and rotate with other approaches (sulfur, biofungicides, resistant varieties). The Shepherd brings this when the user describes mildew, rust, blight — and notes the soil-buildup caveat.",
        "triggers": {"keywords": ["Bordeaux mixture", "copper sulfate fungicide", "mildew control", "Millardet", "vineyard fungicide"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_nitrogen_fixing_legumes",
        "kind": "patent",
        "title": "Legume nitrogen fixation — Rhizobium + nitrogenase = free fertilizer",
        "patent": {"kind": "pd_by_age", "number": "USDA bulletins 1890s onward (federal PD)", "inventor": "Hermann Hellriegel + Hermann Wilfarth (1886)", "year": 1886, "office": None},
        "vertical": "soil",
        "situation": "Legume plants (clover, alfalfa, beans, peas, soybeans, peanuts) host Rhizobium bacteria in root nodules. The nitrogenase enzyme converts atmospheric N₂ to NH₃ (ammonia), then to amino acids. A soybean crop can fix 100–250 kg N/ha/year — replacing the same nitrogen a synthetic fertilizer would supply. Rotation with non-legumes captures the residual N.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "agriculture"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "N₂ + 8 H⁺ + 8 e⁻ + 16 ATP → 2 NH₃ + H₂ + 16 ADP + 16 Pᵢ (nitrogenase reaction). Energy-expensive but free to the farmer.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Nitrogenase reaction: N₂ + 8 H⁺ + 8 e⁻ + 16 ATP → 2 NH₃ + H₂ + 16 ADP + Pᵢ", "data": {}},
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "Rhizobium-legume symbiosis fixes 100–250 kg N/ha/year for soybeans", "data": {"kg_N_per_ha_per_year": 175}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["legume seed (rotation cover or food crop)", "Rhizobium inoculant matched to legume (most seed sold pre-inoculated; otherwise $5/kg seed)"],
            "tools": ["any planting equipment"],
            "steps": ["select a legume matched to climate: clover (cool season cover), cowpea (warm season cover), soybean / common bean / pea (food + N)", "plant at recommended density", "inoculate seed with Rhizobium if soil hasn't grown this legume in 3+ years", "let it grow; if cover crop, terminate at flowering (max N in plant tissue)", "plant heavy-feeder crop (corn, brassicas, leafy greens) in same field next season"],
            "time": "one season cover; or harvest food + reduced fertilizer next year",
            "cost_usd_2026": "$3–10/kg seed; $0 fertilizer replaced",
            "scale": "garden to industrial farm",
        },
        "wisdom": "Legume rotation is the oldest known fertility-restoring practice and one of the most powerful — the Hellriegel-Wilfarth 1886 demonstration explained why it worked but humans had been doing it for millennia. The Shepherd brings this whenever the user asks about reducing fertilizer dependence, building soil, or what to plant after a heavy feeder.",
        "triggers": {"keywords": ["legume", "nitrogen fixation", "Rhizobium", "cover crop", "crop rotation", "nitrogenase"], "axes": ["metabolism", "physical_substance"]},
    },
]


# ── 4 ─ MEDICINE ──────────────────────────────────────────────────────
ENTRIES_MEDICINE = [
    {
        "id": "patent_oral_rehydration_solution",
        "kind": "patent",
        "title": "Oral rehydration solution (ORS) — WHO formula, ~$0.10/dose",
        "patent": {"kind": "pd_by_age", "number": "WHO/UNICEF formula 1975, published PD", "inventor": "Norbert Hirschhorn / Dilip Mahalanabis / David Nalin (independently)", "year": 1968, "office": None},
        "vertical": "medicine",
        "situation": "1 liter of safe water + 2.6 g NaCl + 1.5 g KCl + 2.9 g trisodium citrate + 13.5 g glucose = WHO low-osmolarity ORS (245 mOsm/L). Reduces cholera and acute diarrhea mortality from ~50% to <1%. Glucose drives sodium absorption via SGLT1 even when the gut is otherwise leaking water.",
        "category": "medicine",
        "domains": ["chemistry", "medicine", "biology"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Sodium-glucose cotransport (SGLT1) is preserved during diarrheal illness even when bulk water absorption fails. Glucose pulls Na⁺ in; Na⁺ pulls water in.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Osmolarity ≈ (Na⁺ + K⁺ + Cl⁻ + citrate + glucose) ≈ 245 mOsm/L", "data": {"osmolarity_mOsm_per_L": 245}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Lancet 1978: ORS reduces case-fatality of severe dehydrating diarrhea from 30–50% to <1%", "data": {"cfr_before": 0.40, "cfr_after": 0.005}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["1 L safe water (boiled or chlorinated)", "salt", "sugar or glucose", "optional: potassium chloride (NoSalt salt substitute) and baking soda or citrate"],
            "tools": ["measuring spoons"],
            "steps": ["FIELD VERSION (most lives saved at this complexity): 1 L safe water + 1 tsp (5 g) salt + 8 tsp (40 g) sugar. Stir to dissolve. Sip slowly over hours.", "FULL WHO FORMULA: add 1/2 tsp KCl substitute + 1/2 tsp baking soda if available."],
            "time": "5 min to mix; replace fluids over hours",
            "cost_usd_2026": "<$0.10 per liter dose",
            "scale": "household; ORS sachets cost <$0.05 each commercially",
        },
        "wisdom": "The Lancet called ORS 'potentially the most important medical advance of this century' (1978). Cheaper than the ambulance, saves more lives than the antibiotic. The Shepherd brings this whenever the user describes diarrhea, vomiting, dehydration, or heat illness in someone able to drink. Severe dehydration with shock still needs IV — ORS is for the conscious patient.",
        "triggers": {"keywords": ["ORS", "oral rehydration", "diarrhea treatment", "dehydration", "cholera", "WHO formula"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_hand_washing_semmelweis",
        "kind": "patent",
        "title": "Hand-washing with chlorinated lime — Semmelweis (1847)",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "Ignaz Semmelweis", "year": 1847, "office": None},
        "vertical": "medicine",
        "situation": "Hand-washing in chlorinated lime (Ca(OCl)₂) solution between patients reduced puerperal fever mortality in Vienna General Hospital's First Obstetric Clinic from 18.3% (1846) to 2.2% (1848). Modern equivalent: soap + 20 seconds, OR alcohol-based hand rub (60–80% ethanol or isopropanol).",
        "category": "medicine",
        "domains": ["medicine", "biology", "statistics", "chemistry"],
        "axes": ["metabolism", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Mechanical removal (soap + friction + rinse) + chemical kill (alcohol or chlorine) reduces transient skin microbes by 2–4 log per wash.",
            "domain_results": [
                {"domain": "statistics","verdict": "CONFIRMED", "detail": "Mortality drop 18.3% → 2.2% over a single year is a >5-sigma effect for n ≈ 4000 births/year", "data": {"p_value": "<1e-100", "rate_before": 0.183, "rate_after": 0.022}},
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Hand-borne Streptococcus pyogenes was the puerperal fever pathogen; transmission interrupted by handwash", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["soap (any)", "clean water", "OR alcohol hand sanitizer (60%+ ethanol)"],
            "tools": ["sink or water source"],
            "steps": ["wet hands", "apply soap", "scrub all surfaces 20 seconds (sing 'Happy Birthday' twice)", "rinse", "dry on clean towel or air", "for high-risk situations (medical, food prep, latrine exit): wash before AND after"],
            "time": "30 seconds per wash",
            "cost_usd_2026": "<$0.01 per wash",
            "scale": "individual to hospital",
        },
        "wisdom": "Semmelweis was institutionalized for insisting on hand-washing — the medical establishment refused him; he died in an asylum in 1865, the same year Lister built on his work. Hand-washing remains the single cheapest, highest-impact medical intervention ever discovered. The Shepherd brings this whenever the user is preparing food, treating a wound, attending a birth, or moving between sick and well people.",
        "triggers": {"keywords": ["hand washing", "Semmelweis", "puerperal fever", "infection control", "soap and water"], "axes": ["metabolism", "authority_trust"]},
    },
    {
        "id": "patent_iodine_tincture",
        "kind": "patent",
        "title": "Iodine tincture antiseptic — broad-spectrum since 1839",
        "patent": {"kind": "pd_by_age", "number": "USP monograph since 1830", "inventor": "Jean Lugol (1829) / Antoine-Germain Labarraque (1825)", "year": 1830, "office": None},
        "vertical": "medicine",
        "situation": "2% iodine + 2.4% sodium iodide in 47% ethanol (USP Tincture of Iodine) kills bacteria, viruses, fungi, and protozoa on contact. Applied to skin pre-procedure, it reduces surgical-site infection. 5 drops of 2% iodine per liter of water purifies it in 30 minutes (emergency dose; not for chronic use due to thyroid load).",
        "category": "medicine",
        "domains": ["chemistry", "biology", "medicine"],
        "axes": ["physical_substance", "metabolism"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "I₂ oxidizes sulfhydryl groups in proteins; broad-spectrum because that mechanism is universal across microbes.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "I₂ in ethanol stays dissolved; KI or NaI shifts equilibrium to I₃⁻ keeping it soluble", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Pre-surgical iodine reduces SSI; emergency water purification at 5 drops 2%/L × 30 min", "data": {"water_dose_drops_per_L": 5, "water_contact_min": 30}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["2% iodine tincture (USP, available OTC) — OR — iodine crystals + ethanol if making from scratch"],
            "tools": ["dropper"],
            "steps": ["WOUND: clean wound with water; apply tincture to surrounding skin (NOT inside open wound — it damages healing tissue)", "PRE-PROCEDURE: paint skin, let dry 30 sec before incision", "WATER: 5 drops of 2% iodine per liter clear water, mix, wait 30 min before drinking"],
            "time": "30 seconds to apply; 30 min for water disinfection",
            "cost_usd_2026": "$5 for a bottle that lasts years",
            "scale": "individual to small clinic",
        },
        "wisdom": "Iodine fell out of fashion when alcohol-based antiseptics gained market share, but for spectrum and shelf-life it has no peer in field medicine. The Shepherd brings this when chlorhexidine and povidone-iodine aren't available — old-fashioned tincture works. Caveat: do NOT use long-term for water disinfection (thyroid load); chlorine or filtration is preferred for chronic supply.",
        "triggers": {"keywords": ["iodine", "antiseptic", "tincture of iodine", "wound care", "emergency water purification"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_penicillin_production",
        "kind": "patent",
        "title": "Penicillin production — Florey/Heatley fermentation (1940, expired)",
        "patent": {"kind": "patent_family", "number": "US 2,442,141 (Moyer 1948, expired) and others, all expired", "inventor": "Howard Florey, Norman Heatley, Ernst Chain (extraction); Mary Hunt's mold strain (1943)", "year": 1948, "office": "USPTO"},
        "vertical": "medicine",
        "situation": "Penicillium chrysogenum grown in corn-steep liquor at 24–26°C with vigorous aeration produces penicillin G (benzylpenicillin). The β-lactam ring covalently inhibits bacterial transpeptidase, preventing peptidoglycan cross-linking, lysing growing Gram-positive bacteria. Production: gram quantities per liter of broth after 5–7 days; industrial yields reach 50+ g/L with selected strains.",
        "category": "medicine",
        "domains": ["chemistry", "biology", "medicine"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Submerged-culture fermentation; the science is fully published and unpatented. Yield depends on strain selection and feed media chemistry.",
            "domain_results": [
                {"domain": "biology",   "verdict": "CONFIRMED", "detail": "P. chrysogenum strain NRRL 1951 (Mary Hunt's cantaloupe isolate, 1943) and descendants underlie nearly all production", "data": {}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Penicillin G structure: 6-aminopenicillanic acid + phenylacetic acid sidechain", "data": {}},
                {"domain": "medicine", "verdict": "CONFIRMED", "detail": "Mechanism: β-lactam binds PBPs (penicillin-binding proteins), blocking peptidoglycan synthesis", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["P. chrysogenum culture (NRRL 1951 is publicly distributed)", "corn-steep liquor + lactose + minerals", "sterile fermenter (5–20 L for home / small lab)", "extraction solvent (chloroform / butyl acetate)", "buffers and salts"],
            "tools": ["autoclave or pressure cooker (sterilization)", "pH meter", "aeration pump", "centrifuge or filtration"],
            "steps": ["sterilize all equipment and media", "inoculate Penicillium into broth", "ferment 5–7 days at 24°C with aeration", "filter mycelium off", "extract penicillin into organic solvent at pH 2.0", "back-extract to aqueous at pH 7.0 → crystallize"],
            "time": "1–2 weeks per batch",
            "cost_usd_2026": "Setup $1000–5000 for clean small-lab; per-dose cost low at scale",
            "scale": "Lab scale possible; clinical-grade purity requires controlled environment. **The Shepherd does NOT recommend home production for treatment** — purity, dose accuracy, and contamination risk are real. The knowledge is in the keeping because the chemistry is in the keeping; production at therapeutic standard requires a proper facility.",
        },
        "wisdom": "Penicillin is the canonical 'PD knowledge that changed everything' — Florey and Heatley deliberately did not patent the basic discovery, considering it the heritage of humanity. The Shepherd carries the chemistry and the history; he is honest that producing safe therapeutic doses at home is harder than the chemistry suggests, and that current strains and methods belong in proper labs. For the user who wants to understand HOW antibiotics work, this is the entry. For the user who needs antibiotics, they need a clinic.",
        "triggers": {"keywords": ["penicillin", "antibiotic production", "fermentation", "Florey", "Heatley", "beta-lactam"], "axes": ["metabolism", "physical_substance"]},
    },
]


# ── 5 ─ ENERGY ────────────────────────────────────────────────────────
ENTRIES_ENERGY = [
    {
        "id": "patent_rocket_stove",
        "kind": "patent",
        "title": "Rocket stove — L-feed insulated combustion chamber (Winiarski 1980s)",
        "patent": {"kind": "patent_family", "number": "Aprovecho Research Center designs, openly published PD", "inventor": "Larry Winiarski / Aprovecho Research Center", "year": 1982, "office": None},
        "vertical": "energy",
        "situation": "An L-shaped feed (horizontal stick chamber + vertical insulated combustion chimney) with a tight pot skirt achieves near-complete wood combustion. Thermal efficiency to pot reaches 30–45%, compared to 5–15% for an open three-stone fire. Wood consumption per cooking task drops 4–7x.",
        "category": "energy",
        "domains": ["thermodynamics", "chemistry", "energy"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Insulated combustion chamber maintains temperatures >700°C → complete oxidation of CO and volatiles. Tight skirt forces hot gas into prolonged contact with the pot wall.",
            "domain_results": [
                {"domain": "thermodynamics","verdict": "CONFIRMED", "detail": "Open fire ~5–15% efficient to pot; rocket stove 30–45% (Aprovecho lab measurements)", "data": {"eta_open_fire": 0.10, "eta_rocket_stove": 0.40}},
                {"domain": "chemistry",     "verdict": "CONFIRMED", "detail": "Combustion 2C + O₂ → 2CO + heat; CO + ½O₂ → CO₂ + more heat; both go to completion above 700°C", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fire brick or insulating brick OR a metal can stuffed with wood ash insulation", "metal pipe / can for the chimney", "metal for the pot skirt"],
            "tools": ["tin snips / saw / drill"],
            "steps": ["build vertical insulated combustion chamber 25–40 cm tall, internal diameter 10–15 cm", "horizontal feed at base, smaller cross-section than chimney (ratio ~2:1 area, chimney bigger)", "elevated grate inside feed so air flows under wood", "build pot skirt around top: gap of 6–12 mm between pot wall and skirt", "feed only the tips of sticks; advance them as they burn"],
            "time": "build: 1–3 hours (simple brick) to 1 day (welded steel)",
            "cost_usd_2026": "$10–50 DIY",
            "scale": "single-pot to small institutional",
        },
        "wisdom": "The rocket stove cuts wood use by 4–7× and indoor smoke even more — meaning more forest standing, less respiratory disease, less time spent gathering. The Shepherd brings this when the user cooks with wood and wants to use less of it, or when smoke inhalation is a household issue. Pairs naturally with the rocket mass heater (separate gem) for space heat.",
        "triggers": {"keywords": ["rocket stove", "efficient woodstove", "Winiarski", "appropriate technology cookstove", "biomass"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "patent_parabolic_solar_cooker",
        "kind": "patent",
        "title": "Parabolic solar cooker — geometric focal-point concentration",
        "patent": {"kind": "pd_by_age", "number": "Multiple expired patents from 1860s onward", "inventor": "Augustin Mouchot (1869); design fundamentals predate patent system", "year": 1869, "office": None},
        "vertical": "energy",
        "situation": "A parabolic reflector with focal length f, paraboloid equation y = x²/(4f), reflects parallel sun rays to a single focal point. At 1 m² aperture and 800 W/m² insolation, focal-point irradiance reaches 80+ kW/m² (theoretical) and 5–50 kW/m² practical; cooking temperatures exceed 200°C; water boils in 5–15 minutes.",
        "category": "energy",
        "domains": ["physics", "optics", "thermodynamics"],
        "axes": ["physical_substance", "reasoning", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Conic-section optics; parallel-ray-to-focal-point is the defining property of a paraboloid. Concentration ratio is the geometric ratio of aperture area to focal-region area.",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Paraboloid focuses parallel rays at the focal point (defining property)", "data": {"focal_length_m": 0.50}},
                {"domain": "thermodynamics","verdict": "CONFIRMED", "detail": "1 m² × 800 W/m² × 50% optical efficiency ÷ small focal area → cooking temperatures", "data": {"insolation_W_per_m2": 800, "optical_eta": 0.50}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["reflective sheet (mylar, aluminized polyester, polished aluminum)", "frame (wood, cardboard, metal)", "pot stand at focal point", "tracking mount (manual or sun-tracking)"],
            "tools": ["scissors / saw / glue", "string + chalk for paraboloid template OR satellite-dish recycled"],
            "steps": ["acquire or construct a paraboloid: easiest is a recycled satellite dish lined with mylar", "calculate focal length (for a recycled dish: place straight edge across the rim, measure deepest point d; f = D²/(16d) where D = dish diameter)", "mount pot or stand at the focal point", "aim at sun by hand or with simple shadow-pointer; track every 15–20 min"],
            "time": "1 day build (recycled dish) to 2–3 days (built from scratch)",
            "cost_usd_2026": "$10–60 (dish + mylar)",
            "scale": "single-pot to community-kitchen",
        },
        "wisdom": "The Shepherd brings this where fuel is scarce or smoke is sickening. WARNING: parabolic cookers produce concentrated light at the focal point that can burn skin or eyes in seconds — children and pets must stay clear; users should wear welder's goggles when adjusting aim. Trade-offs: no clouds, no night, no rain — pairs with rocket stove for cloudy and evening cooking.",
        "triggers": {"keywords": ["parabolic solar cooker", "solar cooking", "Mouchot", "concentrating collector", "focal point cooker"], "axes": ["physical_substance", "reasoning"]},
    },
    {
        "id": "patent_charcoal_retort_kiln",
        "kind": "patent",
        "title": "Charcoal retort kiln — pyrolysis at 400–700°C",
        "patent": {"kind": "patent_family", "number": "Multiple US patents 1850s–1950s, all expired", "inventor": "Various; principle predates", "year": 1900, "office": "USPTO"},
        "vertical": "energy",
        "situation": "Heating wood in an oxygen-limited chamber (retort) to 400–700°C drives off volatile compounds (water, tars, methanol, acetic acid, wood gas) leaving behind carbon-rich charcoal (~75–85% carbon by weight). Yield: ~25–35% of dry wood mass becomes charcoal. The released wood gas can be captured and burned to heat the kiln, making the process self-sustaining after startup.",
        "category": "energy",
        "domains": ["chemistry", "thermodynamics", "energy"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Pyrolysis (anaerobic thermal decomposition): C₆H₁₀O₅ (cellulose) → C (charcoal) + CO + CO₂ + CH₄ + H₂O + tar; product slate depends on temperature.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Pyrolysis temperatures: 200–280°C drying + initial decomp; 280–500°C tar and gas release; 500–700°C completion to high-carbon char", "data": {"T_C_range": [400, 700]}},
                {"domain": "energy",  "verdict": "CONFIRMED", "detail": "Wood gas energy content ~5 MJ/Nm³; can be burned to drive the kiln", "data": {"yield_charcoal_fraction": 0.30}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["55-gal steel drum (or two)", "smaller inner drum for retort", "metal pipe for exhaust", "fire bricks (optional, for kiln)"],
            "tools": ["welder or sturdy fasteners", "drill", "tin snips"],
            "steps": ["inner drum: pack tightly with split wood, lid loose (vents)", "place inner drum upside-down inside outer drum filled with fuel wood between the two", "light outer fuel; the inner drum's wood pyrolyzes, releasing gas that burns at the lid gap, sustaining the heat", "cool overnight before opening", "yield: ~25–30% of input mass as good charcoal"],
            "time": "build: 1 day. each batch: 6–10 hours run + overnight cool.",
            "cost_usd_2026": "$50–200 for two drums and bricks",
            "scale": "household; up to small commercial",
        },
        "wisdom": "Charcoal is dense, dry, smoke-free energy — three properties wood lacks. The Shepherd brings this when the user needs cooking fuel that stores, transports, and burns clean. WARNING: open burning of wood for charcoal (traditional mound method) releases massive CO and methane; the retort design captures most of it and burns it back into the kiln. The retort is the environmentally honest version.",
        "triggers": {"keywords": ["charcoal", "retort", "pyrolysis", "biochar", "wood gas"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "patent_bicycle_generator",
        "kind": "patent",
        "title": "Bicycle generator — 50–100W sustainable human electrical output",
        "patent": {"kind": "patent_family", "number": "Multiple expired patents 1900–2005", "inventor": "Various", "year": 1950, "office": "USPTO"},
        "vertical": "energy",
        "situation": "A trained adult sustains 60–100W mechanical output for hours; with 80–85% efficient permanent-magnet generator + rectifier + voltage regulator, ~50–80W of usable DC electrical output. Enough to run LED lighting (3 × 5W), a radio (3W), a phone charger (5W), or charge a 12V battery (slowly).",
        "category": "energy",
        "domains": ["electrical", "physics", "exercise_science"],
        "axes": ["metabolism", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Untrained: ~75W sustained; trained: 150–200W sustained. Generator efficiency × battery efficiency × converter efficiency yields end-use power.",
            "domain_results": [
                {"domain": "exercise_science","verdict": "CONFIRMED", "detail": "Sustained human cycling output: 75W untrained, 150W trained (FTP)", "data": {"P_W_untrained": 75, "P_W_trained": 150}},
                {"domain": "electrical",      "verdict": "CONFIRMED", "detail": "PM generator efficiency 75–90%; net output 50–80% of mechanical input", "data": {"eta_generator": 0.80}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["bike stand or old bicycle frame", "permanent-magnet DC motor (car treadmill motor; scooter hub motor — 24V/250W is ideal)", "drive belt or direct contact roller", "bridge rectifier + voltage regulator (12V output)", "12V battery (lead-acid or LiFePO4) + charge controller"],
            "tools": ["wrenches", "soldering iron", "multimeter"],
            "steps": ["mount the bike rear wheel on a stationary stand", "mount the motor so its shaft contacts the tire OR connect via belt to a small drive pulley on the wheel hub", "wire motor through bridge rectifier (AC if motor is induction, otherwise direct DC)", "regulate to 12–14V output", "connect to battery via charge controller", "loads (lights, USB chargers) draw from battery, not directly from generator"],
            "time": "build: 1 weekend",
            "cost_usd_2026": "$80–200 (motor is the main variable)",
            "scale": "individual; multiple in series for community phone-charging station",
        },
        "wisdom": "Human-electrical is dignified work — not a generator, an effort. 30 minutes pedaling stores enough for an evening of LED light + radio. The Shepherd brings this when the user wants electricity without the grid or solar panels, or as a backup to either. Pairs with a small battery (NOT a wall, just enough — 50 Wh covers most household lighting/comm for a night).",
        "triggers": {"keywords": ["bicycle generator", "pedal power", "human power", "off-grid electricity", "battery charging"], "axes": ["metabolism", "physical_substance"]},
    },
]


# ── 6 ─ SHELTER ───────────────────────────────────────────────────────
ENTRIES_SHELTER = [
    {
        "id": "patent_rammed_earth",
        "kind": "patent",
        "title": "Rammed earth wall — 1–5 MPa compressive strength from subsoil",
        "patent": {"kind": "pd_by_age", "number": "USDA bulletin 1500 (pre-1929, federal PD); technique Roman", "inventor": "predates record; Roman 'pisé de terre'", "year": None, "office": None},
        "vertical": "shelter",
        "situation": "Subsoil (not topsoil) at 8–15% moisture content, compacted in 10 cm lifts inside formwork with a heavy tamper, produces a monolithic wall of compressive strength 1–5 MPa — comparable to weak concrete. With 5–10% stabilizer (lime or cement) added, strength reaches 5–10 MPa. Walls breathe (moisture-buffering), store heat (thermal mass), and last centuries.",
        "category": "construction",
        "domains": ["materials_science", "architecture", "geology"],
        "axes": ["physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Optimum mix: ~70% sand + 30% clay (by weight); Atterberg limit testing classifies suitable subsoil. Moisture at Proctor optimum maximizes dry density.",
            "domain_results": [
                {"domain": "materials_science","verdict": "CONFIRMED", "detail": "Unstabilized rammed earth 1–5 MPa, stabilized 5–10 MPa; tensile strength low (needs rebar where seismic)", "data": {"f_c_unstabilized_MPa": 3, "f_c_stabilized_MPa": 7}},
                {"domain": "architecture",    "verdict": "CONFIRMED", "detail": "Walls 30–60 cm thick; thermal mass damping >12 h; centuries of historical service (Great Wall sections; Alhambra)", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["site subsoil (free)", "lime or Portland cement 5–10% stabilizer if needed", "water", "formwork (plywood or aluminum panels with ties)"],
            "tools": ["pneumatic or hand tamper", "shovel", "wheelbarrow", "level"],
            "steps": ["test soil: jar test (water + soil; settles in layers — want ~70% sand)", "build formwork on prepared foundation (concrete or rubble trench)", "fill formwork with 10 cm layer of damp soil mix", "tamp until ringing sound + no further compression", "repeat layer by layer", "remove formwork immediately after each section; the wall stands"],
            "time": "1–2 weeks for a small structure (slow-and-steady; not fast)",
            "cost_usd_2026": "$1–10 per m² in materials (soil free; stabilizer optional)",
            "scale": "small house to multistory; tested in modern code (NZS 4297, others)",
        },
        "wisdom": "Rammed earth is the building method that comes from the ground you're standing on. The Shepherd brings this where local soil is suitable, the climate is dry-to-moderate, and the user has more time than money. Trade-offs: slow to build, requires dry curing, needs proper roof overhang (no extended water exposure), seismic zones need reinforcement.",
        "triggers": {"keywords": ["rammed earth", "pisé de terre", "earth building", "subsoil construction", "thermal mass"], "axes": ["physical_substance"]},
    },
    {
        "id": "patent_lime_mortar",
        "kind": "patent",
        "title": "Lime mortar — CaO/Ca(OH)₂/CaCO₃ reversible carbon cycle",
        "patent": {"kind": "pd_by_age", "number": None, "inventor": "Roman / predates patents", "year": None, "office": None},
        "vertical": "shelter",
        "situation": "Three reactions: (1) calcination at 900°C: CaCO₃ → CaO + CO₂; (2) slaking with water: CaO + H₂O → Ca(OH)₂; (3) carbonation in air over months to years: Ca(OH)₂ + CO₂ → CaCO₃ + H₂O. All atoms balance; the cement reabsorbs the CO₂ released in step 1 over the life of the building. Compressive strength 0.5–2 MPa (lower than Portland but more flexible and self-healing of cracks).",
        "category": "construction",
        "domains": ["chemistry", "materials_science", "architecture"],
        "axes": ["physical_substance", "metabolism", "conservation_balance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Three-step calcination/slaking/carbonation cycle is fully reversible in carbon terms. Lime predates Portland cement by 8000 years.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "CaCO₃ → CaO + CO₂ (calcination); CaO + H₂O → Ca(OH)₂ (slaking); Ca(OH)₂ + CO₂ → CaCO₃ + H₂O (carbonation). All atoms balance.", "data": {"reactions_balanced": True}},
                {"domain": "materials_science","verdict": "CONFIRMED", "detail": "Hydraulic lime sets faster (weeks) than air lime (months/years); strength 0.5–2 MPa", "data": {"f_c_MPa": 1.5}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["limestone OR hydrated lime / hydraulic lime (sold in bags)", "sand (washed, sharp)", "water"],
            "tools": ["mortar tub", "trowel"],
            "steps": ["FOR SHEER MORTAR: mix 1 part hydrated lime : 3 parts sand : water to a workable consistency", "let stand 30 min to 'fatten' before use", "apply between stones/bricks in thin courses (12 mm)", "mist with water lightly the next several days to slow drying", "carbonates over months to years to full strength"],
            "time": "mix: 10 min. wall: stone-mason pace.",
            "cost_usd_2026": "$10–20 per 25 kg bag of lime; ~$3/m² wall mortar",
            "scale": "from repointing a wall to building cathedrals",
        },
        "wisdom": "Lime mortar is what Portland cement displaced for the wrong reasons — slower to set, lower strength, but it breathes, self-heals fine cracks, and reabsorbs the CO₂ from its own production over the life of the building. The Shepherd brings this for stone, brick, or rubble walls where Portland cement would trap moisture and cause spalling. For load-bearing modern construction, hydraulic lime or natural cement (NHL 3.5, NHL 5) gives faster setting.",
        "triggers": {"keywords": ["lime mortar", "hydraulic lime", "lime cycle", "carbonation", "traditional masonry"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_rocket_mass_heater",
        "kind": "patent",
        "title": "Rocket mass heater — 70–90% efficient wood heat into thermal-mass bench",
        "patent": {"kind": "patent_family", "number": "Aprovecho / Cob Cottage publications, openly published PD", "inventor": "Ianto Evans, Larry Winiarski (rocket combustion), Linda Smiley", "year": 1990, "office": None},
        "vertical": "shelter",
        "situation": "Rocket-stove combustion (insulated J-tube, internal temperatures 800–1000°C, near-complete burn) routed through a horizontal duct embedded in a cob or masonry bench. The thermal mass absorbs 70–90% of the heat that would escape an ordinary stovepipe, releasing it slowly over 12–24 hours. Wood consumption per heating season: 1/4 to 1/8 of a conventional wood stove.",
        "category": "construction",
        "domains": ["thermodynamics", "chemistry", "energy", "architecture"],
        "axes": ["metabolism", "physical_substance", "conservation_balance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two-stage system: (1) clean fast combustion in the J-tube; (2) heat extraction by long contact with thermal mass before exhaust.",
            "domain_results": [
                {"domain": "thermodynamics","verdict": "CONFIRMED", "detail": "Exhaust temperatures often <100°C (vs 200–400°C for conventional stoves); difference is heat retained in mass", "data": {"eta_total": 0.80}},
                {"domain": "chemistry",     "verdict": "CONFIRMED", "detail": "J-tube combustion temperatures >800°C → complete oxidation of CO and volatiles → near-zero PM2.5 emissions", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fire brick (insulating) for the J-tube", "stove pipe for the burn tunnel & exhaust", "barrel for the radiation chamber", "cob (clay + sand + straw) OR brick for thermal-mass bench"],
            "tools": ["masonry tools", "saw + drill"],
            "steps": ["build J-tube: vertical feed (10 cm diameter), horizontal burn tunnel, vertical heat riser inside an insulated chamber", "place inverted barrel over heat riser; gap at top for radiation", "exhaust pipe from base of barrel runs horizontally through a cob bench (5–15 m of pipe)", "exhaust exits low — natural draft pulls air through the system", "let cob cure 4–6 weeks before serious firing"],
            "time": "build: 2–4 weeks (cob takes time to cure)",
            "cost_usd_2026": "$200–800 in materials",
            "scale": "single room to small house (heat travels 5–10 m from bench)",
        },
        "wisdom": "Rocket mass heaters are the most efficient wood-heat technology accessible to amateur builders. The Shepherd brings this for cold climates with wood available, when the user wants to heat with much less fuel and almost no smoke. WARNING: an undersized or poorly drafted system can backpuff carbon monoxide into living space — install a CO alarm, and observe burn behavior the first dozen fires before leaving it unattended.",
        "triggers": {"keywords": ["rocket mass heater", "thermal mass heating", "cob bench heater", "wood heat efficiency"], "axes": ["metabolism", "physical_substance", "conservation_balance"]},
    },
]


# ── 7 ─ COMMUNICATION ─────────────────────────────────────────────────
ENTRIES_COMMS = [
    {
        "id": "patent_crystal_radio",
        "kind": "patent",
        "title": "Crystal radio — AM reception with zero external power",
        "patent": {"kind": "patent_family", "number": "Multiple US 1900s patents (Pickard, US 836,531, 1906; expired)", "inventor": "Greenleaf Whittier Pickard / Jagadish Chandra Bose", "year": 1906, "office": "USPTO"},
        "vertical": "communication",
        "situation": "An LC tank circuit (coil + variable capacitor) tunes to an AM broadcast frequency; a galena or germanium-diode point-contact detector demodulates the AM envelope; high-impedance headphones (≥2 kΩ) reproduce audio. Energy comes entirely from the broadcast signal itself; no batteries, no transistors, no IC. A long antenna + good earth ground is the entire amplification system.",
        "category": "energy",
        "domains": ["electrical", "physics", "information_theory"],
        "axes": ["information_encoding", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Resonant LC selects frequency; diode rectifies the AM envelope; impedance match to headphones recovers the audio.",
            "domain_results": [
                {"domain": "electrical","verdict": "CONFIRMED", "detail": "Resonant f = 1/(2π√LC); typical AM band 540–1700 kHz; L = 240 µH + C = 365 pF max tunes the band", "data": {"f_kHz_min": 540, "f_kHz_max": 1700}},
                {"domain": "physics",   "verdict": "CONFIRMED", "detail": "Galena (PbS) and germanium are natural semiconductors; their I/V asymmetry rectifies the carrier", "data": {}},
            ],
            "axis_overlaps": [{"axis": "information_encoding", "with": ["cryptography", "linguistics", "genetics"], "note": "AM is amplitude-modulation encoding; demodulation is decoding"}],
        },
        "make_it": {
            "materials": ["~50m wire (antenna)", "ground rod / cold-water pipe (earth)", "240 µH air-core coil (wind ~100 turns on a toilet-paper tube)", "365 pF variable capacitor (or fixed)", "germanium diode 1N34A or galena crystal + cat's whisker", "high-impedance headphones (2–4 kΩ crystal or piezo)", "wire and clips"],
            "tools": ["wire strippers", "soldering iron OR alligator clips"],
            "steps": ["wind the coil on a paper tube", "connect coil + variable capacitor in parallel = tuned circuit", "connect antenna to one end of coil, ground to the other end", "diode from one end of coil to headphone input", "headphones return to ground", "tune capacitor until station appears", "for selectivity: tap the coil partway down for antenna connection"],
            "time": "1–3 hours",
            "cost_usd_2026": "$10–20 (or $0 from scrounged parts)",
            "scale": "individual; multiple receivers possible from one antenna with isolation",
        },
        "wisdom": "A crystal radio is the cleanest demonstration that information has physical form — strong AM signals literally carry their own energy budget. The Shepherd brings this when the user wants to receive without consuming power, or to understand what radio actually is. Pairs with the Yagi antenna for distant or weak stations.",
        "triggers": {"keywords": ["crystal radio", "diode detector", "AM receiver", "no-power radio", "galena"], "axes": ["information_encoding", "physical_substance"]},
    },
    {
        "id": "patent_yagi_uda_antenna",
        "kind": "patent",
        "title": "Yagi-Uda antenna — 1926, directional gain from parasitic elements",
        "patent": {"kind": "patent", "number": "US 1,860,123 (1932, expired)", "inventor": "Shintaro Uda and Hidetsugu Yagi", "year": 1926, "office": "USPTO"},
        "vertical": "communication",
        "situation": "A driven half-wave dipole + one reflector (5% longer than driven, λ/4 behind) + 1–N directors (each 5% shorter than the previous, λ/4 spacing in front) produces a directional radiation pattern with 6–14 dBi forward gain. The directors are not connected — only inductive coupling reshapes the pattern.",
        "category": "energy",
        "domains": ["physics", "electrical", "networking"],
        "axes": ["physical_substance", "information_encoding", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Phase-shifted re-radiation from parasitics constructively interferes forward and destructively backward. 3-element ≈ 7 dBi; 6-element ≈ 11 dBi.",
            "domain_results": [
                {"domain": "physics","verdict": "CONFIRMED", "detail": "Half-wave dipole λ/2 long; director spacing 0.15–0.25 λ optimum; theoretical max gain ~12 dBi for 6-element", "data": {"gain_dBi_3el": 7, "gain_dBi_6el": 11}},
                {"domain": "electrical","verdict": "CONFIRMED", "detail": "Driven element ~73Ω; matched via balun or gamma match to 50Ω coax", "data": {"Z_dipole_ohm": 73}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["aluminum tubing or rod (1/4\" or 3/8\")", "wood or PVC boom", "balun for coax-to-balanced match (1:1 current balun for 73Ω dipole)", "coax feed line (RG-58 or RG-8)"],
            "tools": ["measuring tape", "saw", "drill", "SWR analyzer (or operate on receive only)"],
            "steps": ["choose frequency f; calculate λ = 300/f(MHz) meters", "build driven dipole 0.48 λ end-to-end, split in center, fed via balun + coax", "reflector 0.51 λ, behind dipole at 0.20 λ", "director 0.45 λ, in front at 0.15 λ", "add additional directors (0.44, 0.43 λ) each at 0.20 λ spacing for higher gain"],
            "time": "build: 1 weekend",
            "cost_usd_2026": "$30–80 for materials",
            "scale": "individual; multiple for TV/UHF reception or amateur radio",
        },
        "wisdom": "The Yagi turned radio from omnidirectional listening into directed link. The Shepherd brings this when the user needs more range, more selectivity, or a quieter receive on a specific direction. LEGAL: receive-only is universally legal; transmitting requires an amateur license in most jurisdictions. Yagi pattern reciprocity means a receive Yagi works as a transmit Yagi if you have permission to transmit.",
        "triggers": {"keywords": ["Yagi antenna", "directional antenna", "amateur radio", "TV antenna", "Yagi-Uda"], "axes": ["physical_substance", "information_encoding"]},
    },
    {
        "id": "patent_morse_code",
        "kind": "patent",
        "title": "Morse code — variable-length encoding (Vail/Morse, 1838)",
        "patent": {"kind": "pd_by_age", "number": "US 1,647 (1840, expired centuries ago)", "inventor": "Samuel Morse + Alfred Vail", "year": 1838, "office": "USPTO"},
        "vertical": "communication",
        "situation": "Morse code maps each letter to a unique sequence of dots (1 unit) and dashes (3 units), with intra-character gaps of 1 unit, inter-character gaps of 3 units, and inter-word gaps of 7 units. Letter frequency in English roughly inversely correlates with code length (E=•, T=-, both single-unit). Practical hand-key speeds: 12–25 WPM; expert operators: 40–60 WPM. Recoverable through noise levels that defeat voice.",
        "category": "networking",
        "domains": ["information_theory", "linguistics", "networking"],
        "axes": ["information_encoding", "time_sequence", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Variable-length prefix code; Vail's frequency analysis of an 1830s printer's type case produced the assignments. An early near-optimal code (Huffman 1952 was provably optimal; Morse came close by inspection).",
            "domain_results": [
                {"domain": "information_theory","verdict": "CONFIRMED", "detail": "Variable-length encoding; average code length ~10 units/letter in English; SNR floor below voice", "data": {"avg_units_per_letter_english": 10}},
                {"domain": "linguistics",       "verdict": "CONFIRMED", "detail": "Code length anti-correlates with letter frequency (Vail's printer type-case analysis)", "data": {}},
            ],
            "axis_overlaps": [{"axis": "information_encoding", "with": ["cryptography", "genetics"], "note": "Variable-length efficient codes appear independently in language, DNA codon usage, and information theory"}],
        },
        "make_it": {
            "materials": ["any signaling device: hand key, flashlight, whistle, paper-and-pen taps"],
            "tools": ["the operator's memorized table"],
            "steps": ["learn the alphabet (most useful as letters: E=•, T=-, A=•-, N=-•, I=••, M=--, S=•••, O=---, H=••••)", "learn distress: SOS = ••• --- •••", "practice at 5 WPM, build to 20+ WPM", "transmit by any modality: key/light/whistle/tap; the code is medium-independent"],
            "time": "30–60 hours to fluency at 15 WPM",
            "cost_usd_2026": "$0",
            "scale": "individual to military networks",
        },
        "wisdom": "Morse outlasts every higher-bandwidth medium because at low SNR a human ear can pull a CW (continuous-wave) signal out of noise that would defeat voice or digital. The Shepherd brings this where bandwidth is scarce, power is limited, or the modality has to be improvised — light, sound, taps. The same code transmits on any carrier the operators agree on.",
        "triggers": {"keywords": ["Morse code", "CW", "continuous wave", "SOS", "variable-length encoding"], "axes": ["information_encoding", "time_sequence"]},
    },
]


# ── 8 ─ HAND TOOLS / SIMPLE MACHINES ──────────────────────────────────
ENTRIES_TOOLS = [
    {
        "id": "patent_safety_bicycle",
        "kind": "patent",
        "title": "Safety bicycle — Rover (Starley, 1885) + pneumatic tire (Dunlop, 1888)",
        "patent": {"kind": "patent_family", "number": "UK 4116 (Starley 1885); UK 10,607 (Dunlop 1888); both long expired", "inventor": "John Kemp Starley / John Boyd Dunlop", "year": 1885, "office": "UKIPO"},
        "vertical": "hand_tools",
        "situation": "Diamond-frame bicycle with same-size wheels, chain drive (typical 2:1 gear ratio at the rear wheel), and pneumatic tires lets a person travel 3–5× their walking speed for the same metabolic cost. ~20 km/h sustainable on flat over hours; 5–10 W/kg metabolic load. Multiplies a human's effective working range by 4–5×.",
        "category": "energy",
        "domains": ["physics", "exercise_science"],
        "axes": ["physical_substance", "metabolism", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Pneumatic tires reduce rolling resistance; same-size wheels permit lower center of gravity (vs. penny-farthing); chain drive lets gear ratio multiply pedaling cadence into wheel speed.",
            "domain_results": [
                {"domain": "physics","verdict": "CONFIRMED", "detail": "Rolling resistance Crr ≈ 0.005 on pavement; aero drag dominates above 25 km/h", "data": {"Crr": 0.005}},
                {"domain": "exercise_science","verdict": "CONFIRMED", "detail": "Cycling is the most metabolically efficient human locomotion: ~5 kJ/(km·kg) vs ~15 for walking", "data": {"kJ_per_km_per_kg_cycling": 5, "kJ_per_km_per_kg_walking": 15}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["frame (welded steel tubing — many homebuilt designs published)", "wheels (most easily harvested)", "drivetrain (cranks, chain, freewheel)", "tires", "saddle, brakes, cables"],
            "tools": ["wrenches, screwdrivers, tire levers", "ideally a workstand"],
            "steps": ["FOR REPAIR — the primary practical case: learn to patch a tube (most failures), adjust a chain, true a wheel, replace a brake cable, set a derailleur. Free Park Tool tutorials online.", "FOR BUILD — frame brazing and wheel building are 20–40 hour skills each; well-documented in PD literature"],
            "time": "repair: 5–60 min per fix. build from scratch: 50–100 hours.",
            "cost_usd_2026": "$0–100 for a used bicycle + parts; $200–800 to build from components",
            "scale": "individual; community bike-shops repair hundreds",
        },
        "wisdom": "The bicycle is the most efficient self-propelled vehicle humans have ever invented. The Shepherd brings this whenever the user needs to extend their walking range without fuel or infrastructure beyond a path. Local repair skills are most of the value — a tire patch is two minutes; a new chain is twenty; the working bicycle keeps working for decades.",
        "triggers": {"keywords": ["bicycle", "safety bicycle", "Starley", "Dunlop", "pneumatic tire", "human transport"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "patent_treadle_pump",
        "kind": "patent",
        "title": "Treadle pump — foot-driven irrigation lift, 5,000–10,000 L/hr",
        "patent": {"kind": "patent_family", "number": "Multiple expired US/IN patents 1970s–1990s (Polak, IDE)", "inventor": "Gunnar Barnes / Paul Polak (IDE) — popularized in Bangladesh", "year": 1981, "office": "USPTO"},
        "vertical": "hand_tools",
        "situation": "Twin-cylinder reciprocating piston pumps driven by foot treadles lift water from up to ~7 m depth at flow rates of 5,000–10,000 L/hr. ~50 W human power input. Each cylinder pulls water on its up-stroke; alternating treadle action keeps continuous flow. Enables irrigation of ~0.4 ha (one acre) of garden vegetables from a single shallow well.",
        "category": "agriculture",
        "domains": ["physics", "agriculture", "exercise_science"],
        "axes": ["physical_substance", "metabolism"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Suction lift limited to ~10 m by atmospheric pressure (29.4 ft water column); practical limit ~7 m due to friction/leakage. Power × time = flow × head × ρg.",
            "domain_results": [
                {"domain": "physics","verdict": "CONFIRMED", "detail": "P = Q × ρgh / η. 50 W × 0.7 efficiency = 35 W to water. At 5 m head: Q = 35/(1000×9.81×5) = 0.71 L/s ≈ 2,500 L/hr", "data": {"P_input_W": 50, "head_m": 5, "Q_L_per_hr": 2500}},
                {"domain": "agriculture","verdict": "CONFIRMED", "detail": "IDE field studies (Bangladesh): 1.5 million units adopted; raised farm incomes 2-3× in coverage areas", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["2 sections of PVC or bamboo cylinder", "2 pistons (wood + leather seal OR molded rubber)", "2 check valves (flap or ball)", "wooden frame and treadles", "suction pipe + foot valve"],
            "tools": ["saw, drill, hammer"],
            "steps": ["build twin cylinders mounted vertically, sealed bottoms with check-valves", "build pistons that fit cylinders snugly with leather/rubber seals", "linkage: treadles connect via cords/rods to piston rods, configured so one up = the other down", "suction pipe from below cylinders down into water source (foot valve at bottom to prevent backflow)", "outlet from top of cylinders to discharge"],
            "time": "build: 1 weekend",
            "cost_usd_2026": "$25–80 from local materials (IDE design point: $25)",
            "scale": "household to small farm",
        },
        "wisdom": "The treadle pump turned subsistence agriculture into market gardening for over a million Bangladeshi families. The Shepherd brings this where surface water exists shallowly (well, pond, river) and the user has more legs than dollars. Trade-off: works only to ~7 m suction lift; deeper wells need positive-displacement pumps at the water level (different design).",
        "triggers": {"keywords": ["treadle pump", "human-powered pump", "irrigation pump", "appropriate technology"], "axes": ["physical_substance", "metabolism"]},
    },
]


# ── 9 ─ SANITATION ────────────────────────────────────────────────────
ENTRIES_SANITATION = [
    {
        "id": "patent_soap_saponification",
        "kind": "patent",
        "title": "Soap by saponification — NaOH + fat → soap + glycerol",
        "patent": {"kind": "pd_by_age", "number": "Industrial soap process: LeBlanc 1791 / Solvay 1861, all PD", "inventor": "predates record; Babylonian tablets c. 2800 BCE", "year": None, "office": None},
        "vertical": "sanitation",
        "situation": "A triglyceride (fat) heated with aqueous NaOH (sodium hydroxide, lye) undergoes saponification: 3 NaOH + triglyceride → 3 sodium salt of fatty acid (soap) + glycerol. Each fat has a specific saponification value (mg KOH/g fat); olive oil ≈ 190; coconut oil ≈ 250. Misalignment of lye-to-fat dose gives either harsh excess-lye soap or oily under-saponified soap. Proper recipe + 4-week cure produces stable bar soap.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "nutrition"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Saponification balances atoms when correct lye-to-fat dose is used. The 'SAP value' table is empirical chemistry that maps each fat to its exact NaOH requirement.",
            "domain_results": [
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "3 NaOH + (RCOO)₃C₃H₅ → 3 RCOO⁻Na⁺ + C₃H₅(OH)₃. Atoms balance.", "data": {"reaction_balanced": True}},
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Surfactant action: hydrophobic tail + hydrophilic head emulsifies oils, lifting microbes and dirt for rinsing", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fats (lard, tallow, olive oil, coconut oil — any combination)", "sodium hydroxide (lye) — pure, food-grade", "distilled water", "essential oils / herbs (optional, for scent)"],
            "tools": ["digital scale (CRITICAL — measure by weight only)", "non-reactive vessel (stainless or HDPE)", "thermometer", "immersion blender (speeds it up)", "mold (loaf pan or silicone)", "safety: goggles + gloves + long sleeves"],
            "steps": ["calculate lye dose from a saponification calculator using fat weights (do NOT guess)", "carefully dissolve lye in water (lye INTO water, never the reverse — exothermic, can boil over)", "let lye-water cool to 38–43°C; warm fats to same temp", "combine, stir/blend until 'trace' (mayonnaise-like thickening)", "pour into mold, insulate 24 hours", "unmold, cut bars, cure 4–6 weeks (excess water evaporates, residual lye fully reacts)"],
            "time": "active: 1 hour. cure: 4–6 weeks before use.",
            "cost_usd_2026": "$0.50–2 per bar (mostly fat cost)",
            "scale": "household to small-business",
        },
        "wisdom": "Soap is the second-oldest sanitation technology after water itself. The Shepherd brings this when fats are available locally — animal lard, beef tallow, used cooking oil all work. WARNING: lye is dangerously caustic; eye splashes are blinding. Always wear goggles, never leave lye-water unattended, keep vinegar nearby to neutralize spills. Calculate dose, never improvise — wrong ratio gives caustic or rancid soap.",
        "triggers": {"keywords": ["soap making", "saponification", "lye", "tallow soap", "cold process soap"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "patent_composting_toilet",
        "kind": "patent",
        "title": "Composting toilet — Clivus Multrum (Lindstrom, 1939, expired)",
        "patent": {"kind": "patent_family", "number": "SE patents from 1939, US derivatives, all expired", "inventor": "Rikard Lindstrom", "year": 1939, "office": "Swedish PRV"},
        "vertical": "sanitation",
        "situation": "Human excreta + carbon cover material (sawdust, leaves, wood ash) at ~30:1 C:N ratio, separated from urine (or co-composted), enters a chamber with passive aeration and slow drainage. Thermophilic phase 55–65°C for >3 days inactivates pathogens; full year-long cycle through multiple bins or compartments produces stable, pathogen-free humanure for non-edible-plant fertilization. Zero water consumed; zero sewage produced.",
        "category": "agriculture",
        "domains": ["chemistry", "biology", "agriculture", "hydrology"],
        "axes": ["metabolism", "conservation_balance", "time_sequence", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Same C:N + moisture + air + time mechanism as conventional composting; the input is just different. WHO Guidelines for safe humanure use exist (2006 + 2018 revisions).",
            "domain_results": [
                {"domain": "biology",  "verdict": "CONFIRMED", "detail": "Pathogen die-off in composting humanure: Salmonella + Ascaris ova both inactivated by either thermophilic phase OR 1-year storage at ambient", "data": {"thermo_T_C": 55, "thermo_days": 3, "ambient_storage_months": 12}},
                {"domain": "chemistry","verdict": "CONFIRMED", "detail": "Sawdust/leaves at ~30:1 C:N balance the high-N fresh waste to a thermophilic-capable mix", "data": {"target_C_to_N": 30}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["composting toilet chamber (homemade bucket system OR commercial unit) — 2+ bins for rotation", "carbon cover: sawdust, leaves, wood ash, peat moss, or shredded paper", "aeration (passive vent stack)"],
            "tools": ["build with basic carpentry"],
            "steps": ["build two separate chambers; use one until full (months), then switch to second while first matures", "every use: cover with one cup of carbon material — eliminates odor, balances C:N", "passive vent stack carries CO₂ and any odor up and out", "after switching: let the full bin sit at least one year (faster if thermophilic + turned)", "use finished humanure on non-edible perennials, fruit trees (trunks, not fruit), or compost again before any food contact"],
            "time": "build: 1 weekend. Each bin cycle: 6–12 months use + 1 year mature.",
            "cost_usd_2026": "$50–300 DIY; $1500–3000 commercial (Sun-Mar, Clivus Multrum)",
            "scale": "household; commercial units serve high-traffic public sites",
        },
        "wisdom": "The composting toilet is the single largest water-and-sewage simplification in the modern household — 30% of indoor water use disappears, and a regulated waste stream becomes a soil amendment. Joseph Jenkins' *Humanure Handbook* (1995, openly licensed) is the practical reference. The Shepherd brings this where water is scarce, where sewage costs/regulations are heavy, or where the user wants to close the nutrient loop. WHO guidelines + local code compliance matter; pathogen safety is achievable but not automatic.",
        "triggers": {"keywords": ["composting toilet", "humanure", "Clivus Multrum", "dry sanitation", "Jenkins method"], "axes": ["metabolism", "conservation_balance"]},
    },
]


ALL_ENTRIES = (
    ENTRIES_WATER
    + ENTRIES_FOOD
    + ENTRIES_SOIL
    + ENTRIES_MEDICINE
    + ENTRIES_ENERGY
    + ENTRIES_SHELTER
    + ENTRIES_COMMS
    + ENTRIES_TOOLS
    + ENTRIES_SANITATION
)


def main() -> int:
    if not ALMANAC.exists():
        print(f"ERROR: almanac file not found at {ALMANAC}")
        return 1

    existing_ids: set[str] = set()
    with ALMANAC.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing_ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass

    to_write = [e for e in ALL_ENTRIES if e["id"] not in existing_ids]
    skipped = [e["id"] for e in ALL_ENTRIES if e["id"] in existing_ids]
    if skipped:
        print(f"skipping (already present): {skipped}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(f"  + {e['id']:50s}  [{e['vertical']:18s}] {e['verdict']}")

    print(f"\n-- appended {len(to_write)} entries to {ALMANAC.name}")
    print("   restart the API server so the almanac re-reads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
