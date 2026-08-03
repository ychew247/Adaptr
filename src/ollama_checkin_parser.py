import json
import re


CHECKIN_EXTRACTION_INSTRUCTION = """Return JSON only.

Extract an adaptive fitness check-in from the user's free-form text.

Required JSON shape:
{
  "sleep_hours": number or null,
  "stress_level": integer 1-5 or null,
  "energy_level": integer 1-5 or null,
  "soreness_level": integer 1-5 or null,
  "sore_muscle_groups": array of strings,
  "pain_notes": string or null,
  "weight_kg": number or null,
  "workout_completed": "yes | no | missed | partial | unknown",
  "nutrition_adherence": string or null,
  "nutrition_focus": array of strings,
  "body_flags": array of strings
}

Rules:
- Infer body condition and nutrition signals from natural language.
- Use null or empty arrays when information is missing.
- Do not invent exact numbers if the user did not provide them.
- Keep values concise and snake_case where possible."""


class OllamaCheckinParser:
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client

    def parse(self, text):
        content = self.ollama_client.chat_json_instruction(
            CHECKIN_EXTRACTION_INSTRUCTION,
            text,
        )
        data = json.loads(_strip_code_fence(content))

        return {
            "sleep_hours": data.get("sleep_hours"),
            "stress_level": data.get("stress_level"),
            "energy_level": data.get("energy_level"),
            "soreness_level": data.get("soreness_level"),
            "sore_muscle_groups": data.get("sore_muscle_groups") or [],
            "pain_notes": data.get("pain_notes") or "",
            "weight_kg": data.get("weight_kg"),
            "workout_completed": data.get("workout_completed") or "unknown",
            "nutrition_adherence": data.get("nutrition_adherence") or "",
            "checkin_details": {
                "raw_checkin_text": text,
                "nutrition_focus": data.get("nutrition_focus") or [],
                "body_flags": data.get("body_flags") or [],
                "parser": "ollama",
            },
        }


def _strip_code_fence(content):
    stripped = content.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped
