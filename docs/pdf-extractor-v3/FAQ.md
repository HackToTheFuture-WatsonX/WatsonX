# FAQ

Frequently asked, concretely answered. Ordered from most common to least.

---

## Installation & Distribution

### Do I need Python installed?
No. The portable exe bundles a full Python interpreter and every PyPI dependency via PyInstaller.

### Do I need Node.js installed?
No. The portable exe bundles Electron (which includes Node.js + Chromium) and the pre-built React renderer.

### Does the installer differ from the portable exe?
Functionally, no. The NSIS installer writes to `C:\Users\<you>\AppData\Local\Programs\PDF Extractor V3\` and creates Start Menu / Desktop shortcuts. The portable exe runs from wherever you drop it. Both write user data to the same `%APPDATA%\PDF Extractor V3\` location.

### Can I run V3 from a USB drive?
Yes — that's what the portable target is for. Note that user data still lives at `%APPDATA%\PDF Extractor V3\` on the host machine, not on the USB drive.

### Is V3 signed?
Not currently. `electron-builder` is configured with `"sign": null`. Windows SmartScreen may warn on first launch. See [Roadmap.md](Roadmap.md).

### Can I run V3 on macOS or Linux?
Not today. `electron-builder` only targets `--win`. macOS/Linux packaging is on the roadmap.

---

## First-Run & Setup

### Where does V3 store data?
`%APPDATA%\PDF Extractor V3\`. The single SQLite database (`pdf_extractor_v3.db`) holds config, tracking, JWT config, and activity logs. The `Local Folder/` subdirectory holds synced PDFs and their exports.

### Where do I get the Box JWT JSON?
`app.box.com/developers/console` → your app → **Configuration** → **App Settings** → **Generate a Public/Private Keypair**. The download is a `_config.json` file — that's the whole thing V3 wants.

### Where do I get Box folder IDs?
Open the folder in Box in a browser. The URL's numeric segment (e.g. `.../folder/1234567890`) is the folder ID.

### What are the "source", "archive", and "output" folders for on Box?
- **Source** — where the vendor uploads new encrypted PDFs.
- **Archive** — where V3 moves the source after successful download.
- **Output** — where V3 uploads the Word/Excel/JSON exports (optional; leave blank to skip Box upload).

### Why does the ICA sign-in open a *separate* browser window?
The V3 renderer is Chromium locked to `file://`; it cannot host third-party auth. The Electron main process opens a real browser window against `servicesessentials.ibm.com`, watches the authenticated traffic, and extracts credentials directly from the cookie jar (including HttpOnly cookies that JavaScript can't see).

