# Fitness Agent Session Handoff

## Project Context

This project is a CockroachDB-backed fitness agent with a NiceGUI chat interface and local Ollama integration.

The user has been building a GUI and conversational fitness-agent flow. The main objective of the recent work was to make the chat agent answer based on persisted CockroachDB state for every message, rather than generating a fresh workout plan merely because a message did not match a hard-coded command such as `export_plan`.

## Problem Being Solved

The user reported cases like:

- "give me the generated workout plan" produced a new plan rather than returning the existing active plan.
- A readiness update such as "slept 7 hours, energy 3/5, hamstring soreness, pain no" resulted in a vague reply asking for plan details.
- Generic questions related to training state could bypass the appropriate M4-M9 workflow.

The agreed design was:

1. Use Ollama to classify the semantic intent of each message, instead of relying solely on literal command names.
2. Fetch relevant persistent context from CockroachDB before responding to every inquiry.
3. Keep deterministic handling for critical actions and fallbacks; an LLM should not be the only correctness or safety mechanism.
4. Route messages to either an existing-plan explanation, check-in update/replan workflow, plan export, nutrition response, or a grounded generic response.

## Recent Implemented Work

### Context-Aware Chat Routing

A new semantic conversation-router layer was added, centered around:

- `src/fitness_conversation_router.py`
- `src/fitness_agent_runtime.py`
- `src/ollama_chat_language.py`

The implementation uses an Ollama classification result plus deterministic fallback rules. It loads the active plan, recent check-ins, readiness, user profile, goal, and relevant decision records before determining a response path.

Important fixes made while testing:

- Readiness-basis questions are classified before broad old/new-plan wording so they do not get mistaken for plan-provenance requests.
- The active plan lookup recognizes a repaired plan ID stored in `plan_change.repaired_plan_id`, because `plan_repair` decisions can retain the original plan as `plan_id`.
- The chat response should return a previously generated active plan when the user asks for it, unless a new status/check-in update requires a plan repair or regeneration.

### GUI Processing and Stop Behavior

The NiceGUI chat UI was updated to behave more like a typical LLM chat while a request is running:

- On send, the send control becomes a minimal stop control.
- The composer and follow-up/new-chat controls are disabled while processing.
- A subtle processing/status line rotates through lightweight phrases such as "Thinking" and "Plotting" instead of leaving an empty gap.
- Pressing Stop immediately restores the composer and shows `Stopped`.
- A request token plus deep-copied session prevents a late completion from rendering after the user has stopped it.

Primary UI files involved:

- `ui/chat.py`
- `ui/chat_controller.py`
- `ui/chat_state.py`
- `ui/theme.py`

The background request may still finish and write normal backend state after Stop, but its response is intentionally discarded in the UI. True backend request cancellation would require cancellation support through the Ollama and database call stack.

## Validation Already Performed

Focused tests passed:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
C:\Users\hewyu\anaconda3\python.exe -m pytest tests\test_fitness_conversation_router.py tests\test_adaptive_checkin.py tests\test_nicegui_chat_state.py tests\test_nicegui_theme.py tests\test_fitness_agent_runtime.py tests\test_fitness_chat.py tests\test_ollama_chat_language.py tests\test_agent_flow.py -q
```

Result: `51 passed`.

Python compilation also passed:

```powershell
C:\Users\hewyu\anaconda3\python.exe -m compileall -q src app.py nicegui_app.py ui
```

An earlier full suite result was `158 passed, 8 failed`. The eight failures were from absent legacy demo scripts (`scripts/module1...module7`) in the GUI baseline, not from the routing/UI changes.

### Live Browser Test

The local NiceGUI app was tested in the browser.

- The processing state displayed correctly, disabled input correctly, and exposed the Stop control.
- Stopping a generic prompt restored the input and prevented a delayed reply from appearing later.
- A real local CockroachDB check-in was created during testing using wording equivalent to: "slept 6.5 hrs, stress is high today, legs still sore from yesterday". This was intentional live-test data, so be aware it exists in the local database.

At the time of testing, the feature worktree server was running on port `8082`; the original GUI server was on `8081`. Check processes before starting additional servers.

## Git / Workspace State

The feature work was developed in an isolated worktree:

- Worktree: `C:\Users\hewyu\Desktop\CockroachDB-chat-router`
- Branch: `codex/context-aware-chat-routing`
- Base GUI branch: `chat-gui`
- Base GUI commit: `cc45fb7 feat: add fitness chat GUI`

The user had already made a GUI commit on `chat-gui` before the routing work began.

The routing and stop-behavior work had not been committed yet. Before committing, inspect the feature worktree with:

```powershell
git -C C:\Users\hewyu\Desktop\CockroachDB-chat-router status --short
git -C C:\Users\hewyu\Desktop\CockroachDB-chat-router diff --check
```

Likely changed/new files from this follow-up work include:

- `app.py`
- `src/fitness_agent_runtime.py`
- `src/m4_adaptive_checkin.py`
- `src/ollama_chat_language.py`
- `src/fitness_conversation_router.py` (new)
- `ui/chat.py`
- `ui/chat_controller.py`
- `ui/chat_state.py`
- `ui/theme.py`
- related test files, including `tests/test_fitness_conversation_router.py` (new)

Do not revert unrelated GUI changes. Inspect the diff before staging because the repository may contain other user work.

## Module 15: Safety and Validity

The current system already has a narrow pain safety mechanism:

- `src/m5_readiness_score.py` detects `sharp`, `worsening`, `severe`, and `persistent` pain, caps readiness at 30, and sets `safety_triggered`.
- `src/m6_plan_constraints.py` carries `injury_notes` and `medical_constraints` into plan constraints.
- `src/m7_plan_repair.py` converts a pain-triggered repair into a recovery-only session.

This does not yet cover all Module 15 requirements.

### Recommended Module 15 Architecture

Add a deterministic safety assessment that runs before M4-M9 and before normal generic chat responses:

```text
message + parsed check-in + profile + active plan + goal
    -> Module 15 safety assessment
    -> safe response / restricted action OR normal M4-M9 workflow
