import { useRef, useEffect } from 'react'
import { RefreshCw, X } from 'lucide-react'
import Button   from '../components/ui/Button'
import Spinner  from '../components/ui/Spinner'
import { useRunStore } from '../store/run'

export default function Sync() {
  const running    = useRunStore((s) => s.syncRunning)
  const logs       = useRunStore((s) => s.syncLogs)
  const summary    = useRunStore((s) => s.syncSummary)
  const startSync  = useRunStore((s) => s.startSync)
  const cancelSync = useRunStore((s) => s.cancelSync)
  const logRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest log line whenever logs change.
  useEffect(() => {
    logRef.current?.scrollTo({ top: 999999, behavior: 'smooth' })
  }, [logs])

  return (
    <div className="p-7 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Sync Folder</h1>
          <p className="page-sub mt-0.5">Sync IBM Box folder → Local Folder</p>
        </div>
        <div className="flex gap-2">
          <Button variant="teal" onClick={startSync} disabled={running}>
            {running ? <Spinner size={14} /> : <RefreshCw size={14} />}
            {running ? 'Syncing…' : 'Sync Now'}
          </Button>
          {running && (
            <Button variant="danger" onClick={cancelSync}>
              <X size={14} />
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Live log terminal */}
      <div
        ref={logRef}
        className="rounded-xl bg-[#0D1117] border border-[#2D3142] p-4 font-mono text-xs
                   text-[#7DD3A8] min-h-64 max-h-[460px] overflow-y-auto leading-relaxed"
      >
        {logs.length === 0 ? (
          <span className="text-[#3A4D6A]">Click "Sync Now" to start syncing from Box…</span>
        ) : (
          logs.map((l, i) => <div key={i}>{l}</div>)
        )}
      </div>

      {/* Summary */}
      {summary && (
        <div className="mt-4">
          <div className="flex gap-3">
            <span className="badge-green">✅ {summary.downloaded} downloaded</span>
            <span className="badge-accent">{summary.skipped} skipped</span>
            {summary.errors?.length > 0 && (
              <span className="badge bg-red-100 text-red-600">{summary.errors.length} error(s)</span>
            )}
          </div>

          {/* Show the actual error reason(s), not just a count. */}
          {summary.errors?.length > 0 && (
            <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-700 mb-2">
                {summary.errors.length === 1 ? 'Error details' : 'Error details'}
              </p>
              <ul className="space-y-1.5">
                {summary.errors.map((err, i) => (
                  <li
                    key={i}
                    className="text-xs text-red-600 font-mono leading-relaxed break-words"
                  >
                    ⚠ {err}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
