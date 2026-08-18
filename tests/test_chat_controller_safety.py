from ui.chat_controller import FitnessChatController
from ui.chat_state import ChatSession


def test_urgent_chest_pain_bypasses_daily_agent_processing():
    session = ChatSession(phase="daily", user={"id": "user-1", "display_name": "Alex"})
    controller = FitnessChatController(session)

    def daily_processing_must_not_run(_message):
        raise AssertionError("daily agent processing ran after an urgent safety message")

    controller._handle_daily_message = daily_processing_must_not_run
    controller.handle_message("I have acute chest pain. Can I still train today?")

    assert "urgent medical" in session.messages[-1]["content"].lower()
    assert session.status == "Ready"
