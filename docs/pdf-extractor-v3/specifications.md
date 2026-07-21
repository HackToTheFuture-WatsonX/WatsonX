# PDF Extractor V3 — Specifications

This document defines the functional requirements, non-functional requirements, constraints, assumptions, and glossary for PDF Extractor V3. Everything here is V3-specific and self-contained.

---

## Functional Requirements

### FR-01 — Box Synchronisation
- The system shall authenticate to IBM Box using a JWT service-account JSON stored in the `jwt_config` SQLite table
- The system shall download all `.pdf` files from the configured `box.folder_id`
- The system shall skip files that already exist in `Local Folder` (by filename)
- The system shall move each successfully downloaded file to `box.archive_folder_id` on Box
- The system shall recursively descend into Box subfolders when `settings.search_subfolders` is `true`
- The system shall emit `sync:log` SocketIO events for every file action so the UI displays live progress
- The system shall emit `sync:done` with `{downloaded, skipped, errors[]}` on completion
- The system shall trigger a folder scan automatically after a successful sync

### FR-02 — Folder Scan
- The system shall walk `Local Folder/**/*.pdf`, excluding `Extracted/` and `Archive/` subdirectories
- Each discovered PDF shall be registered in the `tracking_files` table with `status = "Pending"`
- Previously extracted files (those with `last_extracted` set) shall preserve their metadata when re-scanned
- Stale entries (where neither `local_path` nor `archive_path` exists on disk) shall be purged from `tracking_files`
- The system shall emit `scan:progress` per file and `scan:done` with total / pending / completed counts

### FR-03 — PDF Extraction Pipeline
- The system shall process all rows in `tracking_files` with `status = "Pending"`
- The system shall decrypt each PDF using `pdf_password` from the `config` table
- The system shall extract text page by page using PyMuPDF and route pages to section parsers
- The system shall produce one `.docx`, one `.xlsx`, and one `.json` output file per PDF
- Output files shall be written into a dated hierarchy: `Extracted/<type>/<YYYY>/<Mon_YYYY>_Extracts/Week_<NN>/<YYYY-MM-DD>/`
- The system shall upload all three output files to `box.output_folder_id`, mirroring the local folder hierarchy on Box
- The system shall move the source PDF to `Local Folder/Archive/` after successful extraction
- The system shall update the corresponding `tracking_files` row: `status = "Completed"`, `ref_number`, `last_extracted`, `archive_path`
- The system shall insert a log entry into the `extraction_logs` table for every processed file (success or failure)
- A failed file shall remain `Pending` in `tracking_files` and shall not stop processing of remaining files
- Only one extraction pipeline shall run at a time
- The system shall emit `extract:progress`, `extract:result`, and `extract:done` SocketIO events

### FR-04 — File Viewer
- The system shall list all extracted `.docx`, `.xlsx`, and `.json` files grouped by document type and case reference
- The system shall sort files by modification time (newest first) within each group
- The system shall open a selected file in the OS default application (`os.startfile()`) on Windows

### FR-05 — Insights & Analytics
- The system shall return a count of total, completed, and pending files from the `tracking_files` table
- The system shall return a bar chart dataset bucketed by the requested period (`day`, `week`, `month`, `year`)
- The system shall return log history from the `extraction_logs` table, filtered to entries on or after the period cutoff
- Log entries shall be truncated to the first 10 lines per entry in the API response

### FR-06 — AI Chat Assistant
- The system shall provide a `POST /api/chat/send` endpoint accepting `{message, history[]}` and returning `{reply}`
- The system shall route the following intents locally without calling ICA:
  - `sync` / `sync folder` → run Box sync
  - `scan` / `scan folder` → run folder scan
  - `extract` / `run extract` → run extraction pipeline
  - `file status` / `how many files` → return tracking counts
  - `logs this week` (and other periods) → return formatted log history from DB
  - `look up [name/ref]` / `find [name]` → search JSON extracts and format report block
  - `generate report for [name]` → locate and open extracted file in OS app
