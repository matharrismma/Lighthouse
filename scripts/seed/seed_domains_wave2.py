"""
seed_domains_wave2.py — Second wave of domain seeds for Concordance
───────────────────────────────────────────────────────────────────
Covers the 24 domains not seeded in wave 1:
  agriculture, astronomy, chemistry, combinatorics, construction,
  cryptography, cybersecurity, electrical, energy, exercise_science,
  finance, genetics, geology, geometry, geography, labor, music_theory,
  networking, nutrition, quantum_computing, real_estate, soil_science,
  sports_analytics, agriculture

Usage: python scripts/seed/seed_domains_wave2.py [--delay N] [--dry-run]
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
STATE_FILE = Path(__file__).parent / "seed_state_w2.json"

SEEDS: dict[str, list[str]] = {

    # ── AGRICULTURE ──────────────────────────────────────────────────────────
    "agriculture": [
        "Crop rotation replaces the same crop each season with different crops in sequence, reducing soil-borne disease, replenishing soil nutrients, and breaking pest cycles.",
        "Nitrogen fixation: legumes (soybeans, clover, alfalfa) host Rhizobium bacteria in root nodules that convert atmospheric N₂ to ammonium, enriching soil without synthetic fertilizer.",
        "The NPK ratio on fertilizer labels indicates percent nitrogen (N), phosphorus (P₂O₅), and potassium (K₂O). 10-10-10 is a balanced all-purpose fertilizer.",
        "Irrigation efficiency: flood irrigation (50-60% efficient), sprinkler (75-85%), drip irrigation (90-95%). Drip delivers water directly to root zones, minimizing evaporation.",
        "The Green Revolution (1960s-70s): development of high-yield crop varieties, synthetic fertilizers, and pesticides dramatically increased food production, preventing famines.",
        "Integrated pest management (IPM) uses biological, cultural, and chemical controls in combination, minimizing pesticide use while achieving economic pest control thresholds.",
        "Soil pH affects nutrient availability. Most crops grow best at pH 6.0-7.0. Lime raises pH; sulfur lowers it. Aluminum toxicity causes problems below pH 5.5.",
        "Cover crops (rye, clover, buckwheat) are grown between main crops to prevent erosion, build organic matter, fix nitrogen, and suppress weeds.",
        "The Dust Bowl (1930s): unsustainable dryland farming stripped native grasses, leaving topsoil vulnerable to wind erosion during drought. A lesson in land stewardship.",
        "Polyculture grows multiple crops together, mimicking natural ecosystems. The Three Sisters (corn, beans, squash) is a Native American polyculture: beans fix nitrogen, squash shades weeds.",
        "Vernalization: some crops (wheat, barley) require a period of cold temperatures to trigger flowering. Winter wheat is planted in fall, vernalized in winter, harvested in summer.",
        "Photosynthetically active radiation (PAR): plants use light between 400-700 nm wavelengths. Canopy architecture, row spacing, and planting density affect PAR interception.",
        "Soil organic matter decomposition by microbes releases nutrients; humus improves soil structure, water retention, and cation exchange capacity. Each 1% organic matter holds ~16,500 gal/acre water.",
        "Food security requires four pillars: availability (sufficient food production), access (economic and physical), utilization (nutritional quality and safety), and stability over time.",
        "Agroforestry integrates trees, crops, and livestock. Trees provide windbreaks, fix nitrogen, prevent erosion, and diversify income while crops grow between rows.",
        "The bread basket regions (US Great Plains, Ukrainian steppe, Argentinian Pampas, Australian wheat belt) produce the majority of the world's cereal grain exports.",
        "Precision agriculture uses GPS, remote sensing, and variable-rate technology to apply inputs (fertilizer, pesticide, water) only where needed, reducing waste and cost.",
        "Grain storage: moisture content below 13-14% prevents fungal growth. Hermetic storage eliminates oxygen, controlling insects without pesticides. USDA grades set quality standards.",
        "Biblical agriculture: the Mosaic law established gleaning rights (Leviticus 19:9-10) — farmers leave field edges unharvested for the poor. Justice and provision woven into land use.",
        "The sabbatical year (shmita): every seventh year, land rests — no planting, pruning, or harvesting (Leviticus 25:1-7). Soil restoration, debt release, and trust in God's provision.",
        "Grafting joins a scion (desired variety) to a rootstock to combine disease resistance, vigor, and fruit quality. Romans 11:17-24 uses grafting as a theological metaphor.",
        "Heirloom seeds are open-pollinated varieties maintained across generations with stable traits. Hybrid F1 seeds offer vigor but don't breed true — requiring annual seed purchase.",
        "Water-use efficiency (WUE) = biomass produced / water consumed. Drought-tolerant crops (sorghum, millet, chickpea) produce more biomass per unit water than maize or wheat.",
        "Composting converts organic waste into humus through aerobic microbial decomposition. A proper compost pile needs C:N ratio ~25:1, moisture ~50%, and turning for aeration.",
        "Arable land is declining per capita globally as population grows and soil degrades. Regenerative agriculture — minimum tillage, cover crops, compost — aims to rebuild soil health.",
    ],

    # ── ASTRONOMY ────────────────────────────────────────────────────────────
    "astronomy": [
        "A light-year is the distance light travels in one year: approximately 9.461 × 10¹⁵ meters or 5.879 × 10¹² miles. The nearest star system (Alpha Centauri) is 4.37 light-years away.",
        "The observable universe spans about 93 billion light-years in diameter. The universe is ~13.8 billion years old, but expansion has stretched the distance to the cosmic horizon.",
        "Kepler's first law: planets orbit the Sun in ellipses with the Sun at one focus. Kepler's second law: a line from the Sun to a planet sweeps equal areas in equal times.",
        "Kepler's third law: T² ∝ a³. The square of the orbital period is proportional to the cube of the semi-major axis. Applies to all objects orbiting the same body.",
        "The Hertzsprung-Russell (H-R) diagram plots stars by luminosity vs. temperature. The main sequence is where hydrogen-burning stars spend most of their lives. The Sun is a G-type main-sequence star.",
        "Stellar evolution: low-mass stars become red giants, shed outer layers as planetary nebulae, leaving white dwarf remnants. High-mass stars end as supernovae, leaving neutron stars or black holes.",
        "A black hole forms when mass is compressed within its Schwarzschild radius. The event horizon is the boundary beyond which nothing — not even light — can escape.",
        "The cosmic microwave background (CMB) is thermal radiation left over from the recombination epoch ~380,000 years after the Big Bang, at a temperature of 2.725 K.",
        "Dark matter makes up ~27% of the universe's energy density. It does not interact with light but affects galaxy rotation curves and large-scale structure formation.",
        "Dark energy (~68% of universe energy density) is the unknown cause of the universe's accelerating expansion, detected by Type Ia supernova observations in 1998.",
        "The Milky Way is a barred spiral galaxy ~100,000 light-years in diameter containing ~200-400 billion stars. The Sun is located ~27,000 light-years from the galactic center.",
        "A parsec (pc) = 3.086 × 10¹⁶ m = 3.26 light-years. Defined as the distance at which one astronomical unit subtends one arcsecond of angle — the basis of parallax measurement.",
        "The Drake equation estimates the number of communicating civilizations in the galaxy: N = R* × fₚ × nₑ × fₗ × fᵢ × fc × L. Most terms are highly uncertain.",
        "Gravitational waves are ripples in spacetime caused by accelerating masses. First detected by LIGO in 2015 from two merging black holes 1.3 billion light-years away.",
        "The Chandrasekhar limit (1.4 M☉): the maximum mass of a stable white dwarf. Above this, electron degeneracy pressure fails, triggering collapse to neutron star or supernova.",
        "Nuclear fusion powers stars: in the Sun's core, four hydrogen nuclei fuse to form helium, releasing ~0.7% of the rest mass as energy (4×10²⁶ W luminosity).",
        "Retrograde motion: planets normally move west to east against background stars. As Earth overtakes an outer planet, it appears to move backward (east to west) temporarily.",
        "The Hubble constant H₀ ≈ 67-74 km/s/Mpc measures the rate of cosmic expansion. Galaxies recede at velocities proportional to their distance (Hubble's law, 1929).",
        "Eclipses: a solar eclipse occurs when the Moon blocks the Sun from Earth's view; a lunar eclipse when Earth's shadow falls on the Moon. Both require Sun-Earth-Moon alignment.",
        "The 23.5° axial tilt of Earth causes seasons. The hemisphere tilted toward the Sun experiences summer (longer days, more direct sunlight); tilted away experiences winter.",
        "Spectroscopy identifies stellar composition via absorption lines. Helium was discovered in the Sun's spectrum (1868) before being found on Earth. Each element produces a unique fingerprint.",
        "The cosmic distance ladder: parallax → Cepheid variables → Type Ia supernovae → Hubble's law. Each rung calibrates the next, extending measurable distances across the universe.",
        "Pulsars are rapidly rotating neutron stars emitting beams of electromagnetic radiation. PSR B1919+21 (1967) was first mistaken for extraterrestrial intelligence — nicknamed 'LGM-1.'",
        "Active galactic nuclei (AGN) and quasars are powered by accretion onto supermassive black holes. The most luminous quasars outshine their entire host galaxy by factors of thousands.",
        "Exoplanet detection methods: transit (brightness dip as planet crosses star), radial velocity (Doppler wobble), direct imaging, microlensing. TESS and Kepler discovered thousands of exoplanets.",
    ],

    # ── CHEMISTRY ────────────────────────────────────────────────────────────
    "chemistry": [
        "The periodic table organizes elements by increasing atomic number, with similar chemical properties repeating periodically — Mendeleev's insight (1869).",
        "Electronegativity: the tendency of an atom to attract electrons in a bond. Fluorine is most electronegative (4.0). Large electronegativity differences create polar/ionic bonds.",
        "Le Chatelier's principle: a system at equilibrium disturbed by a change in concentration, temperature, or pressure shifts to oppose the change and re-establish equilibrium.",
        "pH = -log[H⁺]. A pH of 7 is neutral; below 7 is acidic; above 7 is basic/alkaline. A change of 1 pH unit represents a 10-fold change in hydrogen ion concentration.",
        "Oxidation-reduction (redox) reactions: oxidation is loss of electrons; reduction is gain of electrons. OIL RIG (Oxidation Is Loss, Reduction Is Gain). Electron transfer drives batteries.",
        "Covalent bonds share electron pairs between atoms. Ionic bonds transfer electrons, creating oppositely charged ions. Metallic bonds are shared among a mobile electron sea.",
        "Avogadro's number: 6.022 × 10²³ particles per mole. A mole of water weighs 18 grams. Molar mass in g/mol equals atomic mass in unified atomic mass units.",
        "The ideal gas law: PV = nRT. Pressure times volume equals moles times the gas constant times absolute temperature. Applies at low pressure and high temperature.",
        "Entropy (S) measures disorder. The second law: in any spontaneous process, total entropy increases. Gibbs free energy ΔG = ΔH - TΔS; ΔG < 0 for spontaneous reactions.",
        "Chirality: molecules that are non-superimposable mirror images are enantiomers. Thalidomide's (R) enantiomer treated morning sickness; the (S) enantiomer caused birth defects.",
        "Activation energy is the minimum energy required to initiate a chemical reaction. Catalysts lower activation energy without being consumed, accelerating reaction rates.",
        "Arrhenius equation: k = A e^(-Ea/RT). Rate constant k increases exponentially with temperature T; a 10°C rise roughly doubles reaction rate (for typical Ea values).",
        "Acid-base chemistry: Brønsted-Lowry defines acids as proton donors, bases as proton acceptors. Lewis extends this: acids accept electron pairs; bases donate electron pairs.",
        "Solubility product (Ksp): for sparingly soluble salts, Ksp = [cation]^m [anion]^n at equilibrium. If ion product > Ksp, precipitation occurs.",
        "Functional groups define organic molecule reactivity: hydroxyl (-OH), carbonyl (C=O), carboxyl (-COOH), amino (-NH₂), alkyl (-CH₃). Carbon's four bonds enable structural diversity.",
        "Polymerization: monomers join to form polymers. Addition polymerization (polyethylene, PVC) adds monomers without byproducts. Condensation polymerization (nylon, polyester) releases water.",
        "Spectroscopy identifies compounds: NMR reveals molecular structure from nuclear spin; IR identifies functional groups from bond vibrations; mass spectrometry gives molecular weight and fragments.",
        "Electrochemistry: in a galvanic cell, the anode is oxidized (negative); the cathode is reduced (positive). Cell voltage Ecell = Ecathode - Eanode. Lithium-ion batteries use intercalation.",
        "The half-life of a first-order reaction: t½ = 0.693/k. Independent of concentration. Radioactive decay follows first-order kinetics. Carbon-14 half-life = 5,730 years.",
        "Hydrogen bonding: a relatively strong intermolecular force between H bonded to F, O, or N and another electronegative atom. Explains water's high boiling point, surface tension, and life.",
        "Buffer solutions resist pH change: a weak acid and its conjugate base absorb added H⁺ or OH⁻. The Henderson-Hasselbalch equation: pH = pKa + log([A⁻]/[HA]).",
        "Electronegativity trend: increases left to right across periods (more protons) and decreases top to bottom (larger atomic radius, shielded nucleus).",
        "Transition metals have partially filled d-orbitals enabling variable oxidation states, catalytic activity, and vivid colors. Iron(III) is orange; copper(II) is blue; chromium varies widely.",
        "The water molecule is bent (104.5°) due to two lone pairs on oxygen, giving it a dipole moment. This polarity explains water's unique properties as the universal solvent.",
        "Carbon forms four covalent bonds and can bond to itself in chains and rings, giving organic chemistry its enormous structural diversity. Life is carbon-based for this reason.",
    ],

    # ── COMBINATORICS ────────────────────────────────────────────────────────
    "combinatorics": [
        "The multiplication principle: if event A can occur in m ways and event B in n ways, both together can occur in m × n ways. Counting menus: 4 mains × 3 sides = 12 combinations.",
        "A permutation is an ordered arrangement of r items from n: P(n,r) = n!/(n-r)!. Order matters: the number of ways to arrange 3 books from 5 is P(5,3) = 60.",
        "A combination is an unordered selection of r items from n: C(n,r) = n!/(r!(n-r)!). Order doesn't matter: choosing 3 from 5 books is C(5,3) = 10.",
        "Pascal's triangle: each entry is the sum of the two above it. Row n contains the binomial coefficients C(n,0), C(n,1), ..., C(n,n). Row 4: 1 4 6 4 1.",
        "The binomial theorem: (x+y)^n = Σ C(n,k) x^(n-k) y^k. The expansion of (x+y)³ = x³ + 3x²y + 3xy² + y³.",
        "The inclusion-exclusion principle: |A ∪ B| = |A| + |B| - |A ∩ B|. Generalizes to multiple sets. Used to count elements in unions by correcting for over-counting.",
        "The pigeonhole principle: if n+1 items are placed in n containers, at least one container has ≥ 2 items. Among any 13 people, at least two share a birth month.",
        "Derangements: permutations where no element appears in its original position. D(n) = n! × Σ (-1)^k/k! ≈ n!/e. For n=3, there are D(3)=2 derangements.",
        "The Catalan number Cₙ = C(2n,n)/(n+1). Counts: valid parenthesizations (Cₙ for n pairs), binary trees with n+1 leaves, paths below the diagonal. C₃ = 5, C₄ = 14.",
        "Stars and bars: the number of ways to distribute k identical items into n distinct bins is C(k+n-1, n-1). Distributing 5 identical balls into 3 boxes: C(7,2) = 21 ways.",
        "A partition of n is a way to write n as a sum of positive integers (order irrelevant). Partitions of 4: {4}, {3,1}, {2,2}, {2,1,1}, {1,1,1,1}. Partition function p(n) grows rapidly.",
        "Stirling numbers of the second kind S(n,k): number of ways to partition n elements into exactly k non-empty subsets. S(4,2) = 7.",
        "Generating functions: encode sequences aₙ as coefficients of power series A(x) = Σ aₙ xⁿ. Product of two generating functions corresponds to convolution of their sequences.",
        "The birthday problem: the probability that at least two people in a group of 23 share a birthday exceeds 50%. With 70 people, probability exceeds 99.9%.",
        "Graph theory coloring: the four-color theorem states that any planar map can be colored with 4 colors such that no adjacent regions share a color. Proved computationally in 1976.",
        "Ramsey theory: in any sufficiently large structure, order is unavoidable. R(3,3)=6: among any 6 people, there are either 3 mutual friends or 3 mutual strangers.",
        "The travelling salesman problem (TSP): find the shortest route visiting n cities exactly once. NP-hard; no polynomial-time algorithm is known. For n=20, there are 19!/2 ≈ 6×10¹⁶ routes.",
        "Counting paths in a grid: to go from (0,0) to (m,n) moving only right or up, the number of paths is C(m+n, m). From (0,0) to (3,2): C(5,3) = 10 paths.",
        "The multinomial theorem generalizes the binomial: (x₁+x₂+...+xₖ)^n = Σ (n!/(n₁!n₂!...nₖ!)) x₁^n₁ x₂^n₂ ... xₖ^nₖ where Σnᵢ=n.",
        "Euler's formula for polyhedra: V - E + F = 2, where V is vertices, E is edges, F is faces. A cube: 8 - 12 + 6 = 2. A tetrahedron: 4 - 6 + 4 = 2.",
    ],

    # ── CONSTRUCTION ─────────────────────────────────────────────────────────
    "construction": [
        "The critical path method (CPM) identifies the longest sequence of dependent tasks in a project. Delays on the critical path delay project completion; float elsewhere provides schedule flexibility.",
        "Concrete compressive strength is tested by crushing 28-day cure cylinders. Normal concrete: 3,000-5,000 psi. High-strength concrete: 6,000-10,000+ psi. Water-cement ratio is the primary variable.",
        "Rebar (reinforcing bar) compensates for concrete's low tensile strength. Steel has a yield strength of ~60,000 psi (Grade 60) vs. concrete's ~500 psi in tension.",
        "Foundation types: spread footings distribute load to soil; mat slabs cover entire building footprint; pile foundations transfer load to deeper, stronger strata.",
        "The load path transfers building loads (dead loads, live loads, wind, seismic) from the roof through floors, walls, columns, and foundation to the ground.",
        "Fire-resistive construction (Type I) uses non-combustible materials with specified hourly ratings. A 2-hour fire rating means the assembly resists fire for 2 hours in a standard test.",
        "HVAC design: Manual J calculates heating and cooling loads by zone based on climate, insulation, window area, occupancy, and infiltration. Properly sized systems prevent comfort and efficiency problems.",
        "A building envelope includes the roof, exterior walls, and foundation — the boundary between conditioned and unconditioned space. Thermal bridging through studs reduces effective insulation value.",
        "The International Building Code (IBC) sets minimum standards for structural integrity, fire safety, accessibility, and egress. Local jurisdictions adopt and amend it.",
        "Masonry construction: brick and block walls resist compression well but need steel reinforcement (rebar in grouted cells) for tensile and seismic loads.",
        "Steel moment frames resist lateral forces (wind, seismic) through rigid beam-column connections that transfer bending moments. Braced frames use diagonal bracing instead.",
        "Waterproofing vs. damp-proofing: below-grade waterproofing resists hydrostatic pressure (positive water head); damp-proofing only resists moisture vapor transmission.",
        "Electrical rough-in sequence: service entrance → distribution panel → branch circuits → device boxes. All wiring must be accessible for inspection before drywall.",
        "Post-tensioned concrete uses high-strength steel tendons tensioned after concrete curing, precompressing the concrete to eliminate tensile stresses and allow longer spans.",
        "ADA (Americans with Disabilities Act) requires accessible routes (max 1:20 slope), 36-inch minimum door clear width, accessible restrooms, and parking with proper van-accessible spaces.",
        "Thermal mass: dense materials (concrete, masonry, water) absorb heat during the day and release it at night, moderating temperature swings. Valuable in passive solar design.",
        "A change order documents modifications to the original contract scope, cost, or schedule. Uncontrolled change orders are the primary cause of construction cost overruns.",
        "Value engineering identifies alternatives that achieve the same function at lower cost without sacrificing required performance. Different from cost-cutting that reduces quality.",
        "Punch list: near project completion, the owner or architect creates a list of incomplete or deficient items the contractor must correct before final payment.",
        "Soil bearing capacity determines allowable foundation pressure. Clay: 1,000-3,000 psf; sand: 1,500-4,000 psf; gravel: 3,000-6,000 psf; rock: 10,000+ psf.",
        "Green building certification (LEED, Living Building Challenge) evaluates energy efficiency, water use, materials, site impact, and indoor environmental quality.",
        "Modular construction fabricates building components off-site in controlled factory conditions, then ships and assembles on-site. Reduces weather delays and improves quality control.",
        "Seismic design: buildings in earthquake zones use ductile detailing — members that can deform plastically before failure. Base isolation decouples the structure from ground motion.",
        "The punch-through failure mode in thin concrete slabs: high concentrated loads can push through slabs. Shear reinforcement (stirrups, studs) around columns prevents this.",
        "Project safety: OSHA requires a site safety plan, fall protection above 6 feet, excavation shoring for trenches >5 feet, and daily toolbox talks for high-hazard activities.",
    ],

    # ── CRYPTOGRAPHY ─────────────────────────────────────────────────────────
    "cryptography": [
        "Symmetric encryption uses the same key to encrypt and decrypt. AES-256 is the current standard — approved by NIST, used in TLS, file encryption, and government communications.",
        "Asymmetric (public-key) cryptography uses a key pair: a public key to encrypt, a private key to decrypt. RSA, ECC, and Diffie-Hellman are the main algorithms.",
        "The Diffie-Hellman key exchange allows two parties to establish a shared secret over an insecure channel without prior communication, using modular exponentiation.",
        "RSA security depends on the difficulty of factoring the product of two large primes. Typical key sizes: 2048-4096 bits. Shor's algorithm would break RSA on a sufficiently large quantum computer.",
        "Elliptic curve cryptography (ECC) achieves equivalent security with shorter keys: 256-bit ECC ≈ 3072-bit RSA. Used in TLS, Bitcoin (secp256k1), and Ed25519 signing.",
        "A cryptographic hash function maps arbitrary input to fixed-length output. Properties: deterministic, fast to compute, collision-resistant, and preimage-resistant. SHA-256 produces 256-bit digests.",
        "Digital signatures: sign with private key; verify with public key. If the message or signature changes, verification fails. Ed25519 produces 64-byte signatures with strong security properties.",
        "TLS (Transport Layer Security) secures web communications. TLS handshake: key exchange → certificate verification → symmetric key derivation → encrypted communication.",
        "A salt is a random value added to a password before hashing, preventing rainbow table attacks. Each user's password gets a unique salt even if passwords are identical.",
        "Key derivation functions (KDFs) like bcrypt, scrypt, and Argon2 deliberately slow password hashing to resist brute-force attacks by requiring significant CPU or memory.",
        "Zero-knowledge proofs allow one party to prove they know a secret without revealing it. Zcash uses zk-SNARKs to verify transactions without revealing sender, receiver, or amount.",
        "Homomorphic encryption allows computations on ciphertext that produce encrypted results matching operations on plaintext. Enables secure cloud computation on private data.",
        "The one-time pad provides perfect secrecy: XOR the plaintext with a truly random key of the same length, used only once. Unconditionally secure but impractical for large data.",
        "Block ciphers (AES) encrypt fixed-size blocks. Modes of operation (CBC, GCM, CTR) chain blocks or generate keystreams. GCM (Galois/Counter Mode) provides authenticated encryption.",
        "Perfect forward secrecy (PFS): session keys are ephemeral, derived fresh for each session. Compromising a private key does not decrypt past sessions recorded by an adversary.",
        "Quantum key distribution (QKD): uses quantum mechanical properties to distribute keys. Any eavesdropping disturbs the quantum states, alerting the communicating parties.",
        "A man-in-the-middle (MITM) attack intercepts communications between two parties. Certificate authorities and public-key pinning are defenses; key fingerprint verification is the primitive.",
        "Steganography hides a message within innocuous data (image, audio). Cryptography conceals the content; steganography conceals the existence of communication.",
        "Merkle trees organize data in binary trees where each parent node contains the hash of its children. Efficient integrity verification — used in Git, Bitcoin, and certificate transparency.",
        "The birthday attack exploits the birthday paradox to find hash collisions: for a hash with n-bit output, collisions appear after ~2^(n/2) attempts. SHA-1's 160-bit output requires ~2^80 work.",
    ],

    # ── CYBERSECURITY ────────────────────────────────────────────────────────
    "cybersecurity": [
        "The CIA triad: Confidentiality (only authorized parties access data), Integrity (data is accurate and unmodified), Availability (systems function when needed). All security controls serve these three goals.",
        "Defense in depth: use multiple, independent layers of security so that if one fails, others protect the system. Network perimeter, host-based, application, and data security layers.",
        "Zero trust architecture assumes no user or system is inherently trustworthy, requiring continuous verification, least-privilege access, and micro-segmentation regardless of network location.",
        "Phishing: deceptive emails that trick users into revealing credentials or installing malware. Spear phishing targets specific individuals using personalized information for higher success.",
        "SQL injection: attackers insert malicious SQL into input fields to manipulate database queries. Parameterized queries and prepared statements are the primary defense.",
        "Cross-site scripting (XSS): attackers inject malicious scripts into web pages viewed by other users. Stored XSS persists in the database; reflected XSS bounces off the server.",
        "Penetration testing (pentesting): authorized simulated attacks to identify vulnerabilities before malicious actors do. Follows rules of engagement; report findings and remediation steps.",
        "The OWASP Top 10 is the standard reference for web application security risks: injection, broken authentication, sensitive data exposure, XML external entities, broken access control, etc.",
        "A vulnerability is a weakness; a threat is a potential danger; a risk is likelihood × impact. Not all vulnerabilities represent meaningful risks depending on exploitability and asset value.",
        "Multi-factor authentication (MFA) requires two or more factors: something you know (password), something you have (phone), something you are (biometric). Dramatically reduces account takeover risk.",
        "Incident response phases: Preparation → Detection and Analysis → Containment → Eradication → Recovery → Post-Incident Activity. The NIST framework provides structure.",
        "Ransomware encrypts victim files and demands payment for decryption keys. Defense: offline backups, patch management, least-privilege accounts, and network segmentation.",
        "Social engineering exploits human psychology rather than technical vulnerabilities. Pretexting, baiting, vishing (voice), and tailgating are common tactics.",
        "The principle of least privilege: grant only the minimum access rights necessary for a task. Limits blast radius when credentials are compromised.",
        "Buffer overflow: writing more data than a buffer can hold overwrites adjacent memory. Exploited to execute arbitrary code. Stack canaries, ASLR, and DEP mitigate this.",
        "Public key infrastructure (PKI): the system of certificate authorities (CAs), certificates, and revocation mechanisms that enables trusted authentication in TLS and code signing.",
        "SIEM (Security Information and Event Management) aggregates and correlates logs from across an environment to detect threats, support incident response, and meet compliance requirements.",
        "The kill chain model (Lockheed Martin): Reconnaissance → Weaponization → Delivery → Exploitation → Installation → Command & Control → Actions on Objectives. Breaking any stage stops the attack.",
        "Cryptojacking: malware secretly uses victim compute resources to mine cryptocurrency. Detected by unusual CPU/GPU utilization and abnormal network traffic to mining pools.",
        "Supply chain attacks compromise software or hardware before it reaches the target. SolarWinds (2020) injected malware into a software update trusted by 18,000+ organizations.",
    ],

    # ── ELECTRICAL ───────────────────────────────────────────────────────────
    "electrical": [
        "Kirchhoff's voltage law (KVL): the sum of all voltages around any closed loop is zero. Conservation of energy: voltage rises (sources) equal voltage drops (loads) in any loop.",
        "Kirchhoff's current law (KCL): the sum of currents entering any node equals the sum leaving. Conservation of charge: charge cannot accumulate at a node in steady state.",
        "Resistors in series: Rtotal = R1 + R2 + R3. Resistors in parallel: 1/Rtotal = 1/R1 + 1/R2 + 1/R3. Parallel combinations always have less resistance than the smallest branch.",
        "Power P = IV = I²R = V²/R. Measured in watts. A 100Ω resistor with 10V across it dissipates P = V²/R = 100/100 = 1 watt.",
        "A capacitor stores energy in an electric field. C = Q/V; energy = ½CV². Capacitors block DC and pass AC; their impedance Xc = 1/(2πfC) decreases with frequency.",
        "An inductor stores energy in a magnetic field. Energy = ½LI². Inductors oppose changes in current; their impedance XL = 2πfL increases with frequency.",
        "Impedance Z = R + jX in complex notation, where R is resistance and X is reactance (XL - XC). Ohm's law in AC circuits: V = IZ.",
        "A transformer transfers power between circuits via electromagnetic induction. Turns ratio N1/N2 = V1/V2 = I2/I1. Ideal transformers conserve power: V1I1 = V2I2.",
        "Three-phase power transmits 3× the power of single-phase with only 1.73× the conductors. Used in industrial equipment and power distribution for efficiency and balance.",
        "The semiconductor p-n junction: p-type (excess holes) meets n-type (excess electrons). Forward bias allows current flow; reverse bias blocks it. This asymmetry enables diodes, transistors, solar cells.",
        "A MOSFET (Metal-Oxide-Semiconductor Field-Effect Transistor) uses gate voltage to control drain-source current. The dominant switch in modern digital logic and power electronics.",
        "Power factor = real power / apparent power = cos(φ). Unity power factor means all apparent power is real power. Inductive loads (motors) cause lagging power factor, reducing efficiency.",
        "Grounding: safety ground (green/bare wire) connects metal enclosures to earth, providing a low-resistance path for fault current to trip breakers before shocking users.",
        "Wire gauge (AWG): smaller numbers are larger wire. 14 AWG is the minimum for 15A circuits; 12 AWG for 20A; 10 AWG for 30A. Larger wires carry more current without overheating.",
        "Faraday's law: EMF = -dΦ/dt. A changing magnetic flux through a coil induces a voltage proportional to the rate of change. The basis of generators, transformers, and motors.",
        "Lenz's law: the induced current opposes the change that creates it. A magnet moving into a coil induces a current creating a field opposing the magnet's motion.",
        "Operational amplifiers (op-amps) are high-gain differential amplifiers. With negative feedback, gain equals -R2/R1 (inverting) or 1+R2/R1 (non-inverting). Used in filters, ADCs, and signal processing.",
        "Digital logic gates (AND, OR, NOT, NAND, NOR, XOR) implement Boolean functions. NAND and NOR are universal gates — any logic circuit can be built from either alone.",
        "Fourier analysis decomposes any periodic signal into a sum of sinusoids at harmonic frequencies. Essential for understanding filters, modulation, noise, and spectral content.",
        "ESD (electrostatic discharge) can destroy sensitive ICs. Handling at workstations requires ESD mats, wrist straps, and proper packaging. CMOS gates are especially vulnerable.",
    ],

    # ── ENERGY ───────────────────────────────────────────────────────────────
    "energy": [
        "Primary energy sources: fossil fuels (coal, oil, natural gas), nuclear, hydropower, solar, wind, geothermal, biomass. Fossil fuels supply ~80% of world primary energy.",
        "Energy density: gasoline ~46 MJ/kg; natural gas ~55 MJ/kg; coal ~24 MJ/kg; lithium-ion battery ~0.8 MJ/kg. Fossil fuels' high energy density explains their dominance.",
        "The levelized cost of energy (LCOE) accounts for capital, fuel, O&M, and financing over a plant's life, divided by total electricity produced. Solar and wind LCOE now often beats new fossil fuel plants.",
        "Grid parity: the point at which a renewable source produces electricity at the same cost or less than grid electricity from conventional sources. Solar reached grid parity in most regions by 2020.",
        "The electric grid balances supply and demand in real time. Frequency stays at 60 Hz (US) by matching generation to load; imbalances cause frequency deviation, triggering automatic response.",
        "Nuclear fission: uranium-235 or plutonium-239 fissions into smaller nuclei plus neutrons, releasing ~200 MeV per event — ~2 million times the energy of burning a carbon atom.",
        "Photovoltaic (PV) cells convert light to electricity via the photoelectric effect. Typical monocrystalline silicon efficiency: 20-23%. Theoretical maximum (Shockley-Queisser limit): ~33%.",
        "Wind turbines convert kinetic energy to electricity via the Betz limit: maximum 59.3% of wind energy can be extracted. Modern turbines achieve ~45% efficiency.",
        "Combined heat and power (CHP/cogeneration) uses waste heat from electricity generation for space or process heating, achieving 80-90% total efficiency vs. 35-40% for power generation alone.",
        "Hydroelectric power: potential energy of water (mgh) drives turbines. Provides ~16% of world electricity. Large dams provide dispatchable, long-duration storage but cause ecological disruption.",
        "Pumped hydro storage: surplus electricity pumps water uphill; stored water is released through turbines when demand rises. 95% of grid-scale energy storage worldwide; 70-85% round-trip efficiency.",
        "Lithium-ion battery: lithium ions move between anode (graphite) and cathode (lithium metal oxide) during charge/discharge. High energy density, declining cost; dominant in EVs and grid storage.",
        "The carbon intensity of electricity (kg CO₂/kWh): coal ~1.0, natural gas ~0.5, nuclear ~0.012, wind ~0.011, solar PV ~0.04. Decarbonizing electricity requires shifting to low-carbon sources.",
        "Demand response: utilities pay large electricity users (factories, data centers) to reduce load during peak demand, avoiding the need for expensive, rarely-used peaker plants.",
        "Geothermal energy taps Earth's internal heat: steam from hydrothermal reservoirs drives turbines (flash and dry steam plants); binary cycle uses lower-temperature fluids via heat exchangers.",
        "Smart grid technologies use sensors, communication, and automation to optimize electricity distribution, integrate renewable sources, enable EV charging, and improve outage response.",
        "Energy efficiency (Jevons paradox): efficiency improvements often increase total consumption because they reduce cost, stimulating more use. Policy must address both efficiency and total energy use.",
        "The energy trilemma: energy systems must balance security (reliable supply), sustainability (low emissions), and equity (affordable access). Trade-offs are inherent.",
        "Hydrogen as an energy carrier: produced via electrolysis (green H₂) or steam methane reforming (grey/blue H₂). Energy density 142 MJ/kg; storage and transport are key challenges.",
        "Power-to-X: converting surplus renewable electricity to hydrogen, ammonia, synthetic methane, or other fuels, enabling long-duration storage and decarbonization of hard-to-electrify sectors.",
    ],

    # ── EXERCISE SCIENCE ─────────────────────────────────────────────────────
    "exercise_science": [
        "The principle of progressive overload: muscles adapt to training by growing stronger only when challenged beyond their current capacity. Gradual load increases stimulate adaptation.",
        "VO₂ max (maximal oxygen uptake) is the maximum rate of oxygen consumption during exhaustive exercise. The gold standard for aerobic fitness. Elite cyclists: 85+ mL/kg/min; untrained adults: 35-45.",
        "The SAID principle (Specific Adaptation to Imposed Demands): training adaptations are specific to the type, intensity, and pattern of exercise stimulus. Runners improve running, not swimming.",
        "The three energy systems: phosphocreatine (ATP-PCr, 0-10 sec, anaerobic), glycolytic (10 sec-2 min, anaerobic), and oxidative (>2 min, aerobic). All three contribute simultaneously, with dominance shifting.",
        "Muscle fiber types: Type I (slow-twitch, fatigue-resistant, aerobic) dominate in endurance athletes. Type II (fast-twitch, high force, fatigue quickly) dominate in power athletes.",
        "DOMS (delayed onset muscle soreness) peaks 24-72 hours after novel or eccentric exercise. Caused by microtrauma and inflammation; associated with muscle protein synthesis and adaptation.",
        "The RPE (rating of perceived exertion) scale, developed by Borg, correlates with heart rate and exercise intensity. RPE 12-16 on the 6-20 scale corresponds to moderate-vigorous exercise.",
        "Heart rate zones: Zone 1 (50-60% max HR), Zone 2 (60-70%, aerobic base), Zone 3 (70-80%, tempo), Zone 4 (80-90%, threshold), Zone 5 (90-100%, VO₂ max/sprints).",
        "Resistance training adaptations: initial strength gains (0-8 weeks) are primarily neural (motor unit recruitment, synchronization). Hypertrophy (muscle cross-sectional area increase) develops over months.",
        "Bone remodeling: mechanical loading stimulates osteoblast (bone-building) activity. Weight-bearing exercise increases bone mineral density; non-weight-bearing (swimming) has minimal bone effect.",
        "The anabolic window: protein synthesis is elevated 24-48 hours post-exercise. Consuming protein within 2 hours optimizes muscle protein synthesis, though the window is more forgiving than once thought.",
        "Stretching: static stretching (30-60 second holds) increases flexibility over time but acutely reduces force production if done pre-exercise. Dynamic warm-up is preferred before training.",
        "Training periodization: systematic variation of volume and intensity over weeks (mesocycles) and months (macrocycles) to optimize performance and prevent overtraining.",
        "Overtraining syndrome: chronic fatigue, performance decline, mood disturbance, and immune suppression from excessive training without adequate recovery. Heart rate variability (HRV) is a marker.",
        "The female athlete triad: disordered eating + menstrual irregularity + low bone density. Driven by relative energy deficiency in sport (RED-S). Long-term bone and health consequences.",
        "Core stability training targets the deep stabilizers (transversus abdominis, multifidus) that protect the spine under load. More relevant than global trunk strength for injury prevention.",
        "Interval training (HIIT): alternating high-intensity work periods with recovery. Time-efficient for improving VO₂ max and metabolic fitness; requires adequate recovery between sessions.",
        "Exercise immunology: moderate exercise enhances immune function; prolonged intense exercise (marathons, ultra events) transiently suppresses immunity, increasing infection susceptibility.",
        "Body composition: lean body mass vs. fat mass. Body fat % measured by DEXA (most accurate), hydrostatic weighing, or skinfold calipers. BMI is a population measure, not individual fat assessment.",
        "Physical activity guidelines (WHO): adults need ≥150 minutes/week moderate aerobic activity or ≥75 minutes vigorous, plus muscle-strengthening 2+ days/week.",
    ],

    # ── FINANCE ──────────────────────────────────────────────────────────────
    "finance": [
        "Time value of money: a dollar today is worth more than a dollar in the future due to its earnings potential. Present value PV = FV / (1+r)^n; future value FV = PV × (1+r)^n.",
        "The compound interest formula: A = P(1+r/n)^(nt). Compounding frequency matters: $1,000 at 10% for 1 year = $1,100 (annual), $1,105.08 (monthly), $1,105.17 (daily).",
        "Net present value (NPV) = -Initial investment + Σ (cash flow / (1+r)^t). A positive NPV indicates a project creates value. Accept projects where NPV > 0.",
        "The weighted average cost of capital (WACC) is the blended return rate a company must earn to satisfy all capital providers: WACC = (E/V)×Re + (D/V)×Rd×(1-T).",
        "Portfolio diversification: combining assets with less-than-perfect correlation reduces portfolio variance without reducing expected return. Markowitz's modern portfolio theory (1952).",
        "The efficient market hypothesis (EMH): in a semi-strong efficient market, asset prices reflect all public information. Consistently beating the market requires private information or luck.",
        "Beta measures a stock's systematic risk relative to the market. Beta >1 amplifies market movements; beta <1 dampens them. Beta cannot be diversified away; alpha is excess return.",
        "The Capital Asset Pricing Model (CAPM): Expected return = Rf + β(Rm - Rf). A stock's fair return equals the risk-free rate plus the equity risk premium scaled by beta.",
        "Price-to-earnings (P/E) ratio: stock price / EPS. A P/E of 20 means investors pay $20 per $1 of earnings. High P/E = growth expectations; low P/E = low expectations or value.",
        "Discounted cash flow (DCF) values a business by summing the present values of projected free cash flows plus a terminal value. Sensitive to discount rate and growth assumptions.",
        "Working capital = current assets - current liabilities. Positive working capital indicates ability to meet short-term obligations. Cash conversion cycle measures efficiency.",
        "Leverage amplifies both gains and losses. Debt financing increases return on equity in good times and accelerates losses in bad times. Interest coverage ratio = EBIT/interest.",
        "Fixed income: bonds pay periodic coupon payments and return principal at maturity. Bond price and yield move inversely. Duration measures price sensitivity to yield changes.",
        "The yield curve plots interest rates across maturities. Normal (upward): higher yield for longer maturity. Inverted (downward): historically precedes recessions. Flat: transitional.",
        "Options: a call option gives the right (not obligation) to buy at the strike price; a put option to sell. Black-Scholes model prices European options based on volatility, time, and rates.",
        "Enterprise value (EV) = market cap + debt - cash. EV/EBITDA is a valuation multiple comparable across capital structures. Used in M&A and peer comparisons.",
        "The equity risk premium (ERP) is the excess return investors require to hold equities over risk-free assets. Historically ~4-7% for US stocks. Justifies equity investing over bonds.",
        "Behavioral finance: prospect theory shows people feel losses ~2.5× more acutely than equivalent gains. Mental accounting, anchoring, and herding cause systematic market mispricings.",
        "A financial statement consists of balance sheet (assets = liabilities + equity), income statement (revenue - expenses = net income), and cash flow statement (operating, investing, financing).",
        "Stewardship: the biblical framework for finance. All resources belong to God (Psalm 24:1); humans are stewards, not owners. This changes the motive from accumulation to faithful management.",
    ],

    # ── GENETICS ─────────────────────────────────────────────────────────────
    "genetics": [
        "Alleles are alternative forms of a gene at a locus. Dominant alleles mask recessive ones. A person with one dominant and one recessive allele (heterozygous) shows the dominant trait.",
        "Mendelian ratios: a cross of two heterozygotes (Aa × Aa) yields 1:2:1 genotype ratio (AA:Aa:aa) and 3:1 phenotype ratio (dominant:recessive) for a simple trait.",
        "Sex-linked inheritance: genes on the X chromosome are expressed in males (XY) with one copy. Colorblindness and hemophilia are X-linked recessive — more common in males.",
        "Incomplete dominance: heterozygotes show an intermediate phenotype (red + white flowers = pink). Codominance: both alleles are fully expressed (AB blood type).",
        "A chromosomal crossover (recombination) during meiosis I exchanges segments between homologous chromosomes. Genes farther apart on a chromosome cross over more frequently.",
        "The genetic code: 64 codons (3-nucleotide sequences) encode 20 amino acids plus start (AUG/Met) and three stop codons. Multiple codons can encode the same amino acid (degeneracy).",
        "Mutation types: point mutations (SNPs) change a single base; insertions/deletions cause frameshifts. Mutations can be silent, missense (amino acid change), or nonsense (premature stop).",
        "Chromosomal abnormalities: Trisomy 21 (Down syndrome) results from nondisjunction — failure of chromosomes to separate during meiosis, producing an extra chromosome 21.",
        "Epigenetics: DNA methylation at CpG sites silences genes. Histone acetylation loosens chromatin, promoting transcription. These marks can be heritable and responsive to environment.",
        "Gene therapy: replacing, silencing, or adding genes to treat disease. Ex vivo: modify cells outside the body, then reintroduce. In vivo: deliver vectors directly to target tissue.",
        "CRISPR-Cas9 uses a guide RNA to direct the Cas9 nuclease to a specific genomic locus where it creates a double-strand break. Cells repair the break by error-prone NHEJ or template-directed HDR.",
        "Polygenic traits (height, intelligence, cardiovascular disease risk) result from the combined effect of many loci. Genome-wide association studies (GWAS) identify contributing variants.",
        "Genetic drift: random changes in allele frequency in small populations. Founder effects and population bottlenecks can dramatically shift allele frequencies from ancestral populations.",
        "The Hardy-Weinberg principle: allele and genotype frequencies in a population remain constant generation after generation in the absence of selection, mutation, migration, or drift.",
        "Horizontal gene transfer (HGT): bacteria transfer genes between cells via transformation, transduction, or conjugation. Drives rapid spread of antibiotic resistance across bacterial species.",
        "Genomic imprinting: expression of a gene depends on which parent transmitted it. Prader-Willi and Angelman syndromes arise from the same chromosomal region, differing only by parent of origin.",
        "The 1000 Genomes Project and gnomAD have catalogued millions of human genetic variants. Common variants (MAF >1%) explain less disease risk than rare, high-impact variants.",
        "Tumor suppressor genes (p53, BRCA1) normally inhibit cell proliferation. Loss-of-function mutations in both copies allow uncontrolled growth. p53 is mutated in ~50% of human cancers.",
        "Genetic ancestry testing analyzes SNPs to infer ancestral populations. Results reflect average ancestry over many generations, not identity. Identical twins can receive different results.",
        "The imago Dei (Genesis 1:26-27) provides a theological framework: humans bear God's image, not encoded in DNA but in the capacity for relationship, reason, and moral accountability.",
    ],

    # ── GEOLOGY ──────────────────────────────────────────────────────────────
    "geology": [
        "Plate tectonics: Earth's lithosphere is divided into ~12 major plates that move on the asthenosphere. Plates diverge (mid-ocean ridges), converge (subduction zones), or slide (transform faults).",
        "The rock cycle: igneous rocks form from cooling magma; weathering and erosion create sediment; compaction and cementation form sedimentary rocks; heat and pressure create metamorphic rocks; melting starts the cycle again.",
        "Radiometric dating measures radioactive isotope decay to determine rock age. U-Pb zircon dating is accurate to millions of years. Earth's age: ~4.54 billion years by lead-lead dating of meteorites.",
        "Stratigraphy: the study of rock layers (strata). Law of superposition: in undisturbed sequences, older layers are below younger ones. Relative dating establishes sequence; radiometric dating gives absolute age.",
        "The Richter scale (now moment magnitude scale Mw) measures earthquake energy. Each unit represents ~31.6× more energy. Mw 8.0 releases ~1,000× the energy of Mw 6.0.",
        "Seismic waves: P-waves (compressional) travel through solids and liquids; S-waves (shear) travel only through solids. S-wave shadow zones indicate Earth's liquid outer core.",
        "Earth's interior: crust (0-35 km), mantle (35-2,890 km), outer core (liquid iron-nickel, 2,890-5,150 km), inner core (solid, 5,150-6,371 km). Seismic data revealed this structure.",
        "Mineral identification: hardness (Mohs scale 1-10), cleavage, fracture, luster, streak, crystal system, and specific gravity. Quartz: 7; feldspar: 6; calcite: 3; talc: 1.",
        "Silicates are the most common mineral group (~90% of Earth's crust), based on SiO₄⁴⁻ tetrahedra. Quartz, feldspar, mica, pyroxene, and olivine are common silicates.",
        "Soil horizons (profile): O (organic), A (topsoil, humus-rich), E (eluviation zone), B (illuviation, mineral accumulation), C (weathered parent material), R (bedrock).",
        "Karst topography: dissolution of carbonate rocks (limestone, dolomite) by slightly acidic groundwater creates sinkholes, caves, springs, and disappearing streams.",
        "Volcanoes: shield volcanoes (Hawaii) have low viscosity basaltic lava, broad gentle slopes, and effusive eruptions. Stratovolcanoes (Mt. St. Helens) have viscous andesitic lava and explosive eruptions.",
        "Ice ages: Earth has experienced multiple glacial periods driven by Milankovitch cycles — orbital eccentricity (100,000 yr), axial tilt (41,000 yr), and precession (26,000 yr).",
        "The geologic time scale divides Earth's history into eons (Hadean, Archean, Proterozoic, Phanerozoic), eras, periods, and epochs. The Phanerozoic (541 Ma-present) contains most complex life.",
        "Hydraulic fracturing (fracking) injects fluid at high pressure into shale formations to release trapped hydrocarbons. Induced seismicity from wastewater injection is an associated risk.",
        "Mineral resources: copper, iron, aluminum, gold, and rare earth elements are mined. Ore grade (concentration) and deposit size determine economic viability. Recycling reduces mining pressure.",
        "The Himalayas formed by collision of the Indian and Eurasian plates (~50 Ma), creating the highest mountains on Earth. Continental collision thickens crust without subduction.",
        "Paleontology: fossils of organisms preserved in sedimentary rock inform evolutionary history and past environmental conditions. Index fossils date rock layers by species with known time ranges.",
        "Aquifer recharge: groundwater replenishes through precipitation infiltrating permeable rock. Recharge rates for deep aquifers (Ogallala, Nubian Sandstone) are millennia — effectively non-renewable.",
        "Geohazards: earthquakes, volcanoes, landslides, tsunamis, and subsidence. Tsunami generation requires displacement of a water column by seismic activity or submarine landslide.",
    ],

    # ── GEOMETRY ─────────────────────────────────────────────────────────────
    "geometry": [
        "Euclid's five postulates (c. 300 BC) are the foundation of Euclidean geometry. The fifth (parallel) postulate: through a point not on a line, exactly one parallel line exists.",
        "The Pythagorean theorem: a² + b² = c² for a right triangle with legs a, b and hypotenuse c. Converse: if a² + b² = c², the triangle has a right angle opposite c.",
        "Area formulas: triangle = ½bh; rectangle = lw; circle = πr²; trapezoid = ½(b₁+b₂)h; regular polygon = ½ × perimeter × apothem.",
        "Volume formulas: cube = s³; rectangular prism = lwh; sphere = (4/3)πr³; cylinder = πr²h; cone = (1/3)πr²h; pyramid = (1/3)Bh where B is base area.",
        "Similar triangles have equal corresponding angles and proportional corresponding sides. AA, SAS, and SSS similarity criteria. Scale factor k → area ratio k², volume ratio k³.",
        "The sum of interior angles of a polygon with n sides = (n-2) × 180°. Triangle: 180°; quadrilateral: 360°; pentagon: 540°; hexagon: 720°.",
        "The inscribed angle theorem: an inscribed angle is half the central angle subtending the same arc. An inscribed angle in a semicircle is always 90°.",
        "Thales' theorem: if A, B, and C are points on a circle where AC is a diameter, then angle ABC = 90°. A specific case of the inscribed angle theorem.",
        "The golden ratio φ = (1+√5)/2 ≈ 1.618. A rectangle with side ratio φ:1 is a golden rectangle. Related to the Fibonacci sequence: ratios of consecutive Fibonacci numbers approach φ.",
        "Coordinate geometry: the distance between (x₁,y₁) and (x₂,y₂) is √[(x₂-x₁)² + (y₂-y₁)²]. The midpoint is ((x₁+x₂)/2, (y₁+y₂)/2).",
        "The equation of a circle with center (h,k) and radius r: (x-h)² + (y-k)² = r². A unit circle has center (0,0) and radius 1, forming the basis of trigonometry.",
        "Conic sections are cross-sections of a double cone: circle (plane ⊥ axis), ellipse (tilted plane), parabola (parallel to side), hyperbola (steeper than side).",
        "Non-Euclidean geometry: on a sphere (elliptic geometry), parallel lines don't exist; the sum of triangle angles exceeds 180°. On a hyperbolic surface, many parallels exist; angles sum < 180°.",
        "Trigonometry in a unit circle: sin θ = y-coordinate, cos θ = x-coordinate, tan θ = sin/cos. The Pythagorean identity: sin²θ + cos²θ = 1.",
        "Geometric transformations: translation (shift), rotation (turn about a point), reflection (flip over a line), dilation (scale). Isometries preserve shape and size.",
        "The perimeter of a circle (circumference) C = 2πr = πd. π ≈ 3.14159... is irrational and transcendental. Archimedes approximated it to 3.1418 using 96-gons.",
        "Heron's formula: area of a triangle = √[s(s-a)(s-b)(s-c)] where s = (a+b+c)/2 is the semi-perimeter. No altitude needed — just the three side lengths.",
        "The centroid of a triangle is the intersection of medians, located ⅔ of the distance from each vertex to the midpoint of the opposite side.",
        "Vectors in geometry: a vector has magnitude and direction. Vector addition is the parallelogram law. The dot product A⃗·B⃗ = |A||B|cosθ gives the angle between vectors.",
        "Euler's polyhedron formula V - E + F = 2 applies to any convex polyhedron. For a tetrahedron: 4 - 6 + 4 = 2. For a cube: 8 - 12 + 6 = 2.",
    ],

    # ── GEOGRAPHY ────────────────────────────────────────────────────────────
    "geography": [
        "Latitude measures angular distance north or south of the equator (0° to 90°). Longitude measures angular distance east or west of the prime meridian (0° to 180°).",
        "The five climate zones: tropical (0-23.5°), subtropical (23.5-35°), temperate (35-60°), subpolar (60-70°), and polar (70-90°). Altitude creates microclimates within each zone.",
        "The prime meridian (0° longitude) passes through Greenwich, England. The International Date Line runs approximately along 180° longitude in the Pacific Ocean.",
        "The Tropic of Cancer (23.5°N) and Tropic of Capricorn (23.5°S) mark the latitudes where the Sun is directly overhead on the summer and winter solstices respectively.",
        "Biomes are large ecosystem categories defined by climate and dominant vegetation: tropical rainforest, savanna, desert, Mediterranean, temperate broadleaf, boreal forest (taiga), tundra, polar.",
        "The Amazon Basin contains ~10% of all species on Earth. The Amazon River discharges ~20% of the world's freshwater into the Atlantic Ocean at an average rate of ~215,000 m³/s.",
        "Urbanization: more than 56% of the world's population lives in cities (2020). Megacities have >10 million people. Tokyo (~38 million) is the world's largest metropolitan area.",
        "The Fertile Crescent (modern Iraq, Syria, Turkey, Lebanon, Israel) is where agriculture and the earliest urban civilizations (Sumer, Akkad, Babylon) first developed ~10,000 years ago.",
        "Land use change: deforestation, especially in tropical forests, releases stored carbon, reduces biodiversity, and disrupts hydrological cycles. The Amazon and Congo Basins are primary concerns.",
        "Trade winds blow from subtropical high-pressure zones toward the equatorial low-pressure zone: northeast in the Northern Hemisphere, southeast in the Southern Hemisphere.",
        "Desertification: degradation of dryland ecosystems due to climate variation and human activities (overgrazing, unsustainable agriculture, deforestation). The Sahel region is a prime example.",
        "The polar vortex: a persistent low-pressure area near the poles. When it weakens, cold Arctic air masses can break southward into temperate regions, causing extreme cold spells.",
        "Ocean currents: thermohaline circulation (the 'global conveyor belt') distributes heat, nutrients, and carbon globally. The Gulf Stream warms Western Europe. Disruption would cause major climate shifts.",
        "The Ring of Fire: a ~40,000 km arc around the Pacific Basin where ~75% of the world's volcanoes and ~90% of its earthquakes occur, driven by subduction of oceanic plates.",
        "Watersheds: all precipitation falling within a watershed drains to a common outlet. The Mississippi-Missouri watershed covers 40% of the contiguous US.",
        "The rain shadow effect: moist air rises over mountains, cools, and precipitates on the windward side. The leeward side receives dry air, creating deserts (Atacama, Patagonia, Gobi).",
        "Groundwater depletion: the Aral Sea (Kazakhstan/Uzbekistan) was largely drained by Soviet irrigation diversions, shrinking by 90% in volume — one of the greatest environmental disasters.",
        "Urban heat island effect: cities are 1-3°C warmer than surrounding rural areas due to dark surfaces, reduced vegetation, waste heat, and limited evapotranspiration.",
        "The continental divide (Great Divide) separates watersheds that drain to the Atlantic from those draining to the Pacific. In the US, it runs along the Rocky Mountains.",
        "Biblical geography: the land of Canaan/Israel bridges Africa (Egypt) and Asia (Mesopotamia), placing it at the crossroads of ancient civilization — a strategic location for the unfolding of redemptive history.",
    ],

    # ── LABOR ─────────────────────────────────────────────────────────────────
    "labor": [
        "The labor market: workers supply labor in exchange for wages; employers demand labor to produce goods and services. Equilibrium wage and employment are determined by supply and demand.",
        "Minimum wage laws set a floor below which wages cannot legally fall. The effects on employment are debated: standard theory predicts job losses; recent empirical work shows modest or no job loss in many contexts.",
        "Collective bargaining: unions negotiate wages, benefits, and working conditions with employers. Union membership in the US has declined from ~35% in the 1950s to ~10% today.",
        "The National Labor Relations Act (NLRA, 1935) guarantees workers the right to organize, form unions, and bargain collectively. The NLRB enforces these rights.",
        "Human capital: the economic value of workers' skills, knowledge, and experience. Higher education and training increase human capital and therefore wages and productivity.",
        "The principal-agent problem in employment: workers (agents) may not perfectly align their effort with employer (principal) interests. Incentive structures, monitoring, and culture are solutions.",
        "Gig economy: independent contractors working through platforms (Uber, DoorDash, Upwork) lack employment protections (minimum wage, benefits, workers' comp). Classification as employee vs. contractor is contested.",
        "The efficiency wage theory: employers pay above-market wages to attract higher-quality workers, reduce turnover, and motivate effort. Higher wages reduce shirking and increase productivity.",
        "Occupational licensing: requirements (exams, fees, education) to practice a profession. Protects consumers but also restricts entry, raising prices and wages for incumbents.",
        "The gender pay gap: women earn ~82 cents per dollar earned by men (US, 2023 median). Explained partly by occupation, industry, hours worked, and experience — unexplained residual remains.",
        "Child labor: FLSA prohibits hazardous work under 18 and most work under 14 in the US. Globally, ~160 million children work (ILO, 2020), concentrated in agriculture in developing countries.",
        "Workers' compensation: no-fault insurance covering medical treatment and partial wage replacement for work-related injuries. Eliminates the need to prove employer negligence.",
        "OSHA (Occupational Safety and Health Administration): sets and enforces workplace safety standards. General duty clause requires employers to provide hazard-free workplaces even without a specific standard.",
        "Employee benefits: health insurance, retirement plans (401k, pension), paid leave, and disability insurance constitute a significant portion (30-40%) of total compensation costs.",
        "Remote work: expanded dramatically after COVID-19. Productivity effects are mixed — higher for individual tasks, lower for collaborative and creative work. Changed the geography of labor markets.",
        "Unemployment rate = (unemployed / labor force) × 100. Frictional unemployment (between jobs) is natural; structural (skills mismatch) requires retraining; cyclical follows business cycles.",
        "Just wages: Catholic Social Teaching (Rerum Novarum, 1891) asserts workers deserve wages sufficient to support a dignified life. A just wage is not merely what the market clears at.",
        "Automation and labor displacement: technology eliminates some jobs while creating others. The net effect on employment is debated; the distributional effect (which workers are affected) is not.",
        "Living wage vs. minimum wage: a living wage covers basic needs in a specific location. Minimum wage is a legal floor. In most US cities, the minimum wage is below the living wage.",
        "The biblical framework for work: Colossians 3:23 — 'Whatever you do, work heartily, as for the Lord and not for men.' Work is a calling, not merely economic activity.",
    ],

    # ── MUSIC THEORY ─────────────────────────────────────────────────────────
    "music_theory": [
        "A scale is a series of notes in ascending or descending order within an octave, following a specific pattern of whole and half steps. The major scale: W-W-H-W-W-W-H.",
        "A chord is three or more notes played together. A major triad: root + major third (4 half steps) + perfect fifth (7 half steps). Minor triad: root + minor third (3 half steps) + fifth.",
        "The circle of fifths organizes the 12 major keys in a circle where adjacent keys differ by one sharp or flat. Moving clockwise: C → G → D → A → E → B → F# → C# → ...",
        "Time signature: the top number indicates beats per measure; the bottom indicates the note value getting one beat. 4/4 = four quarter notes per measure; 6/8 = six eighth notes.",
        "Tempo markings (from slow to fast): Grave, Largo, Adagio, Andante, Moderato, Allegretto, Allegro, Vivace, Presto, Prestissimo. In Italian, the tradition of Western classical music.",
        "Harmony: the simultaneous combination of notes to create chords and chord progressions. The I-IV-V-I progression is foundational to Western music in tonal harmony.",
        "The harmonic series: a vibrating string produces a fundamental frequency and overtones at 2f, 3f, 4f, etc. The ratios between overtones determine consonance and dissonance.",
        "Dynamics markings: ppp (pianississimo), pp (pianissimo), p (piano), mp (mezzo-piano), mf (mezzo-forte), f (forte), ff (fortissimo), fff. Also crescendo (gradually louder) and decrescendo.",
        "Counterpoint: the art of combining melodic lines. Bach's fugues exemplify strict counterpoint. Rules governing voice leading (parallel fifths are avoided) evolved through Renaissance polyphony.",
        "Modes: the seven modes are built by starting a major scale on each of its degrees. Ionian = major; Dorian (start on 2nd) = minor with raised 6th; Phrygian (3rd); Lydian (4th); Mixolydian (5th); Aeolian = natural minor; Locrian (7th).",
        "Rhythm: the duration of notes and rests. A whole note = 4 beats; half = 2; quarter = 1; eighth = ½; sixteenth = ¼. Dotted notes add half their value (dotted quarter = 1.5 beats).",
        "The tritone (augmented fourth or diminished fifth) spans exactly half an octave — 6 half steps. In medieval music, called diabolus in musica (devil in music) for its dissonance.",
        "Sonata form (exposition-development-recapitulation): the organizing structure of first movements in Classical symphonies, sonatas, and string quartets. Beethoven expanded its scope dramatically.",
        "Pentatonic scale: five notes per octave. Major pentatonic: 1-2-3-5-6 of the major scale. Minor pentatonic: 1-b3-4-5-b7. Used universally across folk music traditions worldwide.",
        "The equal temperament system divides the octave into 12 equal half steps, enabling modulation between all keys. It slightly detunes perfect intervals from pure ratios.",
        "Pitch notation: concert A = 440 Hz (A4). Each octave doubles the frequency: A3 = 220 Hz; A5 = 880 Hz. The musical alphabet: A-B-C-D-E-F-G, repeating.",
        "Polyphony: multiple independent melodic lines sounding simultaneously. Medieval organum (12th c.) developed into Renaissance polyphony (Palestrina, Lassus) and Baroque counterpoint (Bach).",
        "The psalms were the hymnal of ancient Israel — 150 songs covering every human emotion, from praise (Ps. 150) to lament (Ps. 22) to confession (Ps. 51). Sung antiphonally in temple worship.",
        "Music in Scripture: Jubal was the father of musicians (Genesis 4:21). Singing and instruments are commanded in worship (Psalm 150). Colossians 3:16 links song to Scripture-dwelling.",
        "Figured bass (basso continuo) notation specifies intervals above the bass note using numbers. 6/3 = first inversion triad; 6/4/2 = third inversion seventh chord. Bach and Handel era.",
    ],

    # ── NETWORKING ───────────────────────────────────────────────────────────
    "networking": [
        "The OSI model has 7 layers: Physical (bits), Data Link (frames, MAC), Network (packets, IP), Transport (segments, TCP/UDP), Session, Presentation, Application. TCP/IP model has 4 layers.",
        "IP addresses (IPv4): 32-bit numbers written as four octets (0-255). 192.168.1.1 is a private address. IPv6 uses 128-bit addresses written in hexadecimal: 2001:0db8::1.",
        "Subnetting: a /24 subnet mask (255.255.255.0) gives 254 usable host addresses. CIDR notation: 192.168.1.0/24. Subnetting divides networks to reduce broadcast domains and improve security.",
        "DNS (Domain Name System) translates human-readable domain names to IP addresses. A hierarchical, distributed database: root servers → TLD servers → authoritative name servers.",
        "DHCP (Dynamic Host Configuration Protocol) automatically assigns IP addresses, subnet masks, gateways, and DNS servers to devices, eliminating manual configuration.",
        "TCP three-way handshake: client sends SYN → server responds SYN-ACK → client sends ACK. Establishes a reliable connection before data transfer. Connection teardown uses FIN packets.",
        "The difference between a switch and a router: a switch forwards frames within a LAN based on MAC addresses (Layer 2); a router forwards packets between networks based on IP addresses (Layer 3).",
        "NAT (Network Address Translation): maps multiple private IP addresses to one public IP. Enables home routers to share a single ISP-assigned IP. PAT (port address translation) is the common implementation.",
        "BGP (Border Gateway Protocol) is the routing protocol of the internet — how autonomous systems (ASes) exchange routing information and determine paths between networks.",
        "Latency is the time delay between sending and receiving data. Round-trip time (RTT) is measured by ping. Bandwidth is maximum data transfer rate; throughput is actual rate achieved.",
        "SSL/TLS secures transport-layer communications using asymmetric encryption for key exchange and symmetric encryption for data. HTTPS = HTTP over TLS on port 443.",
        "A CDN (Content Delivery Network) caches content at edge servers geographically close to users, reducing latency and backbone traffic. Cloudflare, Akamai, and AWS CloudFront are major providers.",
        "VPN (Virtual Private Network): encrypts traffic between endpoints, creating a secure tunnel over an untrusted network. Used for remote access and privacy.",
        "QoS (Quality of Service) prioritizes network traffic types. Voice and video require low latency and jitter; file transfers tolerate delay. DSCP markings tag packets for differentiated treatment.",
        "The CAP theorem for distributed systems: Consistency, Availability, Partition tolerance — choose at most two. During a network partition, you must choose between consistency and availability.",
        "HTTP methods: GET (retrieve), POST (create), PUT (replace), PATCH (partial update), DELETE (remove). Status codes: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Server Error.",
        "Firewall types: packet filter (stateless, Layer 3-4), stateful inspection (tracks connection state), application-layer proxy (understands protocols), and next-gen firewall (DPI, IDS/IPS).",
        "mDNS (multicast DNS) resolves hostnames on local networks without a central DNS server. Apple Bonjour uses mDNS for device discovery. Concordance uses it to advertise at `concordance.local`.",
        "Wireless standards: 802.11b/g/n (2.4 GHz), 802.11a/n/ac/ax (5 GHz). Wi-Fi 6 (802.11ax): up to 9.6 Gbps, OFDMA and MU-MIMO for denser environments. 2.4 GHz has range; 5 GHz has speed.",
        "The internet's architecture is a packet-switched network: data is broken into packets, each routed independently, and reassembled at the destination. Contrast with circuit-switched telephone networks.",
    ],

    # ── NUTRITION ─────────────────────────────────────────────────────────────
    "nutrition": [
        "Macronutrients: carbohydrates (4 kcal/g), proteins (4 kcal/g), and fats (9 kcal/g) provide energy. Alcohol provides 7 kcal/g. The body needs all three in appropriate ratios.",
        "Essential amino acids must come from diet because the body cannot synthesize them. The nine essential amino acids: histidine, isoleucine, leucine, lysine, methionine, phenylalanine, threonine, tryptophan, valine.",
        "Essential fatty acids: linoleic acid (omega-6) and alpha-linolenic acid (omega-3) must come from diet. Long-chain omega-3s (EPA, DHA) support brain and cardiovascular health.",
        "Fiber: soluble fiber (oats, legumes, fruits) forms a gel that slows digestion, lowers LDL, and modulates blood glucose. Insoluble fiber (wheat bran, vegetables) promotes bowel motility.",
        "The glycemic index (GI) ranks foods by how quickly they raise blood glucose. High-GI foods (white bread, glucose) cause rapid spikes; low-GI foods (legumes, most vegetables) cause gradual rises.",
        "Micronutrients: vitamins (organic, essential in trace amounts) and minerals (inorganic elements). Deficiencies cause specific diseases: scurvy (vitamin C), rickets (vitamin D), anemia (iron), goiter (iodine).",
        "The fat-soluble vitamins (A, D, E, K) are stored in adipose tissue and can accumulate to toxic levels. Water-soluble vitamins (C and B complex) are excreted in urine and require regular intake.",
        "Dietary reference intakes (DRIs): estimated average requirement (EAR), recommended dietary allowance (RDA), adequate intake (AI), and tolerable upper intake level (UL). Based on age, sex, and life stage.",
        "The Mediterranean diet: high in olive oil, fruits, vegetables, legumes, whole grains, and fish; moderate wine; low in red meat and processed foods. Consistently associated with reduced cardiovascular mortality.",
        "Ultra-processed foods (UPFs) contain additives, preservatives, flavorings, and emulsifiers not used in home cooking. Observational studies link high UPF consumption to obesity, type 2 diabetes, and premature death.",
        "The gut microbiome is shaped by diet. Dietary diversity, fiber, and fermented foods promote microbial diversity. Antibiotics and low-fiber diets reduce diversity and may impair immune and metabolic health.",
        "Protein quality is measured by the Digestible Indispensable Amino Acid Score (DIAAS). Animal proteins score higher than most plant proteins; combining complementary plant proteins (beans + rice) provides complete amino acids.",
        "Caloric balance: weight change = calories consumed - calories expended. A 3,500 kcal deficit/surplus ≈ 1 lb fat gained/lost. Metabolic rate adapts to chronic restriction, complicating long-term weight management.",
        "Food security: 800 million+ people face chronic hunger globally. Micronutrient deficiency ('hidden hunger') affects 2 billion more, even in food-sufficient settings.",
        "Breastfeeding provides complete infant nutrition for the first 6 months. Breast milk contains antibodies, oligosaccharides that feed beneficial gut bacteria, and growth factors unavailable in formula.",
        "Salt (sodium chloride) is essential in small amounts but excessive intake (>2,300 mg/day) raises blood pressure. Processed foods account for ~70% of sodium intake in the US.",
        "Eating patterns vs. single nutrients: the overall dietary pattern matters more than any single nutrient. Reductionist focus on individual nutrients has produced confusion (fat wars, egg debates).",
        "Fasting and intermittent fasting: metabolic switching to ketone bodies during extended fasting has potential benefits for weight, insulin sensitivity, and cellular autophagy.",
        "Food as medicine (Hippocrates): nutrition prevents and treats chronic disease. Dietary intervention can reverse Type 2 diabetes, reduce blood pressure, and lower cardiovascular risk.",
        "Biblical food principles: Levitical dietary laws distinguished clean and unclean animals. Acts 10 and 1 Corinthians 8 address food in the New Covenant context — freedom with consideration of conscience.",
    ],

    # ── QUANTUM COMPUTING ─────────────────────────────────────────────────────
    "quantum_computing": [
        "A qubit (quantum bit) can exist in a superposition of |0⟩ and |1⟩ states simultaneously, unlike a classical bit which is always 0 or 1. Measurement collapses the qubit to a definite state.",
        "Quantum superposition: a qubit in state |ψ⟩ = α|0⟩ + β|1⟩ has probability |α|² of measuring 0 and |β|² of measuring 1. The probabilities must sum to 1: |α|² + |β|² = 1.",
        "Quantum entanglement: two qubits can be correlated such that measuring one instantly determines the state of the other, regardless of distance. Not usable for faster-than-light communication.",
        "Quantum gates are unitary transformations on qubits. The Hadamard gate H creates superposition from |0⟩ or |1⟩. The CNOT gate entangles two qubits. Quantum circuits compose gates.",
        "Quantum interference: quantum algorithms exploit constructive interference (amplify correct answers) and destructive interference (suppress wrong answers) to solve problems efficiently.",
        "Grover's algorithm searches an unsorted database of N items in O(√N) steps — quadratic speedup over classical O(N). Provides a generic speedup for unstructured search problems.",
        "Shor's algorithm factors integers exponentially faster than the best classical algorithm, with implications for RSA cryptography. Requires error-corrected qubits; practical implementation is years away.",
        "Quantum error correction: qubits are fragile; decoherence and gate errors corrupt information. Surface codes and other QEC codes protect logical qubits using many physical qubits (current overhead: 1000:1).",
        "NISQ (Noisy Intermediate-Scale Quantum) era: current quantum computers have 50-1000+ physical qubits but insufficient error correction for fault-tolerant computation.",
        "Quantum supremacy/advantage: Google's 2019 claim that their 53-qubit Sycamore processor performed a specific sampling task in 200 seconds vs. 10,000 years for a classical supercomputer. Disputed by IBM.",
        "The quantum Fourier transform (QFT) is the quantum analog of the discrete Fourier transform, running in O(log²N) time vs. classical O(N log N). Core subroutine in Shor's algorithm.",
        "Quantum annealing: a different computational paradigm that uses quantum tunneling to find low-energy states of optimization problems. D-Wave systems use this approach; utility for practical problems is debated.",
        "Physical qubit implementations: superconducting qubits (Google, IBM), trapped ions (IonQ, Honeywell), photonic qubits, topological qubits (Microsoft's research focus), and neutral atoms.",
        "Quantum key distribution (QKD): BB84 protocol encodes keys in qubit states; eavesdropping disturbs the quantum states and is detectable. Theoretically unbreakable; commercially deployed on fiber and satellite.",
        "Quantum simulation: simulating quantum mechanical systems (molecules, materials) is a natural application of quantum computers. Could accelerate drug discovery, materials science, and chemistry.",
        "The threshold theorem: if physical error rates are below a threshold (~1%), quantum error correction can make logical error rates arbitrarily small. Current best qubit error rates: ~0.1-1%.",
        "Post-quantum cryptography (PQC): classical cryptographic algorithms resistant to quantum attacks. NIST standardized CRYSTALS-Kyber (key exchange) and CRYSTALS-Dilithium (signatures) in 2022.",
        "Quantum complexity classes: BQP (bounded-error quantum polynomial time) contains problems solvable by quantum computers. BQP includes factoring; it is unlikely to contain NP-complete problems.",
        "Quantum teleportation: transfer of a quantum state from one qubit to another using entanglement and classical communication. No matter is teleported; the state is reconstructed, not moved.",
        "The EPB Quantum Network experiment (Chattanooga, TN): using fiber-optic dark channels to transmit QKD keys between nodes. Represents an early US quantum internet testbed.",
    ],

    # ── REAL ESTATE ───────────────────────────────────────────────────────────
    "real_estate": [
        "The three determinants of real estate value: location, location, location. Proximity to employment centers, schools, amenities, and transportation determines desirability.",
        "Cap rate (capitalization rate) = Net Operating Income / Property Value. A cap rate of 5% means 5 cents of NOI per $1 of value. Lower cap rates indicate lower risk/higher prices.",
        "NOI (Net Operating Income) = Gross potential income - vacancy - credit losses - operating expenses (excluding debt service and depreciation). The core metric for income property valuation.",
        "The three approaches to property appraisal: sales comparison (comparing to recent sales of similar properties), income approach (capitalized NOI), and cost approach (land value + depreciated replacement cost).",
        "LTV (loan-to-value ratio) = loan amount / appraised value. Lenders typically require ≤80% LTV for conventional mortgages without PMI. Higher LTV = higher risk for lender.",
        "Amortization: mortgage payments gradually shift from mostly interest (early) to mostly principal (late). A 30-year $300,000 loan at 6%: payment ≈ $1,799/month; ~$273,000 in total interest.",
        "1031 exchange (IRC Section 1031): allows investors to defer capital gains taxes by reinvesting proceeds from a property sale into a 'like-kind' property within specified time limits.",
        "Appreciation vs. cash flow: appreciation is the increase in property value over time; cash flow is periodic income after expenses. Investors typically trade off between the two.",
        "Due diligence in real estate: inspection, title search, environmental review, survey, zoning verification, lease review (for income properties), and review of HOA documents.",
        "Title insurance protects buyers and lenders against title defects (liens, encumbrances, errors) not revealed in the title search. One-time premium paid at closing.",
        "An earnest money deposit (EMD) demonstrates buyer's good faith. Typically 1-3% of purchase price. Forfeited if the buyer defaults; refunded if the seller defaults or contingencies are not met.",
        "Zoning laws regulate land use: residential (R-1, R-2, etc.), commercial, industrial, agricultural, and mixed-use. Non-conforming uses may continue but cannot expand.",
        "The MLS (Multiple Listing Service) is a cooperative database of property listings shared among real estate agents. Allows buyer's agents to access seller's listings.",
        "Short sale: the lender agrees to accept less than the mortgage balance to facilitate a sale, avoiding foreclosure. Requires lender approval and typically involves a longer process.",
        "REITs (Real Estate Investment Trusts) allow individual investors to invest in income-producing real estate portfolios without directly owning property. Required to distribute ≥90% of taxable income.",
        "Property taxes are assessed as a percentage of assessed value. Mill rate: 1 mill = $1 per $1,000 of assessed value. A 20 mill rate on a $200,000 assessed home = $4,000/year.",
        "Easements: a legal right to use another's land for a specific purpose (utility easement, access easement). They run with the land and bind subsequent owners.",
        "The debt service coverage ratio (DSCR) = NOI / annual debt service. Lenders typically require DSCR ≥ 1.25 for commercial real estate loans.",
        "Homeownership builds equity through amortization (paying down principal) and appreciation. It can also impose opportunity cost (vs. investing), illiquidity risk, and maintenance obligations.",
        "Biblical stewardship of land: Leviticus 25:23 — 'The land must not be sold permanently, because the land is mine and you reside in my land as foreigners and strangers.' Land is held in trust.",
    ],

    # ── SOIL SCIENCE ──────────────────────────────────────────────────────────
    "soil_science": [
        "Soil is a complex mixture of mineral particles, organic matter, water, air, and living organisms. It forms over centuries to millennia from weathering of parent material.",
        "Soil texture is determined by the relative proportions of sand (0.05-2 mm), silt (0.002-0.05 mm), and clay (<0.002 mm). The USDA texture triangle classifies 12 textural classes.",
        "Clay particles are plate-like, highly charged, and responsible for most soil chemical activity. Clay minerals (kaolinite, montmorillonite, illite) differ in charge and shrink-swell potential.",
        "Soil organic matter (SOM): decomposed plant, animal, and microbial material that improves structure, water-holding capacity, nutrient availability, and microbial activity. Typically 1-5% in agricultural soils.",
        "The soil food web: bacteria, fungi, protozoa, nematodes, arthropods, and earthworms cycle nutrients and improve structure. Soil health depends on biodiversity and abundance of these organisms.",
        "Cation exchange capacity (CEC): the ability of soil to hold positively charged ions (Ca²⁺, Mg²⁺, K⁺, Na⁺, H⁺). Higher CEC means greater nutrient-holding capacity. Clay and organic matter contribute most.",
        "Soil pH affects nutrient availability and microbial activity. Most nutrients are most available at pH 6.0-7.0. Strongly acidic soils (pH <5.5) increase aluminum and manganese to toxic levels.",
        "Nitrogen cycling in soil: ammonification → nitrification (NH₄⁺ → NO₃⁻ by Nitrosomonas and Nitrobacter) → plant uptake or denitrification (NO₃⁻ → N₂ by anaerobic bacteria).",
        "Phosphorus is often the limiting nutrient in agricultural soils. Unlike nitrogen, phosphorus does not have an atmospheric reservoir and must be mined or recycled. Struvite (MgNH₄PO₄) recovery is emerging.",
        "Soil water: gravitational water drains freely after rain; capillary water (held at field capacity, ~0.03 MPa tension) is available to plants; hygroscopic water (>1.5 MPa tension) is unavailable.",
        "Compaction: tillage, heavy machinery, and animal traffic compact soil, destroying pore space and limiting water infiltration, root penetration, and gas exchange.",
        "Cover crops maintain soil cover year-round, preventing erosion, adding organic matter, fixing nitrogen (legumes), and suppressing weeds. Winter rye, crimson clover, and radishes are common.",
        "No-till farming preserves soil structure by planting through crop residue without tillage, reducing erosion, maintaining soil biota, and sequestering carbon.",
        "Soil carbon sequestration: increasing SOM sequesters atmospheric CO₂. Regenerative agriculture practices (cover crops, compost, reduced tillage) can increase soil carbon at rates of 0.4-1 t C/ha/year.",
        "Erosion: water erosion removes topsoil from slopes; wind erosion affects bare, dry soils. The USLE (Universal Soil Loss Equation) estimates erosion based on rainfall, slope, cover, and practices.",
        "Biochar: charred organic matter added to soil increases CEC, water retention, and microbial habitat. Stable for centuries to millennia; a potential long-duration carbon sink.",
        "Salinization: accumulation of soluble salts in soil, often from irrigation with saline water and inadequate drainage. Reduces osmotic potential, preventing plant water uptake. Affects 20% of irrigated land.",
        "Mycorrhizal fungi associate with plant roots in a mutualistic relationship: plants provide carbon; fungi extend the root system's effective reach, accessing phosphorus, water, and other nutrients.",
        "The Living Soil documentary and Gabe Brown's 'Dirt to Soil' popularized regenerative principles: minimize disturbance, keep soil covered, maintain living roots, diversify species, integrate livestock.",
        "Genesis 2:7 — 'The LORD God formed man from the dust of the ground and breathed into his nostrils the breath of life.' Humanity's origin from and return to soil frames stewardship as sacred.",
    ],

    # ── SPORTS ANALYTICS ─────────────────────────────────────────────────────
    "sports_analytics": [
        "Sabermetrics: the analysis of baseball statistics to evaluate player performance beyond traditional measures. Bill James pioneered it; Moneyball (2003) popularized it via Billy Beane's Oakland A's.",
        "WAR (Wins Above Replacement) estimates how many more wins a player contributes compared to a replacement-level player. Aggregates offensive, defensive, and pitching value into one number.",
        "On-base percentage (OBP) = (H + BB + HBP) / (AB + BB + HBP + SF). Better than batting average because it counts walks. Billy Beane's insight: OBP is undervalued relative to BA.",
        "True shooting percentage (TS%) in basketball = points / (2 × (FGA + 0.44 × FTA)). Accounts for the efficiency difference between 2-point shots, 3-point shots, and free throws.",
        "Player Efficiency Rating (PER) in basketball aggregates per-minute statistical production. Mean PER is ~15; PER >25 indicates elite performance. Created by John Hollinger.",
        "Expected goals (xG) in soccer models the probability that a shot results in a goal based on distance, angle, and shot type. Reveals finishing skill vs. luck over a season.",
        "Win probability (WP): the likelihood a team wins based on current game state (score, time, field position). A model trained on historical outcomes assigns probability at any moment.",
        "Shot quality vs. volume in basketball: the 3-point shot and layup/dunk are highest expected value shots; the mid-range jump shot is least efficient. Analytics has reshaped NBA offense.",
        "Pythagorean expectation (baseball): expected win% = RS²/(RS² + RA²), where RS is runs scored and RA is runs allowed. Teams outperforming their Pythagorean record often regress.",
        "BABIP (Batting Average on Balls in Play) = (H - HR)/(AB - K - HR + SF). Measures how often batted balls fall for hits. Luck normalizes toward ~.300 over time; outliers may indicate skill.",
        "Defensive metrics: Defensive Runs Saved (DRS) and Ultimate Zone Rating (UZR) estimate fielder value. Both compare actual outs made to expected outs based on batted ball location and trajectory.",
        "Pace and possession-based analytics: normalizing NBA statistics per 100 possessions rather than per game allows fair comparison across teams with different pace.",
        "The hot hand fallacy: belief that a player who has been scoring is more likely to score next. Research is mixed: original studies found no hot hand; recent work finds small effects in free throws and 3-pointers.",
        "Draft analytics: evaluating draft prospects using measurable attributes (speed, strength, college statistics, age). The NFL Combine, NBA draft combine, and European soccer scouting use advanced metrics.",
        "Load management: deliberately limiting player minutes to prevent injury. Analytics-driven decision: injury prevention vs. regular-season performance trade-off. Controversial with fans; defensible with long-term data.",
        "Exit velocity and launch angle in baseball: Statcast data from radar and camera systems measures every batted ball. High exit velocity + optimal launch angle (25-35°) maximizes home run probability.",
        "Moneyball principle: market inefficiencies in athlete valuation create arbitrage opportunities. Identify undervalued skills, exploit them until the market corrects. Applies broadly beyond baseball.",
        "Gambling and integrity risks: sports analytics feeds a growing sports betting market. Insider information, match-fixing, and corruption are serious concerns requiring regulation and monitoring.",
        "Pass completion percentage (completion% over expectation, CPOE) in football measures quarterback accuracy against expected completion rate based on throw distance, coverage, and receiver separation.",
        "The 1-3-5-7 framework and similar analytic systems quantify coaching decisions: going for it on 4th down, two-point conversions, run/pass ratios — all subject to expected value optimization.",
    ],

}


# ── helpers ────────────────────────────────────────────────────────────────────

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def load_state() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text())["posted"])
    return set()

def save_state(posted: set) -> None:
    STATE_FILE.write_text(json.dumps({"posted": sorted(posted)}, indent=2))

def post_seed(session, text: str, domain: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"  [DRY] {domain}: {text[:60]}…")
        return True
    try:
        r = session.post(f"{API_BASE}/capture",
                         json={"text": text, "source": f"seed:{domain}",
                               "tags": [domain, "seed", "curated"]},
                         timeout=30)
        if r.status_code == 200:
            d = r.json()
            total = d.get("calibration", {}).get("total_entries_to_date", "?")
            print(f"  ✓ #{total}  {domain}: {text[:55]}…")
            return True
        else:
            print(f"  ✗ HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    posted = set() if args.reset else load_state()

    if not args.dry_run:
        try:
            r = requests.get(f"{API_BASE}/health", timeout=5); r.raise_for_status()
            print(f"✓ Server at {API_BASE} is up")
        except Exception as e:
            sys.exit(f"✗ {API_BASE}: {e}")

    session = requests.Session()
    session.headers["Content-Type"] = "application/json"

    domains = {args.domain: SEEDS[args.domain]} if args.domain and args.domain in SEEDS else SEEDS

    total = skipped = failed = 0
    for domain, texts in sorted(domains.items(), key=lambda x: len(x[1])):
        print(f"\n── {domain.upper()} ({len(texts)} seeds) ──")
        for text in texts:
            h = hash_text(text)
            if h in posted:
                skipped += 1
                continue
            ok = post_seed(session, text, domain, args.dry_run)
            if ok:
                total += 1; posted.add(h)
                if not args.dry_run: save_state(posted); time.sleep(args.delay)
            else:
                failed += 1; time.sleep(args.delay * 2)

    print(f"\n  Posted: {total}  Skipped: {skipped}  Failed: {failed}")

if __name__ == "__main__":
    main()
