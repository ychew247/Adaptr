# Adaptr: Current Implementation Workflow

This document describes the current app, not the original build roadmap. For installation and a judge-ready manual test script, use the [README](../README.md).

## System overview

```text
NiceGUI chat
  -> semantic routing + safety gate
  -> check-in, readiness, plan, repair, nutrition services
  -> CockroachDB (durable memory + decisions + vector retrieval)
  -> Ollama (structured interpretation and plan language)
  -> Amazon S3 (optional private Excel workbook storage)
```

| Module | Responsibility | Status |
| --- | --- | --- |
| 1 | NiceGUI chat application | Complete |
| 2 | Identity and static profile | Complete |
| 3 | Natural-language training goal | Complete |
| 4 | Daily check-in, safety, and readiness | Complete |
| 5 | Validated dated workout plan | Complete |
| 6 | Targeted plan repair | Complete; content-quality refinement remains |
| 7 | Nutrition targets | Complete |
| 8 | CockroachDB memory and decisions | Complete |
| 9 | Excel export and S3 storage | Complete |

## Module 1 — Chat application and routing

**Main files:** `nicegui_app.py`, `ui/chat.py`, `ui/chat_controller.py`, `ui/chat_state.py`

The NiceGUI application runs on `http://127.0.0.1:8081` by default. `FitnessChatController` owns each conversation state and routes a message through these phases:

1. `identity` — find or create the user.
2. `profile` — collect stable baseline details.
3. `goal` / `goal_follow_up` — collect the training target and duration.
4. `daily` — handle check-ins, plan questions, repair requests, next-week requests, and exports.

Ollama classifies daily messages semantically. The application then independently authorizes state-changing actions before saving a check-in, generating a plan, or exporting a workbook. This prevents simple keyword matches from treating refusals or capability questions as actions.

## Module 2 — Identity and static profile

**Main files:** `src/m1_user_identity.py`, `src/m2_static_profile.py`, `src/cockroach_user_repository.py`, `src/cockroach_static_profile_repository.py`

Identity uses a normalized display name. A returning name loads the saved profile and active goal; a new name enters onboarding.

The stored profile includes age, height, starting weight, training experience, equipment, weekly availability, injury/medical considerations, diet preferences, activity level, and BMR formula profile. These stable values are not requested at every check-in.

## Module 3 — Training goal interpretation

**Main files:** `src/m3_training_goal.py`, `src/ollama_goal_parser.py`, `src/cockroach_goal_repository.py`

The user provides one natural-language training goal. Ollama extracts the athlete type, target areas, desired outcomes, and plan duration. A deterministic fallback parser and missing-field follow-up keep the goal usable if the model response is incomplete.

The active goal controls plan style, sport focus, progression window, and nutrition calculations.

## Module 4 — Check-in, safety, and readiness

**Main files:** `src/m4_adaptive_checkin.py`, `src/ollama_checkin_parser.py`, `src/m5_readiness_score.py`, `src/m15_safety_validity.py`, `src/cockroach_checkin_repository.py`

The daily check-in accepts natural language about sleep, energy, stress, soreness, pain, nutrition, weight, and workout completion. Ollama converts the message into structured check-in data; the app keeps the original text for auditability.

Before normal routing, the safety gate intercepts urgent health, harmful-substance, eating-disorder-risk, and unsafe rapid-weight-loss requests. It returns a safe response instead of producing exercise advice.

Readiness combines the current check-in with recent history and produces a score plus one of these bands:

- `train_as_planned`
- `reduce_volume`
- `lighter_session`
- `recovery_day`

## Module 5 — Dated, validated workout plans

**Main files:** `src/m6_hybrid_workout_plan.py`, `src/m6_plan_constraints.py`, `src/m6_plan_validator.py`, `src/program_schedule.py`, `src/workout_plan_selection.py`, `src/cockroach_workout_plan_repository.py`

The first valid check-in generates a plan beginning on the inquiry date, not an assumed Monday. Sessions contain a `scheduled_date`, stable `Day N` label, focus, exercises, sets/reps, adjustment, and status.

Generation combines:

1. Profile, goal, readiness, and check-in constraints.
2. Retrieved CockroachDB memory and fitness-knowledge context.
3. Ollama workout-plan wording.
4. Deterministic validation for calendar, equipment, injury, progression, and volume constraints.

