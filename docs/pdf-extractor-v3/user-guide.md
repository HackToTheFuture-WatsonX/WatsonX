# User Guide

The complete page-by-page tour of PDF Extractor V3. Assumes you have completed the initial setup in [Quickstart.md](Quickstart.md).

---

## The Application Shell

- **Left sidebar** — navigation, dark/light toggle at the bottom.
- **Main content area** — the active page.
- **Floating chat bubble** — bottom-right; always available on every page.
- **Toast overlay** — appears bottom-centre for transient notifications.

The route bar in the URL (`#/sync`, `#/scan`, …) mirrors the sidebar; you can bookmark or link to specific pages when running in dev mode (Electron uses hash routing internally).

---

## Home ( `/` )

Landing card grid. Each card links to a page and shows a one-line status. Use it as a launchpad or ignore it once you know the sidebar.

---

## Sync ( `/sync` )

Downloads PDFs from Box to the Local Folder and archives the source on Box.

### Controls

- **Sync Now** — start a sync.
- **Cancel** — appears while a sync is running; requests cancellation (respected at the next per-item iteration).

### Live Log

Every action is streamed line-by-line:
```
Connecting to Box (source folder 12345)…
  Downloading: BG-2025-01234.pdf
  ✅ Saved: BG-2025-01234.pdf
  📦 Archived on Box: BG-2025-01234.pdf
Sync complete — 3 downloaded, 2 skipped, 0 failed.
```

### Behaviour Notes

