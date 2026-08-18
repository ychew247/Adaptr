from src.cockroach_fitness_knowledge_repository import CockroachFitnessKnowledgeRepository
from src.m11_fitness_knowledge import KnowledgeSnippet


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


def test_upsert_snippet_uses_topic_as_stable_key_and_returns_row():
    connection = FakeConnection(
        (
            "knowledge-1",
            "protein_target_guidance",
            "Protein guidance.",
            "ISSN",
            "https://jissn.biomedcentral.com/",
        )
    )
    snippet = KnowledgeSnippet(
        topic="protein_target_guidance",
        content="Protein guidance.",
        source_name="ISSN",
        source_url="https://jissn.biomedcentral.com/",
        use="Nutrition target calculation",
    )

    row = CockroachFitnessKnowledgeRepository(connection).upsert_snippet(snippet)

    query, params = connection.cursor_instance.queries[0]
    assert "ON CONFLICT (topic)" in query
    assert params == (
        "protein_target_guidance",
        "Protein guidance.",
        "ISSN",
        "https://jissn.biomedcentral.com/",
    )
    assert connection.commits == 1
    assert row["id"] == "knowledge-1"
    assert row["topic"] == "protein_target_guidance"
