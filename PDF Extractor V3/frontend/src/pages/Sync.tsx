import { useState, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import Button   from '../components/ui/Button'
import Spinner  from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import { useSocketEvent } from '../hooks/useSocket'

export default function Sync() {
  const { post, loading } = useApi()
  const [running, setRunning]   = useState(false)
  const [logs,    setLogs]      = useState<string[]>([])
  const [summary, setSummary]   = useState<{ downloaded: number; skipped: number; errors: string[] } | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useSocketEvent<{ message: string }>('sync:log', (data) => {
    setLogs(prev => [...prev, data.message])
    setTimeout(() => logRef.current?.scrollTo({ top: 999999, behavior: 'smooth' }), 30)
  })

  useSocketEvent<any>('sync:done', (data) => {
    setRunning(false)
    if (!data.error) setSummary(data)
    else setLogs(prev => [...prev, `⚠ ${data.error}`])
  })

  async function handleSync() {
    setRunning(true); setSummary(null); setLogs([])
    await post('/api/sync/run')
  }

  return (
    <div className="p-7 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Sync Folder</h1>
          <p className="page-sub mt-0.5">Sync IBM Box folder → Local Folder</p>
        </div>
        <Button variant="teal" onClick={handleSync} disabled={running || loading}>
          {running ? <Spinner size={14} /> : <RefreshCw size={14} />}
          {running ? 'Syncing…' : 'Sync Now'}
        </Button>
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
        <div className="mt-4 flex gap-3">
          <span className="badge-green">✅ {summary.downloaded} downloaded</span>
          <span className="badge-accent">{summary.skipped} skipped</span>
          {summary.errors?.length > 0 && (
            <span className="badge bg-red-100 text-red-600">{summary.errors.length} error(s)</span>
          )}
        </div>
      )}
    </div>
  )
}
