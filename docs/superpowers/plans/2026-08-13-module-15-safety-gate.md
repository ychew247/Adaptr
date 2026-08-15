# Module 15 Safety Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic pre-processing safety assessments that block unsafe fitness guidance and safely restrict pain-related training.

**Architecture:** A pure `m15_safety_validity` module returns a typed structured assessment from the raw message plus profile and goal context. The chat/runtime entry point runs it before existing workflows and only uses retrieved safety snippets to explain, never decide, the result.

**Tech Stack:** Python, pytest, existing CockroachDB repositories and Ollama vector-memory infrastructure.

## Global Constraints

- The safety decision is deterministic and must not depend on Ollama or vector retrieval.
- Explicit symptom negation must prevent false emergency blocks.
- Urgent results never create, repair, or recommend a workout.
- Safety explanations may cite fitness knowledge only after the deterministic decision.

---

### Task 1: Pure safety assessment policy

**Files:**
- Create: `src/m15_safety_validity.py`
- Test: `tests/test_m15_safety_validity.py`

**Interfaces:**
- Produces: `assess_safety(message: str, profile: Mapping | None = None, goal: Mapping | None = None, active_plan: Mapping | None = None, recent_checkin: Mapping | None = None) -> dict[str, Any]`.
- Produces: assessments with `flags`, `highest_severity`, `allowed_actions`, `reason`, and `policy_version`.

- [ ] **Step 1: Write failing emergency tests**

```python
def test_chest_pain_requires_urgent_assessment():
    result = assess_safety("I have acute chest pain; can I still train?")
    assert result["highest_severity"] == "urgent"
    assert "generate_workout" not in result["allowed_actions"]

def test_no_chest_pain_does_not_trigger_an_emergency():
    assert assess_safety("No chest pain, just mild leg soreness")["highest_severity"] == "allowed"
```

- [ ] **Step 2: Run the tests to verify they fail because the module is absent**

Run: `python -m pytest tests/test_m15_safety_validity.py -q`

- [ ] **Step 3: Implement the smallest deterministic policy table and negation-aware matching**

```python
def assess_safety(message: str, **context: Mapping[str, Any] | None) -> dict[str, Any]:
    flags = _flags_from_message(message)
    return _assessment_from_flags(flags, context)
```

- [ ] **Step 4: Run the policy tests and verify they pass**

Run: `python -m pytest tests/test_m15_safety_validity.py -q`

### Task 2: Non-emergency restrictions and regression cases

**Files:**
- Modify: `tests/test_m15_safety_validity.py`

**Interfaces:**
- Consumes: `assess_safety` from Task 1.
- Produces: verified handling for pain, stored constraints, weight-loss/eating-risk, and substance requests.

- [ ] **Step 1: Write failing tests for every restriction category**

```python
def test_worsening_knee_pain_blocks_intense_training():
    result = assess_safety("My knee pain is worsening; make a HIIT session")
    assert result["highest_severity"] == "restricted"

def test_profile_medical_constraint_blocks_specific_plan():
    result = assess_safety("Build a lifting plan", profile={"medical_constraints": "No loaded spinal flexion"})
    assert result["highest_severity"] == "restricted"
```

- [ ] **Step 2: Run the tests to verify each fails before its implementation**

Run: `python -m pytest tests/test_m15_safety_validity.py -q`

- [ ] **Step 3: Add deterministic rule handlers and user-safe reasons**

```python
if _has_hard_pain(message):
    return _restricted("pain", "Avoid intense or painful loading and seek qualified guidance.")
```

- [ ] **Step 4: Run the policy suite and verify it passes**

Run: `python -m pytest tests/test_m15_safety_validity.py -q`

### Task 3: Runtime/router short circuit

**Files:**
- Modify: `src/fitness_agent_runtime.py` and the active chat-routing entry point
- Test: the corresponding runtime/router test module

**Interfaces:**
- Consumes: `assess_safety` from Task 1 and persisted profile, goal, active plan, and check-in context.
- Produces: direct safe response for `urgent` and `blocked`; only `allowed`/appropriate `restricted` results reach normal workflow services.

- [ ] **Step 1: Write a failing integration test proving chest pain never invokes workout generation**

```python
def test_urgent_chest_pain_short_circuits_before_plan_generation():
    response = runtime.respond("I have chest pain")
    assert "urgent medical" in response.lower()
    assert generator.calls == []
```

- [ ] **Step 2: Run the integration test and verify it fails because no safety check is wired in**

Run: `python -m pytest tests/test_fitness_conversation_router.py -q`

- [ ] **Step 3: Call `assess_safety` immediately after context assembly and before intent/workflow dispatch**

```python
assessment = assess_safety(message, profile, goal, active_plan, recent_checkin)
if assessment["highest_severity"] in {"urgent", "blocked"}:
    return safety_response(assessment)
```

- [ ] **Step 4: Run integration and policy tests**

Run: `python -m pytest tests/test_m15_safety_validity.py tests/test_fitness_conversation_router.py -q`

### Task 4: Final validation

**Files:**
- Verify: `src/m15_safety_validity.py`, its unit tests, and router/runtime tests

- [ ] **Step 1: Run relevant tests**

Run: `python -m pytest tests/test_m15_safety_validity.py tests/test_fitness_conversation_router.py tests/test_adaptive_checkin.py -q`

- [ ] **Step 2: Compile changed application code**

Run: `python -m compileall -q src`

- [ ] **Step 3: Review the diff for accidental edits**

Run: `git diff --check`
