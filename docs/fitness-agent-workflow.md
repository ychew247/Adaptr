# Adaptive Fitness Memory Agent Workflow

This document breaks the project into modules so the hackathon build can be completed in manageable pieces. The goal is to demonstrate an agent that stores, retrieves, and acts on persistent fitness memory using CockroachDB and AWS.

## 1. Product Goal

Build an adaptive fitness agent that:

- Identifies each user by name plus a lightweight disambiguator so two users with the same name do not share memory.
- Stores static fitness profile data separately for each user.
- Stores adaptive health stats as dated time-series memory.
- Generates targeted workout and rough nutrition plans.
- Adjusts plans when the user's condition changes.
- Saves every important agent decision and reason.
- Uses CockroachDB Managed MCP and vector indexing to demonstrate production-grade agent memory.

## 2. High-Level Architecture

```text
User interface
  -> Agent orchestration layer
  -> Fitness memory service
  -> CockroachDB
  -> Vector retrieval
  -> Plan generator
  -> Decision logger
  -> AWS services
```

Planned services:

- CockroachDB Cloud as the system of record.
- CockroachDB Managed MCP Server for agent/database access during development and demo.
- CockroachDB vector indexing for semantic retrieval.
- Ollama for local/free LLM reasoning during the hackathon demo.
- AWS Lambda for scheduled daily reminders and weekly replanning, if a free-tier-friendly deployed workflow is needed.
- Amazon S3 for optional uploaded artifacts such as meal photos, imported logs, exported reports, or demo assets.

Note: The organizer message says AWS Bedrock is the listed AWS service without a free tier, and recommends Ollama as the free workaround. This workflow therefore treats Ollama as the model runtime and keeps AWS usage focused on free-account-friendly services such as S3 and optionally Lambda.

## 3. Module 1: User Identity

Purpose: make the agent load the correct memory before giving advice.

Workflow:

1. Agent asks: "What name should I use for your fitness profile?"
2. Agent asks for a lightweight secondary identifier, such as a PIN, passphrase, or email.
3. App searches `users` by normalized name and disambiguator hash.
4. If exactly one user matches, load their memory.
5. If no user matches, create a new user row.
6. If the name matches multiple profiles, ask for the disambiguator instead of silently loading the first row.
7. Continue to static onboarding for new users or daily check-in for returning users.

