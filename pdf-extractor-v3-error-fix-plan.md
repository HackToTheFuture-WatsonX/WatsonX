# PDF Extractor V3 — Bug Fix & Error Visibility Plan

## Top-Level Overview

The application has a scan operation whose results are silently discarded: the
`scan:done` SocketIO event payload is ignored in the frontend store, so scan
summary data (found/total/pending/completed) and error details never reach the
UI. In addition, there is no mechanism for the Scan page to display an error
to the user when a scan fails, and the toast notification system already
present in the project is unused for run-time errors.

This plan fixes the data flow bug, adds a `scanSummary` field to the store,
adds error-detail UI to the Scan page (matching the pattern already used on the
Sync page), and ensures unexpected backend errors emit a toast notification.

**Scope**:
- `PDF Extractor V3/frontend/src/store/run.ts`
- `PDF Extractor V3/frontend/src/pages/Scan.tsx`
- `PDF Extractor V3/frontend/src/types/index.ts`
- `PDF Extractor V3/backend/scanner.py` (minor: align error key with sync pattern)

**Non-goals**:
- Changing the Sync, Extract, or Settings pages (already working)
- Adding new toast calls beyond error paths that have no existing UI
- Database schema or API changes

---

## Sub-Task 1 — Align backend `scanner.py` error payload

### Intent
When `run_scan()` raises an unhandled exception, `_scan_thread` emits
`{"error": "..."}` (singular string). The normal-success path emits no `error`
key at all. Neither case includes an `errors` array consistent with the Sync
convention. Unifying both to always emit a clear `error` key on failure makes
the frontend handler simpler and less error-prone.

### Expected Outcomes
- On scan exception: `scan:done` payload is `{"error": "<message>"}` — unchanged (already correct), but `_status["running"]` is still set to False correctly.
- On scan success/cancel: payload is `{"found", "total", "pending", "completed", "cancelled?"}` — unchanged.
- No functional change to normal scan flow.

### Todo List
1. In `_scan_thread`, ensure `_status["running"] = False` is set even on exception (it already is via `finally`). Verify no regression — no code change needed here.
2. Confirm the exception branch emits `{"error": str(exc)}` — already done. No change required.

> **Note**: After reading the code, the backend scanner is already correct. No changes are needed in `scanner.py`.

### Relevant Context
- [`scanner.py:_scan_thread`](PDF%20Extractor%20V3/backend/scanner.py:83)
- The exception path at line 89 already emits `{"error": str(exc)}`

### Status
[x] done — no code change needed; backend is already correct

---

## Sub-Task 2 — Add `ScanSummary` type and `scanSummary` state to the store

### Intent
The `RunStore` interface has no field to hold scan completion data. The
`scan:done` socket handler ignores its payload entirely. This sub-task adds the
missing type and state field, and fixes the event handler to capture and store
the payload — including errors — exactly as `sync:done` does.

### Expected Outcomes
- `RunStore` exposes a `scanSummary` field of type `ScanSummary | null`
- `startScan` resets `scanSummary: null` at the start of each run
- `scan:done` handler stores the payload in `scanSummary` and handles the
  `error` (fatal scan exception) case by appending to a new `scanError` field
  or by reusing the summary's `error` field
- Scan page components can read `scanSummary` from the store

### Todo List
1. In `run.ts`, add a `ScanSummary` interface:
   ```ts
   interface ScanSummary {
     found: number
     total: number
     pending: number
     completed: number
     error?: string
     cancelled?: boolean
   }
   ```
2. Add `scanSummary: ScanSummary | null` to the `RunStore` interface.
3. Initialise `scanSummary: null` in the store's initial state.
4. In `startScan`, reset `scanSummary: null` alongside `scanFound: 0`.
5. Fix the `scan:done` handler — replace the no-arg arrow with:
   ```ts
   _socket.on('scan:done', (d: ScanSummary) => {
     set({ scanRunning: false, scanSummary: d })
   })
   ```

### Relevant Context
- [`run.ts:RunStore interface`](PDF%20Extractor%20V3/frontend/src/store/run.ts:55)
- [`run.ts:scanRunning initial state`](PDF%20Extractor%20V3/frontend/src/store/run.ts:99)
- [`run.ts:startScan`](PDF%20Extractor%20V3/frontend/src/store/run.ts:101)
- [`run.ts:scan:done handler`](PDF%20Extractor%20V3/frontend/src/store/run.ts:158) ← **the bug**
- Sync pattern to mirror: `sync:done` handler at line 147–152

### Status
[ ] pending

---

## Sub-Task 3 — Add error display UI to the Scan page

