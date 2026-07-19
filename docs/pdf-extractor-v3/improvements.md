# PDF Extractor V3 — Observations & Improvement Opportunities

## Summary

V3 represents a major architectural leap: a proper REST API, a modern React frontend, real-time SocketIO streaming, portable distribution, a GUI settings page, and — most significantly in the current codebase — a **SQLite single source of truth** replacing three loose JSON files. The codebase is well-structured and production-ready for its target use case. The observations below highlight areas for further hardening, scalability improvements, and developer experience enhancements.

---

## 1. Architectural Enhancements

### 1.1 Auto-Sync Not Implemented
**Observation:** `config.json` (now the `config` DB table) exposes `sync.auto_sync_enabled` and `sync.auto_sync_interval_minutes`, and the Settings page shows these toggles — but the backend has no scheduler that acts on them. The switches appear to work but have no effect.

**Suggestion:** Add an `APScheduler` or a `threading.Timer` loop in `main.py` that calls `sync.sync_box_to_local()` on the configured interval when `auto_sync_enabled` is `true`. Re-read config from the DB on each tick so interval changes take effect without restarting.

---

### 1.2 ICA Chat: Polling vs. Streaming
**Observation:** `chat.py → ica_chat()` uses a REST polling loop (GET every 2 s, up to 60 s / 30 polls) to retrieve ICA responses. This blocks a FastAPI worker thread for up to a minute per chat message.

**Suggestion:** Run `ica_chat()` in `asyncio.get_event_loop().run_in_executor()` or convert it to `httpx.AsyncClient` to avoid tying up a synchronous Uvicorn worker. Also expose the 30-poll / 60-s timeout as a `config.ica.poll_timeout_seconds` field rather than a hard-coded constant.

---

### 1.3 Box Upload: No Retry on Transient Failures
**Observation:** `upload_file_to_box()` has no retry logic. A transient Box API error (rate limit, 5xx) permanently fails the file's upload step with no re-attempt.

**Suggestion:** Wrap `client.folder().upload()` and `client.file().update_contents()` in a small exponential-backoff retry loop (default `max_retries=3`, doubling delay starting at 2 s).

---

### 1.4 Extraction Concurrency Guard Is Process-Local
**Observation:** `extractor.py` uses `_status["running"]` (a module-level dict) as a concurrency guard. This works for a single process but does not protect against two separate invocations of `backend.exe` writing to the same database simultaneously.

**Suggestion:** Complement the in-process flag with a `BEGIN EXCLUSIVE TRANSACTION` in `db.tracking_replace_all()` during the extraction write, or write a `running_pid` value to a `locks` table and check it on startup.

---

### 1.5 `tracking_replace_all` Replaces the Entire Table
**Observation:** `db.tracking_replace_all()` issues `DELETE FROM tracking_files` then bulk-inserts all rows. For a large tracking database (hundreds of files) this is unnecessary I/O — only changed rows need to be written.

**Suggestion:** Replace with `INSERT INTO tracking_files ... ON CONFLICT(rel_key) DO UPDATE SET ...` (SQLite UPSERT) for updates, and a targeted `DELETE WHERE rel_key = ?` for purges. This reduces lock time and write amplification.

---

## 2. Codebase Observations

### 2.1 `box_client.py` Still Carries a Legacy Path Fallback
**Observation:** `_resolve_jwt_path()` still searches `WatsonX Challenge - Web/` as a fallback for on-disk JWT files. This couples V3 to a sibling sub-project and will silently succeed with the wrong JWT if one happens to exist there.

**Suggestion:** Remove the `WatsonX Challenge - Web/` candidate entirely. New installs use `db.jwt_config_get()` exclusively; legacy on-disk fallback should only look in `BASE_DIR` (development) and `_data_dir()` (production).

---

### 2.2 `_ica_*.py` Diagnostic Files Left in `backend/`
**Observation:** The `backend/` folder contains 12 `_ica_diag*.py`, `_ica_probe*.py`, `_ica_stream*.py` files that are development diagnostic scripts, not part of the application. They are included in the PyInstaller build (`backend.spec`) and inflate the `.exe` size.

**Suggestion:** Move them to a `backend/_dev_tools/` directory excluded from PyInstaller, or add them to `.gitignore` and delete from the working directory.

---

### 2.3 No Input Validation on `POST /api/view/open`
**Observation:** `viewer.py → view_open()` accepts an arbitrary `path` string and calls `os.startfile(path)`. A malicious request to the local backend (e.g., from another page loaded in the Electron window) could open unexpected executables.

