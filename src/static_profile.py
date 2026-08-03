def parse_int(value: str, field_name: str) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as error:
        raise ValueError(f"{field_name} must be a positive number") from error

    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive number")
    return parsed


def parse_float(value: str, field_name: str) -> float:
    try:
        parsed = float(value.strip())
    except ValueError as error:
        raise ValueError(f"{field_name} must be a positive number") from error

    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive number")
    return parsed


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class StaticProfileService:
    def __init__(self, repository):
        self.repository = repository

    def run_onboarding(self, user, ask=input, say=print):
        existing = self.repository.find_by_user_id(user["id"])
        display_name = user["display_name"]
        if existing is not None:
            say(
                f"I already have {display_name}'s static fitness profile. "
                "Next I will ask for the current goal."
            )
            return "goal_setup"

        profile = {
            "user_id": user["id"],
            "age": parse_int(ask("Age in years, e.g. 25:"), "age"),
            "height_cm": parse_float(ask("Height in cm, e.g. 175:"), "height"),
            "starting_weight_kg": parse_float(
                ask("Starting weight in kg, e.g. 72.5:"), "starting weight"
            ),
            "training_experience": ask(
                "Training experience. Choose beginner, intermediate, or advanced. "
                "Example: beginner = less than 6 months consistent training:"
            ),
            "equipment_access": parse_list(
                ask(
                    "Equipment access, comma-separated. Examples: bodyweight only, "
                    "dumbbells, resistance bands, full gym, treadmill:"
                )
            ),
            "weekly_availability": ask(
                "Weekly availability. Example: 3 days/week, 45 minutes each, "
                "Mon/Wed/Fri evenings:"
            ),
            "injury_notes": ask(
                "Injury notes. Example: knee pain during squats, old ankle sprain, "
                "lower back tightness, or none:"
            ),
            "medical_constraints": ask(
                "Medical constraints. Example: asthma, heart condition, pregnancy, "
                "doctor restrictions, or none:"
            ),
            "diet_preferences": ask(
                "Diet preferences or restrictions. Example: halal, vegetarian, "
                "high protein, lactose intolerant, or none:"
            ),
            "activity_level": ask(
                "Current activity level. Choose sedentary, lightly active, "
                "moderately active, or very active:"
            ),
        }

        self.repository.upsert_profile(profile)
        say(f"Saved {display_name}'s static fitness profile. Next I will ask for the current goal.")
        return "goal_setup"
