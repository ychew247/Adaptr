import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository
from src.m1_user_identity import UserIdentityService
from src.m6_hybrid_workout_plan import (
    DeterministicWorkoutPlanGenerator,
    HybridWorkoutPlanService,
)
from src.m6_vector_preflight import verify_embedding_dimension
from src.ollama_client import OllamaClient
from src.ollama_workout_plan_generator import OllamaWorkoutPlanGenerator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="Alex")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    if args.skip_live:
        print("Module 6 workout plan demo imports successfully.")
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    try:
        import psycopg2
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "psycopg2 is not installed. Run: pip install -r requirements.txt"
        ) from error

    migrations = [
        Path("sql/001_create_users.sql").read_text(encoding="utf-8"),
        Path("sql/002_create_user_profiles.sql").read_text(encoding="utf-8"),
        Path("sql/003_create_goals.sql").read_text(encoding="utf-8"),
        Path("sql/004_create_daily_checkins.sql").read_text(encoding="utf-8"),
        Path("sql/005_create_workout_plans.sql").read_text(encoding="utf-8"),
        Path("sql/006_upgrade_module6_hybrid.sql").read_text(encoding="utf-8"),
    ]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration)
        connection.commit()

        user = UserIdentityService(CockroachUserRepository(connection)).get_or_create_user(
            args.user
        ).user
        ollama_client = OllamaClient()
        memory_repository = CockroachMemoryEmbeddingRepository(connection)
        verify_embedding_dimension(ollama_client, memory_repository)
        service = HybridWorkoutPlanService(
            profile_repository=CockroachStaticProfileRepository(connection),
            goal_repository=CockroachGoalRepository(connection),
            checkin_repository=CockroachCheckinRepository(connection),
            plan_repository=CockroachWorkoutPlanRepository(connection),
            memory_repository=memory_repository,
            embedder=ollama_client,
            plan_generator=(
                DeterministicWorkoutPlanGenerator()
                if args.deterministic
                else OllamaWorkoutPlanGenerator(ollama_client)
            ),
        )
        service.run_plan_generation(user)


if __name__ == "__main__":
    main()
