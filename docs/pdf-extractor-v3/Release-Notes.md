# Release Notes

Cumulative changelog for PDF Extractor V3. Newest first.

Each entry lists user-visible changes. Diff detail lives in git commit history and PR descriptions.

---

## 3.0.0 — 2026-07 (current)

Initial 3.x release. Complete rewrite from V2's Tkinter UI onto Electron + React + FastAPI + SQLite. Backwards-incompatible with V2's data files by design — V3 stores everything in a single SQLite database at `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db`.

### New

- **Portable + installer distribution** — `PDF-Extractor-V3-Setup-3.0.0.exe` and `PDF-Extractor-V3-Portable-3.0.0.exe`. No Python, Node, or Chromium install required.
- **Modern React UI** — 8 routes (Home / Sync / Scan / Extract / View / Insights / Logs / Settings) with dark and light themes.
- **SQLite persistence** — `config`, `tracking_files`, `jwt_config`, `extraction_logs` tables. WAL journal for concurrent access.
- **Real-time progress** — Socket.IO events stream per-file status during Sync, Scan, Upload, and Extract.
- **Ad-hoc Upload Files** — the Scan page accepts OS-picker PDFs (single or multiple), streams them to the backend with per-file progress. Each file gets one row in the progress panel that updates in place across states (`Saving… → Uploaded / Skipped / Error`) — no more three-line-per-file noise.
- **Diagnostics panel** — always-visible section on the Scan page showing last click / pick / fetch outcome. Makes packaged-app failures debuggable without DevTools.
- **Backend log file** — `%TEMP%\pdf-extractor-v3-backend.log`, truncated per launch. Contains every uvicorn access log line and every Python `log.*` line.
- **Route enumeration at startup** — the backend prints every registered API route so packaged binaries can be verified in one glance.
- **Chat assistant (Bee)** — natural-language interface with local skills (`look up`, `sync`, `extract`, `logs`, `file status`) and ICA fallback for free-form chat.
- **Bee system-prompt priming** — `bee_prompt.md` is sent as the first PROMPT on a new chat_id via `POST /api/settings/init/ica/stream`. Persona is version-controlled.
- **Live connection tests** — Server-Sent Event streams for Box and ICA on the Settings page.
- **Browser-assisted ICA login** — Electron opens a dedicated window and captures the full cookie (including HttpOnly), team ID, and a trusted chat_id from an actual `/entries` POST.
- **Activity level tagging** — `backend/activity.py` prepends `[[level=info|warning|error]]` to every log row. Logs page classifies deterministically instead of by keyword heuristic.
- **Secret masking** — `pdf_password` and `ica.full_cookie` always returned as `••••••••` from the Settings API. Round-trip preserves the on-disk value.

### Behaviour Notes

- Sync completing with zero downloads / zero errors is classified as **Info**, not Error (empty Box source is not a failure).
- Changing `ica.chat_id` automatically clears `system_prompt_chat_id`; the Settings status flips to **Not yet primed**.
- Uploads sanitise filenames via `Path(name).name` to prevent path traversal; non-PDF uploads are rejected; duplicates are skipped without overwriting existing tracking rows.
- Extraction failures leave rows at Pending so a re-run retries them. Successes move the source PDF to `Local Folder\Archive\`.

### Fixes During Release Cycle

- **Upload Files button no longer silently "cancels" every real pick.** `e.target.files` is a *live* `FileList`; resetting `e.target.value = ''` cleared it in place before `files.length` was checked, so every successful pick was misclassified as cancelled and `upload()` was never called. Fixed by snapshotting into a real `File[]` array before the reset (`frontend/src/pages/Scan.tsx:onFilesChosen`).
- **Upload progress rows update in place per file.** Previously each state transition (`saving`, `uploaded`, etc.) appended a new row, so a single-file upload showed three lines. Now the Socket.IO handler matches by 1-based index and replaces the existing row, keeping one line per file.
- **Backend log stream ends the file cleanly.** `pythonProcess.on('exit', …)` now ends the write-stream with the exit-code marker so the tail of the log is complete.

### Under the Hood

- FastAPI 0.110+ · Socket.IO `async_mode="asgi"` · uvicorn 0.29+ · PyMuPDF 1.24+ · python-docx 1.1+ · openpyxl 3.1+ · aiofiles 23+.
- React 18.3 · Vite 5.4 · TypeScript 5.5 · Tailwind 3.4 · Zustand 4.5 · socket.io-client 4.7 · recharts 2.12.
- Electron shell packaged via `electron-builder` (NSIS + portable targets).
- Backend frozen with PyInstaller (one-folder mode) via `backend.spec`.

### Known Limitations

- Installer and portable exe are **unsigned** — Windows SmartScreen may warn on first launch. Signing is on the [Roadmap.md](Roadmap.md).
- Auto-sync toggle exists in config but is not wired to a scheduler.
- Extraction is single-threaded.
- No automated test suite.
- Only Windows x64 is produced by the build pipeline today.

---

## Prior Versions

- **V2** — Tkinter GUI, local sync + Box upload. Retained in `PDF Extractor V2/`; not receiving updates.
- **V1** — Tkinter GUI, Box OAuth2. Retained in `PDF Extractor/`; not receiving updates.

See [Product-Overview.md](Product-Overview.md#what-v3-replaces) for the migration rationale.
