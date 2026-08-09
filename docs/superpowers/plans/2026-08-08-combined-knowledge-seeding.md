# Combined Knowledge Seeding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed both general fitness and sport-specific knowledge into the existing global CockroachDB vector memory with one Module 11 command.

**Architecture:** Add a Module 11 helper that reads and combines a sequence of Markdown files before passing snippets to the existing topic upsert and Ollama embedding write-back path. Update the Module 11 runner to use the two repository docs by default while preserving an optional repeated `--knowledge-file` override for future knowledge packs.

**Tech Stack:** Python, CockroachDB, Ollama embeddings, pytest.

## Global Constraints

- Reuse `fitness_knowledge` and `memory_embeddings`; create no new vector table.
- Use `source_type = 'fitness_knowledge'` and `user_id = NULL` for global context.
- Preserve the existing actual-Ollama-dimension and CockroachDB vector-index checks.
- Do not use hardcoded sport selection; retrieval remains semantic.
- Preserve existing dirty worktree changes.

---

### Task 1: Combined Markdown Loader

**Files:**
- Modify: `src/m11_fitness_knowledge.py`
- Modify: `tests/test_m11_fitness_knowledge.py`

**Interfaces:**
- Consumes: `Iterable[Path]` containing Module 11 formatted Markdown files.
- Produces: `parse_fitness_knowledge_files(paths: Iterable[Path]) -> list[KnowledgeSnippet]`.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_fitness_knowledge_files_combines_general_and_sport_topics(tmp_path):
    general = tmp_path / "general.md"
    sport = tmp_path / "sport.md"
    general.write_text("## recovery\n\nRest supports adaptation.\n", encoding="utf-8")
    sport.write_text("## badminton\n\nUse multidirectional footwork.\n", encoding="utf-8")

    snippets = parse_fitness_knowledge_files([general, sport])

    assert [snippet.topic for snippet in snippets] == ["recovery", "badminton"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_m11_fitness_knowledge.py -q`

Expected: FAIL because `parse_fitness_knowledge_files` does not exist.

- [ ] **Step 3: Implement the helper**

```python
def parse_fitness_knowledge_files(paths: Iterable[Path]) -> list[KnowledgeSnippet]:
    snippets: list[KnowledgeSnippet] = []
    for path in paths:
        snippets.extend(parse_fitness_knowledge_markdown(path.read_text(encoding="utf-8")))
    return snippets
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_m11_fitness_knowledge.py -q`

Expected: PASS.

### Task 2: Module 11 Default Knowledge Packs

**Files:**
- Modify: `scripts/run_module.py`
- Modify: `tests/test_run_module_script.py`
- Modify: `docs/fitness-agent-workflow.md`

**Interfaces:**
- Consumes: `parse_fitness_knowledge_files(paths)`.
- Produces: `python scripts/run_module.py --module 11` reading both default docs.

- [ ] **Step 1: Write the failing test**

```python
def test_module11_defaults_include_general_and_sport_knowledge_files():
    assert DEFAULT_KNOWLEDGE_FILES == [
        "docs/fitness-knowledge-snippets.md",
        "docs/sport-specific-knowledge-snippets.md",
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_run_module_script.py -q`

Expected: FAIL because `DEFAULT_KNOWLEDGE_FILES` does not exist.

- [ ] **Step 3: Implement default selection and documentation**

```python
DEFAULT_KNOWLEDGE_FILES = [
    "docs/fitness-knowledge-snippets.md",
    "docs/sport-specific-knowledge-snippets.md",
]

parser.add_argument("--knowledge-file", action="append", dest="knowledge_files")
knowledge_files = args.knowledge_files or DEFAULT_KNOWLEDGE_FILES
snippets = parse_fitness_knowledge_files(Path(path) for path in knowledge_files)
```

Document both default sources, the semantic retrieval policy, and the repeated override for future knowledge packs.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python -m pytest tests/test_m11_fitness_knowledge.py tests/test_run_module_script.py -q`

Expected: PASS.

### Task 3: Verify the Existing Retrieval Contract

**Files:**
- Test: `tests/test_m7_plan_repair.py`
- Verify: `src/cockroach_memory_embedding_repository.py`

- [ ] **Step 1: Run the sport-knowledge retrieval test**

Run: `python -m pytest tests/test_m7_plan_repair.py -q`

Expected: PASS, confirming Module 7 asks the existing vector repository for `fitness_knowledge` context.

- [ ] **Step 2: Run the complete test suite and whitespace check**

Run: `python -m pytest -q`

Run: `git diff --check`

Expected: no Excel or knowledge-seeding test failure and no whitespace errors. Note unrelated existing renamed-script failures if they persist.

