# CockroachDB Hackathon Tools Reference

Concise reference for the CockroachDB tools mentioned in the hackathon brief, with setup notes, common usage, and how each can fit the Adaptive Fitness Memory Agent.

Last checked: 2026-08-01.

## Required Integration Note

The hackathon requires at least two CockroachDB tools. Recommended pair for this project:

1. **CockroachDB Cloud Managed MCP Server**: use during development/demo to inspect databases, tables, schema, running queries, and stored agent memory.
2. **CockroachDB Distributed Vector Search**: use in the app for semantic memory retrieval over check-ins, decision logs, goals, and fitness knowledge snippets.

Strong optional additions:

- **LangChain x CockroachDB** for chat history, vector store, or agent checkpointing.
- **CockroachDB Agent Skills Repo** for schema, performance, operations, and safety guidance.
- **ccloud CLI** for terminal-based Cloud cluster management and connection info.

## 1. ccloud CLI

Official docs: https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started

### What It Is

`ccloud` is CockroachDB Cloud's command-line interface. It lets developers and agents create, manage, inspect, and connect to CockroachDB Cloud clusters from the terminal.

Use it for infrastructure/admin workflows, not as the main application database driver.

### Setup

Windows PowerShell install command from the docs:

```powershell
$ErrorActionPreference = "Stop"; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; $null = New-Item -Type Directory -Force $env:appdata/ccloud; Invoke-WebRequest -Uri https://binaries.cockroachdb.com/ccloud/ccloud_windows-amd64_0.6.12.zip -OutFile ccloud.zip; Expand-Archive -Force -Path ccloud.zip; Copy-Item -Force ccloud/ccloud.exe -Destination $env:appdata/ccloud; $Env:PATH += ";$env:appdata/ccloud";
```

The docs recommend adding `;$env:appdata/ccloud` to the system `Path` so `ccloud` is available in future terminals.

### Login

```bash
ccloud auth login
```

If the machine has no browser:

```bash
ccloud auth login --no-redirect
```

If you belong to multiple organizations:

```bash
ccloud auth login --org {organization-label}
```

### Common Commands

```bash
ccloud quickstart
ccloud cluster list
ccloud cluster info {cluster-name}
ccloud cluster sql {cluster-name}
ccloud cluster sql --connection-url {cluster-name}
ccloud cluster database list {cluster-name}
ccloud cluster database create {cluster-name} {database-name}
ccloud cluster user create {cluster-name} {username}
ccloud audit list
```

### Usage In This Agent

Use `ccloud` to:

- Confirm the cluster exists.
- Retrieve connection URLs.
- Create SQL users for the app.
- List databases during setup.
- Show audit logs or operations readiness in the demo.

Possible demo line:

> The agent stores memory in CockroachDB; `ccloud` gives the operator an agent-friendly CLI for cluster and database management.

## 2. CockroachDB Cloud Managed MCP Server

Official overview: https://www.cockroachlabs.com/docs/v26.2/cockroachdb-and-ai

### What It Is

The Managed MCP Server exposes CockroachDB Cloud cluster tools to MCP-compatible AI clients. It lets an AI assistant inspect and query clusters through tool calls.

Typical capabilities include:

- List clusters.
- List databases.
- List tables.
- Inspect table schemas.
- Show running queries.
- Run read-only SQL queries.
- Explain queries.
- Optionally create databases/tables if write tools are enabled.

### Setup

In CockroachDB Cloud Console, open the MCP setup/config snippet for the target cluster and add it to your MCP-compatible client.

Endpoint from the hackathon brief:

```text
https://cockroachlabs.cloud/mcp
```

### Common Usage Prompts

```text
List all databases in my CockroachDB cluster.
```

```text
List all tables in the fitness_agent database.
```

```text
Show the schema for the daily_checkins table.
```

```text
Run a SELECT query showing the latest 10 agent decisions.
```

### Usage In This Agent

Use MCP for development and demo visibility:

- Show `users`, `daily_checkins`, `workout_plans`, and `agent_decisions`.
- Prove that memory is persisted after conversation turns.
- Inspect query plans for retrieval queries.
- Let the AI coding assistant directly validate database state.

Suggested demo query:

```sql
SELECT decision_type, reason, created_at
FROM agent_decisions
ORDER BY created_at DESC
LIMIT 10;
```

## 3. CockroachDB Agent Skills Repo

GitHub: https://github.com/cockroachlabs/cockroachdb-skills

Official docs: https://www.cockroachlabs.com/docs/v26.2/agent-skills

### What It Is

The Agent Skills Repo is a public collection of machine-executable CockroachDB skills. Skills encode operational expertise with defined inputs, outputs, safety guardrails, and links to official docs.

Skill domains include:

- Onboarding and migrations
- Application development
- Performance and scaling
- Operations and lifecycle
- Resilience and disaster recovery
- Observability and diagnostics
- Security and governance
- Integrations and ecosystem
- Cost and usage management

### Setup

Quick install from the repository README:

```bash
npx skills add cockroachlabs/cockroachdb-skills
```

### Common Usage

Use skills to guide tasks such as:

- Schema design review.
- Query performance checks.
- Production readiness checks.
- Backup and disaster recovery review.
- Security and privilege audits.
- Observability and diagnostics.

Example natural-language prompts after installing skills:

