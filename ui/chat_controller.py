"""NiceGUI-facing controller that delegates fitness work to existing services."""

from __future__ import annotations

from collections import deque
from typing import Any, Callable

from src.fitness_agent_runtime import build_runtime, database_connection
from src.fitness_chat import (
    PROFILE_QUESTIONS,
    format_daily_result,
    is_plan_export_request,
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
from src.ollama_chat_language import OllamaChatLanguage
from src.ollama_client import OllamaClient
from src.workout_plan_excel_export import export_sessions_workbook_bytes
from ui.chat_state import ChatSession


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
        try:
            self._route_message(message)
            self.session.status = "Ready"
        except Exception as error:
            self.session.add_message("assistant", _friendly_error(error))
            self.session.status = "Needs attention"

    def _route_message(self, message: str) -> None:
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
        parsed = parse_training_goal(answer)
        missing = parsed["goal_details"]["missing_fields"]
        if missing:
            self.session.goal_text = answer
            self.session.phase = "goal_follow_up"
            self.session.add_message("assistant", build_follow_up_prompt(missing))
            return
        self._save_goal([answer])

    def _save_goal(self, answers: list[str]) -> None:
        with database_connection() as connection:
            runtime = build_runtime(connection)
            _run_with_answers(
                lambda ask: TrainingGoalService(runtime["goals"]).run_goal_setup(
                    self.session.user, ask=ask, say=lambda _message: None
                ),
                answers,
            )
        self.session.goal_text = ""
        self.session.phase = "daily"
        self.session.add_message(
            "assistant",
            "Your goal is saved and your plan is ready to build. How are you feeling today? "
            "Include sleep, energy, stress, soreness or pain, nutrition, and whether you plan to train.",
        )

    def _handle_daily_message(self, message: str) -> None:
        with database_connection() as connection:
            runtime = build_runtime(connection, include_agent=True)
            if self.session.awaiting_printable_plan:
                outcome = runtime["chat_language"].classify_printable_plan_reply(message)
                if outcome["intent"] == "accept":
                    self.session.awaiting_printable_plan = False
                    self._add_plan_download(
                        self.session.pending_printable_plan,
                        self.session.download_ready_message,
                    )
                    return
                self.session.add_message("assistant", outcome["response"])
                if outcome["intent"] == "decline":
                    self.session.awaiting_printable_plan = False
                    self.session.pending_printable_plan = None
                    self.session.download_ready_message = ""
                return

            if is_plan_export_request(message):
                plan = runtime["plans"].find_active_by_user_id(self.session.user["id"])
                if plan is None:
                    self.session.add_message(
                        "assistant", "There is no active workout plan yet. Share today’s check-in first."
                    )
                    return
                presentation = runtime["plan_presenter"].generate(plan, {})
                self._add_plan_download(plan, presentation["download_ready"])
                return

            result = runtime["agent"].run_daily_flow(
                self.session.user,
                workout_today=_mentions_training_today(message),
                ask=lambda _prompt: message,
                say=lambda _message: None,
            )
            plan = runtime["plans"].find_active_by_user_id(self.session.user["id"])
            if plan is None:
                self.session.add_message("assistant", format_daily_result(result))
                return
            presentation = runtime["plan_presenter"].generate(plan, result["readiness"])

        self.session.add_message("assistant", format_daily_result(result))
        self.session.add_message(
            "assistant",
            presentation["introduction"],
            plan=plan,
            print_question=presentation["print_question"],
        )
        self.session.awaiting_printable_plan = True
        self.session.pending_printable_plan = plan
        self.session.download_ready_message = presentation["download_ready"]

    def _add_plan_download(self, plan: dict[str, Any] | None, message: str) -> None:
        if plan is None or self.session.user is None:
            raise RuntimeError("There is no workout plan ready to download.")
        filename = f"{self.session.user['display_name'].lower().replace(' ', '_')}_workout_plan.xlsx"
        self.session.add_message(
            "assistant",
            message,
            download=export_sessions_workbook_bytes(plan),
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


def _mentions_training_today(message: str) -> bool:
    normalized = message.lower()
    no_training = ("no workout", "not training", "rest day", "won't train", "wont train")
    if any(phrase in normalized for phrase in no_training):
        return False
    return any(word in normalized for word in ("workout", "training", "train", "gym", "session"))


def _friendly_error(error: Exception) -> str:
    message = str(error)
    if "DATABASE_URL" in message:
        return "I cannot connect to the fitness database yet. Start the app with DATABASE_URL set in PowerShell."
    if "Connection" in message or "connection" in message:
        return "I could not reach the fitness database right now. Please check the connection and try again."
    return "I could not complete that update. Please try again with a little more detail."
