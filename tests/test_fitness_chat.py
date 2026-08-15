from src.fitness_chat import (
    PROFILE_QUESTIONS,
    format_daily_result,
    plan_table_rows,
    remaining_plan_table_rows,
    profile_answers_to_queue,
)


def test_profile_answers_keep_the_existing_module_question_order():
    answers = {key: f"answer-{index}" for index, (key, _prompt) in enumerate(PROFILE_QUESTIONS)}

    assert profile_answers_to_queue(answers) == [
        f"answer-{index}" for index, _question in enumerate(PROFILE_QUESTIONS)
    ]


def test_profile_fields_store_requirements_not_fixed_user_facing_questions():
    requirements = dict(PROFILE_QUESTIONS)

    assert requirements["age"] == "your age in years"
    assert requirements["height_cm"] == "your height in centimetres"


def test_training_experience_question_explains_each_level():
    requirements = dict(PROFILE_QUESTIONS)
    prompt = requirements["training_experience"]

    assert "beginner = gym or sport experience up to 1 month" in prompt
    assert "intermediate = trained consistently for 1-12 months" in prompt
    assert "advanced = trained consistently for more than 12 months" in prompt


def test_format_daily_result_returns_clean_user_facing_text():
    text = format_daily_result(
        {
            "readiness": {"readiness_score": 76.99, "band": "reduce_volume"},
            "action": "repair_applied",
            "nutrition": {
                "calories_min": 2533,
                "calories_max": 2533,
                "protein_g": 109,
                "hydration_l": 2.61,
                "fiber_g": 30,
                "notes": "Choose meals that feel sustainable today.",
            },
        }
    )

    assert "Readiness: 77/100 - Reduce volume today." in text
    assert "Workout:" not in text
    assert "Nutrition: 2,533 kcal, 109 g protein, 2.61 L water, 30 g fiber." in text
    assert "id" not in text


def test_plan_table_rows_use_the_validated_session_values():
    rows = plan_table_rows(
        {
            "plan_json": {
                "sessions": [
                    {
                        "scheduled_date": "2026-08-13",
                        "day": "Day 2",
                        "focus": "Upper body",
                        "exercises": ["Dumbbell row", "Push-up"],
                        "sets_reps": "3 x 8",
                        "adjustment": "Reduce working sets by 20%.",
                    }
                ]
            }
        }
    )

    assert rows == [
        {
            "Date": "2026-08-13",
            "Day": "Day 2",
            "Focus": "Upper body",
            "Exercises": "Dumbbell row\nPush-up",
            "Sets/Reps": "3 x 8",
            "Adjustment": "Reduce working sets by 20%.",
        }
    ]


def test_remaining_plan_rows_hide_completed_and_past_sessions_but_keep_dates_and_prescriptions():
    plan = {"plan_json": {"sessions": [
        {"scheduled_date": "2026-08-10", "status": "completed", "day": "Day 1", "focus": "Strength", "exercises": ["row"], "sets_reps": "3 x 8"},
        {"scheduled_date": "2026-08-12", "status": "planned", "day": "Day 2", "focus": "Intervals", "exercises": ["bike"], "sets_reps": "6 x 30 seconds"},
        {"scheduled_date": "2026-08-14", "status": "planned", "day": "Day 3", "focus": "Mobility", "exercises": ["walk"], "sets_reps": "20 minutes"},
    ]}}

    rows = remaining_plan_table_rows(plan, "2026-08-13")

    assert rows == [{"Date": "2026-08-14", "Day": "Day 3", "Focus": "Mobility", "Exercises": "walk", "Sets/Reps": "20 minutes", "Adjustment": ""}]
