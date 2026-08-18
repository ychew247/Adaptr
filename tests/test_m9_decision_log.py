import pytest

from src.m9_decision_log import DecisionLogError, DecisionLogService


class Repository:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []

    def find_by_idempotency_key(self, user_id, decision_type, idempotency_key):
        return self.existing

    def create_decision(self, decision):
        self.created.append(decision)
        return {"id": "decision-1", **decision}

    def timeline_for_user(self, user_id, limit=20):
        return [{"id": "decision-2", "user_id": user_id}]


def test_readiness_log_records_checkin_evidence_with_a_stable_duplicate_key():
    repository = Repository()
    service = DecisionLogService(repository)

    saved = service.log_readiness_assessment(
        user_id="user-1",
        checkin={"id": "checkin-1", "checkin_date": "2026-08-05"},
        readiness={
            "readiness_score": 62.5,
            "band": "reduce_volume",
            "safety_triggered": False,
            "components": {"deduction": 37.5},
        },
    )

    assert saved["decision_type"] == "readiness_assessment"
    assert saved["idempotency_key"] == "checkin:checkin-1"
    assert saved["data_used"] == {
        "checkin_id": "checkin-1",
        "readiness_components": {"deduction": 37.5},
    }
    assert saved["validation_status"] == "calculated"


def test_duplicate_event_returns_saved_row_without_a_second_write():
    existing = {"id": "decision-existing", "decision_type": "readiness_assessment"}
    repository = Repository(existing=existing)
    service = DecisionLogService(repository)

    saved = service.log_readiness_assessment(
        user_id="user-1",
        checkin={"id": "checkin-1", "checkin_date": "2026-08-05"},
        readiness={
            "readiness_score": 62.5,
            "band": "reduce_volume",
            "safety_triggered": False,
            "components": {},
        },
    )

    assert saved == existing
    assert repository.created == []


def test_unknown_decision_type_is_rejected_before_persistence():
    repository = Repository()
    service = DecisionLogService(repository)

    with pytest.raises(DecisionLogError, match="Unsupported decision type"):
        service.log(
            decision_type="unknown",
            user_id="user-1",
            idempotency_key="event-1",
            trigger_date="2026-08-05",
            reason="Unknown action.",
        )

    assert repository.created == []


def test_timeline_delegates_to_the_repository():
    service = DecisionLogService(Repository())

    assert service.timeline_for_user("user-1") == [{"id": "decision-2", "user_id": "user-1"}]

