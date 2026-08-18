"""Module 11: curated fitness knowledge ingestion and vector write-back."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import re


@dataclass(frozen=True)
class KnowledgeSnippet:
    topic: str
    content: str
    source_name: str | None = None
    source_url: str | None = None
    use: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "content": self.content,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "use": self.use,
        }

    def memory_text(self) -> str:
        parts = [f"Topic: {self.topic}"]
        if self.use:
            parts.append(f"Use: {self.use}")
        if self.source_name:
            parts.append(f"Source: {self.source_name}")
        parts.append(self.content)
        return "\n".join(parts)


def parse_fitness_knowledge_markdown(markdown_text: str) -> list[KnowledgeSnippet]:
    """Parse the docs Markdown format into seedable snippets."""
    snippets: list[KnowledgeSnippet] = []
    sections = re.split(r"(?m)^##\s+", markdown_text)
    for section in sections[1:]:
        lines = [line.rstrip() for line in section.splitlines()]
        topic = lines[0].strip()
        metadata: dict[str, str] = {}
        content_lines: list[str] = []
        in_content = False
        for line in lines[1:]:
            if not in_content and not line.strip():
                continue
            metadata_match = re.match(r"^(Source|URL|Use):\s*(.*)$", line)
            if metadata_match and not in_content:
                metadata[metadata_match.group(1).lower()] = _blank_placeholder(
                    metadata_match.group(2).strip()
                )
                continue
            in_content = True
            content_lines.append(line)

        content = "\n".join(content_lines).strip()
        if topic and content:
            snippets.append(
                KnowledgeSnippet(
                    topic=topic,
                    content=content,
                    source_name=metadata.get("source"),
                    source_url=metadata.get("url"),
                    use=metadata.get("use"),
                )
            )
    return snippets


def parse_fitness_knowledge_files(paths: Iterable[Path]) -> list[KnowledgeSnippet]:
    """Read and combine Module 11 Markdown knowledge packs."""
    snippets: list[KnowledgeSnippet] = []
    for path in paths:
        snippets.extend(
            parse_fitness_knowledge_markdown(Path(path).read_text(encoding="utf-8"))
        )
    return snippets


def seed_fitness_knowledge(
    snippets: Iterable[KnowledgeSnippet],
    knowledge_repository: Any,
    memory_repository: Any,
    embedder: Any,
) -> dict[str, int]:
    """Upsert snippets and write each one as global vector memory."""
    snippet_count = 0
    memory_count = 0
    for snippet in snippets:
        stored = knowledge_repository.upsert_snippet(snippet)
        memory_text = snippet.memory_text()
        memory_repository.upsert_memory(
            user_id=None,
            source_type="fitness_knowledge",
            source_id=stored["id"],
            memory_text=memory_text,
            embedding=embedder.embed(memory_text),
            outcome_json={
                "topic": snippet.topic,
                "source_name": snippet.source_name,
                "source_url": snippet.source_url,
                "use": snippet.use,
            },
        )
        snippet_count += 1
        memory_count += 1
    return {"snippets": snippet_count, "memories": memory_count}


def _blank_placeholder(value: str) -> str | None:
    if not value or value == "https://..." or value.lower().startswith("(verify"):
        return None
    return value
