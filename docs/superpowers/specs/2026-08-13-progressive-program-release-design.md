# Progressive Program Release Design

## Goal

Support any requested program duration while generating and showing only the current weekly microcycle.

## Design

The existing `plan_duration_weeks` is the program duration. The first generated plan stores `program_start_date`, `program_end_date`, and `week_number` in its JSON. Sessions are always dated within one calendar week. The active plan represents only the current editable week; completed weeks remain historical records after the next week is released.

Daily check-ins and Module 7 repairs may change only `planned` or `rescheduled` sessions belonging to the active week. They cannot modify historical sessions or create edits in later weeks, because later weeks do not yet exist as persisted workout plans. A user can explicitly request the next week; the application validates that it is inside the requested program duration, archives the current week, and generates the next weekly plan using recent readiness/check-in history.

Exercise variation is bounded: a new week asks Ollama for 2–3 safe substitutions while retaining core movement patterns. Constraints, injuries, medical restrictions, equipment, and safety gates remain authoritative.

## Edge Cases

- A request shorter than a calendar week creates one final partial week.
- A check-in begins midweek: past dates are never backfilled or shown as planned.
- A next-week request after program end returns a completion response, not another plan.
- A safety-triggered repair changes only unresolved sessions of the active plan.
- Explicitly requested program-wide changes create a new goal/program version; ordinary check-ins do not.
