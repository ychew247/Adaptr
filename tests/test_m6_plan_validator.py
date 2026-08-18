from src.m6_plan_validator import validate_plan


def test_validator_rejects_unsafe_equipment_injury_and_volume_violations():
    plan = {
        "intensity_band": "normal",
        "sessions": [
            {
                "day": "Day 1",
                "focus": "Heavy shoulder work",
                "exercises": ["barbell overhead press", "barbell squat"],
                "sets_reps": "6 x 8",
            }
        ],
    }
    constraints = {
        "safety_gate": {"active": True, "reason": "sharp pain"},
        "intensity_ceiling": "recovery",
        "volume_ceiling_sets_per_session": 4,
        "schedule": {"max_sessions": 1},
        "equipment_access": ["dumbbells"],
        "forbidden_exercises": ["overhead press"],
    }

    result = validate_plan(plan, constraints, past_plans=[])

    assert result["hard_validation"]["valid"] is False
    assert "safety_gate_violation" in result["hard_validation"]["error_codes"]
    assert "equipment_violation" in result["hard_validation"]["error_codes"]
    assert "injury_exclusion_violation" in result["hard_validation"]["error_codes"]
    assert "volume_ceiling_violation" in result["hard_validation"]["error_codes"]


def test_validator_rejects_wrong_sport_specific_drills():
    plan = {
        "intensity_band": "normal",
        "sessions": [
            {
                "day": "Day 4",
                "focus": "Lower Body Strength and Agility",
                "exercises": [
                    "Badminton Footwork Intervals",
                    "Split-Step Reaction Drill",
                    "Single-Leg Balance",
                ],
                "sets_reps": "3 sets of 12 reps, 45 minutes",
            }
        ],
    }
    constraints = {
        "safety_gate": {"active": False, "reason": "No hard pain flag."},
        "intensity_ceiling": "normal",
        "volume_ceiling_sets_per_session": 18,
        "schedule": {"max_sessions": 4},
        "equipment_access": ["full gym"],
        "forbidden_exercises": [],
        "target_sports": ["basketball"],
    }

    result = validate_plan(plan, constraints, past_plans=[])

    assert result["hard_validation"]["valid"] is False
    assert "sport_mismatch_violation" in result["hard_validation"]["error_codes"]


def test_validator_allows_general_agility_drills_for_sport_goals():
    plan = {
        "intensity_band": "normal",
        "sessions": [
            {
                "day": "Day 4",
                "focus": "Lower Body Strength and Agility",
                "exercises": ["Lateral Shuffle", "Single-Leg Balance"],
                "sets_reps": "3 sets of 12 reps",
            }
        ],
    }
    constraints = {
        "safety_gate": {"active": False, "reason": "No hard pain flag."},
        "intensity_ceiling": "normal",
        "volume_ceiling_sets_per_session": 18,
        "schedule": {"max_sessions": 4},
        "equipment_access": ["full gym"],
        "forbidden_exercises": [],
        "target_sports": ["basketball"],
    }

    result = validate_plan(plan, constraints, past_plans=[])

    assert result["hard_validation"]["valid"] is True


def test_validator_rejects_duplicate_day_labels_and_sessions_outside_the_plan_week():
    plan = {
        "week_start": "2026-08-22",
        "intensity_band": "normal",
        "sessions": [
            {"day": "Day 2", "scheduled_date": "2026-08-23", "exercises": ["dumbbell row"]},
            {"day": "Day 2", "scheduled_date": "2026-08-25", "exercises": ["lateral shuffle"]},
            {"day": "Day 3", "scheduled_date": "2026-08-27", "exercises": ["dumbbell squat"]},
            {"day": "Day 4", "scheduled_date": "2026-08-29", "exercises": ["mobility flow"]},
        ],
    }
    constraints = {
        "safety_gate": {"active": False},
        "intensity_ceiling": "normal",
        "schedule": {"max_sessions": 4},
        "equipment_access": ["dumbbells"],
        "forbidden_exercises": [],
    }

    result = validate_plan(plan, constraints, [])

    assert "duplicate_session_day" in result["hard_validation"]["error_codes"]
    assert "session_outside_plan_week" in result["hard_validation"]["error_codes"]
