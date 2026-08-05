from src.m4_adaptive_checkin import (
    AdaptiveCheckinService,
    build_adaptive_checkin_prompt,
)


class FakeCheckinRepository:
    def __init__(self, recent_checkins=None):
        self.recent_checkins = recent_checkins or []
        self.saved_checkins = []

    def find_recent_by_user_id(self, user_id, limit=3):
        return self.recent_checkins[:limit]

    def create_checkin(self, checkin):
        self.saved_checkins.append(checkin)
        return checkin


class FakeParser:
    def parse(self, text):
        return {
            "sleep_hours": 6.5,
            "stress_level": 3,
            "energy_level": 4,
            "soreness_level": 2,
            "sore_muscle_groups": ["shoulders"],
            "pain_notes": "",
            "weight_kg": 72.4,
            "workout_completed": "yes",
            "nutrition_adherence": "protein okay, hydration low",
            "checkin_details": {
                "raw_checkin_text": text,
                "nutrition_focus": ["protein", "hydration"],
                "parser": "ollama",
            },
        }


def test_build_adaptive_checkin_prompt_focuses_recovery_after_recent_pain():
    prompt = build_adaptive_checkin_prompt(
        recent_checkins=[{"pain_notes": "hamstring strain", "soreness_level": 4}],
        prompt_picker=lambda prompts: prompts[0],
    )

    assert "hamstring strain" in prompt
    assert "soreness" in prompt.lower()
    assert "nutrition" in prompt.lower()


def test_build_adaptive_checkin_prompt_uses_lightweight_general_prompt_without_recent_issue():
    prompt = build_adaptive_checkin_prompt(
        recent_checkins=[],
        prompt_picker=lambda prompts: prompts[0],
    )

    assert prompt.startswith("Quick check-in:")
    assert "body condition" in prompt
    assert "nutrition" in prompt


def test_adaptive_checkin_service_saves_one_freeform_checkin():
    repository = FakeCheckinRepository()
    service = AdaptiveCheckinService(repository, FakeParser())
    prompts = []
    messages = []

    result = service.run_checkin(
        user={"id": "user-1", "display_name": "Alex"},
        ask=lambda prompt: prompts.append(prompt)
        or "Slept 6.5 hours, shoulders a bit sore, protein okay but hydration low.",
        say=messages.append,
    )

    assert result == "readiness_score"
    assert len(prompts) == 1
    assert len(repository.saved_checkins) == 1
    saved = repository.saved_checkins[0]
    assert saved["user_id"] == "user-1"
    assert saved["sleep_hours"] == 6.5
    assert saved["sore_muscle_groups"] == ["shoulders"]
    assert saved["nutrition_adherence"] == "protein okay, hydration low"
    assert saved["free_text_note"] == (
        "Slept 6.5 hours, shoulders a bit sore, protein okay but hydration low."
    )
    assert saved["checkin_details"]["parser"] == "ollama"
    assert messages == [
        "Saved Alex's adaptive check-in. Next I can calculate readiness and adjust the plan."
    ]
