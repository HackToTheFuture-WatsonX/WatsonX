# ADR 0001 — SQLite as the single persistence layer

- **Status:** Accepted
- **Date:** 2026-02-14
- **Deciders:** V3 core team

## Context

V1 and V2 stored state in loose files under the app directory:

- `config.json` — credentials, folder IDs, sync toggles.
- `tracking_db.json` — per-file processing status.
- `box_jwt_config.json` — Box service-account JWT.
- `Log History/*.log` — one file per extraction run.

Problems observed in production:

1. **Corruption risk on partial writes.** A crash mid-write on `tracking_db.json` produced a truncated JSON file the next start refused to load.
2. **No atomic multi-key updates.** Updating three status columns at once required a full rewrite.
3. **Log-file sprawl.** After a year, the `Log History/` folder held thousands of files. Basic filters (by date, by ref number) required a filesystem walk on every request.
4. **Concurrent access.** Background worker threads writing while the frontend polled ran into rare-but-real "empty file read" races.
5. **User confusion.** "Where's my config? Can I hand-edit it?" — power users would break the app by editing JSON while it ran.

## Decision

Move every piece of application state into a single **SQLite database** file at `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db`. Four tables:

- `config` — key/value store, one row per top-level section (JSON-encoded).
- `tracking_files` — one row per known PDF, PK is `rel_key`.
- `jwt_config` — single row (`CHECK id = 1`) holding the Box JWT JSON.
- `extraction_logs` — activity-log rows, indexed on `occurred_at`.

Access exclusively through `backend/db.py` (thin `sqlite3` wrappers — no ORM). Every access opens a fresh connection with a 30 s busy timeout and `PRAGMA journal_mode=WAL`.

## Consequences

**Positive**
- Atomic multi-column updates via a single `INSERT ... ON CONFLICT DO UPDATE` statement.
- WAL journal permits one writer + many readers concurrently — exactly V3's pattern.
- Backups are one file copy. See [Backup-and-Restore.md](../Backup-and-Restore.md).
- Users who want to inspect state have a well-defined tool (`sqlite3` CLI, DB Browser for SQLite).
- Log queries by period become one SQL scan instead of a filesystem walk.

**Negative**
- Losing "grep the log directory" as a diagnostic tool. Mitigated by the Logs page.
- No visible config editor for power users (they must use the Settings page). Mitigated by exposing every field on the Settings UI.
- Introduces a schema-migration concern for future breaking changes. Currently no versioning exists — see [Database-Schema.md](../Database-Schema.md#migration-story).

**Neutral**
- The Python stdlib `sqlite3` shipped with PyInstaller with no additional hidden imports required.

## Related

- [Database-Schema.md](../Database-Schema.md) — schema definition
- [Backup-and-Restore.md](../Backup-and-Restore.md)
- `backend/db.py`
