# Feature Scope

Definitive list of what the shipping V3 release does, what is planned, and what is intentionally out of scope. Anchored to the code as of version `3.0.0`.

---

## In Scope (Shipping in 3.0.0)

### Core Pipeline

| Feature | Location | Notes |
|---|---|---|
| Box → Local sync | `backend/sync.py` | Downloads every PDF in the configured Box source folder, mirrors subfolders when enabled, archives the source on Box after a successful download |
| Local scan | `backend/scanner.py` | Walks `Local Folder/` and registers PDFs in the `tracking_files` table as `Pending`; purges rows whose files no longer exist |
| Ad-hoc upload | `backend/scanner.py:scan_upload` (`POST /api/scan/upload`) | Multipart upload; per-file Socket.IO progress; duplicates skipped |
| Extraction | `backend/extractor.py` | Decrypt, parse, export Word/Excel/JSON, optional Box upload of outputs, archive source on disk |
| Bulk cancel | Each pipeline module | `POST /api/{sync,scan,extract}/cancel` flips a `threading.Event` respected on the next iteration |

### Data Persistence

| Feature | Location | Notes |
|---|---|---|
| SQLite database | `backend/db.py` | Single file `pdf_extractor_v3.db` in the user data dir; WAL mode |
| Config store | `config` table | Full config dict as one row per top-level key |
| Tracking store | `tracking_files` table | One row per known PDF |
| JWT store | `jwt_config` table | Single row (`id=1`) holding the Box service-account JSON |
| Activity log | `extraction_logs` table | Levelled activity rows with `[[level=…]]` marker |

### Frontend Pages

| Route | File | Purpose |
|---|---|---|
| `/` | `pages/Home.tsx` | Landing card grid with quick actions |
| `/sync` | `pages/Sync.tsx` | Trigger sync + live log |
| `/scan` | `pages/Scan.tsx` | Trigger scan, upload files, view Pending/Completed list, always-on Diagnostics panel |
| `/extract` | `pages/Extract.tsx` | Trigger extract + per-file event stream |
| `/view` | `pages/View.tsx` | Browse Word/Excel/JSON exports by reference |
| `/insights` | `pages/Insights.tsx` | Completion counters + charts |
| `/logs` | `pages/Logs.tsx` | Activity-log table with period + level filters |
| `/settings` | `pages/Settings.tsx` | Credentials, folder IDs, sync toggles, connection tests, ICA priming |

### Cross-Cutting

| Feature | Location | Notes |
|---|---|---|
| Socket.IO progress streaming | `backend/events.py` + `frontend/src/hooks/useSocket.ts` | Thread-safe emit; async_mode="asgi" |
| Server-Sent Events for tests | `backend/settings.py:test_box_stream_endpoint`, `test_ica_stream_endpoint`, `init_ica_stream_endpoint` | Live step-by-step feedback for Box/ICA tests and ICA priming |
| Secret masking | `backend/settings.py:_mask_config` | `pdf_password`, `ica.full_cookie` returned as `••••••••` |
| Activity level tagging | `backend/activity.py` | Every write prepends `[[level=info|warning|error]]` |
| Dark/light theme | `frontend/src/store/theme.ts` | Persisted to `localStorage` |
| Toast notifications | `frontend/src/store/toast.ts` + `components/ui/Toast.tsx` | Global overlay |
| Floating chat bubble | `frontend/src/components/ChatBubble.tsx` | Always available |
| Diagnostics panel | `frontend/src/pages/Scan.tsx` | Records last click, pick, and fetch outcome — makes packaged-app failures debuggable without DevTools |

### AI / Chat

| Feature | Location | Notes |
|---|---|---|
| Bee assistant | `backend/chat.py:route_chat_message` | Rule-router that dispatches to local skills or ICA |
| Local skills | `chat.py` — `skill_lookup_report`, `_skill_open_report`, `_skill_list_all_reports`, `trigger_sync_for_chat`, `trigger_scan_for_chat`, `trigger_extraction_for_chat` | Deterministic; work without ICA |
| ICA two-POST flow | `chat.py:_ica_send_and_stream` | PROMPT then ANSWER trigger; reads SSE `answer:` stream |
| Bee system-prompt priming | `chat.py:initialize_ica_system_prompt` + `backend/prompt/bee_prompt.md` | Sent as the first prompt on a chat_id; recorded in `system_prompt_chat_id` |
| Hallucination guard | `chat.py:_is_hallucinated_reply` | Refuses replies that look like fabricated report content |

### Distribution

| Feature | Location | Notes |
|---|---|---|
| PyInstaller backend build | `backend.spec`, `build_backend.py` | One-folder → `electron/resources/backend/backend.exe` |
| Vite frontend build | `frontend/vite.config.ts` | Base path `./` so `file://` loads work under Electron |
| Electron packaging | `electron/package.json:build` | `electron-builder --win` → NSIS + portable |
| One-shot build | `build_all.bat` | Runs all three steps sequentially |

---

## Planned (Post-3.0.0)

| Feature | Rough scope |
|---|---|
| Auto-sync scheduler | Wire `settings.sync.auto_sync_enabled` + `auto_sync_interval_minutes` to a background timer |
| macOS + Linux packaging | Additional `electron-builder` targets |
| Bulk retry of failed extractions | Batch action on the Extract page |
| Export-to-CSV of activity logs | Logs page toolbar action |
| Signed installers | Code-signing certificate + `electron-builder` sign config |
| Encrypted secrets at rest | Wrap DB or credential columns with DPAPI |

Tracked in [Roadmap.md](Roadmap.md).

---

## Out of Scope (Deliberate)

| Not offered | Rationale |
|---|---|
| Multi-user server mode | V3 is a single-operator desktop client; multi-user would require auth, RBAC, HA infra |
| Report editing / redlining | V3 is a read-only extractor; edits belong in the source vendor system |
| Vendor-neutral PDF templates | The extractor is calibrated to the current vendor's report layout |
| Push notifications | Users are on-screen when they run V3 |
| Mobile client | Windows-only by charter |
| OCR of scanned PDFs | Source PDFs are always digitally generated; OCR would add PyTesseract weight without value |
| Non-Box source integration | Box is the sanctioned vendor channel; other sources go through Upload Files |

Changes to these boundaries require a signed-off ADR (see [ADR/](ADR/)).
