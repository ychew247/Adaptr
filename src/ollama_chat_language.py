"""Constrained Ollama language helpers for the Streamlit chat experience."""

from __future__ import annotations

import json
from typing import Any


PRINTABLE_PLAN_INTENT_INSTRUCTION = """Return JSON only with exactly these fields:
{
  "intent": "accept | decline | unclear",
  "response": "a short, natural response about the printable workout plan"
}

Interpret the user's reply in the context that they were asked whether they
want a printable or downloadable workout plan. Use accept only when they
clearly want the file. Use decline when they clearly do not. Use unclear for
anything else. Do not discuss, alter, or prescribe workout content."""


ONBOARDING_COPY_INSTRUCTION = """Return JSON only with exactly this field:
{
  "message": "a short, warm chat message"
}

Ask for exactly the requested profile information, using varied natural
wording. Do not request any other information, give fitness advice, or make
health claims. The field requirement is authoritative even when the desired
wording varies."""


LANDING_WELCOME_INSTRUCTION = """Return JSON only with exactly these fields:
{
  "headline": "a short fitness-focused welcome headline",
  "prompt": "a friendly question asking what name Fitness Agent should use"
}

The headline should feel energetic and supportive without making health
claims. The prompt must ask only for the user's preferred name."""


ONBOARDING_COPY_CORRECTION_INSTRUCTION = """Return JSON only with exactly this field:
{
  "message": "a short, warm question"
}

Rewrite the prior message so it clearly asks for exactly the requested profile
field. Name or unmistakably describe that field, end with a question mark, and
do not ask for other information or give fitness advice."""


ONBOARDING_FIELD_TERMS = {
    "display_name": ("name", "call"),
    "age": ("age", "year", "old"),
    "height_cm": ("height", "tall", "cm", "centimet"),
    "starting_weight_kg": ("weight", "weigh", "kg", "kilogram"),
    "training_experience": ("experience", "beginner", "intermediate", "advanced"),
    "equipment_access": ("equipment", "available", "access", "use"),
    "weekly_availability": ("week", "day", "time", "minute", "availability"),
    "injury_notes": ("injury", "pain"),
    "medical_constraints": ("medical", "clinician", "health", "restriction"),
    "diet_preferences": ("diet", "food", "restriction", "preference"),
    "activity_level": ("active", "activity", "sedentary"),
    "bmr_formula_profile": ("male", "female", "bmr"),
}


class ChatLanguageFormatError(RuntimeError):
    """Raised when Ollama does not return a valid constrained chat payload."""


class OllamaChatLanguage:
    """Use Ollama for wording and intent, never for validated application actions."""

    def __init__(self, ollama_client: Any) -> None:
        self.ollama_client = ollama_client

    def classify_printable_plan_reply(self, message: str) -> dict[str, str]:
        payload = self._json_payload(
            PRINTABLE_PLAN_INTENT_INSTRUCTION,
            json.dumps({"user_reply": message}),
        )
        intent = payload.get("intent")
        response = payload.get("response")
        if intent not in {"accept", "decline", "unclear"} or not _is_text(response):
            raise ChatLanguageFormatError("Ollama did not return a valid printable-plan intent.")
        return {"intent": intent, "response": response.strip()}

    def generate_onboarding_message(
        self,
        *,
        display_name: str,
        is_new_user: bool,
        field_key: str,
        field_requirement: str,
    ) -> str:
        request = {
            "display_name": display_name,
            "is_new_user": is_new_user,
            "field_key": field_key,
            "field_requirement": field_requirement,
        }
        payload: dict[str, Any] = {}
        try:
            payload = self._json_payload(
                ONBOARDING_COPY_INSTRUCTION,
                json.dumps(request),
            )
            return _validated_onboarding_message(payload, field_key)
        except ChatLanguageFormatError:
            pass

        try:
            corrected = self._json_payload(
                ONBOARDING_COPY_CORRECTION_INSTRUCTION,
                json.dumps({"request": request, "invalid_message": payload.get("message")}),
            )
            return _validated_onboarding_message(corrected, field_key)
        except ChatLanguageFormatError:
            return _onboarding_fallback(field_requirement)

    def generate_landing_welcome(self) -> dict[str, str]:
        try:
            payload = self._json_payload(
                LANDING_WELCOME_INSTRUCTION,
                json.dumps({"app": "Fitness Agent", "first_field": "display_name"}),
            )
            return _validated_landing_welcome(payload)
        except ChatLanguageFormatError:
            return {
                "headline": "Build Today Around the Body You Have",
                "prompt": "What name would you like Fitness Agent to use?",
            }

    def _json_payload(self, instruction: str, user_text: str) -> dict[str, Any]:
        content = self.ollama_client.chat_json_instruction(instruction, user_text)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise ChatLanguageFormatError("Ollama did not return valid chat JSON.") from error
        if not isinstance(payload, dict):
            raise ChatLanguageFormatError("Ollama did not return a JSON object.")
        return payload


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validated_onboarding_message(payload: dict[str, Any], field_key: str) -> str:
    message = payload.get("message")
    if not _is_text(message):
        raise ChatLanguageFormatError("Ollama did not return a valid onboarding message.")
    normalized = message.strip().lower()
    terms = ONBOARDING_FIELD_TERMS.get(field_key, ())
    if not normalized.endswith("?") or not any(term in normalized for term in terms):
        raise ChatLanguageFormatError("Ollama did not clearly ask for the required profile field.")
    return message.strip()


def _validated_landing_welcome(payload: dict[str, Any]) -> dict[str, str]:
    headline = payload.get("headline")
    prompt = payload.get("prompt")
    if not _is_text(headline) or not _is_text(prompt):
        raise ChatLanguageFormatError("Ollama did not return a valid landing welcome.")
    normalized_prompt = prompt.strip().lower()
    if not normalized_prompt.endswith("?") or not any(term in normalized_prompt for term in ("name", "call")):
        raise ChatLanguageFormatError("Ollama did not return a valid display-name prompt.")
    return {"headline": headline.strip(), "prompt": prompt.strip()}


def _onboarding_fallback(field_requirement: str) -> str:
    return f"Please share {field_requirement.rstrip('.?')}."