```

The safety assessment should receive only the relevant current context:

- Current message and parsed symptoms.
- Profile `injury_notes` and `medical_constraints`.
- Recent check-in pain/symptom information.
- Active-plan intensity and the action being requested.
- Goal details, especially unsafe weight-loss-rate requests.
- Nutrition, supplement, drug, and meal-photo requests.

It should output structured data such as:

```python
{
    "flags": ["chest_pain"],
    "highest_severity": "urgent",
    "allowed_actions": ["recommend_urgent_medical_help"],
    "reason": "Chest pain is outside the scope of training advice.",
    "policy_version": "1"
}
```

### What Belongs in Fitness Knowledge vs Safety Policy

Fitness knowledge (`fitness_knowledge` and its vector memories) may contain retrieved supporting education:

- General injury-aware training principles.
- General wellness-oriented nutrition guidance.
- Why meal-photo nutrition estimates are approximate.
- Evidence-backed background that helps explain a safety decision.

Do **not** use retrieved knowledge or Ollama as the final safety gate. Retrieval can miss a result and an LLM can misinterpret an edge case.

Keep emergency symptoms, refusal rules, eating-disorder-risk handling, harmful-drug/supplement handling, and intensity-blocking logic as versioned structured policy in code or a dedicated `safety_rules` table. The existing `fitness_knowledge` table is a simple topic/content store, so it is not a suitable sole source for enforceable rules.

For a minimal first version, put the policy in a Python module and log each result in the existing agent-decision audit trail. Add a dedicated table only if non-developers need to edit/version policies through data.

### Module 15 Rules To Implement

- Urgent symptoms: chest pain, fainting, severe dizziness, or severe shortness of breath. Do not provide workout direction; recommend urgent medical assessment.
- Sharp, worsening, or persistent pain: block intense training and direct the user to appropriate medical or qualified professional guidance.
- Known medical constraints: enforce stored clinician restrictions and ask for needed constraints before offering a specific plan when necessary.
- Unsafe rapid weight-loss requests: decline the target and offer general, sustainable wellness guidance.
- Eating-disorder-risk requests: avoid calorie/weight-loss coaching that reinforces harm; encourage qualified support.
- Harmful supplement or drug requests: refuse instructions that could facilitate harm and offer safer, general alternatives.
- Meal photos: when this feature is added, label estimates as approximate and avoid presenting them as clinical or exact measurements.

## Suggested Next Task

Implement Module 15 as a dedicated `src/m15_safety_validity.py` module with focused tests. Integrate it at the top of the runtime/router flow, then connect its existing pain result to M5/M6/M7 rather than duplicating pain logic.

Good initial tests:

- Chest pain blocks a workout-plan response.
- "No chest pain" does not falsely trigger a block.
- Severe dizziness and fainting receive urgent guidance.
- Sharp/worsening/persistent pain prevents intense workout generation.
- Stored medical constraints affect a generic workout request.
- Unsafe weight-loss goal, eating-disorder-risk wording, and harmful drug/supplement request are refused safely.
- Normal recovery/soreness messages still proceed through the existing readiness flow.

