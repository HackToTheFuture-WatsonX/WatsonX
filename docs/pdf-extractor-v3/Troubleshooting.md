# Troubleshooting

Diagnostic playbook. Symptom → likely cause → concrete fix, ordered from most common to rarest. Every scenario names the exact log file, screen, or endpoint to check.

---

## First: What to look at

Before diagnosing, know these three surfaces:

1. **Scan page → Diagnostics panel** — always visible; shows the last click / pick / fetch outcome. Named the failure most of the time in one glance.
2. **Backend log** — `%TEMP%\pdf-extractor-v3-backend.log`. Every launch truncates and re-opens this. Contains uvicorn access logs and every Python `print()` / `log.info()`.
3. **Electron startup log** — `%TEMP%\pdf-extractor-v3-startup.log`. Contains the isPackaged flag, resolved paths, uncaught exceptions.

Additional:

- `%APPDATA%\PDF Extractor V3\ica.log` — ICA request/response detail with cookie fingerprint (never the actual cookie).
- `http://127.0.0.1:<port>/api/health` — proves the backend is up; the port is in the address bar of DevTools in dev, or in the backend log line `Starting on http://…`.

---

## Application won't start

### Splash appears, then nothing happens for >30 s

Symptom: The dark splash "Starting backend service…" stays forever.

Likely cause: Backend never became healthy.

Check:
- Open `%TEMP%\pdf-extractor-v3-backend.log`.
- Look for a Python traceback in `[err]` lines.
- Look for `Starting on http://127.0.0.1:<port>` — if it never appears, the backend died at import time.

Common root causes:
- **Missing hidden import** — PyInstaller left something out. Add it to `backend.spec:hiddenimports` and re-run `build_backend.py`.
- **Config file corrupt** — rare; `db.py` recreates the SQLite on missing but not on corruption. Rename/delete `pdf_extractor_v3.db` and restart to re-init.
- **Port already in use** — the port finder tries 8765 then increments, skipping 5000/8080/47321. If ports 8765–8784 are all busy, startup fails. Free some ports.

### Windows SmartScreen blocks the exe

