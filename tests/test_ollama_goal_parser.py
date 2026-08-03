from src.ollama_goal_parser import OllamaGoalParser


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return self.content


def test_ollama_goal_parser_converts_model_json_to_training_goal_shape():
    client = FakeOllamaClient(
        """
        {
          "goal_type": "sport_conditioning",
          "plan_duration_weeks": 8,
          "athlete_type": "badminton",
          "target_muscle_groups": ["upper_body"],
          "desired_outcomes": ["strength", "functional_performance"],
          "training_style": ["hybrid", "functional"],
          "sport_specific_focus": ["badminton_movement"]
        }
        """
    )
    parser = OllamaGoalParser(client)

    parsed = parser.parse(
        "I am a badminton athlete and want upper body strength with hybrid functional training for 2 months"
    )

    assert parsed == {
        "goal_type": "sport_conditioning",
        "plan_duration_weeks": 8,
        "goal_details": {
            "raw_goal_text": "I am a badminton athlete and want upper body strength with hybrid functional training for 2 months",
            "athlete_type": "badminton",
            "target_muscle_groups": ["upper_body"],
            "desired_outcomes": ["strength", "functional_performance"],
            "training_style": ["hybrid", "functional"],
            "sport_specific_focus": ["badminton_movement"],
            "missing_fields": [],
            "parser": "ollama",
        },
    }
    assert "Return JSON only" in client.calls[0]["instruction"]


def test_ollama_goal_parser_strips_markdown_code_fence():
    client = FakeOllamaClient(
        """```json
        {"goal_type":"fat_loss","plan_duration_weeks":4,"desired_outcomes":["fat_loss"]}
        ```"""
    )

    parsed = OllamaGoalParser(client).parse("fat loss for 1 month")

    assert parsed["goal_type"] == "fat_loss"
    assert parsed["plan_duration_weeks"] == 4
    assert parsed["goal_details"]["missing_fields"] == []


def test_ollama_goal_parser_marks_missing_required_fields():
    client = FakeOllamaClient('{"athlete_type":"badminton"}')

    parsed = OllamaGoalParser(client).parse("I play badminton")

    assert parsed["goal_type"] == "sport_conditioning"
    assert parsed["plan_duration_weeks"] is None
    assert parsed["goal_details"]["missing_fields"] == ["desired_outcome", "plan_duration"]
