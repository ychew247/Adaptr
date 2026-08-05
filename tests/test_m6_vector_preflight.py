from src.m6_vector_preflight import verify_embedding_dimension


class Embedder:
    def embed(self, text):
        assert text == "fitness-agent vector schema probe"
        return [0.1, 0.2, 0.3]


class MemoryRepository:
    def __init__(self):
        self.dimensions = []

    def ensure_schema(self, dimension):
        self.dimensions.append(dimension)


def test_preflight_uses_the_live_embedding_length_to_verify_memory_schema():
    memory_repository = MemoryRepository()

    dimension = verify_embedding_dimension(Embedder(), memory_repository)

    assert dimension == 3
    assert memory_repository.dimensions == [3]
