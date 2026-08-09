import datetime as dt

from src.cockroach_checkin_repository import CockroachCheckinRepository


CHECKIN_ROW = (
    "checkin-1",
    "user-1",
    dt.date(2026, 8, 9),
    6.5,
    3,
    4,
    2,
    ["shoulders"],
    "",
    72.4,
    "yes",
    "protein okay, hydration low",
    "Slept 6.5 hours.",
    '{"parser": "ollama"}',
    dt.datetime(2026, 8, 9, 8, 0, 0),
)

CHECKIN_PAYLOAD = {
    "user_id": "user-1",
    "sleep_hours": 6.5,
    "stress_level": 3,
    "energy_level": 4,
    "soreness_level": 2,
    "sore_muscle_groups": ["shoulders"],
    "pain_notes": "",
    "weight_kg": 72.4,
    "workout_completed": "yes",
    "nutrition_adherence": "protein okay, hydration low",
    "free_text_note": "Slept 6.5 hours.",
    "checkin_details": {"parser": "ollama"},
}


class RecordingCursor:
    def __init__(self, return_row):
        self.return_row = return_row
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self.return_row


class RecordingConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


def test_create_checkin_uses_user_date_upsert():
    cursor = RecordingCursor(return_row=CHECKIN_ROW)
    repository = CockroachCheckinRepository(RecordingConnection(cursor))

    saved = repository.create_checkin(CHECKIN_PAYLOAD)

    assert "ON CONFLICT (user_id, checkin_date) DO UPDATE" in cursor.sql
    assert saved["id"] == "checkin-1"
