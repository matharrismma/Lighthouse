"""
seed_domains.py — Curated domain seed packets for Concordance
─────────────────────────────────────────────────────────────
Posts carefully crafted knowledge statements to /capture so the engine
has solid precedent cases in every domain before user traffic arrives.

Focuses on the thinnest domains first, then fills all 48.
Each seed is a real, verifiable claim — not lorem ipsum.

Usage:
    python scripts/seed/seed_domains.py                  # all domains
    python scripts/seed/seed_domains.py --domain biology # one domain
    python scripts/seed/seed_domains.py --dry-run        # no POST, just print
    python scripts/seed/seed_domains.py --delay 0.5      # faster (default 1.2s)
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

API_BASE  = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "seed_state.json"

# ── seed corpus ───────────────────────────────────────────────────────────────
# Each entry: (domain_hint, text)
# domain_hint is appended as a source tag so the classifier gets a nudge;
# the engine's own classifier assigns the final domain.

SEEDS: dict[str, list[str]] = {

    # ── COMPUTER SCIENCE (1 packet — most urgent) ─────────────────────────────
    "computer_science": [
        "A binary search algorithm finds a target value in a sorted array by repeatedly halving the search interval, achieving O(log n) time complexity.",
        "A hash table achieves amortized O(1) average-case lookup by mapping keys to array indices via a hash function, with collision resolution by chaining or open addressing.",
        "Dijkstra's algorithm computes the shortest path from a single source to all vertices in a weighted graph with non-negative edge weights in O((V + E) log V) time.",
        "A stack is a last-in, first-out data structure; a queue is first-in, first-out. Both support push/enqueue and pop/dequeue in O(1) time with array or linked-list backing.",
        "Dynamic programming solves problems by breaking them into overlapping subproblems and storing solutions in a table to avoid recomputation — memoization top-down, tabulation bottom-up.",
        "The P vs NP problem asks whether every problem whose solution can be verified quickly can also be solved quickly. It remains unsolved and is one of the seven Millennium Prize Problems.",
        "A Turing machine is a theoretical model of computation consisting of an infinite tape, a read/write head, a finite set of states, and a transition function. Church-Turing thesis: any computable function can be computed by a Turing machine.",
        "Merge sort divides an array in half recursively and merges the sorted halves, achieving O(n log n) time and O(n) auxiliary space — stable and predictable.",
        "A recursive function calls itself with a smaller subproblem and terminates at a base case. Without a base case, recursion causes a stack overflow.",
        "Big-O notation describes the asymptotic upper bound on algorithm growth rate. O(1) is constant, O(log n) logarithmic, O(n) linear, O(n log n) linearithmic, O(n²) quadratic.",
        "A linked list stores elements in nodes where each node holds data and a pointer to the next node. Insertion and deletion are O(1) at a known position; search is O(n).",
        "The two's complement representation allows signed integers to be stored in binary such that subtraction can be performed using the same circuitry as addition.",
        "A compiler translates high-level source code to machine code in phases: lexical analysis, parsing, semantic analysis, intermediate code generation, optimization, and code generation.",
        "TCP provides reliable, ordered, error-checked delivery of a byte stream between applications. UDP provides connectionless, low-latency delivery without guaranteed order or delivery.",
        "SQL's ACID properties — Atomicity, Consistency, Isolation, Durability — guarantee that database transactions are processed reliably even in the event of system failures.",
        "A mutex (mutual exclusion lock) prevents multiple threads from simultaneously accessing a shared resource, avoiding race conditions in concurrent programs.",
        "Public-key cryptography uses a key pair: a public key for encryption, a private key for decryption. RSA relies on the computational difficulty of factoring large integers.",
        "The CAP theorem states that a distributed system can guarantee at most two of: Consistency, Availability, and Partition tolerance simultaneously.",
        "Git tracks changes as a directed acyclic graph of commits. Each commit stores a snapshot, author, timestamp, and parent hash, forming an immutable chain.",
        "Object-oriented programming encapsulates data (attributes) and behavior (methods) in objects. Inheritance, polymorphism, and encapsulation are its three core principles.",
        "A REST API uses HTTP methods (GET, POST, PUT, DELETE) and stateless requests to expose resources identified by URIs, returning structured data (typically JSON).",
        "Garbage collection automatically reclaims memory occupied by objects that are no longer reachable, using algorithms like mark-and-sweep, reference counting, or generational GC.",
        "The halting problem is undecidable: there is no general algorithm that determines whether an arbitrary program will halt or run forever. Proved by Turing in 1936.",
        "A neural network is a layered model of weighted connections. Training adjusts weights via backpropagation to minimize a loss function using gradient descent.",
        "Version control systems track file changes over time, enabling collaboration, rollback, branching, and merging. Git, SVN, and Mercurial are common implementations.",
        "The ISO/OSI model describes network communication in 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application.",
        "A regular expression is a pattern-matching language for strings. Finite automata theory proves that regular expressions correspond exactly to languages recognized by finite automata.",
        "Asymptotic analysis studies algorithm behavior as input size grows toward infinity, abstracting away constant factors and lower-order terms to identify the dominant cost.",
        "A B-tree is a self-balancing search tree optimized for disk storage. It maintains sorted data and allows searches, insertions, and deletions in O(log n) time.",
        "A function is pure if it always returns the same output for the same input and has no side effects. Pure functions are easy to test, parallelize, and reason about.",
        "Moore's Law observed that transistor density on integrated circuits doubles approximately every two years, enabling exponential growth in computing power from 1965 through roughly 2015.",
        "A deadlock occurs when two or more threads each hold a resource the other needs and neither can proceed. Prevention requires resource ordering or timeout-based detection.",
        "The Von Neumann architecture stores program instructions and data in the same memory, with a processor fetching and executing instructions sequentially via a fetch-decode-execute cycle.",
        "A bloom filter is a space-efficient probabilistic data structure that tests set membership with possible false positives but no false negatives.",
        "Code complexity measured by cyclomatic complexity counts the number of independent paths through a function. Lower values indicate simpler, more testable code.",
        "An API (Application Programming Interface) is a contract specifying how software components communicate — defining inputs, outputs, and error conditions without exposing internal implementation.",
        "Containerization (Docker, OCI) packages an application and its dependencies into an isolated unit, ensuring consistent behavior across development, testing, and production environments.",
        "The Liskov Substitution Principle states that objects of a subtype must be substitutable for objects of the supertype without altering program correctness.",
        "Eventual consistency in distributed systems guarantees that, if no new updates are made, all replicas will eventually converge to the same value — used in Cassandra, DynamoDB.",
        "Test-driven development writes failing tests before writing code, then writes the minimum code to pass, then refactors. The cycle is Red → Green → Refactor.",
        "A cache stores frequently accessed data in faster memory closer to the processor. Cache hit rates and eviction policies (LRU, LFU, FIFO) determine performance impact.",
        "The observer pattern defines a one-to-many dependency so that when one object changes state, all dependents are notified automatically — the foundation of event-driven systems.",
        "Idempotency means applying an operation multiple times produces the same result as applying it once. Critical for safe HTTP PUT/DELETE and retry-safe distributed systems.",
        "Formal verification uses mathematical proofs to guarantee that a program or system meets its specification. Used in safety-critical aerospace, medical, and cryptographic code.",
        "Shannon entropy H = -Σ p(x) log p(x) measures the average information content of a message source. Maximum entropy = maximum unpredictability = maximum compression opportunity.",
        "A microservices architecture decomposes an application into small, independently deployable services communicating over APIs, enabling independent scaling and technology choice per service.",
        "The Law of Demeter (principle of least knowledge) states that a module should only interact with its immediate collaborators and not 'reach through' objects to access distant components.",
        "Functional programming treats computation as the evaluation of mathematical functions, avoiding mutable state and side effects. Map, filter, and reduce are its primary combinators.",
        "Encryption at rest protects stored data; encryption in transit protects data moving over networks. Both are required for defense-in-depth against data breaches.",
        "A parser converts a stream of tokens into an abstract syntax tree according to a formal grammar. Recursive descent parsers implement grammar rules directly as function calls.",
    ],

    # ── PHYSICS (2-3 packets each sub-domain) ─────────────────────────────────
    "physics": [
        "Newton's first law: an object remains at rest or in uniform motion unless acted upon by a net external force. This is the law of inertia.",
        "Newton's second law: F = ma. Force equals mass times acceleration. A 1 kg object accelerating at 1 m/s² requires 1 Newton of net force.",
        "Newton's third law: for every action there is an equal and opposite reaction. Forces always occur in pairs acting on different objects.",
        "The law of conservation of energy states that energy cannot be created or destroyed, only converted between forms. Total energy in a closed system is constant.",
        "The law of conservation of momentum states that the total momentum of a closed system remains constant if no external forces act on it.",
        "Kinetic energy KE = ½mv² where m is mass and v is velocity. A 2 kg object moving at 3 m/s has KE = 9 joules.",
        "Gravitational potential energy PE = mgh where m is mass, g is gravitational acceleration (9.81 m/s² near Earth's surface), and h is height.",
        "The speed of light in a vacuum is approximately 2.998 × 10⁸ m/s. No object with mass can reach or exceed this speed.",
        "Special relativity: time dilation means a moving clock runs slower relative to a stationary observer. At velocity v, the Lorentz factor γ = 1/√(1 - v²/c²).",
        "The first law of thermodynamics: ΔU = Q - W. The internal energy change equals heat added minus work done by the system. Energy is conserved.",
        "The second law of thermodynamics: entropy of an isolated system never decreases. Heat flows spontaneously from hot to cold, never the reverse.",
        "Absolute zero (0 K = -273.15°C) is the theoretical minimum temperature where all thermal motion ceases. The third law states entropy approaches a minimum at absolute zero.",
        "The photoelectric effect demonstrates that light behaves as discrete quanta (photons). Einstein's explanation won the 1921 Nobel Prize and established quantum mechanics.",
        "Wave-particle duality: quantum objects exhibit properties of both waves and particles. An electron fired through a double slit produces an interference pattern.",
        "Heisenberg's uncertainty principle: Δx · Δp ≥ ħ/2. Position and momentum cannot both be known with arbitrary precision simultaneously.",
        "Coulomb's law: F = k q₁q₂/r². The electrostatic force between two charges is proportional to their magnitudes and inversely proportional to the distance squared.",
        "Ohm's law: V = IR. Voltage equals current times resistance. A 12V source across 4Ω resistance drives 3 amperes of current.",
        "Maxwell's equations unify electricity, magnetism, and optics. They predict that light is an electromagnetic wave and that its speed in vacuum is constant.",
        "Dimensional analysis verifies equations by checking that units on both sides match. An equation relating force, mass, and acceleration must yield kg·m/s² on both sides.",
        "Conservation of charge: the total electric charge in a closed system is constant. Charge is quantized in units of the elementary charge e = 1.602 × 10⁻¹⁹ C.",
        "The Doppler effect: a wave source moving toward an observer produces shorter wavelengths (higher frequency); moving away produces longer wavelengths (lower frequency).",
        "Archimedes' principle: a body submerged in fluid experiences a buoyant force equal to the weight of the displaced fluid. An object floats if its density is less than the fluid's.",
        "Simple harmonic motion: a restoring force proportional to displacement produces oscillation. Period T = 2π√(m/k) for a mass on a spring with spring constant k.",
        "The electromagnetic spectrum spans radio, microwave, infrared, visible, ultraviolet, X-ray, and gamma radiation in order of increasing frequency and decreasing wavelength.",
        "Radioactive decay follows an exponential law: N(t) = N₀ e^(-λt). Half-life T½ = ln2/λ is the time for half the atoms to decay.",
        "Nuclear fission splits heavy nuclei (U-235, Pu-239) releasing binding energy. Nuclear fusion joins light nuclei (deuterium, tritium) releasing even more energy per unit mass.",
        "The Stefan-Boltzmann law: power radiated per unit area ∝ T⁴. A blackbody at twice the temperature radiates 16 times the power.",
        "Snell's law: n₁ sin θ₁ = n₂ sin θ₂ governs refraction at an interface between media with refractive indices n₁ and n₂.",
        "Pascal's principle: pressure applied to a confined fluid is transmitted equally in all directions. Hydraulic systems amplify force by area ratio.",
        "Work = force × displacement × cos θ. If force and displacement are perpendicular, no work is done regardless of force magnitude.",
        "Power = work / time = force × velocity. Measured in watts (1 W = 1 J/s). A 100W bulb uses 100 joules of energy per second.",
        "Center of mass motion: the center of mass of a system moves as if all external forces act on a single particle of total mass at that point.",
        "Fermi estimation: order-of-magnitude approximations using known quantities and dimensional reasoning. Used to check calculations and probe unknowns.",
    ],

    # ── LINGUISTICS (16 packets — needs depth) ────────────────────────────────
    "linguistics": [
        "Phonemes are the smallest units of sound that distinguish meaning in a language. English has approximately 44 phonemes, though it has only 26 letters.",
        "Morphemes are the smallest meaningful units of language. 'Unbreakable' contains three: un- (not), break (core meaning), -able (capable of).",
        "Syntax is the set of rules governing how words combine into phrases and sentences. Subject-Verb-Object is the dominant order in English.",
        "Semantics studies the meaning of words, phrases, and sentences. Pragmatics studies how context affects meaning beyond literal content.",
        "The Sapir-Whorf hypothesis (linguistic relativity) proposes that the language we speak influences how we think and perceive the world.",
        "A language family is a group of languages descended from a common ancestral language (proto-language). Indo-European is the world's largest family by speakers.",
        "Code-switching is the practice of alternating between two or more languages or dialects within a single conversation or even sentence.",
        "Phonology studies the sound systems of languages — which sounds exist, how they pattern, and how they interact. Every language has its own phonological inventory.",
        "Morphology is the study of word structure and formation. Inflectional morphology marks grammatical categories (tense, number); derivational morphology creates new words.",
        "Language acquisition: children acquire their native language through exposure without explicit instruction. Critical period theory suggests acquisition is optimal before puberty.",
        "The Greek word logos (λόγος) means word, reason, discourse, and divine principle simultaneously. John 1:1 uses logos for the pre-existent Christ, grounding language in theology.",
        "Etymology traces the origin and historical development of words. Understanding etymology reveals conceptual genealogies and clarifies meaning.",
        "Discourse analysis examines language use above the sentence level — how texts and conversations are structured, how coherence is achieved.",
        "A dialect is a regional or social variety of a language distinguished by pronunciation, vocabulary, and grammar. All dialects are linguistically equal; none is more 'correct.'",
        "Pidgins arise as contact languages between groups with no common tongue. When children acquire a pidgin as a native language, it becomes a creole — fully systematic.",
        "Koine Greek (κοινή) was the common dialect of the Hellenistic world and the language of the New Testament, enabling the gospel to reach diverse peoples across the Roman Empire.",
        "The Hebrew word dabar (דָּבָר) means both 'word' and 'deed/event' — language in the Old Testament is inherently performative; God speaks and things come to be.",
        "Evidentiality is a grammatical category marking the speaker's source of information: direct witness, hearsay, inference. Some languages grammatically require it.",
        "A speech act is an utterance that performs an action: asserting, promising, commanding, questioning. Austin and Searle identified locutionary, illocutionary, perlocutionary acts.",
        "The Great Vowel Shift (1400–1700 AD) transformed English vowel pronunciation dramatically, explaining why English spelling often diverges from pronunciation.",
        "Language universals are features found in all known human languages: all have nouns and verbs, all distinguish statements from questions, all have pronoun systems.",
        "Polysemy: a single word with multiple related meanings ('bank': financial institution, riverbank). Homonymy: same sound, unrelated meanings ('bat': cricket bat, flying bat).",
        "Presupposition: information assumed true before a sentence is uttered. 'Have you stopped lying?' presupposes the person was lying — the question traps either answer.",
        "Oral tradition in pre-literate cultures transmits knowledge through memorized formulaic speech. The Iliad, Homeric epics, and early Scripture show oral composition patterns.",
        "Genre and register: the same speaker uses different linguistic forms in a sermon, a text message, and a legal brief. Register is context-appropriate language variation.",
        "Transliteration renders words from one script into another; translation renders meaning. Transliteration of 'amen' (אָמֵן) preserves the Hebrew; translation would be 'truly' or 'so be it.'",
        "The Tower of Babel account (Genesis 11) provides a theological framework for linguistic diversity. The reversal at Pentecost (Acts 2) demonstrates God's redemptive purpose for all languages.",
        "Biblical hermeneutics interprets Scripture using grammatical-historical method: determine the original meaning by studying grammar, historical context, and literary genre.",
        "Metonymy substitutes a related concept: 'the Crown' for the monarchy, 'the pen' for writing. Synecdoche uses part for whole: 'hands' for workers, 'sails' for ships.",
        "Alliteration, assonance, chiasm, and parallelism are rhetorical structures found throughout Hebrew poetry and Pauline epistles, serving mnemonic and emphatic functions.",
    ],

    # ── BIOLOGY ───────────────────────────────────────────────────────────────
    "biology": [
        "Cell theory: all living organisms are composed of cells; the cell is the basic unit of life; all cells arise from pre-existing cells.",
        "DNA (deoxyribonucleic acid) stores genetic information in sequences of four bases: adenine (A), thymine (T), guanine (G), and cytosine (C). A pairs with T; G pairs with C.",
        "The central dogma of molecular biology: DNA is transcribed to RNA, which is translated into protein. Information flows in one direction under normal circumstances.",
        "Natural selection: heritable traits that increase reproductive success become more common in a population over generations. Darwin's mechanism for evolutionary change.",
        "The human genome contains approximately 3 billion base pairs encoding roughly 20,000-25,000 protein-coding genes — less than 2% of total DNA.",
        "Photosynthesis converts CO₂ and H₂O into glucose and O₂ using light energy: 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂. Occurs in chloroplasts.",
        "Cellular respiration: C₆H₁₂O₆ + 6O₂ → 6CO₂ + 6H₂O + ATP. Releases energy stored in glucose. Mitochondria are the primary site.",
        "Meiosis reduces chromosome number by half, producing gametes (sperm/eggs) with 23 chromosomes. Fertilization restores the diploid number of 46.",
        "Mitosis produces two genetically identical daughter cells from one parent cell. It underlies growth, repair, and asexual reproduction.",
        "Homeostasis is the maintenance of stable internal conditions (temperature, pH, blood glucose) in the face of changing external conditions.",
        "The immune system distinguishes self from non-self. Innate immunity responds nonspecifically; adaptive immunity produces antigen-specific antibodies and memory cells.",
        "Enzymes are biological catalysts — proteins (or RNA) that lower the activation energy of reactions without being consumed. Each enzyme has an optimal pH and temperature.",
        "Ecosystems cycle matter and flow energy. Producers fix solar energy; consumers transfer it; decomposers return nutrients to the soil.",
        "Biodiversity at genetic, species, and ecosystem levels increases ecosystem resilience and provides the raw material for adaptation.",
        "Cell differentiation: all cells in an organism contain the same DNA, but gene expression patterns differ, producing the ~200 distinct cell types in the human body.",
        "Viruses are not cells. They are particles containing nucleic acid (DNA or RNA) enclosed in a protein coat (capsid), requiring host cell machinery to replicate.",
        "The phylogenetic tree of life has three domains: Bacteria, Archaea, and Eukarya. All share common ancestry, evidenced by the universal genetic code.",
        "Epigenetics: heritable changes in gene expression that do not alter DNA sequence. Methylation and histone modification can switch genes on or off across generations.",
        "The nitrogen cycle: nitrogen gas (N₂) is fixed by bacteria into ammonium, converted to nitrate by nitrifying bacteria, absorbed by plants, and returned to atmosphere by denitrifiers.",
        "Hormones are chemical messengers produced by endocrine glands that travel through the bloodstream to regulate distant target organs.",
        "ATP (adenosine triphosphate) is the universal energy currency of cells. The hydrolysis of one ATP molecule releases approximately 7.3 kcal/mol.",
        "Apoptosis (programmed cell death) is essential for development, immune function, and cancer suppression. Dysregulation contributes to cancer and autoimmune diseases.",
        "The blood-brain barrier is formed by tight junctions between brain capillary endothelial cells, protecting the CNS from most pathogens and toxins in the bloodstream.",
        "CRISPR-Cas9 allows precise editing of DNA at specific sequences. It uses a guide RNA to direct the Cas9 enzyme to cut the target location in the genome.",
        "Stem cells are undifferentiated cells capable of self-renewal and differentiation into specialized cell types. Embryonic stem cells are pluripotent; adult stem cells are multipotent.",
        "The gut microbiome contains ~38 trillion bacteria with profound effects on digestion, immunity, mental health, and metabolism. Its composition varies by diet, antibiotics, and environment.",
        "Biofilm formation: bacteria attach to surfaces and produce extracellular matrix, creating structured communities up to 1,000× more antibiotic-resistant than planktonic cells.",
        "Mendel's laws: law of segregation (each gamete gets one allele from each gene pair); law of independent assortment (alleles of different genes assort independently).",
        "Convergent evolution produces similar structures in unrelated lineages through similar selective pressures — wings in bats and birds, eyes in vertebrates and octopuses.",
        "Telomeres cap chromosome ends and shorten with each cell division. Telomere shortening is associated with aging; telomerase can extend them in germ cells and cancer cells.",
    ],

    # ── NUMBER THEORY ─────────────────────────────────────────────────────────
    "number_theory": [
        "A prime number has exactly two distinct positive divisors: 1 and itself. 2 is the only even prime. There are infinitely many primes (Euclid's proof, c. 300 BC).",
        "The Fundamental Theorem of Arithmetic: every integer greater than 1 is either prime or a unique product of primes (up to ordering).",
        "The Euclidean algorithm computes the GCD of two integers by repeated division. GCD(48, 18) = GCD(18, 12) = GCD(12, 6) = 6.",
        "Bezout's identity: for integers a and b with GCD d, there exist integers x, y such that ax + by = d. This is the basis for modular inverses.",
        "Fermat's Little Theorem: if p is prime and a is not divisible by p, then a^(p-1) ≡ 1 (mod p). Forms the basis of RSA primality testing.",
        "Euler's totient function φ(n) counts positive integers ≤ n that are coprime to n. For prime p: φ(p) = p-1. For RSA: φ(pq) = (p-1)(q-1).",
        "A perfect number equals the sum of its proper divisors. 6 = 1+2+3; 28 = 1+2+4+7+14. All known perfect numbers are even; it is unknown whether odd perfect numbers exist.",
        "The Sieve of Eratosthenes finds all primes up to N by iteratively marking composites starting from 2, then 3, then each unmarked number.",
        "Modular arithmetic: a ≡ b (mod m) means m divides (a-b). The integers mod m form a ring under addition and multiplication.",
        "The Chinese Remainder Theorem: if m₁, m₂, ..., mₖ are pairwise coprime, the system x ≡ aᵢ (mod mᵢ) has a unique solution mod (m₁m₂...mₖ).",
        "A Mersenne prime has the form 2^p - 1 where p is prime. The largest known primes are almost always Mersenne primes, found by the distributed GIMPS project.",
        "Goldbach's conjecture (1742, unproved): every even integer greater than 2 is the sum of two primes. Verified up to 4 × 10¹⁸.",
        "Diophantine equations require integer solutions. Fermat's Last Theorem: x^n + y^n = z^n has no positive integer solutions for n > 2. Proved by Wiles in 1994.",
        "The Riemann hypothesis concerns the zeros of the Riemann zeta function ζ(s) and predicts the distribution of prime numbers. One of the seven Millennium Prize Problems.",
        "Quadratic residues: a is a quadratic residue mod p if there exists x with x² ≡ a (mod p). The Legendre symbol (a|p) = ±1 or 0 encodes this.",
        "Every positive integer is the sum of at most four perfect squares (Lagrange's four-square theorem). 7 = 4+1+1+1. This is tight — 7 needs exactly four.",
        "The sum of the first n natural numbers is n(n+1)/2. Attributed to Gauss who allegedly computed 1+2+...+100 = 5050 as a schoolboy by pairing terms.",
        "Modular exponentiation allows computing a^b mod m efficiently using repeated squaring, critical for RSA and Diffie-Hellman key exchange.",
        "The greatest common divisor and least common multiple: GCD(a,b) × LCM(a,b) = a × b. LCM(12,18) = 36; GCD(12,18) = 6; 36 × 6 = 216 = 12 × 18.",
        "Twin primes are pairs differing by 2: (3,5), (5,7), (11,13), (17,19). The twin prime conjecture says there are infinitely many — unproved.",
        "Continued fractions represent real numbers as a₀ + 1/(a₁ + 1/(a₂ + ...)); rational numbers terminate; quadratic irrationals repeat; transcendentals are irregular.",
        "Wilson's theorem: (p-1)! ≡ -1 (mod p) if and only if p is prime. Provides a theoretical primality test, though computationally impractical for large numbers.",
        "A Pythagorean triple (a, b, c) satisfies a² + b² = c². The primitive triples are generated by m > n > 0 with GCD(m,n)=1: a=m²-n², b=2mn, c=m²+n².",
        "The harmonic series Σ 1/n diverges (proved by Nicole Oresme c. 1350) yet individual terms approach zero — illustrating that a necessary condition for convergence is not sufficient.",
        "Casting out nines: a number's digital root equals its value mod 9. Used to check arithmetic: if the digital roots of operands don't satisfy the operation, there's an error.",
    ],

    # ── INFORMATION THEORY ────────────────────────────────────────────────────
    "information_theory": [
        "Shannon's source coding theorem: data can be compressed losslessly to at most H(X) bits per symbol on average, where H(X) = -Σ p(x) log₂ p(x) is the source entropy.",
        "Shannon capacity C = B log₂(1 + S/N) gives the maximum rate of error-free data transmission over a channel with bandwidth B and signal-to-noise ratio S/N.",
        "Mutual information I(X;Y) measures how much knowing one variable reduces uncertainty about another. I(X;Y) = H(X) - H(X|Y) ≥ 0.",
        "Huffman coding assigns shorter codes to more frequent symbols, achieving entropy-optimal prefix-free codes. Variable-length codes can beat fixed-length codes.",
        "Run-length encoding compresses sequences of repeated values (e.g., AAABBBCCCC → 3A3B4C). Efficient for sparse data but wasteful for uniformly random data.",
        "Lossless compression (ZIP, FLAC, PNG) recovers the original exactly. Lossy compression (JPEG, MP3) discards imperceptible information for higher compression ratios.",
        "Error-correcting codes add redundancy so errors can be detected and corrected. Hamming codes can correct 1-bit errors in 7-bit blocks using 3 parity bits.",
        "The Kolmogorov complexity K(x) of a string x is the length of the shortest program that outputs x. Incompressible strings are 'random'; most strings are incompressible.",
        "Data compression exploits statistical redundancy. English text has roughly 1–1.5 bits of entropy per character despite using 8 bits in ASCII encoding.",
        "The binary symmetric channel flips each bit with probability p independently. Capacity = 1 - H(p) = 1 + p log p + (1-p) log(1-p).",
        "Entropy is maximized when all outcomes are equally likely. A fair coin flip has entropy H = 1 bit. A biased coin has H < 1 bit.",
        "Cross-entropy H(p, q) = -Σ p(x) log q(x) measures the average bits needed to encode outcomes under true distribution p using model q. KL divergence = H(p,q) - H(p).",
        "Rate-distortion theory quantifies the minimum information rate to transmit a source at a given distortion. It sets theoretical limits for lossy compression.",
        "Turbo codes and LDPC codes approach the Shannon limit in practice, achieving near-capacity performance. Used in 4G/5G cellular and satellite communications.",
        "The Reed-Solomon code is used in CDs, DVDs, QR codes, and space probes. It corrects burst errors by treating data as polynomial coefficients over a finite field.",
        "Information is physical: Landauer's principle states that erasing one bit of information must dissipate at least kT ln 2 joules of energy, linking information to thermodynamics.",
        "Steganography hides information within other data. Watermarking embeds traceable identifiers. Both exploit the gap between the information capacity and the used capacity.",
        "Nyquist-Shannon sampling theorem: a bandlimited signal with maximum frequency f must be sampled at least 2f times per second to allow perfect reconstruction.",
        "Network information theory extends single-user theory to multi-user channels: broadcast channels, multiple-access channels, relay channels, and interference channels.",
        "The minimum description length (MDL) principle selects the model that best compresses the data, balancing model complexity against fit. Grounded in Kolmogorov complexity.",
    ],

    # ── HYDROLOGY ─────────────────────────────────────────────────────────────
    "hydrology": [
        "The hydrological cycle describes the continuous movement of water: evaporation from oceans and land → condensation into clouds → precipitation → surface runoff and infiltration → groundwater → evaporation again.",
        "A watershed (drainage basin) is the land area that collects precipitation and drains to a common outlet. Watersheds are separated by topographic divides.",
        "Groundwater is water held in the pores and fractures of saturated rock and sediment (aquifer). The water table is the upper surface of saturated ground.",
        "Darcy's law governs groundwater flow: Q = -KA(dh/dl), where Q is flux, K is hydraulic conductivity, A is cross-section, and dh/dl is hydraulic gradient.",
        "Evapotranspiration (ET) is the combined water loss through soil evaporation and plant transpiration. In many temperate watersheds, ET accounts for 60-70% of annual precipitation.",
        "Flood frequency analysis uses historical records to estimate the return period of flood events. A '100-year flood' has a 1% probability of occurring in any given year.",
        "Stream discharge Q = A × v, where A is cross-sectional area and v is mean velocity. Measured in cubic meters per second (m³/s).",
        "The rational method estimates peak runoff Q = CiA, where C is the runoff coefficient, i is rainfall intensity, and A is the drainage area. Used for small urban watersheds.",
        "Aquifer types: unconfined aquifers are overlain by permeable material and recharged from the surface; confined aquifers are bounded above by an impermeable layer and under pressure.",
        "Water quality parameters include pH, dissolved oxygen, turbidity, conductivity, BOD (biochemical oxygen demand), and concentrations of nitrates, phosphates, and heavy metals.",
        "Precipitation is not uniformly distributed. Orographic lift forces air up mountain slopes, causing precipitation on windward sides and rain shadows on leeward sides.",
        "Soil infiltration rate is the speed at which soil absorbs water. Clay soils have low infiltration; sandy soils high. Saturation reduces infiltration to zero.",
        "Streamflow hydrograph: a plot of discharge vs. time showing baseflow (groundwater contribution) and storm flow (surface runoff). The rising limb is steeper than the falling limb.",
        "Drought: prolonged deficit of precipitation relative to average. Hydrological drought is measured by stream and groundwater levels, lagging behind meteorological drought.",
        "Water balance equation: P = ET + R + ΔS, where P is precipitation, ET is evapotranspiration, R is runoff, and ΔS is change in storage.",
        "Constructed wetlands remove pollutants through sedimentation, plant uptake, and microbial degradation. Used for wastewater treatment and agricultural runoff management.",
        "The Colorado River Compact (1922) divided the river's water among seven US states. Overallocation has led to chronic deficits — the river often reaches the sea with no water.",
        "Saltwater intrusion: pumping coastal aquifers beyond recharge causes seawater to migrate inland, contaminating freshwater supplies. Irreversible without managed aquifer recharge.",
        "Hydraulic fracturing (fracking) injects water, sand, and chemicals at high pressure to fracture shale formations. Concerns include water use, wastewater disposal, and contamination.",
        "The Ogallala Aquifer underlies 8 US Great Plains states and supplies 30% of US groundwater used for irrigation. It is being depleted far faster than recharge rates.",
    ],

    # ── MANUFACTURING ─────────────────────────────────────────────────────────
    "manufacturing": [
        "Lean manufacturing eliminates waste (muda) in 7 categories: overproduction, waiting, transportation, over-processing, inventory, motion, and defects. Originated at Toyota.",
        "The Kanban system uses visual signals to control production flow, triggering upstream production only when downstream needs arise — a pull system, not push.",
        "Six Sigma aims to reduce process defects to fewer than 3.4 per million opportunities, using DMAIC (Define, Measure, Analyze, Improve, Control) methodology.",
        "Tolerance stackup analysis calculates how individual part tolerances combine in an assembly. Statistical (RSS) analysis is less conservative than worst-case (arithmetic) analysis.",
        "CNC (computer numerical control) machining uses programmed instructions to control tool path. G-code specifies movements; M-code controls machine functions.",
        "Injection molding forces molten plastic into a mold under high pressure. Cycle time = fill + pack + cool + eject. Wall thickness uniformity prevents sink marks and warpage.",
        "Welding joins metals by fusion. MIG (GMAW), TIG (GTAW), and arc welding differ in electrode, shielding gas, and application. Weld quality is affected by heat input and travel speed.",
        "Statistical process control (SPC) monitors production using control charts. Points outside 3-sigma control limits signal process shifts requiring investigation.",
        "Design for manufacturability (DFM) modifies designs to reduce production costs: minimize part count, use standard components, simplify assembly, design for handling.",
        "Additive manufacturing (3D printing) builds parts layer by layer from digital models. FDM, SLA, SLS, and DMLS suit different materials and precision requirements.",
        "Material removal rate (MRR) in machining = depth of cut × feed × cutting speed. Increasing any parameter increases MRR but also heat, tool wear, and potential chatter.",
        "First article inspection (FAI) verifies that the first production part meets all drawing requirements before full production proceeds. AS9102 governs aerospace FAI.",
        "Bill of materials (BOM) lists all parts, assemblies, and quantities needed to build a product. The multi-level BOM shows parent-child relationships between assemblies.",
        "FMEA (Failure Mode and Effects Analysis) systematically identifies failure modes, their effects, and preventive actions. RPN = Severity × Occurrence × Detection.",
        "ISO 9001 certification requires a documented quality management system with processes for planning, customer focus, risk management, and continuous improvement.",
        "Just-in-time (JIT) delivery receives materials exactly when needed, minimizing inventory carrying costs. Vulnerable to supply chain disruptions; requires reliable suppliers.",
        "Poka-yoke (mistake-proofing) designs processes so errors are impossible or immediately detected. Asymmetric connectors, limit switches, and sensors are common implementations.",
        "Heat treatment changes metal properties through controlled heating and cooling cycles. Annealing softens; quenching hardens; tempering reduces brittleness after hardening.",
        "Surface finish Ra (average roughness) is measured in micrometers. Grinding achieves Ra 0.1–1.6; turning 0.8–6.3; casting 6.3–25. Tolerance and Ra requirements must match process capabilities.",
        "Value stream mapping visualizes all steps in a production process from raw material to customer delivery, identifying value-added and non-value-added time.",
    ],

    # ── CALENDAR/TIME ─────────────────────────────────────────────────────────
    "calendar_time": [
        "The Gregorian calendar is the internationally recognized civil calendar. A year has 365 days, with a leap year of 366 every 4 years, except centuries not divisible by 400.",
        "A solar day (mean solar day) is 24 hours — the average time for Earth to complete one rotation relative to the Sun. The sidereal day (relative to stars) is ~23h 56m.",
        "The Julian calendar, introduced by Julius Caesar in 46 BC, used a 365.25-day year. Its drift from the solar year led Pope Gregory XIII to reform it in 1582.",
        "Unix time counts seconds elapsed since 1 January 1970 00:00:00 UTC (the Unix epoch). It is a continuous count, independent of time zones.",
        "ISO 8601 is the international standard for dates and times: YYYY-MM-DDTHH:MM:SSZ. The Z suffix means UTC (Zulu time). Used in APIs, databases, and data interchange.",
        "Time zones offset from UTC. UTC+5:30 is India Standard Time; UTC-5 is Eastern Standard Time. Time zone databases (IANA tz database) include historical rule changes.",
        "The Hebrew calendar is a lunisolar calendar. Months are lunar (~29.5 days); a leap month (Adar II) is added 7 times in 19 years to keep festivals aligned with seasons.",
        "The Jewish Shabbat begins at sunset Friday and ends at nightfall Saturday — following Genesis 1's 'evening and morning' sequence. Biblical days begin at sunset.",
        "The Anno Domini (AD/CE) dating system was devised by Dionysius Exiguus in 525 AD to calculate Easter. Modern scholarship suggests Jesus was born ~4–6 BC.",
        "The Metonic cycle: 19 solar years ≈ 235 lunar months. Used to synchronize lunar and solar calendars. Governs the Jewish calendar's leap-month insertion schedule.",
        "Daylight saving time shifts clocks forward 1 hour in summer to extend evening daylight. About 40% of countries observe it. It was originally proposed by Benjamin Franklin.",
        "A Julian date (JD) is the continuous count of days from noon on January 1, 4713 BC (Julian calendar). Used in astronomy to compute intervals without calendar ambiguity.",
        "The proleptic Gregorian calendar extends Gregorian rules backward before 1582. Astronomers use it for calculations; historians use the Julian calendar for historical dates.",
        "Bible chronology: the Hebrew term 'yom' (day) can mean a 24-hour day, a year, an era, or an indefinite period depending on context and literary genre.",
        "A second is defined as 9,192,631,770 oscillations of cesium-133 atoms. Atomic clocks keep time to within 1 second in 300 million years. UTC incorporates leap seconds.",
        "The Sabbatical year (shmita) occurs every 7 years in the Jewish calendar — the land rests, debts are released (Leviticus 25). The Jubilee year follows 7 sabbatical cycles.",
        "Clock arithmetic (modular arithmetic mod 12 or 24) governs time computation. Adding 5 hours to 9 PM gives 2 AM — hours wrap around at midnight.",
        "The French Republican Calendar (1793–1806) attempted to rationalize time: 10-day weeks, 30-day months in 3 'decades,' and 5-6 extra days. It was abolished by Napoleon.",
        "The Muslim Hijri calendar is purely lunar (354 days/year). Ramadan falls ~11 days earlier each Gregorian year, completing a full cycle every 33 years.",
        "The astronomical year numbering system includes a year 0 (= 1 BC), making it easier to compute BC/AD intervals. Astronomers use it; historians generally do not.",
        "Precession of the equinoxes: Earth's rotational axis traces a cone over 25,772 years, shifting the equinoxes backward through the zodiac — the astronomical basis of the 'Great Year.'",
    ],

    # ── METEOROLOGY ───────────────────────────────────────────────────────────
    "meteorology": [
        "Weather is the short-term state of the atmosphere. Climate is the long-term average and variability of weather over decades or longer.",
        "The Coriolis effect deflects moving air to the right in the Northern Hemisphere and left in the Southern Hemisphere, causing cyclones to rotate counterclockwise in the north.",
        "Atmospheric pressure decreases with altitude roughly exponentially. Sea-level pressure averages 1013.25 hPa. Falling pressure indicates approaching storms.",
        "Air mass types: continental or maritime (moisture), polar or tropical (temperature). Fronts are boundaries between air masses of contrasting properties.",
        "A cold front brings cold air displacing warm air, causing rapid lifting, cumulonimbus clouds, and heavy rain followed by clearing. A warm front causes stratiform, prolonged rain.",
        "The Saffir-Simpson scale rates Atlantic hurricanes 1–5 by sustained wind speed. Category 3+ (sustained winds ≥ 178 km/h) are major hurricanes causing catastrophic damage.",
        "The Enhanced Fujita (EF) scale rates tornadoes 0–5 by estimated wind speed inferred from damage. EF5 tornadoes (wind ≥ 322 km/h) are capable of leveling well-built structures.",
        "CAPE (Convective Available Potential Energy) measures atmospheric instability. High CAPE (>2500 J/kg) supports severe thunderstorms; CAPE alone is insufficient without wind shear.",
        "Relative humidity (RH) is the ratio of actual vapor pressure to saturation vapor pressure at the same temperature. 100% RH = saturation = dew point reached.",
        "Radiative cooling at night causes surface temperatures to fall. Frost forms when surface temperatures drop below 0°C while air temperature may still be above freezing.",
        "El Niño: anomalously warm equatorial Pacific sea surface temperatures that disrupt global weather patterns every 2–7 years, causing droughts, floods, and temperature shifts worldwide.",
        "The jet stream is a narrow band of fast-moving air at ~10 km altitude. It steers mid-latitude storms and separates polar and tropical air masses.",
        "Dew point temperature is the temperature to which air must cool for saturation to occur. A dew point above 21°C (70°F) feels very humid; below 10°C (50°F) is comfortable.",
        "Doppler radar measures precipitation intensity (reflectivity) and radial velocity of hydrometeors, enabling detection of rotation in supercell thunderstorms.",
        "The ITCZ (Intertropical Convergence Zone) is a band of low pressure near the equator where trade winds from the north and south converge, causing persistent rainfall.",
        "Albedo is the fraction of solar radiation reflected by a surface. Fresh snow: ~0.85; ocean: ~0.06; global average: ~0.30. High-albedo surfaces cause local cooling.",
        "Cloud types: cirrus (high, icy), stratus (low, layered), cumulus (vertical, heaped), nimbostratus (rain-bearing layered), cumulonimbus (tall, thunderstorm). Luke Howard's 1803 classification.",
        "Orographic precipitation occurs when moist air is forced to rise over a mountain range. The windward side receives heavy rainfall; the leeward side is in a rain shadow.",
        "The 1970 Bhola cyclone (Bangladesh) killed an estimated 500,000 people — the deadliest tropical cyclone on record — underscoring the life-safety importance of accurate forecasting.",
        "Numerical weather prediction (NWP) uses atmospheric physics equations solved on global grids. The European Centre for Medium-Range Weather Forecasts (ECMWF) runs the most accurate global model.",
    ],

    # ── GOVERNANCE ────────────────────────────────────────────────────────────
    "governance": [
        "Separation of powers divides government authority among legislative (law-making), executive (law-enforcing), and judicial (law-interpreting) branches to prevent tyranny.",
        "The rule of law requires that all persons and institutions, including the government, are accountable to publicly promulgated, equally enforced laws.",
        "Federalism divides sovereignty between a central government and regional governments. The US Constitution reserves powers not delegated to federal government to states or people (10th Amendment).",
        "Representative democracy: citizens elect representatives to govern on their behalf. Direct democracy: citizens vote on laws and policies directly. Most modern democracies blend both.",
        "The social contract theory (Hobbes, Locke, Rousseau) holds that governments derive legitimacy from the consent of the governed, who surrender some freedoms for social protection.",
        "Constitutional supremacy: a written constitution is the highest law. Ordinary legislation cannot override it; judicial review enforces this. Marbury v. Madison (1803) established US judicial review.",
        "Due process: legal proceedings must follow established rules to protect individual rights. Procedural due process protects the process; substantive due process protects fundamental rights.",
        "The principal-agent problem arises when an agent acts on behalf of a principal but has different interests. In governance: voters are principals, legislators are agents.",
        "Checks and balances prevent any single branch from accumulating excessive power. The US President can veto legislation; Congress can override vetoes; courts can strike down laws.",
        "The concept of subsidiarity: decisions should be made at the most local competent level. Higher authorities should intervene only when lower levels cannot adequately act.",
        "Regulatory capture occurs when a regulatory agency advances the interests of the industry it is supposed to regulate rather than the public interest.",
        "Accountability mechanisms: elections, freedom of information laws, independent auditing, ombudsmen, whistleblower protections, and independent judiciary.",
        "Public choice theory applies economic analysis to political processes. Concentrated interests (industries) often outcompete diffuse interests (consumers) in lobbying.",
        "The iron triangle describes the stable relationship between a congressional committee, a federal agency, and an interest group that perpetuates specific policies.",
        "Administrative law governs the procedures by which government agencies make rules, adjudicate disputes, and exercise delegated power.",
        "Magna Carta (1215) established that even the king is subject to law, requiring due process before imprisonment and providing protections against arbitrary royal power.",
        "The Westminster system uses a parliamentary government where the executive (Prime Minister and Cabinet) derives authority from and is accountable to the legislature.",
        "Corruption undermines governance by diverting public resources to private benefit. Transparency International's Corruption Perceptions Index measures perceived corruption annually.",
        "Free press is a cornerstone of democratic governance: investigative journalism exposes corruption, informs citizens, and holds public officials accountable.",
        "The United Nations was established in 1945 to promote international peace, security, and cooperation. The Security Council has five permanent members with veto power.",
    ],

    # ── THEOLOGY / DOCTRINE ───────────────────────────────────────────────────
    "theology_doctrine": [
        "The Trinity: God is one Being in three co-equal, co-eternal Persons — Father, Son, and Holy Spirit. Each Person is fully God; there are not three gods but one God (Deuteronomy 6:4; Matthew 28:19).",
        "The Incarnation: the eternal Son of God took on full human nature, becoming truly God and truly man in one Person (Hypostatic Union). John 1:14: 'The Word became flesh.'",
        "Justification by faith alone (sola fide): sinners are declared righteous before God not by works but by faith in Christ's atoning work (Romans 3:28; Galatians 2:16).",
        "The atonement: Christ's death on the cross satisfied divine justice and reconciled sinners to God. Substitutionary atonement: Christ bore the punishment our sins deserved (Isaiah 53:5–6).",
        "Scripture alone (sola scriptura): the Bible is the supreme authority for Christian faith and practice, sufficient and final over tradition and reason.",
        "The resurrection of Jesus Christ is the foundation of Christian faith (1 Corinthians 15:14–17). A bodily, historical resurrection confirmed by eyewitnesses, not myth.",
        "Total depravity (T in TULIP): every aspect of fallen human nature is corrupted by sin. It does not mean humans are as bad as possible, but that no part is unaffected.",
        "Common grace: God bestows gifts (intellect, conscience, beauty, civil order) on all humanity regardless of salvation status, restraining evil and enabling civilization.",
        "The Lord's Supper (Communion/Eucharist) is a memorial of Christ's sacrifice. Views differ: transubstantiation (Catholic), real presence (Lutheran), memorial (Zwinglian), spiritual presence (Calvinist).",
        "Baptism is administered by water in the name of the Father, Son, and Holy Spirit. Paedobaptists baptize infants as covenant members; credobaptists baptize only professing believers.",
        "The Great Commission (Matthew 28:18–20): Christ commands his followers to make disciples of all nations, baptizing and teaching — the charter for Christian mission.",
        "Eschatology: the study of last things. Views on the millennium (Revelation 20) divide into premillennialism, postmillennialism, and amillennialism.",
        "The covenants of Scripture: creation covenant (works), Noahic, Abrahamic, Mosaic, Davidic, and New Covenant in Christ's blood. Progressive revelation unfolds God's redemptive plan.",
        "The canon of Scripture: the 66 books of the Old and New Testaments recognized by the Church as divinely inspired. Determined by apostolic origin, doctrinal consistency, and widespread reception.",
        "God's sovereignty and human responsibility are both affirmed in Scripture (Proverbs 19:21; Acts 2:23). Reformed theology holds both without resolving the tension philosophically.",
        "The Apostles' Creed (c. 2nd century) is the most universal Christian confession: belief in the Father Almighty, Jesus Christ His only Son, the Holy Spirit, the Church, resurrection, eternal life.",
        "Sanctification is the ongoing process of becoming more conformed to Christ's image by the Holy Spirit's work. Distinct from justification (declared righteous) which is instantaneous.",
        "Apologetics defends the reasonableness and truth of the Christian faith (1 Peter 3:15). Classical, evidential, and presuppositional approaches differ in starting assumptions.",
        "The Nicene Creed (325 AD, revised 381 AD) defines orthodox Trinitarian theology, affirming that the Son is 'of the same substance' (homoousios) as the Father, against Arianism.",
        "Providence: God governs all events in history and creation according to his purposes. Providence does not eliminate secondary causes but works through them.",
    ],

    # ── SCRIPTURE ANCHORS ─────────────────────────────────────────────────────
    "scripture": [
        "John 1:1 — 'In the beginning was the Word, and the Word was with God, and the Word was God.' Establishes the eternal, divine pre-existence of the Son before creation.",
        "Genesis 1:1 — 'In the beginning God created the heavens and the earth.' The Bible's first sentence affirms creation ex nihilo, God's priority, and his sovereign ownership of all things.",
        "Proverbs 3:5–6 — 'Trust in the LORD with all your heart and do not lean on your own understanding; in all your ways acknowledge him, and he will make your paths straight.'",
        "Romans 8:28 — 'All things work together for good for those who love God, who are called according to his purpose.' The anchor text for trusting God through suffering.",
        "Matthew 22:37–40 — The great commandment: love God with all heart, soul, and mind; love your neighbor as yourself. 'On these two commandments depend all the Law and the Prophets.'",
        "Psalm 119:105 — 'Your word is a lamp to my feet and a light to my path.' Scripture as the guide for daily living, not just systematic doctrine.",
        "Isaiah 40:31 — 'Those who wait for the LORD will gain new strength; they will mount up with wings like eagles, they will run and not get tired, they will walk and not become weary.'",
        "Micah 6:8 — 'He has told you, O man, what is good; and what does the LORD require of you but to do justice, to love kindness, and to walk humbly with your God?'",
        "James 2:17 — 'Faith, if it has no works, is dead being by itself.' Faith and works are distinguished (works don't justify) but not separated (real faith produces works).",
        "1 Corinthians 13:4–7 — Love is patient, love is kind... it does not seek its own, it is not provoked... bears all things, believes all things, hopes all things, endures all things.",
        "Philippians 4:6–7 — 'Be anxious for nothing, but in everything by prayer and supplication with thanksgiving let your requests be made known to God.' The antidote to anxiety.",
        "2 Timothy 3:16–17 — 'All Scripture is God-breathed and profitable for teaching, for reproof, for correction, for training in righteousness.' The primary text for biblical inspiration.",
        "Matthew 6:33 — 'Seek first his kingdom and his righteousness, and all these things will be added to you.' Priority ordering of Kingdom before provision.",
        "Romans 3:23–24 — 'All have sinned and fall short of the glory of God, being justified as a gift by his grace through the redemption which is in Christ Jesus.'",
        "Hebrews 11:1 — 'Faith is the assurance of things hoped for, the conviction of things not seen.' Faith is not credulity; it rests on divine promise and evidence.",
        "Revelation 21:4 — 'He will wipe away every tear from their eyes; and there will no longer be any death; there will no longer be any mourning, or crying, or pain.' Final restoration.",
        "Acts 2:38 — Peter at Pentecost: 'Repent, and each of you be baptized in the name of Jesus Christ for the forgiveness of your sins; and you will receive the gift of the Holy Spirit.'",
        "Mark 4:8 — 'Other seeds fell on the good soil and as they grew up and increased, they yielded a crop and produced thirty, sixty, and a hundredfold.' The parable of the sower.",
        "Deuteronomy 6:4–5 (Shema) — 'Hear, O Israel! The LORD is our God, the LORD is one! You shall love the LORD your God with all your heart and with all your soul and with all your might.'",
        "Colossians 1:17 — 'He is before all things, and in Him all things hold together.' The cosmic Christ sustains the coherence of creation — the theological basis for a unified domain grid.",
    ],

    # ── FORMAL LOGIC ──────────────────────────────────────────────────────────
    "formal_logic": [
        "A valid argument is one where, if the premises are true, the conclusion must be true. A sound argument is valid with all true premises. Valid ≠ true; sound = valid + true premises.",
        "Modus ponens: if P then Q; P is true; therefore Q. The fundamental deductive inference form. Modus tollens: if P then Q; Q is false; therefore P is false.",
        "A fallacy is an error in reasoning. Formal fallacies violate logical form (affirming the consequent, denying the antecedent). Informal fallacies involve content (ad hominem, straw man, false dichotomy).",
        "The law of non-contradiction: a proposition cannot be both true and false at the same time and in the same sense. ¬(P ∧ ¬P). Foundation of classical logic.",
        "The law of excluded middle: every proposition is either true or false. P ∨ ¬P. Classical logic; rejected by intuitionistic logicians who require constructive proof.",
        "De Morgan's laws: ¬(P ∧ Q) ≡ ¬P ∨ ¬Q; ¬(P ∨ Q) ≡ ¬P ∧ ¬Q. Allow distribution of negation over conjunction and disjunction.",
        "A syllogism has two premises and a conclusion. All men are mortal; Socrates is a man; therefore Socrates is mortal. The canonical syllogism — Barbara in Aristotelian logic.",
        "Reductio ad absurdum (proof by contradiction): assume the negation of the conclusion; derive a contradiction; therefore the original conclusion must be true.",
        "Propositional logic studies connectives (and, or, not, if-then, iff) between propositions. First-order logic adds quantifiers (∀ all, ∃ there exists) and predicates.",
        "The conditional P → Q is false only when P is true and Q is false. Implication is not causation; it is a truth-functional relationship about when the conditional fails.",
        "Logical equivalence: P ≡ Q means P and Q always have the same truth value. P → Q is logically equivalent to ¬Q → ¬P (contrapositive) but not to Q → P (converse).",
        "Gödel's incompleteness theorems: any consistent formal system strong enough to express arithmetic contains true statements that cannot be proved within the system.",
        "A biconditional P ↔ Q is true when P and Q have the same truth value. Read as 'P if and only if Q.' This is the form of definitions and equivalences.",
        "The principle of charity in interpretation: when multiple interpretations are possible, take the strongest, most rational version of an opponent's argument before responding.",
        "A circular argument (petitio principii / begging the question) uses the conclusion as a hidden premise. It may be valid but is not persuasive to anyone who doubts the conclusion.",
        "The sorites paradox: one grain of sand does not make a heap; adding one grain to a non-heap does not make a heap; by induction, no collection is a heap. Vague predicates resist classical logic.",
        "Abductive reasoning infers the best explanation: 'the grass is wet; if it had rained, the grass would be wet; probably it rained.' Not deductively certain but guides scientific inference.",
        "A necessary condition for P is something that must be true for P to be true. A sufficient condition guarantees P. Being a mammal is necessary but not sufficient for being human.",
        "The quantifier structure of 'all swans are white': ∀x (Swan(x) → White(x)). A single non-white swan falsifies it. Universal claims are falsifiable by one counterexample.",
        "Truth tables enumerate all truth-value combinations for compound propositions, determining tautologies (always true), contradictions (always false), and contingencies (sometimes true).",
    ],

    # ── ECONOMICS ─────────────────────────────────────────────────────────────
    "economics": [
        "Scarcity is the fundamental economic problem: unlimited human wants exceed the limited resources available to satisfy them, requiring choices and trade-offs.",
        "Supply and demand: price adjusts until quantity supplied equals quantity demanded (equilibrium). Rising demand raises price; rising price reduces quantity demanded.",
        "Opportunity cost is the value of the next-best alternative foregone. Every choice has an opportunity cost, even when money is not exchanged.",
        "Comparative advantage: a party should specialize in the good for which it has the lowest opportunity cost, even if another party has absolute advantage in all goods (Ricardo).",
        "GDP (Gross Domestic Product) measures the total market value of all final goods and services produced within a country in a period. C + I + G + NX = GDP.",
        "Inflation is a sustained increase in the general price level, reducing purchasing power. The Consumer Price Index (CPI) tracks a basket of goods. Central banks target ~2% inflation.",
        "The Phillips curve described an empirical inverse relationship between unemployment and inflation. Stagflation in the 1970s demonstrated that this trade-off is not stable long-run.",
        "Monetary policy: central banks adjust interest rates and money supply to achieve price stability and maximum employment. Raising rates reduces borrowing and cools inflation.",
        "Fiscal policy: governments use taxation and spending to influence aggregate demand. Deficit spending stimulates; austerity contracts. The multiplier effect amplifies fiscal impacts.",
        "Market failure occurs when free markets produce inefficient outcomes: externalities, public goods, information asymmetry, and natural monopolies all require potential intervention.",
        "A positive externality (education, vaccination) produces benefits beyond the transaction, leading to under-supply. A negative externality (pollution) leads to over-supply.",
        "Game theory analyzes strategic interactions where outcomes depend on all participants' choices. The prisoner's dilemma shows why rational self-interest can produce suboptimal group outcomes.",
        "Price elasticity of demand: % change in quantity / % change in price. Elastic demand (|E| > 1): price rises reduce revenue. Inelastic (|E| < 1): price rises increase revenue.",
        "The production possibilities frontier shows the maximum combinations of two goods producible with given resources. Points inside are inefficient; outside are currently unattainable.",
        "The invisible hand (Adam Smith, 1776): individuals pursuing self-interest in competitive markets unintentionally promote social welfare, as if guided by an invisible hand.",
        "Marginal analysis: rational decision-making compares marginal benefit and marginal cost. Continue an activity as long as MB ≥ MC; stop when MC > MB.",
        "The Lorenz curve and Gini coefficient measure income inequality. A Gini of 0 = perfect equality; 1 = perfect inequality. The US Gini is approximately 0.41.",
        "Moral hazard: when one party is protected from risk, it may behave differently (more recklessly). Insurance markets, banking bailouts, and principal-agent relationships create moral hazard.",
        "The quantity theory of money: MV = PQ, where M is money supply, V is velocity, P is price level, and Q is real output. Doubling M with constant V and Q doubles P.",
        "Behavioral economics shows that humans deviate from rational-actor models through anchoring, loss aversion, present bias, and social preferences. Thaler and Sunstein: 'nudge.'",
    ],

    # ── MEDICINE ──────────────────────────────────────────────────────────────
    "medicine": [
        "Differential diagnosis is a systematic process of identifying a condition by ruling out competing diagnoses based on symptoms, physical exam, and test results.",
        "Evidence-based medicine (EBM) integrates the best available research evidence, clinical expertise, and patient values/preferences in medical decision-making.",
        "The randomized controlled trial (RCT) is the gold standard for evaluating treatment efficacy. Random assignment to treatment and control groups minimizes confounding.",
        "Sensitivity is the proportion of true positives correctly identified (TP / (TP + FN)). Specificity is the proportion of true negatives correctly identified (TN / (TN + FP)).",
        "Primary prevention stops disease before it begins (vaccination, smoking cessation). Secondary prevention detects disease early (screening). Tertiary prevention reduces disability from established disease.",
        "The dose-response relationship: the biological effect of a substance depends on dose. Paracelsus: 'the dose makes the poison.' All substances are toxic at sufficiently high doses.",
        "Informed consent requires that patients receive complete information about risks, benefits, and alternatives before voluntarily agreeing to treatment. A core principle of medical ethics.",
        "First, do no harm (primum non nocere) is a foundational principle. Every intervention carries risk; the potential benefit must outweigh it. Hippocratic tradition.",
        "Antibiotic resistance: misuse and overuse of antibiotics kills susceptible bacteria while allowing resistant strains to survive and multiply. A global public health emergency.",
        "The four humors (blood, phlegm, yellow bile, black bile) were the dominant medical paradigm for 2,000 years. Germ theory, developed by Pasteur and Koch in the 19th century, replaced it.",
        "Sepsis is a life-threatening organ dysfunction caused by a dysregulated host response to infection. Early recognition and hour-1 bundle (antibiotics, IV fluids, blood cultures) reduces mortality.",
        "The body mass index (BMI) = weight(kg) / height²(m²). Underweight < 18.5; normal 18.5–24.9; overweight 25–29.9; obese ≥ 30. BMI does not measure body fat distribution.",
        "Vaccine immunization trains the immune system to recognize pathogens without causing disease, producing memory cells for rapid response to future exposure.",
        "Atherosclerosis: buildup of plaques in arterial walls, narrowing vessels and causing cardiovascular disease. Risk factors: hypertension, dyslipidemia, smoking, diabetes, family history.",
        "Mental health conditions (depression, anxiety, schizophrenia) have biological, psychological, and social components. DSM-5 and ICD-11 provide diagnostic criteria.",
        "Pharmacokinetics: absorption, distribution, metabolism, and excretion of drugs (ADME). Pharmacodynamics: how drugs produce their biological effects at the molecular level.",
        "Palliative care focuses on improving quality of life for patients with serious illness by relieving pain and other symptoms, not necessarily extending life.",
        "The placebo effect: inert treatments produce real physiological responses due to patient expectation. Placebos are ethically complex; nocebo effects (harm from negative expectation) are equally real.",
        "Telemedicine delivers healthcare remotely via telecommunications. Expanded dramatically during COVID-19; effective for follow-up, mental health, and chronic disease management.",
        "The opioid crisis: overprescription of opioids led to widespread addiction and overdose deaths. 80,000+ Americans died of drug overdose in 2021, mostly from opioids and fentanyl.",
    ],

    # ── STATISTICS ────────────────────────────────────────────────────────────
    "statistics": [
        "The p-value is the probability of observing results at least as extreme as those obtained, assuming the null hypothesis is true. p < 0.05 is a conventional threshold, not absolute proof.",
        "A Type I error (false positive) rejects a true null hypothesis. A Type II error (false negative) fails to reject a false null hypothesis. α is the Type I error rate; β the Type II rate.",
        "The central limit theorem: the sampling distribution of the sample mean approaches a normal distribution as sample size increases, regardless of the population distribution.",
        "Confidence intervals: a 95% CI means that if we repeated the study many times, 95% of the calculated intervals would contain the true population parameter.",
        "Bayesian inference updates prior beliefs with observed data via Bayes' theorem: P(H|E) = P(E|H)P(H) / P(E). The posterior probability replaces the prior after evidence.",
        "Correlation measures the strength and direction of a linear relationship between two variables, ranging from -1 to +1. Correlation ≠ causation.",
        "Regression analysis estimates the relationship between a dependent variable and one or more independent variables. Linear regression: y = β₀ + β₁x + ε.",
        "The null hypothesis significance testing (NHST) framework tests whether observed data are inconsistent with a specific null hypothesis. Criticized for binary pass/fail thinking.",
        "Multiple comparisons: conducting many statistical tests on the same data inflates Type I error. Bonferroni correction adjusts α by dividing by the number of tests.",
        "Effect size quantifies the magnitude of a difference or relationship, independent of sample size. Cohen's d, Pearson's r, and odds ratios are common effect size measures.",
        "Power (1 - β) is the probability that a test correctly rejects a false null hypothesis. Power increases with larger sample size, larger effect size, and higher α.",
        "The standard deviation σ measures the average spread of data around the mean. The standard error SE = σ/√n is the standard deviation of the sampling distribution.",
        "Survival analysis models time-to-event data (time to death, failure, relapse). The Kaplan-Meier curve and Cox proportional hazards model are standard methods.",
        "Random sampling: every member of the population has an equal chance of selection, enabling unbiased generalization. Non-random samples may be biased in unknown ways.",
        "A/B testing: randomly assign users to two conditions (A = control, B = treatment); compare outcomes. Standard in tech product development and clinical trials.",
        "Overfitting: a model that fits training data too closely performs poorly on new data. Regularization, cross-validation, and holdout sets guard against overfitting.",
        "The chi-square test assesses whether observed counts in categories differ from expected counts. Tests independence between categorical variables in contingency tables.",
        "Simpson's paradox: a trend appearing in separate groups may reverse when groups are combined due to confounding. Requires careful stratified analysis.",
        "Bootstrapping: resample the observed data with replacement many times to estimate the sampling distribution of a statistic without parametric assumptions.",
        "The difference between statistical significance and practical significance: a very large study may find tiny effects that are statistically significant but meaningless in practice.",
    ],

}


# ── helpers ───────────────────────────────────────────────────────────────────

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def load_state() -> set:
    if STATE_FILE.exists():
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(d.get("posted", []))
    return set()

def save_state(posted: set) -> None:
    STATE_FILE.write_text(
        json.dumps({"posted": sorted(posted)}, indent=2),
        encoding="utf-8"
    )

def all_seeds() -> Iterator[tuple[str, str]]:
    """Yield (domain, text) pairs in domain order, thinnest domains first."""
    # Sort by domain name to be deterministic; caller can filter
    for domain in sorted(SEEDS.keys()):
        for text in SEEDS[domain]:
            yield domain, text


def post_seed(session: "requests.Session", text: str, domain: str, dry_run: bool) -> bool:
    payload = {
        "text": text,
        "source": f"seed:{domain}",
        "tags": [domain, "seed", "curated"]
    }
    if dry_run:
        print(f"  [DRY] {domain}: {text[:60]}…")
        return True
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=30)
        if r.status_code == 200:
            d = r.json()
            verdict = d.get("verdict", "?")
            gate = d.get("gate", "?")
            print(f"  ✓ [{verdict:>10}] [{gate:>8}] {domain}: {text[:55]}…")
            return True
        else:
            print(f"  ✗ HTTP {r.status_code}: {r.text[:80]}")
            return False
    except Exception as e:
        print(f"  ✗ {e}")
        return False


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed domain knowledge packets")
    parser.add_argument("--domain", help="Seed a specific domain only")
    parser.add_argument("--dry-run", action="store_true", help="Print seeds, don't POST")
    parser.add_argument("--delay", type=float, default=1.2, help="Seconds between POSTs (default 1.2)")
    parser.add_argument("--reset", action="store_true", help="Re-seed even already-posted items")
    args = parser.parse_args()

    posted = set() if args.reset else load_state()

    # Verify server is reachable
    if not args.dry_run:
        try:
            import requests as req
            r = req.get(f"{API_BASE}/health", timeout=5)
            r.raise_for_status()
            print(f"✓ Server at {API_BASE} is up")
        except Exception as e:
            sys.exit(f"✗ Cannot reach {API_BASE}: {e}\n  Start the server first.")

    import requests as req
    session = req.Session()
    session.headers.update({"Content-Type": "application/json"})

    total = 0
    skipped = 0
    failed = 0

    domains_to_seed = (
        {args.domain: SEEDS[args.domain]} if args.domain and args.domain in SEEDS
        else SEEDS
    )

    for domain, texts in domains_to_seed.items():
        print(f"\n── {domain.upper()} ({len(texts)} seeds) ──────────────────")
        for text in texts:
            h = hash_text(text)
            if h in posted:
                skipped += 1
                continue

            ok = post_seed(session, text, domain, args.dry_run)
            if ok:
                total += 1
                posted.add(h)
                if not args.dry_run:
                    save_state(posted)
                    time.sleep(args.delay)
            else:
                failed += 1
                time.sleep(args.delay * 2)  # back off on error

    print(f"\n{'─'*60}")
    print(f"  Posted : {total}")
    print(f"  Skipped: {skipped} (already done)")
    print(f"  Failed : {failed}")
    print(f"  State  : {STATE_FILE}")
    print(f"{'─'*60}")


if __name__ == "__main__":
    main()
