"""Per-browser state for the NiceGUI chat surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


_UNSUPPORTED_JSON_VALUE = object()


@dataclass
class ChatSession:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New chat"
    title_is_custom: bool = False
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

    def to_payload(self) -> dict[str, Any]:
        """Return browser-safe state, omitting non-JSON message metadata."""
        return _json_safe(
            {
                "session_id": self.session_id,
                "title": self.title,
                "title_is_custom": self.title_is_custom,
                "messages": self.messages,
                "phase": self.phase,
                "user": self.user,
                "profile_answers": self.profile_answers,
                "goal_text": self.goal_text,
                "awaiting_printable_plan": self.awaiting_printable_plan,
                "pending_printable_plan": self.pending_printable_plan,
                "download_ready_message": self.download_ready_message,
                "welcome_headline": self.welcome_headline,
                "show_welcome_screen": self.show_welcome_screen,
                "status": self.status,
            }
        )

    @classmethod
    def from_payload(cls, payload: object) -> "ChatSession | None":
        if not isinstance(payload, dict):
            return None
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return None
        messages = payload.get("messages", [])
        if not _is_json_value(messages):
            return None
        return cls(
            session_id=session_id,
            title=_string_or(payload.get("title"), "New chat"),
            title_is_custom=payload.get("title_is_custom") is True,
            messages=list(messages) if isinstance(messages, list) else [],
            phase=_string_or(payload.get("phase"), "identity"),
            user=payload.get("user") if isinstance(payload.get("user"), dict) else None,
            profile_answers=dict(payload.get("profile_answers") or {})
            if isinstance(payload.get("profile_answers"), dict)
            else {},
            goal_text=_string_or(payload.get("goal_text")),
            awaiting_printable_plan=payload.get("awaiting_printable_plan") is True,
            pending_printable_plan=payload.get("pending_printable_plan")
            if isinstance(payload.get("pending_printable_plan"), dict)
            else None,
            download_ready_message=_string_or(payload.get("download_ready_message")),
            welcome_headline=_string_or(payload.get("welcome_headline")),
            show_welcome_screen=payload.get("show_welcome_screen") is True,
            status=_string_or(payload.get("status"), "Ready"),
        )


@dataclass
class ChatSessionStore:
    """Ordered browser-local conversations and the selected conversation."""

    sessions: list[ChatSession] = field(default_factory=list)
    active_session_id: str | None = None

    @property
    def active_session(self) -> ChatSession:
        if self.active_session_id is None:
            raise LookupError("No active chat session.")
        return self.activate(self.active_session_id)

    def start_new_session(self, welcome_message: str, *, welcome_headline: str = "") -> ChatSession:
        session = ChatSession()
        session.start_new_chat(welcome_message, welcome_headline=welcome_headline)
        self.sessions.append(session)
        self.active_session_id = session.session_id
        return session

    def activate(self, session_id: str) -> ChatSession:
        for session in self.sessions:
            if session.session_id == session_id:
                self.active_session_id = session_id
                return session
        raise LookupError(f"Unknown chat session: {session_id}")

    def replace_active(self, session: ChatSession) -> None:
        for index, existing in enumerate(self.sessions):
            if existing.session_id == session.session_id:
                self.sessions[index] = session
                self.active_session_id = session.session_id
                return
        raise LookupError(f"Unknown chat session: {session.session_id}")

    def rename(self, session_id: str, title: str) -> ChatSession:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("A chat name cannot be empty.")
        for session in self.sessions:
            if session.session_id == session_id:
                session.title = cleaned
                session.title_is_custom = True
                return session
        raise LookupError(f"Unknown chat session: {session_id}")

    def delete(self, session_id: str) -> None:
        for index, session in enumerate(self.sessions):
            if session.session_id != session_id:
                continue
            was_active = session_id == self.active_session_id
            self.sessions.pop(index)
            if not was_active:
                return
            if not self.sessions:
                self.active_session_id = None
                return
            self.active_session_id = self.sessions[min(index, len(self.sessions) - 1)].session_id
            return
        raise LookupError(f"Unknown chat session: {session_id}")

    @staticmethod
    def refresh_title(session: ChatSession) -> None:
        if session.title_is_custom:
            return
        display_name = (session.user or {}).get("display_name")
        session.title = display_name.strip() if isinstance(display_name, str) and display_name.strip() else "New chat"

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "active_session_id": self.active_session_id,
            "sessions": [session.to_payload() for session in self.sessions],
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ChatSessionStore":
        if not isinstance(payload, dict) or payload.get("version") != 1:
            return cls()
        raw_sessions = payload.get("sessions")
        active_session_id = payload.get("active_session_id")
        if not isinstance(raw_sessions, list) or not isinstance(active_session_id, str):
            return cls()
        sessions = [session for item in raw_sessions if (session := ChatSession.from_payload(item)) is not None]
        if not sessions or active_session_id not in {session.session_id for session in sessions}:
            return cls()
        return cls(sessions=sessions, active_session_id=active_session_id)


def _string_or(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        converted = [_json_safe(item) for item in value]
        return [item for item in converted if item is not _UNSUPPORTED_JSON_VALUE]
    if isinstance(value, dict):
        converted = ((str(key), _json_safe(item)) for key, item in value.items())
        return {key: item for key, item in converted if item is not _UNSUPPORTED_JSON_VALUE}
    return _UNSUPPORTED_JSON_VALUE