- A file already present in `Local Folder/` is skipped, not overwritten (see [Business-Rules.md](Business-Rules.md#br-4-idempotent-sync)).
- If `settings.search_subfolders` is on, Box subfolders are mirrored locally.
- On completion, a scan auto-runs so newly downloaded files land in the tracking table immediately.
- The activity log row appears with the appropriate level:
  - **Info** — success (including empty batches)
  - **Warning** — per-item errors or user cancel
  - **Error** — the whole sync threw an exception

---

## Scan ( `/scan` )

Registers local PDFs in the tracking database and lets you upload ad-hoc files.

### Controls

- **Upload Files** — opens the OS file picker; accepts one or many `.pdf` files. Each file is streamed to the backend with live per-file progress.
- **Scan Now** — walks `Local Folder/` recursively and registers each PDF as **Pending** (unless already tracked).
- **Cancel** — requests cancellation of a running scan.

### Upload Semantics

- Non-PDF files → rejected with `Error`.
- Duplicate filename → **Skipped — already exists**. The existing tracking status is preserved.
- Success → **Uploaded**, then row shows in the Pending list.

Each file gets **exactly one progress row** that updates in place as its state changes: `Saving… → Uploaded / Skipped / Error`. The row is matched to backend `upload:progress` events by 1-based index (falling back to filename), so per-file transitions never accumulate extra lines. Batch of 10 files → 10 rows, each animating through its own states.

The immediate seed also includes a `reason: "Sending to server…"` on each row, so the panel populates visibly the instant you confirm the picker — even before the backend answers.

### Diagnostics Panel

An always-visible collapsible `<details>` block at the top of the page shows:

- Resolved API base URL.
- Current scan and upload state.
- Backend log file path (with **Copy path** button).
- Last button-click timestamp.
- Last file-picker outcome.
- Last fetch URL, HTTP status, and response body preview.

Use it when "the button did nothing" — it will name the layer that failed (click never fired, picker cancelled, fetch returned 4xx/5xx, network error).

### Table

Columns: **File Name · Ref Number · Status · Last Extracted**. Newest at the bottom. Rows update live during scan/upload events.

---

## Extract ( `/extract` )

Runs the full extraction pipeline over every **Pending** row.

### What Extraction Does (per file)

1. Read the PDF, decrypt using the shared password.
2. Extract text page-by-page.
3. Parse into a structured JSON (`report_summary`, `employment_checks`, `professional_reference_checks`, `other_checks`).
4. Compute `ref_number` (case reference or filename stem).
5. Export three files to the dated hierarchy under `Local Folder/Extracted/`:
   - `<ref>.docx` under `Word Extracts/<year>/<Mon_YYYY>_Extracts/Week_NN/<yyyy-mm-dd>/<ref>/`
   - `<ref>.xlsx` similarly under `CSV Extracts/`
   - `<ref>.json` similarly under `JSON File Extracts/`
6. If a Box `output_folder_id` is configured, upload all three outputs mirroring the local hierarchy.
7. Move the source PDF from `Local Folder/` to `Local Folder/Archive/` (with a `_YYYYMMDDHHMMSS` suffix if a collision would occur).
8. Update the `tracking_files` row: `status = Completed`, `last_extracted`, `ref_number`, `archive_path`.
9. Write an extraction log row to `extraction_logs` with the full manifest.

### Controls

- **Run Extraction** — start the pipeline (no-op if already running).
- **Cancel** — respected at the boundary of the next file.

### Live Events

- `extract:progress` — `{current, total, percent, name}` on every file start.
- `extract:result` — `{status: "ok"|"error", fname, ref, word, excel, json, upload}` on every file completion.
- `extract:done` — `{completed, failed, total, [cancelled]}` at the end.

### Failure Handling

A per-file exception is caught, logged (`FAILED: <fname>`), and the file stays `Pending`. Re-running Extraction retries it.

---

## View ( `/view` )

Browse extracted reports. Rows group by reference number and show the location of the Word, Excel, and JSON output. Clicking a file button opens it in the default OS handler.

Use this page as the day-to-day "give me the Word doc for Ref X" surface.

---

## Insights ( `/insights` )

Read-only dashboard.

- **Completion stats** — Total / Pending / Completed cards.
- **Weekly and monthly counts** — extracted-per-day chart (Recharts).
- **Log history summary** — quick counts by level over the selected period.

---

## Logs ( `/logs` )

Activity-log browser. Every user-visible action writes a row.

### Filters

- **Period** — day, week, month, year.
- **Level** — All, Info, Warning, Error.
- **Rows per page** — 15 / 20 / 30 / 50.

### Row Shape

- **Timestamp** — local time.
- **Ref Number** — either a report reference (extractor) or a category (`SYNC`, `SCAN`, `UPLOAD`, `SETTINGS`, `JWT-UPLOAD`, `BOX-TEST`, `ICA-TEST`, `ICA-INIT`).
- **Level** — Info / Warning / Error badge (derived from the `[[level=…]]` marker prepended by `backend/activity.py`).
- **Message** — the first non-empty line.

Click the chevron to expand a row for the full multi-line content.

---

## Settings ( `/settings` )

Central configuration hub.

### Sections

1. **PDF Password** — the shared decryption password.
2. **Box** — folder IDs + JWT upload; **Test Box** button (SSE stream).
3. **ICA** — cookie / team / chat, **Sign in to ICA** (browser-assisted capture), **Test ICA** and **Initialize ICA System Prompt** (both SSE streams).
4. **Local Folders** — override the `Local Folder/`, `Extracted/`, `Archive/` locations.
5. **Sync Settings** — subfolder search, file extension filter, overwrite policy, activity logging, chat enable.

### Behaviours

- Secrets (`pdf_password`, `ica.full_cookie`) always render as `••••••••`. Sending `••••••••` back on Save is treated as "unchanged" and keeps the on-disk secret.
- Changing `ica.chat_id` auto-clears `system_prompt_chat_id` — the UI immediately flips to **Not yet primed** and you'll need to re-initialize.
- All connection tests are true SSE streams — you see the step-by-step progress live.

---

## Chat with Bee

The floating bubble opens a chat surface.

### Local skills (work offline / without ICA)

| Say | Bee does |
|---|---|
| `sync` / `sync now` / `sync box` | Runs sync, auto-scans, reports counts |
| `scan` / `rescan` / `scan folder` | Runs a scan |
| `extract` / `run extract` / `process files` | Runs the extraction pipeline |
| `file status` / `how many files` | Prints Total / Pending / Completed |
| `logs today` / `logs this week` / `logs this month` / `logs this year` | Prints recent extraction log history |
| `look up <name-or-ref>` / `find <name>` / `report for <name>` | Retrieves the extracted summary for that record |
| `generate report for <name>` | Lists matches; if unique, prompts for Word / Excel / JSON |

### ICA-backed

Anything else falls through to ICA — free-form conversation grounded in the Bee system prompt (see `backend/prompt/bee_prompt.md`). If ICA isn't configured, Bee falls back to a help menu.

### Hallucination Guard

If ICA replies with content that looks like fabricated report fields, V3 replaces it with:

> I can only answer from our extracted records. Please use 'look up [name or reference]' to retrieve the report first.

See [Business-Rules.md](Business-Rules.md#br-12-hallucination-guard).

---

## Keyboard Shortcuts

None currently mapped. `Ctrl+Shift+I` opens DevTools only in dev mode; in packaged builds DevTools is disabled by design.

---

## Where to Go Next

- **[FAQ.md](FAQ.md)** — common questions.
- **[Troubleshooting.md](Troubleshooting.md)** — problem → cause → fix.
- **[Glossary.md](Glossary.md)** — every term used above.
