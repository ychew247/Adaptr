import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.module1_identity_flow import identify_user
from src.ollama_client import OllamaClient
from src.ollama_goal_parser import OllamaGoalParser
from src.m2_static_profile import StaticProfileService
from src.m3_training_goal import TrainingGoalService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    print("Module 3 parser: Ollama")

    if args.skip_live:
        print("Module 3 Ollama demo imports successfully.")
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
    ]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration)
        connection.commit()

        user_repository = CockroachUserRepository(connection)
        profile_repository = CockroachStaticProfileRepository(connection)
        goal_repository = CockroachGoalRepository(connection)
        goal_parser = OllamaGoalParser(OllamaClient())

        user, _next_step = identify_user(user_repository)
        StaticProfileService(profile_repository).run_onboarding(user)
        TrainingGoalService(goal_repository, parser=goal_parser).run_goal_setup(user)


if __name__ == "__main__":
    main()
