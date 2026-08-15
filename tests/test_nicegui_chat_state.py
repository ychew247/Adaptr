from pathlib import Path
from contextlib import contextmanager

from ui.chat_state import ChatSession
from ui.chat_controller import FitnessChatController
import ui.chat_controller as chat_controller


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def test_chat_page_uses_a_request_token_and_stop_control():
    chat = (PROJECT_ROOT / "ui" / "chat.py").read_text(encoding="utf-8")

    assert "self._request_token" in chat
    assert "self._stop_current_request" in chat
    assert "icon={'stop' if active else 'send'}" in chat


def test_goal_flow_saves_the_same_parsed_ollama_result():
    session = ChatSession()
    session.phase = "goal"
    session.user = {"id": "user-1", "display_name": "Alex"}
    controller = FitnessChatController(session)
    parsed_goal = {
        "goal_type": "sport_conditioning",
        "plan_duration_weeks": 4,
        "goal_details": {
            "raw_goal_text": "I am a recreational basketball player. Make me a month-ish program.",
            "athlete_type": "basketball",
            "target_muscle_groups": ["lower_body", "core"],
            "desired_outcomes": ["strength", "jumping_ability", "agility"],
            "training_style": ["beginner_friendly", "full_gym"],
            "sport_specific_focus": ["basketball_conditioning"],
            "missing_fields": [],
            "parser": "ollama",
        },
    }
    saved = {}

    controller._parse_goal = lambda _text: parsed_goal
    controller._save_goal = lambda answers, parsed_goal=None: saved.update(
        {"answers": answers, "parsed_goal": parsed_goal}
    )

    controller._handle_goal(
        "I am a recreational basketball player. Make me a month-ish program to improve lower-body strength, "
        "jumping ability, agility, court conditioning, and core stability."
    )

    assert saved["parsed_goal"] is parsed_goal


def test_completed_new_profile_goal_is_saved_with_the_ollama_parser(monkeypatch):
    session = ChatSession(phase="goal", user={"id": "user-1", "display_name": "Alex"})
    controller = FitnessChatController(session)
    goals = _FakeGoals()

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "goals": goals,
            "goal_parser": _FakeGoalParser(),
        },
    )

    controller.complete_message(
        "I am a badminton player who wants to improve my smashing power in a 2 month duration."
    )

    assert goals.saved["goal_type"] == "sport_conditioning"
    assert goals.saved["plan_duration_weeks"] == 8
    assert session.phase == "daily"
    assert session.status == "Ready"


def test_goal_setup_retries_once_after_a_transient_database_connection_reset():
    session = ChatSession(phase="goal", user={"id": "user-1", "display_name": "Jordan Lim"})
    controller = FitnessChatController(session)
    attempts = []

    def route_once_then_succeed(_message):
        attempts.append("route")
        if len(attempts) == 1:
            raise RuntimeError("connection closed unexpectedly")

    controller._route_message = route_once_then_succeed

    controller.complete_message("I want stronger core and smash power over 2 months.")

    assert attempts == ["route", "route"]
    assert session.status == "Ready"
    assert not any("could not complete" in item["content"].lower() for item in session.messages)


def test_goal_setup_retries_once_after_an_ssl_connection_close():
    session = ChatSession(phase="goal", user={"id": "user-1", "display_name": "Jordan Lim"})
    controller = FitnessChatController(session)
    attempts = []

    def route_once_then_succeed(_message):
        attempts.append("route")
        if len(attempts) == 1:
            raise RuntimeError("SSL connection has been closed unexpectedly")

    controller._route_message = route_once_then_succeed

    controller.complete_message("I want stronger core and smash power over 2 months.")

    assert attempts == ["route", "route"]
    assert session.status == "Ready"


@contextmanager
def _fake_database_connection():
    yield object()


class _FakePlans:
    def __init__(self, plan):
        self.plan = plan

    def find_active_by_user_id(self, user_id):
        return self.plan


class _FakeGoals:
    def __init__(self):
        self.saved = None

    def find_active_by_user_id(self, user_id):
        return None

    def upsert_active_goal(self, goal):
        self.saved = goal


class _FakeGoalParser:
    def parse(self, text):
        return {
            "goal_type": "sport_conditioning",
            "plan_duration_weeks": 8,
            "goal_details": {
                "raw_goal_text": text,
                "athlete_type": "badminton",
                "target_muscle_groups": [],
                "desired_outcomes": ["smashing_power"],
                "training_style": [],
                "sport_specific_focus": ["badminton_smashing_power"],
                "missing_fields": [],
                "parser": "ollama",
            },
        }


class _FakeProfiles:
    def find_by_user_id(self, user_id):
        return {}


