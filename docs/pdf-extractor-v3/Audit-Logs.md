# Audit Logs

The `extraction_logs` table in `pdf_extractor_v3.db` is V3's audit surface. Every user-visible action writes a row here. This document describes what's captured, how it's classified, and how to consume it for compliance evidence.

---

## Schema

```sql
CREATE TABLE extraction_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_number TEXT,
    occurred_at TEXT NOT NULL,       -- ISO-8601 local timestamp
    content    TEXT NOT NULL         -- prefixed with [[level=…]]
);
CREATE INDEX idx_logs_occurred_at ON extraction_logs (occurred_at);
```

- `ref_number` is either a report reference (extractor rows) or a category tag (`SYNC`, `SCAN`, `UPLOAD`, `SETTINGS`, `JWT-UPLOAD`, `BOX-TEST`, `ICA-TEST`, `ICA-INIT`).
- `content` is prepended with `[[level=info|warning|error]]` — see [ADR/0004](ADR/0004-machine-readable-level-tag.md).
- Content is capped at 8000 characters; overflow truncated with `\n… (truncated)`.

---

## What's Captured

Every user-triggered operation and every noteworthy background event:

### Configuration events

| Ref | When | Level | Example |
|---|---|---|---|
| `SETTINGS` | POST /api/settings changes any section | info | `Settings saved — updated section(s): box, ica.` |
| `JWT-UPLOAD` | POST /api/settings/jwt succeeds | info | `Box JWT service-account config saved.` |
| `JWT-UPLOAD` | Invalid JSON on upload | error | `Box JWT upload rejected — invalid JSON: …` |
| `BOX-TEST` | Test succeeds | info | `Box connection OK — user=…, folder=…` |
| `BOX-TEST` | Test fails | error | `Box connection failed: …` |
| `ICA-TEST` | Test succeeds | info | `ICA test OK — reply preview: …` |
| `ICA-TEST` | Test fails | error | `ICA test failed: …` |
| `ICA-TEST` | Missing credentials | warning | `ICA test aborted — missing credentials: session cookie, chat ID` |
| `ICA-INIT` | Priming succeeds | info | `ICA initialized — chat_id=abc12345…, prompt=bee_prompt.md (…)` |
| `ICA-INIT` | Priming fails | error | `ICA priming failed: …` |
| `ICA-INIT` | Missing credentials | warning | `ICA initialization aborted — missing credentials: …` |
| `ICA-INIT` | Persistence failure post-prime | error | `ICA primed but persisting system_prompt_chat_id failed: …` |

### Pipeline events

| Ref | When | Level | Example |
|---|---|---|---|
| `SYNC` | Sync completes with 0 errors | info | `Sync complete — 3 downloaded, 2 skipped, 0 failed.` |
| `SYNC` | Sync completes with errors | warning | `Sync complete — 5 downloaded, 0 skipped, 2 failed. \n [ERR] …` |
| `SYNC` | Sync cancelled | warning | `Sync cancelled by user.` |
| `SYNC` | Sync throws | error | `Sync failed: …` |
| `SCAN` | Scan completes | info | `Scan complete — found 12, total 42, pending 5, completed 37.` |
| `SCAN` | Scan cancelled | warning | `Scan cancelled by user.` |
| `SCAN` | Scan throws | error | `Scan failed: …` |
| `UPLOAD` | Upload batch, no errors | info | `Upload batch — 1 uploaded, 0 skipped, 0 failed.` |
| `UPLOAD` | Upload batch with errors | warning | `Upload batch — 0 uploaded, 0 skipped, 1 failed.` |
| `<ref_number>` | Per-file extraction success | info | Full manifest (see `extractor.write_extraction_log`) |
| `<ref_number>` | Per-file extraction failure | info (content includes `FAILED:`) | `FAILED: <fname>\nError: …` |

Note: extraction-log rows include the full outputs manifest — Word/Excel/JSON paths, Box upload status, archive path, start and completion timestamps. This is intentionally verbose so an audit can trace a single row back to every artefact.

---

## Enabling / Disabling

Global toggle: `config.settings.log_activity` (Settings page → **Log activity to database**). When off, `activity.write()` short-circuits and no rows are written. Python logging (backend log, ICA log) still runs — the toggle only silences the DB-backed audit stream.

Best practice for compliance-oriented deployments: **keep this on**. Turn off only for privacy-sensitive investigations where the operator is intentionally not persisting activity.

---

## Reading the Log

**On-screen** — the Logs page. Filter by period (day/week/month/year) and level (Info/Warning/Error). See [User-Guide.md](User-Guide.md#logs--logs-).

**Programmatically** — GET `/api/insights/log-entries?period=<day|week|month|year>` returns:

```json
{
  "entries": [
    {
      "id": 42,
      "ref_number": "SYNC",
      "occurred_at": "2026-07-20T09:12:33",
      "content": "[[level=info]] Sync complete — 3 downloaded, 2 skipped, 0 failed."
    },
    …
  ]
}
```

**Directly via SQL** — with V3 closed, open `pdf_extractor_v3.db` in any SQLite tool:

```sql
SELECT id, occurred_at, ref_number, content
  FROM extraction_logs
 WHERE occurred_at >= '2026-01-01'
   AND content LIKE '[[level=error]]%'
 ORDER BY occurred_at DESC;
```

---

## Non-Repudiation

The log is **not tamper-evident**. Any user with write access to the DB file can:

- Insert fake rows.
- Delete real rows (`DELETE FROM extraction_logs …`).
- Modify content (`UPDATE extraction_logs SET content = …`).

This is acceptable for V3's threat model (single-user local tool). For deployments needing tamper-evident logging:

- Copy log rows to a write-once external store (SIEM, immutable object storage) on a schedule.
- Sign rows with an external key when copied out — the copy is now tamper-evident, the local copy is a convenience.

Both approaches are out of the app's current scope; they're operator responsibilities.

---

## Correlation with Other Logs

An action can appear in multiple logs:

- **Sync** — one activity row per run + many `[out]` lines in `%TEMP%\pdf-extractor-v3-backend.log`.
- **ICA operations** — one activity row + a request-context block in `%APPDATA%\PDF Extractor V3\ica.log`.
- **Extraction failure** — one activity row (with `FAILED:` in content) + a Python traceback in the backend log.

The activity log answers *what and when*. The backend log answers *why*.

---

## Retention

None enforced by V3. Rows accumulate indefinitely. At ~1 KB per row, ~1000 rows per operator per year is typical.

For deletion:

```sql
DELETE FROM extraction_logs WHERE occurred_at < '2025-01-01';
VACUUM;   -- reclaim disk space (optional)
```

`VACUUM` requires exclusive access — close V3 first.

Automate via Windows Task Scheduler if your policy has a fixed retention window.

---

## Related

- [Logging.md](Logging.md) — every log stream V3 emits
- [Compliance.md](Compliance.md) — legal framing
- [Data-Retention.md](Data-Retention.md) — retention policy
- [ADR/0004](ADR/0004-machine-readable-level-tag.md) — level tag design
