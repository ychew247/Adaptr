# Ollama Goal Interpretation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Ollama interpret free-form program-duration wording in the GUI goal flow while retaining deterministic validation.

**Architecture:** The runtime exposes `OllamaGoalParser`. The GUI uses it for initial and follow-up goal parsing, with `parse_training_goal` only as a fallback when Ollama parsing fails. Before persistence, `TrainingGoalService` rejects non-positive or non-integer durations.

## Tasks

- [ ] Add a regression test showing the GUI parser selection accepts an Ollama-interpreted free-form duration.
- [ ] Add the Ollama goal parser to runtime construction and pass it through the GUI goal-save path.
- [ ] Retain deterministic fallback and validate the saved duration.
- [ ] Run goal, runtime, and UI tests.
