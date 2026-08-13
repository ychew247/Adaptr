"""Guarded Ollama wording for validated workout-plan presentation."""

from __future__ import annotations

import json
from typing import Any, Mapping


PLAN_PRESENTATION_INSTRUCTION = """Return JSON only with exactly these string fields:
{
  "introduction": "one short encouraging introduction to the validated plan",
  "print_question": "one short question asking whether the user wants a printable/downloadable plan",
  "download_ready": "one short sentence introducing the workbook download"
}

Do not add, remove, rename, or prescribe exercises. Do not repeat the sessions,
numeric readiness score, or nutrition targets. Your role is wording only."""


PLAN_PRESENTATION_CORRECTION_INSTRUCTION = """Return JSON only with exactly these string fields:
{
  "introduction": "one short encouraging introduction to the validated plan",
  "print_question": "a question ending in ? that explicitly asks whether the user wants a printable or downloadable workout plan",
  "download_ready": "one short sentence that explicitly says the downloadable workbook or file is ready"
}

Correct the prior wording. Do not add, remove, rename, or prescribe exercises.
Do not repeat sessions, readiness scores, or nutrition targets."""


class PlanPresentationFormatError(RuntimeError):
    """Raised when Ollama does not return the constrained presentation payload."""


class OllamaPlanPresentationGenerator:
    def __init__(self, ollama_client: Any) -> None:
        self.ollama_client = ollama_client

    def generate(
        self, plan: Mapping[str, Any], readiness: Mapping[str, Any]
    ) -> dict[str, str]:
        context = json.dumps(
            {
                "validated_plan": plan.get("plan_json") or {},
                "readiness_band": readiness.get("band"),
            },
            default=str,
        )
        payload: Mapping[str, Any] = {}
        try:
            content = self.ollama_client.chat_json_instruction(PLAN_PRESENTATION_INSTRUCTION, context)
            payload = json.loads(content)
            return _validated_presentation(payload)
        except (json.JSONDecodeError, PlanPresentationFormatError):
            pass

        try:
            corrected_content = self.ollama_client.chat_json_instruction(
                PLAN_PRESENTATION_CORRECTION_INSTRUCTION,
                json.dumps({"context": context, "invalid_presentation": payload}),
            )
            return _validated_presentation(json.loads(corrected_content))
        except (json.JSONDecodeError, PlanPresentationFormatError):
            return _presentation_fallback()


def _validated_presentation(payload: Mapping[str, Any]) -> dict[str, str]:
    fields = ("introduction", "print_question", "download_ready")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in fields):
        raise PlanPresentationFormatError("Ollama presentation is missing required text fields.")

    presentation = {field: payload[field].strip() for field in fields}
    question = presentation["print_question"].lower()
    if not presentation["print_question"].endswith("?") or not any(
        word in question for word in ("printable", "download", "workbook", "file")
    ):
        raise PlanPresentationFormatError("Ollama did not return a printable-plan question.")
    if not any(word in presentation["download_ready"].lower() for word in ("download", "workbook", "file")):
        raise PlanPresentationFormatError("Ollama did not return a download-ready message.")
    return presentation


def _presentation_fallback() -> dict[str, str]:
    return {
        "introduction": "Your validated workout plan is ready.",
        "print_question": "Would you like a printable version of your workout plan?",
        "download_ready": "Your downloadable workout-plan workbook is ready below.",
    }
