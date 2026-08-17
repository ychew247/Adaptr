# S3 Workout Plan Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist exported workout-plan Excel files in private Amazon S3 storage and provide secure, time-limited download links in chat.

**Architecture:** Keep Excel generation local and in-memory. A focused S3 storage adapter uploads the workbook to a private, user-and-plan-scoped key and creates a presigned GET URL. The plan repository persists the S3 key inside `plan_json`, while the UI renders a normal download button that opens the presigned URL.

**Tech Stack:** Python, Boto3, Amazon S3, CockroachDB JSONB, NiceGUI, pytest.

## Global Constraints

- Use `AWS_S3_WORKOUT_PLAN_BUCKET` to opt in to S3 storage.
- Keep the S3 bucket private; never construct public object URLs.
- Use a default presigned URL expiry of 900 seconds, configurable with `AWS_S3_WORKOUT_PLAN_URL_EXPIRY_SECONDS`.
- Preserve the existing in-browser download only when S3 is not configured.

---

### Task 1: Add a focused S3 workbook-storage adapter

**Files:**
- Create: `src/s3_workout_plan_storage.py`
- Modify: `requirements.txt`
- Test: `tests/test_s3_workout_plan_storage.py`

**Interfaces:**
- Produces: `S3WorkoutPlanStorage.from_environment() -> S3WorkoutPlanStorage | None`
- Produces: `upload_workbook(workbook_bytes, *, user_id, plan_id, filename) -> str`
- Produces: `create_download_url(object_key, filename) -> str`

- [ ] Write failing tests for an S3 key, private upload metadata, and a presigned URL.
- [ ] Implement the adapter using `put_object` and `generate_presigned_url`.
- [ ] Add Boto3 as a dependency and run the adapter tests.

### Task 2: Persist the exported S3 key and expose it through chat

**Files:**
- Modify: `src/cockroach_workout_plan_repository.py`
- Modify: `ui/chat_controller.py`
- Modify: `ui/chat.py`
- Test: `tests/test_cockroach_workout_plan_repository.py`
- Test: `tests/test_nicegui_chat_state.py`

**Interfaces:**
- Consumes: `CockroachWorkoutPlanRepository.update_export_s3_key(plan_id, object_key)`.
- Consumes: `S3WorkoutPlanStorage` from Task 1.
- Produces: message metadata `download_url` for an S3-backed button.

- [ ] Write failing tests for persistence and S3-backed metadata.
- [ ] Persist `export_s3_key` in the plan JSON and upload/sign the generated workbook.
- [ ] Render an external download button for `download_url`, retaining byte-download fallback only without S3 configuration.
- [ ] Run focused tests and the project export/chat test suite.
