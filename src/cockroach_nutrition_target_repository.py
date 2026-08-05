from __future__ import annotations

from datetime import date


class CockroachNutritionTargetRepository:
    def __init__(self, connection):
        self.connection = connection

    def upsert_daily_target(self, target):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nutrition_targets (
                  user_id, target_date, calories_min, calories_max, protein_g,
                  hydration_l, fiber_g, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, target_date)
                DO UPDATE SET
                  calories_min = excluded.calories_min,
                  calories_max = excluded.calories_max,
                  protein_g = excluded.protein_g,
                  hydration_l = excluded.hydration_l,
                  fiber_g = excluded.fiber_g,
                  notes = excluded.notes
                RETURNING id, user_id, target_date, calories_min, calories_max,
                  protein_g, hydration_l, fiber_g, notes, created_at
                """,
                (
                    target["user_id"], target.get("target_date") or date.today(), target["calories_min"],
                    target["calories_max"], target["protein_g"], target["hydration_l"],
                    target["fiber_g"], target.get("notes", ""),
                ),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return self._row_to_target(row)

    def find_by_user_id_and_date(self, user_id, target_date):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, target_date, calories_min, calories_max,
                       protein_g, hydration_l, fiber_g, notes, created_at
                FROM nutrition_targets
                WHERE user_id = %s AND target_date = %s
                """,
                (user_id, target_date),
            )
            row = cursor.fetchone()
        return self._row_to_target(row) if row else None

    @staticmethod
    def _row_to_target(row):
        return {
            "id": row[0], "user_id": row[1], "target_date": row[2],
            "calories_min": row[3], "calories_max": row[4], "protein_g": row[5],
            "hydration_l": row[6], "fiber_g": row[7], "notes": row[8],
            "created_at": row[9],
        }
