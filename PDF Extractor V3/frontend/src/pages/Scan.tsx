import { useState, useEffect, useRef } from 'react'
import { FolderSearch, X } from 'lucide-react'
import Button      from '../components/ui/Button'
import Badge       from '../components/ui/Badge'
import EmptyState  from '../components/ui/EmptyState'
import Spinner     from '../components/ui/Spinner'
import { useApi }  from '../hooks/useApi'
import { useRunStore } from '../store/run'
import type { ScanResult, TrackedFile } from '../types'

export default function Scan() {
  const { get }   = useApi()
  const [data, setData] = useState<ScanResult | null>(null)

  const scanning   = useRunStore((s) => s.scanRunning)
  const scanFound  = useRunStore((s) => s.scanFound)
  const startScan  = useRunStore((s) => s.startScan)
  const cancelScan = useRunStore((s) => s.cancelScan)
  const prevScanning = useRef(scanning)

  async function load() {
    const r = await get<ScanResult>('/api/scan/files')
    if (r) setData(r)
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
          <Button onClick={startScan} disabled={scanning}>
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
