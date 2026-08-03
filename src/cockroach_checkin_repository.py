import json


class CockroachCheckinRepository:
    def __init__(self, connection):
        self.connection = connection

    def find_recent_by_user_id(self, user_id, limit=3):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  user_id,
                  checkin_date,
                  sleep_hours,
                  stress_level,
                  energy_level,
                  soreness_level,
                  sore_muscle_groups,
                  pain_notes,
                  weight_kg,
                  workout_completed,
                  nutrition_adherence,
                  free_text_note,
                  checkin_details,
                  created_at
                FROM daily_checkins
                WHERE user_id = %s
                ORDER BY checkin_date DESC, created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()

        return [self._row_to_checkin(row) for row in rows]

    def create_checkin(self, checkin):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO daily_checkins (
                  user_id,
                  sleep_hours,
                  stress_level,
                  energy_level,
                  soreness_level,
                  sore_muscle_groups,
                  pain_notes,
                  weight_kg,
                  workout_completed,
                  nutrition_adherence,
                  free_text_note,
                  checkin_details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                  id,
                  user_id,
                  checkin_date,
                  sleep_hours,
                  stress_level,
                  energy_level,
                  soreness_level,
                  sore_muscle_groups,
                  pain_notes,
                  weight_kg,
                  workout_completed,
                  nutrition_adherence,
                  free_text_note,
                  checkin_details,
                  created_at
                """,
                (
                    checkin["user_id"],
                    checkin["sleep_hours"],
                    checkin["stress_level"],
                    checkin["energy_level"],
                    checkin["soreness_level"],
                    checkin["sore_muscle_groups"],
                    checkin["pain_notes"],
                    checkin["weight_kg"],
                    checkin["workout_completed"],
                    checkin["nutrition_adherence"],
                    checkin["free_text_note"],
                    json.dumps(checkin["checkin_details"]),
                ),
            )
            row = cursor.fetchone()

        self.connection.commit()
        return self._row_to_checkin(row)

    def _row_to_checkin(self, row):
        checkin_details = row[13]
        if isinstance(checkin_details, str):
            checkin_details = json.loads(checkin_details)

        return {
            "id": row[0],
            "user_id": row[1],
            "checkin_date": row[2],
            "sleep_hours": row[3],
            "stress_level": row[4],
            "energy_level": row[5],
            "soreness_level": row[6],
            "sore_muscle_groups": list(row[7] or []),
            "pain_notes": row[8],
            "weight_kg": row[9],
            "workout_completed": row[10],
            "nutrition_adherence": row[11],
            "free_text_note": row[12],
            "checkin_details": checkin_details,
            "created_at": row[14],
        }
