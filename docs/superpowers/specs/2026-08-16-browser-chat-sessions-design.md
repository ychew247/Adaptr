# Browser Chat Sessions Design

## Goal

Keep multiple NiceGUI conversations available in the sidebar, restore them after a browser refresh, and keep all transcript data local to the browser.

## User-visible behaviour

- Opening the app restores saved conversations from browser local storage. The most recently active conversation opens automatically.
- **New chat** creates a separate conversation with the normal welcome prompt. It never clears an existing conversation.
- The sidebar lists all conversations. Selecting one restores its messages, onboarding phase, user/profile state, printable-plan state, and status.
- A new conversation is labelled **New chat** until identity is resolved. It is then labelled with the identified user's `display_name`. Duplicate names are allowed.
- Session history survives refreshes in the same browser profile. Clearing browser site data removes it. It is not saved to CockroachDB and is not shared with another browser/device.

## Architecture

`ui/chat_state.py` owns a JSON-safe `ChatSession` snapshot contract and a `ChatSessionStore` that manages an ordered collection of sessions plus the active session identifier. The store is independent of NiceGUI and therefore unit-testable.

`ui/chat.py` uses the store as the source of truth. It renders dynamic sidebar buttons, swaps the active session/controller when a button is clicked, and syncs a JSON snapshot to `localStorage` after each state change. On first load it reads the snapshot; invalid or unavailable local data falls back to one new welcome session.

The browser key is versioned (`adaptr.chat_sessions.v1`). Stored data contains no credentials; it may contain chat messages and temporary S3 download URLs. Download URLs naturally expire, so a restored expired link is treated as a normal expired link rather than refreshed automatically.

## Error handling and limits

- Malformed, incompatible, or partially missing storage data is discarded without blocking the app; the user receives a fresh chat.
- Storage read/write browser errors do not interrupt fitness-agent work; the current in-memory sessions remain usable.
- The feature has no database migration and no change to existing CockroachDB profile, goal, check-in, plan, or decision records.

## Testing

- Unit-test store creation, new-session preservation, activation, display-name update, and JSON round-trip restoration.
- Unit-test invalid stored payload fallback.
- Characterisation-test that the NiceGUI page uses the browser key and renders a dynamic conversation list rather than a fixed `Current session` item.
- Run existing chat-state and controller tests to ensure planned-workout routing remains unchanged.
