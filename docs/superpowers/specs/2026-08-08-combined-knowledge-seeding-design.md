# Combined Knowledge Seeding Design

## Goal

Seed both general fitness and sport-specific Markdown knowledge into the existing
CockroachDB vector-memory pipeline with one Module 11 command.

## Data Flow

`python scripts/run_module.py --module 11` reads these two files:

- `docs/fitness-knowledge-snippets.md`
- `docs/sport-specific-knowledge-snippets.md`

Every `## topic` section is parsed through the existing Module 11 parser, upserted
into `fitness_knowledge` by topic, embedded with the configured Ollama embedding
model, and upserted as a global `memory_embeddings` row with
`source_type = 'fitness_knowledge'` and `user_id = NULL`.

At plan generation or repair, the app embeds the current user profile, goal,
check-in, and constraints. CockroachDB vector search retrieves only nearby global
knowledge and the user's relevant personal memories. The retrieved snippets are
included in the Ollama prompt as context. Deterministic safety, injury, equipment,
readiness, and volume rules remain authoritative.

## Behavior

- No second vector table or embedding model is introduced.
- Sport choice is semantic: badminton, futsal, running, sprinting, and basketball
  snippets compete in the same vector retrieval query; hardcoded sport routing is
  not used.
- Re-running Module 11 is idempotent: matching topics update their database row
  and associated global embedding instead of adding duplicates.
- A missing source file stops the command with its normal file-not-found error.

## Verification

- Parser and seeding tests confirm snippets from both files are passed to the
  existing upsert and embedding calls.
- Module 11 command test confirms both default files are used.
- A retrieval test confirms sport-specific snippets can be returned as
  `fitness_knowledge` context for a sport-related query.

