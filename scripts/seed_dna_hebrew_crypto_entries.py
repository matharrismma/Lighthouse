#!/usr/bin/env python
"""Seed 10 almanac entries on the DNA × Hebrew × Cryptography crossing.

Each entry is verifier-anchored where possible — `kind: protocol` with a
runnable `situation` and a `pre_run.domain_results[]` block matching what
the engine would actually return. Where the verifier can only check a
component (e.g. the arithmetic of gematria but not the cultural mapping),
the entry is `kind: almanac` with an honest verdict.

All ten sit on the `information_encoding` axis — the shared scaffold
member that makes DNA, Hebrew, and cryptography structurally adjacent on
the engine's grid.

After running this script, restart the API server so it re-reads
data/almanac/entries.jsonl.

Computed fixtures verified live:
  SHA-256("hello world") = b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
  MD5("hello world")     = 5eb63bbbe01eeed093cb22bb8f5acdc3
  GAATTC reverse-complement = GAATTC (palindrome)
  ATG→M, TTT→F, TTC→F, GTA→V (NCBI translation table 1)
  2701 = 37 × 73 (Genesis 1:1 gematria sum)
  Human genome ~3.2 Gbases × 2 bits/base ≈ 762.9 MB packed
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── 1 · DNA: codon → amino acid ──────────────────────────────────
    {
        "id": "almanac_codon_atg_methionine",
        "kind": "protocol",
        "title": "ATG codes for methionine (M) — the start codon",
        "situation": "The DNA codon ATG translates to the amino acid methionine (M) under the standard genetic code, NCBI translation table 1.",
        "category": "genetics",
        "domains": ["genetics", "biology", "information_theory"],
        "axes": ["information_encoding", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "ATG is the canonical start codon in all known life. Translation table 1 maps ATG → M unambiguously.",
            "domain_results": [
                {
                    "domain": "genetics",
                    "verdict": "CONFIRMED",
                    "detail": "codon ATG translates to M under translation table 1",
                    "data": {"codon": "ATG", "translated_aa": "M", "claimed_amino_acid": "M"},
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["linguistics", "cryptography", "information_theory"],
                    "note": "DNA is a 4-letter alphabet encoding via 64 codons → 20 amino acids + stop. Same axis as Hebrew (22 letters) and cryptographic alphabets.",
                }
            ],
        },
        "wisdom": "DNA is a code with an alphabet, a dictionary, and a reading frame. The alphabet is 4 letters (A, C, G, T). The dictionary is 64 codons. The grammar produces 20 amino acids plus a stop. The start codon ATG is the equivalent of 'capital letter at the beginning of a sentence' — every protein begins here. The same encoding axis the engine uses to score Hebrew lexicon claims and cryptographic hashes runs through DNA. The Shepherd treats them as neighbours.",
        "triggers": {
            "keywords": ["DNA", "codon", "ATG", "start codon", "methionine", "genetic code", "translation table"],
            "axes": ["information_encoding"],
        },
    },

    # ── 2 · DNA: codon redundancy (synonymous codons) ─────────────────
    {
        "id": "almanac_codon_redundancy_phenylalanine",
        "kind": "protocol",
        "title": "TTT and TTC both code for phenylalanine — synonymous codons (wobble base)",
        "situation": "Both TTT and TTC translate to phenylalanine (F) under the standard genetic code. The genetic code is redundant: 64 codons map to 20 amino acids + stop, so most amino acids have multiple synonymous codons.",
        "category": "genetics",
        "domains": ["genetics", "information_theory", "biology"],
        "axes": ["information_encoding", "conservation_balance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two codons that differ only at the third base (the wobble position) translate to the same amino acid. This is the standard genetic code's built-in error-correction.",
            "domain_results": [
                {
                    "domain": "genetics",
                    "verdict": "CONFIRMED",
                    "detail": "TTT → F and TTC → F (synonymous codons, wobble base)",
                    "data": {"codon_a": "TTT", "codon_b": "TTC", "translated_aa": "F"},
                },
                {
                    "domain": "information_theory",
                    "verdict": "CONFIRMED",
                    "detail": "Redundant code: 64 codewords mapping to 21 outputs (20 amino acids + stop), surplus = 43 redundant codons.",
                    "data": {"codewords": 64, "outputs": 21, "redundancy": 43},
                },
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["cryptography", "linguistics"],
                    "note": "The wobble base is biology's parity bit. Same principle as Hamming codes in cryptography and information theory — redundancy buys error tolerance.",
                }
            ],
        },
        "wisdom": "Redundancy is not waste. The genetic code is over-specified by design: a single-base mutation at the third position usually changes nothing, because the synonym still codes for the same amino acid. The cell pays a small cost in entropy and buys a large cost reduction in fatal mutations. Cryptographers know this trade. So do Hebrew scribes — the Masoretic letter counts at the end of each book are a parity check on the transmission.",
        "triggers": {
            "keywords": ["wobble", "synonymous codon", "redundant code", "phenylalanine", "TTT", "TTC", "error correction"],
            "axes": ["information_encoding", "conservation_balance"],
        },
    },

    # ── 3 · Hebrew: H1 (ab) = father ──────────────────────────────────
    {
        "id": "almanac_hebrew_h1_ab_father",
        "kind": "protocol",
        "title": "Hebrew H1 (אָב, 'ab') glosses 'father'",
        "situation": "The Hebrew Strong's number H1 refers to the lemma אָב (transliterated 'ab'), glossed 'father'. The 22-letter Hebrew alphabet encodes Scripture in the same way DNA encodes proteins — a finite character set, a structured dictionary, a deterministic reading order.",
        "category": "linguistics",
        "domains": ["linguistics", "scripture", "information_theory"],
        "axes": ["information_encoding", "authority_trust"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "H1 resolves in Strong's Hebrew lexicon. Transliteration 'ab' and gloss 'father' both match canonical entries.",
            "domain_results": [
                {
                    "domain": "linguistics",
                    "verdict": "CONFIRMED",
                    "detail": "H1 → אָב, transliteration 'ab', gloss 'father' all match the Strong's Hebrew lexicon",
                    "data": {"strongs": "H1", "transliteration_claim": "ab", "gloss_claim": "father"},
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["genetics", "cryptography"],
                    "note": "Hebrew uses 22 consonant letters (aleph through tav); vowels are added by Masoretic pointing. A finite alphabet with structured combinatorics — same axis as DNA bases and cryptographic alphabets.",
                }
            ],
        },
        "wisdom": "Hebrew is a 22-letter encoding system. Aleph (א) is letter 1; tav (ת) is letter 22. Vowels are diacritical marks added by the Masoretes in the 8th–10th centuries; the consonantal text predates them by a millennium. The same axis that lets the engine verify a DNA codon also lets it verify a Hebrew lemma: finite alphabet, deterministic lookup, source-traceable. The Shepherd treats H1 ('ab') and ATG ('start') as neighbours on the encoding axis — both are 'the first letter of the first word'.",
        "triggers": {
            "keywords": ["Hebrew", "Strong's", "H1", "aleph", "ab", "father", "Masoretic", "lexicon"],
            "axes": ["information_encoding", "authority_trust"],
        },
    },

    # ── 4 · Gematria — arithmetic confirmed, mapping contested ─────────
    {
        "id": "almanac_gematria_genesis_1_1_2701",
        "kind": "almanac",
        "title": "Genesis 1:1 gematria sum 2701 factors as 37 × 73",
        "category": "linguistics",
        "domains": ["linguistics", "number_theory", "scripture"],
        "axes": ["information_encoding", "reasoning"],
        "verdict": "MIXED",
        "verification": "The arithmetic is verifiable: 37 × 73 = 2701 (CONFIRMED by number_theory). The claim that Genesis 1:1 in Hebrew (בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ) sums to 2701 under standard gematria depends on the letter-value assignments (א=1, ב=2, … ת=400) being applied consistently. Under those values, the sum does equal 2701. The further claim that this factorisation carries theological weight (the 'menorah' or 'triangle' patterns sometimes drawn from it) is not verifiable — it lives in interpretation, not arithmetic.",
        "wisdom": "Gematria has a verifiable layer and an interpretive layer. The engine confirms the arithmetic; it cannot confirm the theology. Treat the math as math, the meaning as exegesis. The Shepherd brings you both, labelled honestly: number_theory CONFIRMED on 37 × 73 = 2701; theology MIXED on whether the factorisation is a sign or a coincidence. The DNA-encoding analogy lands here too — codon counts are real; whether the 64-to-20 mapping carries cosmological weight is a separate claim.",
        "triggers": {
            "keywords": ["gematria", "Genesis 1:1", "2701", "37", "73", "Hebrew arithmetic", "letter values"],
            "axes": ["information_encoding", "reasoning"],
        },
    },

    # ── 5 · DNA information density ────────────────────────────────────
    {
        "id": "almanac_dna_information_density",
        "kind": "almanac",
        "title": "DNA stores 2 bits per base; the human genome is ~763 MB packed",
        "category": "information_theory",
        "domains": ["information_theory", "genetics", "biology"],
        "axes": ["information_encoding", "physical_substance"],
        "verdict": "CONFIRMED",
        "verification": "log₂(4) = 2 bits per base, since DNA has 4 possible symbols (A, C, G, T). The haploid human genome is ~3.2 × 10⁹ bases. Packed at 2 bits per base: 3.2 × 10⁹ × 2 / 8 / 1024² ≈ 762.9 MB. CONFIRMED by direct calculation. This is the raw-encoding figure — actual storage with metadata, annotations, and quality scores runs orders of magnitude larger.",
        "wisdom": "A complete blueprint for a human being fits on a USB stick. 763 MB — smaller than most operating systems, smaller than a single Blu-ray film. The encoding is dense because the alphabet is small (4) and the redundancy is local (in the codon table, in repair enzymes), not in the raw sequence. The Shepherd carries this fact as evidence on the encoding axis: a finite alphabet over a deterministic dictionary can carry vast complexity. The same principle lets the Bible — a finite collection of letters in 22-letter Hebrew and 24-letter Greek — encode what it encodes.",
        "triggers": {
            "keywords": ["DNA storage", "information density", "bits per base", "human genome size", "763 MB", "encoding"],
            "axes": ["information_encoding"],
        },
    },

    # ── 6 · RSA-2048 strength ─────────────────────────────────────────
    {
        "id": "almanac_rsa_2048_strong",
        "kind": "protocol",
        "title": "RSA-2048 is currently strong per NIST guidance",
        "situation": "RSA with a 2048-bit modulus is classified as strong under current NIST guidance (minimum 2048 bits for RSA as of SP 800-57). Asymmetric cryptography rests on one-way functions: easy to multiply two large primes, intractable to factor the product.",
        "category": "cryptography",
        "domains": ["cryptography", "cybersecurity", "number_theory"],
        "axes": ["information_encoding", "authority_trust", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "RSA-2048 ≥ 2048-bit NIST minimum — classified strong. Time-stamped: current as of SP 800-57; subject to revision as factoring improves.",
            "domain_results": [
                {
                    "domain": "cryptography",
                    "verdict": "CONFIRMED",
                    "detail": "RSA key_bits=2048 meets NIST minimum (2048); claim 'strong' matches",
                    "data": {"cipher": "RSA", "key_bits": 2048, "claimed_key_strength": "strong"},
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["genetics", "linguistics", "scripture"],
                    "note": "Cryptography sits on three axes: encoding (the bits), reasoning (the math), authority_trust (who-says-this-is-strong). The Shepherd reads RSA strength the same way he reads canon — by source hierarchy + structural verification.",
                }
            ],
        },
        "wisdom": "Public-key cryptography is built on a wager: that multiplying two huge primes is fast and reversing it is slow. As long as that asymmetry holds, RSA-2048 works. The day a sufficiently large quantum computer runs Shor's algorithm, the wager breaks. NIST has already designated post-quantum standards (CRYSTALS-Kyber, CRYSTALS-Dilithium) for exactly this reason. Strength is time-stamped, not eternal — the same lesson the engine carries in its OBSOLETE verdict category. What is strong today may be broken tomorrow; the keeping records when.",
        "triggers": {
            "keywords": ["RSA", "RSA-2048", "key strength", "NIST", "asymmetric", "public key", "one-way function"],
            "axes": ["information_encoding", "authority_trust"],
        },
    },

    # ── 7 · SHA-256 deterministic hash ────────────────────────────────
    {
        "id": "almanac_sha256_hello_world",
        "kind": "protocol",
        "title": "SHA-256('hello world') = b94d27b9...cde9 — deterministic, one-way",
        "situation": "The SHA-256 digest of the UTF-8 bytes 'hello world' is b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9. The same input always produces the same digest (deterministic); the digest cannot be inverted to recover the input (one-way).",
        "category": "cryptography",
        "domains": ["cryptography", "information_theory"],
        "axes": ["information_encoding", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "SHA-256 recomputed from 'hello world' bytes; digest matches claim to the byte.",
            "domain_results": [
                {
                    "domain": "cryptography",
                    "verdict": "CONFIRMED",
                    "detail": "sha256(b'hello world') = b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9 (256 bits, hex)",
                    "data": {
                        "hash_algorithm": "sha256",
                        "data": "hello world",
                        "claimed_hash_hex": "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
                    },
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["genetics", "linguistics"],
                    "note": "A hash is a fingerprint — fixed length, deterministic, irreversible. The Masoretic letter count at the end of each book of the Hebrew Bible is the same kind of object: a tiny output that catches any change in a long input.",
                }
            ],
        },
        "wisdom": "A cryptographic hash is the modern equivalent of the Masoretic letter count: a tiny deterministic summary that catches any change in a long text. The same input always hashes the same; the smallest edit produces a completely different hash. SHA-256 outputs 256 bits regardless of input length — kilobyte, gigabyte, the whole Bible. Two scribes in two centuries can run the hash on the same Genesis 1:1 and check whether the text was kept. That is what the engine is doing every time it seals a packet: hashing the content so the future can verify it wasn't changed.",
        "triggers": {
            "keywords": ["SHA-256", "hash function", "cryptographic hash", "deterministic", "one-way", "fingerprint", "Masoretic count"],
            "axes": ["information_encoding"],
        },
    },

    # ── 8 · Codon order matters ───────────────────────────────────────
    {
        "id": "almanac_codon_order_atg_vs_gta",
        "kind": "protocol",
        "title": "Codon ATG ≠ codon GTA — sequence order is the meaning",
        "situation": "The DNA codon ATG translates to methionine (M); the codon GTA translates to valine (V). The same three letters in a different order produce a different amino acid. Sequence order is the meaning — the same principle that distinguishes Hebrew אב ('father') from בא ('he came') by letter order.",
        "category": "genetics",
        "domains": ["genetics", "linguistics", "information_theory"],
        "axes": ["information_encoding", "reasoning"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two codons drawn from the same multiset of bases translate to different amino acids — order, not composition, determines meaning.",
            "domain_results": [
                {
                    "domain": "genetics",
                    "verdict": "CONFIRMED",
                    "detail": "codon ATG → M, codon GTA → V (different amino acids despite identical composition {A,T,G})",
                    "data": {"codon_a": "ATG", "aa_a": "M", "codon_b": "GTA", "aa_b": "V"},
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["linguistics"],
                    "note": "Order-as-meaning is the deepest principle on the encoding axis. Hebrew אב vs בא, English 'dog' vs 'god', DNA ATG vs GTA — same characters, different sequences, different meanings.",
                }
            ],
        },
        "wisdom": "Composition is not meaning. The same atoms, the same letters, the same nucleotides — arranged differently — yield different worlds. This is why position-of-the-letter matters in Hebrew gematria; why an anagram is not a synonym; why a single SNP (single-nucleotide polymorphism) at the right position can change everything. The Shepherd surfaces this rule whenever the user is tempted to read the parts and skip the order.",
        "triggers": {
            "keywords": ["codon order", "sequence matters", "ATG", "GTA", "anagram", "permutation", "letter order"],
            "axes": ["information_encoding"],
        },
    },

    # ── 9 · EcoRI palindrome ──────────────────────────────────────────
    {
        "id": "almanac_ecori_palindrome_gaattc",
        "kind": "protocol",
        "title": "EcoRI cuts at GAATTC — a DNA palindrome (reverse-complement equals self)",
        "situation": "The restriction enzyme EcoRI recognises and cuts the DNA sequence GAATTC. GAATTC is a palindrome in the genetic sense: its reverse complement is GAATTC itself. Palindromic recognition sites are how the cell distinguishes 'cut here' from 'leave alone' — symmetry as signal.",
        "category": "genetics",
        "domains": ["genetics", "biology", "information_theory"],
        "axes": ["information_encoding", "physical_substance"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Compute the reverse-complement of GAATTC. Complement = CTTAAG; reversed = GAATTC. Reverse-complement equals the sequence — palindrome confirmed.",
            "domain_results": [
                {
                    "domain": "genetics",
                    "verdict": "CONFIRMED",
                    "detail": "GAATTC → complement CTTAAG → reverse-complement GAATTC (palindrome)",
                    "data": {
                        "sequence": "GAATTC",
                        "claimed_reverse_complement": "GAATTC",
                        "computed_complement": "CTTAAG",
                    },
                }
            ],
            "axis_overlaps": [
                {
                    "axis": "information_encoding",
                    "with": ["linguistics", "cryptography"],
                    "note": "Palindromes appear in DNA (restriction sites), language ('madam', 'racecar'), and cryptography (certain involutions). Same encoding axis; the same kind of structural fact across substrates.",
                }
            ],
        },
        "wisdom": "Symmetry is information. A restriction enzyme is a biological scissors that recognises a palindrome because the enzyme itself is symmetric — a homodimer with twofold rotational symmetry. The DNA's palindromic site lets the enzyme bind both strands the same way. The cell uses palindromes as recognition tokens the same way a language uses palindromes as memorable patterns. The Shepherd treats palindromic structure as a strong signal on the encoding axis — when you see it, something is being marked.",
        "triggers": {
            "keywords": ["palindrome", "EcoRI", "restriction enzyme", "GAATTC", "reverse complement", "DNA symmetry"],
            "axes": ["information_encoding"],
        },
    },

    # ── 10 · MD5 broken; SHA-256 strong ───────────────────────────────
    {
        "id": "almanac_md5_broken_sha256_strong",
        "kind": "protocol",
        "title": "MD5 is broken; SHA-256 is strong — hash strength is time-stamped",
        "situation": "MD5 is classified as broken (practical collision attacks since 2004; chosen-prefix collisions in seconds on commodity hardware by 2009). SHA-256 is classified as strong under current NIST guidance. A hash function that was strong in 1992 (MD5) can be broken by 2009 — strength is a time-stamped property, not an eternal one.",
        "category": "cryptography",
        "domains": ["cryptography", "cybersecurity", "information_theory"],
        "axes": ["information_encoding", "authority_trust", "time_sequence"],
        "verdict": "CONCORDANT",
        "pre_run": {
            "summary": "Two parallel hash_strength checks: MD5 → broken (matches NIST deprecation), SHA-256 → strong (matches current NIST guidance).",
            "domain_results": [
                {
                    "domain": "cryptography",
                    "verdict": "CONFIRMED",
                    "detail": "hash_strength_algorithm=md5 → 'broken' (matches claim)",
                    "data": {"hash_strength_algorithm": "md5", "claimed_hash_strength": "broken"},
                },
                {
                    "domain": "cryptography",
                    "verdict": "CONFIRMED",
                    "detail": "hash_strength_algorithm=sha256 → 'strong' (matches claim)",
                    "data": {"hash_strength_algorithm": "sha256", "claimed_hash_strength": "strong"},
                },
            ],
            "axis_overlaps": [
                {
                    "axis": "time_sequence",
                    "with": ["genetics", "scripture"],
                    "note": "Strength decays. The same axis that records DNA mutation rates and Scripture transmission history records cryptographic strength erosion. What is verifiable today may need re-verification tomorrow.",
                }
            ],
        },
        "wisdom": "Hash strength is a snapshot, not a constant. MD5 was strong, then weak, then broken — over fifteen years, as factoring and collision-search techniques improved. SHA-256 stands today because no one has published a practical attack. The Shepherd treats hash strength like the engine treats almanac verdicts — labelled with a time-stamp, subject to OBSOLETE when reality moves on. Trusting MD5 in 2026 is the same kind of error as trusting a verifier output without checking when it was computed.",
        "triggers": {
            "keywords": ["MD5", "SHA-256", "hash strength", "broken hash", "NIST deprecation", "collision attack"],
            "axes": ["information_encoding", "authority_trust", "time_sequence"],
        },
    },
]


def main() -> int:
    if not ALMANAC.exists():
        print(f"ERROR: almanac file not found at {ALMANAC}")
        return 1

    # Read existing IDs to guard against accidental re-runs.
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

    to_write = [e for e in ENTRIES if e["id"] not in existing_ids]
    skipped = [e["id"] for e in ENTRIES if e["id"] in existing_ids]
    if skipped:
        print(f"skipping (already present): {skipped}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(f"  + {e['id']:50s}  {e['verdict']}")

    print(f"\n-- appended {len(to_write)} entries to {ALMANAC.name}")
    print("   restart the API server so the almanac re-reads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
