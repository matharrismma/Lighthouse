"""
seed_domains_wave4.py — Fourth wave: 11 verifier domains with zero seeds
─────────────────────────────────────────────────────────────────────────
Covers: architecture, ecology, history_chronology, law, materials_science,
        nuclear_physics, oceanography, operations_research, philosophy,
        rhetoric, thermodynamics

Usage: python scripts/seed/seed_domains_wave4.py [--delay N] [--dry-run] [--domain D] [--reset]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import requests
except ImportError:
    sys.exit("pip install requests")

API_BASE   = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "seed_state_w4.json"

SEEDS: dict[str, list[str]] = {

    # ── ARCHITECTURE ─────────────────────────────────────────────────────────
    "architecture": [
        "The Vitruvian triad: firmitas (structural strength), utilitas (functional utility), venustas (aesthetic beauty). Vitruvius (1st century BC) established that all three are necessary in good architecture.",
        "Load paths in structural engineering: gravity loads travel from slabs → beams → columns → foundations. Lateral loads (wind, seismic) require shear walls, braced frames, or moment-resisting frames.",
        "Dead load vs live load: dead load = permanent weight of building materials (structure, finishes); live load = variable occupancy and contents. Building codes specify live loads per occupancy type.",
        "The column-and-beam system: post-and-lintel construction spans horizontal elements (beams) between vertical supports (columns). Span limitations drove development of arches, vaults, and trusses.",
        "The arch transfers compressive loads laterally to abutments. Roman masonry arches required centering during construction; the keystone locks the arch under compression. Concrete and steel allow thinner arches.",
        "Flying buttresses (Gothic cathedrals): exterior arched supports transfer lateral thrust from nave vaults over aisles to outer piers, allowing tall, thin walls with large windows (Chartres, Notre-Dame).",
        "Steel frame construction: moment-resisting frames or braced cores resist lateral forces. Shear walls of concrete or steel braced panels carry both gravity and lateral loads.",
        "Reinforced concrete: concrete strong in compression, weak in tension; steel reinforcing bars carry tensile forces. Post-tensioned concrete uses prestressed cables to keep section in compression.",
        "Building codes (IBC, UBC, Eurocodes): prescriptive rules for minimum safety. Zoning codes regulate land use, setbacks, floor-area ratios, and heights. Fire codes require egress, sprinklers, compartmentalization.",
        "Passive solar design: south-facing glass collects winter sun; roof overhangs shade summer sun. Thermal mass (concrete, brick) absorbs heat and releases it at night. Reduces HVAC load.",
        "The Bauhaus (1919-1933): Walter Gropius's school unified art and craft. 'Form follows function' (Sullivan). Industrial materials, rectilinear forms, rejection of ornament. Foundation of modern design education.",
        "Frank Lloyd Wright's organic architecture: buildings should grow from their site. Fallingwater (1935) cantilevered over a waterfall, merging structure with landscape.",
        "Acoustics in architecture: reverberation time RT60 = time for sound to decay by 60 dB. Concert halls target 1.8-2.2s; speech requires < 1.2s. Absorptive surfaces reduce reverberation.",
        "Daylighting: sidelighting (windows) provides uneven distribution; toplighting (skylights, clerestories) is more uniform. Daylight factor = interior illuminance / outdoor illuminance × 100%.",
        "Structural grids: column spacing of 6-9m is efficient for concrete frames; 9-12m for steel. Long spans require deep beams or trusses. Bay size drives floor plate efficiency.",
        "Sustainable architecture (LEED, BREEAM): ratings systems for energy efficiency, water use, indoor air quality, and materials. Net-zero energy buildings produce as much energy as they consume annually.",
        "Egress design: every occupied floor needs at least two exits; exit travel distance limited by code. Stairwells must be fire-rated; elevator lobbies pressurized in high-rises.",
        "The section: a vertical cut through a building reveals spatial relationships between floors, structure, light, and occupancy. Section drawings are essential design tools.",
        "Modular coordination: designing to standard module (100mm or 4 inches) reduces waste and simplifies construction. Dimensional coordination aligns structural grids, ceiling heights, and facade panels.",
        "Historic preservation: the Secretary of the Interior Standards for Rehabilitation: preserve character-defining features, make new work distinguishable, avoid destruction of historic fabric.",
    ],

    # ── ECOLOGY ──────────────────────────────────────────────────────────────
    "ecology": [
        "Trophic levels: producers (plants, autotrophs) → primary consumers (herbivores) → secondary consumers (carnivores) → tertiary consumers → decomposers. Energy transfers at ~10% efficiency per level.",
        "The 10% rule: approximately 10% of energy is transferred from one trophic level to the next. A pyramid of energy is the only ecological pyramid that never inverts.",
        "Food webs vs food chains: food chains are simple linear sequences; food webs show all feeding relationships in an ecosystem. Removal of a keystone species can collapse a food web.",
        "Keystone species: a species with disproportionately large effect on ecosystem structure relative to its biomass. Sea otters (control urchins → protect kelp forests), wolves (Yellowstone trophic cascade).",
        "Primary succession: colonization of bare substrate (lava, glacial till). Pioneer species (mosses, lichens) modify soil, enabling later plant communities. Climax community is the stable endpoint.",
        "Secondary succession: recovery after disturbance (fire, clearing) where soil remains. Faster than primary succession; abandoned fields → shrubs → forest over decades.",
        "Carrying capacity (K): maximum population size an environment can sustain indefinitely, given available resources. Logistic growth: dN/dt = rN(1 - N/K). Population stabilizes at K.",
        "The competitive exclusion principle (Gause): two species competing for identical resources cannot coexist indefinitely; one will be excluded. Niche differentiation allows coexistence.",
        "Niche: the ecological role and space of an organism — what it eats, when and where it feeds, its habitat. Fundamental niche = potential range; realized niche = actual range after competition.",
        "Symbiosis types: mutualism (+/+, both benefit), commensalism (+/0, one benefits, other unaffected), parasitism (+/-, one benefits, other harmed), predation (+/-, prey consumed).",
        "Nutrient cycling: carbon cycle (photosynthesis, respiration, decomposition, fossil fuels), nitrogen cycle (fixation, nitrification, denitrification), phosphorus cycle (weathering, uptake, decomposition).",
        "Biodiversity metrics: species richness (count), Shannon diversity index H = -Σ pᵢ ln pᵢ (abundance and richness), evenness (how equal the abundances are). High diversity confers ecosystem resilience.",
        "Island biogeography theory (MacArthur & Wilson): species richness on islands reflects equilibrium between immigration and extinction rates. Larger islands and closer islands support more species.",
        "Ecosystem services: provisioning (food, water, timber), regulating (climate regulation, water purification, pollination), cultural (recreation, spiritual), supporting (nutrient cycling, soil formation).",
        "Eutrophication: excess nutrient input (nitrogen, phosphorus) causes algal blooms, oxygen depletion (hypoxia), fish kills. Common in fertilizer-impacted waterways. Gulf of Mexico dead zone.",
        "Climate-ecology interactions: phenological mismatches occur when warming shifts species' timing (flowering, migration) at different rates, breaking mutualistic relationships.",
        "Invasive species: non-native species that spread rapidly and cause ecological or economic harm. Absence of natural predators allows unchecked population growth. Chestnut blight, kudzu, zebra mussels.",
        "r-selected vs K-selected species: r-strategists (high reproduction rate, short life, unstable environments — dandelions, mosquitoes); K-strategists (low reproduction, long life, stable environments — elephants, humans).",
        "Decomposers and detritivores: fungi and bacteria break down dead organic matter, recycling nutrients. Detritivores (earthworms, millipedes) physically break down litter, increasing surface area for decomposers.",
        "The Gaia hypothesis (Lovelock): Earth's biota collectively regulate atmospheric chemistry, temperature, and ocean salinity to maintain habitability. A systems-level model of planetary homeostasis.",
    ],

    # ── HISTORY / CHRONOLOGY ─────────────────────────────────────────────────
    "history_chronology": [
        "Historical periodization: prehistory (before writing) → ancient history (c. 3000 BC–500 AD) → medieval (500–1500 AD) → early modern (1500–1800) → modern (1800–present). Periodization is a scholarly tool, not absolute.",
        "Primary vs secondary sources: primary sources are contemporary with events (documents, artifacts, eyewitness accounts); secondary sources analyze primary sources. Tertiary sources synthesize secondary sources.",
        "Source criticism (Quellenkritik): external criticism (is the source authentic? when and where produced?) and internal criticism (is the content reliable? biases? corroboration?).",
        "The Annales school (Braudel): emphasized long-term structures (geography, climate, social patterns) over events and individual actors. Three timescales: longue durée, medium cycles, events.",
        "Dating methods: stratigraphy (older layers beneath newer), dendrochronology (tree rings), radiocarbon dating (C-14 half-life 5,730 years; useful to ~50,000 BP), potassium-argon (millions of years).",
        "The Julian and Gregorian calendars: Julius Caesar introduced the Julian calendar (365.25 days) in 46 BC. The Gregorian reform (1582, Pope Gregory XIII) corrected drift by dropping 10 days and refining leap year rules.",
        "BC/AD vs BCE/CE: Before Christ/Anno Domini are the traditional Western calendar designations. Before Common Era/Common Era are secular equivalents. The year numbering is identical.",
        "The Axial Age (Karl Jaspers): 800–200 BC saw simultaneous emergence of philosophical and religious traditions — Greek philosophy, Hebrew prophecy, Indian Upanishads/Buddhism, Chinese Confucianism.",
        "World history periodization: ancient river civilizations (Mesopotamia, Egypt, Indus, Yellow River) → classical antiquity (Greece, Rome, Han, Maurya) → post-classical (500–1500) → modern age.",
        "Thucydides and the historical method: Thucydides' History of the Peloponnesian War established analysis of cause and effect, human motivation, and eyewitness testimony as historical methodology.",
        "The printing press (Gutenberg, c. 1440): enabled rapid dissemination of ideas, standardization of vernacular languages, the Reformation, and the Scientific Revolution. Information technology as historical driver.",
        "Counterfactual history: 'What if?' questions about alternative outcomes. Methodologically controversial but useful for testing causal claims. Would removing one cause have prevented the outcome?",
        "Whig history: interpreting the past as inevitable progress toward present liberal democratic institutions. Criticized for anachronism and teleology. Historical actors must be understood in their own context.",
        "Historical synchrony: events in different civilizations at the same time that illuminate global patterns. Same century as the American Revolution: the French Revolution, the Industrial Revolution, and end of the Mughal Empire.",
        "The longue durée in Concordance: Scripture provides the longest reliable longue durée — creation to consummation. Historical patterns that span millennia validate the framework; events are symptoms of deeper currents.",
        "Post hoc ergo propter hoc fallacy in historical reasoning: just because B followed A does not mean A caused B. Correlation across historical periods requires controlling for concurrent factors.",
        "Oral history: transmission of history through speech before writing. Carries cultural memory, genealogy, and cosmology. Limited accuracy over long periods (200+ years) due to drift; supplemented by artifacts.",
        "The Dead Sea Scrolls (discovered 1947): biblical manuscripts from 300 BC–70 AD. Confirmed textual accuracy of Hebrew Bible over 1,000 years. Includes all OT books except Esther.",
        "The Reformation (1517, Luther's 95 Theses): challenged papal authority, indulgences, and tradition. Established sola Scriptura. Split Western Christianity into Catholic and Protestant branches. Triggered the Thirty Years' War.",
        "The French Revolution (1789): overturned the ancien régime. Produced the Declaration of the Rights of Man. Radicalized into the Terror. Napoleon stabilized and exported revolutionary ideals across Europe.",
    ],

    # ── LAW ──────────────────────────────────────────────────────────────────
    "law": [
        "The common law system (US, UK, Australia): judge-made law through precedent (stare decisis). Lower courts must follow higher court decisions within the same jurisdiction. Contrast: civil law systems (code-based).",
        "Stare decisis: 'to stand by decided matters.' Binding precedent: courts are bound by higher courts in the same jurisdiction. Persuasive precedent: from other jurisdictions or dissenting opinions.",
        "Sources of law: constitution (supreme), statutes (legislative acts), regulations (agency rules), common law (judicial decisions), treaties. Hierarchy: constitutional law > statutory > regulatory > common law.",
        "Contract elements: offer, acceptance, consideration (something of value exchanged), mutual assent (meeting of minds), capacity (parties must be legally competent), legality (lawful purpose). All required.",
        "Promissory estoppel: even without consideration, a promise may be enforceable if the promisor should have expected reliance, the promisee did rely to their detriment, and injustice would result from non-enforcement.",
        "The elements of a tort: duty, breach, causation (actual and proximate), damages. Negligence = unreasonable failure to exercise duty of care. Intentional torts (assault, battery) require intent; no injury needed for assault.",
        "Strict liability: liability without fault, for abnormally dangerous activities (blasting, keeping wild animals) and product liability. A manufacturer is liable for a defective product even without negligence.",
        "The First Amendment (US): Congress shall make no law respecting an establishment of religion, prohibiting free exercise, abridging freedom of speech or press, peaceful assembly, or petitioning the government.",
        "Due process: procedural due process (fair procedures before life, liberty, or property is deprived) and substantive due process (some rights protected from government intrusion regardless of procedures).",
        "Equal protection (14th Amendment): no state shall deny any person equal protection of the laws. Tiered scrutiny: strict scrutiny (race, national origin, religion → compelling state interest, narrowly tailored); intermediate (gender); rational basis (economic).",
        "Criminal vs civil law: criminal law (state vs. defendant; beyond reasonable doubt; punishment — prison, fines); civil law (plaintiff vs. defendant; preponderance of evidence; remedy — damages, injunction).",
        "Habeas corpus: the right to challenge unlawful detention before a court. Called the 'great writ of liberty.' Suspended only in cases of rebellion or invasion (US Constitution, Article I §9).",
        "Statutory interpretation canons: textualism (plain meaning of words), purposivism (legislative intent), whole-act rule (interpret sections in context of the whole statute), expressio unius (listing some = excluding others).",
        "International law: treaties (binding on signatories), customary international law (widespread state practice accepted as law), jus cogens (peremptory norms — genocide, slavery — no derogation permitted).",
        "The rule against perpetuities: an interest in property must vest, if at all, within 21 years after the death of a relevant life in being at the time of creation. Prevents indefinite tied-up estates.",
        "Fourth Amendment: protection against unreasonable searches and seizures. Warrant requires probable cause and particularity. Exclusionary rule: evidence from illegal searches may be suppressed (Mapp v. Ohio).",
        "Adverse possession: acquiring title to land through open, notorious, exclusive, hostile, and continuous possession for the statutory period. The policy goal is to settle title disputes and put land to productive use.",
        "Mens rea (guilty mind) and actus reus (guilty act): criminal liability typically requires both. Specific intent crimes require intent to achieve a specific result; general intent requires only intent to do the act.",
        "The attorney-client privilege: confidential communications between attorney and client made for the purpose of legal advice are privileged. Exceptions: crime-fraud exception, corporate counsel contexts.",
        "Statute of limitations: time limits within which legal action must be brought. Tolling (pausing the clock) may occur due to discovery rule, minority, or fraudulent concealment. After expiration, claims are barred.",
    ],

    # ── MATERIALS SCIENCE ────────────────────────────────────────────────────
    "materials_science": [
        "The four main materials classes: metals (metallic bonding, ductile, conductive), ceramics (ionic/covalent, hard, brittle, refractory), polymers (covalent chains, lightweight, insulating), composites (combinations).",
        "Crystal structure and defects: metals crystallize in FCC (Al, Cu, Au), BCC (Fe, W), or HCP (Mg, Ti) structures. Point defects (vacancies, interstitials), dislocations, and grain boundaries affect mechanical properties.",
        "Dislocations and plastic deformation: metals deform plastically by dislocation motion. Strengthening mechanisms: work hardening (introduces more dislocations), grain boundary hardening, solution hardening, precipitation hardening.",
        "Stress-strain behavior: elastic region (Hooke's law, σ = Eε, recoverable); yield point (permanent deformation begins); plastic region; ultimate tensile strength; fracture. Young's modulus E measures stiffness.",
        "The iron-carbon phase diagram: key reference for steel behavior. Eutectoid at 0.77 wt% C and 727°C: austenite → pearlite (ferrite + cementite). Steels < 2.14%C; cast irons > 2.14%C.",
        "Heat treatment of steel: annealing (slow cool → soft, ductile), normalizing (air cool → finer structure), quenching (rapid cool → hard martensite), tempering (reheat after quench → toughness). Time-temperature-transformation (TTT) diagrams guide choices.",
        "Corrosion: electrochemical oxidation of metals. Galvanic corrosion: dissimilar metals in contact in electrolyte — less noble metal (anode) corrodes. Prevention: coatings, cathodic protection, alloy selection.",
        "Polymer chains and properties: degree of polymerization n, molecular weight distribution, crystallinity, glass transition temperature Tg. Above Tg: rubbery; below Tg: glassy. Thermoplastics vs thermosets.",
        "Composite materials: fiber-reinforced polymer (FRP) — fibers carry load, matrix transfers load and provides toughness. Rule of mixtures: Ec = Vf · Ef + Vm · Em (longitudinal stiffness). CFRP: high strength-to-weight.",
        "Ceramics: high melting point, hardness, and chemical resistance. Applications: cutting tools (tungsten carbide), thermal barriers (zirconia), electronics (silicon nitride). Brittle — Weibull modulus quantifies flaw sensitivity.",
        "Fatigue failure: cyclic loading below yield stress can cause crack initiation and propagation leading to fracture. S-N curves (Wöhler curves) relate stress amplitude to cycles to failure. Fatigue limit exists in steel.",
        "Creep: time-dependent deformation under constant stress at elevated temperature (> 0.4 Tm). Described by power-law creep: ε̇ = Aσⁿ exp(-Q/RT). Critical for turbine blades and high-temperature structures.",
        "Fracture mechanics: stress intensity factor K = Yσ√(πa) where Y is geometry factor and a is crack length. Critical value KIC (plane strain fracture toughness) determines fracture initiation.",
        "Band theory of solids: energy bands in solids — valence band (filled), conduction band (empty for insulators), band gap. Conductors: overlapping bands; semiconductors: small gap; insulators: large gap.",
        "Semiconductor doping: n-type adds donor atoms (phosphorus in Si, extra electron); p-type adds acceptor atoms (boron in Si, creates hole). p-n junction forms the basis of diodes, transistors, and solar cells.",
        "Nanomaterials: materials with dimensions < 100 nm. Quantum confinement effects emerge. Surface-to-volume ratio increases dramatically. Applications: quantum dots (displays), carbon nanotubes, nanoparticles (catalysts, medicine).",
        "Biomaterials: materials in contact with biological systems. Biocompatibility requires non-toxicity, corrosion resistance, and mechanical compatibility. Ti alloys for implants; PEEK for spinal devices; UHMWPE for joint replacements.",
        "Thermal properties: coefficient of thermal expansion (CTE) — mismatch causes stress in composites and electronic packages. Thermal conductivity (metals: high; ceramics: moderate; polymers: low). Phase changes absorb/release latent heat.",
        "X-ray diffraction (XRD): Bragg's law nλ = 2d sin θ relates X-ray wavelength, lattice spacing, and diffraction angle. Used to identify crystal structure and phase composition. Essential characterization tool.",
        "The processing-structure-property-performance paradigm: all materials science flows from this chain. Processing determines microstructure; microstructure determines properties; properties determine performance.",
    ],

    # ── NUCLEAR PHYSICS ──────────────────────────────────────────────────────
    "nuclear_physics": [
        "Radioactive decay: unstable nuclei emit particles to reach stability. Alpha decay: emits α (²He⁴), reduces A by 4, Z by 2. Beta minus: neutron → proton + e⁻ + antineutrino. Gamma: photon emission from excited state.",
        "Half-life (t₁/₂): time for half of a radioactive sample to decay. N(t) = N₀ · (1/2)^(t/t₁/₂). Carbon-14: t₁/₂ = 5,730 years. Uranium-238: 4.47 billion years. Technetium-99m: 6 hours (medical imaging).",
        "Binding energy: mass of a nucleus is less than the sum of its constituent nucleons (mass defect). Binding energy per nucleon peaks at iron-56 (most stable nucleus). Fusion releases energy below Fe-56; fission above.",
        "Nuclear fission: heavy nuclei (U-235, Pu-239) split into smaller fragments + neutrons + energy. A chain reaction is sustained when each fission event produces ≥1 neutron causing another fission. Critical mass required.",
        "The Manhattan Project (1942-45): US program to develop atomic bombs. Trinity test (July 1945) was first nuclear detonation. Fat Man (plutonium implosion) and Little Boy (uranium gun-type) were used on Japan.",
        "Nuclear reactors: controlled fission chain reaction. Moderator (water, graphite) slows neutrons to thermal velocities. Control rods (boron, cadmium) absorb neutrons to regulate reaction rate. Coolant removes heat.",
        "Nuclear fusion: light nuclei combine to release energy. The D-T reaction (deuterium + tritium → helium + neutron) releases 17.6 MeV. Powers the sun. ITER project: experimental fusion reactor targeting Q > 1.",
        "Radiation types and penetration: alpha (stopped by paper or skin), beta (stopped by a few mm of aluminum), gamma (requires cm of lead or meters of water), neutron radiation (stopped by hydrogen-rich materials like water or polyethylene).",
        "Radiation dose units: gray (Gy) = 1 J/kg absorbed dose; sievert (Sv) = effective dose accounting for radiation type and tissue sensitivity (weighting factors). 1 Sv from whole-body exposure = ~5% lifetime cancer risk.",
        "The liquid drop model of the nucleus: nucleus behaves like an incompressible fluid. Binding energy: volume term + surface term – Coulomb repulsion – asymmetry term. Explains fission barriers and nuclear stability.",
        "The shell model of the nucleus: magic numbers (2, 8, 20, 28, 50, 82, 126) correspond to closed nuclear shells with extra stability. Analogous to electron shells in atoms.",
        "Neutron stars: when massive stars collapse, protons and electrons combine to form neutrons. Neutron stars are ~20 km diameter, ~1.4 solar masses, densities ~10¹⁷ kg/m³. Supported by neutron degeneracy pressure.",
        "Nuclear medicine: PET scans use positron-emitting isotopes (F-18 in FDG glucose). SPECT uses gamma emitters (Tc-99m). Radiotherapy uses targeted radiation (external beam or internal — brachytherapy) to destroy tumors.",
        "The weak nuclear force: governs beta decay and neutrino interactions. Mediated by W and Z bosons (discovered at CERN, 1983). Responsible for hydrogen fusion in the sun (converts protons to deuterium).",
        "Neutrino oscillation: neutrinos change between electron, muon, and tau types as they propagate. Requires non-zero neutrino mass. Confirmed by Super-Kamiokande (1998, Nobel Prize 2015).",
        "Nuclear waste: spent fuel contains highly radioactive fission products (short half-life, intense heat) and transuranic actinides (long half-life). Requires geological isolation (~10,000 years) in stable rock formations.",
        "The nuclear strong force: binds quarks within nucleons; residual strong force binds nucleons. Very short range (~1 fm). Mediated by gluons (quark level) and pions (nucleon level).",
        "Isotopes vs isobars vs isotones: isotopes — same Z, different N (same element); isobars — same A, different Z (different elements); isotones — same N, different Z.",
        "The four fundamental forces: strong (10⁳⁸), electromagnetic (10³⁶), weak (10²⁵), gravity (1) — relative strengths. At very high energies, electroweak unification occurs; grand unification at still higher energies.",
        "Quantum chromodynamics (QCD): theory of the strong force. Quarks carry color charge (red, green, blue); gluons mediate the force. Color confinement: free quarks never observed. Asymptotic freedom: quarks interact weakly at high energy.",
    ],

    # ── OCEANOGRAPHY ─────────────────────────────────────────────────────────
    "oceanography": [
        "Ocean circulation: driven by thermohaline circulation (density differences from temperature and salinity) and wind-driven surface currents. Deep water forms in polar regions where cold, salty water sinks.",
        "The global ocean conveyor belt (thermohaline circulation): surface currents bring warm water poleward; deep water forms in North Atlantic and Antarctic; upwelling returns nutrients to surface. Cycle ~1,000 years.",
        "Ocean layers: mixed layer (0-200m, wind-mixed, warm), thermocline (200-1000m, rapid temperature decrease), deep ocean (> 1000m, near-constant 2-4°C). Permanent thermocline is the barrier to vertical mixing.",
        "Tides: caused by differential gravitational attraction of Moon (and Sun) on Earth's water. Spring tides (new/full moon, aligned): larger range. Neap tides (quarter moon, perpendicular): smaller range. Tidal period ~12.4 hours.",
        "El Niño-Southern Oscillation (ENSO): periodic weakening of trade winds allows warm Pacific water to shift east. El Niño: warm phase, heavy rainfall in Americas, drought in Australia. La Niña: opposite. 3-7 year cycle.",
        "Ocean acidity: CO₂ dissolves in seawater → carbonic acid → bicarbonate + H⁺. Ocean pH has dropped ~0.1 units since industrialization (30% increase in acidity). Threatens coral reefs and shell-forming organisms (aragonite saturation).",
        "The biological pump: photosynthesis in surface ocean fixes CO₂ into organic matter. Dead organisms sink, carrying carbon to deep ocean. Counterbalances CO₂ uptake and affects climate.",
        "Upwelling zones: coastal regions where wind drives surface water offshore, drawing nutrient-rich cold water from depth. Most productive fishing areas (Peru/Chile, California, Benguela). Fuels fisheries.",
        "Ocean salinity: average ~35 ppt (parts per thousand). Controlled by evaporation (+), precipitation (-), river input (-), sea ice formation (+), and ice melting (-). Salinity affects density and sound propagation.",
        "Waves: generated by wind transferring energy to water surface. Wave height and period depend on wind speed, duration, and fetch. Swells are wind waves that have traveled beyond the generating area.",
        "Submarine canyons and mid-ocean ridges: the Mid-Atlantic Ridge is an underwater mountain range formed by seafloor spreading (divergent plate boundary). New crust forms here; continents move apart at ~2-3 cm/year.",
        "Deep sea ecosystems: hydrothermal vents support life via chemosynthesis (no sunlight). Tube worms, clams, and shrimp thrive on H₂S-oxidizing bacteria. Cold seeps are similar but slower.",
        "Marine stratification and dead zones: eutrophication creates algal blooms; decomposition consumes oxygen in bottom waters; hypoxic (< 2 mg/L O₂) conditions kill benthic life. Gulf of Mexico dead zone ~6,000 mi².",
        "The Coriolis effect in the ocean: winds and currents in the Northern Hemisphere deflect to the right; Southern Hemisphere to the left. Creates ocean gyres (rotating current systems) in each major basin.",
        "Bioluminescence: light production by marine organisms (dinoflagellates, deep-sea fish, squid). Used for predation, defense, and communication. Estimated 76% of deep-sea species are bioluminescent.",
    ],

    # ── OPERATIONS RESEARCH ──────────────────────────────────────────────────
    "operations_research": [
        "Linear programming (LP): optimize a linear objective function subject to linear inequality constraints. Feasible region is a convex polytope; optimal solution is at a vertex.",
        "The simplex method (George Dantzig, 1947): iterates along vertices of the LP feasible region. Exponential worst-case but polynomial on average; practical for thousands of variables.",
        "Duality in LP: every LP (primal) has a dual LP. Weak duality: primal objective ≥ dual objective. Strong duality: optimal values are equal at optimality (when finite). Complementary slackness conditions.",
        "Integer programming (IP): LP with integer constraints. NP-hard in general. Solved by branch-and-bound, cutting planes, or branch-and-cut. Used in scheduling, routing, facility location.",
        "The traveling salesman problem (TSP): find the shortest route visiting each city exactly once and returning to start. NP-complete for exact solution. Approximation algorithms: nearest neighbor (heuristic), Christofides (1.5× optimal).",
        "Queuing theory: analyzes waiting lines. M/M/1 queue (Poisson arrivals, exponential service, 1 server): average queue length L = λ/(μ-λ); average wait W = 1/(μ-λ). Little's law: L = λW.",
        "Little's Law (John Little, 1961): L = λW. Average number in system = arrival rate × average time in system. Applies to any stable queuing system, regardless of distribution or service order.",
        "The knapsack problem: maximize total value of items placed in a knapsack with weight limit W. 0/1 knapsack: DP solution O(nW). Fractional knapsack: greedy by value/weight ratio.",
        "Network flow problems: max-flow min-cut theorem (Ford-Fulkerson): the maximum flow from source to sink equals the minimum cut capacity. Ford-Fulkerson algorithm finds max flow via augmenting paths.",
        "Shortest path algorithms: Dijkstra (non-negative weights, O((V+E) log V)), Bellman-Ford (negative weights, O(VE)), Floyd-Warshall (all-pairs, O(V³)).",
        "Simulation (Monte Carlo): using random sampling to estimate quantities that are hard to compute analytically. Applications: financial risk, system reliability, nuclear reactor design. Key: enough samples for convergence.",
        "Markov Decision Processes (MDPs): framework for sequential decision-making under uncertainty. States, actions, transition probabilities, rewards. Optimal policy found by dynamic programming (Bellman equation) or reinforcement learning.",
        "Game theory in OR: Nash equilibrium — no player benefits from unilateral deviation. Zero-sum games solvable by LP. Non-zero-sum games require equilibrium concepts. Prisoner's dilemma is canonical.",
        "Project scheduling: Critical Path Method (CPM) finds the longest path through the project network — the critical path determines minimum project duration. Slack = latest start - earliest start.",
        "PERT (Program Evaluation and Review Technique): like CPM but uses probabilistic activity durations (optimistic, most likely, pessimistic). Expected duration = (a + 4m + b)/6. Variance = ((b-a)/6)².",
        "Inventory management: Economic Order Quantity (EOQ) = √(2DS/H) where D=annual demand, S=order cost, H=holding cost per unit per year. Minimizes total inventory cost.",
        "Multi-criteria decision analysis (MCDA): decision problems with multiple competing objectives. AHP (Analytic Hierarchy Process), TOPSIS, weighted sum model. Requires eliciting decision-maker preferences.",
        "Robust optimization: finds solutions that remain feasible and near-optimal for all realizations of uncertain parameters within a defined uncertainty set. Trades expected performance for worst-case guarantee.",
        "Stochastic programming: optimization with random parameters. Two-stage: first-stage decisions made before uncertainty realized; second-stage recourse decisions made after. Minimize expected cost.",
        "Revenue management (yield management): airlines, hotels use dynamic pricing to maximize revenue from fixed capacity. Key insight: seat/room sold to lower-value customer prevents sale to higher-value customer later.",
    ],

    # ── PHILOSOPHY ───────────────────────────────────────────────────────────
    "philosophy": [
        "Epistemology asks: what is knowledge? The traditional definition (Plato): justified true belief (JTB). Gettier cases (1963) showed JTB is insufficient — counterexamples where someone has JTB but clearly lacks knowledge.",
        "The problem of induction (Hume): inductive reasoning assumes the future will resemble the past. But this assumption is itself inductive — we cannot justify induction without circularity. Popper's response: falsifiability.",
        "Popper's falsificationism: science progresses by making falsifiable predictions and testing them. Theories that can in principle be falsified are scientific; those that cannot are metaphysical. Unfalsifiable theories should be rejected.",
        "Ontology: the study of being and existence. What kinds of things exist? (particulars, universals, abstract objects, possible worlds, mental states). Realism vs anti-realism about categories.",
        "The mind-body problem: how does mind relate to body? Substance dualism (Descartes): mind and body are distinct substances. Physicalism: mind supervenes on the physical. The hard problem (Chalmers): why is there subjective experience?",
        "Functionalism: mental states are defined by their functional roles (inputs, outputs, other mental state relations), not their physical substrate. Implies multiple realizability — different physical systems could have the same mental states.",
        "Deontological ethics (Kant): actions are right or wrong independent of consequences. The categorical imperative: act only according to maxims you could will to be universal laws. Treat persons as ends, never merely as means.",
        "Consequentialism (utilitarianism): the right action maximizes aggregate welfare (utility). Bentham: quantity of pleasure; Mill: quality matters. Peter Singer: all sentient beings' interests count equally.",
        "Virtue ethics (Aristotle): the right action is what a virtuous person would do in the circumstances. Focus on character traits (virtues: courage, honesty, practical wisdom) rather than rules or consequences.",
        "The trolley problem (Foot, Thomson): is it morally permissible to pull a lever to divert a trolley, killing 1 to save 5? Contrasted with footbridge case: push a large man off a bridge to stop the trolley? Reveals deontological intuitions.",
        "The social contract (Hobbes, Locke, Rousseau): political legitimacy derives from a (hypothetical) contract among individuals. Hobbes: strong sovereign needed to prevent war of all against all. Locke: government must protect natural rights.",
        "Plato's theory of Forms: material objects are imperfect copies of eternal, abstract Forms (the Form of Beauty, Justice, Good). Knowledge is of Forms; perception is of changing copies. Allegory of the Cave.",
        "Aristotle's four causes: material cause (what it's made of), formal cause (what form it has), efficient cause (what made it), final cause (what it's for/its function). Teleology is embedded in nature.",
        "The problem of universals: do universal properties (redness, triangularity) exist independently of particulars? Realism (yes, universals exist), nominalism (only particulars exist), conceptualism (universals are concepts).",
        "Phenomenology (Husserl, Heidegger, Merleau-Ponty): philosophical method that examines conscious experience from the first-person perspective. Bracketing presuppositions; studying intentionality (the 'aboutness' of consciousness).",
        "The is-ought gap (Hume's guillotine): you cannot derive an 'ought' statement from 'is' statements alone. Moral conclusions require at least one moral premise. Naturalistic fallacy: defining 'good' as a natural property.",
        "Free will vs determinism: hard determinism (all events causally determined, free will an illusion), compatibilism (free will compatible with determinism — acting from one's own desires without coercion), libertarianism (agent causation breaks causal chains).",
        "The veil of ignorance (Rawls): to design just social institutions, imagine choosing without knowing your place in society (race, class, gender). Leads to the difference principle: inequalities justified only if they benefit the worst-off.",
        "Epistemic humility and the Socratic method: 'I know that I know nothing.' Wisdom begins with recognizing the limits of one's knowledge. Socrates' questioning method exposed hidden assumptions and revealed ignorance.",
        "The relationship of faith and reason: Augustine — 'faith seeking understanding' (fides quaerens intellectum). Reason is not the ground of faith but the instrument for exploring what is believed. Anselm's ontological argument is reason within faith.",
    ],

    # ── RHETORIC ─────────────────────────────────────────────────────────────
    "rhetoric": [
        "Aristotle's three modes of persuasion: ethos (credibility of the speaker), pathos (emotional appeal to the audience), logos (logical appeal — evidence and reasoning). Effective rhetoric uses all three.",
        "The ad hominem fallacy: attacking the person making the argument rather than the argument itself. Abusive ad hominem: personal insult. Circumstantial ad hominem: claiming bias. Tu quoque: 'you do it too.'",
        "Straw man fallacy: misrepresenting an opponent's argument to make it easier to attack. The response addresses the distorted version, not the actual claim.",
        "False dichotomy (false dilemma): presenting only two options when more exist. 'You're either with us or against us.' Ignores the spectrum of possibilities.",
        "Appeal to authority (argumentum ad verecundiam): using authority as evidence. Legitimate when the authority is genuinely expert and there is consensus. Fallacious when the authority is irrelevant, biased, or disputed.",
        "The slippery slope fallacy: claiming that one step will inevitably lead to extreme consequences without adequate justification of the causal chain. Some slippery slope arguments are legitimate (when mechanism is specified).",
        "Post hoc ergo propter hoc: 'after this, therefore because of this.' Confusing temporal succession with causation. Classic example: Rooster crows; sun rises; therefore rooster causes sunrise.",
        "Begging the question (circular reasoning): the conclusion is assumed in the premises. Not to be confused with 'raises the question.' Example: 'The Bible is true because it says so.'",
        "The Toulmin model of argument: claim (conclusion), grounds (evidence/data), warrant (principle connecting grounds to claim), backing (support for the warrant), qualifier (strength of claim), rebuttal (exceptions).",
        "Anaphora and other rhetorical figures: anaphora = repetition at the beginning of successive clauses ('I have a dream…'). Chiasmus = inverted repetition ('Ask not what your country can do for you…'). Antithesis = contrasting ideas in parallel structure.",
        "Kairos: the opportune moment in rhetoric — the right time and place for a particular argument. What is persuasive depends on context, audience, and timing. Missing kairos can doom a sound argument.",
        "The burden of proof: he who makes a claim bears the burden of proof. 'Shifting the burden' to the opponent requires them to disprove. Extraordinary claims require extraordinary evidence.",
        "Equivocation: using a word with multiple meanings in different senses within the same argument. 'Laws of nature are laws; laws require a lawgiver; therefore nature has a lawgiver.' 'Law' shifts meaning.",
        "Hasty generalization: drawing a universal conclusion from too few examples. A sample of one or two does not establish a rule. Sample bias compounds the problem.",
        "The Gish Gallop: overwhelming opponents with many weak arguments faster than they can be refuted. Each argument may be trivially rebutted but the volume creates an impression of strength. Used in formal debates by bad-faith actors.",
        "Rhetoric in preaching (homiletics): sermon structure (text, exposition, application); illustration as bridge between abstraction and experience; inductive vs deductive preaching; Haddon Robinson's 'big idea' approach.",
        "Rogerian rhetoric: aims to reduce conflict and promote understanding by first demonstrating genuine comprehension of the opponent's position before presenting one's own. Carl Rogers' empathic listening applied to argument.",
        "The principle of charity: interpret ambiguous arguments in their strongest form before critiquing. Steel-manning: actively constructing the best version of the opposing argument. Intellectual honesty requires this.",
        "Propaganda techniques: bandwagon appeal, name-calling, glittering generalities (vague positive words), card stacking (one-sided evidence), plain folks appeal, testimonial. Identified by the Institute for Propaganda Analysis (1938).",
        "Logos and the Christian tradition: in John 1:1, logos (word, reason) is identified with Christ. The Christian intellectual tradition holds that reason is a God-given faculty for understanding His creation — not opposed to faith.",
    ],

    # ── THERMODYNAMICS ───────────────────────────────────────────────────────
    "thermodynamics": [
        "Zeroth Law: if A is in thermal equilibrium with B, and B with C, then A is in thermal equilibrium with C. This makes temperature a well-defined property and is the basis of thermometry.",
        "First Law: energy is conserved. ΔU = Q - W. Internal energy U increases when heat Q flows in or work W is done on the system. Equivalently: you cannot build a perpetual motion machine of the first kind.",
        "Second Law: in any spontaneous process, total entropy of the universe increases. ΔS_universe ≥ 0. Entropy of an isolated system never decreases. This gives time its arrow and limits heat-to-work conversion.",
        "Third Law: the entropy of a perfect crystal at absolute zero is zero. S(0K) = 0. Implies that absolute zero is unattainable (Third Law of thermodynamics). Residual entropy exists for disordered crystals.",
        "The Carnot cycle: the most efficient heat engine operating between temperatures T_H and T_C has efficiency η = 1 - T_C/T_H. All heat engines are less efficient than Carnot. T must be in Kelvin.",
        "Entropy statistical definition (Boltzmann): S = k_B ln Ω, where Ω is the number of microstates consistent with the macrostate. Inscribed on Boltzmann's tombstone. Connects thermodynamics and statistical mechanics.",
        "Gibbs free energy G = H - TS: G < 0 means a process is spontaneous at constant T and P. ΔG = ΔH - TΔS. Chemical equilibrium: ΔG = 0. Phase transitions occur when G of phases are equal.",
        "Enthalpy H = U + PV: heat transferred at constant pressure equals ΔH. Standard enthalpies of formation allow calculating reaction enthalpies via Hess's law: ΔH_rxn = Σ ΔH_f(products) - Σ ΔH_f(reactants).",
        "The heat equation: ∂T/∂t = α ∇²T, where α = k/(ρc_p) is thermal diffusivity. Describes how temperature distributes over time. Fourier's law q = -k ∇T defines heat flux.",
        "Thermodynamic cycles in engineering: Rankine cycle (steam power plants), Brayton cycle (gas turbines, jet engines), refrigeration cycle (reversed Carnot). Each cycle's efficiency bounded by Carnot limit.",
        "Heat transfer modes: conduction (Q = kAΔT/L), convection (Q = hA(T_s - T_∞)), radiation (Q = εσAT⁴, Stefan-Boltzmann law). All three act simultaneously in most real systems.",
        "Phase diagrams: P-T diagram shows solid, liquid, gas phases, triple point (all three phases coexist), and critical point (liquid and gas become indistinguishable). Clausius-Clapeyron equation governs the slopes of phase boundaries.",
        "The ideal gas law PV = nRT is a limiting case. Real gases deviate at high pressure or low temperature. Van der Waals equation (P + a/V²)(V - b) = nRT corrects for intermolecular forces and molecular volume.",
        "Maxwell's demon (thought experiment): a demon controlling a gate between gas compartments could sort fast molecules without doing work, apparently violating the Second Law. Resolution: the demon must erase its memory (Landauer's principle), which costs entropy.",
        "The Maxwell-Boltzmann distribution: speeds of molecules in an ideal gas follow this distribution. Most probable speed v_mp = √(2RT/M); mean speed v̄ = √(8RT/πM); rms speed v_rms = √(3RT/M).",
        "Irreversibility and entropy production: all real processes are irreversible due to friction, heat transfer across finite temperature differences, and mixing. Reversible processes are idealizations that maximize work output.",
        "Exergy (available work): the maximum useful work extractable as a system comes to equilibrium with its environment. Exergy analysis identifies where irreversibilities occur and how to improve system efficiency.",
        "The equipartition theorem: at thermal equilibrium, each quadratic degree of freedom has energy ½k_BT. Monatomic ideal gas: 3 translational DOF → U = 3/2 nRT. Diatomic: +2 rotational → U = 5/2 nRT.",
        "Absolute temperature and the Kelvin scale: temperature is a measure of average thermal energy. Absolute zero (0 K = -273.15°C) is the theoretical minimum. The Kelvin scale is fundamental in thermodynamics.",
        "Black body radiation: a perfect absorber/emitter at temperature T radiates with spectrum given by Planck's law. Total power: P = σAT⁴ (Stefan-Boltzmann). Wien's displacement law: λ_max T = 2.898 × 10⁻³ m·K.",
    ],
}


# ── Runner ────────────────────────────────────────────────────────────────────

def load_state() -> set:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return set(data.get("posted", []))
        except Exception:
            return set()
    return set()

def save_state(posted: set):
    STATE_FILE.write_text(
        json.dumps({"posted": sorted(posted)}, indent=2),
        encoding="utf-8"
    )

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def post_seed(session: requests.Session, domain: str, text: str, dry_run: bool) -> bool:
    fp = fingerprint(text)
    preview = text[:60].replace("\n", " ")
    if dry_run:
        print(f"  [DRY] {domain}: {preview}…")
        return True
    payload = {
        "text": text,
        "source": f"seed:{domain}",
        "tags": [domain, "seed", "curated"],
    }
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        total = (data.get("calibration") or {}).get("total_entries_to_date", "?")
        print(f"  ✓ [{domain}] #{total}  {preview}…")
        return True
    except Exception as e:
        print(f"  ✗ [{domain}] {e}  {preview}…")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Run only this domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    posted = set() if args.reset else load_state()
    session = requests.Session()

    domains = {args.domain: SEEDS[args.domain]} if args.domain else SEEDS

    total_seeds = sum(len(v) for v in domains.values())
    total_new = sum(
        1 for seeds in domains.values()
        for s in seeds if fingerprint(s) not in posted
    )
    print(f"\nWave 4 — {total_seeds} seeds across {len(domains)} domains")
    print(f"Already posted: {len(posted)}  New: {total_new}\n")

    for domain, seeds in domains.items():
        new_in_domain = [s for s in seeds if fingerprint(s) not in posted]
        if not new_in_domain:
            print(f"── {domain.upper()} — all {len(seeds)} already posted, skipping")
            continue

        print(f"\n── {domain.upper()} ({len(new_in_domain)} new / {len(seeds)} total) ──")
        for text in new_in_domain:
            fp = fingerprint(text)
            ok = post_seed(session, domain, text, args.dry_run)
            if ok and not args.dry_run:
                posted.add(fp)
                save_state(posted)
            if not args.dry_run:
                time.sleep(args.delay)

    print(f"\nDone. Total posted this run: {total_new if not args.dry_run else 0}")


if __name__ == "__main__":
    main()
