"""Semantic extraction of requested workout-repair session references."""

from __future__ import annotations

import json
import re
from typing import Any


REPAIR_TARGET_EXTRACTION_INSTRUCTION = """Return JSON only.

Interpret whether the user explicitly asks to amend, repair, change, or adjust
specific sessions in their current workout plan. Extract only the references to
those requested sessions, such as plan day labels (for example, "Day 2") or
dates (for example, "2026-08-19"). Do not infer a target when no specific
session is requested.

Required JSON shape:
{"repair_targets": ["natural session reference"]}
"""


class RepairTargetParseError(ValueError):
    """Raised when the semantic extraction result is unusable."""


class OllamaRepairTargetParser:
    def __init__(self, ollama_client: Any) -> None:
        self.ollama_client = ollama_client

    def parse(self, message: str) -> list[str]:
        content = self.ollama_client.chat_json_instruction(
            REPAIR_TARGET_EXTRACTION_INSTRUCTION, message
        )
        try:
            payload = json.loads(_strip_code_fence(content))
        except (TypeError, json.JSONDecodeError) as error:
            raise RepairTargetParseError("Ollama did not return repair targets as JSON.") from error
        targets = payload.get("repair_targets", [])
        if not isinstance(targets, list) or not all(isinstance(target, str) for target in targets):
            raise RepairTargetParseError("Ollama returned an invalid repair-target list.")
        return [target.strip() for target in targets if target.strip()]


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return match.group(1).strip() if match else stripped
