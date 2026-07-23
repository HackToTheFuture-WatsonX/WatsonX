# Logging

Complete inventory of what V3 writes, where, at what level, and how long it's kept.

---

## Log Streams

| Stream | Location | Owner | Rotation |
|---|---|---|---|
| Startup log | `%TEMP%\pdf-extractor-v3-startup.log` | `electron/main.js` | Truncated & rewritten every launch |
| Backend log | `%TEMP%\pdf-extractor-v3-backend.log` | `electron/main.js` (redirects backend stdout/stderr) | Truncated with header every launch |
| ICA log | `%APPDATA%\PDF Extractor V3\ica.log` | `backend/chat.py` (Python `logging.FileHandler`) | None — grows indefinitely |
| Activity log | `pdf_extractor_v3.db` → `extraction_logs` table | `backend/activity.py` | None — grows indefinitely |
| Uvicorn stdout | Merged into backend log | `backend/main.py` (`log_level="info"`, `access_log=True`) | Truncated with backend log |
| Console (dev only) | Attached terminal | Everything with `print()` or `log.*` | Ephemeral |

---

## Levels

Two systems in play:

1. **Python `logging`** — used internally by `backend/scanner.py`, `sync.py`, `chat.py` etc. Levels: DEBUG < INFO < WARNING < ERROR < CRITICAL. Set to INFO globally.
2. **Activity log level tag** — `[[level=info|warning|error]]` prefix injected by `backend/activity.py`. Independent of Python logging. See [ADR/0004](ADR/0004-machine-readable-level-tag.md).

The two systems are related but distinct: a Python `log.error(...)` line ends up in the backend log; an `activity.write(..., level="error")` call ends up in the activity log and rendered on the Logs page.

---

## Startup Log

Rewritten on every launch of `electron/main.js`. Format:

```
[<ISO timestamp>] <message>
```

Line-buffered. Never blocks. Captures every user-uncatchable failure via:

```js
process.on('uncaughtException', (err) => logLine(`UNCAUGHT EXCEPTION: ${err.stack}`))
process.on('unhandledRejection', (reason) => logLine(`UNHANDLED REJECTION: ${reason}`))
```

Deleted on next launch (truncated to empty).

Retention: one launch's worth. Not intended for archival.

---

## Backend Log

Rewritten with a header on every launch. Format for stdout lines:

```
[out] <raw uvicorn/print line>
```

Format for stderr lines:

```
[err] <raw traceback>
```

Ends with:

```
=== backend exited with code <n> @ <iso> ===
```

Uvicorn `access_log=True` produces one line per HTTP request:

```
INFO:     127.0.0.1:<port> - "<METHOD> <path> HTTP/1.1" <status> <status-text>
```

Retention: one launch's worth.

---

## ICA Log

Written by Python's `FileHandler` in append mode. Format:

```
<YYYY-MM-DD HH:MM:SS,ms>  <LEVEL>    <message>
```

Every ICA request logs its full context (URL, team_id, team_name, chat_id, cookie fingerprint) plus both request outcomes (prompt POST and answer POST). Errors include the response body's first 500 chars.

Cookie is redacted to length + count + first 12 names:
```
cookie    = <2483 chars, 12 cookies: ak_bmsc, bm_sv, _abck, …>
```

Retention: append-only, forever, until the operator deletes it. Consider adding a simple age-based rotation in a future release.

---

## Activity Log ( `extraction_logs` table )

Rows written by `activity.write()`:

```
INSERT INTO extraction_logs (ref_number, occurred_at, content) VALUES (?, ?, ?)
```

Where:

- `ref_number` — either the report reference (`BG-2026-01234`) or a category (`SYNC`, `SCAN`, `UPLOAD`, `SETTINGS`, `JWT-UPLOAD`, `BOX-TEST`, `ICA-TEST`, `ICA-INIT`).
- `occurred_at` — ISO-8601 local timestamp.
- `content` — the message body, prepended with `[[level=info|warning|error]]`.

Content is capped at 8000 chars — overflow is truncated with `\n… (truncated)` at the end (`backend/activity.py:_MAX_CONTENT_CHARS`).

The Logs page reads via `GET /api/insights/log-entries?period=<day|week|month|year>`.

Retention: append-only. The `log_activity` setting on the Settings page (`config.settings.log_activity`) toggles writes globally — flipping it off silences all `activity.write()` calls (Python logging still writes to the backend log).

---

## What Goes Where

| Event | Backend log | ICA log | Activity log |
|---|---|---|---|
| App start | ✓ | — | — |
| Health poll | ✓ (access line) | — | — |
| `POST /api/settings` | ✓ (access) | — | ✓ (diff of masked sections) |
| `POST /api/settings/jwt` | ✓ | — | ✓ (`JWT-UPLOAD`) |
| `POST /api/settings/test/box` | ✓ | — | ✓ (`BOX-TEST` info/error) |
| `POST /api/settings/test/ica` | ✓ | ✓ (full request context) | ✓ (`ICA-TEST`) |
| ICA priming | ✓ | ✓ | ✓ (`ICA-INIT`) |
| Sync run | ✓ (many lines) | — | ✓ (`SYNC` — one summary row) |
| Scan run | ✓ | — | ✓ (`SCAN`) |
| Upload | ✓ (per-file) | — | ✓ (`UPLOAD` — batch summary) |
| Extract per file | ✓ | — | ✓ (per-ref-number, one row per file) |
| Chat message (local skill) | ✓ (access) | — | — |
| Chat message (via ICA) | ✓ (access) | ✓ | — |
| Uncaught exception (backend) | ✓ | — | — |
| Uncaught exception (Electron) | Startup log | — | — |

---

## Log Rotation

None today. Consider adding:

- **Backend log**: already truncated per launch; no action needed.
- **ICA log**: file-size-based rotation at 10 MB. Trivial with `logging.handlers.RotatingFileHandler`.
- **`extraction_logs` table**: retention-policy-based DELETE. Currently 100 % append; a "delete rows older than N days" job could be added if row count exceeds ~100 k. See [Data-Retention.md](Data-Retention.md).

---

## Sensitive Content Rules

Per [Business-Rules.md](Business-Rules.md#br-7-secret-masking) and [Security-Model.md](Security-Model.md):

- Never log `pdf_password` in cleartext.
- Never log `ica.full_cookie` in cleartext (use `_redact_cookie()`).
- The Settings save log entry diffs the **masked** config, not the raw one — the mask value is what's compared, so a saved secret still shows as an unchanged section.

Every log stream above has been reviewed against this rule.

---

## Related

- [Monitoring.md](Monitoring.md) — where to *look*
- [Audit-Logs.md](Audit-Logs.md) — compliance-oriented view of the activity log
- [Data-Retention.md](Data-Retention.md) — retention policies
- `backend/activity.py` — the shared log helper
