"""Deterministic validation of user-requested workout-repair targets."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence


class WorkoutRepairTargetError(ValueError):
    """Raised when a requested repair target does not exist in the active plan."""


def resolve_repair_target_dates(
    references: Sequence[str], sessions: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Resolve user references to unique scheduled dates in the active plan."""
    resolved: list[str] = []
    for reference in references:
        target_date = _resolve_reference(reference, sessions)
        if target_date not in resolved:
            resolved.append(target_date)
    return resolved


def _resolve_reference(reference: str, sessions: Sequence[Mapping[str, Any]]) -> str:
    normalized = reference.strip().casefold()
    date_reference = _normalize_date(reference)
    for session in sessions:
        scheduled_date = str(session.get("scheduled_date") or "")
        if date_reference and scheduled_date == date_reference:
            return scheduled_date
        if str(session.get("day") or "").strip().casefold() == normalized:
            return scheduled_date
    raise WorkoutRepairTargetError(
        f"I could not find '{reference}' in the current workout plan to repair."
    )


def _normalize_date(reference: str) -> str | None:
    parts = reference.strip().split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat()
    except ValueError:
        return None