MVP table:

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name STRING NOT NULL,
  normalized_name STRING NOT NULL,
  identity_hint STRING,
  disambiguator_hash STRING NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (normalized_name, disambiguator_hash)
);
```

Completion target:

- The agent can distinguish between users such as "Alex" and "Sam".
- The agent can distinguish between two users who both enter "Alex".
- Each user has separate profile, check-ins, plans, and decisions.

## 4. Module 2: Static Fitness Memory

Purpose: collect stable context that should not be asked every day.

Static fields:

- Age
- Height
- Starting weight
- Training experience
- Equipment access
- Weekly availability
- Injury or medical constraints
- Diet preferences or restrictions
- Current activity level

Workflow:

1. For a new user, ask for baseline fitness details.
2. Parse the response into structured fields.
3. Save the static profile.
4. Ask follow-up questions only for missing critical fields.

MVP table:

```sql
CREATE TABLE user_profiles (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  age INT,
  height_cm DECIMAL,
  starting_weight_kg DECIMAL,
  training_experience STRING,
  equipment_access STRING[],
  weekly_availability JSONB,
  injury_notes STRING,
  medical_constraints STRING,
  diet_preferences STRING,
  activity_level STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The agent can create a safe baseline plan without repeatedly asking stable details.

## 5. Module 3: Goal Setup

Purpose: make the plan targeted instead of generic.

Supported goals:

- Keep lean
- Fat loss
- Muscle gain
- Strength improvement
- Strengthen specific muscle groups
- Improve VO2 max
- General wellness
- Sport-specific conditioning

Plan duration:

- Ask how long the user wants the overall plan to run, such as 4 weeks, 8 weeks, 12 weeks, or a custom number of months.
- Store the duration with the active goal so weekly plans can be generated as phases inside a longer plan.
- Use the duration to decide progression pacing, review checkpoints, and when to generate milestone summaries.

Workflow:

1. Ask one general free-form question for the user's training target.
2. Include hints so the user can mention what kind of athlete or trainee they are, target muscles, desired outcome, and plan duration in one answer.
3. Parse the free-form answer deterministically into athlete type, target muscle groups, desired outcomes, and plan duration.
4. Ask a follow-up only if the answer is missing required information such as desired outcome or plan duration.
5. Save the active goal, raw goal text, parsed details, and plan duration.
6. Use the goal and duration to select plan style, progression pace, review cadence, and nutrition targets.

General prompt:

```text
What is your training target?

Describe it naturally. Include what kind of athlete or trainee you are, any target muscles or performance areas, your desired outcome, and how long the plan should run.

Examples:
- I am a futsal athlete and want stronger hamstrings and calves, better VO2 max, and to stay lean over 3 months.
- I want bigger shoulders and arms in 8 weeks.
- I want fat loss and stronger core muscles over 1 month.
```

MVP table:

```sql
CREATE TABLE goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  goal_type STRING NOT NULL,
  plan_duration_weeks INT,
  goal_details JSONB,
  status STRING NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The agent can generate different plans for VO2 max, lean maintenance, muscle gain, and specific muscle focus.

## 6. Module 4: Adaptive Daily Memory

Purpose: capture changing health stats that should influence training.

Adaptive fields:

- Sleep duration
- Stress level
- Energy level
- Soreness level
- Sore muscle groups
- Pain notes
- Current weight
- Workout completion
- Nutrition adherence
- Free-text note

Workflow:

1. Ask a short daily or every-few-days body/nutrition check-in.
2. Vary the prompt based on recent memory, such as asking about a previous hamstring strain if it was mentioned before.
3. Let the user answer naturally instead of requiring a strict daily form.
4. Use Ollama to extract structured adaptive memory from the free-form response.
5. Store each check-in as a dated row.
6. Calculate recent trends from the last 3 to 7 check-ins.
7. Feed trends into the readiness score and plan adjustment module.

MVP table:

```sql
CREATE TABLE daily_checkins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  checkin_date DATE NOT NULL DEFAULT current_date,
  sleep_hours DECIMAL,
  stress_level INT,
  energy_level INT,
  soreness_level INT,
  sore_muscle_groups STRING[],
  pain_notes STRING,
  weight_kg DECIMAL,
  workout_completed STRING,
  nutrition_adherence STRING,
  free_text_note STRING,
  checkin_details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, checkin_date)
);
```

Check-in ordering policy:

- For the MVP, the latest check-in per user per date wins.
- If a user checks in twice on the same day, upsert the row and preserve the latest free-text note.
- Trend calculations use one normalized daily row per date, ordered by `checkin_date DESC`.
- Future versions can support multiple same-day check-ins with a `sequence` column, but the MVP avoids ambiguous duplicate rows.

Completion target:

- The agent treats sleep, stress, soreness, pain, and weight as time-series memory, not one-off chat text.
- The recurring user loop focuses mainly on body condition and nutrition instead of repeatedly asking static profile questions.

## 7. Module 5: Readiness Score

Purpose: convert adaptive memory into a simple decision signal.

Inputs:

- Sleep trend
- Stress trend
- Energy trend
- Soreness trend
- Pain flags
- Workout completion

Formula:

1. Compute a personalized baseline for each adaptive metric using the user's own recent history.
2. For cold starts, blend the personal baseline with population defaults so a new user still gets a stable score.
3. Use exponential moving average (EMA) so recent check-ins matter more without ignoring older entries.
4. Convert each metric into a z-score where positive always means "trending worse."
5. Convert z-scores into smooth sigmoid penalties instead of hard binary thresholds.
6. Combine penalties with weights.
7. Apply pain as a hard gate after the score is calculated.

Baseline blending:

```text
mu_blend = (n / (n + k)) * mu_personal + (k / (n + k)) * mu_population
sigma_blend = (n / (n + k)) * sigma_personal + (k / (n + k)) * sigma_population
```

Starting constants:

- `k = 5` for cold-start shrinkage.
- Population sleep baseline: mean 7 hours, sigma 1 hour.
- Population stress, energy, and soreness baseline: mean 3, sigma 1.
- EMA alpha: `0.4`.

Z-score:

```text
z_i = (EMA_i - mu_blend_i) / sigma_blend_i
```

Sign handling:

- Sleep and energy are flipped because lower values are worse.
- Stress and soreness are not flipped because higher values are worse.

Smooth penalty:

```text
penalty_i = 1 / (1 + e^(-2 * (z_i - 0.5)))
```

Weights:

| Metric   | Weight |
|----------|--------|
| Sleep    | 20     |
| Stress   | 15     |
| Energy   | 15     |
| Soreness | 20     |

Full score:

```text
deduction = 20 * penalty_sleep
          + 15 * penalty_stress
          + 15 * penalty_energy
          + 20 * penalty_soreness

