import { useState, useEffect, useRef } from 'react'
import { Cog, CheckCircle, XCircle, X } from 'lucide-react'
import Button      from '../components/ui/Button'
import Spinner     from '../components/ui/Spinner'
import EmptyState  from '../components/ui/EmptyState'
import { useApi }  from '../hooks/useApi'
import { useRunStore } from '../store/run'
import type { ScanResult } from '../types'

export default function Extract() {
  const { get } = useApi()
  const [fileData, setFileData] = useState<ScanResult | null>(null)

  const running       = useRunStore((s) => s.extractRunning)
  const progress      = useRunStore((s) => s.extractProgress)
  const results       = useRunStore((s) => s.extractResults)
  const summary       = useRunStore((s) => s.extractSummary)
  const startExtract  = useRunStore((s) => s.startExtract)
  const cancelExtract = useRunStore((s) => s.cancelExtract)
  const prevRunning   = useRef(running)
  const listRef = useRef<HTMLDivElement>(null)

  async function loadFiles() {
    const r = await get<ScanResult>('/api/scan/files')
    if (r) setFileData(r)
  }

  useEffect(() => { loadFiles() }, [])

  // Reload pending/completed counts whenever an extraction finishes.
  useEffect(() => {
    if (prevRunning.current && !running) loadFiles()
    prevRunning.current = running
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running])

  // Auto-scroll to newest result card.
  useEffect(() => {
    listRef.current?.scrollTo({ top: 999999, behavior: 'smooth' })
  }, [results])

  return (
    <div className="p-7 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Extract Files</h1>
          <p className="page-sub mt-0.5">Run extraction pipeline — decrypt, parse, export Word / Excel / JSON</p>
        </div>
        <div className="flex gap-2">
          <Button variant="green" onClick={startExtract} disabled={running}>
            {running ? <Spinner size={14} /> : <Cog size={14} />}
            {running ? 'Extracting…' : 'Start Extraction'}
          </Button>
          {running && (
            <Button variant="danger" onClick={cancelExtract}>
              <X size={14} />
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Pending summary */}
      {fileData && (
        <div className="flex gap-3 mb-5">
          <span className="badge-amber">{fileData.pending} Pending</span>
          <span className="badge-green">{fileData.completed} Completed</span>
          <span className="badge-accent">{fileData.total} Total</span>
        </div>
      )}

      {/* Progress bar */}
      {running && (
        <div className="mb-5">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Extracting…</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-gray-200 dark:bg-white/10 overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="flex gap-3 mb-5">
          <span className="badge-green">✅ {summary.completed} completed</span>
          {summary.failed > 0 && <span className="badge bg-red-100 text-red-600">❌ {summary.failed} failed</span>}
        </div>
      )}

      {/* Result cards */}
      {results.length === 0 && !running ? (
        <EmptyState icon="⚙️" title="No results yet"
                    description="Scan the Local Folder first, then click 'Start Extraction'." />
      ) : (
        <div ref={listRef} className="flex flex-col gap-3 max-h-[460px] overflow-y-auto">
          {results.map((r, i) => (
            <div key={i}
              className={`card flex items-start gap-3 p-4 border-l-4
                ${r.status === 'ok' ? 'border-l-green' : 'border-l-red-400'}`}
            >
              {r.status === 'ok'
                ? <CheckCircle size={18} className="text-green shrink-0 mt-0.5" />
                : <XCircle    size={18} className="text-red-400 shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <p className="font-semibold text-sm text-gray-900 dark:text-white truncate">{r.fname}</p>
                {r.status === 'ok'
                  ? <p className="text-xs text-gray-500 mt-0.5">Ref: {r.ref} · {r.upload}</p>
                  : <p className="text-xs text-red-400 mt-0.5">{r.error}</p>
                }
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
