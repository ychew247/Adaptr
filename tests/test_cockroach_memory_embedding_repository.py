import pytest

from src.cockroach_memory_embedding_repository import CockroachMemoryEmbeddingRepository


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.results.pop(0) if self.results else None

    def fetchall(self):
        return self.results.pop(0) if self.results else []


class FakeConnection:
    def __init__(self, results):
        self.cursor_instance = FakeCursor(results)
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


def test_ensure_schema_creates_memory_embeddings_when_table_is_missing():
    connection = FakeConnection([None])

    CockroachMemoryEmbeddingRepository(connection).ensure_schema(3)

    schema_queries = "\n".join(query for query, _ in connection.cursor_instance.queries)
    assert "CREATE TABLE IF NOT EXISTS memory_embeddings" in schema_queries
    assert "VECTOR(3)" in schema_queries
    assert "VECTOR INDEX" in schema_queries
    assert connection.commits == 1


def test_search_similar_uses_recent_personal_and_global_cosine_vector_query():
    connection = FakeConnection(
        [
            [
                (
                    "memory-1",
                    "daily_note",
                    "checkin-1",
                    "Soreness improved after mobility.",
                    {"worked": "mobility"},
                    0.15,
                )
            ]
        ]
    )

    memories = CockroachMemoryEmbeddingRepository(connection).search_similar(
        "user-1", [0.1, 0.2, 0.3], limit=3
    )

    query, params = connection.cursor_instance.queries[0]
    assert "embedding <=>" in query
    assert "created_at >= %s" in query
    assert "user_id IS NULL" in query
    assert "embedding <=> %s::VECTOR < %s" in query
    assert "created_at DESC" in query
    assert params[0] == "[0.1,0.2,0.3]"
    assert params[1] == "user-1"
    assert params[4] == 0.40
    assert params[-1] == 3
    assert memories[0]["id"] == "memory-1"
    assert memories[0]["distance"] == 0.15


def test_upsert_memory_does_not_label_a_timestamp_as_similarity_distance():
    connection = FakeConnection(
        [
            (
                "memory-1",
                "daily_note",
                "checkin-1",
                "Soreness improved after mobility.",
                {"worked": "mobility"},
                "2026-08-03T00:00:00Z",
                "2026-08-03T00:00:00Z",
            )
        ]
    )

    memory = CockroachMemoryEmbeddingRepository(connection).upsert_memory(
        user_id="user-1",
        source_type="daily_note",
        source_id="checkin-1",
        memory_text="Soreness improved after mobility.",
        embedding=[0.1, 0.2, 0.3],
        outcome_json={"worked": "mobility"},
    )

    assert memory["distance"] is None


def test_search_similar_can_limit_retrieval_to_prior_agent_decisions():
    connection = FakeConnection([[]])

    CockroachMemoryEmbeddingRepository(connection).search_similar(
        "user-1", [0.1, 0.2, 0.3], source_type="agent_decision"
    )

    query, params = connection.cursor_instance.queries[0]
    assert "source_type = %s" in query
    assert "agent_decision" in params


def test_upsert_memory_rejects_unknown_source_type_before_executing_sql():
    connection = FakeConnection([])
    repository = CockroachMemoryEmbeddingRepository(connection)

    with pytest.raises(ValueError, match="Unsupported memory source type"):
        repository.upsert_memory(
            user_id="user-1",
            source_type="check_in",
            source_id="checkin-1",
            memory_text="Soreness improved after mobility.",
            embedding=[0.1, 0.2, 0.3],
            outcome_json={},
        )

    assert connection.cursor_instance.queries == []


def test_global_fitness_knowledge_can_be_written_without_a_user_id():
    connection = FakeConnection(
        [
            (
                "memory-1", "fitness_knowledge", "knowledge-1", "Progress slowly.", {},
                "2026-08-03T00:00:00Z", "2026-08-03T00:00:00Z",
            )
        ]
    )

    memory = CockroachMemoryEmbeddingRepository(connection).upsert_memory(
        user_id=None,
        source_type="fitness_knowledge",
        source_id="knowledge-1",
        memory_text="Progress slowly.",
        embedding=[0.1, 0.2, 0.3],
        outcome_json={},
    )

    assert memory["source_type"] == "fitness_knowledge"


def test_global_fitness_knowledge_refreshes_existing_null_user_memory():
    connection = FakeConnection(
        [
            (
                "memory-1", "fitness_knowledge", "knowledge-1", "Updated guidance.", {},
                "2026-08-03T00:00:00Z", "2026-08-04T00:00:00Z",
            )
        ]
    )

    memory = CockroachMemoryEmbeddingRepository(connection).upsert_memory(
        user_id=None,
        source_type="fitness_knowledge",
        source_id="knowledge-1",
        memory_text="Updated guidance.",
        embedding=[0.1, 0.2, 0.3],
        outcome_json={},
    )

    query, params = connection.cursor_instance.queries[0]
    assert "UPDATE memory_embeddings" in query
    assert "user_id IS NULL" in query
    assert params[3] == "fitness_knowledge"
    assert memory["id"] == "memory-1"
