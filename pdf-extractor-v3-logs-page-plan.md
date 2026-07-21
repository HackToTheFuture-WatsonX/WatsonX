# PDF Extractor V3 — Logs Page & Scan Bug Fix Plan

## Top-Level Overview

This plan delivers two things in parallel:

1. **Scan bug fix** (carried over from the previous plan): the `scan:done` socket
   event payload is ignored in the store, so scan summary data and any error are
   silently discarded. This must be fixed so the new Logs page can also surface
   scan errors via toast.

2. **Logs page**: a new `/logs` route showing structured extraction log entries
   fetched from the backend SQLite `extraction_logs` table. The page includes a
   period filter, a severity/level filter derived from log content keywords, a
   Refresh control, and a persistent (sticky) error toast when the fetch fails.

**Data source decision**: The existing `GET /api/insights/logs` endpoint returns
a plain-text blob — unsuitable for structured display. A new endpoint
`GET /api/insights/log-entries?period=...` will return the raw rows as JSON so
the frontend can render timestamp, ref number, and content individually.

**Severity inference**: The `extraction_logs.content` field contains free-form
text written by `extractor.py`. Severity is derived client-side by scanning
the content string for keywords: `error`/`fail`/`exception` → Error;
`warning`/`warn`/`skip` → Warning; everything else → Info.

**Files touched**:
- `PDF Extractor V3/backend/insights.py` — add structured log-entries endpoint
- `PDF Extractor V3/frontend/src/store/run.ts` — fix scan bug + add ScanSummary type + toast
- `PDF Extractor V3/frontend/src/pages/Logs.tsx` — new page (create)
- `PDF Extractor V3/frontend/src/pages/Scan.tsx` — add error panel UI
- `PDF Extractor V3/frontend/src/App.tsx` — register `/logs` route
- `PDF Extractor V3/frontend/src/components/Sidebar.tsx` — add Logs nav item
- `PDF Extractor V3/frontend/src/types/index.ts` — add `LogEntry` type

---

## Sub-Task 1 — Fix the scan:done store bug + add ScanSummary + toast

### Intent
The `scan:done` socket handler in `run.ts` takes no arguments, silently
discarding the payload. This prevents scan summary data and errors from ever
reaching any UI component. This sub-task fixes the handler, adds the missing
`scanSummary` state field, resets it on each new scan, and fires a sticky error
toast when the backend reports a fatal scan exception.

### Expected Outcomes
- `ScanSummary` interface is defined in `run.ts`.
- `RunStore` exposes `scanSummary: ScanSummary | null`.
- `startScan` resets `scanSummary: null` at the start of each run.
- `scan:done` handler correctly receives and stores the payload.
- When payload contains `error`, a persistent toast fires:
  `show('Scan error: <message>', 'error', 0)`.
- `useToastStore` is imported into `run.ts`.
- Existing Sync error path also fires a persistent toast (same pattern).

### Todo List
1. In `run.ts`, add at the top of imports:
   ```ts
   import { useToastStore } from './toast'
   ```
2. Add `ScanSummary` interface above `RunStore`:
   ```ts
   interface ScanSummary {
     found: number; total: number; pending: number; completed: number;
     error?: string; cancelled?: boolean
   }
   ```
3. Add `scanSummary: ScanSummary | null` to the `RunStore` interface (after `scanFound`).
4. Initialise `scanSummary: null` in the store's initial state object.
5. In `startScan`, add `scanSummary: null` to the reset `set(...)` call.
6. Replace the broken `scan:done` handler (line 158–160):
   ```ts
   _socket.on('scan:done', (d: ScanSummary) => {
     set({ scanRunning: false, scanSummary: d })
     if (d?.error) useToastStore.getState().show(`Scan error: ${d.error}`, 'error', 0)
   })
   ```
7. In the existing `sync:done` handler (line 150), add a toast for the `d.error`
   branch alongside the existing log append:
   ```ts
   useToastStore.getState().show(`Sync error: ${d.error}`, 'error', 0)
   ```

