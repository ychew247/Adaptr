# Progressive Program Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release a general-duration fitness program one editable week at a time.

**Architecture:** Pure calendar helpers derive an active week and enforce program boundaries. Hybrid generation persists program metadata and receives an explicit week start; the chat controller recognizes an explicit next-week request.

## Tasks

- [ ] Add failing pure tests for calendar-week alignment, duration boundaries, and next-week release.
- [ ] Persist program metadata on each generated weekly plan and force sessions into that week.
- [ ] Add an explicit next-week request path that only generates within the saved duration.
- [ ] Ensure repairs only operate on the active weekly plan’s unresolved sessions.
- [ ] Include bounded 2–3 exercise variation instruction for each newly released week.
- [ ] Run focused program, repair, UI, and full relevant test suites.
