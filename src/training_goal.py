import re


GENERAL_GOAL_PROMPT = """What is your training target?

Describe it naturally. Include what kind of athlete or trainee you are, any target muscles or performance areas, your desired outcome, and how long the plan should run.

Examples:
- I am a futsal athlete and want stronger hamstrings and calves, better VO2 max, and to stay lean over 3 months.
- I want bigger shoulders and arms in 8 weeks.
- I want fat loss and stronger core muscles over 1 month."""


MUSCLE_KEYWORDS = {
    "hamstring": "hamstrings",
    "hamstrings": "hamstrings",
    "calf": "calves",
    "calves": "calves",
    "core": "core",
    "abs": "core",
    "shoulder": "shoulders",
    "shoulders": "shoulders",
    "arm": "arms",
    "arms": "arms",
    "chest": "chest",
    "back": "back",
    "glute": "glutes",
    "glutes": "glutes",
    "quad": "quads",
    "quads": "quads",
}

SPORT_KEYWORDS = {
    "futsal": "futsal",
    "football": "football",
    "soccer": "football",
    "runner": "running",
    "running": "running",
    "run": "running",
    "badminton": "badminton",
    "basketball": "basketball",
    "cycling": "cycling",
    "cyclist": "cycling",
    "swimming": "swimming",
    "swimmer": "swimming",
    "lifter": "strength_training",
    "bodybuilder": "bodybuilding",
}

OUTCOME_KEYWORDS = {
    "fat loss": "fat_loss",
    "lose fat": "fat_loss",
    "weight loss": "fat_loss",
    "lean": "lean_maintenance",
    "vo2": "vo2_max",
    "stamina": "vo2_max",
    "endurance": "vo2_max",
    "strength": "strength",
    "stronger": "strength",
    "strengthen": "strength",
    "muscle gain": "muscle_gain",
    "build muscle": "muscle_gain",
    "bigger": "muscle_gain",
    "physique": "physique",
}


def parse_training_goal(text):
    normalized = text.lower()
    athlete_type = _find_first_keyword(normalized, SPORT_KEYWORDS)
    target_muscle_groups = _find_all_keywords(normalized, MUSCLE_KEYWORDS)
    desired_outcomes = _find_all_keywords(normalized, OUTCOME_KEYWORDS)
    plan_duration_weeks = _parse_duration_weeks(normalized)
    goal_type = _choose_goal_type(athlete_type, desired_outcomes)
    missing_fields = []

    if not desired_outcomes:
        missing_fields.append("desired_outcome")
    if plan_duration_weeks is None:
        missing_fields.append("plan_duration")

    return {
        "goal_type": goal_type,
        "plan_duration_weeks": plan_duration_weeks,
        "goal_details": {
            "raw_goal_text": text,
            "athlete_type": athlete_type,
            "target_muscle_groups": target_muscle_groups,
            "desired_outcomes": desired_outcomes,
            "missing_fields": missing_fields,
        },
    }


def build_follow_up_prompt(missing_fields):
    prompts = []
    if "desired_outcome" in missing_fields:
        prompts.append(
            "What outcome do you want most, e.g. fat loss, VO2 max, stronger core, or bigger shoulders?"
        )
    if "plan_duration" in missing_fields:
        prompts.append("How long should the plan run, e.g. 4 weeks, 8 weeks, or 3 months?")

    return "I need a little more detail before saving the goal. " + " ".join(prompts)


class TrainingGoalService:
    def __init__(self, repository, parser=None):
        self.repository = repository
        self.parser = parser or parse_training_goal

    def run_goal_setup(self, user, ask=input, say=print):
        existing = self.repository.find_active_by_user_id(user["id"])
        display_name = user["display_name"]
        if existing is not None:
            say(
                f"I already have {display_name}'s active training goal. "
                "Next I will ask for adaptive check-in details."
            )
            return "adaptive_checkin"

        answer = ask(GENERAL_GOAL_PROMPT)
        parsed = self.parser.parse(answer) if hasattr(self.parser, "parse") else self.parser(answer)

        if parsed["goal_details"]["missing_fields"]:
            follow_up = ask(build_follow_up_prompt(parsed["goal_details"]["missing_fields"]))
            combined_answer = f"{answer} {follow_up}"
            parsed = (
                self.parser.parse(combined_answer)
                if hasattr(self.parser, "parse")
                else self.parser(combined_answer)
            )

        self.repository.upsert_active_goal(
            {
                "user_id": user["id"],
                "goal_type": parsed["goal_type"],
                "plan_duration_weeks": parsed["plan_duration_weeks"],
                "goal_details": parsed["goal_details"],
                "status": "active",
            }
        )
        say(f"Saved {display_name}'s training goal. Next I will ask for adaptive check-in details.")
        return "adaptive_checkin"


def _find_first_keyword(text, keyword_map):
    for keyword, value in keyword_map.items():
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return value
    return None


def _find_all_keywords(text, keyword_map):
    matches = []
    for keyword, value in keyword_map.items():
        match = re.search(rf"\b{re.escape(keyword)}\b", text)
        if match:
            matches.append((match.start(), value))
    matches.sort(key=lambda item: item[0])

    found = []
    for _position, value in matches:
        if value not in found:
            found.append(value)
    return found


def _parse_duration_weeks(text):
    week_match = re.search(r"\b(\d+)\s*(week|weeks|wk|wks)\b", text)
    if week_match:
        return int(week_match.group(1))

    month_match = re.search(r"\b(\d+)\s*(month|months|mth|mths)\b", text)
    if month_match:
        return int(month_match.group(1)) * 4

    return None


def _choose_goal_type(athlete_type, desired_outcomes):
    if athlete_type and "vo2_max" in desired_outcomes and len(desired_outcomes) > 1:
        return "sport_conditioning"
    if desired_outcomes:
        return desired_outcomes[0]
    if athlete_type:
        return "sport_conditioning"
    return "general_wellness"
