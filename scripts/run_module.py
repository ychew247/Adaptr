import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.m4_adaptive_checkin import AdaptiveCheckinService
from src.cockroach_checkin_repository import CockroachCheckinRepository
from src.cockroach_goal_repository import CockroachGoalRepository
from src.cockroach_static_profile_repository import CockroachStaticProfileRepository
from src.cockroach_user_repository import CockroachUserRepository
from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository
from src.cockroach_agent_decision_repository import CockroachAgentDecisionRepository
from src.cockroach_nutrition_target_repository import CockroachNutritionTargetRepository
from src.demo_user_seed import seed_demo_user
from src.ollama_checkin_parser import OllamaCheckinParser
from src.ollama_client import OllamaClient
from src.ollama_goal_parser import OllamaGoalParser
from src.m2_static_profile import StaticProfileService
from src.m3_training_goal import TrainingGoalService
from src.m1_user_identity import UserIdentityService
from src.m5_readiness_score import compute_readiness
from src.m6_hybrid_workout_plan import (
    DeterministicWorkoutPlanGenerator,
    HybridWorkoutPlanService,
)
from src.m6_vector_preflight import verify_embedding_dimension
from src.ollama_workout_plan_generator import OllamaWorkoutPlanGenerator
from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository
from src.cockroach_fitness_knowledge_repository import CockroachFitnessKnowledgeRepository
from src.m7_plan_repair import PlanRepairService
from src.ollama_plan_repair_generator import OllamaPlanRepairGenerator
from src.ollama_nutrition_note_generator import OllamaNutritionNoteGenerator
from src.m8_nutrition_service import NutritionTargetService
from src.m9_decision_log import DecisionLogService
from src.m11_fitness_knowledge import parse_fitness_knowledge_files, seed_fitness_knowledge
from src.agent_flow import AdaptiveFitnessAgent


MIGRATIONS = [
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
]

DEFAULT_KNOWLEDGE_FILES = [
    "docs/fitness-knowledge-snippets.md",
    "docs/sport-specific-knowledge-snippets.md",
]