class _FakeChatLanguage:
    def __init__(self):
        self.daily_phase_calls = []

    def classify_printable_plan_reply(self, message):
        raise AssertionError("printable classifier should not handle plan lookup requests")

    def classify_daily_phase_message(self, message, *, context):
        self.daily_phase_calls.append({"message": message, "context": context})
        return {
            "intent": "general_question",
            "plan_delivery": "unspecified",
            "workout_today": "unknown",
            "response": "A normal question.",
        }

    def authorize_action(self, message, *, proposed_action, context):
        return {
            "decision": "confirm",
            "workout_today": "yes",
            "response": "Action confirmed.",
        }

    def answer_daily_phase_question(self, message, *, context):
        return "The adjustment column explains how today's session changes."


class _FixedIntentLanguage(_FakeChatLanguage):
    def __init__(self, intent, *, plan_delivery="unspecified", workout_today="unknown"):
        super().__init__()
        self.intent = intent
        self.plan_delivery = plan_delivery
        self.workout_today = workout_today

    def classify_daily_phase_message(self, message, *, context):
        self.daily_phase_calls.append({"message": message, "context": context})
        return {
            "intent": self.intent,
            "plan_delivery": self.plan_delivery,
            "workout_today": self.workout_today,
            "response": "Semantic route selected.",
        }


class _FakeAgent:
    def __init__(self, plan):
        self.plan_service = _FakePlanService(plan)


class _FakePlanService:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def release_next_week(self, user, *, say):
        self.calls.append(user)
        return "plan_ready"


class _FakePlanPresenter:
    def generate(self, plan, readiness):
        return {
            "introduction": "Here is next week.",
            "print_question": "Do you want a printable or downloadable workout plan?",
            "download_ready": "The downloadable workbook is ready.",
        }


def _plan_for_lookup():
    return {
        "id": "plan-1",
        "plan_json": {
            "week_start": "2026-08-10",
            "sessions": [
                {
                    "scheduled_date": "2026-08-10",
                    "day": "Day 1",
                    "focus": "Lower Body Strength",
                    "exercises": ["Goblet Squat"],
                    "sets_reps": "3 x 8",
                    "adjustment": "Train as planned.",
                    "status": "planned",
                },
                {
                    "scheduled_date": "2026-08-13",
                    "day": "Day 3",
                    "focus": "Agility",
                    "exercises": ["Lateral Shuffle"],
                    "sets_reps": "3 x 30 seconds",
                    "adjustment": "Train as planned.",
                    "status": "planned",
                },
            ],
        },
    }


def test_printable_prompt_does_not_swallow_full_week_plan_lookup(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession()
    session.phase = "daily"
    session.user = {"id": "user-1", "display_name": "Alex"}
    session.awaiting_printable_plan = True
    session.pending_printable_plan = plan
    controller = FitnessChatController(session)

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
                "chat_language": _FixedIntentLanguage("current_week_plan"),
        },
    )

    controller._handle_daily_message("show all the workout throughout the week")

    assert session.messages[-1]["plan"] is plan
    assert session.messages[-1]["as_of_date"] == "2026-08-10"
    assert "full current week" in session.messages[-1]["content"].lower()


def test_printable_decline_is_semantically_handled_without_creating_a_checkin(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession(phase="daily", user={"id": "user-1", "display_name": "Alex"})
    session.awaiting_printable_plan = True
    session.pending_printable_plan = plan
    controller = FitnessChatController(session)

    class _PrintableDeclineLanguage(_FakeChatLanguage):
        def __init__(self):
            super().__init__()
            self.printable_calls = []

        def classify_printable_plan_reply(self, message):
            self.printable_calls.append(message)
            return {"intent": "decline", "response": "Okay, I will keep it in chat."}

        def classify_daily_phase_message(self, message, *, context):
            raise AssertionError("A printable decline must not become a daily check-in.")

    language = _PrintableDeclineLanguage()
    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
            "chat_language": language,
        },
    )

    controller._handle_daily_message("do not give me the export")

    assert language.printable_calls == ["do not give me the export"]
    assert session.awaiting_printable_plan is False
    assert session.pending_printable_plan is None
    assert session.messages[-1]["content"] == "Okay, I will keep it in chat."


def test_semantic_chat_only_request_shows_the_plan_without_offering_an_export(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession(phase="daily", user={"id": "user-1", "display_name": "Alex"})
    controller = FitnessChatController(session)

    class _ChatOnlyLanguage(_FakeChatLanguage):
        def classify_daily_phase_message(self, message, *, context):
            self.daily_phase_calls.append({"message": message, "context": context})
            return {
                "intent": "current_week_plan",
                "plan_delivery": "chat",
                "workout_today": "unknown",
                "response": "Showing the plan here.",
            }

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    chat_language = _ChatOnlyLanguage()

    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
            "chat_language": chat_language,
        },
    )

    controller._handle_daily_message(
        "show me the workout plan in chat only, do not give me the export version"
    )

    assert session.messages[-1]["plan"] is plan
    assert session.messages[-1]["plan_view"] == "full_week"
    assert "print_question" not in session.messages[-1]
    assert "download" not in session.messages[-1]
    assert session.awaiting_printable_plan is False
    assert chat_language.daily_phase_calls[0]["message"] == (
        "show me the workout plan in chat only, do not give me the export version"
    )


