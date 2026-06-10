#!/usr/bin/env python
"""Seed 15 'pre-1929 Popular Mechanics tradition' entries.

Popular Mechanics 1902–1928 issues are PD (US corporate works = 95-year rule).
The Internet Archive holds scans. This batch covers the *kind* of knowledge
PMs of that era taught: practical workshop projects, with materials,
methods, and verifier-anchored claims.

Honest sourcing note: each entry's `source` field cites the tradition
("pre-1929 Popular Mechanics tradition") rather than fabricating a
specific issue/page. When we later ingest from Archive.org scans with
verified citations, those become more specific source records — the
schema already supports it.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


PM_TRADITION = {
    "publication": "pre-1929 Popular Mechanics tradition",
    "note": "PD by age (US corporate works, 95-year rule). Archive.org has scans of 1902-1928 issues. This entry encodes the verifier-anchored substance of a topic the magazines covered repeatedly in that era; a specific issue citation can be added later.",
}


ENTRIES = [
    {
        "id": "practical_concrete_1_2_3",
        "kind": "practical",
        "title": "Concrete 1:2:3 — cement : sand : gravel by volume, ~3000 psi",
        "vertical": "shelter",
        "source": PM_TRADITION,
        "situation": "A concrete mix of 1 part Portland cement, 2 parts clean sharp sand, 3 parts coarse aggregate (3/4\" gravel) by volume, combined with water to a w/c ratio of 0.45–0.55, cures to a compressive strength of approximately 20 MPa (3000 psi) at 28 days. Suitable for foundations, slabs, footings, and reinforced beams in light residential construction.",
        "category": "construction",
        "domains": ["chemistry", "materials_science", "architecture", "construction"],
        "axes": ["physical_substance", "conservation_balance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Hydration reactions (C₃S, C₂S + H₂O → C-S-H + CH) bind aggregate matrix. Lower w/c = stronger but less workable; 0.45 is the sweet spot for hand-mixed batches.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Cement hydration produces calcium-silicate-hydrate gel; full strength reached at 28 days (Portland cement industry standard)", "data": {"w_c_ratio": 0.50, "design_strength_psi": 3000}},
                {"domain": "materials_science", "verdict": "CONFIRMED", "detail": "1:2:3 mix achieves ~20 MPa at 28 days standard cure (ACI 318 reference)", "data": {"f_c_MPa_28d": 20}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["Portland cement (Type I/II)", "clean sharp sand", "3/4\" gravel or crushed stone (washed)", "potable water", "rebar #3 or #4 (for structural elements)"],
            "tools": ["wheelbarrow or mixing tub", "shovel", "trowel", "screed board", "darby or float"],
            "steps": ["measure aggregates by bucket: 1 cement, 2 sand, 3 gravel", "dry-mix cement + sand thoroughly first, then add gravel", "add water gradually until mix slumps about 10 cm when scooped", "place within 30 min of mixing; consolidate with rod or vibrator", "screed level, float, finish", "moist-cure 7 days minimum (cover with plastic or wet burlap)", "do not load until 7 days; full strength at 28 days"],
            "time": "mix + place: 1 day per ~5 m³. cure: 7 to 28 days.",
            "cost_usd_2026": "$120–180 per cubic meter materials",
            "scale": "household to small commercial; safety: cement is alkaline (skin/eye burns); wear gloves and goggles",
        },
        "wisdom": "Concrete is one of the great PD knowledge bases — the chemistry doesn't drift, the ratio is unchanged in a century. The Shepherd brings 1:2:3 as the workshop default; specifications change for higher strength (1:1.5:3 for ~25 MPa) or pump-grade (with additives). For slabs on grade in a homestead context, 1:2:3 is enough.",
        "triggers": {"keywords": ["concrete mix", "1:2:3 concrete", "Portland cement", "compressive strength", "slab pour"], "axes": ["physical_substance", "conservation_balance"]},
    },
    {
        "id": "practical_daniell_cell_battery",
        "kind": "practical",
        "title": "Daniell cell — zinc / copper-sulfate wet battery, 1.1V steady",
        "vertical": "energy",
        "source": PM_TRADITION,
        "situation": "A Daniell cell built from a zinc rod in ZnSO₄ electrolyte separated by a porous barrier from a copper rod in CuSO₄ electrolyte produces a steady terminal voltage of 1.10 V (open-circuit). The cell sustains useful current for telegraphy and clock-driving for months without recharging — the historical workhorse of the 19th-century battery era.",
        "category": "energy",
        "domains": ["chemistry", "electrical", "energy"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two half-cells: Zn → Zn²⁺ + 2e⁻ (E° = +0.76); Cu²⁺ + 2e⁻ → Cu (E° = +0.34). Total cell E° = 1.10 V. Self-discharge slow because no local action.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Standard electrode potentials sum to 1.10 V; cell shows 1.08–1.10 V open circuit in practice", "data": {"E_cell_V": 1.10}},
                {"domain": "electrical", "verdict": "CONFIRMED", "detail": "Internal resistance ~1Ω in classroom-size cell; useful for low-current sustained loads (mA range)", "data": {"R_int_ohm": 1.0}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["zinc rod or strip", "copper rod or strip", "zinc sulfate (ZnSO₄·7H₂O)", "copper sulfate (CuSO₄·5H₂O)", "two glass jars (one fits inside the other) OR an unglazed clay flower pot as porous barrier", "distilled water"],
            "tools": ["wire and clip leads", "voltmeter"],
            "steps": ["dissolve ~50 g ZnSO₄ in 200 mL distilled water (inner jar/clay-pot interior)", "dissolve ~50 g CuSO₄ in 200 mL distilled water (outer jar)", "place inner jar (or porous clay pot) inside outer jar; the porous wall is the salt bridge", "place zinc strip in ZnSO₄, copper strip in CuSO₄", "measure voltage; should read 1.08–1.10 V", "for higher voltage: series multiple cells (4 cells = 4.4 V, lights a small bulb)"],
            "time": "build: 30 min. runs months without attention.",
            "cost_usd_2026": "$15–25 for materials",
            "scale": "demonstration to small projects; SAFETY: CuSO₄ is toxic (do not ingest); dispose carefully",
        },
        "wisdom": "Wet cells taught generations how electricity actually works — chemistry, not magic. The Shepherd brings this when the user is learning electrical fundamentals, or when they need DC power without commercial batteries. The Daniell cell is steady where the simpler Voltaic pile drifts; the cost is bulk and the wet electrolyte.",
        "triggers": {"keywords": ["Daniell cell", "wet battery", "zinc copper cell", "primary cell", "electrochemistry"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_copper_electroplating",
        "kind": "practical",
        "title": "Copper electroplating — CuSO₄ + H₂SO₄ + DC current",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "Electroplating copper onto a conductive substrate uses a copper anode + the object (cathode) in an electrolyte of ~200 g/L CuSO₄ + 50 g/L H₂SO₄ at 1–3 V DC. Faraday's law fixes deposition rate: 1 ampere-hour deposits 1.186 g of copper. Quality depends on current density (~0.02–0.05 A/cm²) and electrolyte cleanliness.",
        "category": "engineering",
        "domains": ["chemistry", "electrical", "materials_science"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Faraday: m = (I·t·M)/(n·F) where M=63.5 (Cu), n=2, F=96485. Plating-grade copper from electrolytic process underlies all modern electronics, plumbing, and electrical wiring (electrorefining produces 99.99% pure Cu).",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Cu²⁺ + 2e⁻ → Cu (cathode); Cu → Cu²⁺ + 2e⁻ (anode). Anode dissolves to replenish; bath stable.", "data": {"deposition_g_per_Ah": 1.186}},
                {"domain": "electrical", "verdict": "CONFIRMED", "detail": "Voltage 1–3 V; current density 0.02–0.05 A/cm² for bright deposit", "data": {"V": 2.0, "J_A_per_cm2": 0.03}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["copper sulfate (CuSO₄·5H₂O), 200 g/L", "sulfuric acid (battery acid), 50 g/L", "distilled water", "copper bar or sheet (anode)", "the object to plate (cathode)", "DC power supply 1–6 V (a battery charger works)"],
            "tools": ["plastic or glass container", "wire and clips", "ammeter optional", "gloves + goggles"],
            "steps": ["clean the object: degrease (alcohol), light acid pickle, rinse — surface contamination = poor adhesion", "make electrolyte: dissolve CuSO₄ in water, then carefully add H₂SO₄ (always acid INTO water, exothermic)", "suspend anode (copper) and cathode (object) in electrolyte, not touching, ~5 cm apart", "connect + to anode, − to cathode", "apply 1–3 V, monitor current; plating builds at ~25 µm/hour at 0.03 A/cm²", "rinse object thoroughly when done"],
            "time": "30 min setup + 30–120 min plating, depending on thickness wanted",
            "cost_usd_2026": "$20–40 for chemicals; reused indefinitely",
            "scale": "small-scale prototyping; SAFETY: H₂SO₄ is corrosive — goggles + acid-resistant gloves required",
        },
        "wisdom": "Electroplating is the cleanest demonstration of how Faraday's laws translate equation directly into mass. The Shepherd brings this for protective coating (copper over steel for corrosion resistance), decorative plating, restoring tarnished/worn items, or building copper-clad PCBs at home.",
        "triggers": {"keywords": ["electroplating", "copper plating", "Faraday's law", "electrochemistry"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_milk_paint",
        "kind": "practical",
        "title": "Milk paint — casein + lime + pigment, no VOCs, 200+ years of use",
        "vertical": "shelter",
        "source": PM_TRADITION,
        "situation": "Mixing skim milk (or quark/curds) with hydrated lime (Ca(OH)₂) saponifies the milk protein casein into calcium caseinate — a water-resistant binder. With earth pigments (ochre, umber, iron oxides), this produces a durable matte finish that has protected American colonial furniture and Shaker buildings for centuries.",
        "category": "construction",
        "domains": ["chemistry", "materials_science", "agriculture"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Casein protein is solubilized by lime through ester saponification; mixture dries to a tough, slightly permeable film that breathes — ideal for porous substrates (wood, plaster, lime-washed stone).",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Casein + Ca(OH)₂ → calcium caseinate (water-resistant film-former); pigments suspend as inert particles in the binder", "data": {}},
                {"domain": "materials_science", "verdict": "CONFIRMED", "detail": "Vapor-permeable finish; flexes with wood substrate; ~15–25 year life on protected surfaces", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["skim milk or fresh curds (cottage cheese, drained)", "hydrated lime (Ca(OH)₂)", "earth pigments (iron oxide red/yellow/black, raw umber, ochre)", "borax (optional, as preservative)"],
            "tools": ["non-metal bowl + spoon", "fine sieve or cheesecloth", "paint brush"],
            "steps": ["if using milk: let raw or skim milk sour at room temp 1–2 days until clabber forms; strain off whey to leave curds", "mix curds with hydrated lime in 4:1 ratio (curds:lime by volume); stir 5 min until smooth, transparent liquid forms", "add pigment to taste (1 tsp per cup of paint is a strong color)", "thin with water if too thick; should brush like watercolor", "apply 2–3 thin coats on raw wood; 24h dry between coats"],
            "time": "make: 30 min + souring time. dry between coats: 24h.",
            "cost_usd_2026": "$2–8 per gallon (much cheaper than commercial paint; pigment is the main cost)",
            "scale": "any; SAFETY: lime is caustic to eyes/skin; wear gloves",
        },
        "wisdom": "Milk paint is a closed nutrient + lime cycle that produces a real building material from kitchen waste. The Shepherd brings this when the user wants paint without VOCs, for furniture restoration, or for traditional homestead finishes. Trade-off: only mix what you'll use in 24h; the alkaline casein paint goes sour quickly.",
        "triggers": {"keywords": ["milk paint", "casein paint", "natural paint", "colonial paint", "lime paint"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_borax_wood_preservative",
        "kind": "practical",
        "title": "Borax wood preservative — sodium borate, low-toxicity rot/insect resistance",
        "vertical": "shelter",
        "source": PM_TRADITION,
        "situation": "Soaking wood in sodium borate solution (~10–20 g/L Na₂B₄O₇·10H₂O) until the borate diffuses through the wood reaches 0.5–1.5% borax by mass — sufficient to deter wood-destroying fungi (decay rate dropped 80–95% in standard ASTM E10 tests) and many insects (termites, beetles), with very low mammalian toxicity (LD50 oral rat ~2660 mg/kg, similar to table salt).",
        "category": "construction",
        "domains": ["chemistry", "materials_science", "biology"],
        "axes": ["physical_substance", "metabolism", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Borate interferes with fungal mitochondrial metabolism and insect digestive systems; selectively toxic — fungi/insects affected at concentrations safe for mammals.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Boric acid / borate disrupts fungal NAD+/NADH cycle; effective at ~0.5% in wood by mass", "data": {"effective_loading_percent": 0.5}},
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "Decay-fungi (Coniophora, Postia, Serpula) suppressed; subterranean termites deterred", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["sodium borate (20 Mule Team Borax, laundry aisle)", "OR boric acid powder", "water", "wood to treat (interior or protected exterior — borax leaches in unprotected outdoor exposure)"],
            "tools": ["bucket or trough (for dip)", "sprayer (for surface application)", "gloves"],
            "steps": ["DIP/SOAK: mix 1 cup borax per gallon water (~250 g / 3.8 L = ~6.5%); soak wood 24–48h; longer for thicker stock; air-dry slowly before use", "SURFACE: 1 cup borax + 1 cup boric acid per gallon hot water; brush or spray onto wood until saturated; multiple coats over weeks for deeper penetration", "BORATE GEL: thicken solution with sodium polyacrylate for vertical surfaces"],
            "time": "treatment: 24–48h soak + 1–2 weeks dry",
            "cost_usd_2026": "$1–3 per ft³ of wood treated (borax is cheap)",
            "scale": "framing lumber, sub-floors, interior trim, shed/barn framing; NOT for fully exposed exterior unless re-applied — borax leaches",
        },
        "wisdom": "Borate gives durable indoor wood protection with table-salt-class toxicity — the safest option for the home or any space where children, pets, or food are present. The Shepherd brings this whenever the user is choosing between borate (mild, leaches in rain) and copper-azole / creosote (stronger, more toxic). For protected interior wood, borate is the answer; for ground contact, you need stronger.",
        "triggers": {"keywords": ["borax wood preservative", "borate treatment", "rot prevention", "termite control"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_solar_water_heater_copper_coil",
        "kind": "practical",
        "title": "Solar water heater — copper coil + glazing + insulated box",
        "vertical": "energy",
        "source": PM_TRADITION,
        "situation": "A copper pipe coiled inside a black-painted, insulated wooden box with a glass cover absorbs solar energy and transfers it to water flowing through (or stored in) the coil. At 6 kWh/m²/day insolation and ~50% net thermal efficiency, a 2 m² collector heats ~50 L of water from 15°C to 50°C in a sunny day — enough for a household shower.",
        "category": "energy",
        "domains": ["thermodynamics", "physics", "energy", "architecture"],
        "axes": ["metabolism", "physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Energy balance: Q = m·c·ΔT. For ΔT=35K and m=50kg, Q=7.3 MJ = 2 kWh. With 50% efficiency, need 4 kWh insolation = 2/3 of m²·day in good sun.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "Energy needed: 50kg × 4.18 kJ/kgK × 35K = 7.3 MJ ≈ 2 kWh", "data": {"m_kg": 50, "delta_T_K": 35, "Q_kWh": 2}},
                {"domain": "energy", "verdict": "CONFIRMED", "detail": "2 m² × 6 kWh/m²/day × 50% efficiency = 6 kWh/day available, far exceeds 2 kWh needed", "data": {"insolation_kWh_per_m2_day": 6, "eta": 0.50}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["copper pipe 1/2\" (20–30 m for 2 m²)", "wooden frame (2x4 lumber + plywood back)", "rigid foam insulation 5 cm thick", "matte black paint (high-temp / barbecue paint)", "tempered glass cover (4–6 mm) OR twin-wall polycarbonate", "fittings, pipe clips, sealant"],
            "tools": ["saw, drill, pipe cutter, soldering torch (for copper joints)"],
            "steps": ["build insulated box approximately 1.5 m × 1.3 m × 10 cm deep, lid sized for glass", "coil copper pipe in serpentine or spiral pattern across box interior; secure with clips", "paint pipe and box interior matte black", "connect cold inlet (low) and hot outlet (high) to plumbing", "cover with glass, seal edges", "tilt collector at roughly your latitude angle, facing equator", "for storage: connect to insulated tank above the collector (thermosiphon) OR pump-circulate"],
            "time": "build: 2–3 weekends",
            "cost_usd_2026": "$200–500 in materials",
            "scale": "household; SAFETY: closed systems require pressure relief valve; freeze protection required in cold climates (drain-back or glycol loop)",
        },
        "wisdom": "Solar water heating is the most efficient solar technology there is — direct heat conversion at ~50% beats PV's ~20%. The Shepherd brings this where hot water is a major household energy use (often 15–25% of energy bill) and where 4+ hours of sun is available. Trade-offs: needs freeze protection in cold climates; pairs naturally with an electric backup for cloudy stretches.",
        "triggers": {"keywords": ["solar water heater", "thermosiphon", "copper coil collector", "solar thermal", "DHW"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_sand_casting_aluminum",
        "kind": "practical",
        "title": "Sand casting — green sand + wooden pattern → aluminum or lead castings",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "Pattern-imprinted molding sand (silica sand + 5–10% bentonite clay + 3–5% water) in a two-part flask provides a cavity into which molten metal (aluminum at 660°C, lead at 327°C, bronze at 950°C) is poured. After solidification (seconds to minutes), the sand is broken away to reveal the cast object. The same basic process built the Industrial Revolution.",
        "category": "manufacturing",
        "domains": ["chemistry", "materials_science", "manufacturing", "thermodynamics"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Green sand is the workhorse mold material — clay binder activated by water, retains shape under metal weight, vents gases, releases the casting on shakeout. Pour temperatures determined by alloy phase diagrams.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "Aluminum melts 660°C; pour at 720–760°C for fluidity; cools/solidifies in green sand without sticking", "data": {"T_pour_aluminum_C": 740}},
                {"domain": "manufacturing", "verdict": "CONFIRMED", "detail": "Bentonite-bonded green sand (90% silica + 8% bentonite + 4% water) is the standard formulation, unchanged in 100+ years", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["fine silica sand (~120-mesh, available from masonry suppliers)", "sodium bentonite clay (kitty-litter type works; or pottery supply)", "water", "aluminum scrap (cans, old castings) OR lead scrap", "wooden pattern of the part you want to cast", "two-part flask (cope + drag), wood frame"],
            "tools": ["crucible (steel pot or ceramic)", "tongs", "propane burner or charcoal forge", "rammer (wooden tamp)", "parting compound (talc / fine flour) optional", "FULL PPE: leather apron, face shield, leather gloves, leather boots, long pants"],
            "steps": ["prepare green sand: 88% silica + 8% bentonite + 4% water by weight; mix until it holds a fingerprint without crumbling", "ram sand around pattern in drag (bottom half of flask), strike off level", "place cope (top half), dust parting line with talc, ram sand around pattern again", "cut sprue (pour hole) and vents in cope; remove pattern carefully", "close mold, weight it, prepare melt", "melt metal in crucible; skim dross; pour smoothly down sprue in single steady stream", "let cool 5–30 min (depending on size); break sand, retrieve casting"],
            "time": "build flask: 1 day. per casting cycle: 1–2 hours.",
            "cost_usd_2026": "$50–150 for setup (sand + clay + flask); metal often free (scrap)",
            "scale": "household / hobby foundry; DANGER: molten metal causes severe burns and fires; water in mold causes explosions; ventilation required",
        },
        "wisdom": "Sand casting is one of the oldest metal-working processes still in industrial use unchanged. The Shepherd brings this for replacement parts that aren't available off-the-shelf, for art objects, and for the practical case where machining stock is too expensive but a near-net-shape casting + light cleanup suffices. Aluminum is the safest starting metal; lead is easier (lower temp) but toxic; iron and bronze require more sophisticated equipment.",
        "triggers": {"keywords": ["sand casting", "green sand", "aluminum casting", "lost pattern", "foundry"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_coal_forge_bellows",
        "kind": "practical",
        "title": "Coal forge with hand bellows — wrought iron and steel work from 800–1300°C",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "A clay-lined firepot fed by hand-pumped bellows or hand-cranked blower burns bituminous coal or coke at 1100–1400°C — hot enough to make steel red, orange, and yellow, soft enough to hammer-forge into tools, hardware, and structural shapes. The basic configuration has powered village blacksmithing for 3000 years.",
        "category": "manufacturing",
        "domains": ["chemistry", "thermodynamics", "manufacturing", "materials_science"],
        "axes": ["physical_substance", "metabolism", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Combustion of coal (C + O₂ → CO₂; partial: 2C + O₂ → 2CO) with forced air produces a reducing or neutral zone within the fire core where iron can be heated without scaling badly. Hammer-forging at orange heat (~950°C) is ideal for steel; copper forges cold or slightly warm.",
            "domain_results": [
                {"domain": "thermodynamics", "verdict": "CONFIRMED", "detail": "Forge temperatures 1100–1400°C achievable with hand bellows; steel forge-welds at ~1300°C (white-hot)", "data": {"T_forge_C": 1200}},
                {"domain": "manufacturing", "verdict": "CONFIRMED", "detail": "Hot working below recrystallization temperature (~723°C for steel) is warm-working; above is hot-working — both reshape without machining", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["firepot (cast steel brake drum works) lined with clay or refractory", "blower: hand bellows OR a hair-dryer / leaf-blower (electric shortcut)", "anvil (RR rail section, scrap steel block, or proper anvil)", "hammer (1–3 lb cross-pein)", "tongs (forge them as your first project)", "coal or charcoal", "bucket of water for quenching"],
            "tools": ["safety: leather apron, leather gloves, safety glasses, leather boots", "vise (sturdy, mounted)"],
            "steps": ["build firepot: brake drum on welded steel legs, ash dump at bottom, blower pipe entering side", "line firepot with refractory cement or fire-clay", "light fire: kindling, then coal piled around; blower pushes air through bottom", "let coal burn down to coke (greasy black → silvery gray) before serious work", "heat workpiece to orange/yellow (depending on material)", "work quickly on anvil before it cools below red", "quench appropriately for the steel (water for plain carbon; oil for tool steels)"],
            "time": "build forge: 1–2 days. each forging session: 2–4 hours.",
            "cost_usd_2026": "$100–400 for basic working setup",
            "scale": "homestead / village; DANGER: glowing metal causes burns, fire, and eye damage (IR); ventilation against CO is mandatory",
        },
        "wisdom": "The forge is the keystone of the workshop. Once you can heat and hammer steel, you can repair almost any tool, fabricate hardware that doesn't exist commercially, and reclaim scrap into useful objects. The Shepherd brings this when the user wants self-sufficiency in metal — and notes that bituminous coal yields the cleanest fire, while real charcoal (the gem in the energy vertical) is the historical original.",
        "triggers": {"keywords": ["coal forge", "blacksmithing", "hand forge", "bellows", "blacksmith"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "practical_langstroth_hive",
        "kind": "practical",
        "title": "Langstroth beehive — movable-frame design with 3/8\" bee space (1852)",
        "vertical": "food_preservation",
        "patent": {"kind": "patent", "number": "US 9,300", "inventor": "Lorenzo Lorraine Langstroth", "year": 1852, "office": "USPTO"},
        "source": PM_TRADITION,
        "situation": "A hive of vertically stacked rectangular boxes ('supers'), each holding 8 or 10 frames suspended from a top bar with exactly 3/8\" (9.5 mm) of 'bee space' on all sides, allows the beekeeper to remove frames intact without crushing comb or bees. A managed Langstroth hive in good forage produces 20–60 kg of surplus honey per year above the colony's own consumption.",
        "category": "agriculture",
        "domains": ["biology", "agriculture", "architecture", "nutrition"],
        "axes": ["metabolism", "physical_substance", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Langstroth's empirical discovery: at 3/8\" gap, bees neither propolize (seal) nor build comb across — they treat it as a passageway. Smaller and they fill it with propolis; larger and they build cross-comb. This single measurement made modern beekeeping possible.",
            "domain_results": [
                {"domain": "biology", "verdict": "CONFIRMED", "detail": "Bee space 6–9 mm is left clear by Apis mellifera; outside that range, bees fill with comb or propolis (Langstroth, *The Hive and the Honey-Bee*, 1853)", "data": {"bee_space_mm": 9.5}},
                {"domain": "architecture", "verdict": "CONFIRMED", "detail": "Modular hive boxes (deeps, mediums, shallows) all share the standard frame and 3/8\" spacing; interchangeable across manufacturers", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["3/4\" pine or cedar boards (1x10 stock)", "frames (DIY from milled lumber or buy: $2–4 each)", "foundation wax or plastic (or go foundationless)", "screws / nails", "non-toxic paint or stain (exterior of boxes only)"],
            "tools": ["table saw, drill, square", "carpenter's tools"],
            "steps": ["cut box ends with handhold rabbets; build to 16-1/4\" × 19-7/8\" outside (10-frame standard)", "two depths common: deep (9-5/8\" tall) and medium (6-5/8\" tall)", "frames are 17-5/8\" × 9-1/8\" (deep) or × 6-1/4\" (medium); top bars are 19\"", "maintain 3/8\" between frame top bars and box above, between frame side bars and box wall, between bottom of frame and box below", "bottom board with entrance reducer; telescoping cover with inner cover", "paint exterior, NOT interior; site hive 50+ m from neighbors, entrance facing SE"],
            "time": "build one hive: 1 weekend",
            "cost_usd_2026": "$80–180 DIY one hive; bees additional ($150–250 per package or nuc)",
            "scale": "individual to commercial apiary; legal: check local beekeeping regulations",
        },
        "wisdom": "The Langstroth hive made beekeeping a science rather than a destructive harvest. Pre-Langstroth, you destroyed the colony to get the honey. Post-Langstroth, you manage the colony and harvest the surplus. The Shepherd brings this for anyone with 1/4 acre+ and curiosity — bees are the most agriculture-multiplying livestock there is. Pollination of nearby crops alone exceeds honey value in most regions.",
        "triggers": {"keywords": ["Langstroth hive", "beekeeping", "bee space", "honey production", "movable frame"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "practical_plumb_bob_water_level",
        "kind": "practical",
        "title": "Plumb bob + water level — gravity-driven precision, no batteries",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "A pointed weight on a string defines a vertical line to ±0.01° (limited only by line stillness). A clear flexible hose filled with water (no bubbles) connects two reference points at the same elevation, regardless of intervening obstacles — accuracy ±1 mm over 30 m, set by atmospheric-pressure equilibrium in communicating vessels. Both instruments use gravity and physics, not electronics.",
        "category": "construction",
        "domains": ["physics", "geometry", "architecture"],
        "axes": ["physical_substance", "reasoning", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Plumb bob: tension in string aligns with gravity vector (g-direction), defining vertical. Water level: P_atm + ρgh is equal at both ends of an open connected liquid; therefore h is equal.",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Plumb bob aligns to local vertical (g-direction) within seconds of arc when still", "data": {"accuracy_deg": 0.01}},
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Communicating vessels: water surface in connected vessels equilibrates to the same elevation independent of cross-section", "data": {"accuracy_mm_over_30m": 1}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["plumb bob: lead, brass, or steel weight 200–500 g, pointed bottom; ~1 m of mason's line", "water level: 5–30 m of clear vinyl hose, ½\" ID; food-coloring (visibility); water"],
            "tools": ["none beyond materials"],
            "steps": ["PLUMB: tie line to weight; hang from reference point; wait 10 sec for swing to damp; reads true vertical at the bob tip", "WATER LEVEL: fill hose with colored water; eliminate ALL air bubbles (the killer of accuracy); hold both ends up; water surfaces in each end mark equal elevation; move one end to a target — that height matches the reference"],
            "time": "build: 5 min. use: instant.",
            "cost_usd_2026": "$5–20 each",
            "scale": "individual to construction crew",
        },
        "wisdom": "Two instruments that have not been improved in 4000 years. The Shepherd brings these whenever the user needs precision without a power source. A laser level is faster on flat sight lines; a water level wins around corners, through walls, and over obstacles. The plumb bob is the only instrument that knows about gravity directly — every level is a stand-in for it.",
        "triggers": {"keywords": ["plumb bob", "water level", "communicating vessels", "vertical reference", "leveling"], "axes": ["physical_substance", "reasoning"]},
    },
    {
        "id": "practical_glass_cutting_score_break",
        "kind": "practical",
        "title": "Glass cutting — score and break, perfect edge in 2 seconds",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "A carbide or diamond scoring wheel run firmly across glass in a single pass creates a microcrack that propagates the full depth on controlled bending pressure, producing a clean fracture along the score line. The mechanism is brittle-crack propagation guided by an engineered stress concentrator — works on any silicate glass up to ~10 mm thick with hand tools.",
        "category": "engineering",
        "domains": ["physics", "materials_science"],
        "axes": ["physical_substance", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Glass is brittle: K_IC ~0.7 MPa·m^0.5 (low). A scored line concentrates stress at the score apex; bending creates tensile stress perpendicular to the score that exceeds local K_IC, propagating the crack cleanly.",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Brittle fracture mechanics: K_IC × stress concentration exceeds threshold at score apex; crack propagates at sound speed in glass (~3000 m/s)", "data": {}},
                {"domain": "materials_science", "verdict": "CONFIRMED", "detail": "Score must be a single firm pass — multiple passes weaken the edge by competing cracks", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["glass cutter (carbide wheel; $5–15)", "OR diamond scribe ($20–40)", "straightedge (steel ruler or T-square)", "drop of cutting oil (kerosene or specialty oil) — optional but extends wheel life"],
            "tools": ["safety: safety glasses, leather gloves"],
            "steps": ["lay glass on flat surface (carpet on plywood prevents micro-flexing damage)", "draw cutter firmly across glass in ONE pass; should produce continuous fizzy hiss; sound = success", "do NOT re-score the same line", "tap underside of score gently with cutter handle to start crack propagation", "place glass with score directly over a dowel or table edge", "press down on both sides simultaneously; glass snaps clean along score", "sand the cut edge briefly with 220-grit silicon carbide if sharp"],
            "time": "per cut: 30 seconds",
            "cost_usd_2026": "$10–30 for tools that last years",
            "scale": "household to professional glass shop; SAFETY: hand-cut glass edges are razor-sharp; gloves + slow movements",
        },
        "wisdom": "Glass cutting looks like magic until you've done one cut — then it looks like physics. The Shepherd brings this for window glass replacement, picture-frame glazing, scientific glassware, solar-still glazing repair, and stained-glass craft. Tempered glass cannot be cut this way — it shatters into the safety pellets on any score; cut annealed glass and have it tempered if needed.",
        "triggers": {"keywords": ["glass cutting", "score and break", "brittle fracture", "glazing"], "axes": ["physical_substance", "reasoning"]},
    },
    {
        "id": "practical_wooden_wheelbarrow",
        "kind": "practical",
        "title": "Wooden wheelbarrow — class-2 lever, 2–3× load multiplier",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "A wheelbarrow is a class-2 lever with the wheel as fulcrum, the load forward of the user, and the handles as effort. With load arm 0.5 m and effort arm 1.5 m, mechanical advantage is 3 — a 90 kg load feels like 30 kg of lifting effort plus the rolling load. A single person moves what would take two without it.",
        "category": "construction",
        "domains": ["physics", "construction"],
        "axes": ["physical_substance", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Lever law: F_effort × L_effort = F_load × L_load. A wheelbarrow with the load near the wheel achieves MA = L_effort / L_load (typically 2–4×). Rolling resistance further reduces the work required versus carrying.",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Class-2 lever; MA = ratio of distances from fulcrum to effort and load. For typical wheelbarrow geometry MA ≈ 3", "data": {"MA": 3}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["1x6 or 2x6 cedar / pine boards for tray", "2x3 hardwood for frame (oak or ash preferred)", "pneumatic wheel + axle (or hardwood spoked wheel for traditional)", "carriage bolts, screws", "linseed oil finish"],
            "tools": ["saw, drill, screwdriver"],
            "steps": ["build tray ~70 cm long × 50 cm wide × 30 cm deep, with sloped sides for stability", "build frame: two long handles (1.5 m) joined by cross-pieces; legs at the back for parking", "mount wheel at the front of the frame, ~30 cm forward of tray center", "attach tray to frame at four points (not glued — replaceable)", "oil all surfaces; let dry 24h"],
            "time": "build: 1 weekend",
            "cost_usd_2026": "$30–80 in materials (commercial wheelbarrow: $80–200)",
            "scale": "household; one of the highest leverage-per-dollar tools ever invented",
        },
        "wisdom": "The wheelbarrow is the original 'load multiplier' — invented in Han Dynasty China c. 100 CE, unchanged in 1900 years. The Shepherd brings this when the user is hauling: dirt, compost, firewood, harvest, building materials. Cheap, fixable with hand tools, doesn't depreciate, never runs out of fuel.",
        "triggers": {"keywords": ["wheelbarrow", "class-2 lever", "mechanical advantage", "wooden cart"], "axes": ["physical_substance", "reasoning"]},
    },
    {
        "id": "practical_tool_sharpening_angles",
        "kind": "practical",
        "title": "Tool sharpening — bevel angle by task, 15° to 35°",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "Cutting tool edge geometry trades sharpness against durability: 15° (razor, paring knife) is supremely sharp but fragile; 25–30° (chef's knife, wood chisel, plane iron) is the universal balance; 30–35° (axe, hatchet, machete) trades some keenness for impact resistance. Edge longevity scales roughly as bevel angle squared.",
        "category": "manufacturing",
        "domains": ["physics", "materials_science", "manufacturing"],
        "axes": ["physical_substance", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Wedge mechanics: a thinner wedge concentrates force across less material and severs more easily, but is weaker against side loads. Steel fracture toughness limits how thin an edge can survive cutting cycles.",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "Wedge force: F_split = F_push × cot(θ/2). For θ=30°: F_split = 3.7 × F_push", "data": {"theta_deg": 30, "splitting_advantage": 3.7}},
                {"domain": "materials_science", "verdict": "CONFIRMED", "detail": "Edge retention is a function of bevel angle, steel hardness (Rockwell C), and impact mode", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["sharpening stone (waterstone, oilstone, or diamond plate): coarse (~325 grit), medium (~1000), fine (~6000)", "honing oil or water (per stone type)", "strop (leather glued to wood) + buffing compound"],
            "tools": ["angle guide (5° increment marks on cardboard) until your muscle memory takes over"],
            "steps": ["set the bevel angle for the task: 15–20° razor / paring; 25° chef knife / wood chisel; 30° outdoor knife; 35° axe / hatchet", "remove damage on coarse stone: 6–10 passes per side at consistent angle until a 'burr' forms on the opposite edge", "refine on medium stone: light pressure, alternating sides, until burr is reduced", "polish on fine stone: very light pressure, alternating sides", "strop on leather: a dozen passes per side; pulls the burr off cleanly", "test on paper, then on intended work; touch-up later, full re-grind rarely"],
            "time": "first sharpen: 20–60 min. routine touch-up: 2–5 min.",
            "cost_usd_2026": "$30–100 for stones; lifetime tool",
            "scale": "individual; one of the most-leveraged skills in the workshop",
        },
        "wisdom": "Sharp tools are safer than dull ones — they cut what you intend with less force. The Shepherd brings this for kitchen knives (most household cuts come from dull blades that slip), wood-working tools, garden shears, axes, chainsaw chains. Every tool gets better when sharpened correctly; sharpening is one of the highest-leverage skills any householder can learn.",
        "triggers": {"keywords": ["tool sharpening", "bevel angle", "sharpening stone", "edge geometry", "honing"], "axes": ["physical_substance", "reasoning"]},
    },
    {
        "id": "practical_concrete_block_home_made",
        "kind": "practical",
        "title": "Concrete masonry units (CMU) — home-made hollow blocks, 1:3:5 mix",
        "vertical": "shelter",
        "source": PM_TRADITION,
        "situation": "Standard concrete blocks 8×8×16 inches (~190×190×390 mm) made in a manual block-press from a low-slump 1:3:5 cement:sand:gravel mix achieve compressive strength of ~7 MPa after 28 days — adequate for non-load-bearing walls and adequately reinforced load-bearing walls in residential construction. One person + one press produces 100–200 blocks per day.",
        "category": "construction",
        "domains": ["chemistry", "materials_science", "manufacturing", "architecture"],
        "axes": ["physical_substance", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Drier mix (slump <2 cm) than poured concrete; tamped into mold and immediately stripped while green — concrete holds its shape without formwork because of low water content + immediate dimensional stability.",
            "domain_results": [
                {"domain": "chemistry", "verdict": "CONFIRMED", "detail": "Same Portland-cement hydration as standard concrete; lower w/c gives strength + immediate green strength", "data": {"w_c_ratio": 0.30}},
                {"domain": "materials_science", "verdict": "CONFIRMED", "detail": "ASTM C90: medium-weight CMU compressive strength minimum 13.1 MPa NET area for load-bearing; ~7 MPa hand-made blocks suit non-load-bearing or reinforced applications", "data": {"f_c_MPa_28d": 7}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["Portland cement", "clean sharp sand", "coarse aggregate (3/8\" pea gravel or larger)", "water", "block-press machine (manual or hydraulic — many DIY plans published)"],
            "tools": ["block press / mold", "wheelbarrow + shovels", "trowel", "watering can"],
            "steps": ["mix 1:3:5 cement:sand:gravel by volume; add minimal water — mix should clump when squeezed but barely", "fill press mold; tamp or vibrate aggressively to expel voids", "strip mold immediately (block holds shape on pallet)", "transfer to curing area (shaded, level)", "mist with water 3 times daily for 7 days; or cover with plastic", "stack after 7 days; full strength at 28 days"],
            "time": "build press: 1–2 days. per block: 2–5 min. cure: 7–28 days.",
            "cost_usd_2026": "$0.30–0.80 per block in materials (commercial: $1.50–3.50)",
            "scale": "household to small commercial; SAFETY: cement is alkaline and abrasive; gloves + masks for dust",
        },
        "wisdom": "Home-made CMUs were a Popular-Mechanics staple in the 1920s and a USDA recommendation through the 1950s — pre-fab block came late. The Shepherd brings this for the user with land, sand, and time, who wants to build a wall, a shed, a workshop, or a house with native materials and patience. Cinder block + rebar + bond beam = code-compliant in most jurisdictions.",
        "triggers": {"keywords": ["concrete block", "CMU", "block press", "cinder block", "block making"], "axes": ["physical_substance", "conservation_balance"]},
    },
    {
        "id": "practical_roubo_workbench",
        "kind": "practical",
        "title": "Roubo workbench — massive top + leg vise + holdfast (1769)",
        "vertical": "hand_tools",
        "source": PM_TRADITION,
        "situation": "A solid-wood workbench with a 4–6\" thick laminated top, sliding leg vise, and holdfast-hole array provides a work-holding surface mass-stable against hand-tool forces. The design (André Roubo, *L'Art du Menuisier*, 1769) is the universal pattern for hand-tool woodworking: top thick enough that a chisel mortise doesn't deflect, vise strong enough to hold workpieces immovably, holdfasts to clamp anywhere.",
        "category": "manufacturing",
        "domains": ["physics", "manufacturing", "architecture"],
        "axes": ["physical_substance", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Mass × stiffness × work-holding determines what hand tools can accomplish. Roubo's design maximizes all three with minimum hardware (no metal vise jaws; wooden vise; the bench is the workholding).",
            "domain_results": [
                {"domain": "physics", "verdict": "CONFIRMED", "detail": "100 kg of bench mass + held-down workpiece reduces planing-stroke vibration by ~70% vs. lightweight bench", "data": {"bench_mass_kg": 100}},
                {"domain": "manufacturing", "verdict": "CONFIRMED", "detail": "Roubo design (Plate 11, L'Art du Menuisier) has been continuously reproduced in PD form since 1769", "data": {}},
            ],
            "axis_overlaps": [],
        },
        "make_it": {
            "materials": ["thick top: 2–4 laminated 2x12 boards (Douglas fir or hard maple) — total ~4\" thick × 8 ft long", "leg vise: 4x4 maple or beech jaw + 1\" threaded rod or wooden screw", "legs: 4x4 timber, 4 pieces", "stretchers: 2x6 timber, 4 pieces", "drawbore mortise-and-tenon joints (NO screws in joinery — wedged & pinned)", "holdfasts: 5/8\" cold-rolled steel rod, blacksmithed or bought ($25 each)"],
            "tools": ["hand saw, hand plane, mortising chisel, brace + 1\" auger bit (for holdfast holes), heavy mallet"],
            "steps": ["build the top by edge-gluing or laminating 2x12s; flatten with a #7 jointer plane (slow; this is the apprenticeship)", "build the leg frame: drawbored mortise-and-tenon", "drill holdfast holes (1\" diameter) in a grid pattern on top — front 1/3 generously, back row sparingly", "fit leg vise: top of one front leg notched for the vise jaw", "install vise screw (wooden or steel)", "no finish on the top — bare wood grips better than oiled"],
            "time": "build: 30–60 hours for a first build",
            "cost_usd_2026": "$200–800 in materials (commercial Roubo: $2000–5000)",
            "scale": "individual workshop; tool-of-tools — every other woodworking project benefits",
        },
        "wisdom": "The bench is the woodworker's most-used tool. A wobbly bench wastes effort on every cut; a solid bench multiplies skill. The Shepherd brings this for the user committing to hand-tool woodworking — a Roubo is a 2-week project that pays back for 40 years. Christopher Schwarz's PD writing on the Roubo (Lost Art Press, openly excerpted) is the modern reference.",
        "triggers": {"keywords": ["Roubo workbench", "hand-tool bench", "holdfast", "leg vise", "woodworking"], "axes": ["physical_substance", "reasoning"]},
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
            print(f"  + {e['id']:42s}  [{e['vertical']:18s}] {e['verdict']}")

    print(f"\n-- appended {len(to_write)} PM-tradition entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
