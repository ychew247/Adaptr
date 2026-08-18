"""Select a stored program week independently of the mutable active-plan flag."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

from src.program_schedule import week_for_date


def find_plan_for_date(
    repository: Any,
    *,
    user_id: str,
    reference_date: str | date,
    fallback_plan: Mapping[str, Any] | None,
    fallback_on_miss: bool = True,
) -> Mapping[str, Any] | None:
    """Return the stored plan for the program week containing ``reference_date``.

    Future-plan previews archive earlier weeks in the current schema.  Week
    selection therefore searches by the program calendar before falling back to
    the repository's active-plan record.
    """
    week_start = week_start_for_date(reference_date, fallback_plan)
    finder = getattr(repository, "find_by_user_id_and_week_start", None)
    if week_start is not None and callable(finder):
        selected = finder(user_id, week_start)
        if selected is not None:
            return selected
    latest_on_or_before = getattr(repository, "find_latest_by_user_id_on_or_before_date", None)
    if callable(latest_on_or_before):
        selected = latest_on_or_before(user_id, reference_date)
        if selected is not None:
            return selected
    return fallback_plan if fallback_on_miss else None


def week_start_for_date(
    reference_date: str | date, plan: Mapping[str, Any] | None
) -> str | None:
    """Resolve the program-week start for a calendar date using stored plan metadata."""
    if plan is None:
        return None
    plan_json = plan.get("plan_json") or {}
    program_start = plan_json.get("program_start_date")
    duration_weeks = plan_json.get("duration_weeks") or plan_json.get("plan_duration_weeks")
    if program_start and duration_weeks:
        resolved = week_for_date(
            reference_date,
            {"program_start_date": program_start, "duration_weeks": duration_weeks},
        )
        return resolved["week_start"] if resolved["within_program"] else None

    plan_week_start = plan.get("week_start") or plan_json.get("week_start")
    if plan_week_start is None:
        return None
    start = date.fromisoformat(str(plan_week_start))
    requested = reference_date if isinstance(reference_date, date) else date.fromisoformat(str(reference_date))
    return start.isoformat() if start <= requested <= start + timedelta(days=6) else None
