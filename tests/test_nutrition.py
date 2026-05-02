"""Tests for the nutrition verifier (biology umbrella)."""
from __future__ import annotations

from concordance_engine.verifiers import nutrition as nut


# ── macronutrient calories ─────────────────────────────────────────────

def test_macro_calories_pure_carb():
    # 50g carb at 4 kcal/g = 200 kcal
    r = nut.verify_macronutrient_calories({
        "calories_claimed": 200, "carb_g": 50,
    })
    assert r.status == "CONFIRMED"


def test_macro_calories_full_meal():
    # 50g C + 30g P + 20g F = 200 + 120 + 180 = 500 kcal
    r = nut.verify_macronutrient_calories({
        "calories_claimed": 500, "carb_g": 50, "protein_g": 30, "fat_g": 20,
    })
    assert r.status == "CONFIRMED"


def test_macro_calories_with_alcohol():
    # 0g C + 0g P + 0g F + 14g alcohol = 98 kcal
    r = nut.verify_macronutrient_calories({
        "calories_claimed": 98, "alcohol_g": 14,
    })
    assert r.status == "CONFIRMED"


def test_macro_calories_wrong_claim():
    r = nut.verify_macronutrient_calories({
        "calories_claimed": 1000, "carb_g": 50, "protein_g": 30, "fat_g": 20,
    })
    assert r.status == "MISMATCH"


def test_macro_calories_negative_grams_is_error():
    r = nut.verify_macronutrient_calories({
        "calories_claimed": 100, "carb_g": -10,
    })
    assert r.status == "ERROR"


# ── RDA compliance ─────────────────────────────────────────────────────

def test_rda_vitamin_c_adult_male_sufficient():
    # adult male RDA = 90mg/day
    r = nut.verify_rda_compliance({
        "nutrient": "vitamin_c", "intake_mg": 100,
        "age_sex_group": "adult_male", "claimed_status": "sufficient",
    })
    assert r.status == "CONFIRMED"


def test_rda_vitamin_c_adult_male_deficient():
    r = nut.verify_rda_compliance({
        "nutrient": "vitamin_c", "intake_mg": 30,
        "age_sex_group": "adult_male", "claimed_status": "deficient",
    })
    assert r.status == "CONFIRMED"


def test_rda_iron_pregnant_high_requirement():
    # pregnant RDA for iron = 27mg/day; intake of 20 is deficient.
    r = nut.verify_rda_compliance({
        "nutrient": "iron", "intake_mg": 20,
        "age_sex_group": "pregnant", "claimed_status": "deficient",
    })
    assert r.status == "CONFIRMED"


def test_rda_wrong_status_claim():
    r = nut.verify_rda_compliance({
        "nutrient": "vitamin_c", "intake_mg": 30,
        "age_sex_group": "adult_male", "claimed_status": "sufficient",
    })
    assert r.status == "MISMATCH"


def test_rda_unknown_nutrient_is_na():
    r = nut.verify_rda_compliance({
        "nutrient": "vitamin_unobtainium", "intake_mg": 100,
        "age_sex_group": "adult_male", "claimed_status": "sufficient",
    })
    assert r.status == "NOT_APPLICABLE"


def test_rda_unknown_group_is_na():
    r = nut.verify_rda_compliance({
        "nutrient": "vitamin_c", "intake_mg": 100,
        "age_sex_group": "alien", "claimed_status": "sufficient",
    })
    assert r.status == "NOT_APPLICABLE"


# ── energy balance ─────────────────────────────────────────────────────

def test_energy_balance_deficit():
    r = nut.verify_energy_balance({
        "intake_kcal": 1500, "expenditure_kcal": 2000,
        "claimed_balance_kcal": -500,
    })
    assert r.status == "CONFIRMED"


def test_energy_balance_surplus():
    r = nut.verify_energy_balance({
        "intake_kcal": 2500, "expenditure_kcal": 2000,
        "claimed_balance_kcal": 500,
    })
    assert r.status == "CONFIRMED"


def test_energy_balance_wrong_claim():
    r = nut.verify_energy_balance({
        "intake_kcal": 1500, "expenditure_kcal": 2000,
        "claimed_balance_kcal": 0,
    })
    assert r.status == "MISMATCH"


def test_energy_balance_negative_intake_is_error():
    r = nut.verify_energy_balance({
        "intake_kcal": -100, "expenditure_kcal": 2000,
        "claimed_balance_kcal": -2100,
    })
    assert r.status == "ERROR"


# ── BMI classification ─────────────────────────────────────────────────

def test_bmi_normal():
    # 70kg / 1.75² = 22.86 → normal
    r = nut.verify_bmi_classification({
        "weight_kg": 70, "height_m": 1.75, "claimed_bmi_class": "normal",
    })
    assert r.status == "CONFIRMED"


def test_bmi_underweight():
    # 50kg / 1.70² = 17.30 → underweight
    r = nut.verify_bmi_classification({
        "weight_kg": 50, "height_m": 1.70, "claimed_bmi_class": "underweight",
    })
    assert r.status == "CONFIRMED"


def test_bmi_obese():
    # 100kg / 1.70² = 34.6 → obese
    r = nut.verify_bmi_classification({
        "weight_kg": 100, "height_m": 1.70, "claimed_bmi_class": "obese",
    })
    assert r.status == "CONFIRMED"


def test_bmi_wrong_class():
    r = nut.verify_bmi_classification({
        "weight_kg": 70, "height_m": 1.75, "claimed_bmi_class": "obese",
    })
    assert r.status == "MISMATCH"


def test_bmi_zero_height_error():
    r = nut.verify_bmi_classification({
        "weight_kg": 70, "height_m": 0, "claimed_bmi_class": "normal",
    })
    assert r.status == "ERROR"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = nut.run({"domain": "nutrition"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "nutrition",
        "NUT_VERIFY": {
            "calories_claimed": 500, "carb_g": 50, "protein_g": 30, "fat_g": 20,
            "nutrient": "vitamin_c", "intake_mg": 100,
            "age_sex_group": "adult_male", "claimed_status": "sufficient",
            "intake_kcal": 1500, "expenditure_kcal": 2000,
            "claimed_balance_kcal": -500,
            "weight_kg": 70, "height_m": 1.75, "claimed_bmi_class": "normal",
        },
    }
    results = nut.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 4, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_nutrition_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "nutrition",
        "NUT_VERIFY": {
            "weight_kg": 70, "height_m": 1.75, "claimed_bmi_class": "normal",
        },
    }
    results = run_for_domain("nutrition", packet)
    nut_results = [r for r in results if r.name.startswith("nutrition.")]
    assert len(nut_results) == 1
    assert nut_results[0].status == "CONFIRMED"
