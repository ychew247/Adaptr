import json


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
