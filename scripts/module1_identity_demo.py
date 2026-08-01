import os
from pathlib import Path

import psycopg2

from src.cockroach_user_repository import CockroachUserRepository
from src.module1_identity_flow import run_identity_flow


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    migration = Path("sql/001_create_users.sql").read_text(encoding="utf-8")

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(migration)
        connection.commit()

        repository = CockroachUserRepository(connection)
        run_identity_flow(repository)


if __name__ == "__main__":
    main()
