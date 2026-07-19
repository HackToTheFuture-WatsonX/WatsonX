# PDF Extractor V3 — Implementation Plan

## Top-Level Overview

Build **PDF Extractor V3** — a standalone Electron desktop application that replaces the Tkinter UI of V2 with a modern **React + TypeScript + Vite + Tailwind CSS** frontend, backed by a **FastAPI + Flask-SocketIO** Python server. V3 is completely self-contained inside a new `PDF Extractor V3/` directory; V2 is untouched.

### Port Resolution Strategy

V3 uses a **dynamic port finder** at startup — both in the Python backend and the Electron main process. The logic:

1. Start with preferred port `8765` for FastAPI and `5173` for Vite/Electron renderer
2. Attempt to bind a test socket on that port
3. If the port is already in use, increment by 1 and retry — up to 20 attempts
4. The selected port is written to a temp file (`.v3_port`) in the app directory so Electron and the React app can read it at runtime
5. The React app reads the backend URL from `window.__V3_API_PORT__` injected by Electron's preload, or falls back to reading `.v3_port` via a local IPC call

Ports already used in this workspace that must be avoided:
- `5000` — WatsonX Challenge Web (Flask)
- `8080` — Box OAuth2 redirect URI
- `47321` — Web app single-instance lock port
- `5173` — Vite default (preferred for frontend dev server, but auto-incremented if busy)

---

### Core Architecture

```
PDF Extractor V3/
├── backend/                    # Standalone Python FastAPI + SocketIO server
│   ├── main.py                 # App entry point (FastAPI + SocketIO mount)
│   ├── config.py               # Config loader (config.json)
│   ├── tracking.py             # Tracking DB (tracking_db.json)
│   ├── box_client.py           # Box JWT auth + upload/download helpers
│   ├── sync.py                 # Box → Local Folder sync logic
│   ├── scanner.py              # Local Folder PDF scanner
│   ├── extractor.py            # Extraction pipeline (calls pdf_text_extractor)
│   ├── viewer.py               # Browse extracted file outputs
│   ├── insights.py             # Analytics / log history
│   ├── chat.py                 # ICA AI chat + skill routing
│   ├── pdf_text_extractor.py   # Copied + adapted from V2 (PDF parsing & export)
│   ├── requirements.txt        # Python deps
│   └── config.json             # Shared runtime config (credentials, paths)
│
├── frontend/                   # React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── main.tsx            # Vite entry
│   │   ├── App.tsx             # Router + ThemeProvider
│   │   ├── components/
│   │   │   ├── Sidebar.tsx     # Dark nav sidebar (always dark)
│   │   │   ├── ThemeToggle.tsx # Dark/light toggle for main content
│   │   │   └── ui/             # Reusable: Button, Card, Badge, etc.
│   │   ├── pages/
│   │   │   ├── Home.tsx        # Landing hero + quick-access cards
│   │   │   ├── Sync.tsx        # Sync panel + live log stream
│   │   │   ├── Scan.tsx        # Scan table + status
│   │   │   ├── Extract.tsx     # Extraction pipeline + result cards
│   │   │   ├── View.tsx        # Browse extracted files by type
│   │   │   ├── Insights.tsx    # Bar chart analytics
│   │   │   └── Chat.tsx        # AI assistant chat UI
│   │   ├── hooks/
│   │   │   ├── useSocket.ts    # Socket.io-client hook for live events
│   │   │   └── useApi.ts       # REST fetch wrapper (base URL, error handling)
│   │   ├── store/
│   │   │   └── theme.ts        # Zustand (or Context) for dark/light mode
│   │   └── types/
│   │       └── index.ts        # Shared TypeScript interfaces
│   ├── index.html
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── electron/                   # Electron shell
│   ├── main.js                 # Main process: spawn Python, open window
│   ├── preload.js              # Context bridge (if needed)
│   └── package.json            # electron + electron-builder config
│
└── start_v3.py                 # Dev-mode launcher (FastAPI + Vite + browser)
```

### Data Flow
- **Electron main process** spawns `backend/main.py` (FastAPI on port 8765)
- **Electron renderer** loads the Vite-built React app (served from `frontend/dist/`)
- **React pages** call REST endpoints (`GET /api/…`, `POST /api/…`)
- **React live pages** (Sync, Scan, Extract) also connect via `socket.io-client` to receive streaming log events in real time

