# PDF Extractor V3

A **fully portable** Electron desktop application — no system Python or Node.js required on target machines.

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **Backend**: FastAPI + Flask-SocketIO (compiled to `backend.exe` via PyInstaller)
- **Shell**: Electron 32 + electron-builder (produces NSIS installer + single portable `.exe`)

---

## 📦 Distributable Output

After running `build_all.bat`, you get two ready-to-ship files:

| File | Description |
|---|---|
| `electron/dist/PDF-Extractor-V3-Setup-3.0.0.exe` | NSIS installer — installs to Program Files, adds Start Menu + Desktop shortcut |
| `electron/dist/PDF-Extractor-V3-Portable-3.0.0.exe` | Single-file portable — no installation, run from anywhere (USB drive, shared folder, etc.) |

Both files are **completely self-contained**:
- Python interpreter + all packages bundled inside `backend.exe` (PyInstaller)
- Chromium + Node bundled by Electron
- No system Python, Node.js, or pip required on the target machine

---

## 🚀 Build (One-Time Setup)

### Prerequisites (on the **build** machine only — not needed to run the app)

```bat
REM 1. Install Python build tools
pip install -r "PDF Extractor V3\requirements-build.txt"

REM 2. Install Node deps for frontend
cd "PDF Extractor V3\frontend"
npm install
cd ..

REM 3. Install Node deps for Electron
cd "PDF Extractor V3\electron"
npm install
cd ..
```

### Build everything

```bat
cd "PDF Extractor V3"
build_all.bat
```

That's it. The `build_all.bat` runs all 4 steps automatically:

| Step | What happens |
|---|---|
| 1 | `npm run build` — Vite compiles React → `electron/renderer/` |
| 2 | `python build_backend.py` — PyInstaller compiles Python → `electron/resources/backend/backend.exe` |
| 3 | `electron-builder` — packages everything into installer + portable exe |

---

## ⚙️ Configuration (after installing)

On first launch, config files are created automatically at:

```
%APPDATA%\PDF Extractor V3\
    config.json           ← fill in your credentials here
    box_jwt_config.json   ← replace with your Box JWT config JSON
    tracking_db.json      ← auto-managed
    Log History\          ← extraction logs
    Local Folder\         ← synced PDFs + outputs
```

Edit `config.json` and fill in:

```json
{
  "pdf_password": "your-pdf-password",
  "box": {
    "folder_id":         "YOUR_BOX_SOURCE_FOLDER_ID",
    "archive_folder_id": "YOUR_BOX_ARCHIVE_FOLDER_ID",
    "output_folder_id":  "YOUR_BOX_OUTPUT_FOLDER_ID",
    "jwt_config_file":   "box_jwt_config.json"
  },
  "ica": {
    "full_cookie": "your-full-browser-cookie-string",
    "team_id":     "your-team-uuid",
    "team_name":   "Your%20Team%20Name",
    "chat_id":     "your-chat-uuid"
  }
}
```

Place your `box_jwt_config.json` (downloaded from app.box.com) next to `config.json`.

---

## 🔌 Port Resolution

V3 automatically finds a free port at startup — no manual configuration needed:

1. Tries port **8765** first
2. Skips reserved ports: `5000`, `8080`, `47321`
3. Increments by 1 and retries up to 20 times
4. Chosen port injected into the renderer as `window.__V3_API_PORT__`

---

## 🛠️ Development Mode

If you want to run from source (requires Python + Node):

```bat
cd "PDF Extractor V3"
python start_v3.py
```

This starts the FastAPI backend + Vite dev server and opens the browser automatically.

---

## 📁 Project Structure

```
PDF Extractor V3/
├── backend/                    Python FastAPI + SocketIO server
│   ├── main.py                 Entry point (--port, --data-dir args)
│   ├── config.py               Config loader (data-dir aware)
│   ├── tracking.py             tracking_db.json helpers
│   ├── ports.py                Dynamic port finder
│   ├── events.py               SocketIO event name constants
│   ├── scanner.py              REST: POST /api/scan/run, GET /api/scan/files
│   ├── sync.py                 REST: POST /api/sync/run (live SocketIO logs)
│   ├── box_client.py           Box JWT client + upload helpers
│   ├── extractor.py            REST: POST /api/extract/run (live progress)
│   ├── viewer.py               REST: GET /api/view/files, POST /api/view/open
│   ├── insights.py             REST: GET /api/insights?period=
│   ├── chat.py                 REST: POST /api/chat/send (ICA + skill routing)
│   └── pdf_text_extractor.py   PDF decrypt / parse / export (from V2)
│
├── frontend/                   React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── App.tsx             Router + layout
│       ├── pages/              Home, Sync, Scan, Extract, View, Insights, Chat
│       ├── components/         Sidebar, ThemeToggle, ui/*
│       ├── hooks/              useApi, useSocket
│       ├── store/theme.ts      Zustand dark/light toggle (persisted)
│       └── types/index.ts      TypeScript interfaces
│
├── electron/
│   ├── main.js                 Main process (port finder, spawn backend.exe, window)
│   ├── preload.js              Context bridge (window.electronAPI.getApiPort)
│   ├── package.json            electron + electron-builder config
│   └── resources/backend/      ← PyInstaller output placed here by build_backend.py
│
├── backend.spec                PyInstaller spec
├── build_backend.py            Step 2 of build: PyInstaller runner
├── build_all.bat               Full build pipeline (frontend → backend → Electron)
├── requirements-build.txt      Build-time Python deps (includes PyInstaller)
├── start_v3.py                 Dev-mode launcher
└── README.md
```

---

## 🎨 Design

| | Dark mode | Light mode |
|---|---|---|
| **Sidebar** | Always `#0A0E1A` (navy) | Always `#0A0E1A` |
| **Background** | `#0F1117` | `#F0F2FA` |
| **Cards** | `#1A1F2E` | `#FFFFFF` |
| **Accent** | `#6C63FF` (indigo-violet) | same |
| **Font** | Inter (Google Fonts) | same |

Toggle: header button (☀/🌙), persisted to `localStorage`.
