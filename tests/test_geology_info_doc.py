"""Tests for geology, information_theory, document_validation verifiers."""
from __future__ import annotations

from concordance_engine.verifiers import (
    geology as geo,
    information_theory as info,
    document_validation as doc,
)


# ── Geology: radiometric decay ─────────────────────────────────────────

def test_decay_one_half_life():
    # 1 half-life → 0.5 remaining
    r = geo.verify_radiometric_decay({
        "isotope_half_life_years": 5730, "elapsed_years": 5730,
        "initial_amount": 1.0, "claimed_remaining_amount": 0.5,
    })
    assert r.status == "CONFIRMED"


def test_decay_two_half_lives():
    r = geo.verify_radiometric_decay({
        "isotope_half_life_years": 5730, "elapsed_years": 11460,
        "initial_amount": 1.0, "claimed_remaining_amount": 0.25,
    })
    assert r.status == "CONFIRMED"


def test_decay_zero_time_full_amount():
    r = geo.verify_radiometric_decay({
        "isotope_half_life_years": 5730, "elapsed_years": 0,
        "initial_amount": 100.0, "claimed_remaining_amount": 100.0,
    })
    assert r.status == "CONFIRMED"


def test_decay_wrong_claim():
    r = geo.verify_radiometric_decay({
        "isotope_half_life_years": 5730, "elapsed_years": 5730,
        "initial_amount": 1.0, "claimed_remaining_amount": 1.0,
    })
    assert r.status == "MISMATCH"


# ── Geology: Mohs ──────────────────────────────────────────────────────

def test_mohs_quartz_scratches_calcite():
    # Quartz=7, Calcite=3 → quartz scratches calcite
    r = geo.verify_mohs_scratch({
        "harder_mineral_mohs": 7, "softer_mineral_mohs": 3,
        "claimed_can_scratch": True,
    })
    assert r.status == "CONFIRMED"


def test_mohs_diamond_scratches_anything():
    r = geo.verify_mohs_scratch({
        "harder_mineral_mohs": 10, "softer_mineral_mohs": 9,
        "claimed_can_scratch": True,
    })
    assert r.status == "CONFIRMED"


def test_mohs_equal_hardness_cannot_scratch():
    r = geo.verify_mohs_scratch({
        "harder_mineral_mohs": 7, "softer_mineral_mohs": 7,
        "claimed_can_scratch": False,
    })
    assert r.status == "CONFIRMED"


def test_mohs_softer_cannot_scratch_harder():
    r = geo.verify_mohs_scratch({
        "harder_mineral_mohs": 3, "softer_mineral_mohs": 7,
        "claimed_can_scratch": True,  # wrong
    })
    assert r.status == "MISMATCH"


# ── Geology: Richter ───────────────────────────────────────────────────

def test_richter_2_magnitude_diff_100x():
    r = geo.verify_richter_amplitude({
        "richter_M1": 5.0, "richter_M2": 7.0,
        "claimed_amplitude_ratio": 100.0,
    })
    assert r.status == "CONFIRMED"


def test_richter_1_magnitude_diff_10x():
    r = geo.verify_richter_amplitude({
        "richter_M1": 4.5, "richter_M2": 5.5,
        "claimed_amplitude_ratio": 10.0,
    })
    assert r.status == "CONFIRMED"


def test_richter_wrong_claim():
    r = geo.verify_richter_amplitude({
        "richter_M1": 5.0, "richter_M2": 7.0,
        "claimed_amplitude_ratio": 2.0,
    })
    assert r.status == "MISMATCH"


# ── Information theory: entropy ────────────────────────────────────────

def test_entropy_fair_coin_1_bit():
    r = info.verify_shannon_entropy({
        "probabilities": [0.5, 0.5], "claimed_entropy_bits": 1.0,
    })
    assert r.status == "CONFIRMED"