### Port Handshake Flow

```
Electron main.js
  │
  ├─ find_free_port(8765) → resolves to e.g. 8766 if 8765 busy
  │     (tries socket.bind() in Python subprocess OR in Node net.createServer)
  │
  ├─ writes port to .v3_port temp file
  │
  ├─ spawns: python backend/main.py --port 8766
  │
  ├─ polls GET http://localhost:8766/api/health (500ms interval, 30s timeout)
  │
  ├─ on health OK: creates BrowserWindow
  │     loadFile('frontend/dist/index.html')
  │     injects window.__V3_API_PORT__ = 8766 via executeJavaScript
  │
  └─ on app quit: kills Python child process, deletes .v3_port
```

---

### Design
- **Sidebar** — always dark (`#0A0E1A`), indigo-violet accent (`#6C63FF`), matches V2 visual identity
- **Main content** — toggleable dark / light mode via a header toggle button
- **Dark theme**: `#0F1117` background, `#1A1F2E` cards, `#6C63FF` accent
- **Light theme**: `#F8F9FF` background, `#FFFFFF` cards, `#6C63FF` accent
- **Typography**: Inter (Google Fonts), weights 400/500/600/700

---

## Sub-Tasks

---

### Sub-Task 1 — Backend: Project Scaffold & Core Modules

**Intent**
Stand up the standalone FastAPI + SocketIO Python backend. Copy `pdf_text_extractor.py` from V2, adapt path constants. Scaffold the module structure and verify the server starts cleanly.

**Expected Outcomes**
- `PDF Extractor V3/backend/` exists with all module files
- `uvicorn main:app --port <free_port>` starts without error on the first available port at or above 8765
- `/api/health` returns `{"status": "ok", "version": "3.0.0", "port": <actual_port>}`
- All modules import cleanly (no missing-import errors)

**Todo List**
1. Create `PDF Extractor V3/backend/` directory structure
2. Copy `pdf_text_extractor.py` from V2 into `backend/`; update any hard-coded path references to use `BASE_DIR`
3. Write `config.py` — `_read_config()`, `_local_folder()`, `_extracted_folder()`, `_archive_folder()` (ported from V2)
4. Write `tracking.py` — `load_tracking()`, `save_tracking()` (ported from V2)
5. Write `ports.py` — `find_free_port(preferred: int = 8765, max_attempts: int = 20) -> int`: probe each port with `socket.bind()`; raise `RuntimeError` if none free; also write `read_port_file() -> int` and `write_port_file(port: int)` helpers using `.v3_port` in `BASE_DIR`
6. Write `main.py` — accepts `--port` CLI arg (defaults to `find_free_port(8765)`); FastAPI app + Flask-SocketIO mounted at `/socket.io`; CORS wildcarded for `localhost:*`; include all routers; `/api/health` endpoint returns `{"status": "ok", "port": actual_port}`
7. Write `requirements.txt` — `fastapi`, `uvicorn`, `flask`, `flask-socketio`, `boxsdk`, `PyMuPDF`, `python-docx`, `openpyxl`
8. Create a minimal `config.json` template in `backend/` with all required keys and empty/placeholder values

**Relevant Context**
- V2 config functions: `_read_config()`, `_local_folder()`, `_extracted_folder()` — lines ~150–200 of `pdf_extractor_ui_v2.py`
- V2 tracking functions: `load_tracking()`, `save_tracking()` — lines ~210–230
- `BASE_DIR = Path(__file__).parent.resolve()` — used in V2 for all path anchoring
- `pdf_text_extractor.py` is in `PDF Extractor V2/`

**Status** `[x] done`

---

### Sub-Task 2 — Backend: REST API Routes

**Intent**
Implement all REST API endpoints that the React frontend will call. Each V2 screen maps to an API router module.

**Expected Outcomes**
- All routes documented and testable via `http://localhost:8765/docs` (FastAPI auto-docs)
- Each endpoint returns typed JSON responses matching TypeScript interface expectations

