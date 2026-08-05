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
