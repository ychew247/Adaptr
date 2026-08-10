# Project Handoff: Adaptive Fitness Memory Agent

## Project purpose

This is a CockroachDB x AWS hackathon prototype for an adaptive fitness agent. It uses CockroachDB Cloud as persistent memory, Ollama locally for chat and embeddings, CockroachDB vector search for retrieval, and deterministic safety/nutrition guardrails.

The agent is designed to be more than a chatbot: it records a user profile, remembers goals and past check-ins, assesses daily readiness, generates or repairs workout plans, produces nutrition targets, and logs its decisions.

## Main stack

- Python + `psycopg2`
- CockroachDB Cloud / PostgreSQL-compatible SQL
- CockroachDB managed MCP: useful for inspecting the live database during demos
- Ollama:
  - `llama3.2` for text/structured JSON generation
  - `embeddinggemma` for embeddings
- CockroachDB `VECTOR` storage and vector retrieval
- `openpyxl` for workout-plan `.xlsx` export

## Module overview

- M1: Identify a user by name and create/find the user record.
- M2: Collect stable profile data: age, height, weight, experience, equipment, availability, injuries, dietary needs, and activity level.
- M3: Collect a free-form training goal. Ollama extracts structured goal fields and follows up for missing details.
- M4: Collect a free-form adaptive check-in: sleep, stress, energy, soreness/pain, nutrition note, completion status, and constraints.
- M5: Calculate deterministic readiness using baselines, z-scores, penalties, interaction terms, and a pain safety gate.
- M6: Hybrid workout-plan generation: retrieve -> Ollama generate -> deterministic validate -> retry up to two times -> store only a validated plan.
- M7: Plan repair for pain, low readiness, missed sessions, or time constraints. It retrieves similar precedents, validates repairs, and falls back to the prior valid plan after repeated failure.
- M8: Deterministic nutrition targets (BMR, TDEE, calories, protein, hydration, fiber) with Ollama used only for human-readable advice.
- M9: Decision audit trail with taxonomy, idempotency, parent decision chaining, and timeline query.
- M10: Vector-memory architecture: typed sources, personal + shared knowledge retrieval, similarity cutoff, 12-week recency window, exact retrieved IDs, and write-back.
- M11: Fitness and sport knowledge snippets are embedded and retrieved as global knowledge.
- M12: CockroachDB MCP demonstration / database inspection for judges.

## Important architecture patterns

- Hybrid AI + deterministic guardrails: Ollama drafts natural-language/JSON plans, but Python code owns pain safety, equipment restrictions, injury exclusions, volume/intensity limits, readiness, and nutrition math.
- Agentic control loop: M6/M7 use retrieve -> generate -> validate -> regenerate (maximum two retries) -> store. No unvalidated plan is shown to the user.
- RAG/vector memory: `memory_embeddings` stores user memories and global fitness/sport knowledge. Retrieval results are inserted explicitly into M6/M7 Ollama prompts and their IDs are recorded with the plan/decision.
- Persistent audit trail: `agent_decisions` records why the agent generated, repaired, or retained a plan, with optional `parent_decision_id` chaining.

## Connected daily agent flow

The earlier modules can still be run separately for debugging, but M4-M8 are now connected through one controller.

```text
M4 save/upsert daily check-in
  -> M5 compute readiness once
  -> M9 log readiness assessment
  -> deterministic route
       no active plan -> M6 generate validated plan
       pain / lower readiness / missed session / limited time -> M7 repair validated plan
       otherwise -> keep current plan
  -> M8 calculate nutrition targets with the same readiness
  -> M9 log nutrition/plan decisions
  -> return one GUI-ready result object
```

The controller is [src/agent_flow.py](../src/agent_flow.py). It is named `AdaptiveFitnessAgent` and returns a structured result with `checkin`, `readiness`, `action`, `plan`, `nutrition`, and `summary`.

## Main command to test the connected flow

From the repository root, with CockroachDB credentials configured and Ollama running:

```powershell
python scripts/run_module.py --module agent --user yu --workout-today --bmr-formula-profile male
```