interaction = 10 * penalty_sleep * penalty_soreness

readiness = clip(100 - deduction - interaction, 0, 100)
```

Safety authority model:

- Pain gates override the numeric score after the base readiness is calculated.
- If the latest check-in mentions sharp, worsening, severe, or persistent pain, clamp readiness to at most `30`.
- Trigger safety handling and log `pain_gate_applied = true`.
- This prevents good sleep or nutrition from masking a serious pain signal.

Implementation signature:

```python
def compute_readiness(user_history: list[dict], today_checkin: dict) -> dict:
    ...
```

Returned fields:

- `readiness_score`: score from 0 to 100.
- `band`: route for plan adjustment.
- `safety_triggered`: whether the pain gate fired.
- `components`: z-scores, penalties, baselines, deduction, interaction, and pain-gate flag for decision logging.

Readiness bands:

- 80-100: train as planned.
- 60-79: reduce volume or intensity slightly.
- 40-59: switch to lighter session or recovery work.
- Below 40: recovery day and safety guidance.

Completion target:

- The agent can explain how today's check-in changed today's workout.

## 8. Module 6: Workout Plan Generation

Purpose: create targeted weekly plans.

Inputs:

- Static profile
- Active goal
- Plan duration
- Equipment access
- Weekly availability
- Recent check-ins
- Readiness score
- Prior plans

Workflow:

1. Generate a phase-aware plan for the requested duration, such as 4, 8, or 12 weeks.
2. Break the plan into weekly blocks with training days, exercises, sets, reps, intensity, and rest.
3. Store the active week and the overall duration context.
4. Link plan choices to goal, duration, and profile constraints.
5. On check-in, adjust the current day's session if readiness is low.
6. Promote commonly queried plan fields, such as exercise names, target muscles, and intensity band, alongside the full JSON plan.
7. Archive the old active plan when generating a new active week.
8. Use Ollama to generate the session content from profile, goal, readiness, and equipment context.
9. Enforce readiness and safety constraints in Python after the model response, so the model cannot override a recovery or safety intensity band.

MVP table:

```sql
CREATE TABLE workout_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  goal_id UUID REFERENCES goals(id),
  week_start DATE NOT NULL,
  exercise_names STRING[],
  target_muscle_groups STRING[],
  intensity_band STRING,
  plan_json JSONB NOT NULL,
  status STRING NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

JSONB policy:

- `plan_json` stores the complete generated plan and can remain flexible.
- Frequently queried fields are promoted into columns: `exercise_names`, `target_muscle_groups`, and `intensity_band`.
- This lets the demo query plans without relying on brittle live JSON path expressions.

Completion target:

- The agent can create a different duration-aware plan for each goal and revise the active plan when new adaptive memory arrives.

## 9. Module 7: Plan Repair

Purpose: make the agent complete tasks, not just respond.

Trigger examples:

- User missed a workout.
- User slept poorly.
- User reports high soreness.
- User has pain in a target muscle group.
- User has less time than expected.

Actions:

- Move a session to another day.
- Reduce set count or intensity.
- Replace an exercise.
- Add mobility or recovery work.
- Preserve weekly goal where possible.
- Retrieve similar past memories before choosing the repair strategy.

Implemented repair workflow:

1. Load the active plan, latest check-in, profile, goal, and readiness result.
2. Check idempotency before any model call. One `plan_repair` decision is allowed for each `(user_id, original_plan_id, trigger_date)`.
3. Apply a deterministic safety and readiness action table:
   - sharp, worsening, severe, or persistent pain: recovery substitution only;
   - recovery band: recovery substitution;
   - lighter band: lighter substitution;
   - reduced band: reduced-volume substitution;
   - missed session: reschedule without increasing weekly volume;
   - limited time: shorten one session.
4. Embed the repair trigger plus current plan state and retrieve similar prior `plan_repair` memories from `memory_embeddings`.
5. Send the selected action, constraints, retrieved repair precedents, and any prior validation failure to Ollama. Ollama may suggest only the replacement-session wording and exercises; it cannot choose the safety action.
6. Apply the edit deterministically and run the same full-plan hard validator as Module 6: equipment, injury/medical exclusions, pain gate, volume ceiling, intensity ceiling, and schedule limits.
7. Retry one time with explicit validator feedback. If both attempts fail, leave the previous validated plan active and log a fallback decision.
8. On success, archive the old active plan, save the repaired validated version, write an auditable `agent_decisions` row, and embed the successful repair as future precedent.

