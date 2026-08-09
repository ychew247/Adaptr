from __future__ import annotations

from typing import Any

from src.m5_readiness_score import compute_readiness
from src.m8_nutrition_targets import calculate_nutrition_targets, validate_nutrition_targets


class NutritionTargetService:
    def __init__(
        self,
        profile_repository,
        goal_repository,
        checkin_repository,
        plan_repository,
        nutrition_repository,
        note_generator=None,
        decision_log=None,
    ):
        self.profile_repository = profile_repository
        self.goal_repository = goal_repository
        self.checkin_repository = checkin_repository
        self.plan_repository = plan_repository
        self.nutrition_repository = nutrition_repository
        self.note_generator = note_generator
        self.decision_log = decision_log

    def run_daily_target(
        self,
        user: dict[str, Any],
        workout_today: bool,
        formula_profile: str | None = None,
    ) -> dict[str, Any]:
        profile = self.profile_repository.find_by_user_id(user["id"])
        if formula_profile:
            normalized = formula_profile.strip().lower()
            if normalized not in {"male", "female"}:
                raise ValueError("--bmr-formula-profile must be male or female")
            self.profile_repository.set_bmr_formula_profile(user["id"], normalized)
            profile = {**profile, "bmr_formula_profile": normalized}

        goal = self.goal_repository.find_active_by_user_id(user["id"])
        active_plan = self.plan_repository.find_active_by_user_id(user["id"])
        checkins = self.checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        readiness = None
        readiness_band = None
        if checkins:
            readiness = compute_readiness(list(reversed(checkins[1:])), checkins[0])
            readiness_band = readiness["band"]

        targets = calculate_nutrition_targets(
            profile=profile,
            goal=goal,
            active_plan=active_plan,
            readiness_band=readiness_band,
            workout_today=workout_today,
        )
        validate_nutrition_targets(targets)
        notes = self._generate_notes(targets, profile, workout_today)
        saved_target = self.nutrition_repository.upsert_daily_target(
            {
                "user_id": user["id"],
                "calories_min": targets["calories_min"],
                "calories_max": targets["calories_max"],
                "protein_g": targets["protein_g"],
                "hydration_l": targets["hydration_l"],
                "fiber_g": targets["fiber_g"],
                "notes": notes,
            }
        )
        if self.decision_log is not None:
            parent_decision_id = None
            if readiness is not None:
                readiness_decision = self.decision_log.log_readiness_assessment(
                    user_id=user["id"], checkin=checkins[0], readiness=readiness
                )
                parent_decision_id = readiness_decision.get("id")
            self.decision_log.log_nutrition_target(
                user_id=user["id"],
                nutrition_target=saved_target,
                targets=targets,
                readiness_band=readiness_band,
                parent_decision_id=parent_decision_id,
            )
        return saved_target

    def _generate_notes(self, targets, profile, workout_today):
        if self.note_generator is None:
            return _fallback_note(targets, workout_today)
        try:
            return self.note_generator.generate(targets, profile, workout_today)
        except Exception:
            return _fallback_note(targets, workout_today)


def _fallback_note(targets: dict[str, Any], workout_today: bool) -> str:
    timing = "Include protein after your planned session." if workout_today else "Spread protein across regular meals."
    recovery = " A lighter appetite can be normal on a recovery day; do not cut the target." if targets["readiness_band"] == "recovery" else ""
    low, high = targets["protein_range_g"]
    return f"{timing} Your protein planning range is {low}-{high} g. {recovery} How closely did this feel achievable today?"
