"""NiceGUI-facing controller that delegates fitness work to existing services."""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
import logging
from typing import Any, Callable

from src.fitness_agent_runtime import build_runtime, database_connection
from src.fitness_chat import (
    PROFILE_QUESTIONS,
    format_daily_result,
    profile_answers_to_queue,
)
from src.m1_user_identity import UserIdentityService
from src.m2_static_profile import StaticProfileService
from src.m3_training_goal import (
    GENERAL_GOAL_PROMPT,
    TrainingGoalService,
    build_follow_up_prompt,
    parse_training_goal,
)
from src.m15_safety_validity import assess_safety
from src.ollama_chat_language import OllamaChatLanguage
from src.ollama_client import OllamaClient
from src.ollama_repair_target_parser import RepairTargetParseError
from src.s3_workout_plan_storage import S3WorkoutPlanStorage, WorkoutPlanStorageError
from src.workout_repair_target_selection import (
    WorkoutRepairTargetError,
    resolve_repair_target_dates,
)
from src.workout_plan_selection import find_plan_for_date
from src.workout_plan_excel_export import export_sessions_workbook_bytes
from ui.chat_state import ChatSession


logger = logging.getLogger(__name__)


class FitnessChatController:
    """Owns UI conversation state while reusing the connected agent backend."""

    def __init__(self, session: ChatSession) -> None:
        self.session = session

    def start_new_chat(self) -> None:
        welcome = self._landing_welcome()
        self.session.start_new_chat(welcome["prompt"], welcome_headline=welcome["headline"])

    def handle_message(self, message: str) -> None:
        cleaned = self.begin_message(message)
        if cleaned is not None:
            self.complete_message(cleaned)

    def begin_message(self, message: str) -> str | None:
        """Record a user message so the UI can render it before agent work starts."""
        cleaned = message.strip()
        if not cleaned:
            return None
        self.session.show_welcome_screen = False
        self.session.add_message("user", cleaned)
        self.session.status = "Working"
        return cleaned

    def complete_message(self, message: str) -> None:
        """Run the potentially slow agent work for an already rendered message."""
        retryable_phase = self.session.phase in {"identity", "profile", "goal", "goal_follow_up"}
        for attempt in range(2):
            try:
                self._route_message(message)
                self.session.status = "Ready"
                return
            except Exception as error:
                if attempt == 0 and retryable_phase and _is_transient_database_error(error):
                    continue
                self.session.add_message("assistant", _friendly_error(error))
                self.session.status = "Needs attention"
                return

    def _route_message(self, message: str) -> None:
        assessment = assess_safety(message)
        if assessment["highest_severity"] in {"urgent", "blocked"}:
            self.session.add_message("assistant", assessment["reason"])
            return
        if self.session.phase == "identity":
            self._handle_identity(message)
        elif self.session.phase == "profile":
            self._handle_profile_answer(message)
        elif self.session.phase == "goal":
            self._handle_goal(message)
        elif self.session.phase == "goal_follow_up":
            self._save_goal([self.session.goal_text, message])
        else:
            self._handle_daily_message(message)

    def _handle_identity(self, display_name: str) -> None:
        with database_connection() as connection:
            runtime = build_runtime(connection)
            identity = UserIdentityService(runtime["users"]).get_or_create_user(display_name)
            self.session.user = identity.user
            profile = runtime["profiles"].find_by_user_id(identity.user["id"])
            goal = runtime["goals"].find_active_by_user_id(identity.user["id"])

        if profile is None:
            self.session.phase = "profile"
            self.session.add_message(
                "assistant",
                self._next_profile_prompt(identity.user["display_name"], identity.created),
            )
        elif goal is None:
            self.session.phase = "goal"
            self.session.add_message(
                "assistant", f"Welcome back, {identity.user['display_name']}. {GENERAL_GOAL_PROMPT}"
            )
        else:
            self.session.phase = "daily"
            self.session.add_message(
                "assistant",
                f"Welcome back, {identity.user['display_name']}. Tell me about sleep, energy, soreness, "
                "pain, food, and whether you plan to train today.",
            )

    def _handle_profile_answer(self, answer: str) -> None:
        index = len(self.session.profile_answers)
        key, _requirement = PROFILE_QUESTIONS[index]
        error = _validate_profile_answer(key, answer)
        if error:
            self.session.add_message("assistant", error)
            return
        self.session.profile_answers[key] = answer
        if len(self.session.profile_answers) < len(PROFILE_QUESTIONS):
            self.session.add_message(
                "assistant", self._next_profile_prompt(self.session.user["display_name"], False)
            )
            return

        with database_connection() as connection:
            runtime = build_runtime(connection)
            _run_with_answers(
                lambda ask: StaticProfileService(runtime["profiles"]).run_onboarding(
                    self.session.user, ask=ask, say=lambda _message: None
                ),
                profile_answers_to_queue(self.session.profile_answers),
            )
        self.session.phase = "goal"
        self.session.add_message("assistant", f"Your profile is saved. {GENERAL_GOAL_PROMPT}")

    def _handle_goal(self, answer: str) -> None:
        parsed = self._parse_goal(answer)
        missing = parsed["goal_details"]["missing_fields"]
        if missing:
            self.session.goal_text = answer
            self.session.phase = "goal_follow_up"
            self.session.add_message("assistant", build_follow_up_prompt(missing))
            return
        self._save_goal([answer], parsed_goal=parsed)

    def _save_goal(self, answers: list[str], parsed_goal: dict[str, Any] | None = None) -> None:
        with database_connection() as connection:
            runtime = build_runtime(connection)
            parser = (
                (lambda _text: parsed_goal)
                if parsed_goal is not None
                else (lambda text: self._parse_goal_with_parser(text, runtime["goal_parser"]))
            )
            _run_with_answers(
                lambda ask: TrainingGoalService(runtime["goals"], parser=parser).run_goal_setup(
                    self.session.user,
                    ask=ask,
                    say=lambda _message: None,
                ),
                answers,
            )
        self.session.goal_text = ""
        self.session.phase = "daily"
        self.session.add_message(
            "assistant",
            "Your goal is saved and your plan is ready to build. How are you feeling today? "
            "Include sleep, energy, stress, soreness or pain, and nutrition.",
        )

    def _parse_goal(self, text: str) -> dict[str, Any]:
        with database_connection() as connection:
            runtime = build_runtime(connection)
            return self._parse_goal_with_parser(text, runtime["goal_parser"])

    @staticmethod
    def _parse_goal_with_parser(text: str, parser: Any) -> dict[str, Any]:
        try:
            parsed = parser.parse(text)
            duration = parsed.get("plan_duration_weeks")
            if duration is not None and (not isinstance(duration, int) or duration <= 0):
                raise ValueError("invalid duration")
            return parsed
        except Exception:
            return parse_training_goal(text)

    def _handle_daily_message(self, message: str) -> None:
        with database_connection() as connection:
            runtime = build_runtime(connection, include_agent=True)
            profile = runtime["profiles"].find_by_user_id(self.session.user["id"])
            assessment = assess_safety(message, profile=profile)
            if assessment["highest_severity"] in {"urgent", "blocked"}:
                self.session.add_message("assistant", assessment["reason"])
                return
            if self.session.awaiting_printable_plan:
                try:
                    printable = runtime["chat_language"].classify_printable_plan_reply(message)
                except Exception:
                    printable = {"intent": "unclear", "response": ""}
                if printable["intent"] == "accept":
                    self.session.awaiting_printable_plan = False
                    self._add_plan_download(
                        self.session.pending_printable_plan,
                        self.session.download_ready_message,
                        plans=runtime["plans"],
                    )
                    return
                if printable["intent"] == "decline":
                    self.session.awaiting_printable_plan = False
                    self.session.pending_printable_plan = None
                    self.session.download_ready_message = ""
                    self.session.add_message("assistant", printable["response"])
                    return
            plan = self._plan_for_reference_date(runtime, date.today())
            is_initial_plan_checkin = plan is None
            response_context = self._daily_phase_context(profile, plan)
            intent_context = self._intent_context(plan)
            intent_context["awaiting_printable_plan"] = self.session.awaiting_printable_plan
            try:
                outcome = runtime["chat_language"].classify_daily_phase_message(
                    message, context=intent_context
                )
            except Exception:
                logger.exception(
                    "Daily intent classification failed (phase=%s, has_active_plan=%s)",
                    self.session.phase,
                    plan is not None,
                )
                self.session.add_message(
                    "assistant",
                    "I could not reliably interpret that yet. Please share a check-in with sleep, energy, soreness or pain, and whether you completed today's workout; or ask for a specific plan view.",
                )
                return

            if outcome["intent"] in {"current_week_plan", "specific_session"}:
                self._show_current_week_plan(
                    runtime,
                    requested_day_lookup=outcome["intent"] == "specific_session",
                    offer_download=outcome["plan_delivery"] != "chat",
                )
                return
            if outcome["intent"] == "remaining_plan":
                self._show_remaining_week_plan(runtime)
                return
            if outcome["intent"] == "next_week":
                authorization = self._authorize_action(
                    runtime, message, proposed_action="next_week", context=intent_context
                )
                if authorization["decision"] != "confirm":
                    self.session.add_message("assistant", authorization["response"])
                    return
                self._release_next_week_plan(runtime)
                return
            if outcome["intent"] == "plan_export":
                authorization = self._authorize_action(
                    runtime, message, proposed_action="plan_export", context=intent_context
                )
                if authorization["decision"] != "confirm":
                    self.session.add_message("assistant", authorization["response"])
                    return
                if plan is None:
                    self.session.add_message("assistant", "There is no active workout plan to export yet.")
                    return
                presentation = runtime["plan_presenter"].generate(plan, {})
                self._add_plan_download(plan, presentation["download_ready"], plans=runtime["plans"])
                return
            if outcome["intent"] == "printable_accept" and self.session.awaiting_printable_plan:
                self.session.awaiting_printable_plan = False
                self._add_plan_download(
                    self.session.pending_printable_plan,
                    self.session.download_ready_message,
                    plans=runtime["plans"],
                )
                return
            if outcome["intent"] == "printable_decline" and self.session.awaiting_printable_plan:
                self.session.awaiting_printable_plan = False
                self.session.pending_printable_plan = None
                self.session.download_ready_message = ""
                self.session.add_message("assistant", outcome["response"])
                return
            if outcome["intent"] != "daily_checkin":
                self._answer_daily_phase_question(runtime, message, response_context, outcome["response"])
                return
            try:
                requested_repair_dates = self._requested_repair_dates(runtime, plan, message)
            except (RepairTargetParseError, WorkoutRepairTargetError) as error:
                self.session.add_message("assistant", str(error))
                return
            authorization = self._authorize_action(
                runtime, message, proposed_action="daily_checkin", context=intent_context
            )
            if authorization["decision"] != "confirm":
                self.session.add_message("assistant", authorization["response"])
                return
            if (
                authorization["workout_today"] == "unknown"
                and not is_initial_plan_checkin
                and not requested_repair_dates
            ):
                self.session.add_message(
                    "assistant",
                    "Before I save today’s check-in, are you planning to train today?",
                )
                return

            result = runtime["agent"].run_daily_flow(
                self.session.user,
                workout_today=(
                    True
                    if is_initial_plan_checkin
                    else authorization["workout_today"] == "yes"
                ),
                requested_repair_dates=requested_repair_dates,
                ask=lambda _prompt: message,
                say=lambda _message: None,
            )
            plan = self._plan_for_reference_date(runtime, date.today())
            if plan is None:
                self.session.add_message("assistant", format_daily_result(result))
                return
            if requested_repair_dates and result["action"] == "repair_applied":
                self.session.add_message(
                    "assistant", self._repair_status_message(plan, requested_repair_dates)
                )
            follow_up_intent = outcome.get("follow_up_intent", "none")
            if follow_up_intent != "none":
                self.session.add_message("assistant", format_daily_result(result))
                self._show_confirmed_checkin_follow_up(
                    runtime,
                    message,
                    intent_context,
                    follow_up_intent,
                    outcome["plan_delivery"],
                )
                return
            if result["action"] not in {"plan_ready", "repair_applied"}:
                self.session.add_message("assistant", format_daily_result(result))
                return
            presentation = runtime["plan_presenter"].generate(plan, result["readiness"])

        self.session.add_message("assistant", format_daily_result(result))
        self.session.add_message(
            "assistant",
            presentation["introduction"],
            plan=plan,
            as_of_date=str(result["checkin"].get("checkin_date") or ""),
            print_question=presentation["print_question"],
        )
        self.session.awaiting_printable_plan = True
        self.session.pending_printable_plan = plan
        self.session.download_ready_message = presentation["download_ready"]

    @staticmethod
    def _daily_phase_context(profile: dict[str, Any] | None, plan: dict[str, Any] | None) -> dict[str, Any]:
        plan_json = (plan or {}).get("plan_json") or {}
        return {
            "has_active_plan": plan is not None,
            "awaiting_printable_plan": False,
            "profile": profile or {},
            "week_start": plan_json.get("week_start"),
            "sessions": plan_json.get("sessions") or [],
        }

    @staticmethod
    def _intent_context(plan: dict[str, Any] | None) -> dict[str, Any]:
        """Keep semantic routing within Ollama's reliable context window."""
        plan_json = (plan or {}).get("plan_json") or {}
        sessions = []
        for session in plan_json.get("sessions") or []:
            sessions.append(
                {
                    key: session[key]
                    for key in ("scheduled_date", "day", "focus", "exercises")
                    if key in session
                }
            )
        return {
            "has_active_plan": plan is not None,
            "awaiting_printable_plan": False,
            "week_start": plan_json.get("week_start"),
            "sessions": sessions,
        }

    @staticmethod
    def _requested_repair_dates(
        runtime: dict[str, Any], plan: dict[str, Any] | None, message: str
    ) -> list[str]:
        """Resolve semantic repair references only against the active plan."""
        parser = runtime.get("repair_target_parser")
        if parser is None or plan is None:
            return []
        references = parser.parse(message)
        return resolve_repair_target_dates(
            references, (plan.get("plan_json") or {}).get("sessions") or []
        )

    @staticmethod
    def _repair_status_message(plan: dict[str, Any], target_dates: list[str]) -> str:
        labels = {
            str(session.get("scheduled_date")): str(session.get("day") or "Workout")
            for session in (plan.get("plan_json") or {}).get("sessions") or []
        }
        changed = [f"{labels.get(target_date, 'Workout')} ({target_date})" for target_date in target_dates]
        return f"Updated only: {' and '.join(changed)}. The rest of this week is unchanged."

    def _plan_for_reference_date(
        self,
        runtime: dict[str, Any],
        reference_date: date,
        *,
        fallback_on_miss: bool = True,
    ) -> dict[str, Any] | None:
        active_plan = runtime["plans"].find_active_by_user_id(self.session.user["id"])
        return find_plan_for_date(
            runtime["plans"],
            user_id=self.session.user["id"],
            reference_date=reference_date,
            fallback_plan=active_plan,
            fallback_on_miss=fallback_on_miss,
        )

    @staticmethod
    def _authorize_action(
        runtime: dict[str, Any],
        message: str,
        *,
        proposed_action: str,
        context: dict[str, Any],
    ) -> dict[str, str]:
        """Turn an Ollama proposal into a separately authorized application action."""
        try:
            return runtime["chat_language"].authorize_action(
                message,
                proposed_action=proposed_action,
                context=context,
            )
        except Exception:
            return {
                "decision": "clarify",
                "workout_today": "unknown",
                "response": "I need to confirm that request before I update your plan or record.",
            }

    def _show_confirmed_checkin_follow_up(
        self,
        runtime: dict[str, Any],
        message: str,
        context: dict[str, Any],
        follow_up_intent: str,
        plan_delivery: str,
    ) -> None:
        """Perform one explicit read/view request after a saved check-in."""
        if follow_up_intent in {"current_week_plan", "specific_session"}:
            self._show_current_week_plan(
                runtime,
                requested_day_lookup=follow_up_intent == "specific_session",
                offer_download=plan_delivery == "download",
            )
            return
        if follow_up_intent == "remaining_plan":
            self._show_remaining_week_plan(runtime)
            return
        if follow_up_intent == "next_week":
            authorization = self._authorize_action(
                runtime, message, proposed_action="next_week", context=context
            )
            if authorization["decision"] == "confirm":
                self._release_next_week_plan(runtime)
            else:
                self.session.add_message("assistant", authorization["response"])

    def _answer_daily_phase_question(
        self,
        runtime: dict[str, Any],
        message: str,
        context: dict[str, Any],
        fallback: str,
    ) -> None:
        context["awaiting_printable_plan"] = self.session.awaiting_printable_plan
        try:
            response = runtime["chat_language"].answer_daily_phase_question(
                message, context=context
            )
        except Exception:
            response = fallback
        self.session.add_message("assistant", response)

    def _show_current_week_plan(
        self,
        runtime: dict[str, Any],
        *,
        requested_day_lookup: bool = False,
        offer_download: bool = True,
    ) -> None:
        plan = self._plan_for_reference_date(runtime, date.today())
        if plan is None:
            self.session.add_message(
                "assistant", "There is no active workout plan yet. Share today’s check-in first."
            )
            return
        week_start = str((plan.get("plan_json") or {}).get("week_start") or "")
        message = "Here is the full current week workout plan for reference."
        if requested_day_lookup:
            message = "Here is the full current week workout plan, including earlier days."
        metadata = {
            "plan": plan,
            "as_of_date": week_start,
            "plan_view": "full_week",
        }
        if offer_download:
            metadata["print_question"] = "Do you want a printable or downloadable workout plan?"
        self.session.add_message("assistant", message, **metadata)
        self.session.awaiting_printable_plan = offer_download
        self.session.pending_printable_plan = plan if offer_download else None

    def _show_remaining_week_plan(self, runtime: dict[str, Any]) -> None:
        plan = self._plan_for_reference_date(runtime, date.today())
        if plan is None:
            self.session.add_message("assistant", "There is no active workout plan yet.")
            return
        self.session.add_message(
            "assistant",
            "Here are the remaining planned workouts for the current week.",
            plan=plan,
            print_question="Do you want a printable or downloadable workout plan?",
        )
        self.session.awaiting_printable_plan = True
        self.session.pending_printable_plan = plan

    def _release_next_week_plan(self, runtime: dict[str, Any]) -> None:
        next_plan = self._plan_for_reference_date(
            runtime, date.today() + timedelta(days=7), fallback_on_miss=False
        )
        if next_plan is not None:
            presentation = runtime["plan_presenter"].generate(next_plan, {})
            self.session.add_message(
                "assistant",
                presentation["introduction"],
                plan=next_plan,
                as_of_date=str((next_plan.get("plan_json") or {}).get("week_start") or ""),
                print_question=presentation["print_question"],
            )
            self.session.awaiting_printable_plan = True
            self.session.pending_printable_plan = next_plan
            self.session.download_ready_message = presentation["download_ready"]
            return
        outcome = runtime["agent"].plan_service.release_next_week(
            self.session.user, say=lambda _message: None
        )
        if outcome == "program_complete":
            self.session.add_message(
                "assistant",
                "You have completed the requested program duration. Would you like to start a new program or revise your goal?",
            )
            return
        if outcome == "no_active_plan":
            self.session.add_message(
                "assistant", "There is no current week to advance yet. Share a daily check-in first."
            )
            return
        plan = self._plan_for_reference_date(
            runtime, date.today() + timedelta(days=7), fallback_on_miss=False
        )
        if plan is None:
            plan = runtime["plans"].find_active_by_user_id(self.session.user["id"])
        presentation = runtime["plan_presenter"].generate(plan, {})
        self.session.add_message(
            "assistant",
            presentation["introduction"],
            plan=plan,
            as_of_date=str((plan.get("plan_json") or {}).get("week_start") or ""),
            print_question=presentation["print_question"],
        )
        self.session.awaiting_printable_plan = True
        self.session.pending_printable_plan = plan
        self.session.download_ready_message = presentation["download_ready"]

    def _add_plan_download(
        self,
        plan: dict[str, Any] | None,
        message: str,
        *,
        plans: Any | None = None,
    ) -> None:
        if plan is None or self.session.user is None:
            raise RuntimeError("There is no workout plan ready to download.")
        filename = f"{self.session.user['display_name'].lower().replace(' ', '_')}_workout_plan.xlsx"
        workbook_bytes = export_sessions_workbook_bytes(plan)
        storage = S3WorkoutPlanStorage.from_environment()
        if storage is not None:
            object_key = storage.upload_workbook(
                workbook_bytes,
                user_id=str(self.session.user["id"]),
                plan_id=str(plan["id"]),
                filename=filename,
            )
            if plans is not None:
                plans.update_export_s3_key(plan["id"], object_key)
            (plan.setdefault("plan_json", {}))["export_s3_key"] = object_key
            self.session.add_message(
                "assistant",
                message,
                download_url=storage.create_download_url(object_key, filename),
                filename=filename,
            )
            return
        self.session.add_message(
            "assistant",
            message,
            download=workbook_bytes,
            filename=filename,
        )

    @staticmethod
    def _landing_welcome() -> dict[str, str]:
        return OllamaChatLanguage(OllamaClient()).generate_landing_welcome()

    def _next_profile_prompt(self, display_name: str, is_new_user: bool) -> str:
        key, requirement = PROFILE_QUESTIONS[len(self.session.profile_answers)]
        return OllamaChatLanguage(OllamaClient()).generate_onboarding_message(
            display_name=display_name,
            is_new_user=is_new_user,
            field_key=key,
            field_requirement=requirement,
        )


