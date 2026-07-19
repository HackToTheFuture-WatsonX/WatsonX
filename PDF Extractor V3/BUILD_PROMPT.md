# PDF Extractor V3 — Build Prompt

## Context

This project is `PDF Extractor V3`, located at `c:\work\werud\WatsonX\PDF Extractor V3\`.

It is a **fully portable Electron desktop application** that replaces the Tkinter UI of `PDF Extractor V2` with a modern React + TypeScript + Vite + Tailwind CSS frontend, backed by a standalone FastAPI + Flask-SocketIO Python server. V3 is completely self-contained — V2 is untouched.

All source code is already written and present in the folder. **The only remaining task is to produce the runnable `.exe` files.**

---

## What Is Already Built

### Backend (`PDF Extractor V3/backend/`)
All 13 Python files are written and syntax-clean:

| File | Purpose |
|---|---|
| `main.py` | FastAPI + SocketIO entry point. Accepts `--port` and `--data-dir` CLI args. |
| `config.py` | Config/path helpers. `set_data_dir()` makes all paths point to `%APPDATA%\PDF Extractor V3\` when running as a packaged exe. |
| `tracking.py` | `load_tracking()` / `save_tracking()` for `tracking_db.json`. |
| `ports.py` | `find_free_port(8765, max=20)` — probes with `socket.bind()`, skips ports 5000, 8080, 47321. |
| `events.py` | SocketIO event name constants. |
| `scanner.py` | `POST /api/scan/run`, `GET /api/scan/files` |
| `sync.py` | `POST /api/sync/run` — Box sync with live `sync:log` SocketIO events |
| `box_client.py` | Box JWT client (`JWTAuth`, `Client` from `boxsdk==3.9.2`) |
| `extractor.py` | `POST /api/extract/run` — full pipeline with `extract:progress` / `extract:result` events. Uses direct `import pdf_text_extractor` (NOT importlib) so PyInstaller works. |
| `viewer.py` | `GET /api/view/files`, `POST /api/view/open` |
| `insights.py` | `GET /api/insights?period=` |
| `chat.py` | `POST /api/chat/send` — full ICA chat routing + skill lookup |
| `pdf_text_extractor.py` | Copied from V2 — PDF decrypt/parse/export |

### Frontend (`PDF Extractor V3/frontend/`)
React 18 + Vite + Tailwind. All 7 pages written: Home, Sync, Scan, Extract, View, Insights, Chat.

### Electron Shell (`PDF Extractor V3/electron/`)
- `main.js` — finds free port with Node `net.createServer`, spawns `backend.exe --port X --data-dir %APPDATA%/PDF Extractor V3`, polls `/api/health`, creates window, injects `window.__V3_API_PORT__`.
- `preload.js` — context bridge.
- `package.json` — electron-builder config producing both NSIS installer and portable `.exe`.

### Build Scripts
- `backend.spec` — PyInstaller spec with all hidden imports.
- `build_backend.py` — runs PyInstaller, copies output to `electron/resources/backend/`.
- `build_all.bat` — full pipeline: frontend build → PyInstaller → electron-builder.
- `requirements-build.txt` — all Python deps + PyInstaller.

---

## Goal: Produce the `.exe` Files

Run the full build pipeline to produce two distributable files:

```
PDF Extractor V3/electron/dist/PDF-Extractor-V3-Setup-3.0.0.exe      (NSIS installer)
PDF Extractor V3/electron/dist/PDF-Extractor-V3-Portable-3.0.0.exe   (portable single exe)
```

Both must be **completely self-contained** — no system Python, Node.js, or npm required to run them.

---

## Build Steps (in order)

### Step 1 — Install Python build dependencies

```cmd
cd "PDF Extractor V3"
pip install -r requirements-build.txt
```

Required packages (check each imports correctly before proceeding):
- `pyinstaller` — `python -c "import PyInstaller; print(PyInstaller.__version__)"`
- `PyMuPDF` — `python -c "import fitz; print(fitz.__version__)"`
- `python-docx` — `python -c "import docx; print('OK')"`
- `boxsdk==3.9.2` — `python -c "from boxsdk import JWTAuth, Client; print('OK')"`
- `flask` — `python -c "import flask; print(flask.__version__)"`
- `flask-socketio` — `python -c "import flask_socketio; print('OK')"`
- `python-socketio` — `python -c "import socketio; print('OK')"`
- `fastapi`, `uvicorn`, `pydantic`, `openpyxl` — already installed

> **Important:** `boxsdk` must be version **3.x** (specifically 3.9.2), NOT 10.x (which is `box_sdk_gen` — different API).
> If `pip install "boxsdk[jwt]==3.9.2"` fails to place the `boxsdk/` folder correctly, install it manually:
> 1. `pip download "boxsdk[jwt]==3.9.2" -d C:\Temp\boxpkgs2`
> 2. Extract `boxsdk-3.9.2-py2.py3-none-any.whl` (it's a zip) into Python's `site-packages/`
> 3. Also extract `attrs` wheel (both `attr/` and `attrs/` directories needed)

Verify all packages import before moving to Step 2:
```cmd
python -c "from boxsdk import JWTAuth, Client; import flask; import socketio; import flask_socketio; import fitz; import docx; import PyInstaller; import fastapi; import uvicorn; print('ALL OK')"
```

### Step 2 — Install Node dependencies

```cmd
cd "PDF Extractor V3\frontend"
npm install

