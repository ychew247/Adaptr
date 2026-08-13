from src.ollama_chat_language import OllamaChatLanguage


class FakeOllamaClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def chat_json_instruction(self, instruction, user_text):
        self.calls.append({"instruction": instruction, "user_text": user_text})
        return next(self.responses)


def test_printable_intent_interprets_a_natural_acceptance():
    client = FakeOllamaClient(['{"intent":"accept","response":"Great choice."}'])

    outcome = OllamaChatLanguage(client).classify_printable_plan_reply(
        "I would like a copy for my records"
    )

    assert outcome == {"intent": "accept", "response": "Great choice."}
    assert "I would like a copy" in client.calls[0]["user_text"]


def test_printable_intent_keeps_ambiguous_replies_pending():
    client = FakeOllamaClient(['{"intent":"unclear","response":"Would you like a printable copy?"}'])

    outcome = OllamaChatLanguage(client).classify_printable_plan_reply("Maybe later")

    assert outcome["intent"] == "unclear"


def test_onboarding_copy_uses_the_required_field_without_fixed_question_wording():
    client = FakeOllamaClient(['{"message":"Glad to meet you, Sam. How many years old are you?"}'])

    message = OllamaChatLanguage(client).generate_onboarding_message(
        display_name="Sam",
        is_new_user=True,
        field_key="age",
        field_requirement="a positive age in years",
    )

    assert message == "Glad to meet you, Sam. How many years old are you?"
    assert "a positive age in years" in client.calls[0]["user_text"]


def test_landing_welcome_uses_ollama_for_the_fitness_headline_and_name_prompt():
    client = FakeOllamaClient(
        [
            '{"headline":"Time to Move Your Body","prompt":"What name would you like Fitness Agent to use?"}'
        ]
    )

    welcome = OllamaChatLanguage(client).generate_landing_welcome()

    assert welcome == {
        "headline": "Time to Move Your Body",
        "prompt": "What name would you like Fitness Agent to use?",
    }
    assert "fitness" in client.calls[0]["instruction"].lower()


def test_onboarding_copy_retries_when_it_does_not_name_the_requested_field():
    client = FakeOllamaClient(
        [
            '{"message":"Please respond with the requested profile information."}',
            '{"message":"How tall are you in centimetres?"}',
        ]
    )

    message = OllamaChatLanguage(client).generate_onboarding_message(
        display_name="Sam",
        is_new_user=False,
        field_key="height_cm",
        field_requirement="a positive height in centimetres",
    )

    assert message == "How tall are you in centimetres?"
    assert len(client.calls) == 2


def test_onboarding_copy_uses_a_field_aware_fallback_after_two_invalid_model_responses():
    client = FakeOllamaClient(
        [
            '{"message":"Please respond with the requested profile information."}',
            '{"message":"Tell me more."}',
        ]
    )

    message = OllamaChatLanguage(client).generate_onboarding_message(
        display_name="Sam",
        is_new_user=False,
        field_key="height_cm",
        field_requirement="your height in centimetres",
    )

    assert message == "Please share your height in centimetres."
