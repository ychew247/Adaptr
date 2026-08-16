# Judge-Focused README Design

## Goal

Make the repository front page sufficient for a judge to install, configure, run, and manually test Adaptr without reading the module-development history.

## Content

- State the product purpose and the CockroachDB persistent-memory and Amazon S3 workbook-storage roles.
- List Python, CockroachDB Cloud, and Ollama prerequisites, with `llama3.2` and `embeddinggemma` pull commands.
- Provide copy-paste PowerShell environment setup using `DATABASE_URL` or `COCKROACH_URL`, model settings, and the NiceGUI port.
- Explain optional private-S3 configuration separately, including the local browser-download fallback when no bucket is configured.
- Provide a browser start command and URL.
- Include realistic, ordered mock inputs for onboarding, a standard check-in, targeted multi-session repair, plan viewing, and Excel export, with expected outcomes.
- Include a short S3 verification procedure and troubleshooting for database, Ollama, and S3 credential failures.
- Link to `docs/fitness-agent-workflow.md` for development/module documentation instead of retaining module-by-module steps in the README.

## Constraints

- Do not include connection strings, access keys, or bucket names that could be mistaken for real credentials.
- Keep the primary path runnable without AWS S3.
- Use PowerShell examples because the project is developed and judged from Windows.

