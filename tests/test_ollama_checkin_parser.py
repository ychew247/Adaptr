from src.ollama_checkin_parser import OllamaCheckinParser


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return self.content


def test_ollama_checkin_parser_converts_model_json_to_checkin_shape():
    client = FakeOllamaClient(
        """
        {
          "sleep_hours": 5.5,
          "stress_level": 4,
          "energy_level": 2,
          "soreness_level": 5,
          "sore_muscle_groups": ["hamstrings", "calves"],
          "pain_notes": "mild hamstring strain",
          "weight_kg": 71.8,
          "workout_completed": "missed",
          "nutrition_adherence": "low protein",
          "nutrition_focus": ["protein"],
          "body_flags": ["high_soreness", "pain"]
        }
        """
    )

    parsed = OllamaCheckinParser(client).parse(
        "Slept 5.5 hours, stressed, sore hamstring and calves, missed training, low protein."
    )

    assert parsed == {
        "sleep_hours": 5.5,
        "stress_level": 4,
        "energy_level": 2,
        "soreness_level": 5,
        "sore_muscle_groups": ["hamstrings", "calves"],
        "pain_notes": "mild hamstring strain",
        "weight_kg": 71.8,
        "workout_completed": "missed",
        "nutrition_adherence": "low protein",
        "checkin_details": {
            "raw_checkin_text": (
                "Slept 5.5 hours, stressed, sore hamstring and calves, missed training, low protein."
            ),
            "nutrition_focus": ["protein"],
            "body_flags": ["high_soreness", "pain"],
            "parser": "ollama",
        },
    }
    assert "Return JSON only" in client.calls[0]["instruction"]


def test_ollama_checkin_parser_strips_markdown_code_fence():
    client = FakeOllamaClient(
        """```json
        {"sleep_hours":7,"energy_level":4,"nutrition_adherence":"good"}
        ```"""
    )

    parsed = OllamaCheckinParser(client).parse("slept 7, energy 4, ate well")

    assert parsed["sleep_hours"] == 7
    assert parsed["energy_level"] == 4
    assert parsed["nutrition_adherence"] == "good"
    assert parsed["checkin_details"]["parser"] == "ollama"


def test_explicit_no_pain_overrides_a_contradictory_model_pain_extraction():
    client = FakeOllamaClient('{"pain_notes":"severe pain","body_flags":["pain"]}')

    parsed = OllamaCheckinParser(client).parse("I slept 7 hours, energy 4/5, no pain.")

    assert parsed["pain_notes"] == ""
    assert "pain" not in parsed["checkin_details"]["body_flags"]


def test_training_intention_does_not_count_as_completed_workout():
    client = FakeOllamaClient(
        """
        {
          "sleep_hours": 7,
          "energy_level": 4,
          "soreness_level": 1,
          "pain_notes": null,
          "workout_completed": "yes",
          "nutrition_adherence": "okay"
        }
        """
    )

    parsed = OllamaCheckinParser(client).parse(
        "I slept 7 hours, energy 4/5, no pain, soreness 1/5. "
        "I want to train today. Nutrition was okay."
    )

    assert parsed["workout_completed"] == "unknown"


def test_ten_point_energy_score_is_normalized_to_the_five_point_contract():
    client = FakeOllamaClient(
        '{"sleep_hours":7,"energy_level":7,"soreness_level":1,"pain_notes":null}'
    )

    parsed = OllamaCheckinParser(client).parse(
        "Slept 7 hours, energy 7/10, soreness none, pain none, and I plan to train today."
    )

    assert parsed["energy_level"] == 4
