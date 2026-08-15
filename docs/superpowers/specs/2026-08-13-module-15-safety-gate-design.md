# Module 15 Safety Gate Design

## Goal

Prevent unsafe fitness guidance before a check-in, plan, repair, nutrition response, or general-chat response is processed.

## Architecture

`assess_safety(message, profile, goal, active_plan, recent_checkin)` is a pure, deterministic function. It normalizes the raw message, recognizes explicit negations, then returns a structured assessment containing flags, severity, permitted actions, reason, and policy version. Any blocking result short-circuits normal workflow processing.

The safety gate is authoritative. Fitness-knowledge vector retrieval may later provide one supporting educational snippet to help phrase the response, but it cannot change the assessment or allow a blocked action.

## Rules

- Chest pain, fainting, severe dizziness, or severe shortness of breath: urgent; stop all exercise advice and recommend urgent medical assessment.
- Sharp, worsening, severe, or persistent pain: restrict intense training and direct the user to qualified care when appropriate.
- Stored clinician or medical restrictions: prevent specific workout advice until restrictions can be honored.
- Unsafe rapid weight loss, eating-disorder-risk wording, and harmful drug or supplement requests: do not provide facilitating instructions; offer safe, general alternatives.
- Explicit negation such as `no chest pain` must not trigger an emergency result.

## Integration

The runtime/router calls the gate immediately after receiving the raw message and assembling relevant persisted context. For `urgent` or `blocked` results, it returns the deterministic safe response and does not invoke plan generation, plan repair, or the normal check-in workflow. `restricted` results may route into the existing recovery-oriented readiness/repair path. `allowed` results proceed normally.

## Testing

Unit tests cover every safety category, mixed wording, case normalization, explicit negation, normal soreness, and profile-driven medical constraints. Integration tests verify a blocking assessment prevents downstream generation.
