"""Per-browser state for the NiceGUI chat surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatSession:
    messages: list[dict[str, Any]] = field(default_factory=list)
    phase: str = "identity"
    user: dict[str, Any] | None = None
    profile_answers: dict[str, str] = field(default_factory=dict)
    goal_text: str = ""
    awaiting_printable_plan: bool = False
    pending_printable_plan: dict[str, Any] | None = None
    download_ready_message: str = ""
    welcome_headline: str = ""
    show_welcome_screen: bool = False
    status: str = "Ready"

    def start_new_chat(self, welcome_message: str, *, welcome_headline: str = "") -> None:
        self.messages = [{"role": "assistant", "content": welcome_message}]
        self.phase = "identity"
        self.user = None
        self.profile_answers = {}
        self.goal_text = ""
        self.awaiting_printable_plan = False
        self.pending_printable_plan = None
        self.download_ready_message = ""
        self.welcome_headline = welcome_headline
        self.show_welcome_screen = True
        self.status = "Ready"

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        self.messages.append({"role": role, "content": content, **metadata})
