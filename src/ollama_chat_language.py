"""Constrained Ollama language helpers for the Streamlit chat experience."""

from __future__ import annotations

import json
import re
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


DAILY_PHASE_INTENT_INSTRUCTION = """Return JSON only with exactly these fields:
{
  "intent": "daily_checkin | current_week_plan | remaining_plan | specific_session | next_week | plan_export | printable_accept | printable_decline | goal_update | profile_update | general_question | unclear",
  "follow_up_intent": "none | current_week_plan | remaining_plan | specific_session | next_week",
  "plan_delivery": "chat | download | unspecified",
  "workout_today": "yes | no | unknown",
  "response": "a short, natural response for the selected intent"
}

The user has completed onboarding and is in the normal conversation phase of a
fitness agent. Classify their request; do not assume every message is a daily
check-in. Use daily_checkin only when the message reports today's body,
recovery, workout completion, or nutrition status. Use general_question for a
question that does not provide a check-in.

Interpret the meaning of the whole message, including negation, timing,
questions about a capability, indirect wording, typos, and multiple requests.
Do not trigger an action merely because it contains a related word. For
example, asking what export means or whether it can be done later is a
general_question, while a request to save the active plan as a file is
plan_export. If the user asks to view a plan in this chat and rejects a file,
use current_week_plan or specific_session with plan_delivery=chat. When a
message contains a current-plan request plus a conditional future export, act
only on the immediate plan-view request. Use next_week only for a real request
to view or create the next plan period, not a goal that happens to mention next
week. Set workout_today only for a daily_checkin: yes for a confirmed planned
or completed workout today, no for an explicit rest/skip today, and unknown
when it is uncertain. Do not invent data or prescribe a workout.

Use follow_up_intent only when the user both supplies a real daily check-in and
explicitly asks for one plan view after that check-in. Otherwise use none. Do
not put an export request in follow_up_intent. The application will separately
ask whether any state-changing action is authorized, so never claim that data
was saved or a plan was changed.

Use printable_accept only when context.awaiting_printable_plan is true and the
user is accepting that immediately preceding offer. A standalone request for a
printable, downloadable, or Excel version of a workout plan is plan_export.

Examples:
- “What’s coming up after this week?” is next_week.
- “What am I doing on Thursday?” is specific_session.
- “My export business is stressing me out, and I slept badly” is daily_checkin,
  not an export request.
- “I guess I’ll just look at next week then” is general_question because it is
  not a clear request.
- “Show this week, then export next week later” is current_week_plan with
  plan_delivery=chat: do not take the conditional future export action."""


ACTION_AUTHORIZATION_INSTRUCTION = """Return JSON only with exactly these fields:
{
  "decision": "confirm | reject | clarify",
  "workout_today": "yes | no | unknown",
  "response": "a short, natural response"
}

Decide whether the user means to perform the proposed action now. Interpret
the whole message semantically; never rely on individual keywords.

For proposed_action=daily_checkin, confirm only if the user is actually
providing a current body, recovery, training, or nutrition status for their
fitness record. Reject plan questions, capability questions, goal discussion,
and statements that merely mention training. Clarify when the message is a
possible check-in but its intended update or today's training status is
uncertain. Set workout_today=yes only for a clear intention or completed
training today; set it to no for a clear rest, skip, or no-training statement
today; otherwise use unknown.

For proposed_action=next_week, confirm only for a clear request to view or
create the next plan period now. Reject negation, reluctance, goals that happen
to mention next week, and requests to defer it.

For proposed_action=plan_export, confirm only for a clear request to create a
downloadable plan file now. Reject refusals, questions about exporting later or
on mobile, and unrelated uses of the word export.

Examples:
- “Show me today's plan, not next week's, and don't export it” rejects both
  daily_checkin and plan_export.
- “Trained yesterday, resting today” confirms daily_checkin with workout_today=no.
- “Thinking about skipping the gym today” clarifies daily_checkin with
  workout_today=unknown.
- “I don't want next week's plan yet” rejects next_week.
- “Can you save this as a file I can open later?” confirms plan_export.

Do not say that an action happened. The application performs it only after a
confirm decision."""


