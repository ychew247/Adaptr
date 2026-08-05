from src.m5_readiness_score import compute_readiness


def test_compute_readiness_returns_high_score_for_normal_checkin():
    result = compute_readiness(
        user_history=[
            {"sleep_hours": 7.0, "stress_level": 3, "energy_level": 4, "soreness_level": 2},
            {"sleep_hours": 7.5, "stress_level": 2, "energy_level": 4, "soreness_level": 2},
        ],
        today_checkin={
            "sleep_hours": 7.5,
            "stress_level": 2,
            "energy_level": 4,
            "soreness_level": 2,
            "pain_notes": "",
        },
    )

    assert result["readiness_score"] >= 80
    assert result["band"] == "train_as_planned"
    assert result["safety_triggered"] is False
    assert result["components"]["pain_gate_applied"] is False
    assert set(result["components"]["z_scores"]) == {"sleep", "stress", "energy", "soreness"}


def test_compute_readiness_penalizes_low_sleep_and_high_soreness_continuously():
    result = compute_readiness(
        user_history=[
            {"sleep_hours": 7.5, "stress_level": 2, "energy_level": 4, "soreness_level": 2},
            {"sleep_hours": 7.0, "stress_level": 3, "energy_level": 4, "soreness_level": 2},
            {"sleep_hours": 7.25, "stress_level": 2, "energy_level": 4, "soreness_level": 1},
        ],
        today_checkin={
            "sleep_hours": 5.0,
            "stress_level": 4,
            "energy_level": 2,
            "soreness_level": 5,
            "pain_notes": "",
        },
    )

    assert result["readiness_score"] < 60
    assert result["band"] in {"lighter_session", "recovery_day"}
    assert result["components"]["deduction"] + result["components"]["interaction"] > 40
    assert result["components"]["penalties"]["sleep"] > 0.5
    assert result["components"]["penalties"]["soreness"] > 0.5


def test_compute_readiness_applies_pain_gate_for_sharp_or_worsening_pain():
    result = compute_readiness(
        user_history=[
            {"sleep_hours": 8.0, "stress_level": 1, "energy_level": 5, "soreness_level": 1},
        ],
        today_checkin={
            "sleep_hours": 8.0,
            "stress_level": 1,
            "energy_level": 5,
            "soreness_level": 1,
            "pain_notes": "sharp knee pain during squats",
        },
    )

    assert result["readiness_score"] <= 30
    assert result["band"] == "recovery_day"
    assert result["safety_triggered"] is True
    assert result["components"]["pain_gate_applied"] is True


def test_compute_readiness_handles_cold_start_with_population_defaults():
    result = compute_readiness(
        user_history=[],
        today_checkin={
            "sleep_hours": 6.0,
            "stress_level": 3,
            "energy_level": 3,
            "soreness_level": 3,
            "pain_notes": "",
        },
    )

    assert 0 <= result["readiness_score"] <= 100
    assert result["components"]["baselines"]["sleep"]["n"] == 0
    assert result["safety_triggered"] is False
