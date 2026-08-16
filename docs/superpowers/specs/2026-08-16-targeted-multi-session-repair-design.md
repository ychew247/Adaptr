# Targeted Multi-Session Repair Design

## Goal

Allow a saved daily check-in to amend one or more explicitly requested workout sessions, identified naturally by plan day label (for example, `Day 1`) or scheduled date. Retain the existing automatic repair target when the user does not request a session.

## User-visible behaviour

- A user can combine their status and a repair request in one message: “My shoulder is sore and energy is 3/5; repair Day 2 and 2026-08-19.”
- The saved check-in supplies the same readiness, pain, soreness, sleep, and energy context to every selected session.
- `Day N` resolves against the labels in the active plan. Dates resolve against the plan's `scheduled_date` values.
- The agent changes only selected sessions and explicitly reports their dates and labels. Unselected sessions remain unchanged.
- If the request names no session, the existing target selection remains unchanged: use the check-in date's planned session, otherwise the next planned session.
- Invalid, duplicate, unavailable, or ambiguous targets cause a clarification rather than an unintended plan change.

## Architecture

1. A small Ollama structured-output parser interprets a check-in message for requested repair targets. It produces an array of requested plan labels or dates, not an action decision.
2. A deterministic resolver matches those references to the active plan's sessions and rejects targets outside that plan.
3. The controller saves the check-in as it does today, then passes the resolved target dates to the agent flow.
4. The agent flow invokes the repair service once per target date. Each repair records a separate audit decision and updates the same active plan before the next target is processed.
5. The repair application accepts an explicit target date. It modifies exactly that session, including recovery substitutions; it no longer propagates a requested single-session repair across the week.

## Safety and validation

- Ollama determines what the user meant, but cannot invent target sessions: application code resolves against known session labels and dates.
- Existing readiness and pain gates still determine the type and intensity of each repair.
- The current idempotency key remains scoped to user, plan, and target date, so repeated requests do not duplicate a change.
- Existing plan validation runs after every individual target repair. If one target cannot be repaired safely, that repair is retained as a fallback while other valid target repairs remain recorded.

## Testing

- Parser tests cover one date, multiple dates, plan-day labels, duplicate references, and no explicit target.
- Resolver tests cover matching labels/dates and rejection of a date outside the plan.
- Flow and repair tests prove multiple requested targets are repaired, only those sessions change, and the existing default target is preserved.
- Controller tests prove a compound status-and-targeted-repair message saves the check-in and returns the changed sessions.

