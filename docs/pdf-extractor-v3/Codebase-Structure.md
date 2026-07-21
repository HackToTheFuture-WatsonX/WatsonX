# Codebase Structure

Per-file responsibilities. Read alongside [Technical-Architecture.md](Technical-Architecture.md) for the layered view.

Root: `PDF Extractor V3/`.

---

## Root-Level Files

| File | Purpose |
|---|---|
| `start_v3.py` | Dev launcher — spawns backend, Vite, Electron |
| `build_backend.py` | Runs PyInstaller with sanity preflight (validates required packages including `python_multipart`, `aiofiles`) |
| `backend.spec` | PyInstaller spec: hiddenimports, datas (bee_prompt.md, config template), and local backend modules |
| `build_all.bat` | Orchestrates the three-step production build |
| `requirements-build.txt` | PyInstaller + everything in `backend/requirements.txt` |
| `.v3_port` | Runtime-written port file used by the frontend in dev mode |
| `README.md` | Repo-level readme |

---

## `backend/`

The Python FastAPI + Socket.IO application. Every file has one responsibility.

| File | Role | Key exports |
|---|---|---|
| `main.py` | ASGI app assembly, uvicorn entry, route enumeration | `app`, `_fastapi`, `sio` |
| `db.py` | SQLite persistence — single source of truth | `init_db`, `config_get_all`, `config_replace_all`, `tracking_get_all`, `tracking_replace_all`, `jwt_config_set/get/exists`, `log_add`, `logs_since` |
| `config.py` | Path helpers + config wrappers, `bee_prompt.md` loader | `read_config`, `write_config`, `read_config_safe`, `default_config`, `set_data_dir`, `local_folder`, `extracted_folder`, `archive_folder`, `bee_prompt_text` |
| `activity.py` | Shared activity-log helper — prepends `[[level=…]]` | `write(ref, content, *, when, level)` |
| `events.py` | Socket.IO event constants + thread-safe emit | Event names; `configure`, `emit` |
| `ports.py` | Port picker (preferred 8765, skips 5000/8080/47321) | `find_free_port`, `write_port_file` |
| `scanner.py` | `/api/scan/*` router + local walk + upload endpoint | `run_scan`, `scan_upload` |
| `sync.py` | `/api/sync/*` router — Box → Local | `sync_box_to_local`, `_sync_thread` |
| `extractor.py` | `/api/extract/*` router — full pipeline | `run_extraction`, `build_extract_folder`, `write_extraction_log` |
| `viewer.py` | `/api/view/*` router — export browser | `router`, `_gather_files` |
| `insights.py` | `/api/insights` + log-entries endpoint | `router`, `get_log_history` |
| `chat.py` | `/api/chat/*` router — Bee dispatcher + ICA transport + Box/ICA SSE streams | `route_chat_message`, `ica_chat`, `_ica_send_and_stream`, `test_box_stream`, `test_ica_stream`, `initialize_ica_system_prompt` |
| `settings.py` | `/api/settings/*` router — CRUD + SSE test endpoints | `router`, `_mask_config`, `_deep_merge` |
| `box_client.py` | Box JWT client factory + upload helper | `get_box_client`, `upload_file_to_box` |
| `tracking.py` | Thin wrapper — `load_tracking`, `save_tracking` route to `db.py` | `load_tracking`, `save_tracking` |
| `pdf_text_extractor.py` | Shared core engine — decrypt, parse, export | `open_and_decrypt_pdf`, `extract_text_by_page`, `build_structured_json`, `export_to_word/_csv/_json` |
| `prompt/bee_prompt.md` | Bee persona/rules — sent to ICA as system prompt | — |

Note: `pdf_text_extractor.py` also lives in V1, V2, and the web app — changes must be replicated across all four copies. See [Business-Rules.md](Business-Rules.md) for the shared-engine constraint.

---

## `frontend/`

React + TypeScript + Vite + Tailwind.