**Todo List**
1. Write `scanner.py` — port `_scan_worker` logic; expose as `POST /api/scan/run` (background task) and `GET /api/scan/files` (return tracking DB contents)
2. Write `sync.py` — port `sync_box_to_local()`; expose as `POST /api/sync/run` (background, emits SocketIO events) and `GET /api/sync/status`
3. Write `box_client.py` — port `get_box_client()`, `_resolve_jwt_path()`, `_box_get_or_create_subfolder()`, `upload_file_to_box()` from V2
4. Write `extractor.py` — port extraction pipeline; expose as `POST /api/extract/run` (background, emits progress events) and `GET /api/extract/results`
5. Write `viewer.py` — port `ViewExtractedFrame.on_show()` logic; expose as `GET /api/view/files` returning grouped list by type (Word/Excel/JSON)
6. Write `insights.py` — port `InsightsFrame` data logic + `get_log_history()`; expose as `GET /api/insights?period=day|week|month|year`
7. Write `chat.py` — port `route_chat_message()`, `ica_chat()`, `skill_lookup_report()`, `_find_report_files()`, `_skill_list_all_reports()`, `_skill_open_report()`, `_is_hallucinated_reply()`, `_sanitize_history()`, `_name_matches()`; expose as `POST /api/chat/send`
8. Register all routers in `main.py`

**Relevant Context**
- All backend logic lives in `PDF Extractor V2/pdf_extractor_ui_v2.py`; all non-UI functions are clearly separated from Tkinter code
- ICA API: POST + poll pattern, full_cookie header required — see chat section of exploration notes
- Box SDK usage: `JWTAuth.from_settings_file`, `client.folder().get_items()`, `client.file().content()`, `client.file().move()`, `upload()`

**Status** `[x] done`

---

### Sub-Task 3 — Backend: SocketIO Real-Time Event Layer

**Intent**
Add Flask-SocketIO (mounted into FastAPI via ASGI middleware) so that long-running operations (Sync, Scan, Extract) can stream live log lines and progress events to the React frontend in real time.

**Expected Outcomes**
- SocketIO server runs at `ws://localhost:8765/socket.io`
- React can connect and receive events for `sync:log`, `sync:done`, `scan:progress`, `scan:done`, `extract:progress`, `extract:result`, `extract:done`
- REST endpoints that trigger background tasks emit their progress via SocketIO

**Todo List**
1. In `main.py`, create a `socketio.Server` (Flask-SocketIO async mode) and wrap FastAPI app with `socketio.ASGIApp`
2. Define event names as constants in a shared `events.py` file (avoids typo bugs in frontend and backend)
3. Update `sync.py` — replace V2 `progress_cb` callback with SocketIO emits: `sync:log` (line-by-line), `sync:done` (counts)
4. Update `scanner.py` — emit `scan:progress` (file count) and `scan:done` (total)
5. Update `extractor.py` — emit `extract:progress` (current file, percent), `extract:result` (per-file success/fail JSON), `extract:done` (summary)
6. Write a small test (or manual curl) to confirm events arrive correctly

**Relevant Context**
- V2 threading pattern: all workers call `self.after(0, callback)` to post back to UI — replace this with `socketio.emit()` calls
- Flask-SocketIO + FastAPI integration uses `socketio.ASGIApp(sio, other_asgi_app=fastapi_app)`
- Event names should mirror the V2 frame names for clarity

**Status** `[x] done`

---

### Sub-Task 4 — Frontend: Project Scaffold & Design System

**Intent**
Bootstrap the React + TypeScript + Vite + Tailwind project. Establish the design system: colour tokens, typography, reusable UI primitives (Button, Card, Badge, Spinner), and the dual-mode theme infrastructure.

**Expected Outcomes**
- `npm run dev` starts Vite dev server at `localhost:5173`
- Tailwind CSS configured with custom colour tokens matching the V2 palette
- `ThemeProvider` (React Context) toggles dark/light mode via a class on `<html>`
- Sidebar renders with dark background and nav items; main content area renders in the correct theme
- Reusable components: `Button`, `Card`, `Badge`, `Spinner`, `EmptyState` exist and look correct in both themes

