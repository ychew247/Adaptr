# Adaptive Fitness Memory Agent

An agentic fitness coach for the CockroachDB x AWS Hackathon. The agent identifies each user, builds a durable fitness profile, collects changing daily health signals, and adapts workout and nutrition plans over time using CockroachDB as its persistent memory layer.

## Hackathon Fit

The project is designed around the challenge: build an agentic application that uses CockroachDB as persistent memory and runs on AWS.

CockroachDB tools used:

- CockroachDB Cloud Managed MCP Server for inspecting and operating on stored agent memory.
- CockroachDB Distributed Vector Indexing for semantic retrieval over user memories, check-ins, goals, decisions, and fitness knowledge snippets.
- CockroachDB Agent Skills Repo as a source of database/schema/operations guidance during development.

AWS services planned:

- Amazon S3 for optional uploaded artifacts such as meal photos, progress images, imported fitness logs, generated reports, or demo assets.
- AWS Lambda for optional scheduled check-ins, weekly replanning, and background agent actions.

Model runtime:

- Ollama for local/free LLM reasoning during the hackathon demo.
- Bedrock is intentionally not required because the organizer message notes that it does not have a free tier for participants.

## Core Idea

Most fitness chatbots answer isolated questions. This agent keeps long-term memory.

It remembers who the user is, what their goal is, how their body responds, what plans were created, what they completed, and why the agent changed future workouts. The agent treats health signals such as sleep, soreness, stress, energy, pain, and weight as time-series memory rather than one-off chat messages.

## User Workflow

1. Ask for the user's name.
2. Check whether a profile with that name already exists.
3. If the user exists, load their profile, active goal, recent check-ins, plans, and decision history.
4. If the user is new, create a profile and collect static fitness memory.
5. Ask for the user's current goal.
6. Ask how long the user wants the overall workout plan to run, such as 1 month, 2 months, 3 months, or custom.
7. Collect adaptive memory such as sleep, stress, energy, soreness, weight, pain, workout completion, and nutrition adherence.
8. Generate the first weekly workout block inside the longer duration-aware plan and rough nutrition targets.
9. Store the plan and the agent's reasoning in CockroachDB.
10. On future check-ins, calculate readiness and adjust the plan when needed.
11. At the end of each week, summarize progress and generate the next adaptive plan.

## Memory Types

### Static Memory

Stored once and updated only when needed:

- Name or profile label
- Age
- Height
- Starting weight
- Training experience
- Equipment access
- Availability
- Medical constraints or injuries
- Diet restrictions or preferences
- Current activity level

### Adaptive Memory

Stored as dated check-ins:

- Sleep duration
- Stress level
- Energy level
- Soreness level
- Sore muscle groups
- Pain or injury notes
- Current weight
- Workout completion
- Nutrition adherence
- Free-text notes

## Agentic Features

- User identity and persistent profile loading.
- Daily readiness score based on changing health signals.
- Plan repair when the user misses a workout or reports low recovery.
- Weekly replanning based on trends.
- Nutrition targets adjusted to workout intensity.
- Decision log that records why the agent changed a plan.
- Semantic memory retrieval for prior patterns and similar past situations.
- Safety gate for injury, pain, medical constraints, and unsafe diet requests.

## Example Agent Behavior

User check-in:

> Slept 5 hours, high leg soreness, stressed, knee pain after squats.

Agent action:

> Reduce lower-body intensity today, replace heavy squats with low-impact accessories, move conditioning later in the week, and store the decision reason.

Stored decision:

```json
{
  "decision_type": "workout_adjustment",
  "reason": "High leg soreness, knee pain, and sleep below 6 hours",
  "data_used": ["last_3_checkins", "current_goal", "active_weekly_plan"],
  "plan_change": "Reduced lower-body intensity and moved conditioning"
}
```

## Suggested Data Model

- `users`
- `user_profiles`
- `goals`
- `daily_checkins`
- `workout_plans`
- `nutrition_targets`
- `agent_decisions`
- `memory_embeddings`
- `fitness_knowledge`

## Differentiation

The project is not a generic fitness chatbot. It is a persistent-memory fitness agent that:

- Works without wearables.
- Uses lightweight check-ins as durable time-series memory.
- Explains every meaningful plan change.
- Uses CockroachDB for identity, memory, vector search, and auditability.
- Uses AWS services for optional artifact storage, scheduled jobs, and demo deployment support.

## Detailed Workflow

See [docs/fitness-agent-workflow.md](docs/fitness-agent-workflow.md) for the module-by-module build plan.

## Module 1: User Identity

Module 1 implements name-based user identity:

- Ask for the user's profile name.
- Normalize the name for lookup.
- Load the existing user if found.
- Create a new user if not found.
- Route new users to static onboarding and returning users to adaptive check-in.

