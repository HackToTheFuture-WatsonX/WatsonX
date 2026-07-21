# Architecture Decision Records

An ADR captures **one** significant architectural or product decision — the context that forced it, the alternatives considered, the choice made, and the consequences we accept.

Write one when you're about to do any of the following:
- Change a module boundary (see [Technical-Architecture.md](../Technical-Architecture.md)).
- Bypass a shared abstraction (e.g. talk to Box outside `box_client.py`).
- Add a new external dependency or service.
- Change an on-disk data format (schema migration, config-file location, log rotation).
- Change the distribution model (packaging, signing, install location).

## Format

Each ADR is a numbered markdown file: `NNNN-short-slug.md`. Use the template:

```markdown
# ADR NNNN — <Short title>

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN | Deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** <names>

## Context

What forced the decision. What alternatives were on the table.

## Decision

The choice made, in one paragraph.

## Consequences

Positive, negative, and neutral outcomes. Follow-ups this creates.

## Related

Links to code, ADRs, or docs affected.
```

## Registered ADRs

| # | Title | Status |
|---|---|---|
| [0001](0001-sqlite-persistence.md) | SQLite as the single persistence layer | Accepted |
| [0002](0002-socketio-asgi-mode.md) | Socket.IO `async_mode="asgi"` with thread-safe emit | Accepted |
| [0003](0003-ica-two-post.md) | ICA two-POST prompt/answer flow | Accepted |
| [0004](0004-machine-readable-level-tag.md) | `[[level=…]]` marker for activity-log rows | Accepted |
| [0005](0005-onscreen-diagnostics.md) | On-screen Diagnostics panel over DevTools | Accepted |