**Todo List**
1. Scaffold Vite project: `npm create vite@latest frontend -- --template react-ts`
2. Install dependencies: `tailwindcss`, `postcss`, `autoprefixer`, `react-router-dom`, `socket.io-client`, `zustand`, `lucide-react`, `recharts`
3. Configure `tailwind.config.ts` — extend with custom colours: `sidebar`, `accent`, `card`, `bg`, semantic tokens for dark/light; enable `darkMode: "class"`
4. Configure `vite.config.ts` — proxy `/api` and `/socket.io` to `http://localhost:${process.env.VITE_API_PORT ?? 8765}` for dev-mode; `start_v3.py` will write `VITE_API_PORT` into a `.env.local` before launching Vite
5. Write `src/store/theme.ts` — Zustand store: `isDark`, `toggle()`; persists to `localStorage`
6. Write `src/App.tsx` — `<BrowserRouter>` wrapping `<Routes>`; sidebar always rendered; `ThemeToggle` in header
7. Write `src/components/Sidebar.tsx` — dark nav with brand logo, nav items (Home, Sync, Scan, Extract, View, Insights, Chat), active state with accent colour, version badge at bottom
8. Write `src/components/ui/` — `Button.tsx`, `Card.tsx`, `Badge.tsx`, `Spinner.tsx`, `EmptyState.tsx` — all theme-aware
9. Write `src/types/index.ts` — `TrackedFile`, `ExtractResult`, `ViewFile`, `InsightsData`, `ChatMessage` interfaces
10. Write `src/hooks/useApi.ts` — typed fetch wrapper for REST calls; handles loading + error state
11. Write `src/hooks/useSocket.ts` — `socket.io-client` hook; auto-connect; exposes `on()` / `emit()`

**Relevant Context**
- V2 colour palette: `CLR_SIDEBAR=#0A0E1A`, `CLR_ACCENT=#6C63FF`, `CLR_ACCENT_DARK=#5B52F0`, `CLR_ACCENT2=#A78BFA`, `CLR_TEAL=#0D9488`, `CLR_GREEN_BG=#22C55E`, `CLR_BG=#0F1117` (dark main), `CLR_CARD=#1A1F2E`
- Light theme base: `#F8F9FF` bg, `#FFFFFF` card, same accent colours
- Sidebar must always stay dark (`#0A0E1A`) regardless of light/dark toggle
- Font: Inter (via `@fontsource/inter` or Google Fonts CDN in `index.html`)

**Status** `[x] done`

---

### Sub-Task 5 — Frontend: Home & Sync Pages

**Intent**
Implement the **Home** (landing hero + quick-access cards) and **Sync** (Box sync trigger + live log stream) pages.

**Expected Outcomes**
- Home page shows hero banner (dark gradient, IBM WatsonX eyebrow pill, title, description) and 5 quick-access cards (Scan, Sync, Extract, View, Chat) with hover effects and click navigation
- Sync page shows a "Sync Now" button; clicking it calls `POST /api/sync/run`, disables the button, and streams `sync:log` events into a live terminal-style log area; `sync:done` re-enables the button and shows a summary

**Todo List**
1. Write `src/pages/Home.tsx` — hero banner section; "QUICK ACCESS" section label; 5 `QuickAccessCard` components (icon badge, title, description, "Open →" arrow, hover accent border)
2. Write `src/pages/Sync.tsx` — header with subtitle; "Sync Now" button; live log `<div>` that appends lines as `sync:log` socket events arrive; final summary badge on `sync:done`
3. Connect Sync page to SocketIO via `useSocket` hook — subscribe to `sync:log` and `sync:done` on mount
4. Confirm POST `api/sync/run` triggers backend sync and events flow through

**Relevant Context**
- V2 `HomeFrame` hero: dark `#1A1040` bg, `#A78BFA` eyebrow pill, 22px bold title, muted subtitle
- V2 `SyncFrame` log area: dark `#0D1117` bg, `#7DD3A8` green text, monospace font
- Quick access cards: icon badge (accent-tinted bg + accent icon), bold title, muted description, `"Open →"` label, accent border on hover

**Status** `[x] done`

---

### Sub-Task 6 — Frontend: Scan & Extract Pages

**Intent**
Implement the **Scan** (file tracking table) and **Extract** (extraction pipeline + result cards) pages.

**Expected Outcomes**
- Scan page loads file list from `GET /api/scan/files` and renders a sortable table (filename, path, status badge, last extracted, ref number); "Scan Now" button triggers `POST /api/scan/run` and updates table on `scan:done`
- Extract page shows pending file count; "Start Extraction" button triggers `POST /api/extract/run`; live progress bar + log via `extract:progress` socket events; result cards (success/fail) appear as each file completes via `extract:result`

