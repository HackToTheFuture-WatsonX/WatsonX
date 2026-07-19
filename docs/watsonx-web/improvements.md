# WatsonX Challenge - Web App — Improvements

## Web App-Specific Issues

### IMP-WEB-01: Extraction State is a Module-Level Global
**Current:** `_extract_running` and `_extract_result` are module-level global variables in `app.py`.

**Problem:**
- If the server restarts mid-extraction, the result is lost
- Multiple simultaneous users see the same global state — user A can see user B's extraction result
- There is no extraction history (only the most recent result is stored)

**Recommendation:** Store extraction state per-run in the SQLite tracking DB (see shared IMP-03). Each extraction creates a `run_id`; clients poll by `run_id`. Previous results are queryable.

**Effort:** Medium.

---

### IMP-WEB-02: No Authentication / Access Control
**Current:** The web app has no login screen. Anyone with network access to port 5000 can scan, trigger extraction, read report data, and download files.

**Problem:** Sensitive background check report data is exposed to anyone on the local network (or the internet, if the server is publicly accessible).

**Recommendation:** Add HTTP Basic Auth or session-based auth as a minimum. For a production deployment, integrate with IBM's SSO / IAM. At minimum, add a `require_auth` config flag with a local username/password.

**Effort:** Low (Basic Auth) to High (SSO integration).

---

### IMP-WEB-03: `box_jwt_config.json` Contains Sensitive Private Keys
**Current:** The JWT config file contains RSA private keys for the Box Service Account. If accidentally committed to git or served via the web, it would allow full Box access.

**Problem:** The file has no runtime protection beyond "don't commit it." The web app's `send_file()` endpoint could theoretically serve it if an attacker crafts the right path.

**Recommendation:**
1. Ensure `box_jwt_config.json` is in `.gitignore` (verify this is already the case)
2. Add a path validation check in `/api/download/<path>` to block requests for `.json` files at the app root
3. Consider reading JWT credentials from environment variables rather than a file

**Effort:** Low (gitignore + path validation) to Medium (env vars).

---

### IMP-WEB-04: `/api/download/<path>` Has No Path Traversal Protection
**Current:** The download endpoint reconstructs a file path from URL segments and serves it directly.

**Problem:** A crafted URL like `/api/download/../config.json` could serve the credentials file.

**Recommendation:** Validate that the resolved path starts with one of the known output directories (`Word Extracts/`, `CSV Extracts/`, `JSON File Extracts/`). Reject any path that resolves outside these roots.

**Effort:** Low.

---

### IMP-WEB-05: ICA Cookie Credentials Committed to `config.json`
**Current:** The `ica.full_cookie` field in the repo's `config.json` contains real ICA session tokens.

**Problem:** Anyone with read access to the repository has valid ICA credentials.

**Recommendation:** Rotate the ICA cookie immediately. Add `config.json` to `.gitignore` (or add a `config.example.json` with placeholder values and exclude the real file). Store secrets in environment variables for any deployment beyond local development.

**Effort:** Low (immediate) — rotate the token now.

---

### IMP-WEB-06: Extraction Polling is Fixed-Interval
**Current:** The frontend polls `GET /api/extract/status` at a fixed interval (e.g. every 2 seconds) for the duration of extraction.

**Problem:** Unnecessary repeated HTTP requests during extraction; no real-time per-file progress.

**Recommendation:** Replace polling with **Server-Sent Events (SSE)** — the server pushes progress updates as each file completes. Flask supports SSE via `Response(stream_with_context(...))`. This eliminates polling overhead and gives users real-time per-file feedback.

**Effort:** Medium.

---

## Shared Improvements (also apply to Web App)

- **IMP-02:** Centralize `config.json` schema
- **IMP-03:** Replace `tracking_db.json` with SQLite
- **IMP-05:** Make extractor path configurable (not hardcoded to `../PDF Extractor/`)
- **IMP-06:** Add `validate_config()` startup validation
- **OBS-01:** Move duplicated `build_extract_folder()` and `write_extraction_log()` into the shared engine
- **OBS-04:** Add unit tests for parser logic

---

## Feature Suggestions (Web App)

### FEAT-WEB-01: Multi-User Job Queue
Replace the single-extraction lock with a proper job queue (e.g. using Python's `queue.Queue`). Multiple users could queue extraction runs that execute sequentially, with each user seeing only their own job's status.

### FEAT-WEB-02: Report Search Page
A dedicated `/search` page with a name/ref search box that returns rich report cards directly — without needing to go through the AI chat interface.

### FEAT-WEB-03: Automated Report Delivery
After extraction, automatically email a summary (subject names, case references, overall statuses) to a configured recipient list. This eliminates the need for users to check the dashboard for new results.

### FEAT-WEB-04: Webhook / Box Event Integration
Instead of polling Box on demand, subscribe to Box webhook events for the source folder. When a new PDF is uploaded to Box, the webhook fires and the server automatically scans and optionally extracts — zero user interaction required.
