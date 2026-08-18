"""Live embedding-schema verification required before Module 6 vector retrieval."""

from __future__ import annotations

import logging
from typing import Any


LOGGER = logging.getLogger(__name__)


def verify_embedding_dimension(embedder: Any, memory_repository: Any) -> int:
    """Probe Ollama and ensure memory_embeddings uses that exact vector dimension."""
    embedding = embedder.embed("fitness-agent vector schema probe")
    dimension = len(embedding)
    if dimension == 0:
        raise RuntimeError("Ollama returned an empty embedding; vector retrieval cannot start.")
    memory_repository.ensure_schema(dimension)
    LOGGER.info("Module 6 vector preflight passed with %s dimensions.", dimension)
    return dimension
