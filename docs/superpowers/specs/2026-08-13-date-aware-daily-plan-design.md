# Date-Aware Daily Plan Design

Each generated session is assigned and persists an ISO `scheduled_date` plus a `planned`, `completed`, `missed`, or `rescheduled` status. A check-in uses its saved date (database current date unless explicitly supplied) to identify the scheduled session; it never assumes a completion for an unscheduled date.

The daily presentation preserves the existing table but renders only current and future unresolved sessions, with real dates and explicit prescriptions. When completion is ambiguous, the deterministic scheduler creates a clarification state and Ollama phrases the question; no session status changes until the user selects a dated planned session. Ollama generates conversational copy and prescriptions, while scheduling, status transitions, and validation remain deterministic.

`As prescribed` is invalid output. Missing prescriptions cause generation/repair retry instead of display. Existing undated saved plans are normalized on read using their persisted `week_start` so they remain usable.
