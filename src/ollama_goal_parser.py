import json
import re


VALID_GOAL_TYPES = {
    "fat_loss",
    "muscle_gain",
    "strength",
    "vo2_max",
    "sport_conditioning",
    "physique",
    "general_wellness",
}


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
- Treat "month-ish", "a month", and "one month" as 4 weeks.
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
        desired_outcomes = _as_list(data.get("desired_outcomes"))
        plan_duration_weeks = _normalize_duration_weeks(text, data.get("plan_duration_weeks"))
        athlete_type = data.get("athlete_type")
        missing_fields = []

        if not desired_outcomes:
            missing_fields.append("desired_outcome")
        if plan_duration_weeks is None:
            missing_fields.append("plan_duration")

        goal_type = _normalize_goal_type(data.get("goal_type"), athlete_type, desired_outcomes)

        return {
            "goal_type": goal_type,
            "plan_duration_weeks": plan_duration_weeks,
            "goal_details": {
                "raw_goal_text": text,
                "athlete_type": athlete_type,
                "target_muscle_groups": _as_list(data.get("target_muscle_groups")),
                "desired_outcomes": desired_outcomes,
                "training_style": _as_list(data.get("training_style")),
                "sport_specific_focus": _as_list(data.get("sport_specific_focus")),
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


def _normalize_goal_type(goal_type, athlete_type, desired_outcomes):
    if goal_type in VALID_GOAL_TYPES:
        return goal_type
    return _fallback_goal_type(athlete_type, desired_outcomes)


def _normalize_duration_weeks(text, model_duration):
    text_hint = _duration_hint_weeks(text)
    if text_hint is not None:
        return text_hint
    if isinstance(model_duration, int) and model_duration > 0:
        return model_duration
    return model_duration


def _duration_hint_weeks(text):
    normalized = text.lower()
    week_match = re.search(r"\b(\d+)\s*(?:-|\s)*(week|weeks|wk|wks)(?:-|\s)?ish\b", normalized)
    if week_match:
        return int(week_match.group(1))

    week_match = re.search(r"\b(\d+)\s*(?:-|\s)*(week|weeks|wk|wks)\b", normalized)
    if week_match:
        return int(week_match.group(1))

    month_match = re.search(r"\b(\d+)\s*(?:-|\s)*(month|months|mth|mths)(?:-|\s)?ish\b", normalized)
    if month_match:
        return int(month_match.group(1)) * 4

    month_match = re.search(r"\b(\d+)\s*(?:-|\s)*(month|months|mth|mths)\b", normalized)
    if month_match:
        return int(month_match.group(1)) * 4

    if re.search(r"\b(?:a|one)\s+month(?:-|\s)?ish\b", normalized):
        return 4
    if re.search(r"\bmonth(?:-|\s)?ish\b", normalized):
        return 4
    if re.search(r"\b(?:a|one)\s+month\b", normalized):
        return 4
    if re.search(r"\bcouple\s+of\s+months\b", normalized):
        return 8
    return None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    if isinstance(value, dict):
        items = []
        for key, item_value in value.items():
            if item_value is True:
                items.append(str(key))
            elif item_value:
                items.append(f"{key}: {item_value}")
        return items
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value)]
