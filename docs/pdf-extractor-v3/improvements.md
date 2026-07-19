# PDF Extractor V3 — Observations & Improvement Opportunities

## Summary

V3 represents a significant architectural leap over V1 and V2: a proper REST API, a modern React frontend, real-time streaming, portable distribution, and a GUI-driven settings page. The codebase is well-structured and production-ready for its target use case. The observations below highlight areas for future hardening, scalability improvements, and developer experience enhancements.

---

## 1. Architectural Enhancements

### 1.1 ICA Chat: Polling vs. Streaming
**Observation:** `chat.py → ica_chat()` uses a REST polling loop (GET every 2s, up to 60s / 30 polls) to retrieve ICA responses. This is fragile: if ICA is slow the timeout is hit; if ICA is fast the client waits up to 2s unnecessarily.

**Suggestion:** Investigate whether ICA exposes a Server-Sent Events or WebSocket endpoint. If not, surface the polling timeout as a configurable setting (currently hard-coded at 30 polls × 2s). A progressive backoff (2s, 3s, 5s…) would be more network-friendly.

---

### 1.2 Extraction: No Concurrency Control Beyond a Boolean Flag
**Observation:** `extractor.py` guards against concurrent runs with `_status["running"]`. This is correct for preventing double-runs, but it is a module-level global. If multiple backend processes are ever started (e.g., two dev instances), there is no file-level lock.

**Suggestion:** Add a lock file (`%APPDATA%\PDF Extractor V3\extraction.lock`) so the guard works across processes.

---

### 1.3 Box Upload: No Retry on Transient Failures
**Observation:** `upload_file_to_box()` in `box_client.py` has no retry logic. A transient Box API error (rate limit, 5xx) will permanently fail a file's upload without re-attempting.

**Suggestion:** Add exponential backoff with a configurable `max_retries` (default: 3) around the `client.folder().upload()` and `client.file().update_contents()` calls.

---

### 1.4 Auto-Sync Not Implemented
**Observation:** `config.json` includes `sync.auto_sync_enabled` and `sync.auto_sync_interval_minutes`, and the Settings page exposes them, but the backend has no scheduler that reads these values and triggers sync automatically.

**Suggestion:** Add an `APScheduler` or `threading.Timer` loop in `main.py` that calls `sync.sync_box_to_local()` on the configured interval when `auto_sync_enabled` is true.

---

### 1.5 Chat: Synchronous ICA Call Blocks FastAPI Worker
**Observation:** `chat.py → ica_chat()` uses `urllib.request.urlopen()` with a 60s timeout inside a FastAPI route handler. This blocks a Uvicorn worker thread for up to a minute.

**Suggestion:** Convert `ica_chat()` to an async function using `httpx.AsyncClient` (already a transitive dependency via FastAPI), or run it in `asyncio.get_event_loop().run_in_executor()`.

---

## 2. Codebase Observations

### 2.1 `box_client.py` Hard-Codes a Legacy Path
**Observation:** `_resolve_jwt_path()` includes a search candidate pointing to `WatsonX Challenge - Web/` — a leftover from when V2 and the web app shared a single JWT file. This creates an implicit coupling between V3 and an unrelated sub-project.

**Suggestion:** Remove the `WatsonX Challenge - Web/` fallback path. V3 should only look in `BASE_DIR` (dev) and `_data_dir()` (production). The correct path is already managed by `config.py → jwt_config_path()`.

---

### 2.2 `insights.py` References `LOG_HISTORY_DIR` Before It Is Defined
**Observation:** `get_log_history()` uses `LOG_HISTORY_DIR` as an unresolved name (the function expects it as a module-level variable, but `config.py` exposes `_log_history_dir()` as a callable). This would raise a `NameError` at runtime if `get_log_history()` is called and the variable is not injected.

**Suggestion:** Replace `LOG_HISTORY_DIR.exists()` with `_log_history_dir().exists()` inside `get_log_history()` to call the function-based accessor consistently.

---

### 2.3 No Input Validation on `POST /api/view/open`
**Observation:** `viewer.py → view_open()` accepts an arbitrary `path` string and calls `os.startfile(path)`. While this only affects local files, a malicious request to the local backend could open unexpected executables.

