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


def test_search_similar_uses_a_user_scoped_cosine_vector_query():
    connection = FakeConnection(
        [
            [
                (
                    "memory-1",
                    "checkin",
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
    assert "WHERE user_id = %s" in query
    assert params == ("[0.1,0.2,0.3]", "user-1", "[0.1,0.2,0.3]", 3)
    assert memories[0]["id"] == "memory-1"
    assert memories[0]["distance"] == 0.15


def test_upsert_memory_does_not_label_a_timestamp_as_similarity_distance():
    connection = FakeConnection(
        [
            (
                "memory-1",
                "checkin",
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
        source_type="checkin",
        source_id="checkin-1",
        memory_text="Soreness improved after mobility.",
        embedding=[0.1, 0.2, 0.3],
        outcome_json={"worked": "mobility"},
    )

    assert memory["distance"] is None


def test_search_similar_can_limit_retrieval_to_prior_repair_memories():
    connection = FakeConnection([[]])

    CockroachMemoryEmbeddingRepository(connection).search_similar(
        "user-1", [0.1, 0.2, 0.3], source_type="plan_repair"
    )

    query, params = connection.cursor_instance.queries[0]
    assert "source_type = %s" in query
    assert params[2] == "plan_repair"
