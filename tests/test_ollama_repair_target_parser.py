from src.ollama_repair_target_parser import OllamaRepairTargetParser


class FakeOllamaClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return self.content


def test_parser_extracts_multiple_natural_repair_targets():
    client = FakeOllamaClient('{"repair_targets": ["Day 2", "2026-8-19"]}')

    result = OllamaRepairTargetParser(client).parse(
        "My shoulder is sore, I slept six hours and energy is 3/5; repair Day 2 and 2026-8-19."
    )

    assert result == ["Day 2", "2026-8-19"]
    assert "Return JSON only" in client.calls[0]["instruction"]


def test_parser_returns_no_targets_when_user_did_not_request_a_specific_session():
    client = FakeOllamaClient('{"repair_targets": []}')

    assert OllamaRepairTargetParser(client).parse("I slept 6 hours and feel sore.") == []
