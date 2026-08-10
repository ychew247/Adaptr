import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_agent_decision_repository import CockroachAgentDecisionRepository
from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.m1_user_identity import UserIdentityService
from src.m6_vector_preflight import verify_embedding_dimension
from src.m7_plan_repair import PlanRepairService
from src.ollama_client import OllamaClient
from src.ollama_plan_repair_generator import OllamaPlanRepairGenerator


MIGRATIONS = [
    "sql/001_create_users.sql",
    "sql/002_create_user_profiles.sql",
    "sql/003_create_goals.sql",
    "sql/004_create_daily_checkins.sql",
    "sql/005_create_workout_plans.sql",
    "sql/006_upgrade_module6_hybrid.sql",
    "sql/007_create_agent_decisions.sql",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="Alex")
    parser.add_argument("--trigger")
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    if args.skip_live:
        print("Module 7 plan repair demo imports successfully.")
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    try:
        import psycopg2
    except ModuleNotFoundError as error:
        raise RuntimeError("psycopg2 is not installed. Run: pip install -r requirements.txt") from error

    with psycopg2.connect(database_url) as connection:
        _apply_migrations(connection)
        user = UserIdentityService(CockroachUserRepository(connection)).get_or_create_user(
            args.user
        ).user
        ollama_client = OllamaClient()
        memory_repository = CockroachMemoryEmbeddingRepository(connection)
        verify_embedding_dimension(ollama_client, memory_repository)
        trigger = args.trigger or input("What changed and needs a workout-plan repair? ")
        PlanRepairService(
            profile_repository=CockroachStaticProfileRepository(connection),
            goal_repository=CockroachGoalRepository(connection),
            checkin_repository=CockroachCheckinRepository(connection),
            plan_repository=CockroachWorkoutPlanRepository(connection),
            decision_repository=CockroachAgentDecisionRepository(connection),
            memory_repository=memory_repository,
            embedder=ollama_client,
            repair_generator=OllamaPlanRepairGenerator(ollama_client),
        ).run_repair(user, trigger_text=trigger)


def _apply_migrations(connection):
    with connection.cursor() as cursor:
        for migration in MIGRATIONS:
            cursor.execute(Path(migration).read_text(encoding="utf-8"))
    connection.commit()


if __name__ == "__main__":
    main()
