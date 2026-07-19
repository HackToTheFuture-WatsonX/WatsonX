import { useState, useEffect } from 'react'
import { RefreshCw, FileText, FileSpreadsheet, FileJson, ExternalLink } from 'lucide-react'
import Button      from '../components/ui/Button'
import EmptyState  from '../components/ui/EmptyState'
import Spinner     from '../components/ui/Spinner'
import { useApi }  from '../hooks/useApi'
import type { ViewSection, ViewFile } from '../types'

const TYPE_META: Record<string, { color: string; icon: typeof FileText }> = {
  'Word Documents':  { color: '#6C63FF', icon: FileText },
  'Excel Workbooks': { color: '#0D9488', icon: FileSpreadsheet },
  'JSON Files':      { color: '#A78BFA', icon: FileJson },
}

export default function View() {
  const { get, post, loading } = useApi()
  const [sections, setSections] = useState<ViewSection[]>([])
  const [total,    setTotal]    = useState(0)

  async function load() {
    const r = await get<{ sections: ViewSection[]; total: number }>('/api/view/files')
    if (r) { setSections(r.sections); setTotal(r.total) }
  }

  useEffect(() => { load() }, [])

  async function openFile(path: string) {
    await post('/api/view/open', { path })
  }

  return (
    <div className="p-7 max-w-4xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">View Extracted Files</h1>
          <p className="page-sub mt-0.5">Browse extracted Word, Excel and JSON output files</p>
        </div>
        <Button onClick={load} disabled={loading}>
          {loading ? <Spinner size={14} /> : <RefreshCw size={14} />}
          Refresh
        </Button>
      </div>

      {total === 0 && !loading ? (
        <EmptyState icon="📁" title="No extracted files found"
                    description="Run the extraction pipeline first to generate output files." />
      ) : (
        <div className="flex flex-col gap-6">
          {sections.map((sec) => {
            const meta = TYPE_META[sec.label] ?? { color: '#6C63FF', icon: FileText }
            const Icon = meta.icon
            return (
              <div key={sec.label}>
                {/* Section header */}
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
                    style={{ background: `${meta.color}22`, border: `1px solid ${meta.color}44` }}
                  >
                    <Icon size={14} style={{ color: meta.color }} />
                  </div>
                  <span className="font-semibold text-sm text-gray-900 dark:text-white">{sec.label}</span>
                  <span
                    className="text-xs font-bold px-2 py-0.5 rounded-full"
                    style={{ background: `${meta.color}22`, color: meta.color }}
                  >
                    {sec.count} file{sec.count !== 1 ? 's' : ''}
                  </span>
                  <div className="flex-1 h-px bg-border-light dark:bg-border-dark" />
                </div>

                {/* File groups */}
                {sec.count === 0 ? (
                  <p className="text-sm text-gray-400 pl-10">No files found.</p>
                ) : (
                  <div className="card overflow-hidden">
                    {sec.groups.map((grp) => (
                      <div key={grp.ref}>
                        {/* Ref group label */}
                        <div className="bg-[#EEF4FF] dark:bg-accent/10 border-b border-border-light
                                        dark:border-border-dark px-4 py-2 flex items-center gap-2">
                          <span className="text-xs text-accent font-semibold">📁 {grp.ref}</span>
                        </div>
                        {grp.files.map((f: ViewFile) => (
                          <div key={f.path}
                            className="flex items-center justify-between px-6 py-2.5
                                       border-b border-border-light dark:border-border-dark last:border-0
                                       hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                          >
                            <button
                              onClick={() => openFile(f.path)}
                              className="text-accent text-xs underline-offset-2 underline hover:text-accent-dark
                                         flex items-center gap-1.5 truncate max-w-xs"
                            >
                              <ExternalLink size={11} /> {f.name}
                            </button>
                            <span className="text-xs text-gray-400 shrink-0 ml-3">{f.mtime}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