### Relevant Context
- [`run.ts:scan:done handler`](PDF%20Extractor%20V3/frontend/src/store/run.ts:158) ← the bug
- [`run.ts:sync:done handler`](PDF%20Extractor%20V3/frontend/src/store/run.ts:147)
- [`run.ts:startScan`](PDF%20Extractor%20V3/frontend/src/store/run.ts:101)
- [`toast.ts:show signature`](PDF%20Extractor%20V3/frontend/src/store/toast.ts:21) — `durationMs=0` skips auto-dismiss
- [`scanner.py:_scan_thread`](PDF%20Extractor%20V3/backend/scanner.py:83) — emits `{"error": str(exc)}` on failure

### Status
[ ] pending

---

## Sub-Task 2 — Add error panel to Scan page

### Intent
Now that `scanSummary` exists in the store, the Scan page needs to read it and
display an error panel when the last scan ended with an error — matching the
existing design pattern already used on the Sync page.

### Expected Outcomes
- `Scan.tsx` reads `scanSummary` from `useRunStore`.
- When `scanSummary.error` is present and `!scanSummary.cancelled`, a red
  error panel is rendered below the stats row.
- No visual change when scan completes without error.

### Todo List
1. In `Scan.tsx`, add `scanSummary` to the store selectors:
   ```ts
   const scanSummary = useRunStore((s) => s.scanSummary)
   ```
2. After the `{data && <div className="flex gap-3 mb-5">...` stats block, add:
   ```tsx
   {scanSummary?.error && !scanSummary.cancelled && (
     <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-4">
       <p className="text-sm font-semibold text-red-700 mb-1">Scan error</p>
       <p className="text-xs text-red-600 font-mono break-words">⚠ {scanSummary.error}</p>
     </div>
   )}
   ```

### Relevant Context
- [`Scan.tsx:stats row`](PDF%20Extractor%20V3/frontend/src/pages/Scan.tsx:57)
- [`Sync.tsx:error panel`](PDF%20Extractor%20V3/frontend/src/pages/Sync.tsx:67) — design to replicate
- Depends on Sub-Task 1 having added `scanSummary` to the store.

### Status
[ ] pending

---

## Sub-Task 3 — Add structured log-entries backend endpoint

### Intent
The existing `GET /api/insights/logs` returns a plain-text blob — usable only
for human reading, not for structured UI rendering. A new endpoint
`GET /api/insights/log-entries?period=...` will return each row as a JSON
object `{id, ref_number, occurred_at, content}` so the frontend can display
individual fields and infer severity.

### Expected Outcomes
- `GET /api/insights/log-entries?period=week` returns:
  ```json
  { "entries": [ { "id": 1, "ref_number": "REF123", "occurred_at": "2024-01-15T09:32:00", "content": "..." }, ... ] }
  ```
- `occurred_at` is a UTC ISO 8601 string (already stored that way in the DB).
- Empty period returns `{ "entries": [] }`.
- Existing `/api/insights/logs` (plain-text) endpoint is unchanged.

### Todo List
1. In `insights.py`, add a new route below the existing `/logs` route:
   ```python
   @router.get("/log-entries")
   def insights_log_entries(period: str = "week"):
       today  = datetime.now().date()
       cutoff = {
           "day":   today,
           "week":  today - timedelta(days=today.weekday()),
           "month": today.replace(day=1),
           "year":  today.replace(month=1, day=1),
       }.get(period.lower(), today)
       entries = db.logs_since(cutoff)
       return {
           "entries": [
               {
                   "id":          i + 1,
                   "ref_number":  e.get("ref_number") or "",
                   "occurred_at": e["occurred_at"].isoformat(timespec="seconds"),
                   "content":     e.get("content") or "",
               }
               for i, e in enumerate(entries)
           ]
       }
   ```
   No new DB functions are needed — `db.logs_since()` already returns the right
   rows; only the serialisation differs.

