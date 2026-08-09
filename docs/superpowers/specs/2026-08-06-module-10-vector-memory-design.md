# Module 10 Vector Memory Design

## Goal

Refine the existing `memory_embeddings` pipeline so retrieval supplies only relevant recent personal precedents plus shared fitness knowledge to Modules 6 and 7. This is an upgrade of functionality already introduced by those modules, not a new vector-memory table.

## Existing Foundations

- `verify_embedding_dimension()` probes the active Ollama embedding model before `memory_embeddings` is created or used.
- The repository creates `VECTOR(dimension)` from that observed result, so it does not assume OpenAI's 1536 dimensions.
- The table already has a CockroachDB cosine `VECTOR INDEX` scoped by user and embedding.
- Module 6 writes check-in and validated-plan memory; Module 7 writes validated repair memory.

## Source Types

The repository will validate these application-level source types before a write:

- `daily_note`
- `agent_decision`
- `weekly_summary`
- `fitness_knowledge`
- `goal_description`
- `validated_plan`

Current writers will use `daily_note`, `validated_plan`, and `agent_decision`. The enum prevents silent query misses caused by spelling variants. The existing source-type strings are normalized during schema preparation so old rows remain retrievable.

## Retrieval Policy

`search_similar()` will accept a maximum cosine distance and a personal-memory recency window.

- Personal rows: only rows belonging to the user and created within the last 12 weeks.
- Shared rows: rows with `user_id IS NULL`; intended for `fitness_knowledge`; not subject to the personal recency window.
- Distance cutoff: `0.40` cosine distance. Rows farther away are omitted rather than injected as misleading precedent.
- Ranking: nearest cosine distance first, then newest `created_at` as a deterministic tiebreaker.
- No matching rows: return an empty list. Module 6/7 prompts receive no precedent section rather than irrelevant text.

This 12-week filter is the MVP recency policy. It is intentionally simpler and easier to explain than a mixed distance/time score.

## Schema Behavior

`memory_embeddings.user_id` becomes nullable so shared fitness knowledge can be stored in the same table. User-specific source rows still require a user ID at the repository boundary. The existing runtime schema preparation applies this compatibility upgrade when a table already exists.

The existing vector index remains the current production-relevant index. The documentation will state that a larger deployment should tune or add indexes for global knowledge and benchmark the chosen cutoff.

## Write-Back and Auditability

- After a validated Module 6 plan, write `validated_plan` memory.
- After a successful Module 7 repair, write `agent_decision` memory linked to the repair decision ID.
- Store exact retrieved memory IDs in `workout_plans.retrieved_memory_ids` and `agent_decisions.retrieved_memory_ids`.
- Weekly summaries and fitness-knowledge records will use the same repository when their corresponding modules are implemented.

## Tests and Completion Criteria

- Verify source-type validation rejects invalid values before SQL execution.
- Verify search queries include a 12-week personal-memory filter, shared-knowledge branch, cosine cutoff, and deterministic recency tiebreaker.
- Verify empty retrieval is allowed and does not manufacture a precedent.
- Verify existing Module 6/7 writers use canonical source types and preserve retrieved IDs in their audits.
- Update the workflow to describe the existing vector implementation, its cutoff/recency policy, global knowledge scope, write-back, and vector-index production note.

