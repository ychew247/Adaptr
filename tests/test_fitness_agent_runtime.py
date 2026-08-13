from src.fitness_agent_runtime import configured_database_url


def test_runtime_accepts_the_standard_database_url_variable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://database-url")
    monkeypatch.setenv("COCKROACH_URL", "postgresql://cockroach-url")

    assert configured_database_url() == "postgresql://database-url"


def test_runtime_accepts_cockroach_url_when_database_url_is_not_set(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("COCKROACH_URL", "postgresql://cockroach-url")

    assert configured_database_url() == "postgresql://cockroach-url"
