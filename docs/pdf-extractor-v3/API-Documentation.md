# API Documentation

Complete catalogue of REST endpoints and Socket.IO events exposed by the V3 backend. Base URL is `http://127.0.0.1:<port>` where `<port>` is chosen dynamically at startup (preferred 8765; skips 5000/8080/47321).

The FastAPI-generated Swagger doc is available at `/docs` in dev mode.

---

## Convention

- All bodies are `application/json` unless stated otherwise.
- All errors return HTTP 200 with `{"status": "error", "error": "<message>"}` unless stated otherwise — this is intentional so the frontend can surface the message uniformly without try/catch on every fetch.
- Timestamps use ISO-8601 local time.
- All boolean, integer, and string values are literals — no null placeholders.

---

## Health

### `GET /api/health`

Liveness check used by Electron's health poll.

**Response**
```json
{"status": "ok", "version": "3.0.0"}
```

---

## Scan ( `/api/scan` )

### `POST /api/scan/run`

Trigger a scan in a background thread.

**Response**
```json
{"status": "started"}
```
or
```json
{"status": "already_running"}
```

**Socket.IO events emitted**
- `scan:progress` — `{found: <int>, name: "<filename>"}` per PDF discovered
- `scan:done` — `{found, total, pending, completed, [cancelled]}` on completion

### `POST /api/scan/cancel`

Cancel the running scan.

**Response**: `{"status": "cancelling"}` or `{"status": "not_running"}`

### `GET /api/scan/status`

**Response**: `{"running": bool, "last": <summary or null>}`

### `GET /api/scan/files`

Return the current tracking DB contents.

**Response**
```json
{
  "files": [
    {
      "key": "BG-2026-01234.pdf",
      "name": "BG-2026-01234.pdf",
      "status": "Completed",
      "last_extracted": "2026-07-20T09:12:33",
      "ref_number": "BG-2026-01234",
      "local_path": "C:\\Users\\...\\Local Folder\\BG-2026-01234.pdf"
    }
  ],
  "total": 42,
  "pending": 5,
  "completed": 37
}
```

### `POST /api/scan/upload`

**Content-Type**: `multipart/form-data`
**Field**: `files` (repeated)

Upload one or many PDFs into Local Folder. Non-PDFs and duplicates are rejected/skipped per file.

**Response**
```json
{
  "uploaded": [{"name": "a.pdf", "key": "a.pdf"}],
  "skipped":  [{"name": "b.pdf", "reason": "already exists", "key": "b.pdf"}],
  "errors":   [{"name": "c.txt", "error": "not a PDF"}],
  "totals":   {"total": 42, "pending": 6, "completed": 37}
}
```

**Socket.IO events emitted**
- `upload:progress` — `{name, state: "saving"|"uploaded"|"skipped"|"error", reason, index, total}` per file
- `upload:done` — the same object as the HTTP response

---

## Sync ( `/api/sync` )

### `POST /api/sync/run` · `POST /api/sync/cancel` · `GET /api/sync/status`

Same shape as Scan. Socket.IO events:

- `sync:log` — `{message: "<human-readable line>"}` per action (download / skip / archive / error)
- `sync:done` — `{downloaded, skipped, errors: [<messages>]}` on success or `{cancelled: true}` on cancel or `{error: "<message>"}` on hard failure

---

## Extract ( `/api/extract` )

### `POST /api/extract/run` · `POST /api/extract/cancel` · `GET /api/extract/status`

Same lifecycle shape. Socket.IO events:

- `extract:progress` — `{current, total, percent, name}` on every file start
- `extract:result` — per-file:
  ```json
  {
    "status": "ok",
    "fname": "BG-2026-01234.pdf",
    "ref": "BG-2026-01234",
    "word": "C:\\...\\Word Extracts\\...\\BG-2026-01234.docx",
    "excel": "C:\\...\\CSV Extracts\\...\\BG-2026-01234.xlsx",
    "json": "C:\\...\\JSON File Extracts\\...\\BG-2026-01234.json",
    "upload": "Uploaded to Box folder 987654"
  }
  ```
  or `{status: "error", fname, error}`.
- `extract:done` — `{completed, failed, total, [cancelled]}`

### `GET /api/extract/results`

Alias for `/api/scan/files`.

---

## View ( `/api/view` )

### `GET /api/view/files`

Return every extracted output known to the app, keyed by reference number.

**Response**
```json
{
  "records": [
    {
      "ref": "BG-2026-01234",
      "subject": "Jose Manalo",
      "word":  "C:\\...\\BG-2026-01234.docx",
      "excel": "C:\\...\\BG-2026-01234.xlsx",
      "json":  "C:\\...\\BG-2026-01234.json",
      "extracted_at": "2026-07-20T09:12:33"
    }
  ]
}
```

---

## Insights ( `/api/insights` )

### `GET /api/insights`

**Response**
```json
{
  "total": 100,
  "pending": 5,
  "completed": 95,
  "week":  {"labels": ["Mon","Tue",…], "counts": [3,7,2,4,1,0,0]},
  "month": {"labels": ["Jul 01","Jul 02",…], "counts": [1,0,4,…]}
}
```

