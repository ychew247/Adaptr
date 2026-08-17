import pytest

from src.workout_repair_target_selection import (
    WorkoutRepairTargetError,
    resolve_repair_target_dates,
)


SESSIONS = [
    {"day": "Day 1", "scheduled_date": "2026-08-15"},
    {"day": "Day 2", "scheduled_date": "2026-08-17"},
    {"day": "Day 3", "scheduled_date": "2026-08-19"},
]


def test_resolver_matches_day_labels_and_unpadded_dates_once_each():
    assert resolve_repair_target_dates(["Day 2", "2026-8-19", "day 2"], SESSIONS) == [
        "2026-08-17",
        "2026-08-19",
    ]


def test_resolver_rejects_target_not_in_active_plan():
    with pytest.raises(WorkoutRepairTargetError, match="2026-09-01"):
        resolve_repair_target_dates(["2026-09-01"], SESSIONS)
