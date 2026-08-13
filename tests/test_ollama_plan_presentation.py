from src.ollama_plan_presentation import OllamaPlanPresentationGenerator


class FakeOllamaClient:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = iter(responses or [
            '{"introduction":"Your sessions are set for the week.",'
            '"print_question":"Would you like a printable copy?",'
            '"download_ready":"Your workbook is ready below."}'
        ])

    def chat_json_instruction(self, instruction, user_text, **kwargs):
        self.calls.append({"instruction": instruction, "user_text": user_text, **kwargs})
        return next(self.responses)


def test_plan_presentation_uses_ollama_only_for_words_not_session_data():
    client = FakeOllamaClient()
    presentation = OllamaPlanPresentationGenerator(client).generate(
        {
            "plan_json": {
                "intensity_band": "normal",
                "sessions": [{"day": "Day 1", "exercises": ["goblet squat"]}],
            }
        },
        {"band": "train_as_planned", "readiness_score": 91},
    )

    assert presentation == {
        "introduction": "Your sessions are set for the week.",
        "print_question": "Would you like a printable copy?",
        "download_ready": "Your workbook is ready below.",
    }
    assert "goblet squat" in client.calls[0]["user_text"]


def test_plan_presentation_retries_when_the_printable_question_is_not_a_question():
    client = FakeOllamaClient(
        [
            '{"introduction":"Your sessions are ready.",'
            '"print_question":"Train as planned.",'
            '"download_ready":"A plan was constrained by readiness."}',
            '{"introduction":"Your sessions are ready.",'
            '"print_question":"Would you like a downloadable workbook?",'
            '"download_ready":"Your downloadable workbook is ready below."}',
        ]
    )

    presentation = OllamaPlanPresentationGenerator(client).generate({"plan_json": {}}, {})

    assert presentation["print_question"] == "Would you like a downloadable workbook?"
    assert presentation["download_ready"] == "Your downloadable workbook is ready below."
    assert len(client.calls) == 2


def test_plan_presentation_uses_safe_display_copy_after_two_invalid_responses():
    client = FakeOllamaClient(
        [
            '{"introduction":"Your sessions are ready.",'
            '"print_question":"Train as planned.",'
            '"download_ready":"A plan was constrained by readiness."}',
            '{"introduction":"Your sessions are ready.",'
            '"print_question":"Tell me more.",'
            '"download_ready":"Ready."}',
        ]
    )

    presentation = OllamaPlanPresentationGenerator(client).generate({"plan_json": {}}, {})

    assert presentation == {
        "introduction": "Your validated workout plan is ready.",
        "print_question": "Would you like a printable version of your workout plan?",
        "download_ready": "Your downloadable workout-plan workbook is ready below.",
    }
