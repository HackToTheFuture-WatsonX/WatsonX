import { useState, useEffect, useRef } from 'react'
import { CheckCircle2, FolderSearch, Loader2, Upload, X, XCircle } from 'lucide-react'
import Button      from '../components/ui/Button'
import Badge       from '../components/ui/Badge'
import EmptyState  from '../components/ui/EmptyState'
import Spinner     from '../components/ui/Spinner'
import { useApi, apiBase }  from '../hooks/useApi'
import { useSocketEvent } from '../hooks/useSocket'
import { useRunStore } from '../store/run'
import { useToastStore } from '../store/toast'
import type { ScanResult, TrackedFile, UploadResult } from '../types'

// Per-page diagnostics. Every user action on the Upload flow updates this so a
// packaged-app user can see WHAT the app just did without DevTools — the exact
// button click time, whether the picker returned files, the fetch URL/status/
// body. This is what turns "nothing happens" into a legible bug.
type Diag = {
  lastClick?: string
  lastPick?:  { count: number; names: string[]; when: string } | 'cancelled'
  lastFetch?: { url: string; status: number | 'network-error'; body: string; when: string }
}

// Per-file upload progress event streamed from the backend.
type UploadProgress = {
  name:   string
  state:  'saving' | 'uploaded' | 'skipped' | 'error'
  reason: string
  index:  number
  total:  number
}