def _run_with_answers(operation: Callable[[Callable[[str], str]], Any], answers: list[str]) -> Any:
    queued_answers = deque(answers)

    def ask(_prompt: str) -> str:
        if not queued_answers:
            raise RuntimeError("The chat needs another answer before this step can be saved.")
        return queued_answers.popleft()

    return operation(ask)


def _validate_profile_answer(key: str, answer: str) -> str | None:
    if not answer:
        return "Please enter a response so I can continue."
    if key in {"age", "height_cm", "starting_weight_kg"}:
        try:
            if float(answer) <= 0:
                raise ValueError
        except ValueError:
            return "Please enter a positive number."
    if key == "bmr_formula_profile" and answer.lower() not in {"male", "female"}:
        return "Please answer male or female for the BMR formula profile."
    return None


def _friendly_error(error: Exception) -> str:
    message = str(error)
    if isinstance(error, WorkoutPlanStorageError):
        return message
    if "DATABASE_URL" in message:
        return "I cannot connect to the fitness database yet. Start the app with DATABASE_URL set in PowerShell."
    if "Connection" in message or "connection" in message:
        return "I could not reach the fitness database right now. Please check the connection and try again."
    return "I could not complete that update. Please try again with a little more detail."


def _is_transient_database_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        phrase in message
        for phrase in (
            "connection closed unexpectedly",
            "connection has been closed unexpectedly",
            "connection reset",
            "forcibly closed by the remote host",
            "server closed the connection unexpectedly",
        )
    )
