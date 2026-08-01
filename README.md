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
6. Collect adaptive memory such as sleep, stress, energy, soreness, weight, pain, workout completion, and nutrition adherence.
7. Generate the first weekly workout plan and rough nutrition targets.
8. Store the plan and the agent's reasoning in CockroachDB.
9. On future check-ins, calculate readiness and adjust the plan when needed.
10. At the end of each week, summarize progress and generate the next adaptive plan.

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