def main():
    parser = argparse.ArgumentParser(
        description="Run one fitness-agent module without replaying the full demo flow."
    )
    parser.add_argument("--module", choices=["2", "3", "4", "5", "6", "7", "8", "11", "agent"], required=True)
    parser.add_argument("--user", default="Alex")
    parser.add_argument("--deterministic-plan", action="store_true")
    parser.add_argument(
        "--replace-goal",
        action="store_true",
        help="Archive the current active goal and collect a corrected replacement goal.",
    )
    parser.add_argument("--repair-trigger")
    parser.add_argument(
        "--workout-today",
        action="store_true",
        help="Apply the planned-workout hydration adjustment.",
    )
    parser.add_argument(
        "--bmr-formula-profile",
        choices=["male", "female"],
        help="Store the formula profile required for Mifflin-St Jeor calculations.",
    )
    parser.add_argument(
        "--seed-demo-profile",
        action="store_true",
        help="Create/update demo user Alex through Module 2 before running the selected module.",
    )
    parser.add_argument(
        "--knowledge-file",
        action="append",
        dest="knowledge_files",
        help=(
            "Markdown file containing Module 11 knowledge snippets. "
            "Repeat to seed multiple custom files; overrides the two default files."
        ),
    )
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()

    if args.skip_live:
        print("Direct module runner imports successfully.")
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
        _apply_migrations(connection)

        user_repository = CockroachUserRepository(connection)
        profile_repository = CockroachStaticProfileRepository(connection)
        goal_repository = CockroachGoalRepository(connection)
        checkin_repository = CockroachCheckinRepository(connection)
        plan_repository = CockroachWorkoutPlanRepository(connection)
        nutrition_repository = CockroachNutritionTargetRepository(connection)
        decision_repository = CockroachAgentDecisionRepository(connection)
        decision_log = DecisionLogService(decision_repository)

        if args.module == "11":
            ollama_client = OllamaClient()
            memory_repository = CockroachMemoryEmbeddingRepository(connection)
            verify_embedding_dimension(ollama_client, memory_repository)
            knowledge_files = args.knowledge_files or DEFAULT_KNOWLEDGE_FILES
            snippets = parse_fitness_knowledge_files(
                Path(path) for path in knowledge_files
            )
            result = seed_fitness_knowledge(
                snippets,
                CockroachFitnessKnowledgeRepository(connection),
                memory_repository,
                ollama_client,
            )
            print(
                "Seeded {snippets} fitness knowledge snippets and {memories} vector memories.".format(
                    **result
                )
            )
            return

        if args.seed_demo_profile:
            user = seed_demo_user(user_repository, profile_repository)["user"]
        else:
            user = UserIdentityService(user_repository).get_or_create_user(args.user).user

        if args.module == "2":
            StaticProfileService(profile_repository).run_onboarding(user)
            return

        if args.module == "3":
            _ensure_profile(user, profile_repository)
            TrainingGoalService(
                goal_repository,
                parser=OllamaGoalParser(OllamaClient()),
            ).run_goal_setup(user, replace_existing=args.replace_goal)
            return

        _ensure_profile(user, profile_repository)
        _ensure_goal(user, goal_repository)

        if args.module == "agent":
            ollama_client = OllamaClient()
            memory_repository = CockroachMemoryEmbeddingRepository(connection)
            verify_embedding_dimension(ollama_client, memory_repository)
            agent = AdaptiveFitnessAgent(
                checkin_service=AdaptiveCheckinService(
                    checkin_repository,
                    OllamaCheckinParser(ollama_client),
                ),
                checkin_repository=checkin_repository,
                plan_repository=plan_repository,
                decision_log=decision_log,
                plan_service=HybridWorkoutPlanService(
                    profile_repository=profile_repository,
                    goal_repository=goal_repository,
                    checkin_repository=checkin_repository,
                    plan_repository=plan_repository,
                    memory_repository=memory_repository,
                    embedder=ollama_client,
                    plan_generator=(
                        DeterministicWorkoutPlanGenerator()
                        if args.deterministic_plan
                        else OllamaWorkoutPlanGenerator(ollama_client)
                    ),
                    decision_log=decision_log,
                ),
                repair_service=PlanRepairService(
                    profile_repository=profile_repository,
                    goal_repository=goal_repository,
                    checkin_repository=checkin_repository,
                    plan_repository=plan_repository,
                    decision_repository=decision_repository,
                    decision_log=decision_log,
                    memory_repository=memory_repository,
                    embedder=ollama_client,
                    repair_generator=OllamaPlanRepairGenerator(ollama_client),
                ),
                nutrition_service=NutritionTargetService(
                    profile_repository=profile_repository,
                    goal_repository=goal_repository,
                    checkin_repository=checkin_repository,
                    plan_repository=plan_repository,
                    nutrition_repository=nutrition_repository,
                    note_generator=OllamaNutritionNoteGenerator(ollama_client),
                    decision_log=decision_log,
                ),
            )
            result = agent.run_daily_flow(
                user,
                workout_today=args.workout_today,
                formula_profile=args.bmr_formula_profile,
            )
            print(result["summary"])
            print(f"Plan action: {result['action']}")
            print(f"Nutrition target: {result['nutrition']}")
            return

        if args.module == "4":
            AdaptiveCheckinService(
                checkin_repository,
                OllamaCheckinParser(OllamaClient()),
            ).run_checkin(user)
            return

        checkins = checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        if not checkins:
            print("No adaptive check-in found, so Module 4 check-in will run first.")
            AdaptiveCheckinService(
                checkin_repository,
                OllamaCheckinParser(OllamaClient()),
            ).run_checkin(user)
            checkins = checkin_repository.find_recent_by_user_id(user["id"], limit=30)

        if args.module == "5":
            result = compute_readiness(list(reversed(checkins[1:])), checkins[0])
            decision_log.log_readiness_assessment(
                user_id=user["id"], checkin=checkins[0], readiness=result
            )
            print(f"Readiness score for {user['display_name']}: {result['readiness_score']}")
            print(f"Band: {result['band']}")
            print(f"Safety triggered: {result['safety_triggered']}")
            print(f"Components: {result['components']}")
            return

        if args.module == "8":
            target = NutritionTargetService(
                profile_repository=profile_repository,
                goal_repository=goal_repository,
                checkin_repository=checkin_repository,
                plan_repository=plan_repository,
                nutrition_repository=nutrition_repository,
                note_generator=OllamaNutritionNoteGenerator(OllamaClient()),
                decision_log=decision_log,
            ).run_daily_target(
                user,
                workout_today=args.workout_today,
                formula_profile=args.bmr_formula_profile,
            )
            print(f"Saved nutrition target for {user['display_name']}.")
            print(f"Calories: {target['calories_min']}-{target['calories_max']} kcal")
            print(f"Protein: {target['protein_g']} g | Hydration: {target['hydration_l']} L")
            print(f"Fiber: {target['fiber_g']} g")
            print(f"Notes: {target['notes']}")
            return

        ollama_client = OllamaClient()
        memory_repository = CockroachMemoryEmbeddingRepository(connection)
        verify_embedding_dimension(ollama_client, memory_repository)
        if args.module == "7":
            trigger = args.repair_trigger or input(
                "What changed and needs a workout-plan repair? "
            )
            PlanRepairService(
                profile_repository=profile_repository,
                goal_repository=goal_repository,
                checkin_repository=checkin_repository,
                plan_repository=plan_repository,
                decision_repository=decision_repository,
                decision_log=decision_log,
                memory_repository=memory_repository,
                embedder=ollama_client,
                repair_generator=OllamaPlanRepairGenerator(ollama_client),
            ).run_repair(user, trigger_text=trigger)
            return
        HybridWorkoutPlanService(
            profile_repository=profile_repository,
            goal_repository=goal_repository,
            checkin_repository=checkin_repository,
            plan_repository=plan_repository,
            memory_repository=memory_repository,
            embedder=ollama_client,
            plan_generator=(
                DeterministicWorkoutPlanGenerator()
                if args.deterministic_plan
                else OllamaWorkoutPlanGenerator(ollama_client)
            ),
            decision_log=decision_log,
        ).run_plan_generation(user)


def _apply_migrations(connection):
    with connection.cursor() as cursor:
        for migration in MIGRATIONS:
            cursor.execute(Path(migration).read_text(encoding="utf-8"))
    connection.commit()


def _ensure_profile(user, profile_repository):
    if profile_repository.find_by_user_id(user["id"]) is None:
        print("Static profile is missing, so Module 2 onboarding will run first.")
        StaticProfileService(profile_repository).run_onboarding(user)


def _ensure_goal(user, goal_repository):
    if goal_repository.find_active_by_user_id(user["id"]) is None:
        print("Active goal is missing, so Module 3 goal setup will run first.")
        TrainingGoalService(
            goal_repository,
            parser=OllamaGoalParser(OllamaClient()),
        ).run_goal_setup(user)


if __name__ == "__main__":
    main()
