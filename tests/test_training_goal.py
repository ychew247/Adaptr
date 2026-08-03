from src.training_goal import TrainingGoalService, build_follow_up_prompt, parse_training_goal


class FakeGoalRepository:
    def __init__(self):
        self.goals_by_user_id = {}

    def find_active_by_user_id(self, user_id):
        return self.goals_by_user_id.get(user_id)

    def upsert_active_goal(self, goal):
        self.goals_by_user_id[goal["user_id"]] = goal
        return goal


def test_parse_training_goal_extracts_athlete_muscles_outcomes_and_duration():
    parsed = parse_training_goal(
        "I am a futsal athlete. I want stronger hamstrings and calves, "
        "improve VO2 max, and stay lean over 3 months."
    )

    assert parsed["goal_type"] == "sport_conditioning"
    assert parsed["plan_duration_weeks"] == 12
    assert parsed["goal_details"] == {
        "raw_goal_text": (
            "I am a futsal athlete. I want stronger hamstrings and calves, "
            "improve VO2 max, and stay lean over 3 months."
        ),
        "athlete_type": "futsal",
        "target_muscle_groups": ["hamstrings", "calves"],
        "desired_outcomes": ["strength", "vo2_max", "lean_maintenance"],
        "missing_fields": [],
    }


def test_parse_training_goal_marks_missing_required_info():
    parsed = parse_training_goal("I play badminton")

    assert parsed["goal_type"] == "sport_conditioning"
    assert parsed["plan_duration_weeks"] is None
    assert parsed["goal_details"]["athlete_type"] == "badminton"
    assert parsed["goal_details"]["missing_fields"] == ["desired_outcome", "plan_duration"]


def test_build_follow_up_prompt_asks_only_for_missing_info():
    prompt = build_follow_up_prompt(["desired_outcome", "plan_duration"])

    assert prompt == (
        "I need a little more detail before saving the goal. "
        "What outcome do you want most, e.g. fat loss, VO2 max, stronger core, or bigger shoulders? "
        "How long should the plan run, e.g. 4 weeks, 8 weeks, or 3 months?"
    )


def test_goal_setup_uses_one_general_prompt_and_saves_when_complete():
    repository = FakeGoalRepository()
    service = TrainingGoalService(repository)
    prompts = []
    messages = []

    result = service.run_goal_setup(
        user={"id": "user-1", "display_name": "Alex"},
        ask=lambda prompt: prompts.append(prompt)
        or "I am a runner and want to improve VO2 max over 8 weeks",
        say=messages.append,
    )

    saved = repository.find_active_by_user_id("user-1")
    assert result == "adaptive_checkin"
    assert len(prompts) == 1
    assert prompts[0].startswith("What is your training target?")
    assert saved["goal_type"] == "vo2_max"
    assert saved["plan_duration_weeks"] == 8
    assert saved["goal_details"]["athlete_type"] == "running"
    assert messages == [
        "Saved Alex's training goal. Next I will ask for adaptive check-in details."
    ]


def test_goal_setup_follows_up_when_freeform_answer_is_incomplete():
    repository = FakeGoalRepository()
    service = TrainingGoalService(repository)
    prompts = []
    answers = iter(["I am a casual lifter", "I want fat loss over 1 month"])

    service.run_goal_setup(
        user={"id": "user-1", "display_name": "Alex"},
        ask=lambda prompt: prompts.append(prompt) or next(answers),
        say=lambda message: None,
    )

    saved = repository.find_active_by_user_id("user-1")
    assert len(prompts) == 2
    assert prompts[1].startswith("I need a little more detail before saving the goal.")
    assert saved["goal_type"] == "fat_loss"
    assert saved["plan_duration_weeks"] == 4


def test_goal_setup_skips_existing_active_goal():
    repository = FakeGoalRepository()
    repository.upsert_active_goal({"user_id": "user-1", "goal_type": "fat_loss"})
    service = TrainingGoalService(repository)
    messages = []

    result = service.run_goal_setup(
        user={"id": "user-1", "display_name": "Alex"},
        ask=lambda prompt: "should not ask",
        say=messages.append,
    )

    assert result == "adaptive_checkin"
    assert messages == [
        "I already have Alex's active training goal. Next I will ask for adaptive check-in details."
    ]