**Todo List**
1. Write `src/pages/Scan.tsx` — page header with subtitle; `POST /api/scan/run` button; table with columns (Name, Path, Status, Last Extracted, Ref No); status badge (Pending=orange, Completed=green); empty state illustration
2. Write `src/pages/Extract.tsx` — header; pending count summary; "Start Extraction" button; progress bar (percent from socket); scrollable result card list; each card shows filename, status icon, ref number, elapsed time
3. Both pages subscribe to relevant socket events via `useSocket`
4. Scan page re-fetches `GET /api/scan/files` on `scan:done`
5. Extract page re-fetches `GET /api/scan/files` (to update statuses) on `extract:done`

**Relevant Context**
- V2 `ScanFolderFrame` tree columns: Name, Path, Status, Last Extracted, Ref Number
- V2 `ExtractFrame` result cards: left accent bar, success/fail colour, ref number, filename
- Status badge colours: `Pending` → amber/orange; `Completed` → green; matching V2 treeview tag colours

**Status** `[x] done`

---

### Sub-Task 7 — Frontend: View, Insights & Chat Pages

**Intent**
Implement the **View** (browse extracted files), **Insights** (bar chart analytics), and **Chat** (AI assistant) pages.

**Expected Outcomes**
- View page loads `GET /api/view/files` and renders three sections (Word Documents, Excel Workbooks, JSON Files), each with icon badge + count pill + divider; files grouped by reference subfolder; click-to-open via `POST /api/view/open`
- Insights page loads `GET /api/insights?period=…` and renders stat cards (Total/Completed/Pending) and a stacked bar chart (Recharts `BarChart`) with a period selector (Day/Week/Month/Year)
- Chat page renders a full chat UI — message history, user input, send button; calls `POST /api/chat/send`; renders `**bold**` and `*italic*` markdown; handles special `§LINKS§` extraction-result JSON cards with clickable file links

**Todo List**
1. Write `src/pages/View.tsx` — "Refresh" button; 3 type sections with pill-style headers (matches V3 design language); file rows with clickable filename (underlined, accent colour) + modification time; ref subfolder group labels
2. Write `src/pages/Insights.tsx` — 3 stat cards (Total/Completed/Pending); period selector buttons; Recharts `<BarChart>` with stacked bars (Completed green / Pending amber); dot legend
3. Write `src/pages/Chat.tsx` — scrollable message list; each message has avatar (user vs AI); inline markdown renderer (basic: bold, italic, `---` rule); `§LINKS§` card renderer (expandable with Word/Excel/JSON open buttons); input bar at bottom; send on Enter or button click
4. Wire `POST /api/view/open` to trigger `os.startfile` on backend (Windows-only) — add this endpoint to `viewer.py`

**Relevant Context**
- V2 `ViewExtractedFrame._TYPES`: Word=`CLR_ACCENT`, Excel=`CLR_TEAL`, JSON=`CLR_ACCENT2`
- V2 `ChatFrame` `§LINKS§` format: `{"header": "...", "items": [{"ref": "...", "subject": "...", "word": "path", "excel": "path", "json": "path"}, ...]}`
- V2 `InsightsFrame` chart: stacked bars; period buckets built from log history timestamps
- Recharts `BarChart` fits the stacked bar requirement natively

**Status** `[x] done`

---

### Sub-Task 8 — Electron Shell

**Intent**
Wrap the built React app in an Electron shell. The Electron main process spawns the Python FastAPI backend as a child process, waits for it to be ready, then opens the app window loading the built `frontend/dist/index.html`.

**Expected Outcomes**
- `npm start` (from `electron/`) launches the full app as a native window
- Python FastAPI backend starts automatically; Electron waits for `/api/health` to respond before showing the window
- Window title: "PDF Extractor V3"
- On app quit, the Python child process is cleanly terminated
- `electron-builder` configured for Windows `.exe` installer (NSIS)

**Todo List**
1. Write `electron/package.json` — electron, electron-builder; build config pointing to `frontend/dist/` as renderer source; NSIS installer target for Windows
2. Write `electron/main.js`:
   - Use Node `net.createServer` to probe ports starting at 8765 (skip 5000, 8080, 47321); pick first free port
   - Write chosen port to `.v3_port` in `app.getPath('userData')`
   - Spawn `python backend/main.py --port <chosen_port>` as child process
   - Poll `GET http://localhost:<port>/api/health` every 500ms (max 30s timeout)
   - On health OK: create `BrowserWindow`; load `frontend/dist/index.html`; inject `window.__V3_API_PORT__ = <port>` via `webContents.executeJavaScript`
   - `app.on("will-quit")`: kill Python child process; delete `.v3_port`