cd "..\electron"
npm install
cd ..
```

### Step 3 — Build the React frontend

```cmd
cd "PDF Extractor V3\frontend"
npm run build
```

This outputs the built React app to `PDF Extractor V3/electron/renderer/`.

Verify: `PDF Extractor V3/electron/renderer/index.html` must exist.

### Step 4 — Build the Python backend with PyInstaller

```cmd
cd "PDF Extractor V3"
python build_backend.py
```

This:
1. Runs PyInstaller using `backend.spec`
2. Copies the output to `PDF Extractor V3/electron/resources/backend/`
3. Copies `config.json` template to the same location

Verify: `PDF Extractor V3/electron/resources/backend/backend.exe` must exist.

> If PyInstaller fails with missing module errors, add them to the `hiddenimports` list in `backend.spec` and retry.
> If `backend.exe` crashes on launch, test it directly:
> ```cmd
> "PDF Extractor V3\electron\resources\backend\backend.exe" --port 8765
> ```
> Then check `http://127.0.0.1:8765/api/health` returns `{"status":"ok"}`.

### Step 5 — Package with electron-builder

```cmd
cd "PDF Extractor V3\electron"
npm run dist
```

This produces both targets in `PDF Extractor V3/electron/dist/`:
- `PDF-Extractor-V3-Setup-3.0.0.exe` — NSIS installer
- `PDF-Extractor-V3-Portable-3.0.0.exe` — portable single exe

Verify both files exist and are > 100 MB.

---

## How the Portable App Works at Runtime

```
User double-clicks PDF-Extractor-V3-Portable-3.0.0.exe
  │
  ├─ Electron main process starts
  │
  ├─ Finds free port (starting at 8765, skipping 5000/8080/47321)
  │
  ├─ On first launch: copies config.json template to
  │     %APPDATA%\PDF Extractor V3\config.json
  │
  ├─ Spawns: resources/backend/backend.exe --port <N> --data-dir "%APPDATA%\PDF Extractor V3"
  │     (self-contained Python server — no system Python needed)
  │
  ├─ Polls http://127.0.0.1:<N>/api/health every 500ms (30s timeout)
  │
  ├─ On health OK: opens Electron window loading renderer/index.html
  │     Injects window.__V3_API_PORT__ = <N>
  │
  └─ On quit: kills backend.exe process
```

---

## Configuration (after first launch)

