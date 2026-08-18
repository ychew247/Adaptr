from src.ollama_nutrition_note_generator import OllamaNutritionNoteGenerator


class FakeOllamaClient:
    def chat_json_instruction(self, instruction, user_text, **kwargs):
        return '{"note":"Keep protein steady and have yogurt after training."}'


def test_nutrition_note_unwraps_an_accidental_json_note_response():
    note = OllamaNutritionNoteGenerator(FakeOllamaClient()).generate(
        {
            "calories_min": 2200,
            "calories_max": 2400,
            "protein_g": 120,
            "hydration_l": 2.5,
            "fiber_g": 30,
            "protein_range_g": {"min": 100, "max": 130},
            "planned_intensity": "normal",
            "readiness_band": "train_as_planned",
        },
        {"diet_preferences": "none"},
        True,
    )

    assert note == "Keep protein steady and have yogurt after training."


def test_nutrition_note_unwraps_a_fenced_json_note_response():
    class _FencedJsonClient:
        def chat_json_instruction(self, instruction, user_text, **kwargs):
            return '```json\n{"note":"Keep protein steady after training."}\n```'

    note = OllamaNutritionNoteGenerator(_FencedJsonClient()).generate(
        _targets(), {"diet_preferences": "none"}, True
    )

    assert note == "Keep protein steady after training."


def _targets():
    return {
        "calories_min": 2200,
        "calories_max": 2400,
        "protein_g": 120,
        "hydration_l": 2.5,
        "fiber_g": 30,
        "protein_range_g": {"min": 100, "max": 130},
        "planned_intensity": "normal",
        "readiness_band": "train_as_planned",
    }
