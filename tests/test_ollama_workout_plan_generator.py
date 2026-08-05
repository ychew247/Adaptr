import pytest

from src.ollama_workout_plan_generator import (
    OllamaWorkoutPlanGenerator,
    PlanGenerationFormatError,
)


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return self.content


PROFILE = {
    "training_experience": "intermediate",
    "equipment_access": ["full gym"],
    "weekly_availability": "4 days/week",
}


GOAL = {
    "id": "goal-1",
    "goal_type": "sport_conditioning",
    "plan_duration_weeks": 8,
    "goal_details": {
        "athlete_type": "badminton",
        "target_muscle_groups": ["upper_body"],
        "desired_outcomes": ["strength"],
    },
}


def test_ollama_workout_plan_generator_normalizes_model_plan_json():
    client = FakeOllamaClient(
        """
        {
          "overview": "Badminton-focused hybrid strength week.",
          "sessions": [
            {
              "day": "Day 1",
              "focus": "Upper-body functional strength",
              "exercises": ["landmine press", "single-arm cable row"],
              "sets_reps": "3 x 8",
              "adjustment": "Train as planned."
            },
            {
              "day": "Day 2",
              "focus": "Badminton movement",
              "exercises": ["badminton footwork intervals"],
              "sets_reps": "6 x 30 seconds",
              "adjustment": "Train as planned."
            }
          ],
          "target_muscle_groups": ["upper_body", "core"],
          "coaching_notes": ["Keep movements fast but controlled."]
        }
        """
    )

    plan = OllamaWorkoutPlanGenerator(client).generate(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 86, "band": "train_as_planned", "safety_triggered": False},
    )

    assert plan["generator"] == "ollama"
    assert plan["goal_id"] == "goal-1"
    assert plan["intensity_band"] == "normal"
    assert plan["overview"] == "Badminton-focused hybrid strength week."
    assert plan["exercise_names"] == [
        "landmine press",
        "single-arm cable row",
        "badminton footwork intervals",
    ]
    assert plan["target_muscle_groups"] == ["upper_body", "core"]
    assert plan["coaching_notes"] == ["Keep movements fast but controlled."]
    assert "Return JSON only" in client.calls[0]["instruction"]


def test_ollama_workout_plan_generator_enforces_safety_intensity_band():
    client = FakeOllamaClient(
        """
        {
          "sessions": [
            {
              "day": "Day 1",
              "focus": "Heavy session",
              "exercises": ["barbell squat"],
              "sets_reps": "5 x 5",
              "adjustment": "Go heavy."
            }
          ],
          "intensity_band": "normal"
        }
        """
    )

    plan = OllamaWorkoutPlanGenerator(client).generate(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 30, "band": "recovery_day", "safety_triggered": True},
    )

    assert plan["intensity_band"] == "recovery"
    assert plan["volume_modifier"] == 0.4
    assert plan["sessions"][0]["adjustment"] == "Safety or low readiness: use recovery-only work."


def test_ollama_workout_plan_generator_injects_retrieved_precedents_and_feedback():
    client = FakeOllamaClient(
        '{"sessions": [{"exercises": ["dumbbell row"], "sets_reps": "3 x 8"}]}'
    )

    OllamaWorkoutPlanGenerator(client).generate(
        profile=PROFILE,
        goal=GOAL,
        readiness={"readiness_score": 86, "band": "train_as_planned", "safety_triggered": False},
        constraints={"intensity_ceiling": "normal", "schedule": {"max_sessions": 3}},
        retrieved_memories=[
            {
                "id": "memory-1",
                "memory_text": "Mobility and reduced pressing worked after shoulder soreness.",
                "outcome_json": {"worked": "mobility"},
            }
        ],
        validator_feedback={"error_codes": ["equipment_violation"]},
    )

    prompt = client.calls[0]["user_text"]
    assert "retrieved_precedents" in prompt
    assert "memory-1" in prompt
    assert "validator_feedback" in prompt
    assert "Past precedents must influence" in client.calls[0]["instruction"]


def test_ollama_workout_plan_generator_raises_a_retryable_error_for_malformed_json():
    client = FakeOllamaClient('{"sessions": [{"exercises": ["dumbbell row"]}')

    with pytest.raises(PlanGenerationFormatError, match="valid JSON"):
        OllamaWorkoutPlanGenerator(client).generate(
            profile=PROFILE,
            goal=GOAL,
            readiness={"readiness_score": 86, "band": "train_as_planned", "safety_triggered": False},
        )
