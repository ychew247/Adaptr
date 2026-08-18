import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_user_repository import CockroachUserRepository
from src.module1_identity_flow import run_identity_flow


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    try:
        import psycopg2
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "psycopg2 is not installed. Run: pip install -r requirements.txt"
        ) from error

    migration = Path("sql/001_create_users.sql").read_text(encoding="utf-8")

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(migration)
        connection.commit()

        repository = CockroachUserRepository(connection)
        run_identity_flow(repository)


if __name__ == "__main__":
    main()
