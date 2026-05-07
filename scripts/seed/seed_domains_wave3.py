"""
seed_domains_wave3.py — Third wave: patch thin and mis-named domains
────────────────────────────────────────────────────────────────────
Targets domains that are critically thin in the packet store or
whose Wave-1 seeds used wrong domain keys:
  computer_science, physics_conservation, physics_dimensional,
  statistics_pvalue, statistics_multiple_comparisons,
  statistics_confidence_interval, scripture_anchors,
  governance_decision_packet, theology_doctrine, apologetics,
  eschatology, linguistics_advanced, mathematics_advanced

Usage: python scripts/seed/seed_domains_wave3.py [--delay N] [--dry-run] [--domain D] [--reset]
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
STATE_FILE = Path(__file__).parent / "seed_state_w3.json"

SEEDS: dict[str, list[str]] = {

    # ── COMPUTER SCIENCE (algorithms, data structures, OS, distributed) ──────
    "computer_science": [
        "Big-O notation describes asymptotic upper bounds on algorithm runtime: O(1) constant, O(log n) logarithmic, O(n) linear, O(n log n) linearithmic, O(n²) quadratic, O(2ⁿ) exponential.",
        "Binary search runs in O(log n) on a sorted array by repeatedly halving the search space. Precondition: array must be sorted. Loop invariant: target ∈ arr[lo..hi].",
        "Merge sort is a divide-and-conquer algorithm with guaranteed O(n log n) worst case. It divides arrays recursively, sorts halves, and merges. Stable sort; requires O(n) extra space.",
        "Quicksort averages O(n log n) but worst-case O(n²) on already-sorted input. Randomized pivot selection reduces worst-case probability. In-place; not stable.",
        "Hash tables provide O(1) average insert/lookup/delete using a hash function to map keys to buckets. Collision resolution: chaining (linked lists) or open addressing (linear probing).",
        "A linked list is a sequence of nodes each storing data and a pointer to the next node. O(n) random access, O(1) insertion at head. Doubly-linked lists allow O(1) removal.",
        "Binary search trees maintain sorted order: left subtree < root < right subtree. Average O(log n) search; worst O(n) for degenerate (sorted insertion) trees.",
        "AVL trees and red-black trees are self-balancing BSTs maintaining O(log n) height. Red-black trees guarantee at most 2× height difference between branches.",
        "Graph representations: adjacency matrix O(V²) space, adjacency list O(V+E) space. Matrix favors dense graphs; list favors sparse. Algorithms choose by graph density.",
        "Breadth-first search (BFS) explores neighbors level by level using a queue. Finds shortest path in unweighted graphs. Time O(V+E), space O(V).",
        "Depth-first search (DFS) explores as deep as possible before backtracking using a stack (or recursion). Used for cycle detection, topological sort, connected components.",
        "Dijkstra's algorithm finds shortest paths in weighted graphs with non-negative edges. Uses a min-heap priority queue. Time O((V+E) log V) with binary heap.",
        "Dynamic programming solves problems by breaking them into overlapping subproblems and storing results (memoization/tabulation). Key property: optimal substructure.",
        "The knapsack problem: given items with weights and values, maximize value within weight limit. 0/1 knapsack solved in O(nW) via DP; fractional knapsack greedily in O(n log n).",
        "Heap data structure: a complete binary tree satisfying the heap property (max-heap: parent ≥ children). Heapify O(n), insert/extract-max O(log n). Used in heapsort and priority queues.",
        "Stack (LIFO) and queue (FIFO) are fundamental ADTs. Stacks support push/pop; queues support enqueue/dequeue. Both achievable in O(1) with linked lists or circular arrays.",
        "Amortized analysis gives average cost per operation over a sequence. Dynamic array doubling: each append amortizes to O(1) even though occasional reallocation costs O(n).",
        "P vs NP: P = problems solvable in polynomial time; NP = problems verifiable in polynomial time. NP-complete problems are the hardest in NP. P=NP remains unsolved.",
        "NP-complete problems: SAT (first NP-complete, Cook-Levin theorem), 3-SAT, vertex cover, travelling salesman decision version, graph coloring (k≥3), subset sum.",
        "Greedy algorithms make locally optimal choices at each step. Work when a greedy choice property and optimal substructure hold. Examples: Huffman coding, Kruskal's MST.",
        "Bellman-Ford finds shortest paths with negative edges (no negative cycles). Time O(VE); detects negative cycles by running one extra iteration.",
        "Memory hierarchy: registers (< 1ns) → L1 cache (1-4ns) → L2 cache (4-12ns) → L3 cache (12-40ns) → RAM (60-100ns) → SSD → HDD. Locality of reference is critical.",
        "Virtual memory maps process address space to physical RAM + disk. Page tables translate virtual to physical addresses. Page faults occur when pages must be loaded from disk.",
        "Mutex (mutual exclusion) prevents simultaneous access to shared resources. Deadlock requires: mutual exclusion, hold-and-wait, no preemption, circular wait (Coffman conditions).",
        "TCP (Transmission Control Protocol): reliable, ordered, connection-oriented. Three-way handshake (SYN, SYN-ACK, ACK). Congestion control via slow start and AIMD.",
        "Database ACID properties: Atomicity (all-or-nothing), Consistency (valid state), Isolation (concurrent transactions behave serially), Durability (committed = permanent).",
        "B-trees are self-balancing search trees optimized for disk I/O. All leaves at same depth; nodes store multiple keys. Databases use B+ trees (data only at leaves) for indexes.",
        "The CAP theorem: distributed systems can guarantee only two of three: Consistency, Availability, Partition tolerance. Under network partition, choose CP or AP.",
        "MapReduce: functional programming model for distributed computation. Map phase applies function to each record; reduce phase aggregates by key. Enables petabyte-scale processing.",
        "Regular expressions describe patterns matched by finite automata. Kleene's theorem: a language is regular iff recognizable by a DFA iff describable by a regex.",
        "The halting problem: no algorithm can determine whether an arbitrary program halts. Proved by Turing (1936) via diagonalization — the first undecidable problem.",
        "Garbage collection reclaims unused memory. Strategies: reference counting (cycles need special handling), mark-and-sweep (traces live objects from roots), generational GC.",
        "REST (Representational State Transfer): stateless client-server architecture. Resources identified by URIs; manipulated via HTTP verbs (GET, POST, PUT, DELETE, PATCH).",
        "Cache coherence in multiprocessor systems: MESI protocol (Modified, Exclusive, Shared, Invalid) ensures all processors see consistent memory values.",
        "The Byzantine Generals Problem: how do distributed systems reach consensus when some nodes are faulty or malicious? Requires ≥ 3f+1 nodes to tolerate f Byzantine faults.",
        "Bloom filters: space-efficient probabilistic data structures answering set-membership queries. May return false positives but never false negatives. No deletion in basic form.",
        "The master theorem solves recurrences T(n) = aT(n/b) + f(n). Three cases depending on relationship between f(n) and n^(log_b a): gives O(n^log_b a), O(n^log_b a · log n), or O(f(n)).",
        "Operating system scheduling algorithms: First-Come-First-Served (FCFS), Shortest Job Next (SJN), Round Robin (RR) with time slice, Multilevel Queue, Completely Fair Scheduler (Linux CFS).",
        "Thread-safety: data races occur when two threads access shared data concurrently and at least one writes. Prevention: locks, atomic operations, lock-free algorithms, immutable data.",
        "Shannon's source coding theorem: data can be compressed losslessly to at most H(X) bits/symbol (entropy). Huffman coding achieves near-optimal compression for known distributions.",
    ],

    # ── PHYSICS — CONSERVATION LAWS ──────────────────────────────────────────
    "physics_conservation": [
        "Conservation of energy (First Law of Thermodynamics): total energy of an isolated system is constant. Energy transforms between forms (kinetic, potential, thermal, chemical) but is never created or destroyed.",
        "Conservation of momentum: in the absence of external forces, total linear momentum of a system is constant. p = mv; Δp = FΔt (impulse-momentum theorem).",
        "Conservation of angular momentum: L = Iω is conserved when no external torque acts. A spinning ice skater pulls arms in (decreases I) → ω increases; L stays constant.",
        "Conservation of charge: electric charge is neither created nor destroyed. In particle physics, the net charge before and after any interaction is equal.",
        "Conservation of baryon number: the total number of baryons (protons, neutrons) minus antibaryons is conserved in all known interactions. Proton stability requires B conservation.",
        "Conservation of lepton number: electron, muon, and tau lepton numbers are separately conserved in Standard Model interactions. Neutrino oscillation implies lepton flavor violation.",
        "Noether's theorem: every continuous symmetry of a physical system corresponds to a conservation law. Time translation → energy; spatial translation → momentum; rotation → angular momentum.",
        "Conservation of mass-energy (special relativity): E = mc². Mass is a form of energy. In nuclear reactions, mass defect converts to energy: ΔE = Δm · c².",
        "The work-energy theorem: net work done on an object equals its change in kinetic energy. W_net = ΔKE = ½mv₂² - ½mv₁².",
        "Elastic vs inelastic collisions: elastic conserves both momentum and kinetic energy; perfectly inelastic conserves only momentum (objects stick together). Real collisions are partially inelastic.",
        "Kirchhoff's current law (KCL): the sum of currents entering a node equals the sum leaving. Consequence of charge conservation: charge does not accumulate at nodes.",
        "Kirchhoff's voltage law (KVL): the sum of voltage drops around any closed loop is zero. Consequence of energy conservation: voltage is a state function.",
        "Continuity equation in fluid mechanics: ρ₁A₁v₁ = ρ₂A₂v₂. For incompressible flow: A₁v₁ = A₂v₂. Conservation of mass applied to flowing fluids.",
        "The Pauli exclusion principle: no two identical fermions can occupy the same quantum state. Not a conservation law per se but enforces conservation of fermion number structure.",
        "Entropy in thermodynamics: in any spontaneous process, total entropy of the universe increases (Second Law). For reversible processes, ΔS_total = 0. Energy conservation alone does not predict direction.",
        "CPT symmetry: the combined operations of charge conjugation (C), parity (P), and time reversal (T) are conserved in all known interactions. Individual C, P, CP symmetries can be violated.",
        "Wigner's classification: elementary particles are classified by mass and spin — both conserved Poincaré charges. Particles with same quantum numbers are identical.",
        "Color confinement: in QCD, color charge (strong force) is confined — free quarks never observed. Color neutrality (white) is conserved in all observable hadrons.",
        "Conservation of strangeness: in strong interactions, strangeness quantum number is conserved. Weak interactions can change strangeness by ±1 (kaon decays).",
        "The virial theorem: for a stable gravitational system, ⟨KE⟩ = -½⟨PE⟩ (time-averaged). This constrains cluster masses and explains why bound systems have negative total energy.",
    ],

    # ── PHYSICS — DIMENSIONAL ANALYSIS ───────────────────────────────────────
    "physics_dimensional": [
        "Dimensional analysis verifies physical equations: both sides must have identical dimensions. Newton's second law F=ma: [kg·m/s²] = [kg][m/s²] ✓. A dimensionally wrong equation is definitely wrong.",
        "The SI base units are seven: meter (m, length), kilogram (kg, mass), second (s, time), ampere (A, current), kelvin (K, temperature), mole (mol, amount), candela (cd, luminosity).",
        "Derived units: velocity [m/s], acceleration [m/s²], force [kg·m/s²] = [N], energy [kg·m²/s²] = [J], power [J/s] = [W], pressure [N/m²] = [Pa].",
        "The Buckingham Pi theorem: if a physical problem has n variables with k independent dimensions, it can be expressed in terms of (n-k) dimensionless groups (Pi groups).",
        "Dimensionless numbers in fluid mechanics: Reynolds number Re = ρvL/μ (inertial/viscous forces); Mach number M = v/c_sound; Froude number Fr = v/√(gL) (inertial/gravity).",
        "The Reynolds number predicts flow regime: Re < ~2300 laminar flow (viscous dominates); Re > ~4000 turbulent flow (inertial dominates). Transition region in between.",
        "Natural units simplify physics by setting fundamental constants to 1: Planck units set G = ℏ = c = k_B = 1. Planck length ~1.6×10⁻³⁵ m, Planck time ~5.4×10⁻⁴⁴ s.",
        "Order-of-magnitude estimation (Fermi estimation): using dimensional analysis and physical intuition to estimate quantities to within a factor of 10. Essential for checking calculations.",
        "The fine-structure constant α = e²/(4πε₀ℏc) ≈ 1/137 is a dimensionless measure of electromagnetic coupling strength. Its value determines atomic structure and chemistry.",
        "Dimensional homogeneity in empirical formulas: any physical formula must be dimensionally consistent. Conversion factors (unit conversions) preserve dimensional homogeneity.",
        "Scaling laws in biology: metabolic rate scales as M^(3/4) (Kleiber's law); heart rate as M^(-1/4). These follow from dimensional analysis plus fractal vascular networks.",
        "Power law scaling in physics: period of a pendulum T = 2π√(L/g). Dimensional analysis: [s] from [m] and [m/s²] gives T ∝ √(L/g). The exact coefficient requires solving the ODE.",
        "The gravitational constant G has units [m³/(kg·s²)]. Dimensional analysis of G, c, ℏ gives Planck mass M_P = √(ℏc/G) ≈ 2.18×10⁻⁸ kg — where quantum gravity matters.",
        "Electrical units: [V] = [J/C], [Ω] = [V/A] = [kg·m²/(A²·s³)], [F] = [C/V] = [A²·s⁴/(kg·m²)]. Dimensional analysis confirms Ohm's law V=IR.",
        "Geometric scaling: volume scales as L³, area as L², radius as L. A sphere of radius 2r has 8× the volume and 4× the surface area of radius r. Biology: cell surface-to-volume limits size.",
        "The Navier-Stokes equations in dimensionless form reveal that geometrically similar flows at the same Reynolds number are dynamically identical — the basis for wind tunnel testing.",
        "Stokes drag on a sphere: F = 6πμrv. Dimensional check: [N] = [kg/(m·s)][m][m/s] = [kg·m/s²] ✓. Terminal velocity: mg = 6πμrv_t → v_t = mg/(6πμr).",
        "Fourier's law of heat conduction: q = -k(dT/dx). Units: [W/m²] = [W/(m·K)] · [K/m] ✓. Thermal diffusivity α = k/(ρc_p) has units [m²/s] — same as kinematic viscosity.",
        "Planck's radiation law: dimensional analysis of blackbody radiation requires ℏ, c, k_B, and T. The characteristic photon energy k_BT gives peak frequency via Wien's law.",
        "Pi groups in structural engineering: beam deflection δ/L depends on (F·L²)/(E·I) where E is Young's modulus and I is second moment of area. Both sides are dimensionless.",
    ],

    # ── STATISTICS — P-VALUES ─────────────────────────────────────────────────
    "statistics_pvalue": [
        "A p-value is the probability of obtaining results at least as extreme as observed, assuming the null hypothesis is true. It does NOT equal the probability that H₀ is true.",
        "The conventional threshold α = 0.05 was introduced by Ronald Fisher as a convenient cutoff, not a fundamental truth. Many journals now require pre-registration and report exact p-values.",
        "A p-value < α means the data are surprising under H₀, not that H₁ is true. With large samples, trivially small effects yield tiny p-values (statistical vs practical significance).",
        "Type I error (false positive): rejecting H₀ when it is true. Probability = α. Type II error (false negative): failing to reject H₀ when it is false. Probability = β = 1 - power.",
        "Statistical power = 1 - β = P(reject H₀ | H₁ is true). Power increases with sample size, effect size, and α. Pre-study power analysis is required to avoid underpowered studies.",
        "The null hypothesis significance testing (NHST) framework: specify H₀, choose α, compute test statistic, find p-value, make binary decision. Criticized for encouraging dichotomous thinking.",
        "One-tailed vs two-tailed tests: one-tailed tests have more power but should only be used when the direction of effect is pre-specified. Post-hoc choice of tail inflates Type I error.",
        "The z-test applies when σ is known or n is large (n > 30). Test statistic z = (x̄ - μ₀)/(σ/√n). The t-test uses sample standard deviation s and t-distribution with n-1 degrees of freedom.",
        "Chi-squared test for independence: tests whether two categorical variables are associated. Test statistic χ² = Σ(O-E)²/E, where O = observed and E = expected frequencies. df = (r-1)(c-1).",
        "The Fisher exact test is used for 2×2 contingency tables with small expected cell counts (< 5). Computes exact p-value from hypergeometric distribution.",
        "Effect size measures like Cohen's d, Pearson r, and η² quantify the magnitude of an effect independently of sample size. Report alongside p-values for complete inference.",
        "Publication bias: studies with significant p-values are more likely published. Meta-analyses must account for this via funnel plots, Egger's test, and trim-and-fill methods.",
        "The replication crisis: many published findings with p < 0.05 fail to replicate. Causes include underpowered studies, p-hacking, HARKing (hypothesizing after results known), and publication bias.",
        "Bayesian alternative to p-values: the Bayes factor compares evidence for H₁ vs H₀ directly. BF₁₀ > 3 is considered moderate evidence; BF₁₀ > 10 strong. Does not require a fixed α threshold.",
        "Base rate neglect: even with p < 0.05, the probability that H₀ is false depends on prior probability. If only 10% of tested hypotheses are true, most 'significant' findings are false positives (PPV formula).",
    ],

    # ── STATISTICS — MULTIPLE COMPARISONS ────────────────────────────────────
    "statistics_multiple_comparisons": [
        "The multiple comparisons problem: performing m hypothesis tests at α = 0.05 gives P(at least one false positive) = 1 - (0.95)^m. For m=20, this is ~64%. Some correction is required.",
        "Bonferroni correction: use threshold α/m for each individual test to maintain family-wise error rate (FWER) at α. Simple but conservative; reduces power, especially for large m.",
        "The Holm-Bonferroni method: sort p-values ascending, apply sequentially adjusted thresholds α/m, α/(m-1), etc. Uniformly more powerful than Bonferroni while still controlling FWER.",
        "False discovery rate (FDR): the expected proportion of rejected hypotheses that are false positives. Less stringent than FWER. Appropriate when a few false positives are acceptable.",
        "The Benjamini-Hochberg procedure controls FDR at level q: sort p-values ascending, find largest k such that p_(k) ≤ (k/m)·q, reject first k hypotheses. Used widely in genomics.",
        "P-hacking (data dredging): running many tests, including covariates, removing outliers, or stopping early to achieve p < 0.05. Inflates Type I error without correction.",
        "ANOVA (analysis of variance) tests whether means of ≥2 groups differ. F-statistic = MS_between / MS_within. Post-hoc tests (Tukey, Dunnett, Scheffé) correct for multiple pairwise comparisons.",
        "Tukey's HSD (honestly significant difference): controls FWER for all pairwise comparisons after ANOVA. Based on the studentized range distribution. Appropriate when all pairs are of interest.",
        "Family-wise error rate (FWER) vs false discovery rate (FDR): FWER controls any false positive; FDR controls the proportion of false positives. FDR-controlling procedures are less conservative.",
        "Genome-wide association studies (GWAS) test ~millions of SNPs; use threshold p < 5×10⁻⁸ (corresponding to Bonferroni correction for ~10⁶ tests) to control FWER.",
        "Permutation testing: estimate the null distribution empirically by shuffling labels and recomputing test statistics many times. Automatically accounts for data structure and dependencies.",
        "Closed testing procedure: a general framework for FWER control. A hypothesis H is rejected only if all hypotheses intersecting with H are rejected at level α by valid tests.",
        "The Texas sharpshooter fallacy: finding a pattern post-hoc in data, then claiming it was predicted. Analogous to drawing a bullseye around bullet holes. Requires pre-registration to avoid.",
        "Pre-registration: specifying hypotheses, sample size, analysis plan, and stopping rules before data collection. Separates confirmatory from exploratory analysis. Registered reports guarantee publication.",
        "Structured equation modeling (SEM) and multilevel models handle complex dependency structures where simple multiple-comparison corrections would be overly conservative.",
    ],

    # ── STATISTICS — CONFIDENCE INTERVALS ────────────────────────────────────
    "statistics_confidence_interval": [
        "A 95% confidence interval (CI) means: if the same procedure is repeated on many samples, 95% of the resulting CIs would contain the true parameter. It does NOT mean 95% probability the true value is in this specific interval.",
        "For a normal population with known σ: CI = x̄ ± z_(α/2) · σ/√n. For unknown σ (t-distribution): CI = x̄ ± t_(α/2, n-1) · s/√n.",
        "Margin of error = half-width of the CI = z · σ/√n. To halve the margin of error, quadruple the sample size (because n appears under a square root).",
        "CI width depends on: sample size n (larger = narrower), confidence level (higher = wider), and population variability σ (higher = wider).",
        "Bootstrap CI: resample with replacement B times, compute the statistic each time, use the empirical distribution. Percentile bootstrap CI: [θ̂_(α/2), θ̂_(1-α/2)].",
        "The t-interval for small samples (n < 30) uses the t-distribution with n-1 degrees of freedom. As n → ∞, t approaches z. The t-distribution has heavier tails to account for estimating σ.",
        "Clopper-Pearson exact CI for proportions: based on the binomial distribution. The Wilson interval is preferred for small samples; it has better coverage near p=0 or p=1.",
        "Prediction interval vs confidence interval: CI estimates a population parameter (the mean); prediction interval estimates a single future observation. Prediction intervals are always wider.",
        "CIs for differences: two-sample t-test gives CI for μ₁ - μ₂. If CI excludes 0, the test is significant at the corresponding α. CI provides more information than the p-value alone.",
        "One-sided CIs: lower bound = x̄ - z · σ/√n (for testing H₁: μ > μ₀); upper bound = x̄ + z · σ/√n (for H₁: μ < μ₀). More powerful than two-sided when direction is known.",
        "Simultaneous confidence bands: for regression, the confidence band for the full regression line requires a wider multiplier than for a single prediction to maintain 95% coverage overall.",
        "Robust CIs: standard CIs assume normality or large n. Robust alternatives include the Huber estimator and rank-based methods, which are less sensitive to outliers.",
        "Effect size CIs: reporting CIs for Cohen's d or r allows readers to assess practical significance. A CI entirely above 0 with d > 0.5 is practically as well as statistically meaningful.",
        "Likelihood ratio CI: defined by the set of parameter values not rejected by a likelihood ratio test. More accurate than Wald CIs for non-linear parameters.",
        "Bayesian credible interval: a 95% credible interval contains the true parameter with 95% probability under the posterior distribution. This is the intuitive interpretation people (incorrectly) assign to frequentist CIs.",
    ],

    # ── SCRIPTURE ANCHORS (verse citations, not generic theological) ──────────
    "scripture_anchors": [
        "Matthew 7:24-27 — the parable of the wise and foolish builders. Wise builder hears Jesus' words AND obeys; house stands in storms. Foolish builder hears but does not obey; house falls. Hearing without doing is foolishness.",
        "Proverbs 3:5-6 — 'Trust in the LORD with all your heart, and do not lean on your own understanding. In all your ways acknowledge him, and he will make straight your paths.' Foundational wisdom passage.",
        "Romans 12:2 — 'Do not be conformed to this world, but be transformed by the renewal of your mind, that by testing you may discern what is the will of God.' The mind is the testing instrument.",
        "James 1:5 — 'If any of you lacks wisdom, let him ask God, who gives generously to all without reproach, and it will be given him.' Prayer for wisdom is explicitly commanded and promised.",
        "John 17:17 — 'Sanctify them in the truth; your word is truth.' Jesus' high priestly prayer: Scripture is the sanctifying instrument. Truth is not abstract; it is the Word.",
        "2 Timothy 3:16-17 — 'All Scripture is breathed out by God and profitable for doctrine, reproof, correction, and training in righteousness, that the man of God may be complete.' Canon is closed and sufficient.",
        "Hebrews 4:12 — 'The word of God is living and active, sharper than any two-edged sword, piercing to the division of soul and of spirit.' Scripture is a discerning instrument, not just information.",
        "Psalm 119:105 — 'Your word is a lamp to my feet and a light to my path.' Scripture functions as directional light in darkness, illuminating each step, not the whole road.",
        "Isaiah 55:11 — 'My word…shall not return to me empty, but it shall accomplish that which I purpose.' God's word is efficacious; it performs its intended function without failure.",
        "Deuteronomy 8:3 — 'Man does not live by bread alone, but man lives by every word that comes from the mouth of the LORD.' Quoted by Jesus in the wilderness (Matthew 4:4).",
        "Luke 24:27 — 'Beginning with Moses and all the Prophets, he interpreted to them in all the Scriptures the things concerning himself.' All Scripture points to Christ; Christocentric hermeneutic.",
        "Acts 17:11 — 'The Bereans…received the word with all eagerness, examining the Scriptures daily to see if these things were so.' Scripture is the test; even apostolic teaching must be verified.",
        "Revelation 22:18-19 — Warning against adding to or taking from the book of prophecy. This is the canonical seal; the text is fixed. Tradition cannot supplement Scripture at this level.",
        "Matthew 5:18 — 'Until heaven and earth pass away, not an iota, not a dot, will pass from the Law until all is accomplished.' Jesus affirmed the precision and permanence of Scripture.",
        "1 Corinthians 15:3-4 — 'Christ died for our sins in accordance with the Scriptures, that he was buried, that he was raised on the third day in accordance with the Scriptures.' Core gospel formula anchored in OT prophecy.",
        "Jeremiah 29:11 — 'For I know the plans I have for you, declares the LORD, plans for welfare and not for evil, to give you a future and a hope.' Often over-applied; originally addressed to exiled Israel, but the character of God it reveals is universal.",
        "Genesis 1:1 — 'In the beginning, God created the heavens and the earth.' First verse establishes: God is prior to creation, creation is ex nihilo, time-space-matter-energy are contingent.",
        "John 1:1-3 — 'In the beginning was the Word, and the Word was with God, and the Word was God.' Echoes Genesis 1. The Logos (Christ) was the agent of all creation.",
        "Philippians 4:6-7 — 'Do not be anxious about anything, but in everything by prayer and supplication with thanksgiving let your requests be made known to God.' Prayer displaces anxiety structurally.",
        "Romans 8:28 — 'And we know that for those who love God all things work together for good, for those who are called according to his purpose.' Not all things are good; they work together toward good.",
    ],

    # ── GOVERNANCE DECISION PACKETS ──────────────────────────────────────────
    "governance_decision_packet": [
        "The principal-agent problem: when one party (agent) acts on behalf of another (principal), incentive misalignment arises. Corporate boards, elected officials, and fund managers all face this. Solutions: monitoring, incentive alignment, reputation.",
        "Separation of powers: legislative (makes laws), executive (enforces laws), judicial (interprets laws) branches are distinct to prevent tyranny. Montesquieu's doctrine implemented in the US Constitution.",
        "The Rule of Law requires: laws are public and prospective (not retroactive); applied equally to all; interpreted by an independent judiciary; no one is above the law including rulers.",
        "Checks and balances in the US: Congress passes laws, President can veto, Congress can override with 2/3 majority, courts can strike down unconstitutional laws via judicial review (Marbury v. Madison, 1803).",
        "Federalism divides sovereignty between national and state governments. Enumerated powers (Article I §8) are federal; all others reserved to states (10th Amendment). Prevents geographic tyranny.",
        "Constitutional limits on democracy: individual rights (Bill of Rights) protect minorities from majority rule. Tyranny of the majority is a recognized failure mode of pure democracy.",
        "Consent of the governed: Locke's social contract — legitimate government derives authority from the consent of the governed. If government violates natural rights, revolution is justified.",
        "OECD Principles of Corporate Governance: shareholder rights, equitable treatment, role of stakeholders, disclosure and transparency, responsibilities of the board.",
        "Roberts Rules of Order: procedural framework for deliberative assemblies. Motions are introduced, seconded, debated, amended, and voted upon. Ensures orderly decision-making at scale.",
        "The OODA loop (Observe, Orient, Decide, Act): decision-making cycle developed by Col. John Boyd. Faster OODA loops beat slower ones. Orientation (mental models) is the critical node.",
        "Decision theory: decision under certainty (known outcomes), risk (known probabilities), uncertainty (unknown probabilities), and ambiguity (unknown state space). Each requires different tools.",
        "The Overton window: the range of policies politically acceptable to the mainstream public at a given time. Political entrepreneurs move the window by normalizing previously fringe ideas.",
        "Subsidiarity: decisions should be made at the lowest competent level. Catholic social teaching; also embedded in EU law. Opposes both overcentralization and abdication of duty.",
        "Democratic backsliding: gradual erosion of democratic norms — elected autocrats capturing institutions, undermining press freedom, and packing courts — rather than sudden coups.",
        "The iron triangle of governance: agency (bureaucracy), congressional subcommittee, and interest group form a stable policy-making triad resistant to outside reform. Also called the policy triangle.",
    ],

    # ── THEOLOGY — DOCTRINE ──────────────────────────────────────────────────
    "theology_doctrine": [
        "The Trinity: God is one Being (ousia) in three Persons (hypostases) — Father, Son, Holy Spirit. Co-equal, co-eternal, co-substantial. Not three gods (tritheism) nor one person in three modes (modalism/Sabellianism).",
        "The Nicene Creed (325 AD, expanded 381 AD): 'We believe in one God, the Father Almighty… and in one Lord Jesus Christ, the only-begotten Son of God… Very God of Very God… And in the Holy Spirit, the Lord and giver of life.' Trinitarian orthodoxy established against Arianism.",
        "The hypostatic union: Jesus Christ is fully God and fully human in one Person. Two natures (divine and human) without confusion, change, division, or separation (Chalcedonian Definition, 451 AD).",
        "Original sin (Augustine): Adam's sin corrupted human nature, transmitted to all descendants, resulting in death, concupiscence, and bondage of will. Requires grace, not just moral effort.",
        "Penal substitutionary atonement: Christ bore the punishment that God's justice required for human sin. His death satisfied divine wrath (propitiation) and freed believers from condemnation.",
        "Justification by faith alone (sola fide): sinners are declared righteous before God on the basis of Christ's imputed righteousness received through faith, not works. Luther's discovery from Romans 1:17.",
        "Election and predestination: God sovereignly chooses who will be saved (Ephesians 1:4-5, Romans 8:29-30). Calvinist/Reformed view: unconditional election based on God's will alone, not foreseen faith.",
        "The ordo salutis (order of salvation in Reformed theology): calling → regeneration → faith → repentance → justification → adoption → sanctification → perseverance → glorification.",
        "Common grace vs special grace: common grace (general benevolence to all creation — rain, reason, conscience) vs special grace (saving grace given only to the elect). Both flow from God's character.",
        "The canon of Scripture (Protestant): 66 books — 39 Old Testament, 27 New Testament. Apostolic authorship or connection, consistency with prior revelation, and reception by the church determined canonicity.",
        "The Reformation Solas: Sola Scriptura (Scripture alone is the supreme authority), Sola Fide (faith alone justifies), Sola Gratia (grace alone saves), Solus Christus (Christ alone mediates), Soli Deo Gloria (glory to God alone).",
        "Cessationism vs continuationism: do miraculous sign gifts (tongues, prophecy, healing) continue today? Cessationists say they ceased with the apostolic age; continuationists say they continue.",
        "The Second Coming: Christ will return bodily and visibly (Acts 1:11, Revelation 1:7). Pre/post/amillennial views differ on timing relative to the millennium. Resurrection and final judgment follow.",
        "Imago Dei: humans are made in the image of God (Genesis 1:26-27). This grounds human dignity, moral accountability, and capacity for relationship with God. The image is marred by sin but not erased.",
        "The Great Commission (Matthew 28:18-20): 'All authority in heaven and on earth has been given to me. Go therefore and make disciples of all nations, baptizing them… teaching them to observe all that I have commanded.' Mission is grounded in Christ's universal authority.",
    ],

    # ── APOLOGETICS ──────────────────────────────────────────────────────────
    "apologetics": [
        "The cosmological argument (Kalam version): 1) Everything that begins to exist has a cause. 2) The universe began to exist. 3) Therefore, the universe has a cause. The cause must be uncaused, timeless, spaceless, and immensely powerful — consistent with theism.",
        "The teleological argument (fine-tuning): the fundamental constants of physics are fine-tuned to extraordinary precision for life. The probability of this by chance is astronomically small. God as intentional designer is the simplest explanation.",
        "The ontological argument (Anselm): God is defined as 'that than which nothing greater can be conceived.' A being that exists in reality is greater than one existing only in the mind. Therefore, if God can be conceived, God must exist.",
        "The moral argument: 1) If God does not exist, objective moral values do not exist. 2) Objective moral values do exist (moral realism). 3) Therefore, God exists. C.S. Lewis: the existence of moral law implies a moral Lawgiver.",
        "The argument from consciousness: materialist explanations of consciousness (the hard problem) are inadequate. Consciousness as subjective first-person experience is better explained by a personal, conscious God than by blind physical processes.",
        "The resurrection of Jesus: historical arguments for the resurrection include: the empty tomb (acknowledged by opponents), post-resurrection appearances to multiple witnesses (1 Corinthians 15:3-8), and the disciples' willingness to die for the claim.",
        "N.T. Wright's minimal facts argument: five historically defensible facts about early Christianity (Jesus died, buried, empty tomb, appearances, disciples believed) are best explained by the resurrection.",
        "The reliability of the New Testament: over 5,800 Greek manuscripts, earlier copies, and wider manuscript attestation than any ancient document. The text is 99.5% certain; variants do not affect core doctrine.",
        "C.S. Lewis's trilemma (liar, lunatic, or Lord): Jesus claimed to be God. He was either lying, deluded, or telling the truth. The quality of his teaching and character makes liar and lunatic implausible; Lord remains.",
        "Presuppositionalism (Van Til): the triune God and Scripture are the necessary preconditions for intelligibility, ethics, and science. Atheism is self-defeating because it borrows from the Christian worldview to argue against it.",
    ],

    # ── ESCHATOLOGY ──────────────────────────────────────────────────────────
    "eschatology": [
        "Amillennialism: the millennium of Revelation 20 is symbolic, representing the current church age. Christ reigns now through the church; no literal 1000-year reign on earth before the Second Coming. Dominant view of Reformed and Catholic traditions.",
        "Premillennialism: Christ returns before the millennium, establishing a literal 1000-year reign. Historic premillennialism: church goes through tribulation; dispensational premillennialism adds a pre-tribulation rapture.",
        "The Rapture debate: pretribulational rapture (church removed before 7-year tribulation) is a 19th-century view (John Nelson Darby). Mid-trib, pre-wrath, and posttrib views are also held. The word 'rapture' comes from 1 Thessalonians 4:17 (Latin: raptus).",
        "The Great Tribulation (Matthew 24:21): Jesus warns of unprecedented tribulation. Preterists say this was fulfilled in the Roman destruction of Jerusalem (70 AD); futurists say a global tribulation is yet to come.",
        "Daniel's 70 weeks (Daniel 9:24-27): 70 sevens = 490 years appointed for Israel. Interpreted by dispensationalists as 69 weeks fulfilled in Christ's first coming + a gap + final 7-year tribulation.",
        "The new creation (Revelation 21-22): God will make all things new — a new heaven, new earth, and new Jerusalem. Not destruction of the physical but transformation. Physical resurrection implies continuity with creation.",
        "The final judgment: all will appear before God's throne. Books are opened; the dead judged according to what they have done. The Book of Life determines salvation (Revelation 20:12-15). No purgatory in Protestant theology.",
        "The resurrection of the body: Jesus' resurrection is the prototype. Believers receive glorified bodies (1 Corinthians 15:42-44) — incorruptible, powerful, spiritual (directed by Spirit, not natural desires). Physical and continuous with current body.",
        "Israel and the church in eschatology: dispensationalists maintain a strict distinction between Israel and the church, with future national restoration of Israel. Covenant theologians see the church as the continuation of the covenant community.",
        "The inaugurated eschatology (already/not yet): the Kingdom of God has been inaugurated in Christ's first coming but not yet consummated. The Holy Spirit is the down payment (arrabon) of the coming age (Ephesians 1:14).",
    ],

    # ── MATHEMATICS (advanced topics not in Wave 1) ──────────────────────────
    "mathematics": [
        "Gödel's incompleteness theorems (1931): 1) Any consistent formal system powerful enough to encode arithmetic contains true statements it cannot prove. 2) Such a system cannot prove its own consistency.",
        "Cantor's theorem: for any set S, its power set P(S) has strictly greater cardinality than S. Therefore, there is no 'largest' infinity. Implies the hierarchy ℵ₀ < ℵ₁ < ℵ₂ < …",
        "The Axiom of Choice (AC): for any collection of non-empty sets, there exists a function selecting one element from each set. Equivalent to Zorn's lemma and the well-ordering theorem. Independent of ZF.",
        "Abstract algebra: a group (G, ·) satisfies closure, associativity, identity (e: a·e = a), and inverses (a⁻¹: a·a⁻¹ = e). Groups → rings (two operations) → fields (division allowed).",
        "The fundamental theorem of algebra: every non-constant polynomial with complex coefficients has at least one complex root. Therefore, a degree-n polynomial has exactly n roots (counted with multiplicity).",
        "Euler's identity: e^(iπ) + 1 = 0. Links five fundamental constants (e, i, π, 1, 0). Derived from Euler's formula e^(iθ) = cos θ + i sin θ.",
        "Fermat's Last Theorem: no three positive integers a, b, c satisfy aⁿ + bⁿ = cⁿ for n > 2. Stated 1637, proved by Andrew Wiles (1995) using elliptic curves and modular forms.",
        "The prime number theorem: π(n) ~ n/ln(n) as n → ∞, where π(n) is the count of primes ≤ n. Proved independently by Hadamard and de la Vallée Poussin (1896) using complex analysis.",
        "Calculus fundamental theorem: ∫_a^b f(x)dx = F(b) - F(a) where F' = f. Links differentiation and integration — antiderivatives evaluate definite integrals.",
        "Taylor series: f(x) = Σ f⁽ⁿ⁾(a)/n! · (x-a)ⁿ. Represents smooth functions as infinite polynomials near a point. e^x = 1 + x + x²/2! + … converges for all x.",
    ],

    # ── LINGUISTICS (advanced — pragmatics, typology, acquisition) ───────────
    "linguistics": [
        "Grice's maxims of conversation: Quantity (say enough, not too much), Quality (be truthful), Relation (be relevant), Manner (be clear and orderly). Violations generate conversational implicature.",
        "Speech act theory (Austin, Searle): utterances perform actions — locutionary (literal meaning), illocutionary (intended act: promise, question, command), perlocutionary (effect on listener).",
        "The universal grammar hypothesis (Chomsky): humans are born with an innate language acquisition device (LAD) containing parameters for all possible human languages. Poverty of the stimulus supports innateness.",
        "The critical period hypothesis: language acquisition is most efficient before puberty. Feral children (Genie) and late learners of L2 phonology support a sensitive period for syntax and phonology.",
        "Markedness in typology: universally, unmarked forms are more frequent, simpler, and acquired earlier. Singular is unmarked vs plural; active is unmarked vs passive; /p/ is unmarked vs /ph/ in English.",
        "Constituent structure (X-bar theory): phrases are headed by a lexical item (X⁰), optionally modified by complements (XP → X' + CP) and specifiers (XP → Spec + X'). Accounts for phrase structure universals.",
        "Semantic compositionality (Frege's principle): the meaning of a complex expression is a function of the meanings of its parts and the way they are combined. This is the basis of formal semantics.",
        "Language contact and borrowing: languages in contact exchange vocabulary (loanwords), phonology, and syntax. Pidgins form for basic communication; creoles arise when pidgins become native languages.",
        "The Sapir-Whorf hypothesis (linguistic relativity): language influences thought. Strong version (linguistic determinism) is discredited; weak version (language shapes habitual thought) has experimental support in color perception and spatial cognition.",
        "Historical linguistics: languages change systematically. Grimm's Law: Proto-Germanic shifted stops — PIE *p, t, k → Germanic f, θ, h. Explains why Latin pater = English father.",
        "The Minimalist Program (Chomsky 1995+): the language faculty is optimally designed — only the simplest operations (Merge) and principles (Full Interpretation) are needed. Internalist, not communicative.",
        "Discourse coherence: texts are coherent when propositions are connected by rhetorical relations (elaboration, contrast, cause-effect). Incoherent texts fail the antecedence test for pronoun resolution.",
    ],

    # ── NUMBER THEORY (deeper than Wave 1) ───────────────────────────────────
    "number_theory": [
        "The Fundamental Theorem of Arithmetic: every integer > 1 has a unique factorization into primes. This uniqueness underlies much of number theory and cryptography.",
        "Modular arithmetic: a ≡ b (mod n) iff n | (a - b). Forms the ring ℤ/nℤ. Chinese Remainder Theorem: simultaneous congruences with coprime moduli have a unique solution mod the product.",
        "Euler's totient function φ(n): counts integers from 1 to n coprime to n. φ(p) = p-1 for prime p; φ(pq) = (p-1)(q-1). Used in RSA: m^(φ(n)) ≡ 1 (mod n) when gcd(m,n)=1.",
        "Fermat's Little Theorem: if p is prime and p ∤ a, then a^(p-1) ≡ 1 (mod p). Equivalently, a^p ≡ a (mod p) for all a. Basis for primality tests and the RSA algorithm.",
        "The Riemann Hypothesis: the non-trivial zeros of the Riemann zeta function ζ(s) all lie on the critical line Re(s) = 1/2. If true, gives precise error bounds on the prime number theorem.",
        "Quadratic reciprocity (Gauss): for distinct odd primes p, q: (p/q)(q/p) = (-1)^((p-1)/2 · (q-1)/2). Determines solvability of x² ≡ p (mod q). Called the 'gem of arithmetic' by Gauss.",
        "Mersenne primes: primes of the form 2^p - 1 where p is prime. Only known large primes are Mersenne primes. M₂ = 3, M₃ = 7, M₅ = 31. The GIMPS project searches for new ones.",
        "Goldbach's conjecture (1742, unproved): every even integer > 2 is the sum of two primes. Verified for all even numbers up to 4×10¹⁸. One of the oldest unsolved problems.",
        "Perfect numbers: equal the sum of their proper divisors. 6 = 1+2+3; 28 = 1+2+4+7+14. Even perfect numbers correspond bijectively to Mersenne primes (Euler). Odd perfect numbers unknown.",
        "The p-adic numbers ℚ_p: complete the rationals using the p-adic metric |x|_p = p^(-v_p(x)) where v_p is the p-adic valuation. Ostrowski's theorem: every non-trivial absolute value on ℚ is either the usual absolute value or a p-adic one.",
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
    parser.add_argument("--reset", action="store_true", help="Clear state and re-post all")
    args = parser.parse_args()

    posted = set() if args.reset else load_state()
    session = requests.Session()

    domains = {args.domain: SEEDS[args.domain]} if args.domain else SEEDS

    total_seeds = sum(len(v) for v in domains.values())
    total_new = sum(
        1 for seeds in domains.values()
        for s in seeds if fingerprint(s) not in posted
    )
    print(f"\nWave 3 — {total_seeds} seeds across {len(domains)} domains")
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
