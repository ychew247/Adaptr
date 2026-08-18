"""CockroachDB persistence and retrieval for fitness-agent vector memories."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Sequence


LOGGER = logging.getLogger(__name__)
MEMORY_SOURCE_TYPES = frozenset(
    {
        "daily_note",
        "agent_decision",
        "weekly_summary",
        "fitness_knowledge",
        "goal_description",
        "validated_plan",
    }
)
DEFAULT_MAX_DISTANCE = 0.40
DEFAULT_PERSONAL_MEMORY_WEEKS = 12


class MemoryEmbeddingSchemaError(RuntimeError):
    """Raised when the active embedding model and database vector schema disagree."""


class CockroachMemoryEmbeddingRepository:
    def __init__(self, connection: Any):
        self.connection = connection

    def ensure_schema(self, embedding_dimension: int) -> None:
        """Create the existing memory table only when absent and verify its dimension."""
        if embedding_dimension <= 0:
            raise ValueError("Embedding dimension must be positive.")

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'memory_embeddings'
                """
            )
            table = cursor.fetchone()
            if table is None:
                cursor.execute(_create_memory_embeddings_sql(embedding_dimension))
                self.connection.commit()
                LOGGER.info("Created memory_embeddings with VECTOR(%s).", embedding_dimension)
                return

            cursor.execute("SHOW CREATE TABLE memory_embeddings")
            create_row = cursor.fetchone()

        create_statement = str(create_row[-1] if create_row else "")
        actual_dimension = _vector_dimension(create_statement)
        if actual_dimension != embedding_dimension:
            raise MemoryEmbeddingSchemaError(
                "memory_embeddings uses VECTOR({}), but the active Ollama embedding model "
                "returned {} dimensions. Use a matching model or migrate the existing table."
                .format(actual_dimension if actual_dimension is not None else "unknown", embedding_dimension)
            )
        self._upgrade_existing_schema(create_statement)
        LOGGER.info("Verified memory_embeddings VECTOR(%s).", embedding_dimension)

    def _upgrade_existing_schema(self, create_statement: str) -> None:
        """Make legacy rows compatible with global knowledge and canonical source types."""
        with self.connection.cursor() as cursor:
            if re.search(r"user_id\s+UUID\s+NOT\s+NULL", create_statement, re.IGNORECASE):
                cursor.execute(
                    "ALTER TABLE memory_embeddings ALTER COLUMN user_id DROP NOT NULL"
                )
            cursor.execute(
                """
                UPDATE memory_embeddings
                SET source_type = CASE source_type
                  WHEN 'checkin' THEN 'daily_note'
                  WHEN 'workout_plan' THEN 'validated_plan'
                  WHEN 'plan_repair' THEN 'agent_decision'
                  ELSE source_type
                END
                WHERE source_type IN ('checkin', 'workout_plan', 'plan_repair')
                """
            )
        self.connection.commit()

    def search_similar(
        self,
        user_id: str | None,
        embedding: Sequence[float],
        limit: int = 5,
        source_type: str | None = None,
        max_distance: float = DEFAULT_MAX_DISTANCE,
        personal_memory_weeks: int = DEFAULT_PERSONAL_MEMORY_WEEKS,
    ) -> list[dict[str, Any]]:
        """Find close recent personal memories plus shared fitness knowledge."""
        if not embedding:
            return []
        if max_distance <= 0:
            raise ValueError("max_distance must be positive.")
        if personal_memory_weeks <= 0:
            raise ValueError("personal_memory_weeks must be positive.")
        if source_type is not None:
            _validate_source_type(source_type)

        source_clause = "AND source_type = %s" if source_type else ""
        recent_since = date.today() - timedelta(weeks=personal_memory_weeks)
        parameters: tuple[Any, ...] = (
            _vector_literal(embedding),
            user_id,
            recent_since,
            _vector_literal(embedding),
            max_distance,
            *([source_type] if source_type else []),
            _vector_literal(embedding),
            limit,
        )
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  id,
                  source_type,
                  source_id,
                  memory_text,
                  outcome_json,
                  embedding <=> %s::VECTOR AS distance
                FROM memory_embeddings
                WHERE (
                  (user_id = %s AND created_at >= %s)
                  OR user_id IS NULL
                )
                AND embedding <=> %s::VECTOR < %s
                {source_clause}
                ORDER BY embedding <=> %s::VECTOR, created_at DESC
                LIMIT %s
                """.format(source_clause=source_clause),
                parameters,
            )
            rows = cursor.fetchall()
        return [self._row_to_memory(row) for row in rows]

    def upsert_memory(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
        memory_text: str,
        embedding: Sequence[float],
        outcome_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or refresh a retrievable check-in or validated-plan memory."""
        _validate_source_type(source_type)
        if user_id is None and source_type != "fitness_knowledge":
            raise ValueError("Only fitness_knowledge memory may omit user_id.")
        if user_id is None:
            return self._upsert_global_memory(
                source_type=source_type,
                source_id=source_id,
                memory_text=memory_text,
                embedding=embedding,
                outcome_json=outcome_json,
            )
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO memory_embeddings (
                  user_id, source_type, source_id, memory_text, embedding, outcome_json
                )
                VALUES (%s, %s, %s, %s, %s::VECTOR, %s)
                ON CONFLICT (user_id, source_type, source_id)
                DO UPDATE SET
                  memory_text = excluded.memory_text,
                  embedding = excluded.embedding,
                  outcome_json = excluded.outcome_json,
                  updated_at = now()
                RETURNING id, source_type, source_id, memory_text, outcome_json, created_at, updated_at
                """,
                (
                    user_id,
                    source_type,
                    source_id,
                    memory_text,
                    _vector_literal(embedding),
                    json.dumps(outcome_json),
                ),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return self._row_to_stored_memory(row)

    def _upsert_global_memory(
        self,
        *,
        source_type: str,
        source_id: str,
        memory_text: str,
        embedding: Sequence[float],
        outcome_json: dict[str, Any],
    ) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE memory_embeddings
                SET
                  memory_text = %s,
                  embedding = %s::VECTOR,
                  outcome_json = %s,
                  updated_at = now()
                WHERE user_id IS NULL AND source_type = %s AND source_id = %s
                RETURNING id, source_type, source_id, memory_text, outcome_json, created_at, updated_at
                """,
                (
                    memory_text,
                    _vector_literal(embedding),
                    json.dumps(outcome_json),
                    source_type,
                    source_id,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO memory_embeddings (
                      user_id, source_type, source_id, memory_text, embedding, outcome_json
                    )
                    VALUES (NULL, %s, %s, %s, %s::VECTOR, %s)
                    RETURNING id, source_type, source_id, memory_text, outcome_json, created_at, updated_at
                    """,
                    (
                        source_type,
                        source_id,
                        memory_text,
                        _vector_literal(embedding),
                        json.dumps(outcome_json),
                    ),
                )
                row = cursor.fetchone()
        self.connection.commit()
        return self._row_to_stored_memory(row)

    @staticmethod
    def _row_to_memory(row: Sequence[Any]) -> dict[str, Any]:
        outcome_json = row[4]
        if isinstance(outcome_json, str):
            outcome_json = json.loads(outcome_json)
        return {
            "id": row[0],
            "source_type": row[1],
            "source_id": row[2],
            "memory_text": row[3],
            "outcome_json": outcome_json or {},
            "distance": row[5] if len(row) > 5 else None,
        }

    @staticmethod
    def _row_to_stored_memory(row: Sequence[Any]) -> dict[str, Any]:
        outcome_json = row[4]
        if isinstance(outcome_json, str):
            outcome_json = json.loads(outcome_json)
        return {
            "id": row[0],
            "source_type": row[1],
            "source_id": row[2],
            "memory_text": row[3],
            "outcome_json": outcome_json or {},
            "distance": None,
            "created_at": row[5],
            "updated_at": row[6],
        }


def _create_memory_embeddings_sql(embedding_dimension: int) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS memory_embeddings (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID REFERENCES users(id),
          source_type STRING NOT NULL,
          source_id UUID NOT NULL,
          memory_text STRING NOT NULL,
          embedding VECTOR({embedding_dimension}) NOT NULL,
          outcome_json JSONB NOT NULL DEFAULT '{{}}',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT memory_embeddings_user_source_unique UNIQUE (user_id, source_type, source_id),
          VECTOR INDEX memory_embeddings_user_embedding_idx (user_id, embedding vector_cosine_ops)
        )
    """


def _vector_dimension(create_statement: str) -> int | None:
    match = re.search(r"VECTOR\s*\(\s*(\d+)\s*\)", create_statement, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[{}]".format(",".join(str(float(value)) for value in embedding)
    )


def _validate_source_type(source_type: str) -> None:
    if source_type not in MEMORY_SOURCE_TYPES:
        raise ValueError(f"Unsupported memory source type: {source_type}")
