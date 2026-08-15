from src.m7_plan_repair import (
    PlanRepairService,
    _target_session_index,
    apply_repair_action,
    determine_repair_action,
)


PROFILE = {
    "user_id": "user-1",
    "equipment_access": ["dumbbells", "treadmill"],
    "weekly_availability": "3 days/week",
    "injury_notes": "wrist injury",
    "medical_constraints": "",
}
GOAL = {
    "id": "goal-1",
    "goal_type": "strength",
    "goal_details": {"target_muscle_groups": ["upper_body"]},
}
CHECKIN = {
    "id": "checkin-1",
    "sleep_hours": 7,
    "stress_level": 3,
    "energy_level": 3,
    "soreness_level": 3,
    "sore_muscle_groups": ["wrist"],
    "pain_notes": "Wrist feels sore.",
    "free_text_note": "Need a wrist-friendly session.",
}
ACTIVE_PLAN = {
    "id": "prior-plan-1",
    "user_id": "user-1",
    "goal_id": "goal-1",
    "week_start": "2026-08-04",
    "plan_json": {
        "week_start": "2026-08-04",
        "week_number": 1,
        "goal_id": "goal-1",
        "goal_type": "strength",
        "target_muscle_groups": ["upper_body"],
        "intensity_band": "normal",
        "sessions": [
            {
                "day": "Day 1",
                "focus": "Upper body",
                "exercises": ["dumbbell row"],
                "sets_reps": "3 x 8",
            },
            {
                "day": "Day 3",
                "focus": "Conditioning",
                "exercises": ["treadmill walk"],
                "sets_reps": "20 minutes",
            },
        ],
    },
}


class ProfileRepository:
    def find_by_user_id(self, user_id):
        return PROFILE


class GoalRepository:
    def find_active_by_user_id(self, user_id):
        return GOAL


class CheckinRepository:
    def find_recent_by_user_id(self, user_id, limit=30):
        return [CHECKIN]


class PlanRepository:
    def __init__(self):
        self.created = []

    def find_active_by_user_id(self, user_id):
        return ACTIVE_PLAN

    def find_recent_by_user_id(self, user_id, limit=4):
        return [ACTIVE_PLAN]

    def create_active_plan(self, plan):
        self.created.append(plan)
        return {"id": "repaired-plan-1", **plan}


class DecisionRepository:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []

    def find_repair_by_trigger(self, user_id, plan_id, trigger_date):
        return self.existing

    def create_repair_decision(self, decision):
        self.created.append(decision)
        return {"id": "decision-1", **decision}


class MemoryRepository:
    def __init__(self):
        self.searches = []
        self.stored = []

    def search_similar(self, user_id, embedding, limit=5, source_type=None):
        self.searches.append({"user_id": user_id, "source_type": source_type})
        if source_type == "fitness_knowledge":
            return [
                {
                    "id": "knowledge-memory-1",
                    "source_type": "fitness_knowledge",
                    "memory_text": "For wrist discomfort, avoid painful loading and preserve the pull pattern when possible.",
                    "outcome_json": {"topic": "substitution_general_rules"},
                    "distance": 0.2,
                }
            ]
        return [
            {
                "id": "repair-memory-1",
                "source_type": "plan_repair",
                "memory_text": "A wrist-friendly dumbbell row substitution worked previously.",
                "outcome_json": {"result": "worked"},
                "distance": 0.1,
            }
        ]

    def upsert_memory(self, **memory):
        self.stored.append(memory)
        return {"id": "repair-memory-written"}


class Embedder:
    def embed(self, text):
        return [0.1, 0.2, 0.3]


class DecisionLog:
    def __init__(self):
        self.readiness_calls = []
        self.repair_calls = []

    def log_readiness_assessment(self, **kwargs):
        self.readiness_calls.append(kwargs)
        return {"id": "readiness-decision-1"}

    def log_plan_repair(self, **kwargs):
        self.repair_calls.append(kwargs)
        return {"id": "repair-decision-1"}


class RetryingRepairGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, plan, repair_action, constraints, retrieved_memories, validator_feedback=None):
        self.calls.append({"memories": retrieved_memories, "feedback": validator_feedback})
        if len(self.calls) == 1:
            return {
                "replacement_session": {
                    "focus": "Wrist work",
                    "exercises": ["burpee"],
                    "sets_reps": "3 x 10",
                },
                "coaching_note": "Use the replacement.",
            }
        return {
            "replacement_session": {
                "focus": "Wrist-friendly upper body",
                "exercises": ["dumbbell row"],
                "sets_reps": "3 x 8",
            },
            "coaching_note": "Keep the wrist neutral.",
        }


def _service(generator, decision_repository=None, decision_log=None, plan_repository=None):
    return PlanRepairService(
        profile_repository=ProfileRepository(),
        goal_repository=GoalRepository(),
        checkin_repository=CheckinRepository(),
        plan_repository=plan_repository or PlanRepository(),
        decision_repository=decision_repository or DecisionRepository(),
        decision_log=decision_log,
        memory_repository=MemoryRepository(),
        embedder=Embedder(),
        repair_generator=generator,
    )


def test_repair_retrieves_precedents_retries_invalid_edit_and_stores_validated_version():
    generator = RetryingRepairGenerator()
    service = _service(generator)

    result = service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="My wrist is sore. Please repair today's session.",
        trigger_date="2026-08-04",
    )

    assert result == "repair_applied"
    assert service.memory_repository.searches[0]["source_type"] == "agent_decision"
    assert service.memory_repository.searches[1]["source_type"] == "fitness_knowledge"
    assert generator.calls[0]["memories"][0]["id"] == "repair-memory-1"
    assert generator.calls[0]["memories"][1]["id"] == "knowledge-memory-1"
    assert "injury_exclusion_violation" in generator.calls[1]["feedback"]["error_codes"]
    assert len(service.plan_repository.created) == 1
    assert service.plan_repository.created[0]["validation_status"] == "validated"
    assert service.plan_repository.created[0]["retrieved_memory_ids"] == [
        "repair-memory-1",
        "knowledge-memory-1",
    ]
    assert service.plan_repository.created[0]["generation_attempt"] == 2
    assert service.decision_repository.created[0]["plan_id"] == "prior-plan-1"
    assert service.decision_repository.created[0]["validation_status"] == "validated"
    assert service.memory_repository.stored[0]["source_type"] == "agent_decision"


def test_repair_falls_back_to_prior_valid_plan_after_two_invalid_attempts():
    class AlwaysInvalidRepairGenerator:
        def generate(self, *args, **kwargs):
            return {
                "replacement_session": {
                    "focus": "Unsafe",
                    "exercises": ["burpee"],
                    "sets_reps": "3 x 10",
                }
            }

    service = _service(AlwaysInvalidRepairGenerator())

    result = service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="My wrist is sore.",
        trigger_date="2026-08-04",
    )

    assert result == "repair_fallback"
    assert service.plan_repository.created == []
    assert service.decision_repository.created[0]["validation_status"] == "fallback_to_prior_plan"
    assert service.decision_repository.created[0]["generation_attempt"] == 2


def test_repair_is_idempotent_for_the_same_user_plan_and_trigger_date():
    decision_repository = DecisionRepository(existing={"id": "existing-repair"})
    service = _service(RetryingRepairGenerator(), decision_repository)

    result = service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="My wrist is sore.",
        trigger_date="2026-08-04",
    )

    assert result == "repair_already_recorded"
    assert service.plan_repository.created == []
    assert service.decision_repository.created == []


def test_pain_gate_keeps_deterministic_recovery_exercises_despite_model_suggestion():
    readiness = {"readiness_score": 30, "band": "recovery_day", "safety_triggered": True}
    candidate = apply_repair_action(
        ACTIVE_PLAN["plan_json"],
        determine_repair_action(readiness, "sharp wrist pain"),
        {"replacement_session": {"exercises": ["barbell squat"], "sets_reps": "5 x 5"}},
        {"intensity_ceiling": "recovery"},
        readiness,
        CHECKIN,
        [],
        1,
    )

    assert candidate["sessions"][0]["exercises"] == [
        "mobility breathing reset",
        "easy walk",
        "pain-free range of motion",
    ]
    assert len(candidate["sessions"]) == 2
    assert candidate["sessions"][1]["focus"] == "Safety-first recovery"
    assert candidate["intensity_band"] == "recovery"


