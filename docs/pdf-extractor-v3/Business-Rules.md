# Business Rules

Domain invariants encoded in the V3 pipeline. Each rule is a **must** — violating one is a bug.

---

## BR-1 — Reference Number Priority

The **reference number** used to key an extracted report is derived, in order:

1. `report_summary.case_reference` from the parsed PDF, stripped of whitespace.
2. Falling back to `Path(fname).stem` (the PDF filename without extension).

Enforced at: `backend/extractor.py:run_extraction` (line ~130).

Consequence: filenames should not be renamed after ingestion — the fallback keys the export folder.

---

## BR-2 — Pending vs Completed Status Lifecycle

A `tracking_files` row moves through exactly two states:

- **Pending** — registered by `scanner.run_scan` or `scanner.scan_upload`. Awaiting extraction.
- **Completed** — set by `extractor.run_extraction` after a successful export + archive move.

There is **no in-between status**. A failed extraction leaves the row at `Pending` (with a `FAILED:` row in `extraction_logs`). Re-running extraction retries all `Pending` rows.

---

## BR-3 — Source PDF Move-on-Success

On successful extraction, the source PDF is **moved** (not copied) from `Local Folder/` to `Local Folder/Archive/`. This guarantees the next scan will not re-register the file as Pending.

If the destination name collides, the archived file is suffixed with `_YYYYMMDDHHMMSS` (see `extractor.py:run_extraction`).

If the move itself fails, the `archive_path` field is set to the still-live `local_path` and processing continues.

---

## BR-4 — Idempotent Sync

Sync **never re-downloads** a PDF whose local path already exists. This lets an operator run Sync repeatedly without side effects (`sync.py:_sync_folder` line 66).

Skipped rows are logged with `Skip (exists):` at INFO level.

---

## BR-5 — Box Archive is a Post-Download Operation

After a successful download from Box, the source item is **moved to `archive_folder_id`** on Box (`sync.py:_sync_folder` lines 77–84). This is an *idempotent* operation from the operator's perspective — a re-run finds nothing to download.

If the archive move fails, the local download is retained; a warning is logged. Manual cleanup on Box is required.

---

## BR-6 — Upload Skip-on-Duplicate

The `POST /api/scan/upload` endpoint **never overwrites** an existing file in `Local Folder/`. A duplicate upload:

- Skips the write.
- Preserves the existing `tracking_files.status` (so a previously-Completed row is not reverted to Pending).
- Emits `state=skipped, reason="already exists"` per file.

---

## BR-7 — Secret Masking

Two config values are always masked when sent to the frontend or written to the activity log:

- `pdf_password`
- `ica.full_cookie`

The mask value is `••••••••` (`_MASK` in `settings.py`).

On a POST to `/api/settings`, a masked value in the payload is treated as **"unchanged"** — the backend keeps the real value on disk. This means the UI can safely round-trip the config without leaking secrets.

Enforced at: `backend/settings.py:_mask_config`, `_deep_merge`.

---

## BR-8 — ICA Priming Tied to Chat ID

The Bee persona is sent to ICA as the **first PROMPT** on a chat and only that chat is treated as "primed". The primed chat ID is stored in `config.ica.system_prompt_chat_id`.

**Rule:** changing `config.ica.chat_id` in Settings automatically clears `system_prompt_chat_id`. The UI shows **Not yet primed** and the operator must re-initialize.

Enforced at: `backend/settings.py:save_settings` — if `chat_id` changed, `system_prompt_chat_id` is blanked.

---

## BR-9 — Chat_id Trust: Only /entries Sighted IDs are Trusted

During the browser-assisted ICA login, a `chat_id` observed on a URL matching `/chats/<id>/entries` is trusted; a `chat_id` observed on any other authenticated URL (metadata/config) is provisional and may be overwritten by the next `/entries` sighting.

If no trusted id was captured before the login window closed, `chat_id` is blanked so downstream POSTs don't time out against an uninitialized thread.

Enforced at: `electron/main.js:icaBrowserLogin`.

---

## BR-10 — Empty-Batch Sync is Info, Not Error

A sync run that completes with `0 downloaded, 0 skipped, 0 failed` (empty Box source folder, or every file already synced) writes an **Info-level** row to `extraction_logs`. Only an exception during sync sets the row to `Error`.

Enforced at: `backend/sync.py:_sync_thread` — level is `warning` iff `errors` is non-empty, `error` iff an exception escapes, `info` otherwise.

The Logs page classifier honours the `[[level=…]]` prefix so the empty case renders as Info, not misclassified via keyword heuristic.

---

## BR-11 — Activity Log Content Cap

Every activity-log write is capped at `_MAX_CONTENT_CHARS = 8000` characters. Overflow gets truncated with a `\n… (truncated)` marker.

Enforced at: `backend/activity.py:write`.

---

## BR-12 — Hallucination Guard

If the ICA reply matches any pattern in `_HALLUCINATION_PATTERNS` (fabricated report content, e.g. `Employment History:`, `Identity Verification:`, `Government-issued ID verified`), the reply is replaced with:

> I can only answer from our extracted records. Please use 'look up [name or reference]' to retrieve the report first.

Enforced at: `backend/chat.py:_is_hallucinated_reply` and `route_chat_message`.

---

## BR-13 — File-Type Whitelist on Upload

`POST /api/scan/upload` **rejects** any file whose sanitized name does not end in `.pdf` (case-insensitive). Filenames with path components are reduced to `Path(name).name` first to prevent traversal.

---

## BR-14 — Data Directory Immutability After Startup

`config.set_data_dir(path)` may only be called once — from `main.py` argparse — before any config read. Downstream modules resolve paths lazily through `_data_dir()` so changing it mid-run is not supported.

---

## BR-15 — Per-File Log Level Semantics

Activity-log rows carry one of three levels via `[[level=…]]`:

| Level | When |
|---|---|
| `info` | Successful completion; empty runs; benign skips |
| `warning` | User cancellation; missing credentials; non-fatal per-item failures inside an otherwise-successful batch |
| `error` | Exception that terminated the run; connection test that failed; JWT upload rejected |

The Logs page renders each level with a distinct badge. Filters (`All` / `Info` / `Warning` / `Error`) hide the others.

---

## Related

- [Feature-Scope.md](Feature-Scope.md) — what these rules apply to
- [Database-Schema.md](Database-Schema.md) — where the state lives
- [Audit-Logs.md](Audit-Logs.md) — how log rows are structured
