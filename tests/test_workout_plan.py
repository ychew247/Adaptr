from src.m6_workout_plan import WorkoutPlanService, generate_weekly_plan


class FakeWorkoutPlanRepository:
    def __init__(self):
        self.saved_plans = []

    def create_active_plan(self, plan):
        self.saved_plans.append(plan)
        return plan


class FakeProfileRepository:
    def __init__(self, profile):
        self.profile = profile

    def find_by_user_id(self, user_id):
        return self.profile


class FakeGoalRepository:
    def __init__(self, goal):
        self.goal = goal

    def find_active_by_user_id(self, user_id):
        return self.goal


class FakeCheckinRepository:
    def __init__(self, checkins):
        self.checkins = checkins

    def find_recent_by_user_id(self, user_id, limit=30):
        return self.checkins[:limit]


class FakePlanGenerator:
    def generate(self, profile, goal, readiness):
        return {
            "goal_id": goal["id"],
            "week_start": "2026-08-03",
            "week_number": 1,
            "exercise_names": ["custom ollama exercise"],
            "target_muscle_groups": ["upper_body"],
            "intensity_band": "normal",
            "readiness_score": readiness["readiness_score"],
            "sessions": [],
            "generator": "ollama",
        }


PROFILE = {
    "user_id": "user-1",
    "training_experience": "intermediate",
    "equipment_access": ["full gym", "treadmill"],
    "weekly_availability": "4 days/week, 60 minutes each",
    "injury_notes": "",
}


GOAL = {
    "id": "goal-1",
    "user_id": "user-1",
    "goal_type": "sport_conditioning",
    "plan_duration_weeks": 8,
    "goal_details": {
        "athlete_type": "badminton",
        "target_muscle_groups": ["upper_body"],
        "desired_outcomes": ["strength", "functional_performance"],
        "training_style": ["hybrid", "functional"],
    },
}


def test_generate_weekly_plan_uses_profile_goal_duration_and_readiness():
    plan = generate_weekly_plan(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 84, "band": "train_as_planned", "safety_triggered": False},
        week_start="2026-08-10",
    )

    assert plan["goal_id"] == "goal-1"
    assert plan["plan_duration_weeks"] == 8
    assert plan["week_number"] == 1
    assert plan["readiness_band"] == "train_as_planned"
    assert plan["intensity_band"] == "normal"
    assert len(plan["sessions"]) == 4
    assert "badminton footwork intervals" in plan["exercise_names"]
    assert "upper_body" in plan["target_muscle_groups"]
    assert [session["scheduled_date"] for session in plan["sessions"]] == [
        "2026-08-10",
        "2026-08-12",
        "2026-08-14",
        "2026-08-16",
    ]
    assert {session["status"] for session in plan["sessions"]} == {"planned"}


def test_generate_weekly_plan_reduces_volume_when_readiness_is_lower():
    plan = generate_weekly_plan(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 68, "band": "reduce_volume", "safety_triggered": False},
    )

    assert plan["intensity_band"] == "reduced"
    assert plan["volume_modifier"] == 0.8
    assert plan["sessions"][0]["adjustment"] == "Reduce working sets by 20%."


def test_generate_weekly_plan_prioritizes_recovery_when_safety_is_triggered():
    plan = generate_weekly_plan(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 30, "band": "recovery_day", "safety_triggered": True},
    )

    assert plan["intensity_band"] == "recovery"
    assert plan["sessions"][0]["focus"] == "Safety-first recovery"
    assert "mobility breathing reset" in plan["exercise_names"]


def test_workout_plan_service_saves_active_plan():
    plan_repository = FakeWorkoutPlanRepository()
    service = WorkoutPlanService(
        profile_repository=FakeProfileRepository(PROFILE),
        goal_repository=FakeGoalRepository(GOAL),
        checkin_repository=FakeCheckinRepository(
            [
                {
                    "sleep_hours": 7,
                    "stress_level": 2,
                    "energy_level": 4,
                    "soreness_level": 2,
                    "pain_notes": "",
                }
            ]
        ),
        plan_repository=plan_repository,
        plan_generator=FakePlanGenerator(),
    )
    messages = []

    result = service.run_plan_generation(
        user={"id": "user-1", "display_name": "Alex"},
        say=messages.append,
    )

    assert result == "plan_ready"
    assert len(plan_repository.saved_plans) == 1
    saved = plan_repository.saved_plans[0]
    assert saved["user_id"] == "user-1"
    assert saved["goal_id"] == "goal-1"
    assert saved["intensity_band"] in {"normal", "reduced", "light", "recovery"}
    assert saved["plan_json"]["readiness_score"] >= 0
    assert saved["plan_json"]["generator"] == "ollama"
    assert messages == ["Saved Alex's Week 1 workout plan."]
