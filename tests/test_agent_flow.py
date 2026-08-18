from src.agent_flow import AdaptiveFitnessAgent


USER = {"id": "user-1", "display_name": "Alex"}
CHECKIN = {
    "id": "checkin-1",
    "checkin_date": "2026-08-09",
    "free_text_note": "I feel ready to train.",
    "workout_completed": "yes",
    "pain_notes": "",
}
ACTIVE_PLAN = {
    "id": "plan-1",
    "status": "active",
    "intensity_band": "normal",
}


class CheckinService:
    def __init__(self, checkin):
        self.checkin = checkin

    def run_checkin(self, user, ask, say):
        ask("How are you feeling?")
        return self.checkin


class CheckinRepository:
    def __init__(self, checkin):
        self.checkin = checkin

    def find_recent_by_user_id(self, user_id, limit=30):
        return [self.checkin]


class PlanRepository:
    def __init__(self, active_plan):
        self.active_plan = active_plan

    def find_active_by_user_id(self, user_id):
        return self.active_plan

    def update_plan_sessions(self, plan_id, sessions):
        self.active_plan = {**self.active_plan, "plan_json": {**self.active_plan.get("plan_json", {}), "sessions": sessions}}


class DecisionLog:
    def __init__(self):
        self.calls = []

    def log_readiness_assessment(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "readiness-decision-1"}


class PlanService:
    def __init__(self, plan_repository):
        self.plan_repository = plan_repository
        self.calls = []
        self.refresh_needed = False

    def active_plan_needs_refresh(self, user, active_plan, *, readiness, latest_checkin):
        return self.refresh_needed

    def run_plan_generation(self, user, **kwargs):
        self.calls.append(kwargs)
        self.plan_repository.active_plan = {
            "id": "generated-plan-1",
            "status": "active",
            "intensity_band": "normal",
        }
        return "plan_ready"


class RepairService:
    def __init__(self, plan_repository):
        self.plan_repository = plan_repository
        self.calls = []
        self.result = "repair_applied"

    def run_repair(self, user, **kwargs):
        self.calls.append(kwargs)
        if self.result == "repair_applied":
            self.plan_repository.active_plan = {
                "id": "repaired-plan-1",
                "status": "active",
                "intensity_band": "reduced",
            }
        return self.result


class NutritionService:
    def __init__(self):
        self.calls = []

    def run_daily_target(self, user, **kwargs):
        self.calls.append(kwargs)
        return {"id": "nutrition-1", "calories_min": 2000, "calories_max": 2200}


def _build_agent(readiness, active_plan=ACTIVE_PLAN, checkin=CHECKIN):
    plan_repository = PlanRepository(active_plan)
    repair_service = RepairService(plan_repository)
    plan_service = PlanService(plan_repository)
    nutrition_service = NutritionService()
    agent = AdaptiveFitnessAgent(
        checkin_service=CheckinService(checkin),
        checkin_repository=CheckinRepository(checkin),
        plan_repository=plan_repository,
        decision_log=DecisionLog(),
        plan_service=plan_service,
        repair_service=repair_service,
        nutrition_service=nutrition_service,
        readiness_calculator=lambda history, today: readiness,
    )
    return agent, plan_service, repair_service, nutrition_service


def test_high_readiness_keeps_plan_and_generates_nutrition():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    agent, plans, repairs, nutrition = _build_agent(readiness)

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Feeling good.")

    assert result["action"] == "keep_plan"
    assert plans.calls == []
    assert repairs.calls == []
    assert nutrition.calls[0]["readiness"] == readiness
    assert nutrition.calls[0]["parent_decision_id"] == "readiness-decision-1"


def test_reduced_readiness_automatically_repairs_before_nutrition():
    readiness = {"readiness_score": 65, "band": "reduce_volume", "safety_triggered": False}
    agent, plans, repairs, nutrition = _build_agent(readiness)

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Sore today.")

    assert result["action"] == "repair_applied"
    assert plans.calls == []
    assert repairs.calls[0]["readiness"] == readiness
    assert repairs.calls[0]["parent_decision_id"] == "readiness-decision-1"
    assert result["plan"]["id"] == "repaired-plan-1"
    assert nutrition.calls[0]["readiness"] == readiness


