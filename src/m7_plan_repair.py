"""Module 7: memory-backed, validated repairs for an active workout plan."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import logging
import re
from typing import Any, Mapping, Sequence

from src.m5_readiness_score import compute_readiness
from src.m6_plan_constraints import derive_plan_constraints
from src.m6_plan_validator import validate_plan
from src.ollama_workout_plan_generator import PlanGenerationFormatError


LOGGER = logging.getLogger(__name__)
MAX_REPAIR_ATTEMPTS = 2

_BAND_ACTIONS = {
    "train_as_planned": "targeted_substitution",
    "reduce_volume": "reduce_volume_and_substitute",
    "lighter_session": "lighter_substitution",
    "recovery_day": "recovery_substitution",
}
_RECOVERY_SESSION = {
    "focus": "Safety-first recovery",
    "exercises": ["mobility breathing reset", "easy walk", "pain-free range of motion"],
    "sets_reps": "15-25 minutes, stop if pain worsens",
}


class PlanRepairError(RuntimeError):
    """Raised when the active plan cannot be repaired safely."""


class PlanRepairService:
    """Retrieve repair precedents, generate a bounded edit, validate, then persist."""

    def __init__(
        self,
        *,
        profile_repository: Any,
        goal_repository: Any,
        checkin_repository: Any,
        plan_repository: Any,
        decision_repository: Any,
        decision_log: Any | None = None,
        memory_repository: Any,
        embedder: Any,
        repair_generator: Any,
    ) -> None:
        self.profile_repository = profile_repository
        self.goal_repository = goal_repository
        self.checkin_repository = checkin_repository
        self.plan_repository = plan_repository
        self.decision_repository = decision_repository
        self.decision_log = decision_log
        self.memory_repository = memory_repository
        self.embedder = embedder
        self.repair_generator = repair_generator

    def run_repair(
        self,
        user: Mapping[str, Any],
        *,
        trigger_text: str,
        trigger_date: str | None = None,
        say=print,
    ) -> str:
        active_plan = self.plan_repository.find_active_by_user_id(user["id"])
        if active_plan is None:
            raise PlanRepairError("No active plan exists. Generate Module 6 plan first.")
        trigger_date = trigger_date or str(date.today())
        existing = self.decision_repository.find_repair_by_trigger(
            user["id"], active_plan["id"], trigger_date
        )
        if existing is not None:
            say("A repair for this plan and trigger date already exists; keeping the saved decision.")
            return "repair_already_recorded"

        profile = self.profile_repository.find_by_user_id(user["id"])
        goal = self.goal_repository.find_active_by_user_id(user["id"])
        if profile is None or goal is None:
            raise PlanRepairError("Static profile and active goal are required before repair.")
        checkins = self.checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        latest_checkin = checkins[0] if checkins else {}
        readiness = _readiness_from_checkins(checkins)
        constraints = derive_plan_constraints(profile, goal, readiness, latest_checkin)
        repair_action = determine_repair_action(readiness, trigger_text)
        retrieval_embedding = self.embedder.embed(
            _repair_retrieval_query(active_plan, trigger_text, latest_checkin, readiness)
        )
        retrieved_memories = self._retrieve_repair_context(user["id"], retrieval_embedding)
        retrieved_memory_ids = [memory["id"] for memory in retrieved_memories]
        past_plans = self.plan_repository.find_recent_by_user_id(user["id"], limit=4)
        validator_feedback: dict[str, Any] | None = None
        last_validation: dict[str, Any] | None = None

        for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
            try:
                suggested_edit = self.repair_generator.generate(
                    active_plan["plan_json"],
                    repair_action,
                    constraints,
                    retrieved_memories,
                    validator_feedback=validator_feedback,
                )
            except PlanGenerationFormatError as error:
                validator_feedback = _format_feedback(error)
                last_validation = {"hard_validation": validator_feedback, "soft_score": {}}
                continue

            candidate_plan = apply_repair_action(
                active_plan["plan_json"],
                repair_action,
                suggested_edit,
                constraints,
                readiness,
                latest_checkin,
                retrieved_memory_ids,
                attempt,
            )
            validation = validate_plan(candidate_plan, constraints, past_plans)
            last_validation = validation
            if validation["hard_validation"]["valid"]:
                return self._persist_valid_repair(
                    user,
                    active_plan,
                    candidate_plan,
                    latest_checkin,
                    trigger_text,
                    trigger_date,
                    repair_action,
                    retrieved_memories,
                    validation,
                    attempt,
                    say,
                )

            validator_feedback = validation["hard_validation"]
            LOGGER.warning(
                "Rejected repair attempt %s for user %s: %s",
                attempt,
                user["id"],
                validator_feedback["error_codes"],
            )

        self._persist_fallback(
            user,
            active_plan,
            latest_checkin,
            trigger_text,
            trigger_date,
            repair_action,
            retrieved_memory_ids,
            last_validation or {},
            readiness,
        )
        say("Repair could not pass validation, so the prior validated plan remains active.")
        return "repair_fallback"

    def _persist_valid_repair(
        self,
        user: Mapping[str, Any],
        active_plan: Mapping[str, Any],
        candidate_plan: Mapping[str, Any],
        latest_checkin: Mapping[str, Any],
        trigger_text: str,
        trigger_date: str,
        repair_action: Mapping[str, Any],
        retrieved_memories: Sequence[Mapping[str, Any]],
        validation: Mapping[str, Any],
        attempt: int,
        say: Any,
    ) -> str:
        candidate_plan["validation"] = validation
        candidate_plan["validation_status"] = "validated"
        candidate_plan["decision_reason"] = _repair_reason(repair_action, retrieved_memories)
        saved_plan = self.plan_repository.create_active_plan(
            {
                "user_id": user["id"],
                "goal_id": active_plan["goal_id"],
                "week_start": candidate_plan["week_start"],
                "exercise_names": candidate_plan["exercise_names"],
                "target_muscle_groups": candidate_plan["target_muscle_groups"],
                "intensity_band": candidate_plan["intensity_band"],
                "plan_json": candidate_plan,
                "status": "active",
                "validation_status": "validated",
                "validation_notes": validation,
                "retrieved_memory_ids": candidate_plan["retrieved_memory_ids"],
                "generation_attempt": attempt,
            }
        )
        decision_payload = {
            "user_id": user["id"],
            "checkin_id": latest_checkin.get("id"),
            "plan_id": active_plan["id"],
            "trigger_date": trigger_date,
            "decision_type": "plan_repair",
            "reason": candidate_plan["decision_reason"],
            "data_used": {
                "trigger_text": trigger_text,
                "repair_action": repair_action,
                "readiness": candidate_plan["readiness"],
            },
            "plan_change": {
                "repaired_plan_id": saved_plan["id"],
                "action": repair_action["action"],
                "sessions": candidate_plan["sessions"],
            },
            "safety_flags": ["pain_gate"] if repair_action["pain_gate"] else [],
            "validation_status": "validated",
            "validation_notes": validation,
            "retrieved_memory_ids": candidate_plan["retrieved_memory_ids"],
            "generation_attempt": attempt,
        }
        decision = self._log_repair_decision(
            decision_payload, latest_checkin, candidate_plan["readiness"]
        )
        self._store_repair_memory(user["id"], decision, candidate_plan)
        say(f"Saved {user['display_name']}'s validated plan repair.")
        return "repair_applied"

    def _persist_fallback(
        self,
        user: Mapping[str, Any],
        active_plan: Mapping[str, Any],
        latest_checkin: Mapping[str, Any],
        trigger_text: str,
        trigger_date: str,
        repair_action: Mapping[str, Any],
        retrieved_memory_ids: list[Any],
        validation: Mapping[str, Any],
        readiness: Mapping[str, Any],
    ) -> None:
        payload = {
            "user_id": user["id"],
            "checkin_id": latest_checkin.get("id"),
            "plan_id": active_plan["id"],
            "trigger_date": trigger_date,
            "decision_type": "plan_repair",
            "reason": "Repair validation failed twice; retained the prior validated plan.",
            "data_used": {"trigger_text": trigger_text, "repair_action": repair_action},
            "plan_change": {"action": "keep_prior_valid_plan", "prior_plan_id": active_plan["id"]},
            "safety_flags": ["pain_gate"] if repair_action["pain_gate"] else [],
            "validation_status": "fallback_to_prior_plan",
            "validation_notes": validation,
            "retrieved_memory_ids": retrieved_memory_ids,
            "generation_attempt": MAX_REPAIR_ATTEMPTS,
        }
        self._log_repair_decision(payload, latest_checkin, readiness)

    def _log_repair_decision(
        self,
        payload: Mapping[str, Any],
        latest_checkin: Mapping[str, Any],
        readiness: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if self.decision_log is None:
            return self.decision_repository.create_repair_decision(dict(payload))

        parent_decision_id = None
        if latest_checkin.get("id"):
            parent_decision = self.decision_log.log_readiness_assessment(
                user_id=payload["user_id"], checkin=latest_checkin, readiness=readiness
            )
            parent_decision_id = parent_decision.get("id")
        return self.decision_log.log_plan_repair(
            user_id=payload["user_id"],
            original_plan_id=payload["plan_id"],
            trigger_date=payload["trigger_date"],
            checkin=latest_checkin,
            reason=payload["reason"],
            data_used=payload["data_used"],
            plan_change=payload["plan_change"],
            safety_flags=payload["safety_flags"],
            validation_status=payload["validation_status"],
            validation_notes=payload["validation_notes"],
            retrieved_memory_ids=payload["retrieved_memory_ids"],
            generation_attempt=payload["generation_attempt"],
            parent_decision_id=parent_decision_id,
        )

    def _store_repair_memory(
        self, user_id: str, decision: Mapping[str, Any], candidate_plan: Mapping[str, Any]
    ) -> None:
        decision_id = decision.get("id")
        if not decision_id:
            return
        memory_text = json.dumps(
            {
                "repair_reason": candidate_plan["decision_reason"],
                "repair": candidate_plan["repair"],
                "sessions": candidate_plan["sessions"],
            },
            default=str,
            sort_keys=True,
        )
        try:
            self.memory_repository.upsert_memory(
                user_id=user_id,
                source_type="agent_decision",
                source_id=decision_id,
                memory_text=memory_text,
                embedding=self.embedder.embed(memory_text),
                outcome_json={"validation_status": "validated", "decision_id": str(decision_id)},
            )
        except Exception as error:
            LOGGER.warning("Could not store validated repair memory: %s", error)

    def _retrieve_repair_context(
        self, user_id: str, retrieval_embedding: Sequence[float]
    ) -> list[Mapping[str, Any]]:
        memories: list[Mapping[str, Any]] = []
        seen_ids = set()
        for source_type in ("agent_decision", "fitness_knowledge"):
            for memory in self.memory_repository.search_similar(
                user_id, retrieval_embedding, limit=5, source_type=source_type
            ):
                memory_id = memory.get("id")
                if memory_id in seen_ids:
                    continue
                seen_ids.add(memory_id)
                memories.append(memory)
        return memories


def determine_repair_action(
    readiness: Mapping[str, Any], trigger_text: str
) -> dict[str, Any]:
    """Map safety/readiness bands to deterministic repair actions."""
    trigger = trigger_text.lower()
    pain_gate = bool(readiness.get("safety_triggered")) or any(
        word in trigger for word in ("sharp", "worsening", "severe", "persistent")
    )
    if pain_gate:
        action = "recovery_substitution"
        reason = "Pain gate overrides normal training and requires recovery-only work."
    elif "miss" in trigger or "skip" in trigger:
        action = "reschedule_session"
        reason = "Missed-session trigger moves one session without increasing weekly volume."
    elif "time" in trigger or "busy" in trigger or "short" in trigger:
        action = "shorten_session"
        reason = "Limited-time trigger shortens one session while preserving the weekly goal."
    else:
        action = _BAND_ACTIONS.get(readiness.get("band"), "targeted_substitution")
        reason = "Readiness band selected the repair intensity and volume action."
    return {
        "action": action,
        "reason": reason,
        "pain_gate": pain_gate,
        "required_intensity_band": _intensity_for_action(action, readiness),
    }


def apply_repair_action(
    prior_plan: Mapping[str, Any],
    repair_action: Mapping[str, Any],
    suggested_edit: Mapping[str, Any],
    constraints: Mapping[str, Any],
    readiness: Mapping[str, Any],
    latest_checkin: Mapping[str, Any],
    retrieved_memory_ids: list[Any],
    attempt: int,
) -> dict[str, Any]:
    """Apply only the deterministic action shape around the LLM's replacement wording."""
    candidate = deepcopy(dict(prior_plan))
    sessions = deepcopy(list(candidate.get("sessions") or []))
    if not sessions:
        raise PlanRepairError("Active plan has no sessions to repair.")
    target_index = _target_session_index(sessions, repair_action["action"])
    original_session = sessions[target_index]
    replacement = dict(suggested_edit.get("replacement_session") or {})

    if repair_action["action"] == "recovery_substitution":
        repaired_session = {**original_session, **replacement, **_RECOVERY_SESSION}
        repaired_session["day"] = original_session.get("day", "Day 1")
        repaired_session["focus"] = "Safety-first recovery"
    elif repair_action["action"] == "reschedule_session":
        repaired_session = {**original_session, **replacement}
        repaired_session["day"] = _next_day(original_session.get("day", "Day 1"))
    elif repair_action["action"] == "shorten_session":
        repaired_session = {**original_session, **replacement}
        repaired_session["sets_reps"] = replacement.get("sets_reps") or "20-30 minutes, easy-to-moderate"
    else:
        repaired_session = {**original_session, **replacement}

    repaired_session["exercises"] = list(
        repaired_session.get("exercises") or original_session.get("exercises") or []
    )
    repaired_session["sets_reps"] = repaired_session.get("sets_reps") or original_session.get(
        "sets_reps", "As prescribed"
    )
    sessions[target_index] = repaired_session
    candidate["sessions"] = sessions
    candidate["exercise_names"] = _exercise_names(sessions)
    candidate["intensity_band"] = repair_action["required_intensity_band"]
    candidate["readiness"] = dict(readiness)
    candidate["readiness_score"] = readiness["readiness_score"]
    candidate["readiness_band"] = readiness["band"]
    candidate["safety_triggered"] = readiness["safety_triggered"]
    candidate["constraints"] = dict(constraints)
    candidate["retrieved_memory_ids"] = retrieved_memory_ids
    candidate["generation_attempt"] = attempt
    candidate["source_checkin_id"] = latest_checkin.get("id")
    candidate["repair"] = {
        "action": repair_action["action"],
        "target_session": original_session.get("day"),
        "coaching_note": suggested_edit.get("coaching_note", ""),
    }
    return candidate


