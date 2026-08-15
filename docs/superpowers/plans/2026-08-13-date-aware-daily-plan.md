# Date-Aware Daily Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show only dated, unresolved current-week workouts after each daily check-in.

**Architecture:** Add pure scheduling helpers for date assignment, legacy-plan normalization, session lookup, and remaining-session presentation. Integrate them with generated/repair plans and controller conversation state; Ollama words clarification questions and returns explicit prescriptions.

## Tasks

- [ ] Write failing tests for persisted generated dates, remaining-session filtering, rest days, completed/missed dates, legacy plans, and invalid prescriptions.
- [ ] Fix `_complete_plan` to persist scheduled sessions and normalize old sessions before display/repair.
- [ ] Add deterministic dated-session status resolution and an explicit clarification state for unmatched completions.
- [ ] Reject blank or `As prescribed` prescriptions and retry Ollama generation/repair.
- [ ] Use Ollama to phrase the clarification and remaining-session response; preserve the existing table columns.
- [ ] Run focused workflow/UI tests, compilation, and diff checks.
