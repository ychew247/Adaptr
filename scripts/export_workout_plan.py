import argparse
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.m1_user_identity import normalize_name
from src.workout_plan_excel_export import export_sessions_workbook


def resolve_export_plan(
    user_name: str,
    user_repository: Any,
    plan_repository: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_name = normalize_name(user_name)
    user = user_repository.find_by_normalized_name(normalized_name)
    if user is None:
        raise RuntimeError(f"No user found with the name '{user_name}'.")

    plan = plan_repository.find_active_by_user_id(user["id"])
    if plan is None or plan.get("validation_status") != "validated":
        raise RuntimeError(
            "No validated active workout plan is available for export. "
            "Generate or repair a plan first."
        )
    return user, plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a user's latest validated active workout plan to Excel."
    )
    parser.add_argument("--user", required=True, help="Saved fitness-profile name.")
    parser.add_argument(
        "--output",
        help="Optional .xlsx output path. Defaults to exports/<user>_latest_workout_plan.xlsx.",
    )
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.skip_live:
        print("Workout plan export command imports successfully.")
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

    with psycopg2.connect(database_url) as connection:
        user, plan = resolve_export_plan(
            args.user,
            CockroachUserRepository(connection),
            CockroachWorkoutPlanRepository(connection),
        )

    default_path = PROJECT_ROOT / "exports" / (
        f"{user['normalized_name']}_latest_workout_plan.xlsx"
    )
    output_path = Path(args.output) if args.output else default_path
    saved_path = export_sessions_workbook(plan, output_path)
    print(f"Exported {user['display_name']}'s workout plan to {saved_path}.")


if __name__ == "__main__":
    main()
