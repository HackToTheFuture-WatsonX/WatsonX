# Developer Onboarding

Everything a new engineer needs to be productive on PDF Extractor V3 in one afternoon.

---

## Prerequisites

- **Python 3.12+** on `PATH`.
- **Node.js 18+** with `npm`.
- **Git**.
- **Windows 10 / 11** — the app is Windows-only; dev on macOS/Linux is possible but you can't produce shippable exes.
- (Optional) **VS Code** with Python and TypeScript extensions.
- **Box service-account JWT JSON** and folder IDs (for testing Sync/Extract end-to-end).

---

## One-time Setup

From the repo root:

```bat
:: Python side — install all backend + build deps
pip install -r "PDF Extractor V3\requirements-build.txt"

:: Frontend side
cd "PDF Extractor V3\frontend"
npm install
cd ..

:: Electron side
cd electron
npm install
cd ..
```

Total install time: ~5 minutes on a warm cache.

---

## Running in Dev Mode

Three processes, all in one shot:

```bat
cd "PDF Extractor V3"
python start_v3.py
```

`start_v3.py` launches:

1. FastAPI backend (`python backend/main.py --port 8765`) — API at `http://127.0.0.1:8765/docs`.
2. Vite dev server (`npm run dev` in `frontend/`) — hot module reload at `http://localhost:5173`.
3. Electron main process pointing at the Vite server (proxied to the backend).

Alternatively run each layer manually — see [Environment-Setup.md](Environment-Setup.md).

---

## Repository Tour

The important stuff, in read-first order:

```
PDF Extractor V3/
├── backend/
│   ├── main.py               ← ASGI app, uvicorn entry, route enumeration on startup
│   ├── db.py                 ← SQLite persistence layer (single source of truth)
│   ├── config.py             ← config + path helpers (bee_prompt loader)
│   ├── activity.py           ← [[level=…]] activity-log helper
│   ├── events.py             ← Socket.IO thread-safe emit
│   ├── scanner.py            ← /api/scan/* — walk + upload
│   ├── sync.py               ← /api/sync/*  — Box → local
│   ├── extractor.py          ← /api/extract/* — full pipeline
│   ├── viewer.py             ← /api/view/* — browse exports
│   ├── insights.py           ← /api/insights — dashboard stats + log history
│   ├── chat.py               ← /api/chat/* — Bee router + ICA transport
│   ├── settings.py           ← /api/settings/* — CRUD + SSE tests
│   ├── box_client.py         ← Box JWT client factory + upload helpers
│   ├── tracking.py           ← thin wrapper over db.tracking_*
│   ├── ports.py              ← port picker
│   ├── pdf_text_extractor.py ← DECRYPT · PARSE · EXPORT engine (shared across V1/V2/V3)
│   └── prompt/
│       └── bee_prompt.md     ← ICA system prompt (Bee persona)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx           ← routing, global stores hydration
│   │   ├── pages/            ← Home, Sync, Scan, Extract, View, Insights, Logs, Settings
│   │   ├── components/       ← Sidebar, ChatBubble, ui/*
│   │   ├── hooks/            ← useApi, useSocket
│   │   ├── store/            ← Zustand — theme, run, chat, toast
│   │   └── types/            ← TS interfaces
│   └── vite.config.ts        ← base './' for file:// compat
│
├── electron/
│   ├── main.js               ← main process
│   ├── preload.js            ← contextBridge exposure
│   ├── package.json          ← electron-builder config
│   └── (renderer/, resources/backend/, dist/ ← build artifacts)
│
├── start_v3.py               ← dev launcher for all three layers
├── build_backend.py          ← PyInstaller runner
├── backend.spec              ← PyInstaller spec (hidden imports, datas)
└── build_all.bat             ← production build orchestrator
```

Read the order above and you'll understand every layer in 90 minutes.

---

## First Task: Add a Log Entry

Confidence-building exercise. Add an activity-log entry when the user clicks **Refresh** on the Scan page.

1. Frontend: `frontend/src/pages/Scan.tsx` — add a `refreshLogged` handler that calls a new endpoint.
2. Backend: add `POST /api/scan/refresh` to `scanner.py` that just calls `activity.write("SCAN", "Manual refresh from Scan page.", level="info")` and returns `{"status": "ok"}`.
3. Reload the dev app, click Refresh, then open the Logs page — the row appears.

This exercise walks you through the fetch → backend → SQLite → Socket.IO → React state loop end-to-end.

---

## Coding Conventions

- **Python**: PEP 8, type hints on public functions where useful. `import` order: stdlib → third-party → first-party.
- **TypeScript**: match existing style. Prefer functional components + hooks; no class components. Zustand for cross-page state.
- **Naming**: `snake_case` in Python, `camelCase` / `PascalCase` in TS.
- **Comments**: sparse. Only when the *why* is non-obvious — a bug that prompted the code, a subtle invariant, an incompatibility gotcha. Do not restate what the code does.
- **Logging**: use `logging.getLogger(<module>)` in Python. Every activity-log write must pass an explicit `level=` (info/warning/error).

---

## PR Flow

1. Branch off `main` (typically `dev_<name>` or a feature branch).
2. Make the change; run the app in dev mode; verify the affected pages.
3. Run `npm run build` in `frontend/` and `python build_backend.py` at least once to confirm no import or type break.
4. Update the docs under `docs/pdf-extractor-v3/` where relevant — the doc index in [README.md](README.md) is the source of truth.
5. Open a PR to `main` describing the observable change (not the mechanics — those live in the diff).

Every PR must:

- Preserve the `[[level=…]]` tag on any new activity-log write.
- Preserve secret masking (no `pdf_password` or `full_cookie` in logs).
- Route Box calls through `box_client.get_box_client()`.
- Route ICA calls through `chat._ica_send_and_stream()`.
- Route DB calls through `backend/db.py`.

Violating any of these needs an ADR ([ADR/](ADR/)).

---

## Testing

There is no automated test suite in the repo today (see [Improvements](improvements.md)). Verification is manual:

- **Backend**: hit endpoints via the FastAPI Swagger UI at `/docs`, or with `curl`.
- **Frontend**: Vite hot-reload; use React DevTools in Chrome (dev mode) for state inspection.
- **End-to-end**: full pipeline against a small Box test folder.

Adding a `pytest` suite and Playwright coverage is on the roadmap.

---

## Build Artifacts

`build_all.bat` produces two files under `electron/dist/`:

- `PDF-Extractor-V3-Setup-3.0.0.exe` — NSIS installer.
- `PDF-Extractor-V3-Portable-3.0.0.exe` — single-file portable.

Both bundle Chromium + Node.js + Python + all packages.

See [CI-CD.md](CI-CD.md) and [Deployment-Guide.md](Deployment-Guide.md).

---

## Debugging in Production Builds

Packaged Windows Electron detaches from the console and DevTools is disabled by design. Two surfaces exist for observability:

1. **Backend log** — `%TEMP%\pdf-extractor-v3-backend.log`. Every launch truncates it and appends fresh `[out]` / `[err]` lines with a header.
2. **Diagnostics panel** — on the Scan page. Records the last button click, file pick, and fetch outcome.

See [Troubleshooting.md](Troubleshooting.md#first-what-to-look-at).

---

## Related

- [Codebase-Structure.md](Codebase-Structure.md) — per-file responsibilities
- [Environment-Setup.md](Environment-Setup.md) — install command detail
- [ADR/](ADR/) — decision records
- [Bug-Report-Process.md](Bug-Report-Process.md) — how bugs enter the pipeline
