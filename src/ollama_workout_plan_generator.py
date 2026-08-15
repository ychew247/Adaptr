import json
import re

from src.m6_workout_plan import (
    generate_weekly_plan,
    _readiness_adjustment,
    _target_muscles_from_sessions,
    _unique,
)


WORKOUT_PLAN_INSTRUCTION = """Return JSON only.

Generate a one-week workout plan from the provided fitness profile, active goal, readiness result, and safety constraints.

Required JSON shape:
{
  "overview": "short plan summary",
  "sessions": [
    {
      "day": "Day 1",
      "focus": "session focus",
      "exercises": ["exercise name"],
      "sets_reps": "sets, reps, duration, or intensity",
      "adjustment": "readiness-aware adjustment"
    }
  ],
  "target_muscle_groups": ["upper_body"],
  "coaching_notes": ["short useful note"]
}

Rules:
- Use the requested training goal, athlete type, target muscles, equipment, and weekly availability.
- Respect the provided required_intensity_band and readiness_adjustment.
- If safety_triggered is true, only generate recovery or pain-free mobility work.
- Past precedents must influence the plan: preserve approaches marked as helpful when they remain safe, and avoid approaches associated with poor outcomes or the current injury context.
- Treat validator_feedback as mandatory corrections for this generation attempt.
- Keep nutrition advice out of this plan; Module 8 handles nutrition.
- Do not invent medical certainty or injury diagnosis.
- For a newly released week, preserve core movement patterns and rotate only 2-3 safe exercise variations across the week.
- Keep output concise and practical."""


class PlanGenerationFormatError(RuntimeError):
    """Raised when Ollama returns content that cannot be parsed as plan JSON."""


class OllamaWorkoutPlanGenerator:
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client

    def generate(
        self,
        profile,
        goal,
        readiness,
        constraints=None,
        retrieved_memories=None,
        validator_feedback=None,
    ):
        intensity_band, volume_modifier, adjustment = _readiness_adjustment(readiness)
        constraints = constraints or {}
        retrieved_memories = retrieved_memories or []
        intensity_band = constraints.get("intensity_ceiling") or intensity_band
        volume_modifier = constraints.get("volume_modifier", volume_modifier)
        payload = {
            "profile": profile,
            "goal": goal,
            "readiness": readiness,
            "constraints": constraints,
            "retrieved_precedents": retrieved_memories,
            "validator_feedback": validator_feedback or {},
            "required_intensity_band": intensity_band,
            "volume_modifier": volume_modifier,
            "readiness_adjustment": adjustment,
        }
        content = self.ollama_client.chat_json_instruction(
            WORKOUT_PLAN_INSTRUCTION,
            json.dumps(payload, default=str),
        )
        try:
            data = json.loads(_strip_code_fence(content))
        except json.JSONDecodeError as error:
            raise PlanGenerationFormatError("Ollama did not return valid JSON.") from error
        sessions = _normalize_sessions(data.get("sessions") or [], adjustment)
        if not sessions:
            fallback = generate_weekly_plan(profile, goal, readiness)
            fallback["generator"] = "deterministic_fallback"
            return fallback

        goal_details = goal.get("goal_details") or {}
        target_muscles = _unique(
            [
                *(goal_details.get("target_muscle_groups") or []),
                *(data.get("target_muscle_groups") or []),
                *_target_muscles_from_sessions(sessions),
            ]
        )
        exercise_names = _unique(
            exercise for session in sessions for exercise in session["exercises"]
        )

        return {
            "goal_id": goal["id"],
            "week_start": data.get("week_start") or _today_string(),
            "week_number": data.get("week_number") or 1,
            "plan_duration_weeks": goal.get("plan_duration_weeks"),
            "goal_type": goal["goal_type"],
            "athlete_type": goal_details.get("athlete_type"),
            "target_muscle_groups": target_muscles,
            "exercise_names": exercise_names,
            "intensity_band": intensity_band,
            "volume_modifier": volume_modifier,
            "readiness_score": readiness["readiness_score"],
            "readiness_band": readiness["band"],
            "safety_triggered": readiness["safety_triggered"],
            "overview": data.get("overview") or "",
            "sessions": sessions,
            "coaching_notes": data.get("coaching_notes") or [],
            "generation_context": {
                "training_experience": profile.get("training_experience"),
                "equipment_access": profile.get("equipment_access") or [],
                "weekly_availability": profile.get("weekly_availability"),
                "injury_notes": profile.get("injury_notes"),
                "desired_outcomes": goal_details.get("desired_outcomes") or [],
                "training_style": goal_details.get("training_style") or [],
                "model_required_intensity_band": intensity_band,
                "constraints": constraints,
                "retrieved_memory_ids": [memory.get("id") for memory in retrieved_memories],
                "validator_feedback": validator_feedback or {},
            },
            "generator": "ollama",
        }


def _normalize_sessions(sessions, required_adjustment):
    normalized = []
    for index, session in enumerate(sessions, start=1):
        exercises = session.get("exercises") or []
        prescription = str(session.get("sets_reps") or "").strip()
        if not prescription or prescription.lower() == "as prescribed":
            raise PlanGenerationFormatError("Every workout session needs a specific sets/reps or duration prescription.")
        normalized.append(
            {
                "day": session.get("day") or f"Day {index}",
                "focus": session.get("focus") or "Training session",
                "exercises": [str(exercise) for exercise in exercises if exercise],
                "sets_reps": prescription,
                "adjustment": required_adjustment,
            }
        )
    return [session for session in normalized if session["exercises"]]


def _strip_code_fence(content):
    stripped = content.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _today_string():
    from datetime import date

    return str(date.today())