**Suggestion:** Validate that the provided path resolves to a child of `extracted_folder()` before calling `os.startfile()`. Also model the request body with Pydantic (`class OpenRequest(BaseModel): path: str`) instead of `body: dict`.

---

### 2.4 Chat Has Two Separate Report-Search Functions
**Observation:** `skill_lookup_report()` and `_find_report_files()` both search the `JSON File Extracts/` directory for matching reports but use different matching logic and return different shapes.

**Suggestion:** Consolidate into a single `find_reports(query: str) -> list[dict]` returning a uniform `[{subject, ref, json_path, word_path, excel_path}]` shape. The two callers become formatters on top of this shared function.

---

### 2.5 ICA `full_cookie` Stored in Plaintext in SQLite
**Observation:** The `full_cookie` value (a full browser session cookie granting access to IBM internal services) is stored as a plaintext JSON string in the `config` table. Anyone with read access to `pdf_extractor_v3.db` can extract it.

**Suggestion:** Encrypt the cookie at rest using the Windows Data Protection API (`win32crypt.CryptProtectData`) or the `keyring` library, keyed to the current Windows user account. The Settings page can still display a masked placeholder.

---

## 3. Security Observations

### 3.1 CORS Allows All Origins
**Observation:** `main.py` sets `allow_origins=["*"]` on FastAPI's CORS middleware and `cors_allowed_origins="*"` on SocketIO. Since the backend only listens on `127.0.0.1` this is low-risk, but any `file://` page loaded in the Electron window could make requests to the backend.

**Suggestion:** Restrict allowed origins to `["null"]` (for Electron `file://` pages) and `["http://localhost:5173"]` (Vite dev server) with an environment flag for development vs. production.

---

### 3.2 `db.py` Opens Per-Call Connections Without a Pool
**Observation:** `db._connect()` opens a new `sqlite3.connect()` for every call. Under high-frequency concurrent access (many SocketIO events + REST calls simultaneously) this could exhaust file descriptors.

**Suggestion:** For the current single-user desktop use case this is fine. If V3 ever serves multiple users, introduce a `threading.local()` connection-per-thread pattern or a simple connection pool.

---

## 4. Documentation Gaps

| Gap | Recommendation |
|---|---|
| No JSDoc/TSDoc on React components | Add component-level comments to `Sidebar.tsx`, `ChatBubble.tsx`, all page components |
| No OpenAPI descriptions on route parameters | Add `description=` and `Query()` annotations to `?period=` parameters in `insights.py` |
| `pdf_text_extractor.py` not documented in V3 context | Add a [Parsing Engine](parsing-engine.md) section covering the public API (`open_and_decrypt_pdf`, `build_structured_json`, export functions) |
| No build / release guide | Document the `build_all.bat` pipeline, version bump procedure, and how to verify the portable `.exe` |
| No migration guide from V2 → V3 | A `MIGRATION.md` explaining the switch from `config.json` + `tracking_db.json` to SQLite would help users upgrading from V2 |

---

## 5. Patterns Worth Noting

### Good Patterns
- **SQLite WAL mode** with per-call connections — safe for concurrent background threads without a complex connection pool
- **`db.init_db()` called once at startup** (`main.py` after `set_data_dir`) — clean initialization ordering before any router imports touch the DB
- **`tracking.py` + `config.py` as thin wrappers** over `db.py` — all existing call sites keep working unchanged; the persistence layer is swapped transparently
- **Module-level `set_sio()` injection** — clean dependency injection without global imports threading through every module
- **Atomic config writes** via `config_replace_all()` inside a single transaction — no corrupt state on unexpected shutdown
- **Secret masking on read** — `pdf_password` and `full_cookie` never travel to the frontend even with DevTools open
- **Trusted chat_id guard** in `electron/main.js` — prevents the "(ICA did not respond in time)" failure from uninitialized thread IDs
- **Hallucination detection** before presenting ICA replies — defensive output validation

### Anti-Patterns to Avoid Expanding
- **`os.startfile()` is Windows-only** — `viewer.py` and `chat.py` will silently fail on macOS/Linux (intentional given the Windows distribution target, but worth a `sys.platform` guard and error message)
- **`_SKIP_PORTS` duplicated** in `ports.py` and `electron/main.js` — necessary for dual Python/Node environments but warrants a comment to prevent drift
- **`chat.py` mixes concerns** — intent routing, skill handlers, ICA HTTP client, hallucination detection, and SSE test generators are all in one 700-line file; consider splitting into `chat_router.py`, `chat_skills.py`, and `ica_client.py`
