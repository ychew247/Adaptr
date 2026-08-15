"""UI-neutral construction of the connected adaptive-fitness agent runtime."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any

from src.agent_flow import AdaptiveFitnessAgent
from src.cockroach_agent_decision_repository import CockroachAgentDecisionRepository
from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository
from src.cockroach_nutrition_target_repository import CockroachNutritionTargetRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.m4_adaptive_checkin import AdaptiveCheckinService
from src.m6_hybrid_workout_plan import HybridWorkoutPlanService
from src.m6_vector_preflight import verify_embedding_dimension
from src.m7_plan_repair import PlanRepairService
from src.m8_nutrition_service import NutritionTargetService
from src.m9_decision_log import DecisionLogService
from src.ollama_checkin_parser import OllamaCheckinParser
from src.ollama_chat_language import OllamaChatLanguage
from src.ollama_client import OllamaClient
from src.ollama_goal_parser import OllamaGoalParser
from src.ollama_nutrition_note_generator import OllamaNutritionNoteGenerator
from src.ollama_plan_presentation import OllamaPlanPresentationGenerator
from src.ollama_plan_repair_generator import OllamaPlanRepairGenerator
from src.ollama_workout_plan_generator import OllamaWorkoutPlanGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


@contextmanager
def database_connection():
    database_url = configured_database_url()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL or COCKROACH_URL is not set. Start the app from a PowerShell window where it is set."
        )
    try:
        import psycopg2
    except ModuleNotFoundError as error:
        raise RuntimeError("psycopg2 is not installed. Run pip install -r requirements.txt.") from error

    with psycopg2.connect(database_url) as connection:
        yield connection


def configured_database_url() -> str | None:
    """Support the names commonly used by local CockroachDB setup commands."""
    return os.getenv("DATABASE_URL") or os.getenv("COCKROACH_URL")


def build_runtime(connection: Any, *, include_agent: bool = False) -> dict[str, Any]:
    _apply_migrations(connection)
    users = CockroachUserRepository(connection)
    profiles = CockroachStaticProfileRepository(connection)
    goals = CockroachGoalRepository(connection)
    checkins = CockroachCheckinRepository(connection)
    plans = CockroachWorkoutPlanRepository(connection)
    nutrition = CockroachNutritionTargetRepository(connection)
    decisions = CockroachAgentDecisionRepository(connection)
    decision_log = DecisionLogService(decisions)
    ollama = OllamaClient()
    runtime = {
        "users": users,
        "profiles": profiles,
        "goals": goals,
        "plans": plans,
        "chat_language": OllamaChatLanguage(ollama),
        "goal_parser": OllamaGoalParser(ollama),
    }
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


def _apply_migrations(connection: Any) -> None:
    with connection.cursor() as cursor:
        for migration in MIGRATIONS:
            cursor.execute((PROJECT_ROOT / migration).read_text(encoding="utf-8"))
    connection.commit()