DAILY_PHASE_ANSWER_INSTRUCTION = """Return JSON only with exactly this field:
{"response": "a concise, helpful answer"}

Answer the user's general question using only the supplied active-plan and
profile context. Do not create a check-in, change stored data, invent a
workout, or make medical claims. If the context lacks the answer, say what is
missing and offer the safest relevant next step."""


DAILY_PHASE_INTENTS = {
    "daily_checkin", "current_week_plan", "remaining_plan", "specific_session",
    "next_week", "plan_export", "printable_accept", "printable_decline",
    "goal_update", "profile_update", "general_question", "unclear",
}


DAILY_PHASE_FOLLOW_UP_INTENTS = {
    "none", "current_week_plan", "remaining_plan", "specific_session", "next_week",
}


ACTION_AUTHORIZATION_DECISIONS = {"confirm", "reject", "clarify"}


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
  "prompt": "a friendly question asking what name Adaptr should use"
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

    def classify_daily_phase_message(
        self, message: str, *, context: dict[str, Any]
    ) -> dict[str, str]:
        payload = self._json_payload(
            DAILY_PHASE_INTENT_INSTRUCTION,
            json.dumps({"message": message, "context": context}, default=str),
        )
        intent = payload.get("intent")
        follow_up_intent = payload.get("follow_up_intent", "none")
        plan_delivery = payload.get("plan_delivery", "unspecified")
        workout_today = payload.get("workout_today", "unknown")
        response = payload.get("response")
        if not _is_text(response):
            raise ChatLanguageFormatError("Ollama did not return a valid daily-phase intent.")
        if intent not in DAILY_PHASE_INTENTS:
            intent = "general_question"
        if follow_up_intent not in DAILY_PHASE_FOLLOW_UP_INTENTS:
            follow_up_intent = "none"
        if plan_delivery not in {"chat", "download", "unspecified"}:
            plan_delivery = "unspecified"
        if workout_today not in {"yes", "no", "unknown"}:
            workout_today = "unknown"
        return {
            "intent": intent,
            "follow_up_intent": follow_up_intent,
            "plan_delivery": plan_delivery,
            "workout_today": workout_today,
            "response": response.strip(),
        }

    def authorize_action(
        self,
        message: str,
        *,
        proposed_action: str,
        context: dict[str, Any],
    ) -> dict[str, str]:
        """Ask Ollama for a narrow, independent authorization of a mutation."""
        payload = self._json_payload(
            ACTION_AUTHORIZATION_INSTRUCTION,
            json.dumps(
                {
                    "message": message,
                    "proposed_action": proposed_action,
                    "context": context,
                },
                default=str,
            ),
        )
        decision = payload.get("decision")
        workout_today = payload.get("workout_today", "unknown")
        response = payload.get("response")
        if decision not in ACTION_AUTHORIZATION_DECISIONS or not _is_text(response):
            raise ChatLanguageFormatError("Ollama did not return a valid action authorization.")
        if workout_today not in {"yes", "no", "unknown"}:
            workout_today = "unknown"
        return {
            "decision": decision,
            "workout_today": workout_today,
            "response": response.strip(),
        }

    def answer_daily_phase_question(
        self, message: str, *, context: dict[str, Any]
    ) -> str:
        payload = self._json_payload(
            DAILY_PHASE_ANSWER_INSTRUCTION,
            json.dumps({"message": message, "context": context}, default=str),
        )
        response = payload.get("response")
        if not _is_text(response):
            raise ChatLanguageFormatError("Ollama did not return a valid general answer.")
        return response.strip()

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
                json.dumps({"app": "Adaptr", "first_field": "display_name"}),
            )
            return _validated_landing_welcome(payload)
        except ChatLanguageFormatError:
            return {
                "headline": "Build Today Around the Body You Have",
                "prompt": "What name would you like Adaptr to use?",
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