The UI can show the current week, remaining sessions, a requested session, or an eligible next week. Stored program metadata lets users revisit earlier/current weeks after a future plan has been generated.

## Module 6 — Targeted workout repair

**Main files:** `src/agent_flow.py`, `src/m7_plan_repair.py`, `src/ollama_plan_repair_generator.py`, `src/ollama_repair_target_parser.py`, `src/workout_repair_target_selection.py`

Low readiness, pain/safety signals, missed sessions, or limited-time check-ins can trigger a repair automatically. If the user names sessions in the same message, the app also supports explicit repair targets:

```text
My shoulder is sore and energy is 3/5. Repair Day 2 and 2026-08-20.
```

Ollama extracts the requested references. Deterministic code resolves them only against `Day N` labels and dates that exist in the active plan. Each resolved date receives its own validated, idempotent repair decision.

- With explicit targets, only those sessions change.
- With no explicit target, the existing default remains: use the check-in-date session, or the next planned session.
- The chat names the changed sessions and states that the rest of the week is unchanged.

Current refinement: targeted dates and plan scope work, but the repair generator should be tightened further to avoid generic focus labels or overly broad exercise lists in a repaired session.

## Module 7 — Daily nutrition targets

**Main files:** `src/m8_nutrition_targets.py`, `src/m8_nutrition_service.py`, `src/ollama_nutrition_note_generator.py`, `src/cockroach_nutrition_target_repository.py`

The app calculates calorie, protein, hydration, and fibre targets from the static profile, goal, scheduled activity, and readiness. Ollama produces a concise meal-timing and adherence note; deterministic calculations remain the source of the numeric targets.

## Module 8 — CockroachDB memory and audit trail

**Main files:** `src/fitness_agent_runtime.py`, `sql/`, `src/cockroach_*_repository.py`, `src/m9_decision_log.py`, `src/cockroach_memory_embedding_repository.py`

`build_runtime` applies the SQL migrations before constructing repositories. The main persisted records are:

| Data | Purpose |
| --- | --- |
| `users` | Identity by normalized display name |
| `user_profiles` | Stable training and nutrition context |
| `goals` | Active target and plan duration |
| `daily_checkins` | Time-series recovery and adherence signals |
| `workout_plans` | Dated plan sessions, version/status, and export metadata |
| `nutrition_targets` | Daily calculated nutrition targets |
| `agent_decisions` | Readiness, generation, repair, and nutrition audit trail |
| `memory_embeddings` | Semantic retrieval of check-ins, plans, and decisions |
| `fitness_knowledge` | Seeded knowledge snippets for retrieval |

The app checks the Ollama embedding dimension before vector operations so the database schema and local embedding model remain compatible.

## Module 9 — Excel export and Amazon S3

**Main files:** `src/workout_plan_excel_export.py`, `src/s3_workout_plan_storage.py`, `ui/chat_controller.py`

`export my plan as excel` creates an `.xlsx` workbook containing the dated sessions.

- Without `AWS_S3_WORKOUT_PLAN_BUCKET`, NiceGUI serves the workbook as a local browser download.
- With a bucket configured, the app uploads `workout-plans/<user-id>/<plan-id>.xlsx` to a private bucket using AES-256 server-side encryption.
- The database stores the object key and the chat renders a time-limited presigned `GetObject` download link.

Required S3 permissions are `s3:PutObject`, `s3:GetObject`, and `s3:GetBucketLocation` for the bucket and `workout-plans/*` prefix.

## Verification and current progress

The focused test suites cover routing, check-in extraction, plan generation/validation, date-aware selection, plan repair, S3 storage, Excel creation, and the NiceGUI controller. The README includes a full manual GUI test flow using a fresh mock user.

Recent real-GUI verification confirmed:

1. New-user onboarding, goal parsing, readiness, nutrition, and dated plan generation.
2. Current-week plan display in chat.
3. Multi-session repair by `Day N` plus a displayed date, with only those sessions changed.
4. S3-backed Excel export rendering a presigned download button.

The broad legacy test suite still has unrelated failures from missing old demo scripts, an outdated theme expectation, and a Windows temporary-directory permission issue. Run focused tests while resolving those legacy issues:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests/test_agent_flow.py tests/test_m7_plan_repair.py tests/test_nicegui_chat_state.py tests/test_s3_workout_plan_storage.py -q
```

## Setup reference

See the [README](../README.md) for database, Ollama, optional S3 configuration, and the copy-paste test data used for judging.
