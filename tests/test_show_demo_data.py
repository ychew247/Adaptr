from src.show_demo_data import fetch_memory_tables, format_table_rows


class FakeCursor:
    def __init__(self):
        self.queries = []
        self.results = [
            [("user-1", "Alex", "alex", "2026-08-01")],
            [("Alex", 25, 175, 72, "intermediate", ["full gym"], "4 days", "lightly active")],
            [("Alex", "sport_conditioning", 8, {"athlete_type": "futsal"}, "active", "2026-08-01")],
            [
                (
                    "Alex",
                    "2026-08-03",
                    6.5,
                    3,
                    4,
                    2,
                    ["shoulders"],
                    "",
                    "protein okay",
                    {"parser": "ollama"},
                )
            ],
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query):
        self.queries.append(query)

    def fetchall(self):
        return self.results.pop(0)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_format_table_rows_prints_headers_and_rows():
    output = format_table_rows(
        title="users",
        columns=["display_name", "normalized_name"],
        rows=[("Alex", "alex"), ("Yu", "yu")],
    )

    assert output == "\n".join(
        [
            "== users ==",
            "display_name | normalized_name",
            "-------------+----------------",
            "Alex         | alex",
            "Yu           | yu",
        ]
    )


def test_format_table_rows_handles_empty_rows():
    output = format_table_rows(
        title="user_profiles",
        columns=["user_id", "age"],
        rows=[],
    )

    assert output == "\n".join(
        [
            "== user_profiles ==",
            "No rows found.",
        ]
    )


def test_fetch_memory_tables_returns_users_profiles_goals_and_checkins():
    connection = FakeConnection()

    users, profiles, goals, checkins = fetch_memory_tables(connection)

    assert users == [("user-1", "Alex", "alex", "2026-08-01")]
    assert profiles == [("Alex", 25, 175, 72, "intermediate", ["full gym"], "4 days", "lightly active")]
    assert goals == [("Alex", "sport_conditioning", 8, {"athlete_type": "futsal"}, "active", "2026-08-01")]
    assert checkins == [
        (
            "Alex",
            "2026-08-03",
            6.5,
            3,
            4,
            2,
            ["shoulders"],
            "",
            "protein okay",
            {"parser": "ollama"},
        )
    ]
    assert len(connection.cursor_instance.queries) == 4
