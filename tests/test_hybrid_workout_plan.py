import pytest

from src.m6_hybrid_workout_plan import HybridWorkoutPlanService, PlanGenerationError
from src.ollama_workout_plan_generator import PlanGenerationFormatError


PROFILE = {
    "user_id": "user-1",
    "equipment_access": ["dumbbells", "treadmill"],
    "weekly_availability": "3 days/week",
    "injury_notes": "",
    "medical_constraints": "",
    "training_experience": "intermediate",
}
GOAL = {
    "id": "goal-1",
    "goal_type": "strength",
    "plan_duration_weeks": 8,
    "goal_details": {"target_muscle_groups": ["upper_body"]},
}
CHECKIN = {
    "id": "checkin-1",
    "sleep_hours": 8,
    "stress_level": 2,
    "energy_level": 4,
    "soreness_level": 2,
    "sore_muscle_groups": [],
    "pain_notes": "",
    "free_text_note": "Feeling good after a well-recovered week.",
}


class FixedRepository:
    def __init__(self, value):
        self.value = value

    def find_by_user_id(self, user_id):
        return self.value

    def find_active_by_user_id(self, user_id):
        return self.value


class CheckinRepository:
    def find_recent_by_user_id(self, user_id, limit=30):
        return [CHECKIN]


class PlanRepository:
    def __init__(self):
        self.saved = []

    def find_recent_by_user_id(self, user_id, limit=4):
        return []

    def create_active_plan(self, plan):
        self.saved.append(plan)
        return {"id": "plan-1", **plan}


class MemoryRepository:
    def search_similar(self, user_id, embedding, limit=5):
        return [
            {
                "id": "memory-1",
                "source_type": "checkin",
                "source_id": "old-checkin-1",
                "memory_text": "Shoulder soreness improved after mobility and reduced pressing.",
                "outcome_json": {"worked": "mobility"},
                "distance": 0.1,
            }
        ]

    def upsert_memory(self, **kwargs):
        return {"id": "stored-memory"}


class Embedder:
    def embed(self, text):
        return [0.1, 0.2, 0.3]


class RetryingGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, profile, goal, readiness, constraints=None, retrieved_memories=None, validator_feedback=None):
        self.calls.append({"memories": retrieved_memories, "feedback": validator_feedback})
        if len(self.calls) == 1:
            return {
                "week_start": "2026-08-03",
                "week_number": 1,
                "exercise_names": ["barbell squat"],
                "target_muscle_groups": ["upper_body"],
                "intensity_band": "normal",
                "sessions": [{"day": "Day 1", "focus": "Strength", "exercises": ["barbell squat"], "sets_reps": "3 x 8"}],
            }
        return {
            "week_start": "2026-08-03",
            "week_number": 1,
            "exercise_names": ["dumbbell row", "treadmill walk"],
            "target_muscle_groups": ["upper_body"],
            "intensity_band": "normal",
            "sessions": [
                {"day": "Day 1", "focus": "Strength", "exercises": ["dumbbell row"], "sets_reps": "3 x 8"},
                {"day": "Day 3", "focus": "Conditioning", "exercises": ["treadmill walk"], "sets_reps": "20 minutes"},
            ],
        }


def test_hybrid_service_retries_with_validation_feedback_and_stores_audit_data():
    plans = PlanRepository()
    generator = RetryingGenerator()
    service = HybridWorkoutPlanService(
        profile_repository=FixedRepository(PROFILE),
        goal_repository=FixedRepository(GOAL),
        checkin_repository=CheckinRepository(),
        plan_repository=plans,
        memory_repository=MemoryRepository(),
        embedder=Embedder(),
        plan_generator=generator,
    )

    result = service.run_plan_generation({"id": "user-1", "display_name": "Alex"})

    assert result == "plan_ready"
    assert len(generator.calls) == 2
    assert generator.calls[0]["memories"][0]["id"] == "memory-1"
    assert "equipment_violation" in generator.calls[1]["feedback"]["error_codes"]
    assert len(plans.saved) == 1
    assert plans.saved[0]["validation_status"] == "validated"
    assert plans.saved[0]["retrieved_memory_ids"] == ["memory-1"]
    assert plans.saved[0]["generation_attempt"] == 2
    assert plans.saved[0]["source_checkin_id"] == "checkin-1"


def test_hybrid_service_never_saves_when_all_attempts_fail_validation():
    class InvalidGenerator:
        def generate(self, *args, **kwargs):
            return {
                "week_start": "2026-08-03",
                "week_number": 1,
                "exercise_names": ["barbell squat"],
                "target_muscle_groups": ["upper_body"],
                "intensity_band": "normal",
                "sessions": [{"day": "Day 1", "focus": "Strength", "exercises": ["barbell squat"], "sets_reps": "3 x 8"}],
            }

    plans = PlanRepository()
    service = HybridWorkoutPlanService(
        profile_repository=FixedRepository(PROFILE),
        goal_repository=FixedRepository(GOAL),
        checkin_repository=CheckinRepository(),
        plan_repository=plans,
        memory_repository=MemoryRepository(),
        embedder=Embedder(),
        plan_generator=InvalidGenerator(),
    )

    with pytest.raises(PlanGenerationError):
        service.run_plan_generation({"id": "user-1", "display_name": "Alex"})

    assert plans.saved == []


def test_hybrid_service_retries_when_the_model_returns_malformed_json():
    class FormatFailingGenerator:
        def __init__(self):
            self.calls = []

        def generate(self, *args, **kwargs):
            self.calls.append(kwargs.get("validator_feedback"))
            if len(self.calls) == 1:
                raise PlanGenerationFormatError("Model did not return valid JSON.")
            return {
                "week_start": "2026-08-03",
                "week_number": 1,
                "exercise_names": ["dumbbell row"],
                "target_muscle_groups": ["upper_body"],
                "intensity_band": "normal",
                "sessions": [{"day": "Day 1", "focus": "Strength", "exercises": ["dumbbell row"], "sets_reps": "3 x 8"}],
            }

    plans = PlanRepository()
    generator = FormatFailingGenerator()
    service = HybridWorkoutPlanService(
        profile_repository=FixedRepository(PROFILE),
        goal_repository=FixedRepository(GOAL),
        checkin_repository=CheckinRepository(),
        plan_repository=plans,
        memory_repository=MemoryRepository(),
        embedder=Embedder(),
        plan_generator=generator,
    )

    assert service.run_plan_generation({"id": "user-1", "display_name": "Alex"}) == "plan_ready"
    assert generator.calls[1]["error_codes"] == ["invalid_model_json"]
    assert plans.saved[0]["generation_attempt"] == 2
