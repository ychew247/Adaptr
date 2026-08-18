from src.ollama_chat_language import OllamaChatLanguage
from decimal import Decimal


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


def test_daily_phase_intent_uses_ollama_to_recognize_a_general_plan_question():
    client = FakeOllamaClient(
        ['{"intent":"general_question","plan_delivery":"unspecified","workout_today":"unknown","response":"I can explain the active plan."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "Why is Day 1 no longer in the table?",
        context={"has_active_plan": True, "awaiting_printable_plan": False},
    )

    assert outcome == {
        "intent": "general_question",
        "follow_up_intent": "none",
        "plan_delivery": "unspecified",
        "workout_today": "unknown",
        "response": "I can explain the active plan.",
    }
    assert "Day 1" in client.calls[0]["user_text"]


def test_daily_phase_intent_keeps_the_semantic_checkin_classification():
    client = FakeOllamaClient(
        ['{"intent":"daily_checkin","plan_delivery":"unspecified","workout_today":"unknown","response":"Let us review today."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "What does the adjustment column mean?",
        context={"has_active_plan": True, "awaiting_printable_plan": False},
    )

    assert outcome["intent"] == "daily_checkin"


def test_daily_phase_intent_accepts_json_wrapped_in_a_markdown_code_fence():
    fenced_response = '''```json
        {"intent":"daily_checkin","plan_delivery":"unspecified","workout_today":"yes","response":"I will record this check-in."}
        ```'''
    client = FakeOllamaClient(
        [fenced_response, fenced_response]
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "slept 7 hours and I plan to train today",
        context={"has_active_plan": True},
    )

    assert outcome["intent"] == "daily_checkin"
    assert outcome["workout_today"] == "yes"


def test_daily_phase_intent_retries_once_after_malformed_ollama_json():
    client = FakeOllamaClient(
        [
            "not valid json",
            ('{"intent":"daily_checkin","follow_up_intent":"none",'
             '"plan_delivery":"unspecified","workout_today":"yes",'
             '"response":"I will record this check-in."}'),
        ]
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "slept 7 hours, energy 7/10, no soreness, and I plan to train today",
        context={"has_active_plan": True},
    )

    assert outcome["intent"] == "daily_checkin"
    assert outcome["workout_today"] == "yes"
    assert len(client.calls) == 2


def test_daily_phase_intent_retries_once_after_an_invalid_ollama_schema():
    client = FakeOllamaClient(
        [
            '{"intent":"daily_checkin","workout_today":"yes"}',
            ('{"intent":"daily_checkin","follow_up_intent":"none",'
             '"plan_delivery":"unspecified","workout_today":"yes",'
             '"response":"I will record this check-in."}'),
        ]
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "slept 7 hours, energy 7/10, no soreness, and I plan to train today",
        context={"has_active_plan": True},
    )

    assert outcome["intent"] == "daily_checkin"
    assert len(client.calls) == 2


def test_daily_phase_intent_serializes_database_style_context_values():
    client = FakeOllamaClient(
        ['{"intent":"general_question","plan_delivery":"unspecified","workout_today":"unknown","response":"Your stored plan is available."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "Can you explain my plan?",
        context={"profile": {"starting_weight_kg": Decimal("72.5")}},
    )

    assert outcome["intent"] == "general_question"
    assert "72.5" in client.calls[0]["user_text"]


def test_daily_phase_intent_defaults_omitted_routing_metadata_without_replacing_the_model_intent():
    client = FakeOllamaClient(
        ['{"intent":"current_week_plan","response":"Showing it here."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "show it here, not as a file",
        context={"has_active_plan": True},
    )

    assert outcome == {
        "intent": "current_week_plan",
        "follow_up_intent": "none",
        "plan_delivery": "unspecified",
        "workout_today": "unknown",
        "response": "Showing it here.",
    }


def test_daily_phase_intent_defaults_invalid_routing_metadata_without_replacing_the_model_intent():
    client = FakeOllamaClient(
        ['{"intent":"general_question","plan_delivery":null,"workout_today":"maybe","response":"You can export later."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "is there a way to export later?",
        context={"has_active_plan": True},
    )

    assert outcome["intent"] == "general_question"
    assert outcome["plan_delivery"] == "unspecified"
    assert outcome["workout_today"] == "unknown"


def test_daily_phase_intent_safely_falls_back_to_a_question_for_an_unknown_model_label():
    client = FakeOllamaClient(
        ['{"intent":"current_week_then_export","response":"I can show it first."}']
    )

    outcome = OllamaChatLanguage(client).classify_daily_phase_message(
        "can you export next week's plan after showing me this week's?",
        context={"has_active_plan": True},
    )

    assert outcome == {
        "intent": "general_question",
        "follow_up_intent": "none",
        "plan_delivery": "unspecified",
        "workout_today": "unknown",
        "response": "I can show it first.",
    }


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
