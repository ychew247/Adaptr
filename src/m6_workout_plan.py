from datetime import date, timedelta
import re

from src.m5_readiness_score import compute_readiness


def generate_weekly_plan(profile, goal, readiness, week_start=None, week_number=1):
    goal_details = goal.get("goal_details") or {}
    training_days = _parse_training_days(profile.get("weekly_availability"))
    target_muscles = goal_details.get("target_muscle_groups") or []
    athlete_type = goal_details.get("athlete_type")
    desired_outcomes = goal_details.get("desired_outcomes") or []
    style = goal_details.get("training_style") or []
    intensity_band, volume_modifier, adjustment = _readiness_adjustment(readiness)

    if readiness.get("safety_triggered"):
        sessions = [_recovery_session(adjustment)]
    else:
        sessions = _build_sessions(
            training_days,
            goal["goal_type"],
            athlete_type,
            target_muscles,
            desired_outcomes,
            style,
            adjustment,
        )

    resolved_week_start = str(week_start or date.today())
    sessions = schedule_sessions(sessions, resolved_week_start)

    exercise_names = _unique(
        exercise
        for session in sessions
        for exercise in session["exercises"]
    )

    return {
        "goal_id": goal["id"],
        "week_start": resolved_week_start,
        "week_number": week_number,
        "plan_duration_weeks": goal.get("plan_duration_weeks"),
        "goal_type": goal["goal_type"],
        "athlete_type": athlete_type,
        "target_muscle_groups": _unique([*target_muscles, *_target_muscles_from_sessions(sessions)]),
        "exercise_names": exercise_names,
        "intensity_band": intensity_band,
        "volume_modifier": volume_modifier,
        "readiness_score": readiness["readiness_score"],
        "readiness_band": readiness["band"],
        "safety_triggered": readiness["safety_triggered"],
        "sessions": sessions,
        "generation_context": {
            "training_experience": profile.get("training_experience"),
            "equipment_access": profile.get("equipment_access") or [],
            "weekly_availability": profile.get("weekly_availability"),
            "injury_notes": profile.get("injury_notes"),
            "desired_outcomes": desired_outcomes,
            "training_style": style,
        },
    }


class WorkoutPlanService:
    def __init__(
        self,
        profile_repository,
        goal_repository,
        checkin_repository,
        plan_repository,
        plan_generator=None,
    ):
        self.profile_repository = profile_repository
        self.goal_repository = goal_repository
        self.checkin_repository = checkin_repository
        self.plan_repository = plan_repository
        self.plan_generator = plan_generator

    def run_plan_generation(self, user, say=print):
        profile = self.profile_repository.find_by_user_id(user["id"])
        if profile is None:
            raise RuntimeError("Static profile is missing. Run Module 2 first.")

        goal = self.goal_repository.find_active_by_user_id(user["id"])
        if goal is None:
            raise RuntimeError("Active goal is missing. Run Module 3 first.")

        checkins = self.checkin_repository.find_recent_by_user_id(user["id"], limit=30)
        readiness = _readiness_from_checkins(checkins)
        if self.plan_generator is None:
            plan_json = generate_weekly_plan(profile, goal, readiness)
        else:
            plan_json = self.plan_generator.generate(profile, goal, readiness)
        saved_plan = self.plan_repository.create_active_plan(
            {
                "user_id": user["id"],
                "goal_id": goal["id"],
                "week_start": plan_json["week_start"],
                "exercise_names": plan_json["exercise_names"],
                "target_muscle_groups": plan_json["target_muscle_groups"],
                "intensity_band": plan_json["intensity_band"],
                "plan_json": plan_json,
                "status": "active",
            }
        )

        say(f"Saved {user['display_name']}'s Week {plan_json['week_number']} workout plan.")
        return "plan_ready"


def _readiness_from_checkins(checkins):
    if not checkins:
        return {
            "readiness_score": 85,
            "band": "train_as_planned",
            "safety_triggered": False,
            "components": {"source": "default_no_checkins"},
        }

    return compute_readiness(list(reversed(checkins[1:])), checkins[0])


def schedule_sessions(sessions, week_start):
    """Spread ordered sessions across the plan week without overwriting explicit dates."""
    start = date.fromisoformat(str(week_start))
    count = len(sessions)
    if count == 0:
        return []

    scheduled = []
    for index, session in enumerate(sessions):
        offset = 0 if count == 1 else round(index * 6 / (count - 1))
        scheduled.append(
            {
                **session,
                "scheduled_date": session.get("scheduled_date") or str(start + timedelta(days=offset)),
                "status": session.get("status") or "planned",
            }
        )
    return scheduled


