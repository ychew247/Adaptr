# Judge-Focused README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the module-oriented README with a runnable, judge-focused setup and manual test guide.

**Architecture:** Keep the README as the concise entry point and retain module history only through a link to the existing workflow document.

**Tech Stack:** Markdown, Python, NiceGUI, CockroachDB Cloud, Ollama, Amazon S3.

## Global Constraints

- Never publish real database URLs, access keys, or bucket names.
- Keep AWS S3 optional for local app testing.
- Use PowerShell commands and the configured default Ollama models.

---

### Task 1: Replace README content with the judge journey

**Files:**
- Modify: `README.md`

**Interfaces:** Documents `requirements.txt`, `nicegui_app.py`, `src/fitness_agent_runtime.py`, `src/ollama_client.py`, and optional S3 export settings.

- [ ] Write the README title, architecture, prerequisites, setup environment variables, browser startup, manual test scripts and expected results, S3 verification, troubleshooting, and detailed-workflow link.
- [ ] Verify every referenced command, environment variable, model name, port, and fallback behavior against source files.
- [ ] Commit only the README once verified.