```text
Use CockroachDB skills to review my schema for an agent memory workload.
```

```text
Use CockroachDB skills to check whether my vector search table design is production-ready.
```

### Usage In This Agent

Use the skills repo as a development/operations tool:

- Validate the CockroachDB schema for agent memory.
- Review indexes for `daily_checkins`, `agent_decisions`, and vector memory.
- Check security posture before demo.
- Support the hackathon claim that the project uses CockroachDB's agent-ready skills ecosystem.

## 4. pgvector + CockroachDB Distributed Vector Search

Official overview: https://www.cockroachlabs.com/docs/v26.2/cockroachdb-and-ai

### What It Is

CockroachDB supports AI workloads by storing fixed-length embeddings with the `VECTOR` type and querying them with similarity operators.

Common similarity operators:

- `<->` for L2 distance.
- `<#>` for inner product.
- `<=>` for cosine distance.

CockroachDB also supports distributed vector indexing through C-SPANN indexes, which are designed for scalable similarity search.

### Common Schema Pattern

```sql
CREATE TABLE memory_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  source_type STRING NOT NULL,
  source_id UUID,
  content STRING NOT NULL,
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example semantic retrieval:

```sql
SELECT content, source_type, created_at
FROM memory_embeddings
WHERE user_id = $1
ORDER BY embedding <-> $2
LIMIT 5;
```

### Usage In This Agent

Use vector search for long-term agent memory:

- Retrieve prior check-ins similar to the user's current state.
- Find previous notes mentioning soreness, knee pain, missed workouts, or low sleep.
- Retrieve past decision reasons before changing a new plan.
- Retrieve trusted fitness knowledge snippets before generating advice.

Example:

> User reports high leg soreness and knee pain. The agent embeds that state, retrieves similar past memories, sees that squats previously caused knee pain, and adjusts today's workout.

### Why It Matters

This is the strongest CockroachDB feature for your project because it makes memory useful. The agent is not just storing rows; it can retrieve semantically relevant past context and combine it with structured user data.

## 5. LangChain x CockroachDB

Provider docs: https://docs.langchain.com/oss/python/integrations/providers/cockroachdb

Chat history docs: https://docs.langchain.com/oss/python/integrations/chat_message_histories/cockroachdb

### What It Is

LangChain provides CockroachDB integrations for LLM applications. The `langchain-cockroachdb` package supports:

- CockroachDB vector store.
- CockroachDB chat message history.
- LangGraph checkpointer.
- Multi-tenancy patterns.
- Row-level TTL features.
- Metadata filtering and performance optimizations.

### Setup

```bash
pip install langchain-cockroachdb
```

Connection string shape:

```text
cockroachdb://user:password@host:26257/database?sslmode=verify-full
```

### Vector Store Usage

```python
from langchain_cockroachdb import AsyncCockroachDBVectorStore, CockroachDBEngine
from langchain_openai import OpenAIEmbeddings

engine = CockroachDBEngine.from_connection_string(
    "cockroachdb://user:pass@host:26257/db?sslmode=verify-full"
)

await engine.ainit_vectorstore_table(
    table_name="documents",
    vector_dimension=1536,
)

vector_store = AsyncCockroachDBVectorStore(
    engine=engine,
    embeddings=OpenAIEmbeddings(),
    collection_name="documents",
)
```

### Chat Message History Usage

```python
from langchain_cockroachdb import CockroachDBChatMessageHistory

chat_history = CockroachDBChatMessageHistory(
    session_id="user-session-id",
    connection_string=CONNECTION_STRING,
    table_name="chat_history",
)
```

Common operations:

```python
await chat_history.aadd_message(...)
messages = await chat_history.aget_messages()
await chat_history.aclear()
```

### Usage In This Agent

Use LangChain if the agent is built in Python:

- Store conversation history in CockroachDB.
- Store and query vector memories through LangChain abstractions.
- Use LangGraph checkpointing if the agent has multi-step workflows such as onboarding, daily check-in, plan generation, and weekly replanning.

Good project fit:

> LangChain handles the agent framework; CockroachDB stores durable chat history, profile memory, vector memory, and workflow checkpoints.

## Recommended Tool Combination For MVP

Minimum strong integration:

1. **Managed MCP Server**: demo and inspect CockroachDB memory through AI tools.
2. **Distributed Vector Search**: app feature for semantic fitness memory retrieval.

Better full story:

1. **Managed MCP Server** for agent/database inspection.
2. **Distributed Vector Search** for semantic user memory.
3. **LangChain x CockroachDB** for chat history and vector store integration.
4. **Agent Skills Repo** for schema/performance/security review.
5. **ccloud CLI** for cluster setup and connection operations.

## Source Links

- ccloud CLI get started: https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-get-started
- ccloud CLI command reference: https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-reference
- CockroachDB and AI: https://www.cockroachlabs.com/docs/v26.2/cockroachdb-and-ai
- Agent Skills docs: https://www.cockroachlabs.com/docs/v26.2/agent-skills
- Agent Skills GitHub repo: https://github.com/cockroachlabs/cockroachdb-skills
- LangChain CockroachDB provider: https://docs.langchain.com/oss/python/integrations/providers/cockroachdb
- LangChain CockroachDB chat history: https://docs.langchain.com/oss/python/integrations/chat_message_histories/cockroachdb
