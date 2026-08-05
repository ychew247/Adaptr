# Issues Found in Adaptive Fitness Memory Agent Workflow

Review of `fitness-agent-workflow.md` — overall verdict: **7.5/10**. Strong memory architecture (static / adaptive / goals / decisions split, audit-logged decisions, deterministic readiness score), but the issues below are real gaps, not just polish items.

---

## 1. User identity by name only is a real bug

Module 1 looks up users by `normalized_name` alone. Two users named "Alex" will collide and load the wrong memory — this directly breaks the module's own completion target ("distinguish between users such as Alex and Sam").

**Fix:** Add a lightweight secondary check (PIN, passphrase, or email) on name match, even for the hackathon MVP. At minimum, detect collisions and prompt for a disambiguator instead of silently loading the first match.

---

## 2. Vector retrieval is bolted on, not load-bearing

`memory_embeddings` and vector search are listed as inputs to plan generation and plan repair, but nothing in the workflow text specifies a plan actually *changing because of* a retrieved memory. As written, a judge could ask "what did the embedding table change about the output?" and there's no clear answer.

**Fix:** Wire at least one concrete step where a retrieved memory branches the plan logic — e.g., "last time soreness was this high, a deload worked better than cutting reps, so do that again" — and show it explicitly in the demo script.

---

## 3. Readiness score and safety gates overlap ambiguously

Pain notes both (a) subtract 30 points from the readiness score, and (b) independently "trigger safety handling." It's unclear which system has final authority — does a triggered safety flag override the score-based tier routing, or is it just folded into the same number?

**Fix:** Pick one authority model explicitly: either safety flags short-circuit the readiness score entirely (recommended), or they're purely a scoring input with no separate handling path. Document which.

---

## 4. No idempotency/ordering story for check-ins

`daily_checkins` has no unique constraint on `(user_id, checkin_date)`. A user checking in twice in one day will either duplicate rows or get resolved arbitrarily by query order — which matters for the "trend over last 3-7 check-ins" calculation in Module 5.

**Fix:** Add a unique constraint on `(user_id, checkin_date)` with an explicit upsert/append policy (e.g., latest check-in per day wins, or allow multiple with a `sequence` column and always aggregate by day first).

---

## 5. JSONB fields carry unexamined query load

`plan_json`, `goal_details`, `checkin_details`, and `weekly_availability` are all opaque JSONB blobs. Fine for a hackathon, but any demo moment that needs to query *inside* them (e.g., "show all users whose plan includes deadlifts") will require brittle JSON path queries written live.

**Fix:** Decide upfront which JSONB fields are truly opaque vs. which need at least one promoted/indexed column (e.g., a normalized `exercise_names STRING[]` alongside `plan_json`).

---

## 6. MCP demo module proves storage, not agency

The Module 12 demo queries are read-only SELECTs — they prove data exists, not that the *agent* reasoned its way to that data rather than a hardcoded insert. A skeptical judge could still ask "did the agent really decide this, or did you seed it?"

**Fix:** In the demo script, explicitly tie one `agent_decisions.reason` row back to the specific `daily_checkins` row that caused it (using `data_used JSONB`), and narrate that linkage live rather than just displaying rows.