| Path | Role |
|---|---|
| `src/App.tsx` | HashRouter, sidebar, route table, global overlays |
| `src/main.tsx` | React entry point |
| `src/index.css` | Tailwind directives + global styles |
| `src/pages/Home.tsx` | Landing card grid |
| `src/pages/Sync.tsx` | Sync controls + live log |
| `src/pages/Scan.tsx` | Scan/upload + always-on Diagnostics panel |
| `src/pages/Extract.tsx` | Extract controls + per-file event stream |
| `src/pages/View.tsx` | Browse extracted outputs |
| `src/pages/Insights.tsx` | Dashboard charts |
| `src/pages/Logs.tsx` | Activity-log table with period/level filters — parses `[[level=…]]` |
| `src/pages/Settings.tsx` | Full config UI with SSE tests |
| `src/components/Sidebar.tsx` | Nav + theme toggle |
| `src/components/ChatBubble.tsx` | Global floating chat |
| `src/components/ui/*` | Button, Badge, Spinner, EmptyState, Toast |
| `src/hooks/useApi.ts` | `get`, `post`, `upload` with rich outcome; exports `apiBase()` |
| `src/hooks/useSocket.ts` | Singleton `socket.io-client` connection; `useSocketEvent(name, cb)` |
| `src/store/theme.ts` | Dark/light, persisted to localStorage |
| `src/store/run.ts` | Sync/scan/extract state; binds socket handlers |
| `src/store/chat.ts` | Chat history + hydrate helpers |
| `src/store/toast.ts` | Toast queue |
| `src/types/index.ts` | All TypeScript interfaces |
| `vite.config.ts` | Build config — `base: './'`, `outDir: '../electron/renderer'` |
| `tailwind.config.js` | Custom tokens: `sidebar #0A0E1A`, `accent #6C63FF`, `bg-dark #0F1117` |
| `tsconfig.json`, `tsconfig.node.json`, `tsconfig.tsbuildinfo` | TypeScript setup |
| `package.json` | React 18.3.1, react-router 6, zustand 4.5, socket.io-client 4.7, recharts 2.12, lucide-react 0.447 |

---

## `electron/`

The desktop shell.

| Path | Role |
|---|---|
| `main.js` | Main process — port picker, backend spawn, health poll, IPC handlers, ICA login window |
| `preload.js` | contextBridge exposing `electronAPI.{getApiPort, getBackendLogPath, icaLogin, isElectron}` |
| `package.json` | electron-builder config (NSIS + portable targets) |
| `assets/icon.ico` | App icon |
| `renderer/` | Vite build output (built into by `frontend/vite.config.ts`) |
| `resources/backend/` | PyInstaller build output — `backend.exe` and its data files |
| `dist/` | electron-builder output — `PDF-Extractor-V3-Setup-3.0.0.exe`, `PDF-Extractor-V3-Portable-3.0.0.exe` |

---

## Cross-Cutting Files at the Repo Root

| Path | Purpose |
|---|---|
| `docs/pdf-extractor-v3/` | This documentation set |
| `docs/pdf-extractor-v2/` | Older docs — retained for archaeology |
| `PDF Extractor/` | V1 source — Tkinter + Box OAuth2 |
| `PDF Extractor V2/` | V2 source — Tkinter + local sync + Box upload |
| `WatsonX Challenge - Web/` | Flask web app + watsonx AI |
| `ICA Cookie Parser/` | Standalone HTML utility for manual ICA cookie refresh |

The four apps share the `pdf_text_extractor.py` engine — each has its own copy.

---

## Path Resolution at Runtime

| Concept | Dev | Packaged |
|---|---|---|
| BASE_DIR (backend package dir) | `PDF Extractor V3/backend/` | PyInstaller `_MEIPASS` temp dir |
| Data dir | `PDF Extractor V3/backend/` (unless `--data-dir` given) | `%APPDATA%\PDF Extractor V3\` (Electron passes `--data-dir`) |
| `bee_prompt.md` | `backend/prompt/bee_prompt.md` | `<_MEIPASS>/prompt/bee_prompt.md` |
| Renderer HTML | Vite dev server URL | `electron/renderer/index.html` |
| Backend binary | `python backend/main.py` | `electron/resources/backend/backend.exe` |

`config.set_data_dir()` handles the switch — called once from `main.py` argparse.

---

## Related

- [Technical-Architecture.md](Technical-Architecture.md) — layered view
- [System-Design.md](System-Design.md) — runtime view
- [Developer-Onboarding.md](Developer-Onboarding.md) — first-day walkthrough