### `GET /api/insights/log-entries?period={day|week|month|year}`

**Response**
```json
{
  "entries": [
    {
      "id": 42,
      "ref_number": "BG-2026-01234",
      "occurred_at": "2026-07-20T09:12:33",
      "content": "[[level=info]] Background Check Report Automation V3 — …"
    }
  ]
}
```

Used by the Logs page.

---

## Chat ( `/api/chat` )

### `POST /api/chat/send`

Route a user message through Bee (local skills first, then ICA fallback if configured).

**Body**
```json
{
  "message": "look up Jose Manalo",
  "history": [
    {"role": "user", "content": "…"},
    {"role": "assistant", "content": "…"}
  ]
}
```

**Response**
```json
{"reply": "Subject: Jose Manalo | Ref: BG-2026-01234 | …"}
```

Errors are returned as `{"reply": "⚠ Error: …"}`.

---

## Settings ( `/api/settings` )

### `GET /api/settings`

Returns the full config with secrets masked.

**Response**
```json
{
  "config": {
    "pdf_password": "••••••••",
    "box": {"folder_id": "12345", "archive_folder_id": "67890", "output_folder_id": ""},
    "ica": {"full_cookie": "••••••••", "team_id": "abc", "chat_id": "xyz", …},
    "local": {…},
    "sync": {…},
    "settings": {…}
  }
}
```

### `POST /api/settings`

Save a partial or full config patch. Values equal to the mask (`••••••••`) are preserved unchanged on disk. Trims the ICA cookie of whitespace. If `chat_id` changed, resets `system_prompt_chat_id`.

**Body**
```json
{"config": {"box": {"folder_id": "99999"}}}
```

**Response**
```json
{"status": "saved", "path": "C:\\...\\pdf_extractor_v3.db", "config": <masked>}
```

### `GET /api/settings/status`

**Response**
```json
{
  "box":  {"configured": true,  "jwt_uploaded": true, "folder_id": true},
  "ica":  {"configured": true, "full_cookie": true, "team_id": true, "chat_id": true,
           "system_prompt_chat_id": "xyz", "primed": true},
  "pdf_password": true,
  "ready": true
}
```

### `POST /api/settings/jwt`

Upload or replace the Box service-account JWT JSON.

**Body**
```json
{"content": "<raw JSON text>"}
```

**Response**: `{"status": "saved", "path": "…"}` or `{"status": "error", "error": "Invalid JSON: …"}`.

### `POST /api/settings/test/box`

One-shot Box test (returns final result only). Prefer the SSE endpoint below for live feedback.

**Response**: `{"status": "ok", "user": "…", "folder": "…"}` or `{"status": "error", "error": "…"}`

### `POST /api/settings/test/ica`

One-shot ICA test.

**Response**: `{"status": "ok", "reply_preview": "…"}` or `{"status": "error", "error": "…"}`

### `GET /api/settings/test/box/stream` — Server-Sent Events

Live step-by-step Box test. Each event:
```
data: {"step": "Authenticating with Box…", "state": "run"}
data: {"step": "Signed in as jules@ibm.com ✓", "state": "ok"}
…
data: {"step": "Box connection is working.", "state": "done", "detail": "…"}
```

States: `run` (in progress), `ok` (step passed), `error` (fatal), `done` (test complete).

### `GET /api/settings/test/ica/stream` — SSE

Same shape as Box stream, running the ICA two-POST flow with `"Hi Bee"` as the test prompt.

### `GET /api/settings/init/ica/stream` — SSE

Sends `bee_prompt.md` as the first PROMPT on the currently-configured `chat_id`. Sets `system_prompt_chat_id` on success.

---

## Socket.IO — Complete Event Catalogue

Namespace: `/` (default).

| Event | Data | Emitted from |
|---|---|---|
| `sync:log` | `{message}` | `backend/sync.py` |
| `sync:done` | `{downloaded, skipped, errors}` or `{cancelled: true}` or `{error}` | `backend/sync.py` |
| `scan:progress` | `{found, name}` | `backend/scanner.py` |
| `scan:done` | `{found, total, pending, completed, [cancelled], [error]}` | `backend/scanner.py` |
| `upload:progress` | `{name, state, reason, index, total}` | `backend/scanner.py` |
| `upload:done` | full upload response | `backend/scanner.py` |
| `extract:progress` | `{current, total, percent, name}` | `backend/extractor.py` |
| `extract:result` | per-file result dict | `backend/extractor.py` |
| `extract:done` | `{completed, failed, total, [cancelled]}` | `backend/extractor.py` |

Client-side subscription: `frontend/src/hooks/useSocket.ts` (`useSocketEvent<T>(name, handler)`).

---

## Error Semantics

- **HTTP-level** errors (network, 4xx/5xx) surface only for the multipart upload endpoint, which sets appropriate status codes. Every other endpoint returns HTTP 200 with `{"status": "error", "error": ...}` so the frontend can render the message uniformly.
- **Socket.IO** events never signal errors via a special channel — pipeline modules emit a `*:done` event with an `error` or `cancelled` field.

---

## Related

- [System-Design.md](System-Design.md) — event delivery details
- [Codebase-Structure.md](Codebase-Structure.md) — where each router lives
