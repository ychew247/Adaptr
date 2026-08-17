# Ollama Cloud Integration: Module Map

Use this document for Adaptr's hybrid Ollama deployment: direct Ollama Cloud
API access for chat/generation and a local Ollama container for embeddings.

## Integration Status

The first integration must preserve the current application interfaces:

- `OllamaClient.chat_json_instruction(...)`
- `OllamaClient.embed(...)`
- Existing parser and generator classes that depend on those methods

The direct Cloud chat API base URL is `https://ollama.com`. The client appends
`/api/chat`, so do not configure the chat base URL as `https://ollama.com/api`.

Required environment variables:

```env
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=<secret; never commit>
OLLAMA_MODEL=<remote-chat-model>
OLLAMA_EMBED_BASE_URL=http://ollama:11434
OLLAMA_EMBED_MODEL=embeddinggemma
OLLAMA_TIMEOUT_SECONDS=180
```

## Modules To Change

### 1. API connection and authentication

**File:** `src/ollama_client.py`

Required changes:

- Read `OLLAMA_API_KEY` from the environment.
- Send `Authorization: Bearer <API key>` for direct Cloud chat requests.
- Detect direct remote mode from `OLLAMA_BASE_URL`.
- Do not send native `format: "json"` in direct Cloud mode.
- Retain the current timeout configuration.
- Send embedding requests to `OLLAMA_EMBED_BASE_URL`, without the Cloud API
  key unless `OLLAMA_EMBED_API_KEY` is explicitly configured.

Reason: direct Ollama Cloud requests require bearer authentication. The native
Cloud endpoint does not support structured outputs through `format: "json"`.

### 2. Semantic chat routing JSON handling

**File:** `src/ollama_chat_language.py`

Required changes:

- Keep the existing malformed/invalid JSON retry for daily routing.
- Make JSON decoding accept Markdown code fences, because Cloud models may
  return JSON as a fenced block even when instructed to return JSON only.

### 3. Plan presentation JSON handling

**File:** `src/ollama_plan_presentation.py`

Required changes:

- Replace direct `json.loads(...)` calls with code-fence-tolerant decoding.
- Cover the correction/retry response as well as the first response.

### 4. Nutrition note JSON handling

**File:** `src/ollama_nutrition_note_generator.py`

Required changes:

- Replace direct `json.loads(...)` with code-fence-tolerant decoding.

## Modules Already Prepared for Fenced JSON

These modules already strip code fences before decoding. Test them against the
real Cloud model, but no structural change is expected initially.

- `src/ollama_checkin_parser.py`
- `src/ollama_goal_parser.py`
- `src/ollama_workout_plan_generator.py`
- `src/ollama_plan_repair_generator.py`
- `src/ollama_repair_target_parser.py`

## Deployment and Documentation

### Docker deployment

**File:** `docker-compose.yml`

For the hybrid deployment:

- Do not hard-code `OLLAMA_BASE_URL=http://ollama:11434`; it comes from `.env`
  and points to `https://ollama.com`.
- Keep the local `ollama` service, its `depends_on` reference, and the
  `ollama_models` volume.
- Set only `OLLAMA_EMBED_BASE_URL=http://ollama:11434` in the app container.

This keeps the existing CockroachDB embedding dimension and avoids the remote
`/api/embed` authorization failure observed with the configured Cloud key.

### Example configuration and setup guide

**Files:** `.env.example`, `README.md`

Document the remote base URL, non-secret environment-variable names, selected
model, embedding model, and timeout. Never commit `.env` or an API key.

## Test Modules To Update

- `tests/test_ollama_client.py`
  - bearer header for chat and embeddings
  - remote mode omits `format: "json"`
  - local mode retains `format: "json"`
- `tests/test_ollama_chat_language.py`
  - fenced JSON is accepted
  - invalid remote responses retry once
- `tests/test_ollama_plan_presentation.py`
  - fenced presentation JSON is accepted
- `tests/test_ollama_nutrition_note_generator.py`
  - fenced nutrition JSON is accepted

## Database and Embeddings

No CockroachDB schema change is required because the local embedding model
remains `embeddinggemma` at the existing 768 dimensions. Changing the local
embedding model or its dimensions requires re-indexing stored embeddings.

## Sources

- <https://docs.ollama.com/api/authentication>
- <https://docs.ollama.com/api/introduction>
- <https://docs.ollama.com/capabilities/structured-outputs>
- <https://docs.ollama.com/api/embed>
