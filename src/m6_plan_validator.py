"""Deterministic hard validation and advisory scoring for Module 6 plans."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


_INTENSITY_RANK = {"recovery": 0, "light": 1, "reduced": 2, "normal": 3}
_EQUIPMENT_BY_EXERCISE = {
    "barbell": "barbell",
    "dumbbell": "dumbbells",
    "treadmill": "treadmill",
    "cable": "full gym",
    "landmine": "full gym",
    "lat pulldown": "full gym",
    "chest-supported row": "full gym",
    "medicine ball": "medicine ball",
    "bike": "stationary bike",
}
_RECOVERY_TERMS = ("mobility", "easy walk", "breathing", "range of motion")
_HIGH_INTENSITY_TERMS = ("heavy", "max", "all-out", "sprint", "plyometric")


def validate_plan(
    plan: Mapping[str, Any],
    constraints: Mapping[str, Any],
    past_plans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate a plan. Hard failures prevent persistence; soft notes are advisory."""
    hard_errors = _hard_errors(plan, constraints)
    return {
        "hard_validation": {
            "valid": not hard_errors,
            "error_codes": _unique(code for code, _ in hard_errors),
            "errors": [{"code": code, "message": message} for code, message in hard_errors],
        },
        "soft_score": _soft_score(plan, constraints, past_plans),
    }


def _hard_errors(
    plan: Mapping[str, Any], constraints: Mapping[str, Any]
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    sessions = list(plan.get("sessions") or [])
    safety_active = bool((constraints.get("safety_gate") or {}).get("active"))

    if safety_active and any(not _is_recovery_session(session) for session in sessions):
        errors.append(
            ("safety_gate_violation", "Safety gate allows recovery or pain-free mobility only.")
        )

    requested_intensity = str(plan.get("intensity_band") or "normal").lower()
    intensity_ceiling = str(constraints.get("intensity_ceiling") or "normal").lower()
    if _INTENSITY_RANK.get(requested_intensity, 99) > _INTENSITY_RANK.get(intensity_ceiling, 3):
        errors.append(
            (
                "intensity_ceiling_violation",
                f"Plan intensity '{requested_intensity}' exceeds '{intensity_ceiling}'.",
            )
        )

    max_sessions = int((constraints.get("schedule") or {}).get("max_sessions") or 1)
    if len(sessions) > max_sessions:
        errors.append(
            ("schedule_violation", f"Plan has {len(sessions)} sessions; maximum is {max_sessions}.")
        )

    allowed_equipment = [str(item).lower() for item in constraints.get("equipment_access") or []]
    forbidden = [str(item).lower() for item in constraints.get("forbidden_exercises") or []]
    set_ceiling = int(constraints.get("volume_ceiling_sets_per_session") or 18)
    for session in sessions:
        exercises = [str(exercise).lower() for exercise in session.get("exercises") or []]
        for exercise in exercises:
            required_equipment = _equipment_requirement(exercise)
            if required_equipment and not _has_equipment(required_equipment, allowed_equipment):
                errors.append(
                    (
                        "equipment_violation",
                        f"'{exercise}' requires {required_equipment}, which is not available.",
                    )
                )
            if any(blocked in exercise for blocked in forbidden):
                errors.append(
                    (
                        "injury_exclusion_violation",
                        f"'{exercise}' conflicts with an injury or medical exclusion.",
                    )
                )

        estimated_sets = _estimate_sets(str(session.get("sets_reps") or ""))
        if estimated_sets > set_ceiling:
            errors.append(
                (
                    "volume_ceiling_violation",
                    f"'{session.get('day', 'Session')}' has {estimated_sets} sets; ceiling is {set_ceiling}.",
                )
            )

    return errors


def _soft_score(
    plan: Mapping[str, Any],
    constraints: Mapping[str, Any],
    past_plans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sessions = list(plan.get("sessions") or [])
    exercises = [
        str(exercise).lower()
        for session in sessions
        for exercise in session.get("exercises") or []
    ]
    notes: list[str] = []
    score = 100

    if len(exercises) != len(set(exercises)):
        notes.append("Repeated exercises appear in the same weekly plan.")
        score -= 10
    if not _rest_days_are_spaced(sessions):
        notes.append("Training days are consecutive; add recovery spacing where possible.")
        score -= 10
    target_muscles = constraints.get("target_muscle_groups") or []
    actual_muscles = plan.get("target_muscle_groups") or []
    missing_targets = [muscle for muscle in target_muscles if muscle not in actual_muscles]
    if missing_targets:
        notes.append(f"Target muscles missing from plan metadata: {', '.join(missing_targets)}.")
        score -= 15
    if _estimated_plan_sets(plan) > len(sessions) * int(
        constraints.get("volume_ceiling_sets_per_session") or 18
    ):
        notes.append("Weekly set estimate is high for the current readiness limit.")
        score -= 15
    progression = _progression_note(plan, past_plans)
    if progression:
        notes.append(progression)

    return {
        "score": max(0, score),
        "notes": notes,
        "estimated_total_sets": _estimated_plan_sets(plan),
        "muscle_group_balance": "balanced" if not missing_targets else "needs_attention",
    }


def _is_recovery_session(session: Mapping[str, Any]) -> bool:
    session_text = " ".join(
        [str(session.get("focus") or ""), *[str(item) for item in session.get("exercises") or []]]
    ).lower()
    return any(term in session_text for term in _RECOVERY_TERMS) and not any(
        term in session_text for term in _HIGH_INTENSITY_TERMS
    )


def _equipment_requirement(exercise: str) -> str | None:
    return next(
        (equipment for keyword, equipment in _EQUIPMENT_BY_EXERCISE.items() if keyword in exercise),
        None,
    )


def _has_equipment(required_equipment: str, equipment_access: Sequence[str]) -> bool:
    return (
        required_equipment == "bodyweight"
        or "full gym" in equipment_access
        or required_equipment in equipment_access
    )


def _estimate_sets(sets_reps: str) -> int:
    match = re.search(r"\b(\d+)\s*(?:x|sets?)\b", sets_reps.lower())
    return int(match.group(1)) if match else 0


def _estimated_plan_sets(plan: Mapping[str, Any]) -> int:
    return sum(_estimate_sets(str(session.get("sets_reps") or "")) for session in plan.get("sessions") or [])


def _rest_days_are_spaced(sessions: Sequence[Mapping[str, Any]]) -> bool:
    day_numbers = []
    for session in sessions:
        match = re.search(r"\b(\d+)\b", str(session.get("day") or ""))
        if match:
            day_numbers.append(int(match.group(1)))
    return all(next_day - day > 1 for day, next_day in zip(day_numbers, day_numbers[1:]))


def _progression_note(
    plan: Mapping[str, Any], past_plans: Sequence[Mapping[str, Any]]) -> str | None:
    if not past_plans:
        return "No prior plan available; establish a baseline before progressive overload."
    previous = past_plans[0].get("plan_json") or past_plans[0]
    delta = _estimated_plan_sets(plan) - _estimated_plan_sets(previous)
    if delta > 4:
        return "Volume rises materially above the previous plan; monitor recovery."
    if delta < -4:
        return "Volume is below the previous plan, consistent with a deload or reduced readiness."
    return "Volume remains close to the previous plan."


def _unique(values: Any) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