export default function Scan() {
  const { get, upload } = useApi()
  const [data, setData] = useState<ScanResult | null>(null)
  const [uploading, setUploading] = useState(false)
  // Live per-file progress lines received via Socket.IO during an upload.
  // Cleared at the start of each new upload; kept afterwards so the user can
  // review what happened.
  const [uploadLog, setUploadLog] = useState<UploadProgress[]>([])
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [diag, setDiag] = useState<Diag>({})
  const [backendLogPath, setBackendLogPath] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const showToast = useToastStore((s) => s.show)

  // Ask the Electron main process where the backend log file lives so the
  // Diagnostics panel can display it (and copy to clipboard). Only available
  // in the packaged / desktop shell — in a plain browser dev context, the
  // helper doesn't exist and we render a hint instead.
  useEffect(() => {
    const api = (window as any).electronAPI
    if (api?.getBackendLogPath) {
      api.getBackendLogPath().then((p: string) => setBackendLogPath(p || ''))
        .catch(() => setBackendLogPath(''))
    }
  }, [])

  // Stream per-file upload events. Each file gets ONE row in the log that is
  // updated in place across state transitions (saving → uploaded/skipped/error)
  // instead of accumulating a new line per state — otherwise a single file
  // shows up 2-3 times which is noisy and confusing. Match first by 1-based
  // index (backend emits enumerate(files, start=1)), then fall back to name
  // in case indices ever drift.
  useSocketEvent<UploadProgress>('upload:progress', (ev) => {
    setUploadLog((prev) => {
      const i = prev.findIndex(p =>
        (ev.index > 0 && p.index === ev.index) || p.name === ev.name
      )
      if (i === -1) return [...prev, ev]
      const next = prev.slice()
      next[i] = ev
      return next
    })
  })

  const scanning    = useRunStore((s) => s.scanRunning)
  const scanFound   = useRunStore((s) => s.scanFound)
  const scanSummary = useRunStore((s) => s.scanSummary)
  const startScan   = useRunStore((s) => s.startScan)
  const cancelScan  = useRunStore((s) => s.cancelScan)
  const prevScanning = useRef(scanning)

  async function load() {
    const r = await get<ScanResult>('/api/scan/files')
    if (r) setData(r)
  }

  // Trigger the hidden file input. Kept as a separate function so onClick reads
  // naturally next to the other action buttons. Records the click time in the
  // diagnostics panel so the user has proof the button worked — even if the
  // file picker fails to open, cancels, or onChange never fires.
  function pickFiles() {
    setDiag(prev => ({ ...prev, lastClick: new Date().toISOString() }))
    fileInputRef.current?.click()
  }

  async function onFilesChosen(e: React.ChangeEvent<HTMLInputElement>) {
    // e.target.files is a LIVE FileList — setting e.target.value = '' clears
    // it in place. Snapshot into a real Array BEFORE the reset, otherwise
    // every pick looks like "cancelled by user" (this was the actual bug).
    const rawFiles = e.target.files
    const picked: File[] = rawFiles ? Array.from(rawFiles) : []
    // Reset AFTER the snapshot so re-picking the same filename re-fires
    // onChange (browsers otherwise treat "same file" as no change).
    e.target.value = ''
    if (picked.length === 0) {
      setDiag(prev => ({ ...prev, lastPick: 'cancelled' }))
      return
    }

    const pickedNames = picked.map(f => f.name)
    setDiag(prev => ({
      ...prev,
      lastPick: { count: picked.length, names: pickedNames, when: new Date().toISOString() },
    }))

    setUploading(true)
    setUploadResult(null)
    // Seed one "saving" row per picked file so the panel shows the full list
    // immediately (before the backend answers). The Socket.IO stream then
    // updates each row in place as its state transitions.
    setUploadLog(pickedNames.map((name, i) => ({
      name,
      state:  'saving',
      reason: 'Sending to server…',
      index:  i + 1,
      total:  picked.length,
    })))
    const outcome = await upload<UploadResult>('/api/scan/upload', picked)
    setUploading(false)

    // Capture the full fetch outcome for the Diagnostics panel even on success —
    // useful for confirming "the request really did reach the backend on port X"
    // when the visible result looks weird.
    setDiag(prev => ({
      ...prev,
      lastFetch: {
        url:    outcome.url,
        status: outcome.status,
        body:   outcome.body,
        when:   new Date().toISOString(),
      },
    }))

    const r = outcome.data
    if (!r) {
      const msg = outcome.error || 'Upload failed — no response from server.'
      // Mark every still-"saving" seeded row as error so the user sees which
      // files failed. -1 as index avoids colliding with any real per-file event.
      setUploadLog(prev => prev.map(row =>
        row.state === 'saving'
          ? { ...row, state: 'error' as const, reason: msg }
          : row,
      ))
      showToast(msg, 'error', 0)  // duration 0 = sticky, so user can read it
      return
    }

    setUploadResult(r)
    await load()

    const u = r.uploaded.length
    const s = r.skipped.length
    const errCount = r.errors.length
    const parts = [`Uploaded ${u}`]
    if (s > 0) parts.push(`Skipped ${s} (already exists)`)
    if (errCount > 0) parts.push(`Errors ${errCount}`)
    const kind = errCount > 0 ? 'error' : (u === 0 && s > 0 ? 'warning' : 'success')
    showToast(parts.join(' · '), kind)
  }

  async function copyBackendLogPath() {
    if (!backendLogPath) return
    try {
      await navigator.clipboard.writeText(backendLogPath)
      showToast(`Copied: ${backendLogPath}`, 'success')
    } catch {
      showToast(backendLogPath, 'info', 0)
    }
  }

  useEffect(() => { load() }, [])

  // Reload the file table whenever a scan finishes (scanning: true → false).
  useEffect(() => {
    if (prevScanning.current && !scanning) load()
    prevScanning.current = scanning
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanning])

  return (
    <div className="p-7">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Scan Local Folder</h1>
          <p className="page-sub mt-0.5">Detect PDF files and register them for extraction</p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="hidden"
            onChange={onFilesChosen}
          />
          <Button variant="ghost" onClick={pickFiles} disabled={uploading || scanning}>
            {uploading ? <Spinner size={14} /> : <Upload size={14} />}
            {uploading ? 'Uploading…' : 'Upload Files'}
          </Button>
          <Button onClick={startScan} disabled={scanning || uploading}>
            {scanning ? <Spinner size={14} /> : <FolderSearch size={14} />}
            {scanning ? `Scanning… (${scanFound})` : 'Scan Now'}
          </Button>
          {scanning && (
            <Button variant="danger" onClick={cancelScan}>
              <X size={14} />
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Stats row */}
      {data && (
        <div className="flex gap-3 mb-5">
          <span className="badge-accent">{data.total} Total</span>
          <span className="badge-green">{data.completed} Completed</span>
          <span className="badge-amber">{data.pending} Pending</span>
        </div>
      )}

      {/* Scan error panel */}
      {scanSummary?.error && !scanSummary.cancelled && (
        <div className="mt-1 mb-5 rounded-xl border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800 p-4">
          <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-1">Scan error</p>
          <p className="text-xs text-red-600 dark:text-red-400 font-mono break-words">⚠ {scanSummary.error}</p>
        </div>
      )}

      {/* Upload progress + results panel. Shows the live per-file stream while
          uploading, and the final per-file outcomes afterwards. Dismissable so
          it doesn't stick around after the user has seen the result. */}
      {(uploading || uploadLog.length > 0 || uploadResult) && (
        <div className="mb-5 rounded-xl border border-border-light dark:border-border-dark
                        bg-card-light dark:bg-card-dark overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b
                          border-border-light dark:border-border-dark
                          bg-gray-50 dark:bg-white/5">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-100">
              {uploading ? <Spinner size={14} /> : <Upload size={14} />}
              {uploading
                ? `Uploading… ${uploadLog[uploadLog.length - 1]?.index ?? 0}/${uploadLog[uploadLog.length - 1]?.total ?? '?'}`
                : 'Upload results'}
            </div>
            {!uploading && (
              <button
                onClick={() => { setUploadLog([]); setUploadResult(null) }}
                className="p-1 rounded text-gray-400 hover:text-gray-700 dark:hover:text-gray-200
                           hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                title="Dismiss"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Live per-file event list */}
          <div className="max-h-56 overflow-y-auto px-4 py-2 font-mono text-xs">
            {uploadLog.length === 0 && uploading && (
              <p className="text-gray-500 dark:text-gray-400">Preparing upload…</p>
            )}
            {uploadLog.map((ev, i) => {
              const icon =
                ev.state === 'uploaded' ? <CheckCircle2 size={12} className="text-green shrink-0" /> :
                ev.state === 'skipped'  ? <Loader2      size={12} className="text-yellow-500 shrink-0" /> :
                ev.state === 'error'    ? <XCircle      size={12} className="text-red-500 shrink-0" /> :
                                          <Spinner      size={12} />
              const label =
                ev.state === 'uploaded' ? 'Uploaded' :
                ev.state === 'skipped'  ? 'Skipped'  :
                ev.state === 'error'    ? 'Error'    :
                                          'Saving…'
              const color =
                ev.state === 'uploaded' ? 'text-green' :
                ev.state === 'skipped'  ? 'text-yellow-600 dark:text-yellow-400' :
                ev.state === 'error'    ? 'text-red-500' :
                                          'text-gray-600 dark:text-gray-300'
              return (
                <div key={i} className="flex items-center gap-2 py-0.5">
                  {icon}
                  <span className="text-gray-400 shrink-0">[{ev.index}/{ev.total}]</span>
                  <span className={`shrink-0 font-semibold ${color}`}>{label}</span>
                  <span className="truncate text-gray-800 dark:text-gray-100">{ev.name}</span>
                  {ev.reason && <span className="text-gray-500 dark:text-gray-400 truncate">— {ev.reason}</span>}
                </div>
              )
            })}
          </div>

          {/* Final totals footer (only after completion) */}
          {uploadResult && !uploading && (
            <div className="border-t border-border-light dark:border-border-dark
                            bg-gray-50 dark:bg-white/5 px-4 py-2 flex flex-wrap gap-3 text-xs">
              <span className="badge-green">{uploadResult.uploaded.length} Uploaded</span>
              <span className="badge-amber">{uploadResult.skipped.length} Skipped</span>
              {uploadResult.errors.length > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5
                                 bg-red-500/10 text-red-500 border border-red-500/30">
                  {uploadResult.errors.length} Error{uploadResult.errors.length === 1 ? '' : 's'}
                </span>
              )}
              <span className="text-gray-500 dark:text-gray-400 ml-auto">
                Logged under ref <code>UPLOAD</code> on the Logs page.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Diagnostics — always visible so a packaged-app user can see exactly
          what the app just did without opening DevTools. Collapsed by default
          so it doesn't intrude, but the section headline surfaces the last
          click/pick/fetch state at a glance. */}
      <details className="mb-5 rounded-xl border border-border-light dark:border-border-dark
                          bg-card-light dark:bg-card-dark text-xs open:pb-3">
        <summary className="cursor-pointer select-none px-4 py-2.5 font-semibold
                            text-gray-700 dark:text-gray-200 flex items-center gap-2">
          <span>Diagnostics</span>
          <span className="text-[10px] font-normal text-gray-500 dark:text-gray-400">
            (click to expand — shows API base, scan state, last upload attempt)
          </span>
        </summary>
        <div className="px-4 space-y-1 font-mono text-[11px] text-gray-700 dark:text-gray-300">
          <div><span className="text-gray-500">API base:</span> {apiBase()}</div>
          <div>
            <span className="text-gray-500">Scan state:</span>{' '}
            {scanning ? (
              <span className="text-yellow-500">running (found: {scanFound})</span>
            ) : (
              <span className="text-green">idle</span>
            )}
            {' · '}
            <span className="text-gray-500">Upload state:</span>{' '}
            {uploading ? <span className="text-yellow-500">uploading</span> : <span className="text-green">idle</span>}
          </div>
          <div>
            <span className="text-gray-500">Backend log:</span>{' '}
            {backendLogPath ? (
              <>
                <code className="break-all">{backendLogPath}</code>{' '}
                <button
                  onClick={copyBackendLogPath}
                  className="ml-1 underline text-accent hover:text-accent-dark"
                >Copy path</button>
              </>
            ) : (
              <span className="text-gray-500">not available (browser dev mode)</span>
            )}
          </div>
          <hr className="border-border-light dark:border-border-dark my-2" />
          <div>
            <span className="text-gray-500">Last button click:</span>{' '}
            {diag.lastClick
              ? <code>{new Date(diag.lastClick).toLocaleString()}</code>
              : <span className="text-gray-500">(none yet — click "Upload Files")</span>}
          </div>
          <div>
            <span className="text-gray-500">Last file pick:</span>{' '}
            {diag.lastPick === 'cancelled'
              ? <span className="text-yellow-500">cancelled by user</span>
              : diag.lastPick
                ? <code>{diag.lastPick.count} file(s): {diag.lastPick.names.join(', ')} @ {new Date(diag.lastPick.when).toLocaleTimeString()}</code>
                : <span className="text-gray-500">(none yet)</span>}
          </div>
          <div>
            <span className="text-gray-500">Last fetch:</span>{' '}
            {diag.lastFetch ? (
              <>
                <div><code className="break-all">POST {diag.lastFetch.url}</code></div>
                <div>
                  <span className="text-gray-500">Status:</span>{' '}
                  <span className={
                    diag.lastFetch.status === 200 ? 'text-green' :
                    diag.lastFetch.status === 'network-error' ? 'text-red-500' :
                    'text-yellow-500'
                  }>{String(diag.lastFetch.status)}</span>{' '}
                  @ {new Date(diag.lastFetch.when).toLocaleTimeString()}
                </div>
                <div className="whitespace-pre-wrap break-all">
                  <span className="text-gray-500">Body:</span>{' '}
                  <span className="text-gray-800 dark:text-gray-100">{diag.lastFetch.body || '(empty)'}</span>
                </div>
              </>
            ) : (
              <span className="text-gray-500">(none yet)</span>
            )}
          </div>
        </div>
      </details>

      {/* Table */}
      {!data || data.files.length === 0 ? (
        <EmptyState icon="📂" title="No PDF files found"
                    description="Click 'Scan Now' to scan the Local Folder for PDFs." />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#0D1117] text-white text-xs uppercase">
                {['File Name', 'Ref Number', 'Status', 'Last Extracted'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.files.map((f: TrackedFile) => (
                <tr key={f.key} className="border-t border-border-light dark:border-border-dark
                                           hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{f.name}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{f.ref_number ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge
                      label={f.status}
                      variant={f.status === 'Completed' ? 'green' : 'amber'}
                    />
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {f.last_extracted ? new Date(f.last_extracted).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
