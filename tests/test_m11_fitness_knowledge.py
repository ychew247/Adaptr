from pathlib import Path

from src.m11_fitness_knowledge import (
    parse_fitness_knowledge_files,
    parse_fitness_knowledge_markdown,
    seed_fitness_knowledge,
)


class KnowledgeRepository:
    def __init__(self):
        self.snippets = []

    def upsert_snippet(self, snippet):
        self.snippets.append(snippet)
        return {"id": f"knowledge-{len(self.snippets)}", **snippet.to_record()}


class MemoryRepository:
    def __init__(self):
        self.memories = []

    def upsert_memory(self, **memory):
        self.memories.append(memory)
        return {"id": f"memory-{len(self.memories)}"}


class Embedder:
    def __init__(self):
        self.texts = []

    def embed(self, text):
        self.texts.append(text)
        return [0.1, 0.2, 0.3]


def test_parse_fitness_knowledge_markdown_extracts_snippets_and_guardrail_safe_pain_wording():
    markdown = Path("docs/fitness-knowledge-snippets.md").read_text(encoding="utf-8")

    snippets = parse_fitness_knowledge_markdown(markdown)

    topics = [snippet.topic for snippet in snippets]
    assert "joint_specific_pain_gate" in topics
    joint_pain = next(snippet for snippet in snippets if snippet.topic == "joint_specific_pain_gate")
    assert "localized to a joint" not in joint_pain.content
    assert "sharp, worsening, severe, persistent" in joint_pain.content
    assert "clearly aggravated by loading a joint" in joint_pain.content


def test_parse_fitness_knowledge_files_combines_general_and_sport_topics(tmp_path):
    general_file = tmp_path / "general.md"
    sport_file = tmp_path / "sport.md"
    general_file.write_text(
        "## recovery_basics\n\nRest supports adaptation.\n",
        encoding="utf-8",
    )
    sport_file.write_text(
        "## badminton_footwork\n\nUse multidirectional court movement.\n",
        encoding="utf-8",
    )

    snippets = parse_fitness_knowledge_files([general_file, sport_file])

    assert [snippet.topic for snippet in snippets] == [
        "recovery_basics",
        "badminton_footwork",
    ]


def test_seed_fitness_knowledge_writes_global_vector_memory_for_each_snippet():
    snippets = parse_fitness_knowledge_markdown(
        """
## protein_target_guidance
Source: ISSN
URL: https://jissn.biomedcentral.com/
Use: Nutrition target calculation

Daily protein intake of roughly 1.4-2.0 g/kg supports most exercising users.
"""
    )
    knowledge_repository = KnowledgeRepository()
    memory_repository = MemoryRepository()
    embedder = Embedder()

    result = seed_fitness_knowledge(
        snippets, knowledge_repository, memory_repository, embedder
    )

    assert result == {"snippets": 1, "memories": 1}
    assert knowledge_repository.snippets[0].topic == "protein_target_guidance"
    assert memory_repository.memories[0]["user_id"] is None
    assert memory_repository.memories[0]["source_type"] == "fitness_knowledge"
    assert memory_repository.memories[0]["source_id"] == "knowledge-1"
    assert "protein_target_guidance" in embedder.texts[0]