def test_entropy_certain_outcome_zero():
    r = info.verify_shannon_entropy({
        "probabilities": [1.0, 0.0, 0.0], "claimed_entropy_bits": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_entropy_uniform_4_outcomes_2_bits():
    r = info.verify_shannon_entropy({
        "probabilities": [0.25, 0.25, 0.25, 0.25],
        "claimed_entropy_bits": 2.0,
    })
    assert r.status == "CONFIRMED"


def test_entropy_doesnt_sum_to_1_error():
    r = info.verify_shannon_entropy({
        "probabilities": [0.5, 0.3], "claimed_entropy_bits": 1.0,
    })
    assert r.status == "ERROR"


# ── Information theory: BSC capacity ───────────────────────────────────

def test_bsc_perfect_channel():
    # p=0 → C=1
    r = info.verify_bsc_capacity({
        "bsc_error_rate": 0.0, "claimed_capacity_bits": 1.0,
    })
    assert r.status == "CONFIRMED"


def test_bsc_useless_channel_p_half():
    # p=0.5 → C=0 (no information)
    r = info.verify_bsc_capacity({
        "bsc_error_rate": 0.5, "claimed_capacity_bits": 0.0,
    })
    assert r.status == "CONFIRMED"


def test_bsc_p_0_1_capacity():
    # p=0.1 → C = 1 - H₂(0.1) ≈ 0.531
    r = info.verify_bsc_capacity({
        "bsc_error_rate": 0.1, "claimed_capacity_bits": 0.531,
    })
    assert r.status == "CONFIRMED"


# ── Information theory: Hamming distance ───────────────────────────────

def test_hamming_three_diff():
    # 10101010 vs 10100100: positions 4,5,6 differ (3 differences)
    r = info.verify_hamming_distance({
        "string_a": "10101010", "string_b": "10100100", "claimed_hamming": 3,
    })
    assert r.status == "CONFIRMED"


def test_hamming_zero_identical():
    r = info.verify_hamming_distance({
        "string_a": "abc", "string_b": "abc", "claimed_hamming": 0,
    })
    assert r.status == "CONFIRMED"


def test_hamming_unequal_length_error():
    r = info.verify_hamming_distance({
        "string_a": "abc", "string_b": "abcd", "claimed_hamming": 1,
    })
    assert r.status == "ERROR"


def test_hamming_wrong_claim():
    r = info.verify_hamming_distance({
        "string_a": "10101010", "string_b": "10100100", "claimed_hamming": 5,
    })
    assert r.status == "MISMATCH"


# ── Document validation: ISBN-10 ───────────────────────────────────────

def test_isbn10_valid():
    # Real ISBN-10: 0-306-40615-2
    r = doc.verify_isbn10({
        "isbn10": "0306406152", "claimed_isbn10_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_isbn10_with_x_check_digit():
    # 0-201-61622-X is a valid ISBN-10 (Bjarne Stroustrup's "The Design and
    # Evolution of C++"). Mod-11 check passes.
    r = doc.verify_isbn10({
        "isbn10": "020161622X", "claimed_isbn10_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_isbn10_bogus_invalid():
    # 1234567890 fails mod-11 (sum = 210, 210 mod 11 = 1)
    r = doc.verify_isbn10({
        "isbn10": "1234567890", "claimed_isbn10_valid": False,
    })
    assert r.status == "CONFIRMED"


def test_isbn10_wrong_claim():
    # 1234567890 is invalid; claim 'valid' should mismatch.
    r = doc.verify_isbn10({
        "isbn10": "1234567890", "claimed_isbn10_valid": True,
    })
    assert r.status == "MISMATCH"


# ── Document validation: ISBN-13 ───────────────────────────────────────

def test_isbn13_valid():
    # ISBN-13 of '0-306-40615-2' is 978-0-306-40615-7
    r = doc.verify_isbn13({
        "isbn13": "9780306406157", "claimed_isbn13_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_isbn13_invalid():
    r = doc.verify_isbn13({
        "isbn13": "9780306406150", "claimed_isbn13_valid": False,
    })
    assert r.status == "CONFIRMED"


# ── Document validation: Luhn ──────────────────────────────────────────

def test_luhn_test_visa():
    # Standard test Visa from public test suites
    r = doc.verify_luhn({
        "luhn_number": "4532015112830366", "claimed_luhn_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_luhn_invalid_number():
    r = doc.verify_luhn({
        "luhn_number": "4532015112830367", "claimed_luhn_valid": False,
    })
    assert r.status == "CONFIRMED"


def test_luhn_with_dashes_accepted():
    r = doc.verify_luhn({
        "luhn_number": "4532-0151-1283-0366", "claimed_luhn_valid": True,
    })
    assert r.status == "CONFIRMED"


# ── Document validation: EAN/UPC ───────────────────────────────────────

def test_ean_upc_a_valid():
    # UPC-A 036000291452 is a published valid example
    r = doc.verify_ean_upc({
        "ean_or_upc": "036000291452", "claimed_ean_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_ean_invalid():
    r = doc.verify_ean_upc({
        "ean_or_upc": "036000291453", "claimed_ean_valid": False,
    })
    assert r.status == "CONFIRMED"


# ── run dispatch ───────────────────────────────────────────────────────

def test_geo_run_dispatches_all():
    packet = {
        "domain": "geology",
        "GEO_VERIFY": {
            "isotope_half_life_years": 5730, "elapsed_years": 5730,
            "initial_amount": 1.0, "claimed_remaining_amount": 0.5,
            "harder_mineral_mohs": 7, "softer_mineral_mohs": 3,
            "claimed_can_scratch": True,
            "richter_M1": 5.0, "richter_M2": 7.0,
            "claimed_amplitude_ratio": 100.0,
        },
    }
    results = geo.run(packet)
    assert len(results) == 3
    assert all(r.status == "CONFIRMED" for r in results)


def test_info_run_dispatches_all():
    packet = {
        "domain": "information_theory",
        "INFO_VERIFY": {
            "probabilities": [0.5, 0.5], "claimed_entropy_bits": 1.0,
            "bsc_error_rate": 0.0, "claimed_capacity_bits": 1.0,
            "string_a": "abc", "string_b": "abc", "claimed_hamming": 0,
        },
    }
    results = info.run(packet)
    assert len(results) == 3
    assert all(r.status == "CONFIRMED" for r in results)


def test_doc_run_dispatches_all():
    packet = {
        "domain": "document_validation",
        "DOC_VERIFY": {
            "isbn10": "0306406152", "claimed_isbn10_valid": True,
            "isbn13": "9780306406157", "claimed_isbn13_valid": True,
            "luhn_number": "4532015112830366", "claimed_luhn_valid": True,
            "ean_or_upc": "036000291452", "claimed_ean_valid": True,
        },
    }
    results = doc.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)
