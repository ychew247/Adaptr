# Module 9 Decision Logging Design

## Goal

Create one auditable timeline for the actions that materially change a user's training guidance. The decision log records the rule-based facts behind an action, the generated or changed plan, validation outcome, and optional causal parent decision.

## Decision Taxonomy

`decision_type` is a fixed application-level vocabulary:

- `readiness_assessment`
- `plan_generation`
- `plan_repair`
- `nutrition_target`
- `weekly_replan`

The database migration will add a `CHECK` constraint for these labels. Any future label requires an explicit code and schema change.

## Data Model

Add two fields to `agent_decisions` through a new forward-only migration:

- `idempotency_key STRING NOT NULL`: a deterministic key derived by the service from the event that caused the action.
- `parent_decision_id UUID NULL REFERENCES agent_decisions(id)`: links a resulting action to the earlier decision that caused it.

Add a unique index on `(user_id, decision_type, idempotency_key)`. This makes reruns safe while allowing intentional later decisions. The existing repair constraint remains compatible during the transition.

`parent_decision_id` is optional. For example, a `plan_repair` can point to its `readiness_assessment`; a nutrition target can point to the readiness decision used for its note. It is omitted when there is no causal predecessor.

## Service Interface

`DecisionLogService` owns taxonomy validation, idempotency-key construction, and persistence. Its public methods are:

- `log_readiness_assessment(...)`
- `log_plan_generation(...)`
- `log_plan_repair(...)`
- `log_nutrition_target(...)`
- `timeline_for_user(user_id, limit=20)`

Modules provide structured facts; they do not hand-write SQL or decide their own duplicate policy.

## Workflow

1. A module completes its deterministic calculation or validated action.
2. The module calls the corresponding `DecisionLogService` method with source IDs and evidence.
3. The service validates `decision_type`, assembles `data_used`, builds its idempotency key, and checks for an existing matching row.
4. If a matching row exists, it returns that row without another write. Otherwise it stores one new `agent_decisions` row.
5. The service returns the persisted row ID so a later action can set `parent_decision_id`.

Idempotency scopes:

- readiness: one decision for each `checkin_id`;
- plan generation: one decision for each stored `plan_id`;
- plan repair: one decision for `(original_plan_id, trigger_date)`;
- nutrition target: one decision for each stored nutrition target;
- weekly replan: one decision for `(plan_id, week_start)`.

## Integration

- Module 5 writes `readiness_assessment` after calculating a score.
- Module 6 writes `plan_generation` after storing a validated plan and links it to the readiness decision for its source check-in when available.
- Module 7 continues to write `plan_repair`, now through the shared service, and links it to the triggering readiness decision when available.
- Module 8 writes `nutrition_target` after its deterministic target is stored and links it to the readiness decision when available.

The log does not replace domain tables. `daily_checkins`, `workout_plans`, and `nutrition_targets` remain the source of truth for their corresponding records.

## Timeline Query

```sql
SELECT
  decision_type,
  reason,
  trigger_date,
  validation_status,
  parent_decision_id,
  created_at
FROM agent_decisions
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 20;
```

`agent_decisions_user_created_idx (user_id, created_at DESC)` supports this core read.

## Tests and Completion Criteria

- Reject an unknown decision type before a database write.
- Repeating an identical event returns the existing decision and does not commit a duplicate row.
- Create and query at least `readiness_assessment`, `plan_generation`, and `plan_repair` rows.
- Verify causal chaining where a parent row exists.
- Verify Module 8 creates a `nutrition_target` decision without changing its deterministic numeric calculation.

