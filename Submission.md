# ClearCheck — Submission

> Built with **IBM Bob** (AI SDLC partner) and powered at runtime by **IBM Box** and **IBM Consulting Advantage (ICA)**.

---

## Solution Impacts

- **Simplify personal/team process(es)** — Collapses a multi-step manual routine (download → unlock → read → re-key) into a five-click pipeline: **Sync → Scan → Extract → View → (optional) Chat**.
- **Reduce time and/or manual effort to complete routine task(s)** — A batch of ~50 pending reports that took a full business day to process by hand completes in minutes; no manual file downloads, renames, or spreadsheet re-entry.
- **Improve the accuracy and consistency of output(s)** — A deterministic parser produces the same three-file layout (Word / Excel / JSON) for every report, eliminating misread verdicts (e.g. "Cleared" vs "Not Cleared") and inconsistent hand-keyed data.
- **Reduce operational risk / ensure compliance** — Every action (sync, scan, upload, extract, settings save, connection test) writes a timestamped, level-tagged row to the `extraction_logs` table, creating an immutable, queryable audit trail linked by case reference.
- **Reduce time and effort accessing information** — The File Viewer groups outputs by type and case reference, and the **Bee** assistant answers plain-language questions grounded strictly in extracted records — no reopening PDFs.
- **Speed up product/offering development** — ClearCheck itself was generated, refactored, and documented with **IBM Bob**, an AI SDLC partner, compressing build time across code, docs, and boilerplate.
- **Innovation and exploration of new features** — Brings conversational AI (ICA) and real-time telemetry (Socket.IO) to a workflow previously locked behind encrypted, unstructured PDFs.

---

## Solution Statement

Every day, HR teams across organisations receive password-protected background check report PDFs by email — and every day, staff manually download those files, unlock them, read through dense two-column layouts, and re-enter critical data into spreadsheets. One misread verdict — "Cleared" mistaken for "Not Cleared" — can trigger a compliance failure. There is no audit trail, no progress visibility, and no way to interrogate a report without physically reopening the PDF. This is the problem **ClearCheck** solves.

ClearCheck is a fully portable, zero-dependency Windows desktop application that automates the complete background check report pipeline — from the moment a report lands in **IBM Box**, to structured, searchable, exportable data — without requiring a single manual file operation. The solution is built on integrated layers of technology, and the application itself was developed with **IBM Bob**, an AI SDLC (Software Development Lifecycle) partner used to generate, refactor, and document the codebase.

The pipeline begins in the cloud. Background check reports are stored in a configured **IBM Box** folder, and ClearCheck syncs those PDFs to the local machine using a **JWT service-account** connection (`boxsdk` v3) — no interactive login, no expiring OAuth tokens. It then scans the local folder, registers each pending report in a SQLite tracking table, and runs the extraction pipeline: **PyMuPDF** decrypts the password-protected file, a deterministic structured parser routes each page to the correct handler (cover summary, employment checks, professional reference checks, database/other checks such as adverse media, sanctions, and bankruptcy), and the extracted data is written to three output formats — a formatted **Word** document (`python-docx`), a structured **Excel** workbook (`openpyxl`), and a machine-readable **JSON** file. All three are uploaded back to a Box output folder automatically, mirroring the local dated folder hierarchy. The source PDF is then archived. Every step is logged to a SQLite audit database with timestamps and reference numbers — a permanent, queryable record of every extraction ever run.

The entire experience is real-time. Long-running operations (Box sync, folder scan, extraction) stream live progress events to the UI over **Socket.IO** (WebSocket), so HR staff see exactly which file is being processed and when it completes — no polling, no page refreshes, no guessing.

Finally, **IBM Consulting Advantage (ICA)** powers a natural-language assistant named **Bee**, integrated directly into the application. Rather than reopening PDFs or navigating menus, HR staff can simply ask, "What was the overall status for the case received last Monday?" or "Look up John Smith." They can also drive the application by intent — "sync now," "scan folder," "run extraction," "file status," or "logs this week" — which Bee routes to the corresponding backend operation. Crucially, Bee answers **only** from data already extracted and stored, and every ICA reply passes a regex-based hallucination guard before it reaches the user, ensuring accurate, traceable responses with no fabricated verdicts.

