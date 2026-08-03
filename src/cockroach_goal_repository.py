import json


class CockroachGoalRepository:
    def __init__(self, connection):
        self.connection = connection

    def find_active_by_user_id(self, user_id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, goal_type, plan_duration_weeks, goal_details, status, created_at, updated_at
                FROM goals
                WHERE user_id = %s AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return self._row_to_goal(row)

    def upsert_active_goal(self, goal):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE goals
                SET status = 'archived', updated_at = now()
                WHERE user_id = %s AND status = 'active'
                """,
                (goal["user_id"],),
            )
            cursor.execute(
                """
                INSERT INTO goals (
                  user_id,
                  goal_type,
                  plan_duration_weeks,
                  goal_details,
                  status
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, user_id, goal_type, plan_duration_weeks, goal_details, status, created_at, updated_at
                """,
                (
                    goal["user_id"],
                    goal["goal_type"],
                    goal["plan_duration_weeks"],
                    json.dumps(goal["goal_details"]),
                    goal["status"],
                ),
            )
            row = cursor.fetchone()

        self.connection.commit()
        return self._row_to_goal(row)

    def _row_to_goal(self, row):
        goal_details = row[4]
        if isinstance(goal_details, str):
            goal_details = json.loads(goal_details)

        return {
            "id": row[0],
            "user_id": row[1],
            "goal_type": row[2],
            "plan_duration_weeks": row[3],
            "goal_details": goal_details,
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
