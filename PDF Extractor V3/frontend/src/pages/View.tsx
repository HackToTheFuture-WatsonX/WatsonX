import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, FileText, FileSpreadsheet, FileJson, Search, ChevronLeft, ChevronRight } from 'lucide-react'
import Button      from '../components/ui/Button'
import EmptyState  from '../components/ui/EmptyState'
import Spinner     from '../components/ui/Spinner'
import { useApi }  from '../hooks/useApi'
import type { ViewRow } from '../types'

const PAGE_SIZES = [15, 20, 30, 50]

export default function View() {
  const { get, post, loading } = useApi()
  const [rows,     setRows]     = useState<ViewRow[]>([])
  const [total,    setTotal]    = useState(0)
  const [search,   setSearch]   = useState('')
  const [page,     setPage]     = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0])

  async function load() {
    const r = await get<{ rows: ViewRow[]; total: number }>('/api/view/table')
    if (r) { setRows(r.rows); setTotal(r.total) }
  }

  useEffect(() => { load() }, [])

  async function openFile(path: string) {
    if (!path) return
    await post('/api/view/open', { path })
  }

  // Search across filename + reference number.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(r =>
      r.name.toLowerCase().includes(q) ||
      (r.ref ?? '').toLowerCase().includes(q)
    )
  }, [rows, search])

  // Reset to first page whenever the query, page size or dataset changes.
  useEffect(() => { setPage(1) }, [search, pageSize, total])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage  = Math.min(page, pageCount)
  const start     = (safePage - 1) * pageSize
  const pageRows  = filtered.slice(start, start + pageSize)

  return (
    <div className="p-7 max-w-5xl">
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
        <>
          {/* Toolbar: search */}
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search by filename or reference…"
                className="w-full bg-[#F0F2F8] dark:bg-white/5 border border-border-light dark:border-border-dark
                           rounded-xl pl-9 pr-3 py-2 text-sm outline-none
                           focus:border-accent dark:focus:border-accent transition-colors
                           text-gray-900 dark:text-white placeholder-gray-400"
              />
            </div>
            <span className="text-xs text-gray-400 shrink-0">
              {filtered.length} file{filtered.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Table */}
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#EEF4FF] dark:bg-accent/10 border-b border-border-light dark:border-border-dark
                               text-left text-xs font-semibold text-gray-600 dark:text-gray-300">
                  <th className="px-5 py-2.5">Filename</th>
                  <th className="px-5 py-2.5 w-48">Datetime Extracted</th>
                  <th className="px-5 py-2.5 w-40 text-center">Files</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-5 py-8 text-center text-sm text-gray-400">
                      No files match your search.
                    </td>
                  </tr>
                ) : (
                  pageRows.map((r, i) => (
                    <tr key={`${r.ref}/${r.name}/${i}`}
                        className="border-b border-border-light dark:border-border-dark last:border-0
                                   hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
                      <td className="px-5 py-2.5">
                        <span className="text-gray-900 dark:text-white font-medium truncate block max-w-md" title={r.name}>
                          {r.name}
                        </span>
                        {r.ref && (
                          <span className="text-[11px] text-accent">📁 {r.ref}</span>
                        )}
                      </td>
                      <td className="px-5 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                        {r.datetime || '—'}
                      </td>
                      <td className="px-5 py-2.5">
                        <div className="flex items-center justify-center gap-2">
                          <IconAction
                            title="View Word Document"
                            disabled={!r.word}
                            color="#6C63FF"
                            onClick={() => openFile(r.word)}
                            icon={FileText}
                          />
                          <IconAction
                            title="View Excel Spreadsheet"
                            disabled={!r.excel}
                            color="#0D9488"
                            onClick={() => openFile(r.excel)}
                            icon={FileSpreadsheet}
                          />
                          <IconAction
                            title="View JSON File"
                            disabled={!r.json}
                            color="#A78BFA"
                            onClick={() => openFile(r.json)}
                            icon={FileJson}
                          />
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination footer */}
          <div className="flex items-center justify-between mt-4 text-xs text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-2">
              <span>Rows per page</span>
              <select
                value={pageSize}
                onChange={e => setPageSize(Number(e.target.value))}
                className="bg-[#F0F2F8] dark:bg-white/5 border border-border-light dark:border-border-dark
                           rounded-lg px-2 py-1 text-xs outline-none focus:border-accent
                           text-gray-900 dark:text-white"
              >
                {PAGE_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <span>
                {filtered.length === 0
                  ? '0 of 0'
                  : `${start + 1}–${Math.min(start + pageSize, filtered.length)} of ${filtered.length}`}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="p-1.5 rounded-lg border border-border-light dark:border-border-dark
                             disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                  title="Previous page"
                >
                  <ChevronLeft size={14} />
                </button>
                <span className="px-2">{safePage} / {pageCount}</span>
                <button
                  onClick={() => setPage(p => Math.min(pageCount, p + 1))}
                  disabled={safePage >= pageCount}
                  className="p-1.5 rounded-lg border border-border-light dark:border-border-dark
                             disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                  title="Next page"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function IconAction({
  title, disabled, color, onClick, icon: Icon,
}: {
  title:    string
  disabled: boolean
  color:    string
  onClick:  () => void
  icon:     typeof FileText
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={disabled ? 'Not available' : title}
      className="w-8 h-8 rounded-md flex items-center justify-center transition-all
                 disabled:opacity-25 disabled:cursor-not-allowed enabled:hover:scale-110"
      style={{
        background: `${color}1A`,
        border:     `1px solid ${color}44`,
      }}
    >
      <Icon size={15} style={{ color }} />
    </button>
  )
}
