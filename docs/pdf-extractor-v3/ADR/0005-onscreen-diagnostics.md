# ADR 0005 — On-screen Diagnostics panel over DevTools

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** V3 core team

## Context

A user reported: "I click Upload Files and nothing happens." No error, no toast, no file on disk. The user was running the packaged portable exe.

Diagnosing this remotely was hard because:

- Packaged Windows Electron detaches from the console — nothing printed to stdout is visible to the user.
- DevTools (`Ctrl+Shift+I`) is disabled in packaged builds by design (opens only when `!app.isPackaged`).
- Backend stdout/stderr previously went nowhere in packaged mode — the `pythonProcess.stdout.on('data', d => process.stdout.write(d))` call was a no-op with no attached console.
- Uvicorn was configured with `log_level="warning"`, so request lines were suppressed. A missing endpoint (404) and a working endpoint (200) looked identical to the operator.

The user had no way to determine which layer failed:
- Did the button ever fire?
- Did the OS file picker open?
- Did `onChange` receive files?
- Did the fetch leave the app?
- Did it reach the backend?
- Did the backend accept it?

## Decision

Add three durable diagnostic surfaces:

1. **Backend log file** — `%TEMP%\pdf-extractor-v3-backend.log`. `electron/main.js` truncates the file at every launch with a header (`=== backend launch @ <iso> ===`, cmd, cwd) and pipes `backend.exe` stdout/stderr into it with `[out]` / `[err]` line prefixes. Exit code recorded at the tail.

2. **Verbose uvicorn logs** — flipped `log_level` to `"info"` and set `access_log=True`. Every request now shows as `INFO: 127.0.0.1:xxxxx - "POST /api/scan/upload HTTP/1.1" 200 OK` in the backend log. Also, on startup the backend enumerates every registered route so the packaged binary can be proven to contain the expected endpoints:
   ```
   [V3 Backend] Registered routes:
   [V3 Backend]   POST   /api/scan/upload
   …
   ```

3. **On-screen Diagnostics panel** — an always-visible collapsible `<details>` block on the Scan page. Captures:
   - Resolved API base URL.
   - Scan and upload state.
   - Backend log path (with **Copy path** button).
   - `Last button click:` timestamp (proves the click reached `onClick`).
   - `Last file pick:` count / filenames / `cancelled` (proves what the picker returned).
   - `Last fetch:` URL, HTTP status (colour-coded), and response body preview (proves what the backend said, or "network-error" if the fetch itself failed).

Additionally, `useApi.upload()` was extended to return `{data, error, url, status, body}` so callers can render the fetch outcome without duplicating the fetch.

## Consequences

**Positive**
- "Nothing happens" is now impossible — every click populates at least one Diagnostics field.
- Remote support becomes tractable: ask the user to expand Diagnostics and read out three lines.
- The backend log survives a crash — the write-stream flushes per data event.
- Verbose access logs cost nothing at V3's throughput.

**Negative**
- Diagnostics section takes vertical space on the Scan page. Mitigated by making it a collapsed `<details>`.
- The backend log includes every request path, which reveals endpoint names. Not sensitive at V3's threat model (single-user local machine); reviewed in [Security-Model.md](../Security-Model.md).

**Neutral**
- Diagnostics panel is Scan-only for now. Extending to Sync/Extract is possible but hasn't been justified by user reports yet.

## Follow-ups

- Consider a **Copy diagnostics to clipboard** button that dumps everything (API base, log path, last fetch) as one bug-report-ready block.
- Consider surfacing the backend log path in Settings too.
- Extend the Diagnostics pattern to the Sync and Extract pages.

## Bugs Named by This Panel

Within days of shipping, the Diagnostics panel named its first real bug:

- **`Last file pick: cancelled by user` on every real pick.** The Diagnostics readout showed `Last button click: <ts>` but `Last file pick: cancelled by user` even when the user had genuinely picked a file. Root cause: `e.target.files` is a live `FileList`; the handler reset `e.target.value = ''` *before* reading `files.length`, which cleared the list in place. Fix in `frontend/src/pages/Scan.tsx:onFilesChosen`: snapshot into a `File[]` via `Array.from(rawFiles)` before resetting the input value.

Without the Diagnostics panel this bug would have been near-impossible to diagnose remotely — the visible symptom (button does nothing) points at every layer at once. The panel isolated it to "picker → onChange" in a single glance.

## Related

- `electron/main.js:spawnBackend` — the log-file redirect
- `backend/main.py` — verbose logging + route enumeration
- `frontend/src/pages/Scan.tsx` — Diagnostics section
- `frontend/src/hooks/useApi.ts:upload` — extended return shape
- [Troubleshooting.md](../Troubleshooting.md)
