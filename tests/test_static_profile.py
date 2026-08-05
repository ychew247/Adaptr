from src.m2_static_profile import StaticProfileService, parse_float, parse_int


class FakeProfileRepository:
    def __init__(self):
        self.profiles_by_user_id = {}

    def find_by_user_id(self, user_id):
        return self.profiles_by_user_id.get(user_id)

    def upsert_profile(self, profile):
        self.profiles_by_user_id[profile["user_id"]] = profile
        return profile


def test_parse_int_rejects_non_positive_values():
    try:
        parse_int("0", "age")
    except ValueError as error:
        assert str(error) == "age must be a positive number"
    else:
        raise AssertionError("Expected non-positive age to be rejected")


def test_parse_float_accepts_decimal_values():
    assert parse_float("68.5", "starting weight") == 68.5


def test_static_profile_onboarding_saves_profile_and_routes_to_goal_setup():
    repository = FakeProfileRepository()
    service = StaticProfileService(repository)
    prompts = []
    answers = iter(
        [
            "23",
            "170",
            "68.5",
            "beginner",
            "dumbbells, resistance bands",
            "Mon Wed Fri",
            "old ankle sprain",
            "none",
            "halal, high protein",
            "sedentary",
            "male",
        ]
    )
    messages = []

    result = service.run_onboarding(
        user={"id": "user-1", "display_name": "Yu"},
        ask=lambda prompt: prompts.append(prompt) or next(answers),
        say=messages.append,
    )

    saved = repository.find_by_user_id("user-1")
    assert result == "goal_setup"
    assert saved["age"] == 23
    assert saved["height_cm"] == 170.0
    assert saved["starting_weight_kg"] == 68.5
    assert saved["equipment_access"] == ["dumbbells", "resistance bands"]
    assert saved["weekly_availability"] == "Mon Wed Fri"
    assert saved["bmr_formula_profile"] == "male"
    assert prompts[0] == "Age in years, e.g. 25:"
    assert messages == [
        "Saved Yu's static fitness profile. Next I will ask for the current goal."
    ]


def test_static_profile_onboarding_prompts_include_guidance_and_examples():
    repository = FakeProfileRepository()
    service = StaticProfileService(repository)
    prompts = []
    answers = iter(["23", "170", "68.5", "beginner", "bodyweight", "3 days", "none", "none", "none", "lightly active", "female"])

    service.run_onboarding(
        user={"id": "user-1", "display_name": "Yu"},
        ask=lambda prompt: prompts.append(prompt) or next(answers),
        say=lambda message: None,
    )

    assert prompts == [
        "Age in years, e.g. 25:",
        "Height in cm, e.g. 175:",
        "Starting weight in kg, e.g. 72.5:",
        "Training experience. Choose beginner, intermediate, or advanced. Example: beginner = less than 6 months consistent training:",
        "Equipment access, comma-separated. Examples: bodyweight only, dumbbells, resistance bands, full gym, treadmill:",
        "Weekly availability. Example: 3 days/week, 45 minutes each, Mon/Wed/Fri evenings:",
        "Injury notes. Example: knee pain during squats, old ankle sprain, lower back tightness, or none:",
        "Medical constraints. Example: asthma, heart condition, pregnancy, doctor restrictions, or none:",
        "Diet preferences or restrictions. Example: halal, vegetarian, high protein, lactose intolerant, or none:",
        "Current activity level. Choose sedentary, lightly active, moderately active, or very active:",
        "For the Mifflin-St Jeor BMR formula, choose male or female. This is used only for the formula and is never guessed:",
    ]


def test_static_profile_onboarding_skips_existing_profile():
    repository = FakeProfileRepository()
    repository.upsert_profile({"user_id": "user-1", "age": 23})
    service = StaticProfileService(repository)
    messages = []

    result = service.run_onboarding(
        user={"id": "user-1", "display_name": "Yu"},
        ask=lambda prompt: "should not be asked",
        say=messages.append,
    )

    assert result == "goal_setup"
    assert messages == [
        "I already have Yu's static fitness profile. Next I will ask for the current goal."
    ]
