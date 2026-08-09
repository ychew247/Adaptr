import pytest

from src.m8_nutrition_targets import NutritionCalculationError, calculate_nutrition_targets


def test_fat_loss_targets_apply_formula_and_male_safety_floor():
    result = calculate_nutrition_targets(
        profile={
            "age": 25,
            "height_cm": 175,
            "starting_weight_kg": 72,
            "bmr_formula_profile": "male",
            "weekly_availability": "4 days/week",
        },
        goal={"goal_type": "fat_loss", "goal_details": {}},
        active_plan=None,
        readiness_band="train_as_planned",
        workout_today=False,
    )

    assert result["bmr"] == 1693.75
    assert result["activity_factor"] == 1.55
    assert result["calories_min"] == 2101
    assert result["calories_max"] == 2232
    assert result["protein_g"] == 158
    assert result["protein_range_g"] == [144, 173]
    assert result["hydration_l"] == 2.38
    assert result["fiber_g"] == 30


def test_high_intensity_workout_adds_calories_and_hydration():
    base = calculate_nutrition_targets(
        profile={
            "age": 30,
            "height_cm": 160,
            "starting_weight_kg": 60,
            "bmr_formula_profile": "female",
            "weekly_availability": "2 days/week",
        },
        goal={"goal_type": "muscle_gain", "goal_details": {}},
        active_plan=None,
        readiness_band="train_as_planned",
        workout_today=False,
    )
    result = calculate_nutrition_targets(
        profile={
            "age": 30,
            "height_cm": 160,
            "starting_weight_kg": 60,
            "bmr_formula_profile": "female",
            "weekly_availability": "2 days/week",
        },
        goal={"goal_type": "muscle_gain", "goal_details": {}},
        active_plan={"intensity_band": "high", "plan_json": {"days": [{}, {}]}},
        readiness_band="train_as_planned",
        workout_today=True,
    )

    assert result["calories_min"] == base["calories_min"] + 100
    assert result["calories_max"] == base["calories_max"] + 150
    assert result["hydration_l"] == round(base["hydration_l"] + 0.9, 2)
    assert result["workout_today"] is True


def test_recovery_does_not_cut_calories():
    standard = calculate_nutrition_targets(
        profile={
            "age": 24,
            "height_cm": 170,
            "starting_weight_kg": 50,
            "bmr_formula_profile": "female",
            "weekly_availability": "0 days/week",
        },
        goal={"goal_type": "maintenance", "goal_details": {}},
        active_plan=None,
        readiness_band="train_as_planned",
        workout_today=False,
    )
    recovery = calculate_nutrition_targets(
        profile={
            "age": 24,
            "height_cm": 170,
            "starting_weight_kg": 50,
            "bmr_formula_profile": "female",
            "weekly_availability": "0 days/week",
        },
        goal={"goal_type": "maintenance", "goal_details": {}},
        active_plan=None,
        readiness_band="recovery",
        workout_today=False,
    )

    assert recovery["calories_min"] == standard["calories_min"]
    assert recovery["calories_max"] == standard["calories_max"]


def test_missing_formula_profile_is_rejected_instead_of_guessed():
    with pytest.raises(NutritionCalculationError, match="BMR formula profile"):
        calculate_nutrition_targets(
            profile={"age": 25, "height_cm": 175, "starting_weight_kg": 72},
            goal={"goal_type": "fat_loss", "goal_details": {}},
            active_plan=None,
            readiness_band="train_as_planned",
            workout_today=False,
        )


def test_activity_factor_accepts_saved_short_form_availability():
    result = calculate_nutrition_targets(
        profile={
            "age": 21,
            "height_cm": 175,
            "starting_weight_kg": 64,
            "bmr_formula_profile": "male",
            "weekly_availability": "4days",
        },
        goal={"goal_type": "maintenance", "goal_details": {}},
        active_plan=None,
        readiness_band="train_as_planned",
        workout_today=False,
    )

    assert result["weekly_sessions"] == 4
    assert result["activity_factor"] == 1.55