Cause: The exe is unsigned (see [FAQ.md](FAQ.md#is-v3-signed)). Click **More info** → **Run anyway**. Signing is on the roadmap.

### Dialog: "PDF Extractor V3 — Fatal Error"

The `uncaughtException` handler fired. The dialog body has the stack trace. Copy it and file a bug per [Bug-Report-Process.md](Bug-Report-Process.md).

---

## Upload / Scan issues

### "Upload Files" button seems to do nothing

Symptom: Click the button, no OS file picker appears, no error, no toast.

Fix: Open the **Diagnostics** panel on the Scan page. It records `lastClick`, `lastPick`, `lastFetch` even when everything else is silent.

- `Last button click: (none yet)` → the button never fired. Check for a runtime error in the renderer (rare in packaged builds).
- `Last file pick: cancelled by user` when you did pick a file → in 3.0.0 this was a real bug (fixed): the live `FileList` was cleared by resetting `input.value` too early. `Scan.tsx:onFilesChosen` now snapshots the pick into a `File[]` before the reset. If you see this on a current build, the OS file picker really returned no files (user pressed Cancel, or the accept filter matched nothing).
- `Last fetch: (none yet)` → click fired, picker returned, but upload never sent. Investigate.
- `Last fetch: 200 · body: …` with `uploaded: 0` → the file was rejected by the backend. The body names the reason (`not a PDF`, `already exists`).

Also check `%TEMP%\pdf-extractor-v3-backend.log` for a `POST /api/scan/upload` line.

### "Upload Files" returns 404

Cause: Packaged binary is stale — the endpoint was compiled after the exe was built.

Fix: Rebuild via `build_all.bat`. Verify at startup: the backend log lists every registered route on boot; `/api/scan/upload` should be one of them.

### Scan finds zero files even though PDFs are in the folder

Cause: The scanner walks `Local Folder/` recursively but skips anything under `Extracted/` or `Archive/`. If your PDFs are in a subfolder that shares a name with either, they'd be excluded.

Fix: Move the PDFs to `Local Folder/` (or a differently-named subfolder). Or override `local.local_folder` in Settings.

---

## Sync issues

### Empty sync shown as Error on the Logs page

Symptom: An empty Box source folder made Sync report `0 downloaded, 0 skipped, 0 failed` — but the Logs page shows the row as Error.

Cause: Pre-3.0.0 activity-log rows lacked the `[[level=…]]` marker; the Logs page fell back to a keyword heuristic that matched "0 error(s)".

Fix in current release: `backend/activity.py` now prepends `[[level=…]]`; the Logs classifier reads that tag first. New rows render correctly. Older rows may still misclassify — filter by period **This Week** or newer.

### Sync fails with "Cannot list folder"

Cause: Box JWT authenticated but the JWT service-account lacks access to the target folder.

Fix: On the Box side, add the service-account email as **Editor** or **Viewer** on the source, archive, and output folders. Test again — the SSE stream will succeed once permissions propagate (usually seconds).

### Sync says "Archive move failed" per file

Cause: The service account has read access to the source folder but not the archive folder.

Fix: Grant Editor role on the archive folder as well. Until then, source PDFs are still downloaded locally, but they won't be moved on Box — periodic manual cleanup required.

---

## Extract issues

### Every file fails with a decryption error

Cause: `pdf_password` is wrong.

Fix: Settings → paste the correct password → Save. Re-run Extract. See also `write_extraction_log` output on the Logs page — the exception text names the cause.

### One specific file fails, others succeed

Cause: PDF is malformed or its layout deviates from the parsed template.

Fix: Open the Word/JSON export (if any partial output was written) or the source PDF. If the layout is genuinely new, `backend/pdf_text_extractor.py` needs to be extended — this is a code change.

### Extract succeeds locally but skips Box upload

Symptom: Log line shows `Upload failed: <reason>` or `Box upload not configured`.

Fix:
- `Box upload not configured` → set `box.output_folder_id` in Settings.
- `Upload failed: …` → check Box permissions on the output folder; check `%TEMP%\pdf-extractor-v3-backend.log` for the full traceback.

---

## Chat / Bee issues

### Chat replies with the help menu instead of a real answer

Cause: ICA credentials are missing or incomplete.

Fix: Settings → verify cookie, team_id, chat_id are all present → **Test ICA**. If Test succeeds but Chat still uses the menu, click **Initialize ICA System Prompt** and confirm the status becomes **Primed**.

### Chat times out ("ICA did not respond in time")

Common cause: `chat_id` points at an uninitialized thread. This used to happen when the login window auto-captured a placeholder chat_id from a metadata call.

Fix (already in 3.0.0): `electron/main.js` only trusts a `chat_id` observed on a `/entries` POST (a real prompt submission). Re-run **Sign in to ICA** and *send at least one message* in the sign-in browser window before closing it.

### Chat says "I can only answer from our extracted records…"

Cause: The hallucination guard triggered — ICA's reply looked like fabricated report data.

Fix: This is expected behaviour. Use `look up <name-or-ref>` to retrieve real extracted content.

---

## Settings / Connection tests

### Box test says "Could not open the configured folder"

Cause: `folder_id` typo, or JWT lacks access.

Fix: Verify the folder ID in Box (URL after `.../folder/`). Ensure the service account (whose email is in the JWT JSON, `enterpriseID` section) is added as a collaborator on that folder.

### ICA test hangs at "Sending test prompt"

Cause: Session cookie expired or `chat_id` invalid.

Fix: **Sign in to ICA** again to refresh credentials. If the problem persists, `%APPDATA%\PDF Extractor V3\ica.log` contains the full request context (with cookie redacted) — send it with the bug report.

### JWT upload rejected as invalid JSON

Cause: The pasted content wasn't the raw JSON file. If you copied from a viewer that pretty-printed it, whitespace can still be fine — the actual problem is usually smart-quote substitution.

Fix: Open the `_config.json` file directly and copy its contents byte-for-byte, or use **Browse** and select the file. Ensure it starts with `{` and ends with `}`.

---

## Log file locations (quick reference)

| Log | Purpose |
|---|---|
| `%TEMP%\pdf-extractor-v3-startup.log` | Electron main-process startup |
| `%TEMP%\pdf-extractor-v3-backend.log` | Backend process (uvicorn access + every log/print) |
| `%APPDATA%\PDF Extractor V3\ica.log` | Detailed ICA request/response |
| `extraction_logs` table in the DB | User-facing activity log (viewed on the Logs page) |

---

## Escalation

If a symptom isn't covered here:

1. Reproduce with the Scan-page **Diagnostics** panel expanded.
2. Capture `%TEMP%\pdf-extractor-v3-backend.log` and `%APPDATA%\PDF Extractor V3\ica.log`.
3. File a bug per [Bug-Report-Process.md](Bug-Report-Process.md).
