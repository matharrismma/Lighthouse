"""Tests for the genetics verifier (standard genetic code, base pairing,
ORF bounds, GC content, codon translation).
"""
from __future__ import annotations

from concordance_engine.verifiers import genetics as gen


# ── complementarity ────────────────────────────────────────────────────

def test_dna_complement_basic():
    r = gen.verify_complementarity({"sequence": "ATCG", "claimed_complement": "TAGC"})
    assert r.status == "CONFIRMED"


def test_dna_complement_wrong():
    r = gen.verify_complementarity({"sequence": "ATCG", "claimed_complement": "TAGT"})
    assert r.status == "MISMATCH"


def test_dna_complement_length_mismatch():
    r = gen.verify_complementarity({"sequence": "ATCG", "claimed_complement": "TAG"})
    assert r.status == "MISMATCH"
    assert "length" in r.detail.lower()


def test_dna_complement_invalid_chars_is_error():
    r = gen.verify_complementarity({"sequence": "ATXG", "claimed_complement": "TAGC"})
    assert r.status == "ERROR"


def test_rna_complement():
    r = gen.verify_complementarity({
        "sequence": "AUCG", "claimed_complement": "UAGC", "rna": True,
    })
    assert r.status == "CONFIRMED"


# ── reverse complement ─────────────────────────────────────────────────

def test_reverse_complement_basic():
    # ATCG → complement TAGC → reverse CGAT
    r = gen.verify_reverse_complement({
        "sequence": "ATCG", "claimed_reverse_complement": "CGAT",
    })
    assert r.status == "CONFIRMED"


def test_reverse_complement_wrong():
    r = gen.verify_reverse_complement({
        "sequence": "ATCG", "claimed_reverse_complement": "TAGC",  # plain complement, not reversed
    })
    assert r.status == "MISMATCH"


# ── GC content ─────────────────────────────────────────────────────────

def test_gc_content_exact():
    # GCGC has GC fraction 1.0
    r = gen.verify_gc_content({"sequence": "GCGC", "claimed_gc_fraction": 1.0})
    assert r.status == "CONFIRMED"


def test_gc_content_half():
    # ATGC has GC fraction 0.5
    r = gen.verify_gc_content({"sequence": "ATGC", "claimed_gc_fraction": 0.5})
    assert r.status == "CONFIRMED"


def test_gc_content_wrong_claim():
    r = gen.verify_gc_content({"sequence": "ATGC", "claimed_gc_fraction": 0.75})
    assert r.status == "MISMATCH"


def test_gc_content_out_of_range():
    r = gen.verify_gc_content({"sequence": "ATGC", "claimed_gc_fraction": 1.5})
    assert r.status == "MISMATCH"
    assert "[0, 1]" in r.detail


# ── codon translation (full sequence) ──────────────────────────────────

def test_codon_translation_known_protein():
    # ATG=M, GCC=A, AAA=K, TAA=stop
    r = gen.verify_codon_translation({
        "sequence": "ATGGCCAAATAA",
        "claimed_protein": "MAK*",
    })
    assert r.status == "CONFIRMED"


def test_codon_translation_wrong_protein():
    r = gen.verify_codon_translation({
        "sequence": "ATGGCCAAATAA",
        "claimed_protein": "MEH*",
    })
    assert r.status == "MISMATCH"


def test_codon_translation_non_multiple_of_3_is_error():
    r = gen.verify_codon_translation({
        "sequence": "ATGGCCAA",  # 8 bases
        "claimed_protein": "MA",
    })
    assert r.status == "ERROR"


def test_codon_translation_rna_input():
    r = gen.verify_codon_translation({
        "sequence": "AUGGCCAAAUAA",
        "claimed_protein": "MAK*",
        "rna": True,
    })
    assert r.status == "CONFIRMED"


# ── single codon → amino acid ──────────────────────────────────────────

def test_codon_amino_acid_known():
    r = gen.verify_codon_amino_acid({"codon": "ATG", "claimed_amino_acid": "M"})
    assert r.status == "CONFIRMED"


def test_codon_amino_acid_stop_word():
    r = gen.verify_codon_amino_acid({"codon": "TAA", "claimed_amino_acid": "stop"})
    assert r.status == "CONFIRMED"


def test_codon_amino_acid_stop_star():
    r = gen.verify_codon_amino_acid({"codon": "TAG", "claimed_amino_acid": "*"})
    assert r.status == "CONFIRMED"


def test_codon_amino_acid_wrong_letter():
    r = gen.verify_codon_amino_acid({"codon": "ATG", "claimed_amino_acid": "K"})
    assert r.status == "MISMATCH"


def test_codon_amino_acid_invalid_codon_length():
    r = gen.verify_codon_amino_acid({"codon": "AT", "claimed_amino_acid": "M"})
    assert r.status == "ERROR"


# ── ORF bounds ─────────────────────────────────────────────────────────

def test_orf_bounds_valid_open_reading_frame():
    # ATG GCC AAA TAA: bases 0..12, ATG start + TAA stop
    r = gen.verify_orf_bounds({
        "sequence": "ATGGCCAAATAA",
        "claimed_orf": {"start": 0, "end": 12},
    })
    assert r.status == "CONFIRMED"


def test_orf_bounds_no_start_codon_mismatches():
    r = gen.verify_orf_bounds({
        "sequence": "GCCGCCAAATAA",  # starts with GCC not ATG
        "claimed_orf": {"start": 0, "end": 12},
    })
    assert r.status == "MISMATCH"
    assert "start codon" in r.detail


def test_orf_bounds_no_stop_codon_mismatches():
    r = gen.verify_orf_bounds({
        "sequence": "ATGGCCAAACCC",  # ends with CCC (Pro), not stop
        "claimed_orf": {"start": 0, "end": 12},
    })
    assert r.status == "MISMATCH"
    assert "stop codon" in r.detail.lower()


def test_orf_bounds_length_not_multiple_of_3():
    r = gen.verify_orf_bounds({
        "sequence": "ATGGCCAAATAACGT",
        "claimed_orf": {"start": 0, "end": 13},  # 13 not divisible by 3
    })
    assert r.status == "MISMATCH"


def test_orf_bounds_out_of_range():
    r = gen.verify_orf_bounds({
        "sequence": "ATGGCCAAATAA",
        "claimed_orf": {"start": 0, "end": 99},
    })
    assert r.status == "MISMATCH"
    assert "out of bounds" in r.detail


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = gen.run({"domain": "genetics"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "genetics",
        "GENETICS_VERIFY": {
            "sequence": "ATGGCCAAATAA",
            "claimed_complement": "TACCGGTTTATT",
            "claimed_reverse_complement": "TTATTTGGCCAT",
            "claimed_gc_fraction": 4/12,  # ATGGCCAAATAA has G+G+C+C = 4 of 12
            "claimed_protein": "MAK*",
            "codon": "ATG",
            "claimed_amino_acid": "M",
            "claimed_orf": {"start": 0, "end": 12},
        },
    }
    results = gen.run(packet)
    statuses = [(r.name, r.status) for r in results]
    # 6 checks dispatched
    assert len(results) == 6, statuses
    confirmed = [s for (_, s) in statuses if s == "CONFIRMED"]
    assert len(confirmed) == 6, statuses


def test_engine_dispatches_genetics_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "genetics",
        "GENETICS_VERIFY": {"codon": "ATG", "claimed_amino_acid": "M"},
    }
    results = run_for_domain("genetics", packet)
    gen_results = [r for r in results if r.name.startswith("genetics.")]
    assert len(gen_results) == 1
    assert gen_results[0].status == "CONFIRMED"
