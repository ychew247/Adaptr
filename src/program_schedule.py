"""Calendar rules for releasing a multi-week program one week at a time."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping


def program_window(start_date: str | date, duration_weeks: int) -> dict[str, Any]:
    if duration_weeks <= 0:
        raise ValueError("Program duration must be at least one week.")
    first_week = _date(start_date)
    return {
        "program_start_date": first_week.isoformat(),
        "program_end_date": (first_week + timedelta(days=duration_weeks * 7 - 1)).isoformat(),
        "duration_weeks": duration_weeks,
    }


def week_for_date(checkin_date: str | date, program: Mapping[str, Any]) -> dict[str, Any]:
    current = _date(checkin_date)
    start = _date(program["program_start_date"])
    duration = int(program["duration_weeks"])
    week_number = (current - start).days // 7 + 1
    return {
        "week_number": week_number,
        "week_start": (start + timedelta(days=(week_number - 1) * 7)).isoformat(),
        "within_program": 1 <= week_number <= duration,
    }


def next_week_start(active_plan: Mapping[str, Any]) -> str | None:
    plan = active_plan.get("plan_json") or active_plan
    duration = int(plan.get("plan_duration_weeks") or 0)
    current_week = int(plan.get("week_number") or 1)
    if current_week >= duration:
        return None
    return (_date(plan["week_start"]) + timedelta(days=7)).isoformat()


def _date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))