**Suggestion:** Validate that the provided path is within `extracted_folder()` before calling `os.startfile()`. Add a `Pydantic` model for the request body instead of a raw `dict`.

---

### 2.4 `chat.py` Contains Two Separate Report-Matching Functions
**Observation:** `skill_lookup_report()` and `_find_report_files()` both search the JSON extracts directory for reports matching a query. They use similar but different matching logic and result shapes.

**Suggestion:** Consolidate into a single `find_reports(query)` function that returns a unified result structure. `skill_lookup_report()` would then be a formatter on top of that.

---

### 2.5 `build_extract_folder()` Is Called Three Times Per File
**Observation:** In `extractor.py`, `build_extract_folder()` is called once for each of `word_root`, `csv_root`, and `json_root` — all with the same `now` timestamp — so it constructs the same date-based path three times.

**Suggestion:** Call it once and reuse the `Path` components:
```python
daily_folder = build_extract_folder_base(now)  # returns year/month/week/date parts
word_daily = word_root / daily_folder
csv_daily  = csv_root  / daily_folder
```

---

## 3. Security Observations

### 3.1 ICA Cookie Stored in Plaintext
**Observation:** `full_cookie` is stored as plaintext in `config.json`. ICA session cookies contain authentication tokens with privileged access to IBM internal services.

**Suggestion:** Encrypt the cookie at rest using the Windows Data Protection API (`win32crypt.CryptProtectData`) or the `keyring` library. The Settings page can still show a masked placeholder without reading the raw value.

---

### 3.2 CORS Allows All Origins
**Observation:** `main.py` configures `allow_origins=["*"]` on the FastAPI CORS middleware and `cors_allowed_origins="*"` on the SocketIO server. Since the backend only listens on `127.0.0.1`, this is low-risk, but any page loaded in Chromium could make authenticated requests.

**Suggestion:** Restrict allowed origins to `null` (Electron file:// pages) and the Vite dev server URL for development: `["null", "http://localhost:5173"]`.

---

## 4. Documentation Gaps

| Gap | Recommendation |
|---|---|
| No JSDoc/TSDoc on React components | Add component-level comments to `Sidebar.tsx`, `ChatBubble.tsx`, and all page components |
| No OpenAPI descriptions on route parameters | Add `description=` to FastAPI route parameters and `Query()` annotations for `?period=` |
| `pdf_text_extractor.py` has no standalone documentation | Document its public API (`open_and_decrypt_pdf`, `build_structured_json`, `export_to_*`) in the shared docs |
| No changelog or migration guide from V2 → V3 | A `MIGRATION.md` would help users running V2 understand how to move their `config.json` and Box setup |
| Build instructions in `BUILD_PROMPT.md` are not surfaced in `README.md` | Merge or cross-link the detailed build steps |

---

## 5. Patterns Worth Noting

### Good Patterns
- **Module-level `set_sio()` injection** in `scanner.py`, `sync.py`, `extractor.py` — clean dependency injection without globals threading through every function.
- **Atomic config writes** in `config.py → write_config()` using `os.replace()` — prevents corrupt JSON on unexpected shutdown.
- **Secret masking on read** in `settings.py → _mask_config()` — secrets never travel to the frontend even if the browser DevTools are open.
- **Trusted chat_id guard** in `electron/main.js → icaBrowserLogin()` — prevents the "(ICA did not respond in time)" failure caused by uninitialized thread IDs.
- **Hallucination detection** in `chat.py → _is_hallucinated_reply()` — defensive AI output validation before presenting to users.

### Anti-Patterns to Avoid Expanding
- **`_SKIP_PORTS` duplicated** in both `ports.py` and `electron/main.js` — this is intentional for the dual Python/Node environment, but a comment explaining the duplication would prevent confusion.
- **`os.startfile()` only works on Windows** — `viewer.py → view_open()` and `chat.py → _skill_open_report()` will silently fail on macOS/Linux. This is documented by the Windows-only distribution target, but worth a `sys.platform` guard and a clear error message.
