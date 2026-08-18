"""Behavioral tests for the deterministic Module 15 safety gate."""

from src.m15_safety_validity import assess_safety


def test_chest_pain_blocks_workout_guidance_and_requires_urgent_assessment():
    result = assess_safety("I have acute chest pain. Can I still do my workout?")

    assert result["flags"] == ["chest_pain"]
    assert result["highest_severity"] == "urgent"
    assert result["allowed_actions"] == ["recommend_urgent_medical_help"]
    assert "urgent medical" in result["reason"].lower()


def test_fainting_and_severe_dizziness_each_require_urgent_assessment():
    for message, expected_flag in (
        ("I fainted after my last set", "fainting"),
        ("I feel severely dizzy after exercising", "severe_dizziness"),
        ("My shortness of breath is severe", "severe_shortness_of_breath"),
    ):
        result = assess_safety(message)

        assert expected_flag in result["flags"]
        assert result["highest_severity"] == "urgent"


def test_explicitly_denied_emergency_symptoms_do_not_block_normal_soreness():
    result = assess_safety("No chest pain or dizziness, just mild leg soreness from yesterday.")

    assert result["flags"] == []
    assert result["highest_severity"] == "allowed"
    assert "generate_workout" in result["allowed_actions"]


def test_hard_pain_restricts_intense_training_without_treating_normal_soreness_as_pain():
    restricted = assess_safety("My knee pain is worsening. Make me a HIIT workout.")
    allowed = assess_safety("My quads are sore after squats, but there is no sharp pain.")

    assert restricted["flags"] == ["hard_pain"]
    assert restricted["highest_severity"] == "restricted"
    assert "generate_intense_workout" not in restricted["allowed_actions"]
    assert allowed["highest_severity"] == "allowed"


def test_stored_medical_constraints_restrict_specific_workout_advice():
    result = assess_safety(
        "Build me a strength workout.",
        profile={"medical_constraints": "Clinician says no loaded spinal flexion."},
    )

    assert result["flags"] == ["medical_constraint"]
    assert result["highest_severity"] == "restricted"
    assert "generate_workout" not in result["allowed_actions"]


def test_harmful_requests_are_blocked_without_blocking_safe_general_nutrition_question():
    drug_result = assess_safety("Give me a steroid cycle and dosage for muscle gain.")
    eating_result = assess_safety("How can I eat 500 calories a day to lose weight fast?")
    normal_result = assess_safety("What is a balanced post-workout meal?")

    assert drug_result["highest_severity"] == "blocked"
    assert "harmful_substance_request" in drug_result["flags"]
    assert eating_result["highest_severity"] == "blocked"
    assert "eating_disorder_risk" in eating_result["flags"]
    assert normal_result["highest_severity"] == "allowed"


def test_rapid_weight_loss_target_is_restricted_to_sustainable_guidance():
    result = assess_safety("I need to lose 10 kg in one week.")

    assert result["flags"] == ["unsafe_rapid_weight_loss"]
    assert result["highest_severity"] == "blocked"
    assert result["allowed_actions"] == ["offer_sustainable_wellness_guidance"]