The result is a solution that eliminates manual file handling, enforces a consistent extraction process, produces audit-ready records, and brings conversational AI to a domain previously locked behind unstructured PDFs. It runs as a single portable `.exe` that deploys to any Windows machine with no installation, no system Python, and no IT involvement required.

**ClearCheck turns a compliance risk into a compliance asset.**

---

## Technical Statement

ClearCheck is built on a modern, production-grade stack chosen for portability and zero friction on corporate Windows machines — no system dependencies, no IT provisioning, no installation. The application was developed using **IBM Bob**, an AI SDLC partner used across the build for code generation, refactoring, debugging, and documentation, while its runtime AI is powered by **IBM Consulting Advantage (ICA)**.

**Distribution.** The app ships as a fully self-contained Windows executable built with **Electron 32** and **electron-builder**, producing both an NSIS installer and a portable single-file `.exe`. Inside, two runtimes co-exist: a Chromium React frontend (**React 18, TypeScript, Vite, Tailwind CSS**) and a **PyInstaller**-bundled Python 3.12 backend (**FastAPI, Uvicorn, python-socketio**) carrying its own interpreter and every package — PyMuPDF, python-docx, openpyxl, `boxsdk` v3. Neither Python nor Node.js need be present on the target machine.

**Backend.** The backend exposes seven REST routers — **scan, sync, extract, view, insights, chat, settings** — and a Socket.IO event bus in **`async_mode="asgi"`** (a deliberate migration from threading mode, which silently dropped events from worker threads; workers now schedule emits onto the captured Uvicorn loop via `events.emit()`). Long-running operations stream live progress to the frontend without polling. Event names are defined as constants in `events.py` and consumed by the `useSocket` hook.

**Intake & PDF core.** Reports sync from a configured **IBM Box** folder to the local machine via a **JWT service-account** connection — no interactive OAuth, no token expiry. **PyMuPDF (`fitz`)** decrypts each password-protected PDF, then a deterministic parser routes pages by ALL-CAPS heading: Page 0 (cover) yields the summary — subject name, case reference, verdict (Cleared / Not Cleared), receipt date, package type — and later pages feed employment checks, professional reference checks, and database/other checks (adverse media, sanctions, bankruptcy). Extracted data is exported to **Word, Excel, and JSON** simultaneously and uploaded back to Box.

**Persistence.** All state — configuration, file tracking, JWT credentials, and logs — lives in a single **SQLite** database (`pdf_extractor_v3.db`) in `%APPDATA%\PDF Extractor V3\`, running in WAL mode so worker threads write while the main thread reads. Every run is timestamped in an append-safe `extraction_logs` table with a machine-readable `[[level=info|warning|error]]` marker — an immutable compliance record.

**Conversational AI (ICA + Bee).** The **ICA** integration at `POST /api/chat/send` powers the **Bee** assistant, governed by a personalised prompt (`backend/prompt/bee_prompt.md`). Bee is record-grounded and read-only — answering *only* from extracted JSON, refusing anything not in the data — and every reply passes a regex hallucination guard (`chat.py:_HALLUCINATION_PATTERNS`). Bee also routes intents (`sync`/`scan`/`extract`, `file status`, `logs this week`, `look up <name/ref>`, `generate report for <name>`) to backend operations, forwarding only general questions to ICA. The result is a pipeline deterministic from intake to export, fully auditable, and deployable with a double-click.

---

## Technology Credits

| Layer | Technology |
|---|---|
| Development (build-time) | **IBM Bob** — AI SDLC partner (code generation, refactor, debug, docs) |
| Cloud storage & transport | **IBM Box** (JWT service-account, `boxsdk` v3) |
| Desktop shell | Electron 32 + electron-builder (NSIS + portable `.exe`) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, Uvicorn, python-socketio (`async_mode="asgi"`), PyInstaller |
| PDF engine | PyMuPDF (`fitz`), python-docx, openpyxl |
| Persistence | SQLite (`pdf_extractor_v3.db`, WAL mode) |
| Conversational AI (runtime) | **IBM Consulting Advantage (ICA)** — "Bee" assistant |
