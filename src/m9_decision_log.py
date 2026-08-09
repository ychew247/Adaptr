"""Module 9: typed, idempotent audit records for agent decisions."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping


DECISION_TYPES = frozenset(
    {
        "readiness_assessment",
        "plan_generation",
        "plan_repair",
        "nutrition_target",
        "weekly_replan",
    }
)


class DecisionLogError(ValueError):
    """Raised when a caller attempts to log an unsupported decision."""


class DecisionLogService:
    """Centralize decision taxonomy, idempotency, and audit payload construction."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def log(
        self,
        *,
        decision_type: str,
        user_id: str,
        idempotency_key: str,
        trigger_date: str | date | None,
        reason: str,
        checkin_id: str | None = None,
        plan_id: str | None = None,
        data_used: Mapping[str, Any] | None = None,
        plan_change: Mapping[str, Any] | None = None,
        safety_flags: list[str] | None = None,
        validation_status: str = "pending",
        validation_notes: Mapping[str, Any] | None = None,
        retrieved_memory_ids: list[str] | None = None,
        generation_attempt: int = 1,
        parent_decision_id: str | None = None,
    ) -> dict[str, Any]:
        if decision_type not in DECISION_TYPES:
            raise DecisionLogError(f"Unsupported decision type: {decision_type}")
        if not idempotency_key:
            raise DecisionLogError("idempotency_key is required")

        existing = self.repository.find_by_idempotency_key(
            user_id, decision_type, idempotency_key
        )
        if existing is not None:
            return existing

        return self.repository.create_decision(
            {
                "user_id": user_id,
                "checkin_id": checkin_id,
                "plan_id": plan_id,
                "trigger_date": trigger_date or date.today(),
                "decision_type": decision_type,
                "idempotency_key": idempotency_key,
                "reason": reason,
                "data_used": dict(data_used or {}),
                "plan_change": dict(plan_change or {}),
                "safety_flags": safety_flags or [],
                "validation_status": validation_status,
                "validation_notes": dict(validation_notes or {}),
                "retrieved_memory_ids": retrieved_memory_ids or [],
                "generation_attempt": generation_attempt,
                "parent_decision_id": parent_decision_id,
            }
        )

    def log_readiness_assessment(
        self, *, user_id: str, checkin: Mapping[str, Any], readiness: Mapping[str, Any]
    ) -> dict[str, Any]:
        checkin_id = checkin.get("id")
        if not checkin_id:
            raise DecisionLogError("Readiness logging requires a saved check-in ID")
        return self.log(
            decision_type="readiness_assessment",
            user_id=user_id,
            idempotency_key=f"checkin:{checkin_id}",
            trigger_date=checkin.get("checkin_date"),
            checkin_id=checkin_id,
            reason=(
                f"Readiness score {readiness['readiness_score']} is "
                f"{readiness['band']}."
            ),
            data_used={
                "checkin_id": checkin_id,
                "readiness_components": readiness.get("components") or {},
            },
            safety_flags=["pain_gate"] if readiness.get("safety_triggered") else [],
            validation_status="calculated",
            validation_notes={
                "readiness_score": readiness["readiness_score"],
                "band": readiness["band"],
            },
        )

    def log_plan_generation(
        self,
        *,
        user_id: str,
        plan: Mapping[str, Any],
        checkin: Mapping[str, Any],
        readiness: Mapping[str, Any],
        reason: str,
        validation: Mapping[str, Any],
        retrieved_memory_ids: list[str],
        generation_attempt: int,
        parent_decision_id: str | None = None,
    ) -> dict[str, Any]:
        plan_id = plan["id"]
        return self.log(
            decision_type="plan_generation",
            user_id=user_id,
            idempotency_key=f"plan:{plan_id}",
            trigger_date=plan.get("week_start"),
            checkin_id=checkin.get("id"),
            plan_id=plan_id,
            reason=reason,
            data_used={
                "readiness": dict(readiness),
                "source_checkin_id": checkin.get("id"),
            },
            plan_change={"generated_plan_id": plan_id},
            safety_flags=["pain_gate"] if readiness.get("safety_triggered") else [],
            validation_status="validated",
            validation_notes=validation,
            retrieved_memory_ids=retrieved_memory_ids,
            generation_attempt=generation_attempt,
            parent_decision_id=parent_decision_id,
        )

    def log_plan_repair(
        self,
        *,
        user_id: str,
        original_plan_id: str,
        trigger_date: str,
        checkin: Mapping[str, Any],
        reason: str,
        data_used: Mapping[str, Any],
        plan_change: Mapping[str, Any],
        safety_flags: list[str],
        validation_status: str,
        validation_notes: Mapping[str, Any],
        retrieved_memory_ids: list[str],
        generation_attempt: int,
        parent_decision_id: str | None = None,
    ) -> dict[str, Any]:
        return self.log(
            decision_type="plan_repair",
            user_id=user_id,
            idempotency_key=f"repair:{original_plan_id}:{trigger_date}",
            trigger_date=trigger_date,
            checkin_id=checkin.get("id"),
            plan_id=original_plan_id,
            reason=reason,
            data_used=data_used,
            plan_change=plan_change,
            safety_flags=safety_flags,
            validation_status=validation_status,
            validation_notes=validation_notes,
            retrieved_memory_ids=retrieved_memory_ids,
            generation_attempt=generation_attempt,
            parent_decision_id=parent_decision_id,
        )

    def log_nutrition_target(
        self,
        *,
        user_id: str,
        nutrition_target: Mapping[str, Any],
        targets: Mapping[str, Any],
        readiness_band: str | None,
        parent_decision_id: str | None = None,
    ) -> dict[str, Any]:
        target_id = nutrition_target["id"]
        return self.log(
            decision_type="nutrition_target",
            user_id=user_id,
            idempotency_key=f"nutrition:{target_id}",
            trigger_date=nutrition_target.get("target_date"),
            reason="Nutrition targets were calculated from profile, training frequency, goal, and workout context.",
            data_used={
                "bmr": targets["bmr"],
                "tdee": targets["tdee"],
                "activity_factor": targets["activity_factor"],
                "readiness_band": readiness_band,
                "workout_today": targets["workout_today"],
            },
            plan_change={
                "nutrition_target_id": target_id,
                "calories_min": nutrition_target["calories_min"],
                "calories_max": nutrition_target["calories_max"],
                "protein_g": nutrition_target["protein_g"],
                "hydration_l": nutrition_target["hydration_l"],
            },
            validation_status="validated",
            validation_notes={"numeric_validation": "passed"},
            parent_decision_id=parent_decision_id,
        )

    def timeline_for_user(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.timeline_for_user(user_id, limit=limit)
