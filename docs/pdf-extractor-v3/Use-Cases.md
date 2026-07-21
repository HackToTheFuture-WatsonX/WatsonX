# Use Cases

Concrete scenarios drawn from live HR operations. Each use case names the actor, precondition, primary path, exceptions, and expected outcome.

---

## UC-1 — Daily Intake

**Actor:** HR operations analyst.
**Precondition:** Vendors have uploaded new encrypted PDFs to the configured Box source folder overnight.
**Trigger:** Analyst starts their day.

### Primary Flow

1. Launch **PDF-Extractor-V3-Portable-3.0.0.exe**.
2. Click **Sync** in the sidebar → **Sync Now**.
   *Live log shows each PDF downloaded from Box; archived on Box after success.*
3. Click **Scan Now** on the Sync page (or the auto-scan runs when sync completes).
   *The `tracking_files` table registers each new PDF as `Pending`.*
4. Navigate to **Extract** → **Run Extraction**.
   *Per-file progress events populate a live counter.*
5. Wait for the run to finish. Failures (if any) are surfaced inline with an `Error` badge.
6. Navigate to **View** to open the Word/Excel/JSON output for any file.

### Exceptions

- **Box source folder empty.** Sync completes with `0 downloaded, 0 skipped, 0 failed`; the row on the Logs page appears as **Info**, not Error. See [Troubleshooting.md](Troubleshooting.md#empty-sync-shown-as-error).
- **PDF password wrong.** Extraction fails per-file; the log row records the exception and the file stays `Pending`.
- **Box archive-move fails.** File still downloads locally; a warning line appears in the sync log; the file is not archived on Box. Manual cleanup required.

### Expected Outcome

A folder full of yesterday's reports converted to searchable exports, archived on Box, and available in the local `Extracted/` hierarchy.

---

## UC-2 — Ad-hoc Upload

**Actor:** HR analyst.
**Precondition:** A single-file report arrived by email rather than Box.
**Trigger:** Analyst needs to process it without waiting for the sync cycle.

### Primary Flow

1. Save the PDF anywhere on disk.
2. In V3, open **Scan** → click **Upload Files**.
3. Pick the PDF(s) in the OS file picker.
4. Watch the per-file progress rows (`Saving → Uploaded`).
5. Click **Extract** to process.

### Exceptions

- **File already exists in Local Folder.** Upload is skipped; the row shows **Skipped — already exists**. Tracking status is preserved (so a previously-completed file is not reverted to Pending).
- **Wrong file type.** Non-PDF uploads are rejected with an `Error` row; nothing is written to disk.

### Expected Outcome

A one-off report processed identically to any Box-sourced PDF, with an `UPLOAD` row in the activity log for audit.

---

## UC-3 — "Where's the report for Jose Manalo?"

**Actor:** HR analyst answering a stakeholder question.

### Primary Flow

1. Click the floating **Bee** chat bubble in the bottom-right corner.
2. Type `look up Jose Manalo` (or `find Jose` or `report for Jose Manalo`).
3. Bee returns the full extracted summary with subject name, case reference, overall status, employment/reference/database check results.
4. To open the underlying file, type `generate report for Jose Manalo` → pick **Word**, **Excel**, or **JSON**.
5. The associated exported file opens in the default OS handler.

### Exceptions

- **Multiple matches.** Bee lists all matches and asks "Which person did you mean?"
- **No match found.** `No records found matching '<query>'.`

### Expected Outcome

A conversational shortcut to the same content that would otherwise require navigating the View page and grepping filenames.

---

## UC-4 — Compliance Audit Sampling

**Actor:** Compliance reviewer.
**Precondition:** Random-sample audit of processed reports.

### Primary Flow

1. Open **Insights** → note the last-week and month-to-date completion counts.
2. Open **Logs** → filter to **This Month** → **Info** and **Error** rows.
3. For each sampled reference number, use Bee's `look up <ref>` to view the extracted summary, then open the Word export to compare against the source.

### Expected Outcome

Reviewer can trace every processed report from the timestamped activity-log row back to the exact Word/Excel/JSON files and the archived source PDF.

---

## UC-5 — Onboarding a New Operator Machine

**Actor:** IT admin / new operator.

### Primary Flow

1. Copy `PDF-Extractor-V3-Portable-3.0.0.exe` to the new machine (or install the NSIS setup).
2. Launch the app → **Settings**.
3. Paste the PDF password (used to decrypt vendor-supplied encrypted PDFs).
4. Enter the Box folder IDs (source, archive, output).
5. Upload the Box JWT service-account JSON via the **Upload JWT** button.
6. Click **Test Box** → wait for the SSE stream to show `Box connection is working`.
7. Click **Sign in to ICA** → complete IBMid SSO in the pop-up browser → V3 auto-captures the session cookie, team ID, and chat ID.
8. Click **Test ICA** → wait for `ICA connection is working`.
9. Click **Initialize ICA System Prompt** → the Bee persona is sent as the first prompt on the chosen chat; `system_prompt_chat_id` gets recorded so the UI shows **Primed**.

### Expected Outcome

Machine is fully configured and ready for the daily intake flow (UC-1). Every setting is stored inside `pdf_extractor_v3.db` and survives app restarts.

---

## UC-6 — Chat-Driven Batch Trigger

**Actor:** Power user on the go.
**Precondition:** New files just arrived in Box.

### Primary Flow

1. Open the Bee chat bubble.
2. Type `sync` → Bee downloads new PDFs, auto-scans, and reports counts.
3. Type `extract` → Bee runs the pipeline over all `Pending` rows.
4. Type `logs this week` → Bee prints the recent extraction history.

### Expected Outcome

The same full pipeline as UC-1 but driven entirely from the chat surface — useful in narrow screens or shared sessions.

---

## Cross-Cutting Notes

- Every use case above writes at least one row to the `extraction_logs` table with an appropriate `[[level=…]]` marker for the Logs page.
- Long-running operations (sync, scan, upload, extract) stream progress events over Socket.IO. Navigating away and back mid-run rehydrates state from the run store — no progress is lost visually.
- ICA-dependent use cases (UC-3, UC-4, UC-6) degrade gracefully when ICA is not configured: Bee still handles the deterministic skills (`look up`, `sync`, `scan`, `extract`, `file status`, `logs`) locally.