def test_explicit_repair_dates_run_one_repair_for_each_requested_session():
    readiness = {"readiness_score": 65, "band": "reduce_volume", "safety_triggered": False}
    agent, plans, repairs, _ = _build_agent(readiness)

    result = agent.run_daily_flow(
        USER,
        workout_today=False,
        requested_repair_dates=["2026-08-17", "2026-08-19"],
        ask=lambda _: "My shoulder is sore.",
    )

    assert result["action"] == "repair_applied"
    assert plans.calls == []
    assert [call["trigger_date"] for call in repairs.calls] == ["2026-08-17", "2026-08-19"]


def test_reduced_readiness_repairs_only_the_affected_session_before_any_full_plan_refresh():
    readiness = {"readiness_score": 65, "band": "reduce_volume", "safety_triggered": False}
    agent, plans, repairs, _ = _build_agent(readiness)
    plans.refresh_needed = True

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Sore today.")

    assert result["action"] == "repair_applied"
    assert plans.calls == []
    assert repairs.calls[0]["readiness"] == readiness


def test_safety_readiness_automatically_repairs():
    readiness = {"readiness_score": 30, "band": "recovery_day", "safety_triggered": True}
    agent, _, repairs, _ = _build_agent(readiness)

    result = agent.run_daily_flow(USER, workout_today=False, ask=lambda _: "Sharp pain today.")

    assert result["action"] == "repair_applied"
    assert repairs.calls[0]["readiness"] == readiness


def test_missing_active_plan_generates_a_validated_plan_before_nutrition():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    agent, plans, repairs, nutrition = _build_agent(readiness, active_plan=None)

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Ready to start.")

    assert result["action"] == "plan_ready"
    assert plans.calls[0]["readiness"] == readiness
    assert repairs.calls == []
    assert result["plan"]["id"] == "generated-plan-1"
    assert nutrition.calls[0]["parent_decision_id"] == "readiness-decision-1"


def test_legacy_plan_without_dates_or_prescriptions_is_replaced_before_display():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    legacy_plan = {
        "id": "legacy-plan-1",
        "status": "active",
        "plan_json": {"sessions": [{"day": "Day 1", "sets_reps": "As prescribed"}]},
    }
    agent, plans, repairs, _ = _build_agent(readiness, active_plan=legacy_plan)

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Feeling good.")

    assert result["action"] == "plan_ready"
    assert len(plans.calls) == 1
    assert repairs.calls == []


def test_invalid_active_plan_is_revalidated_and_replaced_before_display():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    agent, plans, repairs, _ = _build_agent(readiness)
    plans.refresh_needed = True

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Feeling good.")

    assert result["action"] == "plan_ready"
    assert len(plans.calls) == 1
    assert plans.calls[0]["latest_checkin"] == CHECKIN
    assert repairs.calls == []


def test_missed_session_repairs_even_when_readiness_is_high():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    checkin = {**CHECKIN, "workout_completed": "missed", "free_text_note": "I missed my session."}
    agent, plans, repairs, _ = _build_agent(readiness, checkin=checkin)

    result = agent.run_daily_flow(USER, workout_today=False, ask=lambda _: "I missed my session.")

    assert result["action"] == "repair_applied"
    assert plans.calls == []
    assert repairs.calls[0]["trigger_text"] == "I missed my session."


def test_limited_minutes_repairs_even_when_readiness_is_high():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    checkin = {**CHECKIN, "free_text_note": "I only have 15 minutes today."}
    agent, plans, repairs, _ = _build_agent(readiness, checkin=checkin)

    result = agent.run_daily_flow(USER, workout_today=True, ask=lambda _: "Only 15 minutes today.")

    assert result["action"] == "repair_applied"
    assert plans.calls == []
    assert repairs.calls[0]["trigger_text"] == "I only have 15 minutes today."


def test_result_is_gui_ready():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    agent, _, _, _ = _build_agent(readiness)

    result = agent.run_daily_flow(USER, workout_today=False, ask=lambda _: "Feeling good.")

    assert set(result) == {"checkin", "readiness", "action", "plan", "nutrition", "summary"}
    assert "85" in result["summary"]


def test_formula_profile_is_forwarded_to_nutrition():
    readiness = {"readiness_score": 85, "band": "train_as_planned", "safety_triggered": False}
    agent, _, _, nutrition = _build_agent(readiness)

    agent.run_daily_flow(
        USER,
        workout_today=True,
        formula_profile="male",
        ask=lambda _: "Feeling good.",
    )

    assert nutrition.calls[0]["formula_profile"] == "male"
