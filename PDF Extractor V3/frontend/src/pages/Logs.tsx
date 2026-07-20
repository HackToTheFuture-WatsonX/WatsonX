import { Fragment, useState, useEffect, useMemo } from 'react'

import { RefreshCw, ScrollText, ChevronRight, ChevronDown, ChevronLeft } from 'lucide-react'

import Button     from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import Spinner    from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import { useToastStore } from '../store/toast'
import type { LogEntry, LogsResponse } from '../types'

const PERIODS    = ['day', 'week', 'month', 'year'] as const
const LEVELS     = ['All', 'Info', 'Warning', 'Error'] as const
const PAGE_SIZES = [15, 20, 30, 50] as const


type Level = 'Info' | 'Warning' | 'Error'
type LevelFilter = 'All' | Level

function inferLevel(content: string): Level {
  const lower = content.toLowerCase()
  if (/error|fail|exception/.test(lower)) return 'Error'
  if (/warning|warn|skip/.test(lower))    return 'Warning'
  return 'Info'
}

const LEVEL_BADGE: Record<Level, string> = {
  Error:   'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  Warning: 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
  Info:    'bg-accent/10 text-accent',
}

function firstLine(content: string, max = 120): string {
  const line = (content.split('\n').find(l => l.trim()) ?? '').trim()
  return line.length > max ? line.slice(0, max) + '…' : line
}

export default function Logs() {
  const { get, loading, error } = useApi()
  const show = useToastStore((s) => s.show)

  const [entries,     setEntries]     = useState<LogEntry[]>([])
  const [period,      setPeriod]      = useState<string>('week')
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('All')

  // Pagination + per-row expand state
  const [page,     setPage]     = useState(1)
  const [pageSize, setPageSize] = useState<number>(PAGE_SIZES[0])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  async function load(p: string) {
    const r = await get<LogsResponse>(`/api/insights/log-entries?period=${p}`)
    if (r) {
      setEntries(r.entries)
    } else {
      show(`Failed to load logs: ${error ?? 'Unknown error'}`, 'error', 0)
    }
  }

  useEffect(() => { load(period) }, [period])

  const visible = useMemo(
    () =>
      levelFilter === 'All'
        ? entries
        : entries.filter(e => inferLevel(e.content) === levelFilter),
    [entries, levelFilter],
  )

  // Reset to first page whenever the result set changes
  useEffect(() => { setPage(1) }, [visible, pageSize])

  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize))
  const clampedPage = Math.min(page, totalPages)
  const startIdx = (clampedPage - 1) * pageSize
  const paged = visible.slice(startIdx, startIdx + pageSize)

  function toggleRow(id: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }


  return (
    <div className="p-7 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <ScrollText size={20} className="text-accent" />
            Activity Logs
          </h1>
          <p className="page-sub mt-0.5">Extraction log history from the database</p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Period filter */}
          <div className="flex items-center gap-1">
            {PERIODS.map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors
                  ${period === p
                    ? 'bg-accent text-white'
                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10'}`}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Level filter */}
          <div className="flex items-center gap-1 border-l border-border-light dark:border-border-dark pl-2">
            {LEVELS.map(l => (
              <button
                key={l}
                onClick={() => setLevelFilter(l)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors
                  ${levelFilter === l
                    ? 'bg-accent text-white'
                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10'}`}
              >
                {l}
              </button>
            ))}
          </div>

          {/* Refresh */}
          <Button size="sm" onClick={() => load(period)} disabled={loading}>
            {loading ? <Spinner size={12} /> : <RefreshCw size={12} />}
          </Button>
        </div>
      </div>

      {/* Entry count badge */}
      {!loading && entries.length > 0 && (
        <div className="flex gap-3 mb-5">
          <span className="badge-accent">{entries.length} total</span>
          {visible.length !== entries.length && (
            <span className="badge-accent">{visible.length} shown</span>
          )}
        </div>
      )}

      {/* Log table */}
      {loading ? (
        <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400 py-12 justify-center">
          <Spinner size={16} />
          Loading logs…
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon="📋"
          title="No log entries found"
          description={
            levelFilter !== 'All'
              ? `No ${levelFilter} entries for this period. Try a different filter.`
              : 'Log entries appear after running extraction tasks.'
          }
        />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#0D1117] text-white text-xs uppercase">
                <th className="w-10 px-4 py-3" />
                {['Timestamp', 'Ref Number', 'Level', 'Message'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.map(entry => {
                const level = inferLevel(entry.content)
                const ts    = (() => {
                  try { return new Date(entry.occurred_at).toLocaleString() }
                  catch { return entry.occurred_at }
                })()
                const isOpen = expanded.has(entry.id)
                return (
                  <Fragment key={entry.id}>
                    <tr
                      className="border-t border-border-light dark:border-border-dark
                                 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                    >

                      <td className="px-4 py-3 align-top">
                        <button
                          type="button"
                          onClick={() => toggleRow(entry.id)}
                          aria-expanded={isOpen}
                          title={isOpen ? 'Hide details' : 'Show details'}
                          className="p-1 rounded text-gray-400 hover:text-accent hover:bg-gray-100
                                     dark:hover:bg-white/10 transition-colors"
                        >
                          {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap font-mono text-xs align-top">
                        {ts}
                      </td>
                      <td className="px-4 py-3 text-gray-700 dark:text-gray-300 font-medium align-top">
                        {entry.ref_number || '—'}
                      </td>
                      <td className="px-4 py-3 align-top">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${LEVEL_BADGE[level]}`}>
                          {level}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-300 max-w-xs truncate align-top">
                        {firstLine(entry.content)}
                      </td>
                    </tr>
                    {isOpen && (
                      <tr
                        className="border-t border-border-light dark:border-border-dark bg-gray-50 dark:bg-white/5"
                      >
                        <td />
                        <td colSpan={4} className="px-4 py-3">
                          <pre className="whitespace-pre-wrap break-words font-mono text-xs
                                          text-gray-700 dark:text-gray-300">
                            {entry.content}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>

          {/* Pagination footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3
                          border-t border-border-light dark:border-border-dark text-xs
                          text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-2">
              <span>Rows per page</span>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="rounded-lg border border-border-light dark:border-border-dark
                           bg-transparent px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
              >
                {PAGE_SIZES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <span>
                {visible.length === 0
                  ? '0 of 0'
                  : `${startIdx + 1}–${Math.min(startIdx + pageSize, visible.length)} of ${visible.length}`}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={clampedPage <= 1}
                  title="Previous page"
                  className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="px-1">{clampedPage} / {totalPages}</span>
                <button
                  type="button"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={clampedPage >= totalPages}
                  title="Next page"
                  className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10
                             disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

