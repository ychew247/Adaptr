# Context-Aware Fitness Chat Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route daily chat messages by semantic intent and answer plan-related follow-ups from CockroachDB-backed fitness state.

**Architecture:** Create a UI-neutral conversation router that accepts a message, a small mutable conversation state, and runtime repositories/services. It classifies the message with constrained Ollama JSON plus deterministic fallbacks, invokes the existing agent only for complete check-ins, and returns structured response events for both chat UIs.

**Tech Stack:** Python, Streamlit, NiceGUI, CockroachDB repositories, Ollama JSON instructions, pytest.

## Global Constraints

- Keep M4-M9 as the source of truth; do not duplicate readiness, plan repair, or nutrition logic.
- Load persisted context before replying to a state-dependent question.
- Do not run the daily flow for plan views, exports, provenance, causal, or off-topic messages.
- Preserve the existing dirty worktree and avoid unrelated refactors.

---

### Task 1: Constrained Intent and Completeness Classification

**Files:**
- Modify: `src/ollama_chat_language.py`
- Test: `tests/test_ollama_chat_language.py`

**Interfaces:**
- Produces `OllamaChatLanguage.classify_daily_message(message: str) -> dict[str, str]`.
- Valid intents: `checkin`, `plan_view`, `plan_question`, `nutrition_question`, `plan_provenance`, `plan_change_reason`, `export_plan`, `off_topic`, `unclear`.

- [ ] **Step 1: Write failing tests**

```python
def test_daily_intent_classifies_a_natural_plan_view_request():
    client = FakeOllamaClient(['{"intent":"plan_view"}'])
    assert OllamaChatLanguage(client).classify_daily_message("give me the generated workout plan") == {"intent": "plan_view"}

def test_daily_intent_rejects_unknown_intent_values():
    client = FakeOllamaClient(['{"intent":"chat"}'])
    with pytest.raises(ChatLanguageFormatError):
        OllamaChatLanguage(client).classify_daily_message("hello")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ollama_chat_language.py -q`

Expected: FAIL because `classify_daily_message` does not exist.

- [ ] **Step 3: Add the constrained JSON instruction and validator**

```python
def classify_daily_message(self, message: str) -> dict[str, str]:
    payload = self._json_payload(DAILY_MESSAGE_INTENT_INSTRUCTION, json.dumps({"user_message": message}))
    intent = payload.get("intent")
    if intent not in DAILY_MESSAGE_INTENTS:
        raise ChatLanguageFormatError("Ollama did not return a valid daily-message intent.")
    return {"intent": intent}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ollama_chat_language.py -q`

Expected: PASS.

### Task 2: UI-Neutral Router and Grounded Response Builders

**Files:**
- Create: `src/fitness_conversation_router.py`
- Modify: `src/fitness_chat.py`
- Test: `tests/test_fitness_conversation_router.py`

**Interfaces:**
- Consumes `runtime["agent"]`, repositories for plans/check-ins/nutrition/decisions, `chat_language`, a user, and a mutable pending-check-in list.
- Produces `ConversationOutcome(kind: str, messages: list[dict[str, Any]], pending_checkin: list[str])`.

- [ ] **Step 1: Write failing priority-scenario tests**

```python
def test_plan_view_reads_the_active_plan_without_running_daily_flow():
    outcome = router.handle("give me the generated workout plan", state)
    assert outcome.kind == "plan_view"
    assert agent.calls == []
    assert outcome.messages[0]["plan"]["id"] == "active-plan"

def test_complete_checkin_runs_the_existing_daily_flow():
    outcome = router.handle("slept 6.5 hrs, stress is high, legs sore", state)
    assert outcome.kind == "daily_result"
    assert agent.calls == ["slept 6.5 hrs, stress is high, legs sore"]

def test_plan_provenance_uses_recent_plan_rows():
    outcome = router.handle("is this the same plan from earlier today?", state)
    assert "same plan" in outcome.messages[0]["content"].lower()
    assert "2026-08-13" in outcome.messages[0]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fitness_conversation_router.py -q`

Expected: FAIL because the router module does not exist.

- [ ] **Step 3: Implement router intent dispatch**

```python
class FitnessConversationRouter:
    def handle(self, message, state):
        intent = self._intent_for(message)
        if intent == "checkin":
            return self._handle_checkin(message, state)
        return self._answer_grounded_intent(intent, message, state)
```

Implement deterministic fallback classification, complete-check-in detection,
active-plan display, nutrition-target explanation, recent-plan provenance,
decision-history causal answers, per-session set-reduction explanations, and
off-topic/unclear responses. Use only repository data for plan facts.

- [ ] **Step 4: Run router tests to verify they pass**

Run: `python -m pytest tests/test_fitness_conversation_router.py -q`

Expected: PASS.

### Task 3: Shared Runtime Context and UI Integration

**Files:**
- Modify: `src/fitness_agent_runtime.py`
- Modify: `app.py`
- Modify: `ui/chat_controller.py`
- Modify: `ui/chat_state.py`
- Test: `tests/test_nicegui_chat_state.py`

**Interfaces:**
- Runtime exposes `checkins`, `nutrition`, and `decisions` with existing repositories.
- Streamlit session state and `ChatSession` expose `pending_checkin_messages: list[str]`.

- [ ] **Step 1: Write failing state and integration tests**

```python
def test_new_chat_clears_pending_checkin_messages():
    session = ChatSession(pending_checkin_messages=["slept poorly"])
    session.start_new_chat("Welcome")
    assert session.pending_checkin_messages == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_nicegui_chat_state.py -q`

Expected: FAIL because `pending_checkin_messages` does not exist.

- [ ] **Step 3: Replace duplicated daily handlers with router calls**

```python
outcome = router.handle(message, conversation_state)
for response in outcome.messages:
    add_message("assistant", response["content"], **response.get("metadata", {}))
```

Retain the printable-download confirmation path. Route exports through the
router or the existing export handler only after semantic classification.

- [ ] **Step 4: Run focused integration tests**

Run: `python -m pytest tests/test_nicegui_chat_state.py tests/test_fitness_agent_runtime.py -q`

Expected: PASS.

### Task 4: Scenario Regression Coverage and Verification

**Files:**
- Modify: `tests/test_fitness_conversation_router.py`

- [ ] **Step 1: Add scenario tests C, D, E, G, and H**

```python
def test_partial_checkin_waits_then_runs_with_accumulated_messages():
    assert router.handle("didn't sleep great last night", state).kind == "checkin_follow_up"
    assert router.handle("maybe 5 hours, energy 3 out of 5", state).kind == "checkin_follow_up"
    assert router.handle("no pain, just tired", state).kind == "daily_result"

def test_off_topic_message_does_not_run_daily_flow():
    outcome = router.handle("what is a good post-workout snack in general?", state)
    assert outcome.kind == "off_topic"
    assert agent.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fitness_conversation_router.py -q`

Expected: FAIL until all scenario behavior is implemented.

- [ ] **Step 3: Add the minimal router behavior required by the failing scenarios**

Use the existing check-in parser through `run_daily_flow`; do not add direct
database writes in the router. For corrections, mark the response as a
check-in and pass the correction text to the existing M4 upsert path.

- [ ] **Step 4: Run focused and full verification**

Run: `python -m pytest tests/test_fitness_conversation_router.py tests/test_fitness_chat.py tests/test_ollama_chat_language.py tests/test_agent_flow.py -q`

Expected: PASS.

Run: `python -m pytest -q`

Expected: PASS with no new failures.