All user data lives at `%APPDATA%\PDF Extractor V3\`:

```
config.json           ← fill in credentials (auto-created as template on first launch)
box_jwt_config.json   ← place your Box JWT JSON file here
tracking_db.json      ← auto-managed
Log History\          ← extraction logs
Local Folder\         ← synced PDFs and extracted outputs
```

Edit `config.json`:
```json
{
  "pdf_password": "YOUR_PDF_PASSWORD",
  "box": {
    "folder_id":         "YOUR_SOURCE_FOLDER_ID",
    "archive_folder_id": "YOUR_ARCHIVE_FOLDER_ID",
    "output_folder_id":  "YOUR_OUTPUT_FOLDER_ID",
    "jwt_config_file":   "box_jwt_config.json"
  },
  "ica": {
    "full_cookie": "YOUR_FULL_BROWSER_COOKIE_STRING",
    "team_id":     "YOUR_TEAM_UUID",
    "team_name":   "Your%20Team%20Name",
    "chat_id":     "YOUR_CHAT_UUID",
    "base_url":    "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat"
  },
  "local": {
    "local_folder":     "Local Folder",
    "extracted_folder": "Local Folder/Extracted",
    "archive_folder":   "Local Folder/Archive"
  },
  "sync": {
    "auto_sync_enabled": false,
    "auto_sync_interval_minutes": 30
  },
  "settings": {
    "search_subfolders": true,
    "overwrite_existing_exports": false
  }
}
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Desktop shell | Electron + electron-builder | Produces real `.exe`, bundles Chromium — no browser needed |
| Python bundling | PyInstaller one-folder build → `backend.exe` | Bundles Python interpreter + all packages — no system Python on target |
| Portable vs installer | Both targets via electron-builder | Installer for managed machines; portable for USB / shared folders |
| Backend API | FastAPI + python-socketio (threading mode) | REST for data + WebSocket for live log streaming |
| Real-time events | Flask-SocketIO + socket.io-client | `sync:log`, `scan:progress`, `extract:progress`, `extract:result` |
| Port resolution | `find_free_port(8765)` via socket probe | Avoids conflicts with ports 5000, 8080, 47321 already used in workspace |
| User data | `%APPDATA%\PDF Extractor V3\` via `--data-dir` | Config/DB/logs in writable location, not inside read-only app bundle |
| Box SDK version | `boxsdk==3.9.2` (NOT 10.x) | V3 backend uses same `JWTAuth`/`Client` API as V2 |
| Theme | Always-dark sidebar + toggleable dark/light main content | Sidebar identity stays consistent; user preference for main area |

---

## Project File Map

```
PDF Extractor V3/
├── backend/
│   ├── main.py                 FastAPI entry, --port + --data-dir args
│   ├── config.py               set_data_dir() + all path helpers
│   ├── tracking.py             tracking_db.json load/save
│   ├── ports.py                find_free_port()
│   ├── events.py               SocketIO event name constants
│   ├── scanner.py              /api/scan/*
│   ├── sync.py                 /api/sync/* + live SocketIO logs
│   ├── box_client.py           JWTAuth, Client, upload helpers
│   ├── extractor.py            /api/extract/* + progress events
│   ├── viewer.py               /api/view/*
│   ├── insights.py             /api/insights
│   ├── chat.py                 /api/chat/send + ICA routing
│   ├── pdf_text_extractor.py   PDF decrypt/parse/export (from V2)
│   ├── config.json             Template — copied to %APPDATA% on first launch
│   └── requirements.txt        Runtime Python deps
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx             Router + sidebar + theme toggle
│   │   ├── pages/              Home, Sync, Scan, Extract, View, Insights, Chat
│   │   ├── components/         Sidebar, ThemeToggle, ui/Button|Card|Badge|Spinner|EmptyState
│   │   ├── hooks/              useApi.ts, useSocket.ts
│   │   ├── store/theme.ts      Zustand dark/light (persisted to localStorage)
│   │   └── types/index.ts      TypeScript interfaces
│   ├── tailwind.config.js      Custom colour tokens (sidebar, accent, card, bg, etc.)
│   ├── vite.config.ts          Proxy /api + /socket.io to backend port
│   └── package.json
│
├── electron/
│   ├── main.js                 Port finder, spawn backend.exe, health poll, window
│   ├── preload.js              contextBridge → window.electronAPI.getApiPort()
│   ├── package.json            electron-builder: nsis + portable targets
│   └── resources/backend/      ← PyInstaller output goes here (Step 4)
│
├── backend.spec                PyInstaller spec (all hiddenimports listed)
├── build_backend.py            Runs PyInstaller → copies to electron/resources/backend/
├── build_all.bat               Full pipeline (Steps 3–5 in one command)
├── requirements-build.txt      Runtime deps + pyinstaller
├── start_v3.py                 Dev-mode launcher (no build needed)
└── README.md                   Full documentation
```

---

## Troubleshooting

**`No module named 'boxsdk'` at PyInstaller time**
→ Verify `from boxsdk import JWTAuth, Client` works in your Python session first. The version must be 3.x.

**`backend.exe` exits immediately**
→ Run it directly in a terminal: `backend.exe --port 8765` and read the error output.
→ Likely a missing hidden import — add it to `hiddenimports` in `backend.spec` and rebuild.

**Electron window shows blank / can't connect to backend**
→ Open DevTools (F12) in the Electron window and check console for the actual API port.
→ Verify `window.__V3_API_PORT__` is set: run `window.__V3_API_PORT__` in the DevTools console.

**`npm run build` fails**
→ Make sure `npm install` was run in `frontend/` first.
→ Check TypeScript errors with `npx tsc --noEmit`.

**`electron-builder` fails with "file not found: renderer/index.html"**
→ Step 3 (frontend build) must complete first — it outputs to `electron/renderer/`.

**`electron-builder` fails with "file not found: resources/backend/backend.exe"**
→ Step 4 (PyInstaller) must complete first.
