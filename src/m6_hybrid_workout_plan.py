"""Hybrid Module 6 orchestration: retrieval, LLM generation, validation, and audit."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Mapping, Sequence

from src.m5_readiness_score import compute_readiness
from src.m6_plan_constraints import derive_plan_constraints
from src.m6_plan_validator import validate_plan
from src.m6_workout_plan import generate_weekly_plan, schedule_sessions
from src.ollama_workout_plan_generator import PlanGenerationFormatError


LOGGER = logging.getLogger(__name__)
MAX_RETRIES = 2


class PlanGenerationError(RuntimeError):
    """Raised when no generated plan passes deterministic validation."""


class DeterministicWorkoutPlanGenerator:
    """Compatibility generator for the CLI's --deterministic-plan option."""

    def generate(
        self,
        profile: Mapping[str, Any],
        goal: Mapping[str, Any],
        readiness: Mapping[str, Any],
        constraints: Mapping[str, Any] | None = None,
        retrieved_memories: Sequence[Mapping[str, Any]] | None = None,
        validator_feedback: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = generate_weekly_plan(profile, goal, readiness)
        plan["generator"] = "deterministic"
        return plan


class HybridWorkoutPlanService:
    """Generate plans from constrained LLM output and CockroachDB memory precedents."""

    def __init__(
        self,
        *,
        profile_repository: Any,
        goal_repository: Any,
        checkin_repository: Any,
        plan_repository: Any,
        memory_repository: Any,
        embedder: Any,
        plan_generator: Any,
        decision_log: Any | None = None,
    ) -> None:
        self.profile_repository = profile_repository
        self.goal_repository = goal_repository
        self.checkin_repository = checkin_repository
        self.plan_repository = plan_repository
        self.memory_repository = memory_repository
        self.embedder = embedder
        self.plan_generator = plan_generator
        self.decision_log = decision_log

    def run_plan_generation(
        self,
        user: Mapping[str, Any],
        *,
        readiness: Mapping[str, Any] | None = None,
        latest_checkin: Mapping[str, Any] | None = None,
        parent_decision_id: str | None = None,
        say=print,
    ) -> str:
        profile = self.profile_repository.find_by_user_id(user["id"])
        if profile is None:
            raise PlanGenerationError("Static profile is missing. Run Module 2 first.")
        goal = self.goal_repository.find_active_by_user_id(user["id"])
        if goal is None:
            raise PlanGenerationError("Active goal is missing. Run Module 3 first.")

        checkins = self.checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        latest_checkin = latest_checkin or (checkins[0] if checkins else {})
        readiness = readiness or _readiness_from_checkins(checkins)
        constraints = derive_plan_constraints(profile, goal, readiness, latest_checkin)
        past_plans = self._past_plans(user["id"])
        query_text = _retrieval_query(profile, goal, latest_checkin, readiness)
        query_embedding = self.embedder.embed(query_text)
        retrieved_memories = self.memory_repository.search_similar(user["id"], query_embedding, limit=5)
        retrieved_memory_ids = [memory["id"] for memory in retrieved_memories]

        self._store_checkin_memory(user["id"], latest_checkin, query_embedding, readiness)
        validator_feedback: dict[str, Any] | None = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                generated_plan = self.plan_generator.generate(
                    profile,
                    goal,
                    readiness,
                    constraints=constraints,
                    retrieved_memories=retrieved_memories,
                    validator_feedback=validator_feedback,
                )
            except PlanGenerationFormatError as error:
                validator_feedback = {
                    "error_codes": ["invalid_model_json"],
                    "errors": [{"code": "invalid_model_json", "message": str(error)}],
                }
                LOGGER.warning(
                    "Ollama plan generation attempt %s returned malformed JSON for user %s.",
                    attempt,
                    user["id"],
                )
                continue
            plan_json = _complete_plan(
                generated_plan,
                goal,
                readiness,
                constraints,
                latest_checkin,
                retrieved_memory_ids,
                attempt,
            )
            validation = validate_plan(plan_json, constraints, past_plans)
            if validation["hard_validation"]["valid"]:
                plan_json["validation"] = validation
                plan_json["validation_status"] = "validated"
                plan_json["decision_reason"] = _decision_reason(constraints, retrieved_memories)
                saved_plan = self.plan_repository.create_active_plan(
                    {
                        "user_id": user["id"],
                        "goal_id": goal["id"],
                        "week_start": plan_json["week_start"],
                        "exercise_names": plan_json["exercise_names"],
                        "target_muscle_groups": plan_json["target_muscle_groups"],
                        "intensity_band": plan_json["intensity_band"],
                        "plan_json": plan_json,
                        "status": "active",
                        "validation_status": "validated",
                        "validation_notes": validation,
                        "retrieved_memory_ids": retrieved_memory_ids,
                        "generation_attempt": attempt,
                        "source_checkin_id": latest_checkin.get("id"),
                    }
                )
                self._store_plan_memory(user["id"], saved_plan, plan_json)
                if self.decision_log is not None and latest_checkin.get("id"):
                    if parent_decision_id is None:
                        readiness_decision = self.decision_log.log_readiness_assessment(
                            user_id=user["id"], checkin=latest_checkin, readiness=readiness
                        )
                        parent_decision_id = readiness_decision.get("id")
                    self.decision_log.log_plan_generation(
                        user_id=user["id"],
                        plan=saved_plan,
                        checkin=latest_checkin,
                        readiness=readiness,
                        reason=plan_json["decision_reason"],
                        validation=validation,
                        retrieved_memory_ids=retrieved_memory_ids,
                        generation_attempt=attempt,
                        parent_decision_id=parent_decision_id,
                    )
                say(f"Saved {user['display_name']}'s validated Week {plan_json['week_number']} workout plan.")
                return "plan_ready"

            validator_feedback = validation["hard_validation"]
            LOGGER.warning(
                "Rejected plan generation attempt %s for user %s: %s",
                attempt,
                user["id"],
                validator_feedback["error_codes"],
            )

        raise PlanGenerationError(
            "No workout plan passed deterministic safety validation after {} attempts.".format(
                MAX_RETRIES + 1
            )
        )

    def _past_plans(self, user_id: str) -> Sequence[Mapping[str, Any]]:
        find_recent = getattr(self.plan_repository, "find_recent_by_user_id", None)
        return find_recent(user_id, limit=4) if find_recent else []

    def _store_checkin_memory(
        self,
        user_id: str,
        checkin: Mapping[str, Any],
        embedding: Sequence[float],
        readiness: Mapping[str, Any],
    ) -> None:
        if not checkin.get("id"):
            return
        try:
            self.memory_repository.upsert_memory(
                user_id=user_id,
                source_type="daily_note",
                source_id=checkin["id"],
                memory_text=_checkin_memory_text(checkin, readiness),
                embedding=embedding,
                outcome_json={"readiness_score": readiness["readiness_score"], "band": readiness["band"]},
            )
        except Exception as error:  # Memory persistence must not expose an unvalidated plan.
            LOGGER.warning("Could not store check-in memory: %s", error)

    def _store_plan_memory(
        self, user_id: str, saved_plan: Mapping[str, Any], plan_json: Mapping[str, Any]
    ) -> None:
        plan_id = saved_plan.get("id")
        if not plan_id:
            return
        try:
            memory_text = "Validated plan: " + json.dumps(
                {
                    "sessions": plan_json["sessions"],
                    "readiness_score": plan_json["readiness_score"],
                    "decision_reason": plan_json["decision_reason"],
                },
                default=str,
            )
            self.memory_repository.upsert_memory(
                user_id=user_id,
                source_type="validated_plan",
                source_id=plan_id,
                memory_text=memory_text,
                embedding=self.embedder.embed(memory_text),
                outcome_json={"validation_status": "validated", "plan_id": str(plan_id)},
            )
        except Exception as error:
            LOGGER.warning("Could not store validated-plan memory: %s", error)


def _readiness_from_checkins(checkins: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not checkins:
        return {
            "readiness_score": 85,
            "band": "train_as_planned",
            "safety_triggered": False,
            "components": {"source": "default_no_checkins"},
        }
    return compute_readiness(list(reversed(checkins[1:])), checkins[0])


def _retrieval_query(
    profile: Mapping[str, Any],
    goal: Mapping[str, Any],
    checkin: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> str:
    return json.dumps(
        {
            "goal": goal.get("goal_details") or {},
            "goal_type": goal.get("goal_type"),
            "equipment": profile.get("equipment_access") or [],
            "injury_notes": profile.get("injury_notes") or "",
            "checkin": {
                "soreness": checkin.get("soreness_level"),
                "sore_muscle_groups": checkin.get("sore_muscle_groups") or [],
                "pain_notes": checkin.get("pain_notes") or "",
                "note": checkin.get("free_text_note") or "",
            },
            "readiness_band": readiness.get("band"),
        },
        sort_keys=True,
    )


def _complete_plan(
    plan: Mapping[str, Any],
    goal: Mapping[str, Any],
    readiness: Mapping[str, Any],
    constraints: Mapping[str, Any],
    checkin: Mapping[str, Any],
    retrieved_memory_ids: list[Any],
    attempt: int,
) -> dict[str, Any]:
    completed = dict(plan)
    sessions = list(completed.get("sessions") or [])
    week_start = completed.get("week_start") or str(date.today())
    sessions = schedule_sessions(sessions, week_start)
    completed.update(
        {
            "goal_id": goal["id"],
            "week_start": week_start,
            "week_number": completed.get("week_number") or 1,
            "plan_duration_weeks": goal.get("plan_duration_weeks"),
            "goal_type": goal.get("goal_type"),
            "exercise_names": completed.get("exercise_names") or _exercise_names(sessions),
            "target_muscle_groups": completed.get("target_muscle_groups")
            or (goal.get("goal_details") or {}).get("target_muscle_groups")
            or [],
            "intensity_band": completed.get("intensity_band")
            or constraints["intensity_ceiling"],
            "readiness_score": readiness["readiness_score"],
            "readiness_band": readiness["band"],
            "safety_triggered": readiness["safety_triggered"],
            "constraints": constraints,
            "retrieved_memory_ids": retrieved_memory_ids,
            "generation_attempt": attempt,
            "source_checkin_id": checkin.get("id"),
        }
    )
    return completed


def _exercise_names(sessions: Sequence[Mapping[str, Any]]) -> list[str]:
    return list(
        dict.fromkeys(
            str(exercise)
            for session in sessions
            for exercise in session.get("exercises") or []
        )
    )


def _checkin_memory_text(checkin: Mapping[str, Any], readiness: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "checkin_note": checkin.get("free_text_note") or "",
            "pain_notes": checkin.get("pain_notes") or "",
            "sore_muscle_groups": checkin.get("sore_muscle_groups") or [],
            "readiness_score": readiness.get("readiness_score"),
            "readiness_band": readiness.get("band"),
        },
        sort_keys=True,
    )


def _decision_reason(
    constraints: Mapping[str, Any], retrieved_memories: Sequence[Mapping[str, Any]]
) -> str:
    if constraints["safety_gate"]["active"]:
        return "Safety gate required a recovery-only plan."
    if retrieved_memories:
        return "Plan was constrained by readiness and informed by similar past memories."
    return "Plan was constrained by readiness; no similar past memory was available."
