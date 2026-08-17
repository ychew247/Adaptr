# Targeted Multi-Session Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair one or more explicitly requested sessions from one daily check-in without changing the automatic default repair target.

**Architecture:** Ollama extracts target references. Deterministic code resolves them against the active-plan sessions, and the repair flow runs one validated repair per resolved date. A repair applies only to its named session.

**Tech Stack:** Python, NiceGUI, Ollama structured JSON, CockroachDB, pytest.

## Global Constraints

- Interpret target references with Ollama, never hardcoded keyword routing.
- Mutate only targets resolved from the active plan.
- Preserve current date-aware repair when there are no targets.
- Retain per-user, plan, and target-date repair idempotency.

---

### Task 1: Parse and resolve requested session targets

**Files:**
- Create: `src/ollama_repair_target_parser.py`
- Create: `src/workout_repair_target_selection.py`
- Test: `tests/test_ollama_repair_target_parser.py`
- Test: `tests/test_workout_repair_target_selection.py`

**Interfaces:** `OllamaRepairTargetParser.parse(message) -> list[str]`; `resolve_repair_target_dates(references, sessions) -> list[str]`.

- [ ] Write a parser test that returns `['Day 2', '2026-8-19']` from a compound soreness-and-repair message.
- [ ] Run it and confirm it fails because the parser does not exist.
- [ ] Implement JSON-only target extraction and empty-list handling.
- [ ] Write resolver tests for labels, unpadded ISO dates, duplicate references, and unavailable targets.
- [ ] Implement exact plan-session matching and run both tests.
- [ ] Commit the parser and resolver.

### Task 2: Make repair application target-specific

**Files:**
- Modify: `src/m7_plan_repair.py`
- Test: `tests/test_m7_plan_repair.py`

**Interfaces:** Add optional `target_date` to `apply_repair_action`; `PlanRepairService.run_repair(trigger_date=...)` passes it through.

- [ ] Write a failing test where recovery repair targets `2026-08-19` and leaves the other sessions byte-for-byte unchanged.
- [ ] Run it and confirm it fails because the selected target is not accepted or all sessions are changed.
- [ ] Use `target_date` before the current check-in-date fallback and remove the recovery whole-week loop.
- [ ] Run the Module 7 suite and commit the repair change.

### Task 3: Route explicit targets from chat through the agent flow

**Files:**
- Modify: `src/fitness_agent_runtime.py`
- Modify: `src/agent_flow.py`
- Modify: `ui/chat_controller.py`
- Test: `tests/test_agent_flow.py`
- Test: `tests/test_nicegui_chat_state.py`

**Interfaces:** Add `requested_repair_dates: list[str] | None` to `AdaptiveFitnessAgent.run_daily_flow`.

- [ ] Write a failing flow test proving two dates call the repair service twice in date order.
- [ ] Run it and confirm it fails because the argument does not exist.
- [ ] Implement sequential repair calls, using existing default routing when the list is empty.
- [ ] Write a controller test for the user's compound shoulder/arm soreness, six-hour sleep, 3/5 energy, and two-date repair request.
- [ ] Run the controller and flow tests, then commit the routing change.

### Task 4: Verify behavior

**Files:**
- Test: `tests/test_ollama_repair_target_parser.py`
- Test: `tests/test_workout_repair_target_selection.py`
- Test: `tests/test_m7_plan_repair.py`
- Test: `tests/test_agent_flow.py`
- Test: `tests/test_nicegui_chat_state.py`

- [ ] Run the targeted pytest suite.
- [ ] Run a live Ollama extraction for `repair Day 2 and 2026-8-19` and confirm resolution to plan dates.
- [ ] Use the NiceGUI session for Micheal Phelps: submit the compound status request, ask for the repaired plan, and verify only the two named dates change.
- [ ] Commit verification-only changes, if any.

