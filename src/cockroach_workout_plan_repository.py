import json
from datetime import date, timedelta


class CockroachWorkoutPlanRepository:
    def __init__(self, connection):
        self.connection = connection

    def create_active_plan(self, plan):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workout_plans
                SET status = 'archived'
                WHERE user_id = %s AND status = 'active'
                """,
                (plan["user_id"],),
            )
            cursor.execute(
                """
                INSERT INTO workout_plans (
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                """,
                (
                    plan["user_id"],
                    plan["goal_id"],
                    plan["week_start"],
                    plan["exercise_names"],
                    plan["target_muscle_groups"],
                    plan["intensity_band"],
                    json.dumps(plan["plan_json"]),
                    plan["status"],
                    plan.get("validation_status", "pending"),
                    json.dumps(plan.get("validation_notes") or {}),
                    plan.get("retrieved_memory_ids") or [],
                    plan.get("generation_attempt", 1),
                ),
            )
            row = cursor.fetchone()

        self.connection.commit()
        return self._row_to_plan(row)

    def find_active_by_user_id(self, user_id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                FROM workout_plans
                WHERE user_id = %s AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return self._row_to_plan(row)

    def find_by_user_id_and_week_start(self, user_id, week_start):
        """Fetch a program week even when a later preview archived it.

        Older versions of the repair pipeline could leave a corrupted duplicate
        row behind.  Prefer the newest usable version, but retain a usable
        earlier version instead of surfacing the malformed duplicate.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                FROM workout_plans
                WHERE user_id = %s AND week_start = %s
                ORDER BY created_at DESC
                """,
                (user_id, week_start),
            )
            rows = cursor.fetchall()

        if not rows:
            return None
        plans = [self._row_to_plan(row) for row in rows]
        return next(
            (plan for plan in plans if _has_valid_session_calendar(plan, week_start)),
            plans[0],
        )

    def find_latest_by_user_id_on_or_before_date(self, user_id, reference_date):
        """Return the newest program week that has started by the requested date."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                FROM workout_plans
                WHERE user_id = %s AND week_start <= %s
                ORDER BY week_start DESC, created_at DESC
                LIMIT 1
                """,
                (user_id, reference_date),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return self._row_to_plan(row)

    def update_plan_sessions(self, plan_id, sessions):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workout_plans
                SET plan_json = jsonb_set(plan_json, '{sessions}', %s::JSONB)
                WHERE id = %s
                """,
                (json.dumps(sessions), plan_id),
            )
        self.connection.commit()

    def update_export_s3_key(self, plan_id, object_key):
        """Record the private S3 workbook object associated with this plan."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workout_plans
                SET plan_json = jsonb_set(plan_json, '{export_s3_key}', %s::JSONB)
                WHERE id = %s
                """,
                (json.dumps(object_key), plan_id),
            )
        self.connection.commit()

    def update_plan_after_repair(self, plan_id, plan):
        """Persist a validated repair as a version of the same program week."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workout_plans
                SET
                  exercise_names = %s,
                  target_muscle_groups = %s,
                  intensity_band = %s,
                  plan_json = %s,
                  validation_status = %s,
                  validation_notes = %s,
                  retrieved_memory_ids = %s,
                  generation_attempt = %s
                WHERE id = %s
                RETURNING
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                """,
                (
                    plan["exercise_names"],
                    plan["target_muscle_groups"],
                    plan["intensity_band"],
                    json.dumps(plan["plan_json"]),
                    plan.get("validation_status", "validated"),
                    json.dumps(plan.get("validation_notes") or {}),
                    plan.get("retrieved_memory_ids") or [],
                    plan.get("generation_attempt", 1),
                    plan_id,
                ),
            )
            row = cursor.fetchone()
        self.connection.commit()
        if row is None:
            raise ValueError(f"Workout plan {plan_id} does not exist.")
        return self._row_to_plan(row)

    def find_recent_by_user_id(self, user_id, limit=4):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  user_id,
                  goal_id,
                  week_start,
                  exercise_names,
                  target_muscle_groups,
                  intensity_band,
                  plan_json,
                  status,
                  validation_status,
                  validation_notes,
                  retrieved_memory_ids,
                  generation_attempt,
                  created_at
                FROM workout_plans
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
        return [self._row_to_plan(row) for row in rows]

    def _row_to_plan(self, row):
        plan_json = row[7]
        if isinstance(plan_json, str):
            plan_json = json.loads(plan_json)
        validation_notes = row[10]
        if isinstance(validation_notes, str):
            validation_notes = json.loads(validation_notes)

        return {
            "id": row[0],
            "user_id": row[1],
            "goal_id": row[2],
            "week_start": row[3],
            "exercise_names": list(row[4] or []),
            "target_muscle_groups": list(row[5] or []),
            "intensity_band": row[6],
            "plan_json": plan_json,
            "status": row[8],
            "validation_status": row[9],
            "validation_notes": validation_notes or {},
            "retrieved_memory_ids": list(row[11] or []),
            "generation_attempt": row[12],
            "created_at": row[13],
        }


def _has_valid_session_calendar(plan, expected_week_start):
    """Reject only clearly corrupt duplicate records; allow older undated plans."""
    plan_json = plan.get("plan_json") or {}
    sessions = plan_json.get("sessions") or []
    dated_sessions = [session for session in sessions if session.get("scheduled_date")]
    if not dated_sessions:
        return True

    try:
        start = date.fromisoformat(str(plan_json.get("week_start") or expected_week_start))
    except (TypeError, ValueError):
        return False
    end = start + timedelta(days=6)
    labels = set()
    for session in dated_sessions:
        label = str(session.get("day") or "").strip().lower()
        if label and label in labels:
            return False
        labels.add(label)
        try:
            scheduled_date = date.fromisoformat(str(session["scheduled_date"]))
        except (TypeError, ValueError):
            return False
        if not start <= scheduled_date <= end:
            return False
    return True