3. Write `electron/preload.js` — expose `ipcRenderer` for `get-api-port` channel via `contextBridge`; React can call `window.electronAPI.getApiPort()`
4. Add `build:frontend` script to `frontend/package.json` that outputs to `../electron/frontend/dist/`
5. Write `start_v3.py` — dev-mode launcher:
   - Call `find_free_port(8765)` (Python); write `.v3_port` + write `frontend/.env.local` with `VITE_API_PORT=<port>`
   - Start `uvicorn backend.main:app --port <port>` in background subprocess
   - Start `npm run dev` in `frontend/` (Vite finds its own port)
   - Poll health; open browser once ready
6. Document build steps in `PDF Extractor V3/README.md`

**Relevant Context**
- Ports to avoid: 5000 (Web Flask), 8080 (Box OAuth2 redirect), 47321 (Web lock port)
- Health check: `GET http://localhost:<dynamic_port>/api/health` → `{"status": "ok", "port": <port>}`
- Python executable path: use `sys.executable` in spawned process command, or bundle Python via PyInstaller into `backend.exe` as `extraResources`
- `.v3_port` file acts as the shared contract between Python, Node, and React at runtime

**Status** `[x] done`

---

### Sub-Task 9 — Integration Testing & Polish

**Intent**
End-to-end validation of all pages and flows. Fix any integration issues between frontend, backend, and Electron shell. Polish visual details.

**Expected Outcomes**
- All 7 pages render correctly in both dark and light modes
- Sync, Scan, Extract flows complete end-to-end with live events visible in the UI
- Chat sends messages and receives AI responses
- View page opens files via the OS
- Insights chart renders with real data
- Electron app launches, loads the UI, and quits cleanly
- No console errors in Electron DevTools

**Todo List**
1. Run full sync + scan + extract cycle; confirm SocketIO events arrive and UI updates correctly
2. Confirm dark/light mode toggle works on all pages; sidebar stays dark in both modes
3. Test Chat page with a real ICA query; confirm `§LINKS§` card renders correctly with file open buttons
4. Test View page file-open via `POST /api/view/open`; confirm `os.startfile()` fires
5. Test Insights with real log history data; confirm chart periods filter correctly
6. Confirm Electron app window opens, Python process spawns/terminates cleanly
7. Fix any CORS, port, or path issues discovered during testing
8. Final visual pass: spacing, font sizes, hover states, responsive sizing (window resize)
9. **In-app Settings/Configuration page** — added so credentials (Box, ICA, PDF password) can be configured via the UI instead of hand-editing `config.json`

**Settings Page Addition (this pass)**
Because credentials are not pre-configured, an in-app **Settings** page was added so the whole app is configurable from the UI:
- **Backend** — `config.py` gained `write_config()` (atomic write), `read_config_safe()`, `default_config()` (full template), `jwt_config_path()`, `write_jwt_config()`. New `settings.py` router (`/api/settings`) exposes:
  - `GET /api/settings` — current config with secrets masked (`••••••••`)
  - `POST /api/settings` — save config via partial deep-merge (mask values are skipped so real secrets are never overwritten)
  - `GET /api/settings/status` — which credential groups (Box / ICA / PDF password) are configured
  - `POST /api/settings/jwt` — upload/replace the Box JWT config JSON
  - `POST /api/settings/test/box` — live Box JWT connection test
  - `POST /api/settings/test/ica` — live ICA cookie/team/chat connection test
- **Frontend** — new `src/pages/Settings.tsx` (PDF password, IBM Box folder IDs + JWT upload/test, ICA fields + test, extraction/sync Options toggles); `types/index.ts` gained `AppConfig` + `SettingsStatus`; `App.tsx` route `/settings`; `Sidebar.tsx` new "System" nav group with a Settings item.

