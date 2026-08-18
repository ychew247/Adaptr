from src.ollama_plan_repair_generator import OllamaPlanRepairGenerator


class FakeOllamaClient:
    def __init__(self):
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return '''
        {
          "replacement_session": {
            "focus": "Wrist-friendly upper body",
            "exercises": ["dumbbell row"],
            "sets_reps": "3 x 8"
          },
          "coaching_note": "Keep the wrist neutral."
        }
        '''


def test_repair_generator_injects_retrieved_repair_precedents_and_validator_feedback():
    client = FakeOllamaClient()

    repair = OllamaPlanRepairGenerator(client).generate(
        plan={"sessions": [{"day": "Day 1", "exercises": ["push-up"]}]},
        repair_action={"action": "targeted_substitution"},
        constraints={"forbidden_exercises": ["push-up"]},
        retrieved_memories=[{"id": "repair-memory-1", "memory_text": "Rows worked before."}],
        validator_feedback={"error_codes": ["injury_exclusion_violation"]},
    )

    assert repair["replacement_session"]["exercises"] == ["dumbbell row"]
    assert "repair-memory-1" in client.calls[0]["user_text"]
    assert "validator_feedback" in client.calls[0]["user_text"]
    assert "Past repair precedents must influence" in client.calls[0]["instruction"]
