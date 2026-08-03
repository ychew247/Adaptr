class CockroachStaticProfileRepository:
    def __init__(self, connection):
        self.connection = connection

    def find_by_user_id(self, user_id):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  user_id,
                  age,
                  height_cm,
                  starting_weight_kg,
                  training_experience,
                  equipment_access,
                  weekly_availability,
                  injury_notes,
                  medical_constraints,
                  diet_preferences,
                  activity_level,
                  created_at,
                  updated_at
                FROM user_profiles
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return {
            "user_id": row[0],
            "age": row[1],
            "height_cm": row[2],
            "starting_weight_kg": row[3],
            "training_experience": row[4],
            "equipment_access": list(row[5] or []),
            "weekly_availability": row[6],
            "injury_notes": row[7],
            "medical_constraints": row[8],
            "diet_preferences": row[9],
            "activity_level": row[10],
            "created_at": row[11],
            "updated_at": row[12],
        }

    def upsert_profile(self, profile):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPSERT INTO user_profiles (
                  user_id,
                  age,
                  height_cm,
                  starting_weight_kg,
                  training_experience,
                  equipment_access,
                  weekly_availability,
                  injury_notes,
                  medical_constraints,
                  diet_preferences,
                  activity_level,
                  updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                RETURNING
                  user_id,
                  age,
                  height_cm,
                  starting_weight_kg,
                  training_experience,
                  equipment_access,
                  weekly_availability,
                  injury_notes,
                  medical_constraints,
                  diet_preferences,
                  activity_level,
                  created_at,
                  updated_at
                """,
                (
                    profile["user_id"],
                    profile["age"],
                    profile["height_cm"],
                    profile["starting_weight_kg"],
                    profile["training_experience"],
                    profile["equipment_access"],
                    profile["weekly_availability"],
                    profile["injury_notes"],
                    profile["medical_constraints"],
                    profile["diet_preferences"],
                    profile["activity_level"],
                ),
            )
            row = cursor.fetchone()

        self.connection.commit()
        return {
            "user_id": row[0],
            "age": row[1],
            "height_cm": row[2],
            "starting_weight_kg": row[3],
            "training_experience": row[4],
            "equipment_access": list(row[5] or []),
            "weekly_availability": row[6],
            "injury_notes": row[7],
            "medical_constraints": row[8],
            "diet_preferences": row[9],
            "activity_level": row[10],
            "created_at": row[11],
            "updated_at": row[12],
        }
