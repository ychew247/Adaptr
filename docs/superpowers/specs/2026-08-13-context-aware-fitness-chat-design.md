# Context-Aware Fitness Chat Design

## Goal

Route each daily chat message to the appropriate existing fitness service or
CockroachDB-backed answer, so plan and follow-up questions do not create
check-ins or receive generic, ungrounded replies.

## Design

Both chat UIs will delegate daily-phase messages to one UI-neutral router.
The router uses constrained Ollama JSON intent classification with a
deterministic fallback, then fetches the state required by that intent.
Ollama may interpret wording and phrase general responses; persisted module
data remains authoritative.

Check-in messages are accumulated in session state until they include a
numeric sleep value and at least one recovery signal (energy, stress,
soreness, or explicit pain status). The router then passes the combined text
to the existing M4-M8 flow. Corrections reuse the existing check-in upsert.

Plan, nutrition, provenance, causal, and set-reduction questions use active
plans, recent plans, nutrition targets, check-ins, and decision history from
CockroachDB. Off-topic messages do not invoke the daily flow.

## Boundaries

M4-M9 remain unchanged as the source of persisted check-ins, readiness,
plans, nutrition targets, and decisions. The router only chooses when to
read their state and when to run the existing daily flow. Both Streamlit and
NiceGUI use the same router behavior.

## Acceptance Criteria

- The priority scenarios A, B, and F in
  `chat-intent-routing-test-scenarios.md` are covered by automated tests.
- Partial check-ins wait for sufficient information and then trigger one
  M4-M8 run with the accumulated text.
- Corrections update today's check-in through the existing upsert path.
- Grounded answers use the matching persisted data rather than generic text.
- Off-topic messages do not create a check-in or decision.
