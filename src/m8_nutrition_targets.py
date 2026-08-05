"""Deterministic nutrition-target calculations for Module 8."""

from __future__ import annotations

import math
import re
from typing import Any


class NutritionCalculationError(ValueError):
    """Raised when stored data cannot safely support a nutrition calculation."""


ACTIVITY_FACTORS = (
    (0, 1.2),
    (3, 1.375),
    (5, 1.55),
    (7, 1.725),
)


def calculate_nutrition_targets(
    profile: dict[str, Any],
    goal: dict[str, Any],
    active_plan: dict[str, Any] | None,
    readiness_band: str | None,
    workout_today: bool,
) -> dict[str, Any]:
    """Return validated targets; no LLM output participates in this calculation."""
    age = _positive_number(profile, "age")
    height_cm = _positive_number(profile, "height_cm")
    weight_kg = _positive_number(profile, "starting_weight_kg")
    formula_profile = _formula_profile(profile)

    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    bmr += 5 if formula_profile == "male" else -161

    sessions = _weekly_session_count(active_plan, profile.get("weekly_availability", ""))
    activity_factor = _activity_factor(sessions)
    tdee = bmr * activity_factor
    nutrition_goal = _nutrition_goal(goal)
    calorie_low, calorie_high = _calorie_multiplier_range(nutrition_goal)
    calories_min = tdee * calorie_low
    calories_max = tdee * calorie_high

    planned_intensity = (active_plan or {}).get("intensity_band", "").lower()
    if workout_today and planned_intensity == "high":
        calories_min += 100
        calories_max += 150

    safety_floor = 1500 if formula_profile == "male" else 1200
    calories_min = max(math.ceil(calories_min), safety_floor)
    calories_max = max(math.ceil(calories_max), calories_min)

    protein_low, protein_high = (
        (2.0, 2.4) if nutrition_goal == "fat_loss" else (1.4, 2.0)
    )
    protein_g = round(weight_kg * ((protein_low + protein_high) / 2))
    hydration_l = weight_kg * 0.033 + (0.5 if workout_today else 0)
    if workout_today and planned_intensity == "high":
        hydration_l += 0.4

    result = {
        "bmr": round(bmr, 2),
        "tdee": round(tdee, 2),
        "activity_factor": activity_factor,
        "weekly_sessions": sessions,
        "nutrition_goal": nutrition_goal,
        "calories_min": calories_min,
        "calories_max": calories_max,
        "protein_g": protein_g,
        "protein_range_g": [math.ceil(weight_kg * protein_low), math.ceil(weight_kg * protein_high)],
        "hydration_l": round(hydration_l, 2),
        "fiber_g": 30 if formula_profile == "male" else 25,
        "bmr_formula_profile": formula_profile,
        "readiness_band": readiness_band,
        "planned_intensity": planned_intensity or "not_planned",
    }
    validate_nutrition_targets(result)
    return result


def validate_nutrition_targets(targets: dict[str, Any]) -> None:
    """Enforce the deterministic safety limits before a target is stored or shown."""
    formula_profile = targets.get("bmr_formula_profile")
    if formula_profile not in {"male", "female"}:
        raise NutritionCalculationError("BMR formula profile must be male or female")
    floor = 1500 if formula_profile == "male" else 1200
    if targets["calories_min"] < floor:
        raise NutritionCalculationError("calories_min is below the safety floor")
    if targets["calories_max"] < targets["calories_min"]:
        raise NutritionCalculationError("calories_max must be at least calories_min")
    for key in ("protein_g", "hydration_l", "fiber_g"):
        if targets[key] <= 0:
            raise NutritionCalculationError(f"{key} must be positive")


def _formula_profile(profile: dict[str, Any]) -> str:
    value = str(profile.get("bmr_formula_profile") or "").strip().lower()
    if value not in {"male", "female"}:
        raise NutritionCalculationError(
            "BMR formula profile is required. Store either 'male' or 'female'; do not guess."
        )
    return value


def _positive_number(profile: dict[str, Any], key: str) -> float:
    try:
        value = float(profile[key])
    except (KeyError, TypeError, ValueError) as error:
        raise NutritionCalculationError(f"{key} is required for nutrition targets") from error
    if value <= 0:
        raise NutritionCalculationError(f"{key} must be positive")
    return value


def _weekly_session_count(active_plan: dict[str, Any] | None, weekly_availability: str) -> int:
    if active_plan:
        days = (active_plan.get("plan_json") or {}).get("days")
        if isinstance(days, list) and days:
            return min(len(days), 7)
    match = re.search(r"\b([0-7])\s*(?:days?|sessions?)\b", weekly_availability.lower())
    return int(match.group(1)) if match else 0


def _activity_factor(sessions: int) -> float:
    for maximum, factor in ACTIVITY_FACTORS:
        if sessions <= maximum:
            return factor
    return 1.725


def _nutrition_goal(goal: dict[str, Any]) -> str:
    goal_type = str(goal.get("goal_type") or "").lower()
    if goal_type in {"fat_loss", "muscle_gain"}:
        return goal_type
    return "maintenance"


def _calorie_multiplier_range(goal: str) -> tuple[float, float]:
    if goal == "fat_loss":
        return 0.80, 0.85
    if goal == "muscle_gain":
        return 1.05, 1.15
    return 1.0, 1.0