def _readiness_from_checkins(checkins: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not checkins:
        return {
            "readiness_score": 85,
            "band": "train_as_planned",
            "safety_triggered": False,
            "components": {"source": "default_no_checkins"},
        }
    return compute_readiness(list(reversed(checkins[1:])), checkins[0])


def _repair_retrieval_query(
    active_plan: Mapping[str, Any],
    trigger_text: str,
    checkin: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> str:
    return json.dumps(
        {
            "repair_trigger": trigger_text,
            "current_sessions": (active_plan.get("plan_json") or {}).get("sessions") or [],
            "pain_notes": checkin.get("pain_notes") or "",
            "soreness": checkin.get("soreness_level"),
            "readiness_band": readiness.get("band"),
        },
        default=str,
        sort_keys=True,
    )


def _target_session_index(sessions: Sequence[Mapping[str, Any]], action: str) -> int:
    if action == "reschedule_session":
        return len(sessions) - 1
    return 0


def _next_day(day: str) -> str:
    match = re.search(r"(\d+)", day)
    return f"Day {int(match.group(1)) + 1}" if match else "Day 2"


def _exercise_names(sessions: Sequence[Mapping[str, Any]]) -> list[str]:
    return list(
        dict.fromkeys(
            str(exercise) for session in sessions for exercise in session.get("exercises") or []
        )
    )


def _intensity_for_action(action: str, readiness: Mapping[str, Any]) -> str:
    if action == "recovery_substitution":
        return "recovery"
    return {
        "train_as_planned": "normal",
        "reduce_volume": "reduced",
        "lighter_session": "light",
        "recovery_day": "recovery",
    }.get(readiness.get("band"), "normal")


def _format_feedback(error: Exception) -> dict[str, Any]:
    return {
        "valid": False,
        "error_codes": ["invalid_model_json"],
        "errors": [{"code": "invalid_model_json", "message": str(error)}],
    }


def _repair_reason(
    repair_action: Mapping[str, Any], retrieved_memories: Sequence[Mapping[str, Any]]
) -> str:
    if repair_action["pain_gate"]:
        return "Pain gate selected a recovery repair; the candidate passed validation."
    if retrieved_memories:
        return "Repair action was rule-based and the exercise substitution used similar past repair memory."
    return "Repair action was selected from the readiness-band rule table; no similar repair memory was found."
