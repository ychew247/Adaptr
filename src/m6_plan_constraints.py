"""Deterministic limits that bound Module 6 workout-plan generation."""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping

from src.m5_readiness_score import has_hard_pain_flag

LOGGER = logging.getLogger(__name__)

_PAIN_WORDS = ("sharp", "worsening", "severe", "persistent")
_RECOVERY_EXERCISES = [
    "mobility breathing reset",
    "easy walk",
    "pain-free range of motion",
    "gentle mobility flow",
]
_EXERCISE_CATALOG = {
    "dumbbell row": "dumbbells",
    "dumbbell squat": "dumbbells",
    "goblet squat": "dumbbells",
    "treadmill walk": "treadmill",
    "treadmill intervals": "treadmill",
    "bike intervals": "stationary bike",
    "landmine press": "full gym",
    "chest-supported row": "full gym",
    "cable face pull": "full gym",
    "lat pulldown": "full gym",
    "barbell squat": "barbell",
    "romanian deadlift": "barbell",
    "medicine ball slam": "medicine ball",
    "badminton footwork intervals": "bodyweight",
    "lateral shuffle": "bodyweight",
    "split-step reaction drill": "bodyweight",
    "single-leg balance": "bodyweight",
    "plank": "bodyweight",
    "dead bug": "bodyweight",
    "mobility flow": "bodyweight",
    "easy walk": "bodyweight",
}
_INJURY_EXCLUSIONS = {
    "shoulder": ["overhead press", "shoulder press", "upright row", "heavy pressing"],
    "wrist": ["push-up", "burpee", "plank", "heavy pressing"],
    "knee": ["jump", "sprint", "deep squat", "lunge"],
    "hamstring": ["romanian deadlift", "deadlift", "sprint", "hamstring curl"],
    "back": ["deadlift", "barbell squat", "good morning"],
}
_BAND_LIMITS = {
    "train_as_planned": ("normal", 18, 1.0),
    "reduce_volume": ("reduced", 12, 0.8),
    "lighter_session": ("light", 8, 0.6),
    "recovery_day": ("recovery", 4, 0.4),
}
_SPORT_TERMS = (
    "basketball",
    "badminton",
    "futsal",
    "football",
    "soccer",
    "running",
    "cycling",
    "swimming",
)


def derive_plan_constraints(
    profile: Mapping[str, Any],
    goal: Mapping[str, Any],
    readiness: Mapping[str, Any],
    latest_checkin: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return JSON-serializable constraints for a single generated plan."""
    latest_checkin = latest_checkin or {}
    pain_text = str(latest_checkin.get("pain_notes") or "").lower()
    safety_reason = _safety_reason(readiness, pain_text)
    safety_active = safety_reason is not None
    intensity_ceiling, set_ceiling, volume_modifier = _BAND_LIMITS.get(
        str(readiness.get("band") or "train_as_planned"),
        _BAND_LIMITS["train_as_planned"],
    )
    if safety_active:
        intensity_ceiling, set_ceiling, volume_modifier = _BAND_LIMITS["recovery_day"]

    equipment_access = [str(item).lower() for item in profile.get("equipment_access") or []]
    forbidden = _injury_exclusions(profile, pain_text)
    max_sessions = 1 if safety_active else _parse_training_days(profile.get("weekly_availability"))
    allowed_exercises = (
        list(_RECOVERY_EXERCISES)
        if safety_active
        else _allowed_exercises(equipment_access, forbidden)
    )
    goal_details = goal.get("goal_details") or {}
    constraints = {
        "safety_gate": {"active": safety_active, "reason": safety_reason or "No hard pain flag."},
        "equipment_access": equipment_access,
        "allowed_exercises": allowed_exercises,
        "forbidden_exercises": forbidden,
        "volume_ceiling_sets_per_session": set_ceiling,
        "volume_modifier": volume_modifier,
        "intensity_ceiling": intensity_ceiling,
        "intensity_range": _intensity_range(intensity_ceiling),
        "schedule": {
            "max_sessions": max_sessions,
            "weekly_availability": profile.get("weekly_availability") or "3 days/week",
        },
        "target_muscle_groups": goal_details.get("target_muscle_groups") or [],
        "target_sports": _target_sports(goal_details),
        "injury_notes": profile.get("injury_notes") or "",
        "medical_constraints": profile.get("medical_constraints") or "",
    }
    LOGGER.info(
        "Derived Module 6 constraints: safety=%s, intensity=%s, max_sessions=%s",
        safety_active,
        intensity_ceiling,
        max_sessions,
    )
    return constraints


def _safety_reason(readiness: Mapping[str, Any], pain_text: str) -> str | None:
    if readiness.get("safety_triggered"):
        return "Readiness safety gate was triggered."
    if has_hard_pain_flag(pain_text):
        return "Check-in contains a hard pain flag."
    return None


def _injury_exclusions(profile: Mapping[str, Any], pain_text: str) -> list[str]:
    health_text = " ".join(
        [
            str(profile.get("injury_notes") or "").lower(),
            str(profile.get("medical_constraints") or "").lower(),
            pain_text,
        ]
    )
    exclusions: list[str] = []
    for body_area, exercises in _INJURY_EXCLUSIONS.items():
        if body_area in health_text:
            exclusions.extend(exercises)
    return _unique(exclusions)


def _allowed_exercises(equipment_access: list[str], forbidden: list[str]) -> list[str]:
    allowed: list[str] = []
    for exercise, required_equipment in _EXERCISE_CATALOG.items():
        has_equipment = (
            required_equipment == "bodyweight"
            or "full gym" in equipment_access
            or required_equipment in equipment_access
        )
        if has_equipment and not any(blocked in exercise for blocked in forbidden):
            allowed.append(exercise)
    return [*_RECOVERY_EXERCISES, *allowed]


def _parse_training_days(availability: Any) -> int:
    match = re.search(r"\b(\d+)\s*(?:day|days)\b", str(availability or "").lower())
    if not match:
        return 3
    return max(1, min(6, int(match.group(1))))


def _intensity_range(ceiling: str) -> dict[str, str]:
    upper_bound = {
        "normal": "moderate-to-hard",
        "reduced": "moderate",
        "light": "easy-to-moderate",
        "recovery": "easy",
    }[ceiling]
    return {"minimum": "easy", "maximum": upper_bound}


def _target_sports(goal_details: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(goal_details.get("raw_goal_text") or ""),
            str(goal_details.get("athlete_type") or ""),
            " ".join(str(item) for item in goal_details.get("sport_specific_focus") or []),
        ]
    ).lower()
    return [sport for sport in _SPORT_TERMS if re.search(rf"\b{re.escape(sport)}\b", text)]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