This prompts for the adaptive check-in, then runs the connected M4-M8 flow. `--bmr-formula-profile male` or `female` is needed when the user has no previously saved formula profile.

Individual module commands remain available through `scripts/run_module.py --module 1` through `--module 8` for focused debugging.

## Key source files

- `src/agent_flow.py`: connected M4-M8 controller.
- `src/m4_adaptive_checkin.py`: check-in prompting/parsing and persistence.
- `src/m5_readiness_score.py`: deterministic readiness formula and bands.
- `src/m6_hybrid_workout_plan.py`: validated plan-generation loop.
- `src/m7_plan_repair.py`: validated plan-repair loop.
- `src/m8_nutrition_targets.py`: BMR/TDEE/calorie/protein/hydration calculations.
- `src/m8_nutrition_service.py`: stores nutrition target and asks Ollama for explanatory text.
- `src/cockroach_memory_embedding_repository.py`: vector-memory write/search.
- `src/m11_knowledge_ingestion.py` (or equivalent knowledge-ingestion module): embeds fitness/sport knowledge snippets.
- `src/m9_decision_log.py`: decision audit service.
- `scripts/run_module.py`: CLI entry point.
- `scripts/export_workout_plan.py` and `src/workout_plan_excel_export.py`: `.xlsx` export of workout sessions.

## Database data stored so far

- `users`: user identity.
- `user_profiles`: stable profile.
- goal table: structured active goals.
- daily check-in table: changing state and raw note.
- readiness records / decision log: readiness scores and reasoning.
- `workout_plans`: validated generated/repaired plans, validation audit, retrieved memory IDs, attempts, source check-in.
- nutrition targets table: deterministic daily nutrition figures plus Ollama notes.
- `agent_decisions`: auditable action history.
- `memory_embeddings`: personal memories, validated plans/decisions, summaries, and global fitness/sport knowledge.

## Documentation and context sources

- `docs/fitness-agent-workflow.md`: the main implementation workflow and module specifications.
- `docs/fitness-knowledge-snippets.md`: general guardrail-aware fitness knowledge for M11.
- `docs/sport-specific-knowledge-snippets.md`: sport context, such as badminton/futsal, for M11 retrieval.
- `docs/cockroachdb-tools-reference.md`: concise CockroachDB tool reference.
- `about_the_project.md`: architecture/accomplishment write-up for the submission. It may currently be an uncommitted deletion; check `git status` before changing it.

## Recent connected-flow changes

Recent commits on branch `module-9-11`:

- `2f5a079 feat: upsert and return adaptive checkins`
- `bf53af2 feat: share readiness context across agent services`
- `28bc621 feat: add adaptive fitness agent flow`
- `7a294c4 feat: expose complete adaptive agent flow`

## Test status

Focused connected-flow coverage passed:

```text
30 passed
```

The complete suite currently reports:

```text
108 passed, 8 failed
```

The eight failures are not from the new connected flow. Tests still call the old demo filenames such as `scripts/module1_identity_demo.py`, but the workspace has uncommitted deletions/renames to `m1_...` through `m7_...`. Decide whether to update those tests or restore compatibility wrappers before the final submission.

## Current workspace caution

There are user-owned, uncommitted changes related to demo script renaming, Excel export, docs, and `requirements.txt`. Do not use destructive Git commands or revert them. Inspect `git status` before staging or committing future work.

## Remaining work

1. Build the Streamlit GUI that calls `AdaptiveFitnessAgent.run_daily_flow()` instead of individual modules.
2. Add an organized workout-plan screen and button to export only workout sessions to `.xlsx`.
3. Resolve old demo-script test names versus new `m1_...` naming.
4. Run a live CockroachDB + Ollama end-to-end test using a demo user.
5. Push the four connected-flow commits to GitHub when ready.
6. Prepare a short judging demo: query `memory_embeddings`, show `retrieved_memory_ids` in `workout_plans`, then show a plan repair influenced by retrieved memory.

## Suggested first message in the next chat

```text
Read docs/chat-handoff.md and continue from the remaining work. First inspect git status, then help me implement the Streamlit GUI using the existing AdaptiveFitnessAgent flow.
```