Example:

```text
User: I missed Push Day.
Agent: I moved Push Day to Thursday, shortened Friday's session, and kept total weekly chest volume within range.
```

Memory-backed repair example:

```text
Current check-in: high hamstring soreness and low sleep.
Vector retrieval finds: "Last time hamstring soreness stayed high after sprint work, a deload plus hip mobility resolved it faster than simply cutting reps."
Agent action: replace today's hamstring-heavy lower-body work with mobility, light posterior-chain accessories, and move sprint conditioning later in the week.
```

Completion target:

- A missed workout changes the stored plan instead of only receiving encouragement.
- At least one demo repair changes because a retrieved memory influenced the selected repair action.

## 10. Module 8: Nutrition Targets

Purpose: support training with deterministic, auditable targets rather than LLM-estimated nutrition numbers. This is planning guidance, not medical advice.

### Inputs

- Static profile: age, height, starting weight, and the user's selected BMR formula profile (`male` or `female`). This selection is stored once; the agent must never guess it.
- Stored weekly availability and, when available, active-plan session frequency.
- Active training goal, active workout plan, latest readiness band, and whether a workout is planned today.

### Deterministic calculation rules

1. Calculate BMR with Mifflin-St Jeor: male is `10 * weight_kg + 6.25 * height_cm - 5 * age + 5`; female is `10 * weight_kg + 6.25 * height_cm - 5 * age - 161`.
2. Derive the TDEE activity factor from the stored plan frequency first, then `weekly_availability` if no plan frequency is available. Use `1.2` for 0 sessions, `1.375` for 1-3 sessions, `1.55` for 4-5 sessions, and `1.725` for 6-7 sessions. `TDEE = BMR * activity_factor`.
3. Derive the calorie range from goal category: fat loss is `TDEE * 0.80` to `TDEE * 0.85`; maintenance and sport conditioning are `TDEE` to `TDEE`; muscle gain is `TDEE * 1.05` to `TDEE * 1.15`.
4. Derive protein from body weight. Maintenance and muscle gain use `1.4-2.0 g/kg`; fat loss uses `2.0-2.4 g/kg` to better support lean-mass retention during a calorie deficit. The MVP stores the deterministic midpoint as `protein_g` and includes the full range in the human-facing note.
5. Set hydration to `weight_kg * 0.033 L`, then add `0.5 L` when a workout is planned today.
   The MVP fiber target is a fixed `30 g` for the male formula profile and `25 g` for the female formula profile.
6. For a high-intensity planned session, add `100-150 kcal` to the calorie range and `0.4 L` (the fixed midpoint of the allowed `0.3-0.5 L` range) to hydration.
7. A `recovery` readiness band never reduces calories. It only changes the human-facing note to acknowledge that a lighter appetite can be normal.
8. Apply the non-negotiable calorie safety floor after calculation: `1500 kcal` minimum for the male formula profile and `1200 kcal` for the female formula profile. The maximum must never be lower than the final minimum.

### Workflow

1. Load profile, goal, active plan, latest check-in/readiness, and plan or availability frequency.
2. Compute BMR, TDEE, calorie range, protein, hydration, and fiber deterministically in Python.
3. Validate the numeric result: valid formula profile, positive values, correct safety floor, and `calories_max >= calories_min`.
4. Give Ollama the computed values and constraints only. Ollama may create meal-timing suggestions, food ideas that respect diet preferences, and an adherence question; it cannot change the numeric targets.
5. Store the validated daily nutrition target and the explanatory note in CockroachDB.
6. At the next adaptive check-in, use the note to ask about nutrition adherence without requiring daily logging.

MVP nutrition output:

- Validated calorie range
- Protein target with the calculation range in notes
- Hydration target
- Fiber target
- Pre-workout or post-workout suggestion based on the already-computed plan intensity

MVP table:

