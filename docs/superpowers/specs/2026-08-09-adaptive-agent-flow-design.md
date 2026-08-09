# Adaptive Agent Flow Design

## Goal

Provide one controller that turns a natural-language check-in into a complete,
auditable daily fitness response: saved check-in, readiness result, a validated
plan action when needed, and nutrition guidance.

## Scope

The controller orchestrates existing Modules 4 through 8 for a user who has
already completed identity, static-profile, and goal setup. It also generates a
first validated plan through Module 6 when no active plan exists.

## Architecture

Create `AdaptiveFitnessAgent` in `src/agent_flow.py`. It receives existing
repositories and services through its constructor so the GUI has a single,
testable entry point and contains no business rules.

`run_daily_flow(user, workout_today, ask=input, say=print)` will:

1. Run Module 4 to parse the free-text response with Ollama and upsert that
   user's row for the current date.
2. Run Module 5 once using the saved check-in and recent history.
3. Log the `readiness_assessment` through `DecisionLogService`.
4. Load the active plan and route deterministically:
   - no active plan: run Module 6 plan generation;
   - readiness `80-100`: retain the active plan;
   - readiness `60-79`: run Module 7 automatic reduced-volume repair;
   - readiness below `60`, or any safety pain flag: run Module 7 lighter or
     recovery repair;
   - missed-workout or time-limit signals in the parsed check-in: run Module 7
     even when readiness is at least `80`.
5. Reload the active plan after any generation or repair.
6. Run Module 8 using the same computed readiness and the final plan state.
7. Return an `AgentFlowResult` dictionary containing the saved check-in,
   readiness, action, plan status, nutrition target, and concise summary.

Module 7 and Module 8 will accept optional precomputed readiness data. This
prevents inconsistent calculations while their existing idempotent Module 9
logging continues to protect against duplicate records.

## Daily Check-in Persistence

`CockroachCheckinRepository.create_checkin` will use CockroachDB upsert
semantics for `(user_id, checkin_date)`. A later check-in on the same day
replaces the adaptive values and free-text note, then returns the saved row.
`AdaptiveCheckinService.run_checkin` will return that row rather than a route
string.

## User-facing Behavior

`workout_today` remains explicit input. The CLI exposes it as `--workout-today`;
the future GUI exposes the same value as a toggle. The controller will not
invent a training-day schedule from an unstructured weekly plan.

If repair validation fails twice, Module 7 retains the prior validated plan.
The controller still completes Module 8 against that retained plan and returns
the fallback action in its result.

## CLI Integration

Add `--module agent` to `scripts/run_module.py`. It follows the current
identity/profile/goal checks, asks the Module 4 check-in question, runs the
complete flow, and prints a compact result. Existing per-module commands stay
available for focused testing.

## Error Handling

The check-in is saved before later work begins. A failed plan generation or
repair is reported as an action error; the controller must never present an
unvalidated plan. Module 8 retains its deterministic numeric calculation and
fallback note behavior if Ollama's explanatory call fails.

## Tests

Add focused unit tests with in-memory fakes for:

- high readiness retaining the active plan;
- `60-79` readiness automatically calling repair;
- a pain gate calling repair;
- no active plan calling generation;
- nutrition receiving the shared readiness and final plan state;
- same-day check-in upsert behavior;
- result structure remaining suitable for a future GUI.

## Out of Scope

- GUI implementation.
- Scheduled reminders and weekly replanning.
- Automatically inferring whether today is a planned workout day.