### Relevant Context
- [`insights.py:insights_logs`](PDF%20Extractor%20V3/backend/insights.py:95) — existing plain-text endpoint to sit beside
- [`db.py:logs_since`](PDF%20Extractor%20V3/backend/db.py:248) — returns `[{ref_number, occurred_at (datetime), content}]`
- `occurred_at` is a Python `datetime` object when returned from `logs_since`; must be `.isoformat()` serialised.

### Status
[ ] pending

---

## Sub-Task 4 — Add `LogEntry` type to `types/index.ts`

### Intent
The new Logs page needs a TypeScript type for the structured log entries
returned by the new endpoint. Adding it to the shared types file keeps
conventions consistent with the rest of the project.

### Expected Outcomes
- `LogEntry` interface exported from `types/index.ts`.
- `LogsResponse` wrapper type also exported.
- No existing types changed.

### Todo List
1. Append to `types/index.ts`:
   ```ts
   export interface LogEntry {
     id:          number
     ref_number:  string
     occurred_at: string   // ISO 8601 string, e.g. "2024-01-15T09:32:00"
     content:     string
   }

   export interface LogsResponse {
     entries: LogEntry[]
   }
   ```

### Relevant Context
- [`types/index.ts`](PDF%20Extractor%20V3/frontend/src/types/index.ts)

### Status
[ ] pending

---

## Sub-Task 5 — Create `pages/Logs.tsx`

### Intent
The main deliverable: a new page component at `/logs` that displays structured
extraction log entries with a period filter, severity filter, Refresh button,
and a sticky error toast on fetch failure.

### Design decisions
- **Period filter**: matches the Insights page exactly — inline pill buttons
  for `day / week / month / year`, active one highlighted `bg-accent text-white`.
- **Severity filter**: inline pill buttons for `All / Info / Warning / Error`
  placed beside the period filter in the same header row.
- **Severity inference** (client-side, no backend change):
  - `error` / `fail` / `exception` (case-insensitive) in `content` → **Error** (red)
  - `warning` / `warn` / `skip` (case-insensitive) in `content` → **Warning** (amber)
  - all other entries → **Info** (accent/purple)
- **Log table**: card with table, columns — Timestamp | Ref | Level | Message.
  Message is the first non-empty line of `content` (truncated to ~120 chars);
  full content visible on hover via `title` attribute.
- **Empty state**: `EmptyState` component with 📋 icon.
- **Error toast**: when `useApi` returns `null` (fetch failed), call
  `show('Failed to load logs: <error>', 'error', 0)` — persistent, user-dismissible.
- **Refresh**: button in header re-calls `load(period)`. While loading, button
  shows `<Spinner size={12} />`.
- **No new dependencies** — uses only existing UI components, hooks, and stores.

### Expected Outcomes
- Page renders at `#/logs`.
- Loads entries on mount and when period changes.
- Period and severity filter buttons work correctly.
- Table shows timestamp, ref, level badge, first line of content.
- Error toast fires (sticky) if fetch fails; no toast on success.
- Empty state shown when no entries exist for the period.
- Visual style matches existing pages.

### Todo List
1. Create `PDF Extractor V3/frontend/src/pages/Logs.tsx` with:
   - Imports: `useState`, `useEffect` from react; `RefreshCw`, `ScrollText`
     from lucide-react; `Button`, `Badge`, `EmptyState`, `Spinner` from
     `../components/ui/`; `useApi` from `../hooks/useApi`; `useToastStore`
     from `../store/toast`; `LogEntry`, `LogsResponse` from `../types`.
   - `PERIODS = ['day', 'week', 'month', 'year']`
   - `LEVELS = ['All', 'Info', 'Warning', 'Error']`
   - `inferLevel(content: string): 'Info' | 'Warning' | 'Error'` helper.
   - Component state: `entries`, `period`, `levelFilter`, `{ get, loading, error }`.
   - `load(p)` calls `get<LogsResponse>('/api/insights/log-entries?period=' + p)`.
     On null result (error): `show('Failed to load logs: ' + (error ?? 'Unknown error'), 'error', 0)`.
   - `useEffect(() => { load(period) }, [period])`.
   - Filtered entries: `entries.filter(e => levelFilter === 'All' || inferLevel(e.content) === levelFilter)`.
   - Header: title + subtitle on left; period pills + level pills + Refresh button on right.
   - Severity badge colours:
     - `Error` → `bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400`
     - `Warning` → `bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400`
     - `Info` → `bg-accent/10 text-accent`
   - Table columns: Timestamp (formatted locale string), Ref (`—` if empty),
     Level (inline badge), Message (first non-empty line, max 120 chars, full
     content in `title`).

