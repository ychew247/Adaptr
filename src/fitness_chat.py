"""Presentation helpers for the Streamlit fitness-agent chat."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping


TRAINING_EXPERIENCE_LEVEL_GUIDE = (
    "beginner = gym or sport experience up to 1 month, or you just started a specific sport; "
    "intermediate = trained consistently for 1-12 months; "
    "advanced = trained consistently for more than 12 months"
)

TRAINING_EXPERIENCE_PROMPT = f"your training experience: {TRAINING_EXPERIENCE_LEVEL_GUIDE}"


PROFILE_QUESTIONS = (
    ("age", "your age in years"),
    ("height_cm", "your height in centimetres"),
    ("starting_weight_kg", "your current weight in kilograms"),
    (
        "training_experience",
        TRAINING_EXPERIENCE_PROMPT,
    ),
    (
        "equipment_access",
        "the equipment you can use, listed with commas",
    ),
    (
        "weekly_availability",
        "how much time you can train each week, including days and minutes per session",
    ),
    ("injury_notes", "any injuries or pain to consider, or none if not applicable"),
    (
        "medical_constraints",
        "any medical constraints or clinician restrictions, or none if not applicable",
    ),
    (
        "diet_preferences",
        "any diet preferences or restrictions, or none if not applicable",
    ),
    (
        "activity_level",
        "your activity level outside training: sedentary, lightly active, moderately active, or very active",
    ),
    (
        "bmr_formula_profile",
        "the male or female BMR formula profile for nutrition calculations",
    ),
)


def profile_answers_to_queue(answers: Mapping[str, str]) -> list[str]:
    """Return answers in the exact order expected by StaticProfileService."""
    return [answers[key] for key, _prompt in PROFILE_QUESTIONS]


def is_plan_export_request(message: str) -> bool:
    normalized = message.lower()
    return (
        any(phrase in normalized for phrase in ("excel", "export"))
        or ("download" in normalized and any(word in normalized for word in ("plan", "workout", "training")))
    )


def plan_table_rows(plan: Mapping[str, Any]) -> list[dict[str, str]]:
    sessions = (plan.get("plan_json") or {}).get("sessions") or []
    return [
        {
            "Date": str(session.get("scheduled_date") or ""),
            "Day": str(session.get("day") or ""),
            "Focus": str(session.get("focus") or ""),
            "Exercises": "\n".join(str(exercise) for exercise in session.get("exercises") or []),
            "Sets/Reps": str(session.get("sets_reps") or ""),
            "Adjustment": str(session.get("adjustment") or ""),
        }
        for session in sessions
    ]


def format_daily_result(result: Mapping[str, Any]) -> str:
    readiness = result["readiness"]
    nutrition = result["nutrition"]
    score = round(float(readiness["readiness_score"]))
    band = str(readiness["band"])
    band_text = {
        "train_as_planned": "Train as planned today.",
        "reduce_volume": "Reduce volume today.",
        "lighter_session": "Keep today light.",
        "recovery_day": "Prioritize recovery today.",
    }.get(band, band.replace("_", " ").capitalize() + ".")
    note = str(nutrition.get("notes") or "").strip()

    return "\n\n".join(
        part
        for part in (
            f"Readiness: {score}/100 - {band_text}",
            "Nutrition: {calories:,} kcal, {protein} g protein, {hydration} L water, {fiber} g fiber.".format(
                calories=int(nutrition["calories_min"]),
                protein=int(nutrition["protein_g"]),
                hydration=_number_text(nutrition["hydration_l"]),
                fiber=int(nutrition["fiber_g"]),
            ),
            note,
        )
        if part
    )


def _number_text(value: Any) -> str:
    number = float(value) if isinstance(value, Decimal) else value
    return f"{number:g}"
