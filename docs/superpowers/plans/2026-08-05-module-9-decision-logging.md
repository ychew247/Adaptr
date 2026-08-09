# Module 9 Decision Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed, idempotent, chained decision timeline that records readiness, plan generation, plan repair, and nutrition decisions in CockroachDB.

**Architecture:** A new `DecisionLogService` validates a fixed taxonomy, derives duplicate keys, and delegates persistence to the existing CockroachDB repository. Module services call named logging methods after their domain records are stored. A forward-only migration adds idempotency and parent-chain fields, while the existing index serves timeline reads.

**Tech Stack:** Python, psycopg2, CockroachDB SQL, pytest.

## Global Constraints

- Use only the approved decision types: `readiness_assessment`, `plan_generation`, `plan_repair`, `nutrition_target`, `weekly_replan`.
- Never replace domain tables with audit rows.
- Return an existing row on a duplicate event; do not write or commit a duplicate.
- Keep readiness, workout-plan, repair, and nutrition calculations deterministic.
- Preserve Module 6/7 validation audit fields and retrieved memory IDs.

---

### Task 1: Schema and repository support

**Files:**
- Create: `sql/010_upgrade_agent_decisions_module9.sql`
- Modify: `src/cockroach_agent_decision_repository.py`
- Modify: `scripts/run_module.py`
- Test: `tests/test_cockroach_agent_decision_repository.py`

**Interfaces:**
- Produces `CockroachAgentDecisionRepository.find_by_idempotency_key(user_id, decision_type, idempotency_key) -> dict | None`.
- Produces `CockroachAgentDecisionRepository.create_decision(decision) -> dict`.
- Produces `CockroachAgentDecisionRepository.timeline_for_user(user_id, limit) -> list[dict]`.

- [ ] **Step 1: Write failing repository tests**

```python
saved = repository.create_decision({
    "user_id": "user-1", "decision_type": "readiness_assessment",
    "idempotency_key": "checkin:checkin-1", "trigger_date": "2026-08-05",
    "reason": "Readiness calculated.", "data_used": {}, "plan_change": {},
})
assert saved["idempotency_key"] == "checkin:checkin-1"
assert "parent_decision_id" in saved
```

- [ ] **Step 2: Run the targeted test and confirm it fails**

Run: `python -m pytest tests/test_cockroach_agent_decision_repository.py -q`

- [ ] **Step 3: Add the migration and repository fields**

```sql
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS idempotency_key STRING;
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS parent_decision_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS agent_decisions_user_type_key_idx
ON agent_decisions (user_id, decision_type, idempotency_key);
```

Update all repository SELECT/INSERT mappings to include the two fields and add the generic lookup/timeline methods.

- [ ] **Step 4: Run repository tests**

Run: `python -m pytest tests/test_cockroach_agent_decision_repository.py -q`

### Task 2: Shared decision-log service

**Files:**
- Create: `src/m9_decision_log.py`
- Create: `tests/test_m9_decision_log.py`

**Interfaces:**
- Produces `DecisionLogService.log_readiness_assessment(...) -> dict`.
- Produces `DecisionLogService.log_plan_generation(...) -> dict`.
- Produces `DecisionLogService.log_plan_repair(...) -> dict`.
- Produces `DecisionLogService.log_nutrition_target(...) -> dict`.

- [ ] **Step 1: Write failing taxonomy and duplicate tests**

```python
with pytest.raises(DecisionLogError, match="Unsupported decision type"):
    service.log("unknown", user_id="user-1", idempotency_key="x", reason="x")

assert service.log_readiness_assessment(...)["id"] == "existing-decision"
assert repository.created == []
```

- [ ] **Step 2: Run the targeted test and confirm it fails**

Run: `python -m pytest tests/test_m9_decision_log.py -q`

- [ ] **Step 3: Implement named methods and idempotency keys**

```python
def log_readiness_assessment(self, *, user_id, checkin, readiness):
    return self._log(
        decision_type="readiness_assessment",
        idempotency_key=f"checkin:{checkin['id']}",
        reason=f"Readiness score {readiness['readiness_score']} is {readiness['band']}.",
        data_used={"checkin_id": checkin["id"], "components": readiness["components"]},
    )
```

- [ ] **Step 4: Run service tests**

Run: `python -m pytest tests/test_m9_decision_log.py -q`

### Task 3: Integrate Modules 5–8

**Files:**
- Modify: `src/m6_hybrid_workout_plan.py`
- Modify: `src/m7_plan_repair.py`
- Modify: `src/m8_nutrition_service.py`
- Modify: `scripts/run_module.py`
- Test: `tests/test_hybrid_workout_plan.py`
- Test: `tests/test_m7_plan_repair.py`
- Test: `tests/test_m8_nutrition_targets.py`

**Interfaces:**
- Consumes `DecisionLogService` from Task 2.
- Produces one persisted decision after an accepted Module 6 plan, Module 7 result/fallback, and Module 8 target.

- [ ] **Step 1: Add failing integration tests with fake loggers**

```python
assert logger.plan_generation_calls[0]["plan_id"] == "saved-plan"
assert logger.plan_repair_calls[0]["parent_decision_id"] == "readiness-decision"
assert logger.nutrition_calls[0]["nutrition_target_id"] == "target-1"
```

- [ ] **Step 2: Run the focused integration tests and confirm they fail**

Run: `python -m pytest tests/test_hybrid_workout_plan.py tests/test_m7_plan_repair.py tests/test_m8_nutrition_targets.py -q`

- [ ] **Step 3: Inject the shared service into Module 6–8 constructors**

```python
saved_plan = self.plan_repository.create_active_plan(payload)
self.decision_log.log_plan_generation(
    user_id=user["id"], plan=saved_plan, checkin=latest_checkin,
    readiness=readiness, reason=plan_json["decision_reason"],
    retrieved_memory_ids=retrieved_memory_ids, validation=validation,
    generation_attempt=attempt,
)
```

Module 5 is a pure function; the CLI will call `log_readiness_assessment` after calculating its result. Module 6–8 will look up/create the source readiness row before writing a child decision where a check-in exists.

- [ ] **Step 4: Run focused integration tests**

Run: `python -m pytest tests/test_hybrid_workout_plan.py tests/test_m7_plan_repair.py tests/test_m8_nutrition_targets.py -q`

### Task 4: Documentation and end-to-end checks

**Files:**
- Modify: `docs/fitness-agent-workflow.md`
- Modify: `scripts/show_demo_data.py`
- Test: `tests/test_show_demo_data.py`

**Interfaces:**
- Produces a Module 9 workflow section with taxonomy, timeline SQL, chaining, index, and coverage target.
- Produces a demo-data view that includes the user decision timeline.

- [ ] **Step 1: Add a failing display test**

```python
assert "== agent_decisions ==" in output
assert "parent_decision_id" in output
```

- [ ] **Step 2: Update documentation and demo query**

```sql
SELECT decision_type, reason, trigger_date, validation_status, parent_decision_id, created_at
FROM agent_decisions
WHERE user_id = %s
ORDER BY created_at DESC
LIMIT 20;
```

- [ ] **Step 3: Run the full suite**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; C:\Users\hewyu\anaconda3\python.exe -m pytest -q`

