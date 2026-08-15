"""Deterministic session-state transitions for dated workout plans."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


def needs_plan_refresh(plan: Mapping[str, Any] | None) -> bool:
    """Identify persisted legacy session data that cannot support dated coaching."""
    sessions = ((plan or {}).get("plan_json") or {}).get("sessions")
    if not sessions:
        return False
    return any(
        not session.get("scheduled_date")
        or str(session.get("sets_reps") or "").strip().lower() == "as prescribed"
        for session in sessions
    )


def resolve_checkin_session(
    sessions: Sequence[Mapping[str, Any]], checkin_date: str, workout_completed: str
) -> dict[str, Any]:
    """Resolve a check-in without guessing an unscheduled completion."""
    updated = [dict(session) for session in deepcopy(list(sessions))]
    status = str(workout_completed or "unknown").lower()
    scheduled_index = next(
        (
            index
            for index, session in enumerate(updated)
            if str(session.get("scheduled_date") or "") == str(checkin_date)
            and session.get("status", "planned") in {"planned", "rescheduled"}
        ),
        None,
    )
    if status in {"yes", "partial"} and scheduled_index is None:
        return {
            "action": "ask_completed_session",
            "sessions": updated,
            "options": [
                {"day": session.get("day"), "scheduled_date": session.get("scheduled_date")}
                for session in updated
                if session.get("status", "planned") in {"planned", "rescheduled"}
            ],
        }
    if scheduled_index is None or status not in {"yes", "partial", "missed"}:
        return {"action": "no_status_change", "sessions": updated, "options": []}
    updated[scheduled_index]["status"] = "completed" if status in {"yes", "partial"} else "missed"
    return {
        "action": "mark_completed" if status in {"yes", "partial"} else "mark_missed",
        "sessions": updated,
        "options": [],
    }
