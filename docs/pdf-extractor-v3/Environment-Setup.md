# Environment Setup

Installation and runtime prerequisites for **development** and **packaged** modes.

---

## Packaged (End-User) Mode

**Prerequisites: none.**

Both the NSIS installer and the portable exe bundle:

- Chromium (via Electron)
- Node.js runtime (via Electron)
- Python 3.12 interpreter (via PyInstaller freeze)
- Every PyPI package listed in `backend/requirements.txt`
- The pre-built React renderer

The user just launches the exe. Data lives in `%APPDATA%\PDF Extractor V3\`.

Minimum host requirements:

- Windows 10 (build 1903+) or Windows 11
- x64 processor
- ~500 MB free disk (portable exe ~300 MB; installer footprint similar)
- ~500 MB free RAM headroom for Chromium + Python

---

## Development Mode

Full source-tree development requires three toolchains.

### 1. Python 3.12+

Install from python.org or Microsoft Store. Verify:

```bat
python --version
:: Python 3.12.x
```

Install dependencies:

```bat
cd "PDF Extractor V3"
pip install -r requirements-build.txt
```

This installs both the runtime deps (via `-r backend/requirements.txt`) and PyInstaller for building. Runtime packages:

```
fastapi>=0.110.0
python-multipart>=0.0.9
uvicorn[standard]>=0.29.0
python-socketio>=5.11.0
python-engineio>=4.9.0
flask>=3.0.0
flask-socketio>=5.3.6
boxsdk[jwt]>=3.9.2
PyMuPDF>=1.24.0
python-docx>=1.1.0
openpyxl>=3.1.0
pydantic>=2.0.0
aiofiles>=23.0.0
```

Build-only:

```
pyinstaller>=6.10.0
```

Note: `flask` / `flask-socketio` were used in earlier drafts of V3 and remain listed for compatibility; the shipping backend uses `python-socketio` + FastAPI exclusively.

### 2. Node.js 18+

Install from nodejs.org. Verify:

```bat
node --version   :: v18.x or higher
npm --version    :: 9.x or higher
```

Install frontend deps:

```bat
cd "PDF Extractor V3\frontend"
npm install
```

Frontend packages (versions from `frontend/package.json`):

- `react 18.3.1`, `react-dom 18.3.1`, `react-router-dom 6.26.2`
- `socket.io-client 4.7.5`
- `zustand 4.5.5`
- `lucide-react 0.447.0`, `recharts 2.12.7`
- Dev tools: `vite 5.4.8`, `typescript 5.5.3`, `tailwindcss 3.4.13`

### 3. Electron

Install the Electron toolchain deps:

```bat
cd "PDF Extractor V3\electron"
npm install
```

This pulls Electron itself and `electron-builder`. Version pinned in `electron/package.json`.

---

## Running Layers Individually

Useful when iterating on one layer without touching the others.

### Backend alone

```bat
cd "PDF Extractor V3\backend"
python main.py --port 8765
```

Optional flags:
- `--port <N>` — force a specific port
- `--data-dir "<path>"` — use a custom data directory (defaults to the backend/ folder in dev)

Swagger UI: `http://127.0.0.1:8765/docs`.

### Frontend alone

```bat
cd "PDF Extractor V3\frontend"
npm run dev
```

Serves at `http://localhost:5173`. In dev mode, `/api/*` requests are proxied to `http://127.0.0.1:8765`.

### Electron alone (points at Vite dev server)

Managed by `start_v3.py`. Manual invocation is not typical.

### Everything at once

```bat
cd "PDF Extractor V3"
python start_v3.py
```

Kills all three processes on Ctrl+C.

---

## Environment Variables

None required at runtime. The application respects standard Windows conventions (`%APPDATA%`, `%TEMP%`) via Node.js `os` and Python `os.path.expandvars`.

For build-time overrides, see [CI-CD.md](CI-CD.md).

---

## Verifying the Setup

Smoke test after install:

1. Start dev mode: `python start_v3.py`.
2. Wait for `[V3 Backend] Starting on http://127.0.0.1:8765`.
3. Browse `http://localhost:5173` in a browser — the sidebar renders with all 8 routes.
4. Browse `http://127.0.0.1:8765/docs` — Swagger lists every endpoint from [API-Documentation.md](API-Documentation.md).
5. Click `/api/health` in Swagger → **Try it out** → **Execute** → `{"status": "ok", "version": "3.0.0"}`.

If any step fails, see [Troubleshooting.md](Troubleshooting.md).

---

## Related

- [Developer-Onboarding.md](Developer-Onboarding.md) — first-day walkthrough
- [Deployment-Guide.md](Deployment-Guide.md) — install/uninstall
- [CI-CD.md](CI-CD.md) — build pipeline
