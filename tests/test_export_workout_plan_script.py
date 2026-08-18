import pytest

from scripts.export_workout_plan import resolve_export_plan


class FakeUserRepository:
    def __init__(self, user):
        self.user = user

    def find_by_normalized_name(self, normalized_name):
        return self.user


class FakePlanRepository:
    def __init__(self, plan):
        self.plan = plan

    def find_active_by_user_id(self, user_id):
        return self.plan


def test_resolve_export_plan_returns_the_validated_active_plan():
    user = {"id": "user-1", "display_name": "Yu", "normalized_name": "yu"}
    plan = {"id": "plan-1", "validation_status": "validated", "plan_json": {"sessions": [{}]}}

    actual_user, actual_plan = resolve_export_plan(
        "yu",
        FakeUserRepository(user),
        FakePlanRepository(plan),
    )

    assert actual_user == user
    assert actual_plan == plan


def test_resolve_export_plan_rejects_an_unvalidated_active_plan():
    with pytest.raises(RuntimeError, match="validated active workout plan"):
        resolve_export_plan(
            "yu",
            FakeUserRepository({"id": "user-1"}),
            FakePlanRepository({"validation_status": "pending"}),
        )


def test_resolve_export_plan_rejects_an_unknown_user():
    with pytest.raises(RuntimeError, match="No user found"):
        resolve_export_plan(
            "unknown",
            FakeUserRepository(None),
            FakePlanRepository(None),
        )

