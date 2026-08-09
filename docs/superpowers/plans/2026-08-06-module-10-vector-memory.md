# Module 10 Vector Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing CockroachDB vector-memory repository so Module 6 and 7 retrieve only recent, close personal precedents plus global knowledge.

**Architecture:** Keep `memory_embeddings` as the only vector table and retain the live Ollama dimension preflight. The repository owns source-type validation, safe schema compatibility, cutoff/recency retrieval, and global-memory support. Existing plan and repair writers use canonical source types.

**Tech Stack:** Python, psycopg2, CockroachDB vector indexes, Ollama embeddings, pytest.

## Global Constraints

- Use the existing `memory_embeddings` table; do not create a second vector table.
- Continue deriving `VECTOR(dimension)` from the active Ollama embedding output.
- Allow only `daily_note`, `agent_decision`, `weekly_summary`, `fitness_knowledge`, `goal_description`, and `validated_plan` as source types.
- Personal memory window: 12 weeks.
- Cosine distance cutoff: 0.40.
- Global `fitness_knowledge` rows have `user_id IS NULL` and are not subject to the personal recency filter.

---

### Task 1: Repository source and retrieval policy

**Files:**
- Modify: `src/cockroach_memory_embedding_repository.py`
- Modify: `tests/test_cockroach_memory_embedding_repository.py`

**Interfaces:**
- Produces `MEMORY_SOURCE_TYPES` as the fixed source vocabulary.
- Produces `CockroachMemoryEmbeddingRepository.search_similar(user_id, embedding, limit=5, source_type=None, max_distance=0.40, personal_memory_weeks=12)`.
- Allows `upsert_memory(user_id=None, source_type='fitness_knowledge', ...)`.

- [ ] **Step 1: Write failing tests for invalid source types and filtered retrieval**

```python
with pytest.raises(ValueError, match="Unsupported memory source type"):
    repository.upsert_memory(user_id="user-1", source_type="check_in", ...)

repository.search_similar("user-1", [0.1, 0.2, 0.3])
query, params = cursor.queries[0]
assert "created_at >=" in query
assert "user_id IS NULL" in query
assert "embedding <=> %s::VECTOR < %s" in query
assert params[-2:] == (0.40, 5)
```

- [ ] **Step 2: Run the repository test and confirm it fails**

Run: `python -m pytest tests/test_cockroach_memory_embedding_repository.py -q`

- [ ] **Step 3: Implement canonical validation, compatibility upgrade, and retrieval filters**

```python
MEMORY_SOURCE_TYPES = frozenset({...})

WHERE (
  (user_id = %s AND created_at >= %s)
  OR user_id IS NULL
)
AND embedding <=> %s::VECTOR < %s
ORDER BY embedding <=> %s::VECTOR, created_at DESC
LIMIT %s
```

Call a schema compatibility helper from `ensure_schema()` to make `user_id` nullable for existing tables and normalize legacy source types.

- [ ] **Step 4: Run the repository tests and confirm they pass**

Run: `python -m pytest tests/test_cockroach_memory_embedding_repository.py -q`

### Task 2: Canonical write-back integration

**Files:**
- Modify: `src/m6_hybrid_workout_plan.py`
- Modify: `src/m7_plan_repair.py`
- Modify: `tests/test_hybrid_workout_plan.py`
- Modify: `tests/test_m7_plan_repair.py`

**Interfaces:**
- Consumes validated source types from Task 1.
- Produces `daily_note`, `validated_plan`, and `agent_decision` writes without changing retrieved-memory audit IDs.

- [ ] **Step 1: Write failing assertions for canonical source types**

```python
assert memory_repository.stored[0]["source_type"] == "daily_note"
assert memory_repository.stored[1]["source_type"] == "validated_plan"
assert repair_memory.stored[0]["source_type"] == "agent_decision"
```

- [ ] **Step 2: Run the focused integration tests and confirm they fail**

Run: `python -m pytest tests/test_hybrid_workout_plan.py tests/test_m7_plan_repair.py -q`

- [ ] **Step 3: Change only writer source-type values**

```python
self.memory_repository.upsert_memory(source_type="daily_note", ...)
self.memory_repository.upsert_memory(source_type="validated_plan", ...)
self.memory_repository.upsert_memory(source_type="agent_decision", ...)
```

- [ ] **Step 4: Run focused integration tests and confirm they pass**

Run: `python -m pytest tests/test_hybrid_workout_plan.py tests/test_m7_plan_repair.py -q`

### Task 3: Workflow documentation and end-to-end verification

**Files:**
- Modify: `docs/fitness-agent-workflow.md`
- Test: `tests/test_cockroach_memory_embedding_repository.py`

**Interfaces:**
- Documents that Module 10 upgrades already-built Module 6/7 retrieval.
- Documents live dimensions, existing vector index, cutoff, 12-week policy, global knowledge, write-back, and audit IDs.

- [ ] **Step 1: Update Module 10 workflow text and SQL examples**

```sql
WHERE (user_id = $1 AND created_at >= $2) OR user_id IS NULL
ORDER BY embedding <=> $3, created_at DESC
LIMIT 5;
```

- [ ] **Step 2: Run the full suite**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; C:\Users\hewyu\anaconda3\python.exe -m pytest -q`