def _parse_training_days(availability):
    if not availability:
        return 3

    match = re.search(r"\b(\d+)\s*(day|days)\b", str(availability).lower())
    if match:
        return max(1, min(6, int(match.group(1))))
    return 3


def _readiness_adjustment(readiness):
    if readiness.get("safety_triggered") or readiness["band"] == "recovery_day":
        return "recovery", 0.4, "Safety or low readiness: use recovery-only work."
    if readiness["band"] == "lighter_session":
        return "light", 0.6, "Use a lighter session and avoid maximal effort."
    if readiness["band"] == "reduce_volume":
        return "reduced", 0.8, "Reduce working sets by 20%."
    return "normal", 1.0, "Train as planned."


def _build_sessions(
    training_days,
    goal_type,
    athlete_type,
    target_muscles,
    desired_outcomes,
    style,
    adjustment,
):
    templates = [
        _strength_session(target_muscles, adjustment),
        _conditioning_session(goal_type, athlete_type, adjustment),
        _hybrid_session(target_muscles, athlete_type, style, adjustment),
        _accessory_session(target_muscles, desired_outcomes, adjustment),
        _zone2_session(adjustment),
        _mobility_session(adjustment),
    ]
    return templates[:training_days]


def _strength_session(target_muscles, adjustment):
    upper_focus = "upper_body" in target_muscles or "shoulders" in target_muscles
    exercises = (
        ["landmine press", "chest-supported row", "cable face pull", "push-up"]
        if upper_focus
        else ["goblet squat", "romanian deadlift", "split squat", "plank"]
    )
    return {
        "day": "Day 1",
        "focus": "Strength foundation",
        "exercises": exercises,
        "sets_reps": "3 sets of 6-10 reps",
        "adjustment": adjustment,
    }


def _conditioning_session(goal_type, athlete_type, adjustment):
    if athlete_type == "badminton":
        exercises = ["badminton footwork intervals", "lateral shuffle", "split-step reaction drill"]
    elif goal_type == "vo2_max":
        exercises = ["treadmill intervals", "bike intervals", "easy cooldown"]
    else:
        exercises = ["tempo walk", "bike intervals", "core carry"]

    return {
        "day": "Day 2",
        "focus": "Conditioning",
        "exercises": exercises,
        "sets_reps": "20-30 minutes total",
        "adjustment": adjustment,
    }


def _hybrid_session(target_muscles, athlete_type, style, adjustment):
    exercises = ["medicine ball slam", "single-arm cable row", "farmer carry"]
    if athlete_type == "badminton" or "functional" in style:
        exercises.append("multi-direction lunge")
    if "upper_body" in target_muscles:
        exercises.append("scapular wall slide")

    return {
        "day": "Day 3",
        "focus": "Hybrid functional strength",
        "exercises": exercises,
        "sets_reps": "3 rounds, controlled pace",
        "adjustment": adjustment,
    }


def _accessory_session(target_muscles, desired_outcomes, adjustment):
    exercises = ["mobility warmup", "band external rotation", "dead bug"]
    if "upper_body" in target_muscles or "strength" in desired_outcomes:
        exercises.extend(["incline dumbbell press", "lat pulldown"])
    else:
        exercises.extend(["step-up", "hamstring bridge"])

    return {
        "day": "Day 4",
        "focus": "Accessory and weak-point work",
        "exercises": exercises,
        "sets_reps": "2-3 sets of 10-15 reps",
        "adjustment": adjustment,
    }


def _zone2_session(adjustment):
    return {
        "day": "Day 5",
        "focus": "Aerobic base",
        "exercises": ["zone 2 treadmill", "easy mobility"],
        "sets_reps": "30-40 minutes",
        "adjustment": adjustment,
    }


def _mobility_session(adjustment):
    return {
        "day": "Day 6",
        "focus": "Mobility and recovery",
        "exercises": ["mobility flow", "breathing reset", "easy walk"],
        "sets_reps": "20-30 minutes",
        "adjustment": adjustment,
    }


def _recovery_session(adjustment):
    return {
        "day": "Day 1",
        "focus": "Safety-first recovery",
        "exercises": ["mobility breathing reset", "easy walk", "pain-free range of motion"],
        "sets_reps": "15-25 minutes, stop if pain worsens",
        "adjustment": adjustment,
    }


def _target_muscles_from_sessions(sessions):
    muscles = []
    text = " ".join(" ".join(session["exercises"]) for session in sessions)
    if any(keyword in text for keyword in ["press", "row", "face pull", "lat pulldown"]):
        muscles.append("upper_body")
    if any(keyword in text for keyword in ["squat", "lunge", "step-up"]):
        muscles.append("lower_body")
    if any(keyword in text for keyword in ["dead bug", "plank", "carry"]):
        muscles.append("core")
    return muscles


def _unique(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
