"""Streamlit chat interface for the adaptive fitness agent."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import html
import os
from pathlib import Path
from typing import Any, Callable

import streamlit as st

from src.agent_flow import AdaptiveFitnessAgent
from src.cockroach_agent_decision_repository import CockroachAgentDecisionRepository
from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository
from src.cockroach_nutrition_target_repository import CockroachNutritionTargetRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.fitness_chat import (
    PROFILE_QUESTIONS,
    format_daily_result,
    is_plan_export_request,
    plan_table_rows,
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
from src.m4_adaptive_checkin import AdaptiveCheckinService
from src.m6_hybrid_workout_plan import HybridWorkoutPlanService
from src.m6_vector_preflight import verify_embedding_dimension
from src.m7_plan_repair import PlanRepairService
from src.m8_nutrition_service import NutritionTargetService
from src.m9_decision_log import DecisionLogService
from src.ollama_checkin_parser import OllamaCheckinParser
from src.ollama_client import OllamaClient
from src.ollama_chat_language import OllamaChatLanguage
from src.ollama_nutrition_note_generator import OllamaNutritionNoteGenerator
from src.ollama_plan_repair_generator import OllamaPlanRepairGenerator
from src.ollama_plan_presentation import OllamaPlanPresentationGenerator
from src.ollama_workout_plan_generator import OllamaWorkoutPlanGenerator
from src.workout_plan_excel_export import export_sessions_workbook_bytes


PROJECT_ROOT = Path(__file__).resolve().parent
MIGRATIONS = (
    "sql/001_create_users.sql",
    "sql/002_create_user_profiles.sql",
    "sql/003_create_goals.sql",
    "sql/004_create_daily_checkins.sql",
    "sql/005_create_workout_plans.sql",
    "sql/006_upgrade_module6_hybrid.sql",
    "sql/007_create_agent_decisions.sql",
    "sql/008_create_nutrition_targets.sql",
    "sql/009_upgrade_profiles_for_nutrition.sql",
    "sql/010_upgrade_agent_decisions_module9.sql",
    "sql/011_create_fitness_knowledge.sql",
)


def main() -> None:
    st.set_page_config(page_title="Fitness Agent", page_icon="FA", layout="centered")
    _apply_styles()
    _initialize_state()

    st.markdown("<h1 class='agent-title'>Fitness Agent</h1>", unsafe_allow_html=True)
    _render_messages()

    prompt = st.chat_input("Message Fitness Agent")
    if prompt:
        _add_message("user", prompt)
        try:
            _handle_message(prompt)
        except Exception as error:
            _add_message("assistant", _friendly_error(error))
        st.rerun()


def _initialize_state() -> None:
    if "messages" in st.session_state:
        return
    st.session_state.messages = []
    st.session_state.phase = "identity"
    st.session_state.user = None
    st.session_state.profile_answers = {}
    st.session_state.goal_text = ""
    st.session_state.awaiting_printable_plan = False
    st.session_state.pending_printable_plan = None
    st.session_state.download_ready_message = ""
    _add_message("assistant", _name_prompt())


def _handle_message(message: str) -> None:
    phase = st.session_state.phase
    if phase == "identity":
        _handle_identity(message)
    elif phase == "profile":
        _handle_profile_answer(message)
    elif phase == "goal":
        _handle_goal(message)
    elif phase == "goal_follow_up":
        _save_goal([st.session_state.goal_text, message])
    else:
        _handle_daily_message(message)


def _handle_identity(display_name: str) -> None:
    with _database_connection() as connection:
        runtime = _build_runtime(connection)
        identity = UserIdentityService(runtime["users"]).get_or_create_user(display_name)
        st.session_state.user = identity.user
        profile = runtime["profiles"].find_by_user_id(identity.user["id"])
        goal = runtime["goals"].find_active_by_user_id(identity.user["id"])

    if profile is None:
        st.session_state.phase = "profile"
        _add_message(
            "assistant",
            _next_profile_prompt(identity.user["display_name"], identity.created),
        )
        return
    if goal is None:
        st.session_state.phase = "goal"
        _add_message("assistant", f"Welcome back, {identity.user['display_name']}. {GENERAL_GOAL_PROMPT}")
        return

    st.session_state.phase = "daily"
    _add_message(
        "assistant",
        f"Welcome back, {identity.user['display_name']}. Have you stayed active today? "
        "Tell me about sleep, energy, soreness, pain, food, and whether you plan to train.",
    )


def _handle_profile_answer(answer: str) -> None:
    index = len(st.session_state.profile_answers)
    key, _prompt = PROFILE_QUESTIONS[index]
    cleaned = answer.strip()
    error = _validate_profile_answer(key, cleaned)
    if error:
        _add_message("assistant", error)
        return

    st.session_state.profile_answers[key] = cleaned
    if len(st.session_state.profile_answers) < len(PROFILE_QUESTIONS):
        _add_message("assistant", _next_profile_prompt(st.session_state.user["display_name"], False))
        return

    with _database_connection() as connection:
        runtime = _build_runtime(connection)
        _run_with_answers(
            lambda ask: StaticProfileService(runtime["profiles"]).run_onboarding(
                st.session_state.user, ask=ask, say=lambda _message: None
            ),
            profile_answers_to_queue(st.session_state.profile_answers),
        )
    st.session_state.phase = "goal"
    _add_message("assistant", f"Your profile is saved. {GENERAL_GOAL_PROMPT}")


def _handle_goal(answer: str) -> None:
    parsed = parse_training_goal(answer)
    missing = parsed["goal_details"]["missing_fields"]
    if missing:
        st.session_state.goal_text = answer
        st.session_state.phase = "goal_follow_up"
        _add_message("assistant", build_follow_up_prompt(missing))
        return
    _save_goal([answer])


def _save_goal(answers: list[str]) -> None:
    with _database_connection() as connection:
        runtime = _build_runtime(connection)
        _run_with_answers(
            lambda ask: TrainingGoalService(runtime["goals"]).run_goal_setup(
                st.session_state.user, ask=ask, say=lambda _message: None
            ),
            answers,
        )
    st.session_state.goal_text = ""
    st.session_state.phase = "daily"
    _add_message(
        "assistant",
        "Your goal is saved and your plan is ready to build. How are you feeling today? "
        "Include sleep, energy, stress, soreness or pain, nutrition, and whether you plan to train.",
    )


def _handle_daily_message(message: str) -> None:
    with _database_connection() as connection:
        runtime = _build_runtime(connection, include_agent=True)
        if st.session_state.awaiting_printable_plan:
            outcome = runtime["chat_language"].classify_printable_plan_reply(message)
            if outcome["intent"] == "accept":
                st.session_state.awaiting_printable_plan = False
                _add_plan_download(
                    st.session_state.pending_printable_plan,
                    st.session_state.download_ready_message,
                )
                return
            _add_message("assistant", outcome["response"])
            if outcome["intent"] == "decline":
                st.session_state.awaiting_printable_plan = False
                st.session_state.pending_printable_plan = None
                st.session_state.download_ready_message = ""
            return
        if is_plan_export_request(message):
            plan = runtime["plans"].find_active_by_user_id(st.session_state.user["id"])
            if plan is None:
                _add_message("assistant", "There is no active workout plan to export yet. Share today’s check-in first.")
                return
            presentation = runtime["plan_presenter"].generate(plan, {})
            _add_plan_download(plan, presentation["download_ready"])
            return

        result = runtime["agent"].run_daily_flow(
            st.session_state.user,
            workout_today=_mentions_training_today(message),
            ask=lambda _prompt: message,
            say=lambda _message: None,
        )
        plan = runtime["plans"].find_active_by_user_id(st.session_state.user["id"])
        if plan is None:
            _add_message("assistant", format_daily_result(result))
            return
        presentation = runtime["plan_presenter"].generate(plan, result["readiness"])

    _add_message("assistant", format_daily_result(result))
    _add_message(
        "assistant",
        presentation["introduction"],
        plan=plan,
        print_question=presentation["print_question"],
    )
    st.session_state.awaiting_printable_plan = True
    st.session_state.pending_printable_plan = plan
    st.session_state.download_ready_message = presentation["download_ready"]


def _build_runtime(connection: Any, *, include_agent: bool = False) -> dict[str, Any]:
    _apply_migrations(connection)
    users = CockroachUserRepository(connection)
    profiles = CockroachStaticProfileRepository(connection)
    goals = CockroachGoalRepository(connection)
    checkins = CockroachCheckinRepository(connection)
    plans = CockroachWorkoutPlanRepository(connection)
    nutrition = CockroachNutritionTargetRepository(connection)
    decisions = CockroachAgentDecisionRepository(connection)
    decision_log = DecisionLogService(decisions)
    runtime = {
        "users": users,
        "profiles": profiles,
        "goals": goals,
        "plans": plans,
    }
    ollama = OllamaClient()
    runtime["chat_language"] = OllamaChatLanguage(ollama)
    if not include_agent:
        return runtime

    memories = CockroachMemoryEmbeddingRepository(connection)
    verify_embedding_dimension(ollama, memories)
    runtime["agent"] = AdaptiveFitnessAgent(
            checkin_service=AdaptiveCheckinService(checkins, OllamaCheckinParser(ollama)),
            checkin_repository=checkins,
            plan_repository=plans,
            decision_log=decision_log,
            plan_service=HybridWorkoutPlanService(
                profile_repository=profiles,
                goal_repository=goals,
                checkin_repository=checkins,
                plan_repository=plans,
                memory_repository=memories,
                embedder=ollama,
                plan_generator=OllamaWorkoutPlanGenerator(ollama),
                decision_log=decision_log,
            ),
            repair_service=PlanRepairService(
                profile_repository=profiles,
                goal_repository=goals,
                checkin_repository=checkins,
                plan_repository=plans,
                decision_repository=decisions,
                decision_log=decision_log,
                memory_repository=memories,
                embedder=ollama,
                repair_generator=OllamaPlanRepairGenerator(ollama),
            ),
            nutrition_service=NutritionTargetService(
                profile_repository=profiles,
                goal_repository=goals,
                checkin_repository=checkins,
                plan_repository=plans,
                nutrition_repository=nutrition,
                note_generator=OllamaNutritionNoteGenerator(ollama),
                decision_log=decision_log,
            ),
        )
    runtime["plan_presenter"] = OllamaPlanPresentationGenerator(ollama)
    return runtime


@contextmanager
def _database_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Start Streamlit from a PowerShell window where it is set.")
    try:
        import psycopg2
    except ModuleNotFoundError as error:
        raise RuntimeError("psycopg2 is not installed. Run pip install -r requirements.txt.") from error

    with psycopg2.connect(database_url) as connection:
        yield connection


def _apply_migrations(connection: Any) -> None:
    with connection.cursor() as cursor:
        for migration in MIGRATIONS:
            cursor.execute((PROJECT_ROOT / migration).read_text(encoding="utf-8"))
    connection.commit()


def _run_with_answers(operation: Callable[[Callable[[str], str]], Any], answers: list[str]) -> Any:
    queued_answers = deque(answers)

    def ask(_prompt: str) -> str:
        if not queued_answers:
            raise RuntimeError("The chat needs another answer before this step can be saved.")
        return queued_answers.popleft()

    return operation(ask)


def _name_prompt() -> str:
    return OllamaChatLanguage(OllamaClient()).generate_onboarding_message(
        display_name="",
        is_new_user=True,
        field_key="display_name",
        field_requirement="the name the person would like Fitness Agent to use",
    )


def _next_profile_prompt(display_name: str, is_new_user: bool) -> str:
    key, requirement = PROFILE_QUESTIONS[len(st.session_state.profile_answers)]
    return OllamaChatLanguage(OllamaClient()).generate_onboarding_message(
        display_name=display_name,
        is_new_user=is_new_user,
        field_key=key,
        field_requirement=requirement,
    )


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


def _add_message(role: str, content: str, **metadata: Any) -> None:
    st.session_state.messages.append({"role": role, "content": content, **metadata})


def _add_plan_download(plan: dict[str, Any], message: str) -> None:
    _add_message(
        "assistant",
        message,
        download=export_sessions_workbook_bytes(plan),
        filename=f"{st.session_state.user['display_name'].lower().replace(' ', '_')}_workout_plan.xlsx",
    )


def _render_messages() -> None:
    for index, message in enumerate(st.session_state.messages):
        role = message["role"]
        content = html.escape(message["content"]).replace("\n", "<br>")
        css_class = "user-bubble" if role == "user" else "assistant-bubble"
        st.markdown(f"<div class='{css_class}'>{content}</div>", unsafe_allow_html=True)
        if message.get("plan"):
            st.table(plan_table_rows(message["plan"]))
        if message.get("print_question"):
            question = html.escape(message["print_question"])
            st.markdown(f"<div class='assistant-bubble'>{question}</div>", unsafe_allow_html=True)
        if message.get("download"):
            st.download_button(
                "Download workout plan (.xlsx)",
                data=message["download"],
                file_name=message["filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download-{index}-{message['filename']}",
            )


def _friendly_error(error: Exception) -> str:
    message = str(error)
    if "DATABASE_URL" in message:
        return "I cannot connect to the fitness database yet. Start the app with DATABASE_URL set in PowerShell."
    if "Connection" in message or "connection" in message:
        return "I could not reach the fitness database right now. Please check the connection and try again."
    return "I could not complete that update. Please try again with a little more detail."


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container { max-width: 760px; padding-top: 2.2rem; padding-bottom: 7rem; }
            .agent-title { font-size: 1.45rem; font-weight: 700; margin: 0 0 1.8rem; color: #18303c; }
            .assistant-bubble, .user-bubble {
                width: fit-content; max-width: 82%; padding: 0.75rem 0.9rem; margin: 0.55rem 0;
                border-radius: 8px; line-height: 1.5; font-size: 0.96rem;
            }
            .assistant-bubble { background: #f2f5f6; color: #1e2b32; margin-right: auto; }
            .user-bubble { background: #0f766e; color: #ffffff; margin-left: auto; }
            [data-testid='stChatInput'] { position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%); width: min(760px, calc(100% - 2rem)); }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