```sql
CREATE TABLE nutrition_targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  target_date DATE NOT NULL,
  calories_min INT,
  calories_max INT,
  protein_g INT,
  hydration_l DECIMAL,
  fiber_g INT,
  notes STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The diet feature supports the workout plan without pretending to be medical nutrition therapy.

## 11. Module 9: Decision Logging

Purpose: prove the agent has auditable memory.

Every major action should record:

- What the agent decided.
- Why it decided that.
- What data it used.
- What changed.
- Whether a safety rule was triggered.

MVP table:

```sql
CREATE TABLE agent_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  checkin_id UUID,
  plan_id UUID,
  trigger_date DATE,
  decision_type STRING NOT NULL,
  reason STRING NOT NULL,
  data_used JSONB,
  plan_change JSONB,
  safety_flags STRING[],
  validation_status STRING NOT NULL DEFAULT 'pending',
  validation_notes JSONB,
  retrieved_memory_ids UUID[],
  generation_attempt INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The demo can show a timeline of agent decisions for a user.
- Each major decision can be traced back to the specific check-in, plan, and retrieved memories that caused it.
- A repair that failed validation can be shown as a fallback decision that intentionally preserved the prior valid plan.

## 12. Module 10: Vector Memory and Retrieval

Purpose: let the agent retrieve relevant past context semantically.

Use cases:  

- Find similar past weeks where the user had low sleep and high soreness.
- Retrieve old notes mentioning knee pain, fatigue, or missed workouts.
- Retrieve relevant fitness knowledge snippets before generating advice.
- Compare current user state to prior successful weeks.
- Branch plan repair based on what worked in a similar prior situation.

Memory candidates for embeddings:

- Free-text daily notes.
- Agent decision reasons.
- Weekly summaries.
- Fitness knowledge snippets.
- Goal descriptions.

MVP table:

```sql
CREATE TABLE memory_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  source_type STRING NOT NULL,
  source_id UUID,
  content STRING NOT NULL,
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example retrieval:

```sql
SELECT content
FROM memory_embeddings
WHERE user_id = $1
ORDER BY embedding <-> $2
LIMIT 5;
```

Completion target:

- Before adjusting a plan, the agent can retrieve relevant memories instead of relying only on the latest message.
- The demo includes one case where retrieved memory changes the chosen plan repair strategy.

## 13. Module 11: Fitness Knowledge Base

Purpose: reduce hallucination by grounding responses in curated context.

Knowledge categories:

- Progressive overload
- Recovery and deload principles
- Beginner training safety
- VO2 max training basics
- Protein and calorie target guidance
- Injury and pain safety rules
- Exercise substitution rules

Workflow:

1. Store short trusted snippets in `fitness_knowledge`.
2. Embed each snippet into `memory_embeddings` or a dedicated vector table.
3. Retrieve relevant snippets during planning.
4. Make the agent state uncertainty and ask follow-up questions when needed.

MVP table:

```sql
CREATE TABLE fitness_knowledge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic STRING NOT NULL,
  content STRING NOT NULL,
  source_name STRING,
  source_url STRING,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The agent combines user memory with trusted fitness guidance before giving recommendations.

## 14. Module 12: CockroachDB Managed MCP Demo

Purpose: satisfy hackathon requirements and show database transparency.

Demo actions:

- List databases.
- Show tables.
- Inspect schema.
- Run read-only queries against users, check-ins, plans, and decisions.
- Use MCP to verify stored agent memory after a conversation.
- Show how one `agent_decisions` row links back to the `daily_checkins` row and active plan that caused it.

Example demo query:

```sql
SELECT decision_type, reason, created_at
FROM agent_decisions
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 10;
```

Agency proof query:

```sql
SELECT
  d.decision_type,
  d.reason,
  c.free_text_note AS triggering_checkin,
  d.data_used,
  d.plan_change
FROM agent_decisions AS d
JOIN daily_checkins AS c ON c.id = d.checkin_id
WHERE d.user_id = $1
ORDER BY d.created_at DESC
LIMIT 5;
```

Completion target:

- Judges can see that the agent's memory is really stored in CockroachDB.
- Judges can see that the agent's decisions are caused by stored user memory, not just seeded rows.

## 15. Module 13: CockroachDB Agent Skills Repo

Purpose: use CockroachDB's open-source agent expertise during development.

How to use it:

1. Add relevant CockroachDB Agent Skills to the project or agent environment.
2. Use schema design skills when creating tables and indexes.
3. Use query performance skills when designing retrieval queries.
4. Use operations/security skills when presenting production readiness.

Completion target:

- The project can claim use of the Agent Skills Repo as part of its development and operational workflow.

## 16. Module 14: Model Runtime and AWS Integration

