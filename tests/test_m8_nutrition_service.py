from src.m8_nutrition_service import NutritionTargetService


class ProfileRepository:
    def find_by_user_id(self, user_id):
        return {
            "age": 25,
            "height_cm": 175,
            "starting_weight_kg": 72,
            "bmr_formula_profile": "male",
            "weekly_availability": "4 days/week",
        }


class GoalRepository:
    def find_active_by_user_id(self, user_id):
        return {"goal_type": "maintenance", "goal_details": {}}


class CheckinRepository:
    def find_recent_by_user_id(self, user_id, limit=30):
        return [{"id": "checkin-1", "checkin_date": "2026-08-05", "sleep_hours": 7, "stress_level": 3, "energy_level": 3, "soreness_level": 3, "pain_notes": ""}]


class PlanRepository:
    def find_active_by_user_id(self, user_id):
        return None


class NutritionRepository:
    def upsert_daily_target(self, target):
        return {"id": "target-1", "target_date": "2026-08-05", **target}


class DecisionLog:
    def __init__(self):
        self.readiness_calls = []
        self.nutrition_calls = []

    def log_readiness_assessment(self, **kwargs):
        self.readiness_calls.append(kwargs)
        return {"id": "readiness-decision-1"}

    def log_nutrition_target(self, **kwargs):
        self.nutrition_calls.append(kwargs)
        return {"id": "nutrition-decision-1"}


def test_nutrition_service_logs_the_saved_target_with_its_readiness_parent():
    decisions = DecisionLog()
    service = NutritionTargetService(
        ProfileRepository(), GoalRepository(), CheckinRepository(), PlanRepository(),
        NutritionRepository(), decision_log=decisions,
    )

    saved = service.run_daily_target({"id": "user-1"}, workout_today=True)

    assert saved["id"] == "target-1"
    assert decisions.readiness_calls[0]["checkin"]["id"] == "checkin-1"
    assert decisions.nutrition_calls[0]["nutrition_target"]["id"] == "target-1"
    assert decisions.nutrition_calls[0]["parent_decision_id"] == "readiness-decision-1"
