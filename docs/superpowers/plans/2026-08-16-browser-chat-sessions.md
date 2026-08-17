# Browser Chat Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve multiple named NiceGUI chats in browser local storage and restore the selected chat after refresh.

**Architecture:** `ChatSessionStore` will own JSON-safe ordered chat snapshots and active-session selection. `FitnessAgentPage` will use it to render dynamic sidebar entries and synchronize its state to the browser's versioned local-storage key; CockroachDB remains untouched.

**Tech Stack:** Python 3, dataclasses, NiceGUI, browser `localStorage`, pytest.

## Global Constraints

- Keep chat transcripts in the browser; do not add CockroachDB persistence.
- A new session starts as `New chat`, then becomes the identified display name; duplicates are valid.
- Invalid browser data falls back to a usable new conversation.
- Never put credentials in browser storage.

---

### Task 1: Add serializable multi-session state

**Files:**
- Modify: `ui/chat_state.py`
- Modify: `tests/test_nicegui_chat_state.py`

**Interfaces:**
- Produces `ChatSessionStore.start_new_session(welcome_message: str, *, welcome_headline: str = "") -> ChatSession`.
- Produces `ChatSessionStore.activate(session_id: str) -> ChatSession`.
- Produces `ChatSessionStore.to_payload() -> dict[str, object]` and `ChatSessionStore.from_payload(payload: object) -> ChatSessionStore`.

- [ ] Write failing tests that prove starting a second chat preserves the first and that a named active chat round-trips through JSON.
- [ ] Run `python -m pytest tests/test_nicegui_chat_state.py -q` and confirm failure because `ChatSessionStore` does not exist.
- [ ] Add `session_id` and `title` to `ChatSession`, then implement the store with strict mapping/list/string/number/boolean/null payload validation.
- [ ] Re-run `python -m pytest tests/test_nicegui_chat_state.py -q` and confirm the new tests pass.
- [ ] Commit only this task’s state and tests with `feat: add browser chat session state`.

### Task 2: Connect session state to the NiceGUI page

**Files:**
- Modify: `ui/chat.py`
- Modify: `tests/test_nicegui_chat_state.py`

**Interfaces:**
- Consumes `ChatSessionStore` from Task 1.
- Produces `_new_chat()`, `_activate_chat(session_id: str)`, `_restore_sessions()`, and `_persist_sessions()` page behaviours.

- [ ] Write a failing page-characterisation test requiring `adaptr.chat_sessions.v1`, `localStorage.getItem`, `localStorage.setItem`, `_activate_chat`, and no hard-coded `Current session` item.
- [ ] Run that test and confirm it fails against the fixed sidebar.
- [ ] Render dynamic conversation buttons, restore session data before creating an initial session, and persist after new chat, identity completion, message completion, stopping, and chat selection.
- [ ] Re-run `python -m pytest tests/test_nicegui_chat_state.py -q` and confirm the test passes.
- [ ] Commit only this task’s page and tests with `feat: persist browser chat sessions`.

### Task 3: Document and verify the feature

**Files:**
- Modify: `README.md`
- Test: `tests/test_nicegui_chat_state.py`

**Interfaces:**
- Documents that conversation history survives refresh only in the same browser profile and disappears when site data is cleared.

- [ ] Add the concise README note: “Chat history is stored only in this browser. It survives a page refresh, but clearing site data or using another browser starts with no local chat history.”
- [ ] Run `python -m pytest tests/test_nicegui_chat_state.py tests/test_agent_flow.py -q` and confirm zero failures.
- [ ] Run `git diff --check` and confirm exit code 0.
- [ ] Commit only the README with `docs: explain local chat persistence`.
