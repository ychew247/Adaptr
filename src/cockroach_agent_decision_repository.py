"""CockroachDB persistence for auditable agent decisions."""

from __future__ import annotations

import json
from typing import Any, Sequence


class CockroachAgentDecisionRepository:
    def __init__(self, connection: Any):
        self.connection = connection

    def find_repair_by_trigger(
        self, user_id: str, plan_id: str, trigger_date: str
    ) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id, user_id, checkin_id, plan_id, trigger_date, decision_type, reason,
                  data_used, plan_change, safety_flags, validation_status, validation_notes,
                  retrieved_memory_ids, generation_attempt, created_at
                FROM agent_decisions
                WHERE user_id = %s AND plan_id = %s AND trigger_date = %s
                  AND decision_type = 'plan_repair'
                LIMIT 1
                """,
                (user_id, plan_id, trigger_date),
            )
            row = cursor.fetchone()
        return self._row_to_decision(row) if row else None

    def find_by_idempotency_key(
        self, user_id: str, decision_type: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id, user_id, checkin_id, plan_id, trigger_date, decision_type, reason,
                  data_used, plan_change, safety_flags, validation_status, validation_notes,
                  retrieved_memory_ids, generation_attempt, created_at, idempotency_key,
                  parent_decision_id
                FROM agent_decisions
                WHERE user_id = %s AND decision_type = %s AND idempotency_key = %s
                LIMIT 1
                """,
                (user_id, decision_type, idempotency_key),
            )
            row = cursor.fetchone()
        return self._row_to_decision(row) if row else None

    def create_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_decisions (
                  user_id, checkin_id, plan_id, trigger_date, decision_type, idempotency_key,
                  reason, data_used, plan_change, safety_flags, validation_status,
                  validation_notes, retrieved_memory_ids, generation_attempt, parent_decision_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                  id, user_id, checkin_id, plan_id, trigger_date, decision_type, reason,
                  data_used, plan_change, safety_flags, validation_status, validation_notes,
                  retrieved_memory_ids, generation_attempt, created_at, idempotency_key,
                  parent_decision_id
                """,
                self._insert_params(decision),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return self._row_to_decision(row)

    def create_repair_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        return self.create_decision(
            {
                **decision,
                "idempotency_key": decision.get("idempotency_key")
                or f"repair:{decision['plan_id']}:{decision['trigger_date']}",
            }
        )

    def timeline_for_user(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id, user_id, checkin_id, plan_id, trigger_date, decision_type, reason,
                  data_used, plan_change, safety_flags, validation_status, validation_notes,
                  retrieved_memory_ids, generation_attempt, created_at, idempotency_key,
                  parent_decision_id
                FROM agent_decisions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
        return [self._row_to_decision(row) for row in rows]

    @staticmethod
    def _insert_params(decision: dict[str, Any]) -> tuple[Any, ...]:
        return (
            decision["user_id"],
            decision.get("checkin_id"),
            decision.get("plan_id"),
            decision["trigger_date"],
            decision["decision_type"],
            decision["idempotency_key"],
            decision["reason"],
            json.dumps(decision.get("data_used") or {}),
            json.dumps(decision.get("plan_change") or {}),
            decision.get("safety_flags") or [],
            decision.get("validation_status", "pending"),
            json.dumps(decision.get("validation_notes") or {}),
            decision.get("retrieved_memory_ids") or [],
            decision.get("generation_attempt", 1),
            decision.get("parent_decision_id"),
        )

    @staticmethod
    def _row_to_decision(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": row[0],
            "user_id": row[1],
            "checkin_id": row[2],
            "plan_id": row[3],
            "trigger_date": row[4],
            "decision_type": row[5],
            "reason": row[6],
            "data_used": _json_value(row[7]),
            "plan_change": _json_value(row[8]),
            "safety_flags": list(row[9] or []),
            "validation_status": row[10],
            "validation_notes": _json_value(row[11]),
            "retrieved_memory_ids": list(row[12] or []),
            "generation_attempt": row[13],
            "created_at": row[14],
            "idempotency_key": row[15] if len(row) > 15 else None,
            "parent_decision_id": row[16] if len(row) > 16 else None,
        }


def _json_value(value: Any) -> dict[str, Any]:
    return json.loads(value) if isinstance(value, str) else (value or {})
