import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.show_demo_data import fetch_memory_tables, format_table_rows


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

    migrations = [
        Path(path).read_text(encoding="utf-8")
        for path in [
            "sql/001_create_users.sql",
            "sql/002_create_user_profiles.sql",
            "sql/003_create_goals.sql",
            "sql/004_create_daily_checkins.sql",
            "sql/005_create_workout_plans.sql",
            "sql/006_upgrade_module6_hybrid.sql",
            "sql/007_create_agent_decisions.sql",
            "sql/010_upgrade_agent_decisions_module9.sql",
        ]
    ]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration)
        connection.commit()

        users, profiles, goals, checkins, plans, decisions = fetch_memory_tables(connection)

    print(
        format_table_rows(
            title="users",
            columns=["id", "display_name", "normalized_name", "created_at"],
            rows=users,
        )
    )
    print()
    print(
        format_table_rows(
            title="user_profiles",
            columns=[
                "display_name",
                "age",
                "height_cm",
                "weight_kg",
                "experience",
                "equipment",
                "availability",
                "activity",
            ],
            rows=profiles,
        )
    )
    print()
    print(
        format_table_rows(
            title="goals",
            columns=[
                "display_name",
                "goal_type",
                "duration_weeks",
                "goal_details",
                "status",
                "updated_at",
            ],
            rows=goals,
        )
    )
    print()
    print(
        format_table_rows(
            title="daily_checkins",
            columns=[
                "display_name",
                "date",
                "sleep",
                "stress",
                "energy",
                "soreness",
                "sore_groups",
                "pain",
                "nutrition",
                "details",
            ],
            rows=checkins,
        )
    )
    print()
    print(
        format_table_rows(
            title="workout_plans",
            columns=[
                "display_name",
                "week_start",
                "exercises",
                "targets",
                "intensity",
                "plan_json",
                "status",
            ],
            rows=plans,
        )
    )
    print()
    print(
        format_table_rows(
            title="agent_decisions",
            columns=[
                "display_name",
                "decision_type",
                "reason",
                "trigger_date",
                "validation_status",
                "parent_decision_id",
                "created_at",
            ],
            rows=decisions,
        )
    )


if __name__ == "__main__":
    main()
