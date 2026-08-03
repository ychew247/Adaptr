import json
import re


GOAL_EXTRACTION_INSTRUCTION = """Return JSON only.

Extract a training goal from the user's free-form text.

Required JSON shape:
{
  "goal_type": "fat_loss | muscle_gain | strength | vo2_max | sport_conditioning | physique | general_wellness",
  "plan_duration_weeks": number or null,
  "athlete_type": string or null,
  "target_muscle_groups": array of strings,
  "desired_outcomes": array of strings,
  "training_style": array of strings,
  "sport_specific_focus": array of strings
}

Rules:
- Infer meaning, do not rely only on exact keywords.
- Convert months to weeks using 1 month = 4 weeks.
- Use snake_case values.
- If the user is training for a sport and has performance goals, use goal_type "sport_conditioning".
- If required information is missing, return null or empty arrays instead of inventing it."""


class OllamaGoalParser:
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client

    def parse(self, text):
        content = self.ollama_client.chat_json_instruction(
            GOAL_EXTRACTION_INSTRUCTION,
            text,
        )
        data = json.loads(_strip_code_fence(content))
        desired_outcomes = data.get("desired_outcomes") or []
        plan_duration_weeks = data.get("plan_duration_weeks")
        athlete_type = data.get("athlete_type")
        missing_fields = []

        if not desired_outcomes:
            missing_fields.append("desired_outcome")
        if plan_duration_weeks is None:
            missing_fields.append("plan_duration")

        goal_type = data.get("goal_type") or _fallback_goal_type(athlete_type, desired_outcomes)

        return {
            "goal_type": goal_type,
            "plan_duration_weeks": plan_duration_weeks,
            "goal_details": {
                "raw_goal_text": text,
                "athlete_type": athlete_type,
                "target_muscle_groups": data.get("target_muscle_groups") or [],
                "desired_outcomes": desired_outcomes,
                "training_style": data.get("training_style") or [],
                "sport_specific_focus": data.get("sport_specific_focus") or [],
                "missing_fields": missing_fields,
                "parser": "ollama",
            },
        }


def _strip_code_fence(content):
    stripped = content.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _fallback_goal_type(athlete_type, desired_outcomes):
    if athlete_type:
        return "sport_conditioning"
    if desired_outcomes:
        return desired_outcomes[0]
    return "general_wellness"