Run the database-backed demo after setting `DATABASE_URL`:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
python scripts/module1_identity_demo.py
```

The script applies `sql/001_create_users.sql` before running the identity flow.

## Module 2: Static Profile

Module 2 implements static fitness profile onboarding:

- Load or create the user by name.
- Skip static onboarding if the profile already exists.
- Collect stable profile fields such as age, height, starting weight, training experience, equipment, availability, injuries, medical constraints, diet preferences, and activity level.
- Save the profile in CockroachDB.
- Route the user to goal setup.

Run the database-backed demo after setting `DATABASE_URL`:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
python scripts/module2_static_profile_demo.py
```

The script applies `sql/001_create_users.sql` and `sql/002_create_user_profiles.sql` before running the identity and static-profile flows.

## Module 3: Training Goal

Module 3 uses one free-form goal prompt instead of one question per field:

```text
What is your training target?
```

The user can answer naturally, for example:

```text
I am a futsal athlete and want stronger hamstrings and calves, better VO2 max, and to stay lean over 3 months.
```

The default demo deterministically parses:

- Athlete or trainee type
- Target muscle groups
- Desired outcomes
- Plan duration
- Raw goal text

Run the database-backed demo:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
python scripts/module3_goal_setup_demo.py
```

The script applies `sql/001_create_users.sql`, `sql/002_create_user_profiles.sql`, and `sql/003_create_goals.sql` before running identity, static profile, and goal setup.

Run the Ollama-backed demo from Module 1 through Module 3:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
python scripts/module3_goal_setup_ollama_demo.py
```

This still uses structured prompts for identity and static health stats, then uses Ollama to extract the free-form training goal into JSON before saving it to CockroachDB.

## Ollama Setup

Ollama is used as the local/free model runtime.

Recommended local models:

```powershell
ollama pull llama3.2
ollama pull embeddinggemma
```

Optional app config:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
$env:OLLAMA_EMBED_MODEL = "embeddinggemma"
```

Test the app's Ollama integration:

```powershell
python scripts/test_ollama_connection.py
```

Expected result:

- Chat API returns structured JSON.
- Embedding API returns a numeric vector.

## Demo User

Seed a stable demo user named `Alex` through Module 2:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
python scripts/seed_demo_user.py
```

The seed script creates or updates:

- User: `Alex`
- Age: `25`
- Height: `175 cm`
- Starting weight: `72 kg`
- Training experience: `intermediate`
- Equipment: `full gym`, `treadmill`
- Availability: `4 days/week, 60 minutes each, Mon/Tue/Thu/Sat evenings`
- Injury note: `mild knee discomfort after heavy squats`
- Diet preference: `high protein, no strict restrictions`
- Activity level: `lightly active`

View saved Module 1 and Module 2 data without opening the CockroachDB SQL shell:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
python scripts/show_demo_data.py
```

## Module 4: Adaptive Check-In

Module 4 starts the reusable loop after registration and goal setup:

- Load or create the user by name.
- Skip static profile and goal setup when they already exist.
- Ask one lightweight body/nutrition check-in prompt.
- Let the user answer freely instead of filling a strict form.
- Use Ollama to extract sleep, stress, energy, soreness, pain, workout completion, and nutrition adherence.
- Save the check-in as time-series memory in CockroachDB.

Run the Ollama-backed demo from Module 1 through Module 4:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
python scripts/module4_adaptive_checkin_demo.py
```

Example check-in answer:

```text
Slept 6 hours, shoulders still sore, energy 3, no sharp pain, completed yesterday's workout, protein was okay but hydration was low.
```

View saved check-ins:

```powershell
python scripts/show_demo_data.py
```

## Direct Module Testing

Use `scripts/run_module.py` when you want to jump to a module without replaying the full Module 1 onward flow.

Set your connection once:

```powershell
$env:DATABASE_URL = "your-cockroachdb-connection-string"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
```

Run only Module 2 for a named user:

```powershell
python scripts/run_module.py --module 2 --user Alex
```

Run Module 3 directly. If the static profile is missing, Module 2 runs first:

```powershell
python scripts/run_module.py --module 3 --user Alex
```

Run Module 4 directly. If static profile or active goal is missing, the runner fills those prerequisites first:

```powershell
python scripts/run_module.py --module 4 --user Alex
```

Run Module 5 directly. If no check-in exists, the runner asks for a Module 4 check-in first:

```powershell
python scripts/run_module.py --module 5 --user Alex
```

Run Module 6 directly to generate and save an Ollama-backed Week 1 workout plan:

```powershell
python scripts/run_module.py --module 6 --user Alex
```

For deterministic debugging without Ollama plan generation:

```powershell
python scripts/run_module.py --module 6 --user Alex --deterministic-plan
```

For a stable demo profile before testing later modules:

```powershell
python scripts/run_module.py --module 6 --seed-demo-profile
```

You can also compute readiness from the latest saved check-in:

```powershell
python scripts/module5_readiness_demo.py --user Alex
```

Or generate an Ollama-backed plan from the latest saved profile, goal, and check-in:

```powershell
python scripts/module6_workout_plan_demo.py --user Alex
```
