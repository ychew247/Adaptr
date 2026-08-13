from __future__ import annotations

import json
from typing import Any


class OllamaNutritionNoteGenerator:
    """Uses Ollama for prose only; numeric nutrition targets are code-owned."""

    def __init__(self, client):
        self.client = client

    def generate(self, targets: dict[str, Any], profile: dict[str, Any], workout_today: bool) -> str:
        prompt = {
            "computed_targets": {
                key: targets[key]
                for key in ("calories_min", "calories_max", "protein_g", "hydration_l", "fiber_g")
            },
            "protein_range_g": targets["protein_range_g"],
            "diet_preferences": profile.get("diet_preferences", "none"),
            "workout_today": workout_today,
            "planned_intensity": targets["planned_intensity"],
            "readiness_band": targets["readiness_band"],
        }
        instruction = (
            "Write a concise fitness-nutrition note. Treat all computed targets as immutable: "
            "do not change, recalculate, or add nutrition numbers. Give meal timing or snack ideas "
            "that respect diet preferences and finish with one short adherence question. Return plain text."
        )
        content = self.client.chat_json_instruction(
            instruction, json.dumps(prompt), require_json=False
        )
        return _plain_note(content)


def _plain_note(content: str) -> str:
    """Accept a plain note and unwrap legacy models that still return JSON."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()
    note = payload.get("note") if isinstance(payload, dict) else None
    return note.strip() if isinstance(note, str) and note.strip() else content.strip()
