# Monitoring

PDF Extractor V3 is a single-user desktop app. There is no centralised monitoring stack — monitoring means "what does the operator have to look at when something feels wrong". This doc enumerates those surfaces.

---

## Surfaces at a Glance

| Surface | What it tells you | Where |
|---|---|---|
| Diagnostics panel | Last click / pick / fetch state on the Scan page | Scan page, expand `<details>` |
| Backend log | Uvicorn access + every Python `log.info/warning/error` and stdout | `%TEMP%\pdf-extractor-v3-backend.log` |
| Startup log | Electron main-process boot narrative | `%TEMP%\pdf-extractor-v3-startup.log` |
| ICA log | Every ICA request/response with cookie fingerprint | `%APPDATA%\PDF Extractor V3\ica.log` |
| Activity log | User-visible transactions with `[[level=…]]` | Logs page (backed by `extraction_logs` table) |
| Health endpoint | Backend liveness | `http://127.0.0.1:<port>/api/health` |
| Insights page | Throughput dashboard | Insights page |

---

## Health Endpoint

`GET /api/health` returns:

```json
{"status": "ok", "version": "3.0.0"}
```

Electron polls this at 500 ms intervals for up to 30 s at startup. In steady state, the frontend does not poll — the endpoint exists for external smoke checks and manual verification.

Failure mode: TCP connection refused → backend is dead or not yet up. Non-200 response → backend is up but the FastAPI app failed to include the router.

---

## Backend Log — `%TEMP%\pdf-extractor-v3-backend.log`

Written by `electron/main.js` — it truncates the file at every launch, prepends a header, then pipes stdout/stderr from `backend.exe`:

```
=== backend launch @ 2026-07-20T09:12:33.123Z ===
cmd: C:\...\backend.exe --port 8765 --data-dir C:\Users\...\AppData\Roaming\PDF Extractor V3
cwd: C:\...\resources\backend

[out] [V3 Backend] Starting on http://127.0.0.1:8765
[out] [V3 Backend] Registered routes:
[out] [V3 Backend]   POST   /api/scan/upload
[out] [V3 Backend]   POST   /api/sync/run
… (every route)
[out] INFO:     Started server process [12345]
[out] INFO:     Uvicorn running on http://127.0.0.1:8765
[out] INFO:     127.0.0.1:56312 - "GET /api/health HTTP/1.1" 200 OK
[out] INFO:     127.0.0.1:56312 - "POST /api/scan/upload HTTP/1.1" 200 OK
[out] [scanner] INFO POST /api/scan/upload — 1 file(s) → C:\...\Local Folder
[out] [scanner] INFO   incoming: name='BG-2026-01234.pdf' content_type=application/pdf
[out] [scanner] INFO upload done — 1 uploaded, 0 skipped, 0 error(s)
```

Contents of interest:

- **`INFO: Started server process`** — uvicorn is up.
- **`Registered routes:`** followed by every path — proves the packaged binary contains the endpoints the frontend expects.
- **`INFO: 127.0.0.1:... - "POST /api/... HTTP/1.1" <status>`** — one line per request. Non-200 responses are immediately visible.
- **`[scanner] INFO …`, `[ica] INFO …`** — module-specific INFO/WARN/ERROR lines from Python `logging`.

On process exit:

```
=== backend exited with code <n> @ <iso> ===
```

A non-zero exit is always a bug worth investigating.

---

## Startup Log — `%TEMP%\pdf-extractor-v3-startup.log`

Electron main-process narrative:

```
[2026-07-20T09:12:33.045Z] === PDF Extractor V3 launch === isPackaged pending, argv=…
[2026-07-20T09:12:33.121Z] whenReady: isPackaged=true resourcesPath=C:\… __dirname=C:\…
[2026-07-20T09:12:33.122Z] ensureUserConfig done
[2026-07-20T09:12:33.130Z] findFreePort -> 8765
[2026-07-20T09:12:33.140Z] createWindow called (splash)
[2026-07-20T09:12:33.150Z] spawnBackend called
[2026-07-20T09:12:38.900Z] waitForHealth resolved (backend healthy)
[2026-07-20T09:12:38.901Z] loadRenderer called
```

Any `UNCAUGHT EXCEPTION` or `UNHANDLED REJECTION` is logged here with a stack trace, and a modal dialog appears for the user.

---

## ICA Log — `%APPDATA%\PDF Extractor V3\ica.log`

Set up in `backend/chat.py`:

```
2026-07-20 09:15:42,013  INFO     [ica_chat] ICA request context:
2026-07-20 09:15:42,013  INFO     [ica_chat]   base_url  = https://servicesessentials.ibm.com/curatorai/services/chat/new-chat
2026-07-20 09:15:42,013  INFO     [ica_chat]   url       = …/chats/<id>/entries
2026-07-20 09:15:42,013  INFO     [ica_chat]   team_id   = <redacted>
2026-07-20 09:15:42,013  INFO     [ica_chat]   cookie    = <2483 chars, 12 cookies: ak_bmsc, bm_sv, _abck, …>
2026-07-20 09:15:42,013  INFO     [ica_chat] POST prompt (14 chars) → …
2026-07-20 09:15:42,912  INFO     [ica_chat] prompt accepted (HTTP 200), _id=abcd1234…
2026-07-20 09:15:42,913  INFO     [ica_chat] POST answer trigger (promptEntryId=abcd1234…) → …
2026-07-20 09:15:44,201  INFO     [ica_chat] answer stream received (HTTP 201, 1523 bytes)
2026-07-20 09:15:44,201  INFO     [ica_chat] parsed reply (487 chars)
```

The cookie is always redacted to a length + name fingerprint — never the value. This makes it safe to share with support.

---

## Activity Log — Logs page

The user-visible operational log. Every important operation writes a row. Filterable by period (day/week/month/year) and level (Info/Warning/Error). See [Audit-Logs.md](Audit-Logs.md).

Watch for:

- **Sudden spike of Error rows** — usually a credential expiry (ICA cookie) or Box permission change.
- **Persistent Pending** — files that fail extraction stay Pending; a growing Pending count with no matching Info completion is a red flag.

---

## What to Watch For

| Symptom | Where to look first |
|---|---|
| App won't start | Startup log → look for `UNCAUGHT EXCEPTION` |
| Backend never becomes healthy | Backend log → look for Python traceback |
| Upload button seems to do nothing | Diagnostics panel |
| Sync says "0 downloaded" repeatedly | Backend log for the actual `folder(id).get_items` traceback (probably a permission problem) |
| Chat times out or refuses to answer | ICA log for the last request context |
| Extraction fails on a specific file | Logs page → filter by that file's ref_number |

---

## Not Monitored

- **CPU / memory / disk** — not tracked by V3; use Windows Task Manager or `resource.getrusage` from a dev session if needed.
- **Network throughput** — not tracked. Sync speed is dominated by Box's API latency.
- **User activity metrics** — no telemetry. No analytics phone-home.

---

## Related

- [Logging.md](Logging.md) — log formats and levels
- [Incident-Response.md](Incident-Response.md) — what to do when monitoring surfaces something bad
- [Troubleshooting.md](Troubleshooting.md) — symptom → cause playbook
