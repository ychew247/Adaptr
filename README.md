# Adaptr — Adaptive Fitness Memory Agent

Adaptr is a conversational fitness coach that builds a dated workout plan, stores long-term training memory, and adapts only the sessions affected by a user’s latest check-in.

It uses:

- **CockroachDB Cloud** for persistent user profiles, goals, check-ins, plans, nutrition targets, audit decisions, and vector-searchable memory.
- **Ollama** for local structured language interpretation and workout/nutrition generation.
- **Amazon S3** (optional locally) to privately store exported Excel workout plans and return short-lived download links.

## What judges can test

- Natural-language onboarding and goal collection.
- Dated workout-plan generation anchored on the day of inquiry.
- Daily readiness and nutrition updates from sleep, energy, soreness, pain, and food signals.
- Targeted repair of one or several requested workout sessions by `Day N` or date, without rewriting the rest of the week.
- Current-week plan viewing in chat.
- Excel export, optionally backed by private S3 storage.

## Prerequisites

- Python 3.10+ (the project is tested with Anaconda Python on Windows).
- A CockroachDB Cloud cluster and connection string.
- [Ollama](https://ollama.com/) running locally.
- Optional: an AWS account, a private S3 bucket, and credentials with `s3:PutObject` and `s3:GetObject` for workbook exports.

## Quick start

Clone the public repository, then open PowerShell in the project directory.

```powershell
python -m pip install -r requirements.txt
ollama pull llama3.2
ollama pull embeddinggemma
```

If Ollama is not already running, start it in another terminal:

```powershell
ollama serve
```

Configure the app. Replace the database value with your CockroachDB Cloud connection string; do not commit it.

```powershell
$env:DATABASE_URL = "postgresql://<user>:<password>@<host>:26257/<database>?sslmode=verify-full"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
$env:OLLAMA_EMBED_MODEL = "embeddinggemma"
$env:NICEGUI_PORT = "8081"
```

Start the app:

```powershell
python nicegui_app.py
```

Open [http://127.0.0.1:8081](http://127.0.0.1:8081). Database migrations are applied automatically when the chat first connects to the database.

Chat history is stored only in this browser. It survives a page refresh, but clearing site data or using another browser starts with no local chat history.

## Manual test script

Use a new name, such as **Judge Badminton Demo**, to create isolated mock data. Enter the following profile answers in the order requested:

| Profile field | Mock input |
| --- | --- |
| Age | `25` |
| Height | `175` |
| Starting weight | `72` |
| Training experience | `intermediate` |
| Equipment | `dumbbells, cable machine, treadmill, badminton court` |
| Weekly availability | `4 days per week, 60 minutes each session` |
| Injury notes | `none` |
| Medical constraints | `none` |
| Diet preferences | `no restrictions` |
| Activity level | `moderately active` |
| BMR formula profile | `male` |

When prompted for a goal, send:

```text
I am a recreational badminton player who wants to improve smashing power, shoulder stability, footwork, and court endurance over 2 months.
```

For the first check-in, send:

```text
I slept 8 hours, energy is 4/5, mild soreness 1/5, no pain, ate normally, and I plan to train today.
```

Expected result: the app stores the check-in, calculates readiness, generates a dated weekly plan, and shows it in chat.

### Test targeted plan repair

After a plan exists, send this single combined status and repair request:

```text
I am having soreness in my shoulder and arm, slept 6 hours, and energy is 3/5. According to my status, repair Day 2 and <the scheduled date shown for Day 3>.
```

Then send:

```text
show me the repaired workout
```

Replace the placeholder with the date displayed for Day 3 in the generated table (for example, `2026-08-20` when the plan starts on `2026-08-16`). Expected result: the assistant confirms the exact sessions updated. Only **Day 2** and the named date are amended; every other session in the week is retained.

### Test plan chat and export

```text
show me this week's plan in chat
```

Expected result: the full current-week plan appears in the conversation without creating an export.

```text
export my plan as excel
```

Expected result: the chat renders a **Download workout plan (.xlsx)** button.

## Optional: enable private Amazon S3 exports

Without S3 settings, Excel files download directly from the local app. To store generated workbooks in a private S3 bucket and serve a temporary download link, set:

```powershell
$env:AWS_S3_WORKOUT_PLAN_BUCKET = "your-private-bucket-name"
$env:AWS_REGION = "ap-southeast-1"
$env:AWS_S3_WORKOUT_PLAN_URL_EXPIRY_SECONDS = "900" # optional; 15 minutes is the default
```

Use normal AWS credentials in the same PowerShell session (for example, an IAM user's access key/secret key environment variables or an AWS profile). The principal needs `s3:PutObject`, `s3:GetObject`, and `s3:GetBucketLocation` for the bucket and its `workout-plans/*` objects.

To verify the export, request `export my plan as excel`, click the chat button, and confirm that the workbook downloads. In the S3 console, look for an object under:

```text
workout-plans/<user-id>/<plan-id>.xlsx
```

The bucket remains private; Adaptr uses server-side encryption and creates a presigned `GetObject` URL only at download time.

## Deploy to an AWS EC2 public IP

The repository includes a Docker deployment for an Ubuntu EC2 instance with at least 8 GiB memory and 30 GiB disk. It runs NiceGUI, Ollama, and a Caddy reverse proxy; only port 80 is exposed publicly.

On EC2, clone the public repository and enter it:

```bash
git clone https://github.com/<your-account>/<your-repository>.git adaptr
cd adaptr
cp .env.example .env
nano .env
```

Set `DATABASE_URL`, `AWS_REGION`, and `AWS_S3_WORKOUT_PLAN_BUCKET` in `.env`. For the Linux Docker container, the URL must include `sslmode=verify-full&sslrootcert=system`. Do not add AWS access keys to this file; attach an EC2 IAM role that grants the app's existing S3 policy instead.

Start the containers and download the required Ollama models:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull embeddinggemma
docker compose ps
```

Open `http://<EC2-public-IP>` in a browser. The EC2 security group needs public inbound TCP port `80`; restrict SSH port `22` to your own IP. The public URL is HTTP while using a raw IP address. Attach an Elastic IP before sharing the final submission link so that the address remains stable across instance restarts.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Database connection error | Confirm `DATABASE_URL` (or `COCKROACH_URL`) is set in the same PowerShell session and that the CockroachDB cluster is reachable. |
| Ollama connection error | Run `ollama serve`, then verify `ollama list` includes `llama3.2` and `embeddinggemma`. |
| The app still shows old behavior after editing code | Stop the server with `Ctrl+C` and restart `python nicegui_app.py`; reload is disabled by default. |
| S3 upload fails with `AccessDenied` | Verify the IAM policy resource matches `arn:aws:s3:::<bucket>/workout-plans/*` and restart the app after changing credentials. |
| No S3 download button | Set `AWS_S3_WORKOUT_PLAN_BUCKET` before launching the app. Without it, local in-browser download remains available. |

## Development documentation

The detailed module-by-module development workflow, schema rationale, and architecture notes are in [docs/fitness-agent-workflow.md](docs/fitness-agent-workflow.md).

## License

Add an MIT or Apache-2.0 `LICENSE` file before public judging so GitHub can identify the repository as open source.