2. **Helper `inferLevel`**:
   ```ts
   function inferLevel(content: string): 'Info' | 'Warning' | 'Error' {
     const lower = content.toLowerCase()
     if (/error|fail|exception/.test(lower)) return 'Error'
     if (/warning|warn|skip/.test(lower))    return 'Warning'
     return 'Info'
   }
   ```

### Relevant Context
- [`Insights.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Insights.tsx) — period pill filter pattern to replicate
- [`Scan.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Scan.tsx) — table layout pattern
- [`Sync.tsx`](PDF%20Extractor%20V3/frontend/src/pages/Sync.tsx) — error display pattern
- [`toast.ts:show`](PDF%20Extractor%20V3/frontend/src/store/toast.ts:21) — `durationMs=0` = sticky
- [`useApi.ts`](PDF%20Extractor%20V3/frontend/src/hooks/useApi.ts) — `{ get, loading, error }`

### Status
[ ] pending

---

## Sub-Task 6 — Register route in App.tsx and nav item in Sidebar.tsx

### Intent
Wire the new Logs page into the router and make it reachable from the sidebar.

### Expected Outcomes
- Navigating to `#/logs` renders the Logs page.
- A "Activity Logs" nav item appears in the sidebar's Navigation section, after
  Insights, using the `ScrollText` icon from lucide-react.
- The item highlights correctly when active (existing `NavItem` logic handles this).
- Sidebar collapses correctly (tooltip shows "Activity Logs").

### Todo List
**App.tsx:**
1. Add import: `import Logs from './pages/Logs'`
2. Add route inside `<Routes>`: `<Route path="/logs" element={<Logs />} />`

**Sidebar.tsx:**
1. Add `ScrollText` to the lucide-react import line.
2. Add to the `NAV` array after the Insights entry:
   ```ts
   { to: '/logs', icon: ScrollText, label: 'Activity Logs' },
   ```

### Relevant Context
- [`App.tsx:Routes`](PDF%20Extractor%20V3/frontend/src/App.tsx:35)
- [`Sidebar.tsx:NAV array`](PDF%20Extractor%20V3/frontend/src/components/Sidebar.tsx:12)
- [`Sidebar.tsx:lucide imports`](PDF%20Extractor%20V3/frontend/src/components/Sidebar.tsx:3)

### Status
[ ] pending

---

## Implementation Order

Sub-tasks must be executed in this order because later tasks depend on earlier ones:

```
1 (store fix) → 2 (Scan error panel)
3 (backend endpoint) → 4 (TS type) → 5 (Logs page)
6 (routing + nav) — depends on 5
```

Sub-tasks 1–2 and 3–5 can be worked in parallel since they touch independent layers.

---

## Summary of All Files Changed

| File | Change |
|------|--------|
| `backend/insights.py` | Add `GET /api/insights/log-entries` endpoint |
| `frontend/src/store/run.ts` | Fix `scan:done` handler; add `ScanSummary` + `scanSummary` field; add toast imports and calls |
| `frontend/src/pages/Scan.tsx` | Read `scanSummary`; add error panel |
| `frontend/src/pages/Logs.tsx` | **New file** — full Logs page |
| `frontend/src/App.tsx` | Import `Logs`; add `/logs` route |
| `frontend/src/components/Sidebar.tsx` | Add `ScrollText` import; add Logs nav item |
| `frontend/src/types/index.ts` | Add `LogEntry` and `LogsResponse` interfaces |