Purpose: keep the project functional without Bedrock credits while still satisfying the AWS requirement.

Recommended MVP:

- Ollama for local LLM inference.
- Amazon S3 for user-uploaded artifacts, imported logs, generated reports, or demo files.
- Optional AWS Lambda for scheduled check-ins and weekly replanning if time allows.

Ollama usage:

1. Run a small local model such as Llama 3.1, Mistral, Phi, or another demo-friendly model.
2. Send the agent prompt, retrieved CockroachDB memory, and structured user state to the local model.
3. Store model outputs, plan changes, and decisions back into CockroachDB.

Example local model flow:

```text
User check-in
  -> app reads CockroachDB profile and recent memory
  -> app retrieves vector memories
  -> app calls Ollama locally
  -> app validates output with safety/readiness rules
  -> app stores plan and decision log in CockroachDB
```

AWS usage:

1. Use S3 to store optional artifacts such as meal photos, imported CSV logs, generated summaries, or demo screenshots.
2. Store only the S3 object key and extracted structured metadata in CockroachDB.
3. Optionally use Lambda for scheduled jobs, such as daily check-in reminders or weekly plan generation.

Optional extension:

- Use a vision-capable local model or separate image-analysis tool for approximate meal-photo extraction.
- Store extracted meal data in CockroachDB.
- Ask the user to confirm estimates before using them.

Completion target:

- The agent remains functional for judging without paid Bedrock usage.
- At least one AWS service is used, preferably S3 for artifact storage or Lambda for scheduled agent actions.

Judging/deployment note:

- Keep the functional app available throughout judging.
- Put the functional app link only in the submission form's "Additional Info" answers that are visible to judges, to avoid unnecessary outside usage.

## 17. Module 15: Safety and Validity

Purpose: prevent the agent from giving unsafe or unsupported advice.

Safety gates:

- Chest pain, fainting, severe dizziness, or severe shortness of breath.
- Sharp, worsening, or persistent pain.
- Known medical constraints.
- Unsafe rapid weight-loss goals.
- Eating disorder risk.
- Requests for harmful supplement or drug use.

Agent behavior:

- Do not generate intense workouts when safety flags are present.
- Recommend medical or professional guidance when appropriate.
- Keep nutrition advice general and wellness-oriented.
- Mark meal-photo nutrition estimates as approximate.

Completion target:

- The agent can refuse unsafe recommendations and explain the safety reason.

## 18. Suggested Build Order

1. Create CockroachDB schema.
2. Build user identity lookup by name.
3. Build static onboarding.
4. Build goal setup.
5. Build daily check-in storage.
6. Build readiness score.
7. Build first workout plan generation.
8. Build agent decision logging.
9. Build plan repair.
10. Build weekly summary and replanning.
11. Add fitness knowledge snippets.
12. Add embeddings and vector retrieval.
13. Add MCP demo queries.
14. Add Ollama model integration.
15. Add AWS S3 or Lambda integration.
16. Polish demo flow.

## 19. Demo Script

1. Start with a new user named Alex.
2. Collect static profile.
3. Ask Alex for a goal: improve VO2 max while staying lean.
4. Collect today's adaptive memory.
5. Generate Week 1 plan and nutrition targets.
6. Show rows inserted into CockroachDB.
7. Simulate a poor-recovery check-in: low sleep, high soreness, knee pain.
8. Agent checks safety flags before readiness scoring.
9. Agent retrieves a similar prior memory or relevant knowledge snippet.
10. Agent repairs the plan using the current check-in plus retrieved memory.
11. Show the decision log explaining why the plan changed.
12. Run MCP queries that link the decision row back to the triggering check-in and plan.

## 20. MVP Definition

The MVP is complete when:

- Multiple users can be identified by name.
- New users can be registered.
- Static profile memory is saved.
- Daily adaptive memory is saved.
- A targeted weekly workout plan is generated.
- A rough nutrition target is generated.
- At least one check-in can trigger a plan adjustment.
- Agent decisions are logged.
- MCP can inspect stored memory.
- Vector retrieval is included for at least one memory or knowledge use case.
- At least one AWS service is part of the architecture or running demo.

## 21. Future Extensions

- Meal-photo estimation through a local vision model or image-analysis service.
- CSV import from existing fitness apps.
- Calendar-based workout scheduling.
- Multi-goal periodization.
- Progress charts.
- Form analysis through MediaPipe.
- Duplicate-name handling with email or login.
- Production authentication and privacy controls.
