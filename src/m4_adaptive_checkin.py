import random


GENERAL_CHECKIN_PROMPTS = [
    (
        "Quick check-in: tell me your body condition and nutrition today. "
        "You can mention sleep, energy, stress, soreness, pain, completed workouts, "
        "protein, hydration, or anything that changed."
    ),
    (
        "How are you feeling today? Include any body signals like soreness or pain, "
        "plus a quick nutrition note such as protein, hydration, appetite, or meal consistency."
    ),
    (
        "What changed since your last update? Body condition, workout completion, "
        "and nutrition are enough."
    ),
]


def build_adaptive_checkin_prompt(recent_checkins=None, prompt_picker=random.choice):
    recent_checkins = recent_checkins or []
    issue = _latest_body_issue(recent_checkins)
    if issue:
        return (
            f"Last time you mentioned {issue}. How does that feel now? "
            "Also share today's soreness, energy, sleep, and nutrition so I can remember it."
        )

    return prompt_picker(GENERAL_CHECKIN_PROMPTS)


class AdaptiveCheckinService:
    def __init__(self, repository, parser):
        self.repository = repository
        self.parser = parser

    def run_checkin(self, user, ask=input, say=print):
        recent_checkins = self.repository.find_recent_by_user_id(user["id"], limit=3)
        prompt = build_adaptive_checkin_prompt(recent_checkins)
        answer = ask(prompt)
        parsed = self.parser.parse(answer)

        checkin = {
            "user_id": user["id"],
            "sleep_hours": parsed["sleep_hours"],
            "stress_level": parsed["stress_level"],
            "energy_level": parsed["energy_level"],
            "soreness_level": parsed["soreness_level"],
            "sore_muscle_groups": parsed["sore_muscle_groups"],
            "pain_notes": parsed["pain_notes"],
            "weight_kg": parsed["weight_kg"],
            "workout_completed": parsed["workout_completed"],
            "nutrition_adherence": parsed["nutrition_adherence"],
            "free_text_note": answer,
            "checkin_details": parsed["checkin_details"],
        }
        saved_checkin = self.repository.create_checkin(checkin)

        say(
            f"Saved {user['display_name']}'s adaptive check-in. "
            "Next I can calculate readiness and adjust the plan."
        )
        return saved_checkin


def _latest_body_issue(recent_checkins):
    for checkin in recent_checkins:
        pain_notes = checkin.get("pain_notes")
        if pain_notes:
            return pain_notes

        soreness_level = checkin.get("soreness_level")
        sore_groups = checkin.get("sore_muscle_groups") or []
        if soreness_level is not None and soreness_level >= 4:
            if sore_groups:
                return f"{', '.join(sore_groups)} soreness"
            return "high soreness"

    return None