def test_repair_logs_the_decision_with_its_readiness_parent():
    decisions = DecisionLog()
    service = _service(RetryingRepairGenerator(), decision_log=decisions)

    assert service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="My wrist is sore.",
        trigger_date="2026-08-04",
    ) == "repair_applied"

    assert decisions.readiness_calls[0]["checkin"]["id"] == "checkin-1"
    assert decisions.repair_calls[0]["parent_decision_id"] == "readiness-decision-1"


def test_repair_uses_shared_readiness_without_duplicate_log():
    decisions = DecisionLog()
    readiness = {
        "readiness_score": 65,
        "band": "reduce_volume",
        "safety_triggered": False,
        "components": {"source": "agent_flow"},
    }
    service = _service(RetryingRepairGenerator(), decision_log=decisions)

    assert service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="Automatic readiness adjustment.",
        trigger_date="2026-08-04",
        readiness=readiness,
        latest_checkin=CHECKIN,
        parent_decision_id="flow-readiness-1",
    ) == "repair_applied"

    assert decisions.readiness_calls == []
    assert decisions.repair_calls[0]["parent_decision_id"] == "flow-readiness-1"


def test_date_aware_repair_targets_the_session_scheduled_for_today():
    sessions = [
        {"day": "Day 1", "scheduled_date": "2026-08-10", "status": "planned"},
        {"day": "Day 2", "scheduled_date": "2026-08-13", "status": "planned"},
        {"day": "Day 3", "scheduled_date": "2026-08-14", "status": "planned"},
    ]

    assert _target_session_index(sessions, "reschedule_session", "2026-08-13") == 1


def test_limited_minutes_selects_a_matching_shortened_session():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    action = determine_repair_action(readiness, "I only have 15 minutes today.")

    candidate = apply_repair_action(
        ACTIVE_PLAN["plan_json"],
        action,
        {"replacement_session": {"exercises": ["dumbbell row"]}},
        {"intensity_ceiling": "normal"},
        readiness,
        CHECKIN,
        [],
        1,
    )

    assert action["action"] == "shorten_session"
    assert candidate["sessions"][0]["sets_reps"] == "15 minutes, easy-to-moderate"


def test_negated_pain_does_not_select_a_recovery_repair():
    action = determine_repair_action(
        {"readiness_score": 65, "band": "reduce_volume", "safety_triggered": False},
        "I missed yesterday, have a mild shoulder ache that is not sharp, and only have 20 minutes.",
    )

    assert action["pain_gate"] is False
    assert action["action"] == "reschedule_session"


def test_rescheduling_only_moves_the_target_session_without_renumbering_or_shifting_the_week():
    prior_plan = {
        "sessions": [
            {"day": "Day 1", "scheduled_date": "2026-08-22", "status": "planned"},
            {"day": "Day 2", "scheduled_date": "2026-08-24", "status": "planned"},
        ]
    }
    readiness = {"readiness_score": 80, "band": "train_as_planned", "safety_triggered": False}

    candidate = apply_repair_action(
        prior_plan,
        determine_repair_action(readiness, "I missed today's workout."),
        {"replacement_session": {}},
        {},
        readiness,
        {"checkin_date": "2026-08-22"},
        [],
        1,
    )

    assert candidate["sessions"][0]["day"] == "Day 1"
    assert candidate["sessions"][0]["scheduled_date"] == "2026-08-23"
    assert candidate["sessions"][1]["day"] == "Day 2"
    assert candidate["sessions"][1]["scheduled_date"] == "2026-08-24"


def test_repair_updates_the_existing_week_instead_of_creating_a_duplicate_plan_row():
    class InPlacePlanRepository(PlanRepository):
        def __init__(self):
            super().__init__()
            self.updated = []

        def update_plan_after_repair(self, plan_id, plan):
            self.updated.append({"plan_id": plan_id, "plan": plan})
            return {"id": plan_id, **plan}

    plans = InPlacePlanRepository()
    service = _service(RetryingRepairGenerator(), plan_repository=plans)

    assert service.run_repair(
        {"id": "user-1", "display_name": "Alex"},
        trigger_text="My wrist is sore. Please repair today's session.",
        trigger_date="2026-08-04",
    ) == "repair_applied"

    assert plans.updated[0]["plan_id"] == "prior-plan-1"
    assert plans.created == []
