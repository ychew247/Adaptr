"""Ollama adapter for bounded Module 7 exercise substitutions."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from src.ollama_workout_plan_generator import PlanGenerationFormatError


REPAIR_INSTRUCTION = """Return JSON only.

Suggest a single replacement session for a fitness-plan repair. The deterministic repair action is already selected and cannot be overridden.

Required JSON shape:
{
  "replacement_session": {
    "focus": "short focus",
    "exercises": ["exercise"],
    "sets_reps": "specific safe sets, reps, or duration"
  },
  "coaching_note": "short practical note"
}

Rules:
- Obey every equipment, injury, medical, intensity, volume, and schedule constraint.
- Past repair precedents must influence the substitution when relevant: reuse what worked when still safe, and avoid what previously failed.
- Treat validator_feedback as mandatory corrections for this attempt.
- Do not change the repair action or invent medical certainty."""


class OllamaPlanRepairGenerator:
    def __init__(self, ollama_client: Any):
        self.ollama_client = ollama_client

    def generate(
        self,
        plan: Mapping[str, Any],
        repair_action: Mapping[str, Any],
        constraints: Mapping[str, Any],
        retrieved_memories: Sequence[Mapping[str, Any]],
        validator_feedback: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "current_plan": plan,
            "deterministic_repair_action": repair_action,
            "constraints": constraints,
            "retrieved_repair_precedents": list(retrieved_memories),
            "validator_feedback": validator_feedback or {},
        }
        content = self.ollama_client.chat_json_instruction(
            REPAIR_INSTRUCTION,
            json.dumps(payload, default=str),
        )
        try:
            data = json.loads(_strip_code_fence(content))
        except json.JSONDecodeError as error:
            raise PlanGenerationFormatError("Ollama did not return valid repair JSON.") from error
        replacement = data.get("replacement_session") or {}
        if not replacement.get("exercises"):
            raise PlanGenerationFormatError("Ollama repair JSON is missing replacement exercises.")
        return {
            "replacement_session": {
                "focus": replacement.get("focus") or "Adjusted session",
                "exercises": [str(item) for item in replacement["exercises"] if item],
                "sets_reps": replacement.get("sets_reps") or "As prescribed",
            },
            "coaching_note": data.get("coaching_note") or "",
        }


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return match.group(1).strip() if match else stripped
