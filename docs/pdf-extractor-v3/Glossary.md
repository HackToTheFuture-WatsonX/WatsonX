# Glossary

Terminology used across the codebase and documentation. Alphabetical.

---

**Activity log**
Rows in the `extraction_logs` SQLite table. Every user-visible operation (sync, scan, upload, extract, settings save, JWT upload, Box test, ICA test, ICA prime) writes one row. Viewable on the Logs page.

**Archive folder (Box)**
The Box folder where V3 moves the source PDF after a successful download. Configured via `box.archive_folder_id`.

**Archive folder (local)**
The on-disk folder (`Local Folder/Archive/`) where V3 moves the source PDF after a successful extraction. Configured via `local.archive_folder`.

**Bee**
The assistant persona used by the built-in chat. Persona is defined in `backend/prompt/bee_prompt.md` and sent as the first ICA prompt during "priming" (see below).

**Box JWT config**
The service-account JSON downloaded from Box Developer Console. Contains a signed private key that authenticates V3 to Box as a specific service account. Stored in the `jwt_config` table (single row).

**Case reference (`case_reference`)**
The primary identifier extracted from `report_summary.case_reference` in a parsed report. Used as the ref number for outputs when non-empty, falling back to the PDF filename stem.

**Chat ID (`chat_id`)**
The ID of a specific ICA chat thread. V3 sends every prompt to a single chat_id captured during the browser-assisted sign-in.

**Data directory**
`%APPDATA%\PDF Extractor V3\` on packaged installs; the `backend/` folder in dev. Location of `pdf_extractor_v3.db`, `ica.log`, and `Local Folder/`.

**Diagnostics panel**
The always-visible collapsible section on the Scan page that surfaces last button click, file picker outcome, and fetch URL/status/body. Designed to make packaged-app failures observable without DevTools.

**Extract folder**
`Local Folder/Extracted/`, home to the `Word Extracts/`, `CSV Extracts/`, and `JSON File Extracts/` dated hierarchies.

**Full cookie (`full_cookie`)**
The complete Cookie header sent to `servicesessentials.ibm.com`, including HttpOnly authentication cookies. Captured directly from the Electron cookie jar during ICA sign-in. Stored masked (`••••••••`) when returned via the Settings API.

**Hallucination guard**
Set of regex patterns in `chat.py:_HALLUCINATION_PATTERNS`. If an ICA reply matches, V3 substitutes a canned message telling the user to run `look up <name>` for real data.

**ICA (IBM Consulting Advantage)**
IBM's internal generative-AI chat service used as V3's remote LLM. Reached at `https://servicesessentials.ibm.com/curatorai/…`.

**Level tag**
The machine-readable `[[level=info|warning|error]]` prefix `backend/activity.py` prepends to every activity-log row. Consumed by the Logs page classifier.

**Local Folder**
`%APPDATA%\PDF Extractor V3\Local Folder\`. Root of the synced-PDF workspace. Contains synced PDFs, `Extracted/`, and `Archive/` subfolders.

**Output folder (Box)**
Optional Box folder where V3 uploads the Word/Excel/JSON exports after a successful local extraction. Configured via `box.output_folder_id`. Leave blank to skip Box upload.

**PDF password (`pdf_password`)**
The shared password used by the vendor to encrypt every PDF report. Stored masked in the Settings API.

**Pending / Completed**
The two tracking statuses. Pending = registered but not extracted. Completed = extraction succeeded and outputs are written. No intermediate state exists — failed extractions leave rows at Pending.

**Preload script**
`electron/preload.js`. Runs in the renderer process with `contextIsolation: true` and exposes a minimal API (`electronAPI.getApiPort`, `getBackendLogPath`, `icaLogin`) via `contextBridge`.

**Priming (of ICA)**
The one-time operation that sends `bee_prompt.md` as the first PROMPT on a new chat_id, so subsequent turns are grounded in the Bee persona. Success is recorded in `config.ica.system_prompt_chat_id`.

**Ref number (`ref_number`)**
The identifier used to key export folders and log rows. Equal to `case_reference` from the parsed PDF when present; otherwise `Path(fname).stem`.

**Renderer**
The Electron renderer process — a Chromium instance that hosts the React app. Communicates with the backend over `127.0.0.1:<port>` HTTP + WebSocket.

**Source folder (Box)**
The Box folder where vendors upload new reports. V3 lists this folder during Sync. Configured via `box.folder_id`.

**Splash**
The dark data-URI HTML page loaded into the main BrowserWindow immediately at startup, replaced by the React renderer once the backend health-check passes.

**SSE (Server-Sent Events)**
The transport used by connection tests (Box, ICA, ICA-init). One HTTP GET returns a text/event-stream response with a series of `data: {...}` events, each describing one step of the test.

**System prompt chat ID (`system_prompt_chat_id`)**
The chat_id that has been primed with `bee_prompt.md`. Compared against the current `chat_id` to compute the Settings page **Primed / Not yet primed** state.

**Team ID / Team name (`team_id`, `team_name`)**
ICA team identifiers sent as request headers (URL-encoded). Captured during browser-assisted sign-in.

**Tracking DB / tracking store**
The `tracking_files` SQLite table. One row per known PDF, keyed by relative path.

**Trusted chat_id**
A `chat_id` that has been observed on a `/entries` POST — i.e., the user actually submitted a prompt on that chat. Only trusted chat_ids are persisted; provisional ones (seen on metadata/config URLs) are discarded on window close.

**Two-POST flow**
ICA's chat submission pattern: first POST a `type: PROMPT` entry, then POST a `type: ANSWER` entry carrying `content.promptEntryId` back-referencing the prompt. The second request returns the streamed answer as `text/event-stream` with chunks prefixed `answer: `.

**Uvicorn**
The ASGI server hosting the FastAPI + Socket.IO backend. Binds `127.0.0.1` on a dynamic port (preferred 8765).

**Word / Excel / JSON extracts**
The three outputs produced per extracted PDF. Named `<ref>.docx`, `<ref>.xlsx`, `<ref>.json`. All contain the same structured data — the format is the difference.

**Zustand**
The React state-management library used for `theme`, `chat`, `toast`, and `run` stores.
