# Adaptive Fitness Memory Agent Workflow

This document breaks the project into modules so the hackathon build can be completed in manageable pieces. The goal is to demonstrate an agent that stores, retrieves, and acts on persistent fitness memory using CockroachDB and AWS.

## 1. Product Goal

Build an adaptive fitness agent that:

- Identifies each user by name.
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
2. App searches `users` by normalized name.
3. If the user exists, load their memory.
4. If the user does not exist, create a new user row.
5. Continue to static onboarding for new users or daily check-in for returning users.

MVP table:

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name STRING NOT NULL,
  normalized_name STRING NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The agent can distinguish between users such as "Alex" and "Sam".
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
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

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

Example rule set:

```text
Start at 100.
Subtract 20 if sleep average over last 2 days is below 6 hours.
Subtract 15 if stress is high.
Subtract 15 if energy is low.
Subtract 20 if soreness is high.
Subtract 30 and trigger safety handling if pain notes mention sharp or worsening pain.
```

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

MVP table:

```sql
CREATE TABLE workout_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  goal_id UUID REFERENCES goals(id),
  week_start DATE NOT NULL,
  plan_json JSONB NOT NULL,
  status STRING NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

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

Example:

```text
User: I missed Push Day.
Agent: I moved Push Day to Thursday, shortened Friday's session, and kept total weekly chest volume within range.
```

Completion target:

- A missed workout changes the stored plan instead of only receiving encouragement.

## 10. Module 8: Nutrition Targets

Purpose: support training without overbuilding a full diet app.

MVP nutrition output:

- Estimated calorie range
- Protein target
- Hydration target
- Fiber/fruit/vegetable goal
- Pre-workout or post-workout suggestion based on workout intensity

Workflow:

1. Calculate baseline nutrition target from static profile and goal.
2. Adjust daily recommendation based on planned workout intensity.
3. Store the daily nutrition target.
4. Ask for adherence in the next check-in.

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
  decision_type STRING NOT NULL,
  reason STRING NOT NULL,
  data_used JSONB,
  plan_change JSONB,
  safety_flags STRING[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Completion target:

- The demo can show a timeline of agent decisions for a user.

## 12. Module 10: Vector Memory and Retrieval

Purpose: let the agent retrieve relevant past context semantically.

Use cases:

- Find similar past weeks where the user had low sleep and high soreness.
- Retrieve old notes mentioning knee pain, fatigue, or missed workouts.
- Retrieve relevant fitness knowledge snippets before generating advice.
- Compare current user state to prior successful weeks.

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

Example demo query:

```sql
SELECT decision_type, reason, created_at
FROM agent_decisions
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 10;
```

Completion target:

- Judges can see that the agent's memory is really stored in CockroachDB.

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
8. Agent repairs the plan.
9. Show the decision log explaining why the plan changed.
10. Show vector retrieval finding a similar prior memory or relevant knowledge snippet.
11. Run MCP queries to inspect the stored data.

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