**Verification Results**
- Python deps: all already satisfied (fastapi, uvicorn, python-socketio, flask-socketio, boxsdk, PyMuPDF, python-docx, openpyxl, pydantic v2, aiofiles) — no install needed.
- Backend imports cleanly — 22 routes registered (incl. settings router).
- Endpoints verified via FastAPI `TestClient`: `/api/health` → ok v3.0.0; `/api/settings` → all 6 config sections; `/api/settings/status` → credential state; save round-trip works with `pdf_password` masked on read-back and non-secret fields persisted.
- `npm install` completed for both `frontend/` (185 pkgs) and `electron/` (404 pkgs).
- Frontend `npm run build` (`tsc -b && vite build`) compiled with **zero type errors**; production bundle emitted to `electron/renderer/`.

**Remaining (requires real credentials to fully exercise)**
- Live Box sync / extract / ICA chat end-to-end runs, `os.startfile()` file-open, and the full Electron packaged `.exe` launch are pending real Box JWT + ICA credentials (set them via the new Settings page, then run `python "PDF Extractor V3/start_v3.py"` for dev mode or `npm start` in `electron/`).

**Status** `[x] done — core integration verified; live credential-dependent flows pending real credentials`


---

## Phase 10 — Standalone Build & Runtime Resolution

**Goal** Produce a working, double-clickable Windows desktop app (NSIS installer + portable `.exe`) that launches its window with the Python backend frozen into the bundle — no Python install required on the target machine.

### Build pipeline (`build_all.bat`)
1. `npm run build` in `frontend/` → static bundle emitted to `electron/renderer/`.
2. `python build_backend.py` → **PyInstaller 6.21** one-folder build of `backend/main.py` → `dist/backend/` (`backend.exe` + `_internal/`), copied to `electron/resources/backend/`.
3. `cd electron && npm run dist` → **electron-builder 25.1.8** produces `PDF-Extractor-V3-Setup-3.0.0.exe` (NSIS) and `PDF-Extractor-V3-Portable-3.0.0.exe` in `electron/dist/`, with the frozen backend embedded as `extraResources`.

### Bugs found & fixed
- **PyInstaller missing hidden import** — `python-socketio` with `async_mode="threading"` dynamically imports `engineio.async_drivers.threading`. Added to `backend.spec` `hiddenimports` so the frozen exe starts.
- **uvicorn app reference** — inside a frozen bundle there is no importable `"main"` module, so `uvicorn.run("main:app", …)` crashed. Changed to pass the **app object**: `uvicorn.run(app, …)`.
- **Windows cp1252 console crash** — unicode arrows in log output crashed the frozen console. Fixed with a UTF-8 stream reconfigure at startup + ASCII arrows.
- **Code signing** — disabled (`sign:null`, `signAndEditExecutable:false` in `package.json` + `CSC_IDENTITY_AUTO_DISCOVERY=false`) since the app is unsigned.
- **Diagnostics safety net** — `main.js` now writes a startup trace to `%TEMP%\pdf-extractor-v3-startup.log`, shows a native error dialog on uncaught exceptions / startup failure, and captures backend `stderr` for the dialog. This survives as a permanent troubleshooting aid.

### Root-cause of "window never appears"
The app was **not broken**. The failure to show a window during testing was caused by the environment variable **`ELECTRON_RUN_AS_NODE=1`** being set in the developer's terminal (inherited from the IDE/agent process). This variable forces *every* Electron binary to run as headless Node.js — it never enters GUI mode, never runs the app entry, and no window is created. Clearing it (`set "ELECTRON_RUN_AS_NODE="`) makes the packaged app launch normally.

> If the app ever launches with no window, check that `ELECTRON_RUN_AS_NODE` is **not** set in the environment.

### End-to-end verification (env var cleared)
Both the unpacked build **and** the self-extracting portable `.exe` were launched and confirmed via the startup log:
`whenReady (isPackaged=true)` → `findFreePort → 8765` → `spawnBackend` → **`waitForHealth resolved (backend healthy)`** → `createWindow` — with 4 Electron processes + 1 `backend.exe` running (window visible, backend serving). The portable variant self-extracts to `%TEMP%` and takes ~20 s for backend cold-start, comfortably inside the 30 s `HEALTH_TIMEOUT`.

**Deliverables** `electron/dist/PDF-Extractor-V3-Setup-3.0.0.exe` (NSIS installer, ~135 MB) and `electron/dist/PDF-Extractor-V3-Portable-3.0.0.exe` (portable, ~135 MB) — both freshly rebuilt from the verified-working sources.

