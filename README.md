# Adaptr

Adaptr is a conversational fitness coach that turns natural-language goals and daily check-ins into dated, adaptive workout plans.

## Live Demo

Try the deployed application here:

http://32.236.59.211/

## Features

- Natural-language onboarding, training-goal collection, and daily readiness check-ins.
- Dated weekly plans anchored to the date the user asks, not a fixed Monday start.
- Targeted workout repair for one or several named days/dates without rewriting unaffected sessions.
- Plan viewing in chat, including current-week, next-week, and named-day requests.
- Excel export with private Amazon S3 storage and a short-lived download link.
- Persistent profile, plans, check-ins, and training memory in CockroachDB Cloud.

## Architecture

```text
Browser → Caddy → NiceGUI app → CockroachDB Cloud
                              → Ollama Cloud (chat and generation)
                              → local Ollama (embeddings)
                              → Amazon S3 (Excel exports)
```

## Setup and Run Locally

Prerequisites: Docker Desktop (or Docker Engine + Compose), a CockroachDB Cloud connection string, and an Ollama Cloud API key. Local Ollama is used only for `embeddinggemma`.

```bash
git clone https://github.com/ychew247/CockroachDB
cd adaptr
cp .env.example .env
```

Edit `.env` with your CockroachDB URL, Ollama API key, selected model, and optional S3 bucket. Then start the stack and download the embedding model:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull embeddinggemma
```

Open [http://localhost](http://localhost) (or [http://localhost:8081](http://localhost:8081) when running `python nicegui_app.py` directly).

## Configuration

Required variables in `.env`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | CockroachDB Cloud connection URL. Docker requires `sslrootcert=system`. |
| `OLLAMA_API_KEY` | Ollama Cloud API key. Never commit it. |
| `OLLAMA_MODEL` | Ollama Cloud model used for chat and structured generation. |

Common optional variables:

| Variable | Default / purpose |
| --- | --- |
| `OLLAMA_BASE_URL` | `https://ollama.com` |
| `OLLAMA_EMBED_BASE_URL` | `http://ollama:11434` in Docker |
| `OLLAMA_EMBED_MODEL` | `embeddinggemma` |
| `OLLAMA_TIMEOUT_SECONDS` | `180` |
| `AWS_REGION` | Region of the S3 export bucket |
| `AWS_S3_WORKOUT_PLAN_BUCKET` | Enables private S3-backed Excel exports |
| `AWS_S3_WORKOUT_PLAN_URL_EXPIRY_SECONDS` | Presigned download lifetime; default `900` |

For EC2, attach an IAM role with `s3:PutObject`, `s3:GetObject`, and `s3:GetBucketLocation` for `workout-plans/*`. Do not put AWS access keys in `.env`.

## Testing

Run the automated test suite:

```bash
python -m pytest tests/
```

Quick manual demo:

1. Register with a new name.
2. Use a goal such as: `I am a badminton player who wants to improve smashing power and footwork over 2 months.`
3. Send: `I slept 8 hours, energy 4/5, mild soreness 1/5, no pain, and I plan to train today.`
4. Ask: `show me this week's plan in chat`, then `export my plan as excel`.

The final request should display a **Download workout plan (.xlsx)** button. With S3 enabled, the workbook is stored at `workout-plans/<user-id>/<plan-id>.xlsx` and downloaded through a temporary private link.

## Project Structure

| Path | Purpose |
| --- | --- |
| `src/` | Fitness domain logic, Ollama clients, plan generation/repair, CockroachDB and S3 integrations. |
| `ui/` | NiceGUI chat interface and conversation controller. |
| `tests/` | Automated unit and integration-style tests. |
| `docs/` | Module workflow and implementation notes. |
| `docker-compose.yml` | EC2/local Docker deployment: app, Caddy, and local embedding service. |