- General questions shall be forwarded to ICA when ICA credentials are configured
- All ICA replies shall pass a hallucination-detection regex check before being returned to the client
- When ICA is not configured, the system shall return a help menu listing available commands

### FR-07 — Settings & Configuration
- The system shall persist application configuration in the `config` SQLite table (one row per top-level section)
- The system shall return configuration via `GET /api/settings` with `pdf_password` and `full_cookie` masked as `••••••••`
- The system shall accept configuration updates via `POST /api/settings` using a deep-merge strategy; masked values shall be silently ignored so real secrets are never overwritten with mask text
- The `full_cookie` value shall be automatically stripped of leading/trailing whitespace on save
- The system shall accept Box JWT JSON via `POST /api/settings/jwt` and store it in the `jwt_config` table
- The system shall expose streaming connection tests for Box and ICA via Server-Sent Events (`GET /api/settings/test/box/stream`, `GET /api/settings/test/ica/stream`)
- Each SSE test stream shall emit `{step, state: "run"|"ok"|"error"|"done"}` events; the stream shall end on `"done"` or `"error"`

### FR-08 — ICA Browser Login
- The system (Electron main process) shall open a `BrowserWindow` pointing at IBM Consulting Advantage for one-click credential capture
- The window shall use a persistent session partition so the user stays logged in across attempts
- The system shall intercept outgoing request headers to capture `cookie`, `teamid`, `teamname`, and `chat_id`
- A `chat_id` shall only be accepted as authoritative when captured from a real `/chats/{id}/entries` POST request (proof that the user sent a message and the thread is initialised)
- The captured credentials shall be automatically persisted to the `config` table on `POST /api/settings`

---

## Non-Functional Requirements

### NFR-01 — Distribution
- The application shall be fully self-contained: no Python, Node.js, or npm shall be required on the target machine
- The application shall be distributable as both an NSIS installer and a single portable `.exe`

### NFR-02 — Responsiveness
- All network operations (Box sync, Box upload, ICA chat) shall run on background threads
- The FastAPI + SocketIO server shall remain responsive during any extraction or sync operation
- The UI shall display live progress via SocketIO events; it shall never block waiting for a background operation to complete

### NFR-03 — Persistence
- All application data (config, file tracking, JWT key material, extraction logs) shall be stored in a single SQLite database (`pdf_extractor_v3.db`) in WAL mode
- The database shall survive unexpected process termination without corruption

### NFR-04 — Security
- The `pdf_password` and `full_cookie` values shall never be returned to the frontend in cleartext
- The Box JWT key material shall be stored in the database, not as a separate file on disk
- The ICA `full_cookie` shall not be logged in the clear; `chat.py` shall log only a redacted fingerprint (cookie names + length)

### NFR-05 — Reliability
- A failed extraction for one file shall not stop processing of subsequent files
- Failed files shall remain `Pending` with a log entry recording the error
- The application shall display a startup error dialog if the backend fails to start within 30 seconds