**Status** `[x] done — packaged NSIS + portable installers build and launch end-to-end (window + frozen backend verified)`


---

## Phase 11 — White-Screen & Slow-Startup Fixes

**Goal** After Phase 10 the packaged app launched but showed a **long white screen** before the UI appeared. This phase eliminates both the white screen and the perceived slow start.

### Bugs found & fixed
- **White screen (root cause)** — Electron loads the built renderer via `loadFile()`, i.e. a `file://` URL. Vite emitted **absolute** asset paths (`/assets/…`), which under `file://` resolve to the *filesystem root* and 404 → blank white page. **Fix:** set `base: './'` in `frontend/vite.config.ts` so Vite emits **relative** paths (`./assets/…`). Verified: built `electron/renderer/index.html` now references `./assets/index-*.js` / `./assets/index-*.css`.
- **Router incompatible with file://** — React Router `BrowserRouter` uses the HTML5 history API, which misbehaves under `file://`. **Fix:** switched `App.tsx` to `HashRouter` (routes become `#/sync`, `#/scan`, … — safe for `file://`).
- **Slow appearance (UX)** — the window was previously created **only after** `waitForHealth` resolved (PyInstaller backend cold-start), so the user stared at nothing. **Fix:** `main.js` now **creates and shows the window immediately** with an inline data-URL **loading splash** (dark `#0F1117` bg + indigo spinner + "Starting backend service…"), spawns the backend **in parallel**, then swaps in the real renderer via `loadRenderer(port)` once `/api/health` is healthy. Split into two functions: `createWindow()` (instant splash) and `loadRenderer(port)` (deferred `loadFile` + port injection).

### Launch note (`ELECTRON_RUN_AS_NODE`)
The IDE/agent injects `ELECTRON_RUN_AS_NODE=1` into every spawned terminal's **process** environment (not persisted in the User/Machine registry). `cmd`'s `set "ELECTRON_RUN_AS_NODE="` did **not** reliably propagate to a `start`-detached child, so the packaged exe kept exiting instantly with **no window and no startup log**. Launching via PowerShell with `Remove-Item Env:\ELECTRON_RUN_AS_NODE` fully deletes the variable for the child and the app runs normally.

### End-to-end verification (fresh win-unpacked build)
Startup log (`%TEMP%\pdf-extractor-v3-startup.log`) confirmed the new sequence and timing:
`createWindow called (splash)` (**~0.25 s** after launch — splash visible instantly, no white screen) → `spawnBackend called` → `waitForHealth resolved (backend healthy)` (**~2 s** cold-start) → `loadRenderer called`. **Total launch-to-UI ≈ 2.6 s**, with a spinner shown the entire time.

**Status** `[x] done — white screen eliminated (relative assets + HashRouter); instant splash + parallel backend warm-up verified via startup log`


---

## Key Decisions Recorded

| Decision | Choice | Rationale |
|---|---|---|
| Frontend framework | React + TypeScript + Vite + Tailwind CSS | Modern, fast, type-safe |
| Desktop shell | Electron + electron-builder | Single .exe installer; polished native-window feel |
| Backend framework | FastAPI (REST) + Flask-SocketIO (real-time) | FastAPI for auto-docs + type validation; SocketIO for live log streaming |
| Real-time transport | Flask-SocketIO WebSockets | Bidirectional; handles progress callbacks cleanly; React socket.io-client well-supported |
| V2 independence | Fully standalone V3 backend | No coupling to V2 files; clean architecture |
| Theme | Dark sidebar always + toggleable main content (dark/light) | Best of both: always-modern sidebar; user preference for main area |
| Chart library | Recharts | Purpose-built for React; lightweight; stacked bar support native |
| State management | Zustand | Minimal boilerplate for theme + global state |
| Port resolution | `find_free_port(8765, max=20)` via socket probe; port written to `.v3_port`; injected into renderer as `window.__V3_API_PORT__`; Vite proxy reads `VITE_API_PORT` from `.env.local` | Avoids conflicts with ports 5000, 8080, 47321 already in use; works on any machine without manual config |

## File Count Summary

| Layer | Files |
|---|---|
| Backend Python modules | 10 |
| Frontend React pages | 7 |
| Frontend components/hooks/types | ~12 |
| Electron shell | 3 |
| Config / docs | 3 |
| **Total** | **~35** |
