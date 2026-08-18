import json
from decimal import Decimal

from src.cockroach_agent_decision_repository import CockroachAgentDecisionRepository


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.results.pop(0) if self.results else None


class FakeConnection:
    def __init__(self, results):
        self.cursor_instance = FakeCursor(results)
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


def test_create_repair_decision_persists_the_module6_audit_fields():
    connection = FakeConnection(
        [
            (
                "decision-1", "user-1", "checkin-1", "plan-1", "2026-08-04",
                "plan_repair", "Recovered safely.", {"trigger": "wrist soreness"},
                {"action": "replace"}, [], "validated", {"hard_validation": {"valid": True}},
                ["memory-1"], 2, "2026-08-04T00:00:00Z",
            )
        ]
    )
    decision = {
        "user_id": "user-1",
        "checkin_id": "checkin-1",
        "plan_id": "plan-1",
        "trigger_date": "2026-08-04",
        "decision_type": "plan_repair",
        "reason": "Recovered safely.",
        "data_used": {"trigger": "wrist soreness"},
        "plan_change": {"action": "replace"},
        "safety_flags": [],
        "validation_status": "validated",
        "validation_notes": {"hard_validation": {"valid": True}},
        "retrieved_memory_ids": ["memory-1"],
        "generation_attempt": 2,
    }

    saved = CockroachAgentDecisionRepository(connection).create_repair_decision(decision)

    query, params = connection.cursor_instance.queries[0]
    assert "validation_status" in query
    assert "retrieved_memory_ids" in query
    assert "generation_attempt" in query
    assert params[5] == "repair:plan-1:2026-08-04"
    assert params[-5:] == (
        "validated",
        '{"hard_validation": {"valid": true}}',
        ["memory-1"],
        2,
        None,
    )
    assert saved["trigger_date"] == "2026-08-04"
    assert saved["validation_status"] == "validated"


def test_find_repair_by_trigger_is_scoped_to_user_and_date_across_plan_versions():
    connection = FakeConnection([None])

    result = CockroachAgentDecisionRepository(connection).find_repair_by_trigger(
        "user-1", "plan-1", "2026-08-04"
    )

    query, params = connection.cursor_instance.queries[0]
    assert result is None
    assert "user_id = %s" in query
    assert "plan_id = %s" not in query
    assert "trigger_date = %s" in query
    assert params == ("user-1", "2026-08-04")


def test_insert_params_serializes_decimal_values_in_json_payloads():
    params = CockroachAgentDecisionRepository._insert_params(
        {
            "user_id": "user-1",
            "trigger_date": "2026-08-10",
            "decision_type": "nutrition_target",
            "idempotency_key": "nutrition:target-1",
            "reason": "Nutrition targets calculated.",
            "data_used": {"tdee": Decimal("2314.75")},
            "plan_change": {"hydration_l": Decimal("2.64")},
        }
    )

    assert json.loads(params[7]) == {"tdee": 2314.75}
    assert json.loads(params[8]) == {"hydration_l": 2.64}
