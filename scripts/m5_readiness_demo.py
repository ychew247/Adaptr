import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.m5_readiness_score import compute_readiness
from src.m1_user_identity import UserIdentityService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="Alex")
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    if args.skip_live:
        print("Module 5 readiness demo imports successfully.")
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
        Path("sql/004_create_daily_checkins.sql").read_text(encoding="utf-8"),
    ]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration)
        connection.commit()

        user_repository = CockroachUserRepository(connection)
        checkin_repository = CockroachCheckinRepository(connection)
        user = UserIdentityService(user_repository).get_or_create_user(args.user).user
        checkins = checkin_repository.find_recent_by_user_id(user["id"], limit=30)

    if not checkins:
        raise RuntimeError("No check-ins found. Run Module 4 first.")

    today_checkin = checkins[0]
    history = list(reversed(checkins[1:]))
    result = compute_readiness(history, today_checkin)

    print(f"Readiness score for {user['display_name']}: {result['readiness_score']}")
    print(f"Band: {result['band']}")
    print(f"Safety triggered: {result['safety_triggered']}")
    print(f"Components: {result['components']}")


if __name__ == "__main__":
    main()
