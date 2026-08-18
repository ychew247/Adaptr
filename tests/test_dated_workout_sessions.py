from src.dated_workout_sessions import needs_plan_refresh, resolve_checkin_session


SESSIONS = [
    {"day": "Day 1", "scheduled_date": "2026-08-10", "status": "planned"},
    {"day": "Day 2", "scheduled_date": "2026-08-12", "status": "planned"},
    {"day": "Day 3", "scheduled_date": "2026-08-14", "status": "planned"},
]


def test_completed_checkin_marks_only_the_session_scheduled_for_that_date():
    result = resolve_checkin_session(SESSIONS, "2026-08-12", "yes")

    assert result["action"] == "mark_completed"
    assert result["sessions"][1]["status"] == "completed"
    assert result["sessions"][0]["status"] == "planned"


def test_completed_checkin_on_rest_day_requires_clarification_instead_of_guessing():
    result = resolve_checkin_session(SESSIONS, "2026-08-13", "yes")

    assert result["action"] == "ask_completed_session"
    assert [option["day"] for option in result["options"]] == ["Day 1", "Day 2", "Day 3"]
    assert all(session["status"] == "planned" for session in result["sessions"])


def test_missed_checkin_marks_only_the_session_scheduled_for_that_date():
    result = resolve_checkin_session(SESSIONS, "2026-08-12", "missed")

    assert result["action"] == "mark_missed"
    assert result["sessions"][1]["status"] == "missed"


def test_completed_history_is_not_overwritten_by_a_safety_or_status_update():
    sessions = [{**SESSIONS[0], "status": "completed"}, *SESSIONS[1:]]

    result = resolve_checkin_session(sessions, "2026-08-10", "missed")

    assert result["action"] == "no_status_change"
    assert result["sessions"][0]["status"] == "completed"


def test_legacy_plan_requires_refresh_but_dated_explicit_plan_does_not():
    assert needs_plan_refresh({"plan_json": {"sessions": [{"sets_reps": "As prescribed"}]}})
    assert not needs_plan_refresh(
        {"plan_json": {"sessions": [{"scheduled_date": "2026-08-12", "sets_reps": "3 x 8"}]}}
    )