### Intent
Even after the store fix, the Scan page never reads `scanSummary` — it only
reads `scanRunning` and `scanFound`. This sub-task adds a summary row and an
error detail panel (matching the Sync page's design) so users can see:
- A "N found during scan" badge after a successful scan
- An "Error" badge and red detail box if a scan error occurred

### Expected Outcomes
- After a successful scan the page shows a post-scan summary badge (found
  count) alongside the existing Total/Completed/Pending badges from the REST
  endpoint refresh.
- If the scan ended with `scanSummary.error` set, a red error panel is shown
  below the stats, containing the error message, styled identically to the
  Sync page error panel.
- If the scan was cancelled, no error panel is shown (just the normal stats).
- No change to the file table rendering.

### Todo List
1. In `Scan.tsx`, import `scanSummary` from the store:
   ```ts
   const scanSummary = useRunStore((s) => s.scanSummary)
   ```
2. Below the stats row (`{data && ...}`), add a conditional error panel:
   ```tsx
   {scanSummary?.error && !scanSummary.cancelled && (
     <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-4">
       <p className="text-sm font-semibold text-red-700 mb-1">Scan error</p>
       <p className="text-xs text-red-600 font-mono break-words">⚠ {scanSummary.error}</p>
     </div>
   )}
   ```
3. Optionally, show a small "N found in last scan" badge (using `scanSummary.found`) in the stats row when the scan has just completed and `scanSummary` is populated.

### Relevant Context
- [`Scan.tsx:stats row`](PDF%20Extractor%20V3/frontend/src/pages/Scan.tsx:57)
- [`Sync.tsx:error panel`](PDF%20Extractor%20V3/frontend/src/pages/Sync.tsx:67) — design to replicate
- [`run.ts:scanSummary`](PDF%20Extractor%20V3/frontend/src/store/run.ts:99) — will exist after Sub-Task 2

### Status
[ ] pending

---

## Sub-Task 4 — Wire the toast store for unexpected run errors

### Intent
Currently, if the backend emits `sync:done` with `{"error": "..."}` (an
unhandled exception in `_sync_thread`), the log gets a `⚠` line but no toast
is shown. Similarly, after Sub-Task 2, a scan fatal error is stored in
`scanSummary.error` but nothing proactively notifies the user who may be on a
different page. The existing `useToastStore` (already wired into the app) is
the right channel for these proactive alerts.

### Expected Outcomes
- When `sync:done` arrives with `d.error` set, a `useToastStore.show(...)` call
  fires with `kind: 'error'` in addition to the existing log append.
- When `scan:done` arrives with `d.error` set, a toast fires with `kind: 'error'`.
- Error toasts are **persistent** (no auto-dismiss) — `durationMs: 0` — and can
  only be removed by the user clicking the `×` button already rendered on every toast.
- No toast fires on cancelled operations.

### Todo List
1. In `run.ts`, import `useToastStore`:
   ```ts
   import { useToastStore } from './toast'
   ```
2. In the `sync:done` handler, after the existing log append, add:
   ```ts
   useToastStore.getState().show(`Sync error: ${d.error}`, 'error', 0)
   ```
   The third argument `0` passes `durationMs = 0` to `toast.ts:show`, which skips
   the `setTimeout` auto-dismiss (see [`toast.ts:24`](PDF%20Extractor%20V3/frontend/src/store/toast.ts:24)).
3. In the new `scan:done` handler (added in Sub-Task 2), handle the error case:
   ```ts
   _socket.on('scan:done', (d: ScanSummary) => {
     set({ scanRunning: false, scanSummary: d })
     if (d?.error) useToastStore.getState().show(`Scan error: ${d.error}`, 'error', 0)
   })
   ```
   Same `durationMs = 0` — sticky until dismissed.

### Relevant Context
- [`toast.ts`](PDF%20Extractor%20V3/frontend/src/store/toast.ts)
- [`run.ts:sync:done handler`](PDF%20Extractor%20V3/frontend/src/store/run.ts:147)
- [`run.ts:scan:done handler`](PDF%20Extractor%20V3/frontend/src/store/run.ts:158)

### Status
[ ] pending

---

## Summary of Files Changed

| File | Change |
|------|--------|
| `frontend/src/store/run.ts` | Add `ScanSummary` type + `scanSummary` field; fix `scan:done` handler; add toast calls |
| `frontend/src/pages/Scan.tsx` | Read `scanSummary`; add error panel UI |
| `backend/scanner.py` | No changes needed |
| `frontend/src/types/index.ts` | No changes needed (ScanSummary is internal to run.ts) |