### What does "primed" mean for ICA?
It means `backend/prompt/bee_prompt.md` has been sent as the first PROMPT on the currently-configured `chat_id`. The chat now knows who Bee is and how she should behave. See [Business-Rules.md](Business-Rules.md#br-8-ica-priming-tied-to-chat-id).

---

## Running the Pipeline

### Why did Sync report "0 downloaded, 0 skipped, 0 failed"?
The Box source folder is empty (or every file is already present locally). This is Info, not Error — see [Business-Rules.md](Business-Rules.md#br-10-empty-batch-sync-is-info-not-error).

### Why is my file stuck at Pending after extraction?
The extraction threw an exception — check the Logs page for a row keyed by the filename stem, level Error. Common causes: wrong PDF password, corrupted PDF, unsupported layout. See [Troubleshooting.md](Troubleshooting.md).

### Why does Bee say "I can only answer from our extracted records"?
The reply from ICA matched the hallucination guard patterns (looked like fabricated report content). Bee refuses to make up data. Use `look up <name>` to retrieve real extracted content.

### Can I run Sync and Extract concurrently?
Each is single-instance (guarded by a `_status["running"]` flag). If you click Sync while Sync is running the API returns `{"status": "already_running"}` — the second request is a no-op. Cross-operation concurrency (Sync + Extract) is technically permitted but not recommended.

### Where do the exports go?
`%APPDATA%\PDF Extractor V3\Local Folder\Extracted\` under a dated hierarchy:

```
Extracted/
    Word Extracts/2026/Jul_2026_Extracts/Week_29/2026-07-20/BG-2026-01234/BG-2026-01234.docx
    CSV Extracts/2026/Jul_2026_Extracts/Week_29/2026-07-20/BG-2026-01234/BG-2026-01234.xlsx
    JSON File Extracts/2026/Jul_2026_Extracts/Week_29/2026-07-20/BG-2026-01234/BG-2026-01234.json
```

If a Box output folder ID is configured, the same three files are also uploaded to Box, mirroring the dated subfolder structure.

---

## Data & Persistence

### Where's `config.json`?
There isn't one. V3 stores config as rows in the `config` table of `pdf_extractor_v3.db`. Prior versions used a JSON file.

### Where are the `.log` files?
There aren't any. V3 stores extraction and activity logs as rows in `extraction_logs`. The Logs page is the canonical viewer.

### Can I edit the database directly?
Yes — it's plain SQLite. Close V3 first (WAL mode is safe but concurrent writers are unadvisable). Any tool that speaks SQLite (`sqlite3` CLI, DB Browser for SQLite, DBeaver) will do.

### How do I back up my configuration?
Copy `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db`. That single file contains everything. See [Backup-and-Restore.md](Backup-and-Restore.md).

### How do I reset the app to a clean state?
Delete `%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db` (with V3 closed) and relaunch. Note: this also removes JWT credentials and every tracking row.

---

## Security

### Are secrets encrypted?
Not at rest. `pdf_password`, `ica.full_cookie`, and the Box JWT JSON live in the SQLite DB under Windows file permissions (`%APPDATA%` is per-user). They are always masked (`••••••••`) when returned to the frontend or written to the activity log. See [Security-Model.md](Security-Model.md).

### Does V3 phone home?
No telemetry, no analytics, no automatic update checks. The only outbound HTTPS traffic is to Box and ICA — and only when you click Sync, Test, or Chat.

### Is the API port open to the network?
No. Uvicorn binds `127.0.0.1` only. The port is dynamically chosen (preferred 8765).

---

## Chat & AI

### Does Chat work without ICA?
Yes. Bee has local skills that work entirely offline: `look up`, `sync`, `scan`, `extract`, `file status`, `logs`. Only free-form conversation requires ICA.

### Does V3 use OpenAI / Anthropic / an external LLM?
No. The only AI backend is IBM Consulting Advantage. If you don't configure ICA, Bee runs local rule-based skills only.

### Why did Bee refuse to answer?
Either (1) the hallucination guard triggered — the reply looked like fabricated report data; or (2) ICA credentials are missing — the fallback help menu is shown instead.

---

## Development

### How do I run in dev mode?
```bat
cd "PDF Extractor V3"
python start_v3.py
```
Requires Python 3.12+ and Node.js. See [Environment-Setup.md](Environment-Setup.md).

### How do I contribute a bug fix?
Follow [Developer-Onboarding.md](Developer-Onboarding.md). PRs should include a `[[level=…]]`-appropriate activity-log entry if a new user-visible operation is added.

### Where's the OpenAPI / Swagger doc?
`http://127.0.0.1:<port>/docs` (dev mode). The port is printed on backend startup.

---

## Everything Else

### What's the version?
`3.0.0`. Check `About` menu (or `GET /api/health` returns `{"status": "ok", "version": "3.0.0"}`).

### Where do I file a bug?
See [Bug-Report-Process.md](Bug-Report-Process.md). The Diagnostics panel on the Scan page + the backend log at `%TEMP%\pdf-extractor-v3-backend.log` are almost always the right first attachments.

### Why is this called V3?
V1 (Box OAuth2 + Tkinter) and V2 (local sync + Tkinter) preceded it. V3 rebuilt everything on Electron + React + FastAPI + SQLite. See [Product-Overview.md](Product-Overview.md#what-v3-replaces).
