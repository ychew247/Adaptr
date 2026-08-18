"""CockroachDB repository for curated Module 11 fitness knowledge."""

from __future__ import annotations

from typing import Any, Sequence

from src.m11_fitness_knowledge import KnowledgeSnippet


class CockroachFitnessKnowledgeRepository:
    def __init__(self, connection: Any):
        self.connection = connection

    def upsert_snippet(self, snippet: KnowledgeSnippet) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fitness_knowledge (topic, content, source_name, source_url)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (topic)
                DO UPDATE SET
                  content = excluded.content,
                  source_name = excluded.source_name,
                  source_url = excluded.source_url,
                  updated_at = now()
                RETURNING id, topic, content, source_name, source_url
                """,
                (
                    snippet.topic,
                    snippet.content,
                    snippet.source_name,
                    snippet.source_url,
                ),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return _row_to_snippet(row)


def _row_to_snippet(row: Sequence[Any]) -> dict[str, Any]:
    return {
        "id": row[0],
        "topic": row[1],
        "content": row[2],
        "source_name": row[3],
        "source_url": row[4],
    }
