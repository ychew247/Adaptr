from src.workout_plan_selection import find_plan_for_date


class _PlanRepository:
    def __init__(self, plans):
        self.plans = plans
        self.requested_week_start = None

    def find_by_user_id_and_week_start(self, user_id, week_start):
        self.requested_week_start = week_start
        return self.plans.get((user_id, week_start))

    def find_latest_by_user_id_on_or_before_date(self, user_id, reference_date):
        return self.plans.get((user_id, "latest_on_or_before", reference_date))


def test_find_plan_for_date_retrieves_the_archived_week_containing_the_inquiry_date():
    user_id = "user-1"
    active_future_plan = {
        "user_id": user_id,
        "week_start": "2026-08-29",
        "status": "active",
        "plan_json": {
            "program_start_date": "2026-08-15",
            "duration_weeks": 8,
            "week_number": 3,
        },
    }
    inquiry_week_plan = {
        "user_id": user_id,
        "week_start": "2026-08-15",
        "status": "archived",
        "plan_json": {"week_number": 1},
    }
    repository = _PlanRepository({(user_id, "2026-08-15"): inquiry_week_plan})

    selected = find_plan_for_date(
        repository,
        user_id=user_id,
        reference_date="2026-08-15",
        fallback_plan=active_future_plan,
    )

    assert repository.requested_week_start == "2026-08-15"
    assert selected is inquiry_week_plan


def test_find_plan_for_date_recovers_the_latest_stored_week_before_the_inquiry_date():
    user_id = "user-1"
    active_future_plan = {
        "user_id": user_id,
        "week_start": "2026-08-29",
        "status": "active",
        "plan_json": {
            "program_start_date": "2026-08-29",
            "duration_weeks": 8,
            "week_number": 1,
        },
    }
    inquiry_week_plan = {"user_id": user_id, "week_start": "2026-08-15", "status": "archived"}
    repository = _PlanRepository(
        {(user_id, "latest_on_or_before", "2026-08-15"): inquiry_week_plan}
    )

    selected = find_plan_for_date(
        repository,
        user_id=user_id,
        reference_date="2026-08-15",
        fallback_plan=active_future_plan,
    )

    assert selected is inquiry_week_plan
