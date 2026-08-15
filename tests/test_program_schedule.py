import pytest

from src.program_schedule import program_window, next_week_start, week_for_date


def test_program_window_starts_on_the_inquiry_date_without_backfilling_prior_days():
    window = program_window("2026-08-16", duration_weeks=4)

    assert window == {
        "program_start_date": "2026-08-16",
        "program_end_date": "2026-09-12",
        "duration_weeks": 4,
    }


def test_program_window_uses_a_friday_inquiry_as_day_one():
    window = program_window("2026-08-14", duration_weeks=1)

    assert window["program_start_date"] == "2026-08-14"
    assert window["program_end_date"] == "2026-08-20"


def test_week_for_date_uses_the_calendar_week_and_does_not_backfill_prior_days():
    week = week_for_date("2026-08-13", {"program_start_date": "2026-08-10", "duration_weeks": 8})

    assert week == {"week_number": 1, "week_start": "2026-08-10", "within_program": True}


def test_next_week_release_stops_at_the_requested_program_duration():
    active_plan = {"plan_json": {"week_start": "2026-08-31", "week_number": 4, "plan_duration_weeks": 4}}

    assert next_week_start(active_plan) is None


def test_next_week_release_moves_seven_days_from_a_midweek_program_start():
    active_plan = {
        "plan_json": {
            "program_start_date": "2026-08-16",
            "week_start": "2026-08-16",
            "week_number": 1,
            "plan_duration_weeks": 8,
        }
    }

    assert next_week_start(active_plan) == "2026-08-23"


def test_date_outside_the_requested_duration_is_not_a_releasable_week():
    week = week_for_date("2026-09-07", {"program_start_date": "2026-08-10", "duration_weeks": 4})

    assert week["week_number"] == 5
    assert week["within_program"] is False


def test_invalid_zero_week_duration_is_rejected():
    with pytest.raises(ValueError, match="at least one week"):
        program_window("2026-08-13", duration_weeks=0)
