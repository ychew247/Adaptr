# Module 11 Fitness Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed curated fitness knowledge into CockroachDB and vector memory so Modules 6 and 7 can retrieve it as global context.

**Architecture:** Store canonical snippets in `docs/fitness-knowledge-snippets.md`, parse them into `KnowledgeSnippet` objects, upsert them into `fitness_knowledge`, and write one global `memory_embeddings` row per snippet with `source_type='fitness_knowledge'` and `user_id=None`. Existing hard validators remain authoritative.

**Tech Stack:** Python, psycopg2, CockroachDB JSON/UUID tables, Ollama embeddings, pytest.

## Global Constraints

- Reuse `memory_embeddings`; do not create another vector memory table.
- Global knowledge rows use `user_id IS NULL` and `source_type='fitness_knowledge'`.
- Fitness knowledge guides Ollama but cannot override deterministic guardrails or validators.
- Use TDD for new behavior.

---

### Task 1: Knowledge Parser And Seeder

**Files:**
- Create: `src/m11_fitness_knowledge.py`
- Test: `tests/test_m11_fitness_knowledge.py`
- Modify: `docs/fitness-knowledge-snippets.md`

**Interfaces:**
- Produces: `parse_fitness_knowledge_markdown(markdown_text: str) -> list[KnowledgeSnippet]`
- Produces: `seed_fitness_knowledge(snippets, knowledge_repository, memory_repository, embedder) -> dict[str, int]`

- [ ] Write tests proving snippets parse from Markdown and the joint pain wording matches current hard pain flags.
- [ ] Run the new test and confirm it fails because the parser does not exist.
- [ ] Implement parser and seed function.
- [ ] Run the new test and confirm it passes.

### Task 2: Cockroach Fitness Knowledge Repository

**Files:**
- Create: `src/cockroach_fitness_knowledge_repository.py`
- Create: `sql/011_create_fitness_knowledge.sql`
- Test: `tests/test_cockroach_fitness_knowledge_repository.py`

**Interfaces:**
- Produces: `CockroachFitnessKnowledgeRepository.upsert_snippet(snippet) -> dict`

- [ ] Write tests proving `upsert_snippet` upserts by topic and returns the stored row.
- [ ] Run the repository test and confirm it fails because the repository does not exist.
- [ ] Implement the repository and migration.
- [ ] Run the repository test and confirm it passes.

### Task 3: CLI Integration And Retrieval

**Files:**
- Modify: `scripts/run_module.py`
- Modify: `src/m7_plan_repair.py`
- Modify: `docs/fitness-agent-workflow.md`
- Test: `tests/test_run_module_script.py`
- Test: `tests/test_m7_plan_repair.py`

**Interfaces:**
- Consumes: `seed_fitness_knowledge(...)`
- Produces: `python scripts/run_module.py --module 11`

- [ ] Write tests proving `--module 11 --skip-live` imports and Module 7 asks for both repair decisions and global knowledge.
- [ ] Run the tests and confirm they fail for the missing module choice / retrieval behavior.
- [ ] Wire Module 11 into the CLI and add global knowledge retrieval to Module 7 repair.
- [ ] Run focused tests and full pytest.

