class CockroachUserRepository:
    def __init__(self, connection):
        self.connection = connection

    def find_by_normalized_name(self, normalized_name):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, display_name, normalized_name, created_at, updated_at
                FROM users
                WHERE normalized_name = %s
                """,
                (normalized_name,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "display_name": row[1],
            "normalized_name": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    def create_user(self, display_name, normalized_name):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (display_name, normalized_name)
                VALUES (%s, %s)
                RETURNING id, display_name, normalized_name, created_at, updated_at
                """,
                (display_name, normalized_name),
            )
            row = cursor.fetchone()

        self.connection.commit()
        return {
            "id": row[0],
            "display_name": row[1],
            "normalized_name": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }
