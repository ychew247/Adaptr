from src.m6_plan_constraints import derive_plan_constraints


def test_constraints_turn_sharp_shoulder_pain_into_recovery_only_limits():
    constraints = derive_plan_constraints(
        profile={
            "equipment_access": ["dumbbells", "treadmill"],
            "weekly_availability": "4 days/week, 45 minutes",
            "injury_notes": "Previous left shoulder strain",
            "medical_constraints": "",
        },
        goal={"goal_details": {"target_muscle_groups": ["upper_body"]}},
        readiness={"readiness_score": 30, "band": "recovery_day", "safety_triggered": True},
        latest_checkin={"pain_notes": "Sharp left shoulder pain that is worsening"},
    )

    assert constraints["safety_gate"]["active"] is True
    assert constraints["intensity_ceiling"] == "recovery"
    assert constraints["volume_ceiling_sets_per_session"] == 4
    assert constraints["schedule"]["max_sessions"] == 1
    assert "overhead press" in constraints["forbidden_exercises"]
    assert "mobility breathing reset" in constraints["allowed_exercises"]
