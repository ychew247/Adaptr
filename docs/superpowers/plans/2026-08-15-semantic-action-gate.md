# Semantic Action Gate Implementation Plan

**Goal:** Prevent an Ollama routing error from saving a check-in, changing a plan, or exporting a workbook without a second semantic authorization.

**Architecture:** Keep Ollama as the semantic interpreter, but split triage from authorization. The controller treats a rejected or ambiguous authorization as read-only conversation; only a confirmed action reaches the existing fitness workflow. A confirmed daily check-in may carry one explicit follow-up plan request.

**Constraints:** Do not use keyword-trigger routing. Do not run automated or GUI tests until the user explicitly authorizes testing.

### Task 1: Extend semantic contracts

**Files:** `src/ollama_chat_language.py`

- Add an optional follow-up plan intent to daily-phase triage.
- Add a narrow action-authorization call returning `confirm`, `reject`, or `clarify`, plus the semantically determined training-today state.
- Validate all model output before the controller consumes it.

### Task 2: Gate controller actions

**Files:** `ui/chat_controller.py`

- Require authorization before invoking daily persistence, next-week release, or workbook export.
- On rejected/ambiguous authorization, render only an explanatory response.
- Do not use triage's training-today value to persist a check-in; use the authorization result.
- Execute one explicit follow-up view after a confirmed check-in only when safe.

### Task 3: Separate routine check-in presentation from plan mutation

**Files:** `ui/chat_controller.py`

- Render the workout table and printable prompt only for a new plan or an actual repair.
- Render a normal daily result without re-presenting the entire plan.

### Deferred verification

No tests are run in this implementation phase at the user's request. Later validation must cover the GUI edge-case matrix and the controller/unit routing cases.