### NFR-06 — Portability
- All file paths shall be resolved relative to `_data_dir()` (backed by `--data-dir` CLI arg) so the app works from any location
- The `data_dir` shall default to `backend/` in development and `%APPDATA%\PDF Extractor V3\` in production

### NFR-07 — Compatibility
- The extraction engine shall produce structurally identical JSON output to V2 for the same input PDF
- The JSON output schema shall be stable across V3 minor versions

---

## Constraints

| Constraint | Detail |
|---|---|
| **Python 3.12** | Required for `dict \| None` type union syntax and other 3.10+ features |
| **Windows only** | `os.startfile()` and `win32crypt` are Windows-specific; the app is distributed as a Windows `.exe` |
| **PyInstaller one-folder build** | All Python modules and data files must be declared in `backend.spec`; dynamic imports bypass static analysis |
| **boxsdk v3 (3.9.2)** | Must use `boxsdk` v3, NOT `box_sdk_gen` v10; the JWT API is incompatible between the two |
| **In-memory PDF processing** | PDFs are loaded fully into memory; very large files (>100 MB) may cause memory pressure |
| **ICA polling model** | ICA does not expose a streaming endpoint; the chat loop polls every 2 s for up to 60 s per message |
| **Report format** | The PDF parser is tuned to the Corpnet Global Corp two-column layout with ALL-CAPS section headings |
| **Single user** | The backend listens on `127.0.0.1` only; multi-user access is not a design goal |

---

## Assumptions

1. All PDFs in the Box source folder are Corpnet Global Corp background check reports using the known layout
2. The `pdf_password` in the database correctly decrypts all current reports
3. The Box source folder does not contain non-report PDFs that would be incorrectly parsed
4. Report status verdicts appear only on the cover page (page 0) and occasionally page 1 — never exclusively on detail pages
5. Section headings in the PDF are identifiable as ALL-CAPS text by regex
6. The `Case Reference No` field on the cover page is a reliable unique identifier per report
7. The ICA chat session (`chat_id`) remains valid for the lifetime of the browser session cookie (`full_cookie`)
8. The Electron app runs on Windows 10 or later (required for `os.startfile()` and the NSIS/portable packaging)

---

## Glossary

| Term | Plain-Language Definition |
|---|---|
| **Background Check Report** | A formal document from Corpnet Global Corp verifying a person's employment history, professional references, and database records (sanctions, adverse media, credit, etc.) |
| **Box / IBM Box** | A cloud file storage service (like Google Drive) where PDF reports arrive and where extracted outputs are uploaded |
| **Case Reference Number** | A unique code assigned to each background check case (e.g. `RN-123456_789_10`) — used as the primary key for report lookup |
| **Cleared** | The check result shows no issues — the candidate passed that particular verification |
| **Not Cleared** | The check result shows a problem — something did not verify correctly |
| **Pending** | A PDF that has been registered in the tracking database but not yet extracted |
| **Completed** | A PDF that has been successfully extracted, exported, archived, and uploaded |
| **Extraction** | The process of opening a PDF, decrypting it, reading its contents, and converting them into structured Word / Excel / JSON files |
| **Tracking Database** | The `tracking_files` table in `pdf_extractor_v3.db` — records each PDF's filename, status, reference number, and archive location |
| **SQLite / `pdf_extractor_v3.db`** | The single database file storing all V3 application data (config, tracking, JWT, logs); replaces the `config.json`, `tracking_db.json`, and `Log History/` files from V2 |
| **JWT / JWT Config** | A JSON file containing a Box service-account cryptographic key pair, used to authenticate with Box without a user-facing login. Stored in the `jwt_config` table in V3 |
| **WAL Mode** | Write-Ahead Logging — a SQLite feature that allows background threads to write while the main thread reads, without blocking |
| **ICA / IBM Consulting Advantage** | IBM's internal AI chat platform (CuratorAI) used as the AI assistant backend for general questions |
| **Cookie (ICA)** | A browser session token captured from the ICA web app, used to authenticate API requests on behalf of the signed-in user |
| **SocketIO** | A real-time event protocol (WebSocket-based) used by the backend to stream live progress messages to the frontend during sync, scan, and extraction |
| **SSE / Server-Sent Events** | A one-way streaming HTTP protocol used for the Settings connection tests — the backend pushes step-by-step progress events to the browser |
| **Bee** | The name of the V3 AI assistant persona, used in the Chat page |
| **Hallucination Guard** | A regex pattern list that checks every ICA reply for fabricated report data before displaying it to the user |
| **PyInstaller** | A tool that packages a Python application and all its dependencies into a standalone executable (`backend.exe`) |
| **Electron** | A framework for building desktop apps using web technologies (JavaScript, HTML, CSS). V3 uses it to bundle the React UI and manage the backend process lifecycle |
| **Archive folder (local)** | `Local Folder/Archive/` — where source PDFs are moved after successful extraction |
| **Archive folder (Box)** | The Box folder (`box.archive_folder_id`) where source PDFs are moved after being downloaded, so they are not re-synced |
| **Output folder (Box)** | The Box folder (`box.output_folder_id`) where extracted Word / Excel / JSON files are uploaded |
| **DFD** | Data Flow Diagram — a diagram showing how data moves through a system |
