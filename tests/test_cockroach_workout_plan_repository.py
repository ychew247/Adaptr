from src.cockroach_workout_plan_repository import CockroachWorkoutPlanRepository


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.cursor_instance = FakeCursor(row)
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


class MultipleRowsCursor(FakeCursor):
    def __init__(self, rows):
        super().__init__(None)
        self.rows = rows

    def fetchall(self):
        return self.rows


class MultipleRowsConnection(FakeConnection):
    def __init__(self, rows):
        self.cursor_instance = MultipleRowsCursor(rows)
        self.commits = 0


def test_create_active_plan_persists_validation_audit_columns():
    connection = FakeConnection(
        (
            "plan-1",
            "user-1",
            "goal-1",
            "2026-08-03",
            ["dumbbell row"],
            ["upper_body"],
            "normal",
            {"week_number": 1},
            "active",
            "validated",
            {"hard_validation": {"valid": True}},
            ["memory-1"],
            2,
            "2026-08-03",
        )
    )
    plan = {
        "user_id": "user-1",
        "goal_id": "goal-1",
        "week_start": "2026-08-03",
        "exercise_names": ["dumbbell row"],
        "target_muscle_groups": ["upper_body"],
        "intensity_band": "normal",
        "plan_json": {"week_number": 1},
        "status": "active",
        "validation_status": "validated",
        "validation_notes": {"hard_validation": {"valid": True}},
        "retrieved_memory_ids": ["memory-1"],
        "generation_attempt": 2,
    }

    saved = CockroachWorkoutPlanRepository(connection).create_active_plan(plan)

    insert_query, params = connection.cursor_instance.queries[1]
    assert "validation_status" in insert_query
    assert "validation_notes" in insert_query
    assert "retrieved_memory_ids" in insert_query
    assert "generation_attempt" in insert_query
    assert params[-4:] == ("validated", '{"hard_validation": {"valid": true}}', ["memory-1"], 2)
    assert saved["validation_status"] == "validated"
    assert saved["retrieved_memory_ids"] == ["memory-1"]
    assert saved["generation_attempt"] == 2


def test_find_plan_for_week_skips_a_later_corrupted_duplicate():
    valid_row = (
        "original-plan",
        "user-1",
        "goal-1",
        "2026-08-22",
        ["dumbbell row"],
        ["legs"],
        "normal",
        {
            "week_start": "2026-08-22",
            "sessions": [
                {"day": "Day 1", "scheduled_date": "2026-08-22"},
                {"day": "Day 2", "scheduled_date": "2026-08-24"},
            ],
        },
        "archived",
        "validated",
        {},
        [],
        1,
        "2026-08-15T07:33:30Z",
    )
    corrupted_newer_row = (
        "duplicate-plan",
        "user-1",
        "goal-1",
        "2026-08-22",
        ["dumbbell row"],
        ["legs"],
        "normal",
        {
            "week_start": "2026-08-22",
            "sessions": [
                {"day": "Day 2", "scheduled_date": "2026-08-23"},
                {"day": "Day 2", "scheduled_date": "2026-08-25"},
                {"day": "Day 3", "scheduled_date": "2026-08-27"},
                {"day": "Day 4", "scheduled_date": "2026-08-29"},
            ],
        },
        "archived",
        "validated",
        {},
        [],
        1,
        "2026-08-15T07:36:28Z",
    )

    selected = CockroachWorkoutPlanRepository(
        MultipleRowsConnection([corrupted_newer_row, valid_row])
    ).find_by_user_id_and_week_start("user-1", "2026-08-22")

    assert selected["id"] == "original-plan"
