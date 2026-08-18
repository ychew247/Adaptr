"""GUI-ready orchestration for the adaptive fitness agent's daily flow."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, TypedDict

from src.m5_readiness_score import compute_readiness
from src.m6_hybrid_workout_plan import PlanGenerationError
from src.m7_plan_repair import PlanRepairError
from src.dated_workout_sessions import needs_plan_refresh, resolve_checkin_session
from src.workout_plan_selection import find_plan_for_date


class AgentFlowResult(TypedDict):
    checkin: Mapping[str, Any]
    readiness: Mapping[str, Any]
    action: str
    plan: Mapping[str, Any] | None
    nutrition: Mapping[str, Any]
    summary: str


class AdaptiveFitnessAgent:
    """Coordinate a saved check-in through readiness, plan action, and nutrition."""

    def __init__(
        self,
        *,
        checkin_service: Any,
        checkin_repository: Any,
        plan_repository: Any,
        decision_log: Any,
        plan_service: Any,
        repair_service: Any,
        nutrition_service: Any,
        readiness_calculator: Callable[[list[Mapping[str, Any]], Mapping[str, Any]], Mapping[str, Any]] = compute_readiness,
    ) -> None:
        self.checkin_service = checkin_service
        self.checkin_repository = checkin_repository
        self.plan_repository = plan_repository
        self.decision_log = decision_log
        self.plan_service = plan_service
        self.repair_service = repair_service
        self.nutrition_service = nutrition_service
        self.readiness_calculator = readiness_calculator

    def run_daily_flow(
        self,
        user: Mapping[str, Any],
        *,
        workout_today: bool,
        formula_profile: str | None = None,
        requested_repair_dates: list[str] | None = None,
        ask=input,
        say=print,
    ) -> AgentFlowResult:
        checkin = self.checkin_service.run_checkin(user, ask=ask, say=say)
        active_plan = self._plan_for_checkin_date(user, checkin)
        if active_plan and (active_plan.get("plan_json") or {}).get("sessions"):
            resolution = resolve_checkin_session(
                active_plan["plan_json"]["sessions"],
                str(checkin.get("checkin_date")),
                str(checkin.get("workout_completed") or "unknown"),
            )
            if resolution["action"] in {"mark_completed", "mark_missed"}:
                self.plan_repository.update_plan_sessions(active_plan["id"], resolution["sessions"])
            elif resolution["action"] == "ask_completed_session":
                say("I need to know which dated workout you completed before I update the plan.")
        history = self.checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        readiness = self.readiness_calculator(list(reversed(history[1:])), checkin)
        readiness_decision = self.decision_log.log_readiness_assessment(
            user_id=user["id"], checkin=checkin, readiness=readiness
        )
        parent_decision_id = readiness_decision.get("id")

        action = self._route_plan_action(
            user,
            checkin,
            readiness,
            parent_decision_id,
            say,
            active_plan=active_plan,
            requested_repair_dates=requested_repair_dates,
        )
        nutrition = self.nutrition_service.run_daily_target(
            user,
            workout_today=workout_today,
            formula_profile=formula_profile,
            readiness=readiness,
            parent_decision_id=parent_decision_id,
        )
        plan = self._plan_for_checkin_date(user, checkin)
        summary = self._build_summary(user, readiness, action, plan)
        say(summary)

        return {
            "checkin": checkin,
            "readiness": readiness,
            "action": action,
            "plan": self._plan_summary(plan),
            "nutrition": nutrition,
            "summary": summary,
        }

    def _route_plan_action(
        self,
        user: Mapping[str, Any],
        checkin: Mapping[str, Any],
        readiness: Mapping[str, Any],
        parent_decision_id: str | None,
        say: Callable[[str], None],
        *,
        active_plan: Mapping[str, Any] | None = None,
        requested_repair_dates: list[str] | None = None,
    ) -> str:
        if active_plan is None:
            active_plan = self._plan_for_checkin_date(user, checkin)
        if needs_plan_refresh(active_plan):
            return self.plan_service.run_plan_generation(
                user,
                readiness=readiness,
                latest_checkin=checkin,
                parent_decision_id=parent_decision_id,
                say=say,
            )
        try:
            if active_plan is None:
                return self.plan_service.run_plan_generation(
                    user,
                    readiness=readiness,
                    latest_checkin=checkin,
                    parent_decision_id=parent_decision_id,
                    say=say,
                )
            if requested_repair_dates:
                outcomes = [
                    self.repair_service.run_repair(
                        user,
                        trigger_text=self._repair_trigger(checkin, readiness),
                        trigger_date=target_date,
                        readiness=readiness,
                        latest_checkin=checkin,
                        parent_decision_id=parent_decision_id,
                        say=say,
                    )
                    for target_date in requested_repair_dates
                ]
                if "repair_applied" in outcomes:
                    return "repair_applied"
                return outcomes[-1]
            if self._should_repair(checkin, readiness):
                return self.repair_service.run_repair(
                    user,
                    trigger_text=self._repair_trigger(checkin, readiness),
                    trigger_date=str(checkin.get("checkin_date")) if checkin.get("checkin_date") else None,
                    readiness=readiness,
                    latest_checkin=checkin,
                    parent_decision_id=parent_decision_id,
                    say=say,
                )
            if self._active_plan_needs_refresh(user, active_plan, readiness, checkin):
                return self.plan_service.run_plan_generation(
                    user,
                    readiness=readiness,
                    latest_checkin=checkin,
                    parent_decision_id=parent_decision_id,
                    say=say,
                )
        except (PlanGenerationError, PlanRepairError):
            return "plan_action_failed"
        return "keep_plan"

    def _plan_for_checkin_date(
        self, user: Mapping[str, Any], checkin: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        active_plan = self.plan_repository.find_active_by_user_id(user["id"])
        checkin_date = checkin.get("checkin_date")
        if not checkin_date:
            return active_plan
        return find_plan_for_date(
            self.plan_repository,
            user_id=user["id"],
            reference_date=str(checkin_date),
            fallback_plan=active_plan,
        )

    @staticmethod
    def _should_repair(
        checkin: Mapping[str, Any], readiness: Mapping[str, Any]
    ) -> bool:
        if readiness.get("safety_triggered"):
            return True
        if readiness.get("band") != "train_as_planned":
            return True
        if (checkin.get("workout_completed") or "").lower() in {"missed", "partial"}:
            return True
        note = (checkin.get("free_text_note") or "").lower()
        return any(word in note for word in ("limited time", "short on time", "too busy")) or bool(
            re.search(r"\b(?:only have|have)\s+\d{1,3}\s*(?:minutes?|mins?)\b", note)
        )

    def _active_plan_needs_refresh(
        self,
        user: Mapping[str, Any],
        active_plan: Mapping[str, Any] | None,
        readiness: Mapping[str, Any],
        checkin: Mapping[str, Any],
    ) -> bool:
        checker = getattr(self.plan_service, "active_plan_needs_refresh", None)
        if checker is None or active_plan is None:
            return False
        return bool(
            checker(user, active_plan, readiness=readiness, latest_checkin=checkin)
        )

    @staticmethod
    def _repair_trigger(
        checkin: Mapping[str, Any], readiness: Mapping[str, Any]
    ) -> str:
        note = (checkin.get("free_text_note") or "").strip()
        if note:
            return note
        return f"Automatic readiness adjustment: {readiness.get('band', 'unknown')}."

    @staticmethod
    def _plan_summary(plan: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        if plan is None:
            return None
        return {
            "id": plan.get("id"),
            "status": plan.get("status"),
            "intensity_band": plan.get("intensity_band"),
        }

    @staticmethod
    def _build_summary(
        user: Mapping[str, Any],
        readiness: Mapping[str, Any],
        action: str,
        plan: Mapping[str, Any] | None,
    ) -> str:
        action_text = {
            "keep_plan": "kept the active plan",
            "plan_ready": "generated a validated plan",
            "repair_applied": "applied a validated plan repair",
            "repair_fallback": "kept the prior validated plan after repair validation failed",
            "repair_already_recorded": "kept the repair already recorded for today",
            "plan_action_failed": "kept the available plan after an action could not be completed",
        }.get(action, action.replace("_", " "))
        plan_text = " No active plan is available." if plan is None else " Nutrition targets are ready."
        return (
            f"{user['display_name']}: readiness {readiness['readiness_score']} "
            f"({readiness['band']}); {action_text}.{plan_text}"
        )
