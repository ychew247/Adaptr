from ui.chat_state import ChatSession
from ui.chat_controller import FitnessChatController


def test_new_chat_resets_the_conversation_to_a_welcome_message():
    session = ChatSession()
    session.add_message("user", "Old check-in")

    session.start_new_chat("Welcome. What should I call you?", welcome_headline="Time to move.")

    assert session.phase == "identity"
    assert session.messages == [{"role": "assistant", "content": "Welcome. What should I call you?"}]
    assert session.welcome_headline == "Time to move."
    assert session.show_welcome_screen is True
    assert session.user is None
    assert session.awaiting_printable_plan is False


def test_session_keeps_structured_plan_and_download_metadata():
    session = ChatSession()

    session.add_message(
        "assistant",
        "Your plan is ready.",
        plan={"plan_json": {"sessions": []}},
        filename="mock_workout_plan.xlsx",
    )

    assert session.messages[0]["plan"] == {"plan_json": {"sessions": []}}
    assert session.messages[0]["filename"] == "mock_workout_plan.xlsx"


def test_begin_message_adds_user_message_before_agent_work_runs():
    session = ChatSession()
    controller = FitnessChatController(session)

    message = controller.begin_message("  I slept well and will train today.  ")

    assert message == "I slept well and will train today."
    assert session.status == "Working"
    assert session.show_welcome_screen is False
    assert session.messages == [
        {"role": "user", "content": "I slept well and will train today."}
    ]