def test_day_lookup_shows_full_week_instead_of_running_daily_flow(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession()
    session.phase = "daily"
    session.user = {"id": "user-1", "display_name": "Alex"}
    controller = FitnessChatController(session)

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
                "chat_language": _FixedIntentLanguage("specific_session", plan_delivery="chat"),
        },
    )

    controller._handle_daily_message("where is day 1")

    assert session.messages[-1]["plan"] is plan
    assert session.messages[-1]["as_of_date"] == "2026-08-10"
    assert session.messages[-1]["plan_view"] == "full_week"


def test_ollama_session_lookup_does_not_run_a_checkin(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession()
    session.phase = "daily"
    session.user = {"id": "user-1", "display_name": "Alex"}
    controller = FitnessChatController(session)

    class _SessionLookupLanguage(_FakeChatLanguage):
        def classify_daily_phase_message(self, message, *, context):
            return {
                "intent": "specific_session",
                "plan_delivery": "chat",
                "workout_today": "unknown",
                "response": "Showing that session.",
            }

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
            "chat_language": _SessionLookupLanguage(),
            "agent": _FailIfDailyFlowRuns(),
        },
    )

    controller._handle_daily_message("Could you pull up the session I have this Saturday?")

    assert session.messages[-1]["plan"] is plan
    assert session.messages[-1]["plan_view"] == "full_week"


def test_printable_prompt_does_not_swallow_next_week_generation(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession()
    session.phase = "daily"
    session.user = {"id": "user-1", "display_name": "Alex"}
    session.awaiting_printable_plan = True
    session.pending_printable_plan = plan
    controller = FitnessChatController(session)
    fake_agent = _FakeAgent(plan)

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
                "chat_language": _FixedIntentLanguage("next_week"),
            "agent": fake_agent,
            "plan_presenter": _FakePlanPresenter(),
        },
    )

    controller._handle_daily_message("generate the next week workout beforehand and send it to me")

    assert fake_agent.plan_service.calls == [session.user]
    assert session.messages[-1]["content"] == "Here is next week."
    assert session.messages[-1]["plan"] is plan


def test_general_daily_question_does_not_run_a_checkin_or_repair(monkeypatch):
    plan = _plan_for_lookup()
    session = ChatSession()
    session.phase = "daily"
    session.user = {"id": "user-1", "display_name": "Alex"}
    controller = FitnessChatController(session)

    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(plan),
            "chat_language": _FakeChatLanguage(),
            "agent": _FailIfDailyFlowRuns(),
        },
    )

    controller._handle_daily_message("What does the adjustment column mean?")

    assert session.messages[-1]["content"] == "The adjustment column explains how today's session changes."


def test_first_checkin_assumes_training_when_no_plan_exists(monkeypatch):
    session = ChatSession(phase="daily", user={"id": "user-1", "display_name": "Alex"})
    controller = FitnessChatController(session)

    class _InitialCheckinLanguage(_FakeChatLanguage):
        def classify_daily_phase_message(self, message, *, context):
            return {
                "intent": "daily_checkin",
                "plan_delivery": "unspecified",
                "workout_today": "unknown",
                "response": "Thanks for the check-in.",
            }

    class _InitialPlanAgent:
        def __init__(self):
            self.workout_today = None

        def run_daily_flow(self, _user, *, workout_today, ask, say):
            self.workout_today = workout_today
            return {
                "checkin": {},
                "readiness": {"readiness_score": 85, "band": "train_as_planned"},
                "action": "plan_ready",
                "nutrition": {
                    "calories_min": 2500,
                    "calories_max": 2500,
                    "protein_g": 120,
                    "hydration_l": 2.5,
                    "fiber_g": 30,
                    "notes": "Keep meals consistent.",
                },
            }

    agent = _InitialPlanAgent()
    monkeypatch.setattr(chat_controller, "database_connection", _fake_database_connection)
    monkeypatch.setattr(
        chat_controller,
        "build_runtime",
        lambda _connection, include_agent=False: {
            "profiles": _FakeProfiles(),
            "plans": _FakePlans(None),
            "chat_language": _InitialCheckinLanguage(),
            "agent": agent,
        },
    )

    controller._handle_daily_message("I slept well and my energy is good.")

    assert agent.workout_today is True
    assert "are you planning to train" not in session.messages[-1]["content"].lower()


class _FailIfDailyFlowRuns:
    def run_daily_flow(self, *args, **kwargs):
        raise AssertionError("A general question must not create a daily check-in.")
