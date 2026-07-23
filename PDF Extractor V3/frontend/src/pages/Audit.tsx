import { useState, useEffect, useMemo } from 'react'
import { RefreshCw, Download, DatabaseZap, Search, Check, X, Pencil } from 'lucide-react'
import Button    from '../components/ui/Button'
import Spinner   from '../components/ui/Spinner'
import { useApi, apiBase } from '../hooks/useApi'
import { useToastStore } from '../store/toast'
import type { AuditListResponse, AuditRow, AuditOverrideRequest } from '../types'

// Columns the user can override inline (keyed by their AuditResource label).
const EDITABLE = new Set([
  'Candidate Name', 'Onboarding Date', 'Background Check Date', 'isCompliant',
])

// Map an AuditResource label → the override request field name.
const LABEL_TO_FIELD: Record<string, keyof AuditOverrideRequest> = {
  'Candidate Name':        'candidate_name',
  'Onboarding Date':       'onboarding_date',
  'Background Check Date': 'background_check_date',
  'isCompliant':           'is_compliant',
}

// Columns rendered/edited as a calendar date (no time).
const DATE_COLUMNS = new Set(['Onboarding Date', 'Background Check Date'])

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

// Parse a stored date string into a canonical YYYY-MM-DD (what <input type="date">
// expects). Accepts YYYY-MM-DD, DD/MM/YYYY, DD-Mmm-YYYY, DD Mmm YYYY. Returns ''
// if the value can't be recognised as a date.
function toIsoDate(raw: string): string {
  const v = (raw || '').trim()
  if (!v) return ''
  // Already ISO (optionally with time) — keep the date part.
  const iso = v.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`
  // DD/MM/YYYY or DD-MM-YYYY
  const dmy = v.match(/^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$/)
  if (dmy) {
    const [, d, m, y] = dmy
    return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`
  }
  // DD-Mmm-YYYY or DD Mmm YYYY
  const dMonY = v.match(/^(\d{1,2})[ \-]([A-Za-z]{3,})[ \-](\d{4})$/)
  if (dMonY) {
    const [, d, mon, y] = dMonY
    const mi = MONTHS.findIndex((mm) => mm.toLowerCase() === mon.slice(0, 3).toLowerCase())
    if (mi >= 0) return `${y}-${String(mi + 1).padStart(2, '0')}-${d.padStart(2, '0')}`
  }
  return ''
}

// Format any recognised date string as DD-Mmm-YYYY for display (e.g. 21-Jul-2026).
// Falls back to the original string if it isn't a parseable date.
function formatDisplayDate(raw: string): string {
  const iso = toIsoDate(raw)
  if (!iso) return (raw || '').trim()
  const [y, m, d] = iso.split('-')
  const mon = MONTHS[Number(m) - 1] || m
  return `${d}-${mon}-${y}`
}

// Value fed to <input type="datetime-local"> — a calendar+time picker whose
// time is always pinned to midnight (YYYY-MM-DDT00:00:00). Empty if unparseable.
function toDatetimeLocalValue(raw: string): string {
  const iso = toIsoDate(raw)
  return iso ? `${iso}T00:00:00` : ''
}

// Canonical stored form for a date column: YYYY-MM-DD 00:00:00. Date comes first
// so lexical string comparison stays equivalent to chronological comparison.
// Empty string if the value can't be parsed (lets the user clear the field).
function toStoredDatetime(raw: string): string {
  const iso = toIsoDate(raw)
  return iso ? `${iso} 00:00:00` : ''
}



export default function Audit() {
  const { get, post, loading } = useApi()
  const showToast = useToastStore((s) => s.show)

  const [columns, setColumns] = useState<string[]>([])
  const [rows,    setRows]    = useState<AuditRow[]>([])
  const [query,   setQuery]   = useState('')
  const [busy,    setBusy]    = useState(false)

  // Inline edit state: which row (by S/N ref) + field is being edited.
  const [editKey,  setEditKey]  = useState<string | null>(null)
  const [editVal,  setEditVal]  = useState('')

  async function load() {
    const r = await get<AuditListResponse>('/api/audit')
    if (r) {
      setColumns(r.columns)
      setRows(r.rows)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((r) =>
      Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(q)),
    )
  }, [rows, query])

  function startEdit(rowIdx: number, col: string, current: string) {
    setEditKey(`${rowIdx}::${col}`)
    // Date columns feed an <input type="datetime-local"> (a calendar picker whose
    // time is pinned to midnight), which requires a YYYY-MM-DDTHH:MM value.
    setEditVal(DATE_COLUMNS.has(col) ? toDatetimeLocalValue(current) : current)
  }



  function cancelEdit() {
    setEditKey(null)
    setEditVal('')
  }

  async function saveEdit(row: AuditRow, col: string) {
    const ref = (row['S/N'] as string) || ''
    if (!ref) {
      showToast('Cannot save: this row has no reference number.', 'warning')
      cancelEdit()
      return
    }
    const field = LABEL_TO_FIELD[col]
    const body: AuditOverrideRequest = { ref_number: ref }
    // Date columns persist as canonical YYYY-MM-DD 00:00:00; other columns save as-is.
    ;(body as any)[field] = DATE_COLUMNS.has(col) ? toStoredDatetime(editVal) : editVal
    setBusy(true)
    const r = await post<{ status: string }>('/api/audit/override', body)
    setBusy(false)
    if (r?.status === 'ok') {
      showToast('Override saved.', 'success')
      cancelEdit()
      await load()
    } else {
      showToast('Failed to save override.', 'error')
    }
  }

  async function runBackfill() {
    setBusy(true)
    const r = await post<{ scanned: number; stored: number; skipped: number; errors: number }>(
      '/api/audit/backfill',
    )
    setBusy(false)
    if (r) {
      showToast(`Backfill complete — ${r.stored} stored, ${r.skipped} skipped, ${r.errors} errors.`, 'success')
      await load()
    } else {
      showToast('Backfill failed.', 'error')
    }
  }

  function exportExcel() {
    // Server-side .xlsx build — open the endpoint so the browser downloads it.
    window.open(`${apiBase()}/api/audit/export`, '_blank')
  }

  return (
    <div className="p-7">
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="page-title">Audit Resource</h1>
          <p className="page-sub mt-0.5">
            Master list of extracted background-check reports — export to Excel or edit audit fields inline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={runBackfill} disabled={busy || loading}>
            {busy ? <Spinner size={12} /> : <DatabaseZap size={12} />} Backfill
          </Button>
          <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
            {loading ? <Spinner size={12} /> : <RefreshCw size={12} />} Refresh
          </Button>
          <Button size="sm" variant="green" onClick={exportExcel} disabled={rows.length === 0}>
            <Download size={12} /> Export Excel
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search candidates, results…"
          className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-border-light dark:border-border-dark
                     bg-white dark:bg-white/5 text-gray-900 dark:text-white
                     focus:outline-none focus:border-accent"
        />
      </div>

      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        {filtered.length} of {rows.length} record{rows.length === 1 ? '' : 's'}
      </p>

      {/* Table */}
      <div className="card overflow-auto max-h-[calc(100vh-260px)]">
        <table className="min-w-full text-xs whitespace-nowrap">
          <thead className="sticky top-0 z-10 bg-gray-50 dark:bg-[#0F1A30]">
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  className="px-3 py-2.5 text-left font-semibold text-gray-600 dark:text-gray-300
                             border-b border-border-light dark:border-border-dark"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, rIdx) => (
              <tr
                key={rIdx}
                className="border-b border-border-light/60 dark:border-border-dark/60
                           hover:bg-gray-50 dark:hover:bg-white/5"
              >
                {columns.map((col) => {
                  const val = String(row[col] ?? '')
                  const isEditing = editKey === `${rIdx}::${col}`
                  const editable  = EDITABLE.has(col)
                  const isCompliantCol = col === 'isCompliant'
                  const isDateCol = DATE_COLUMNS.has(col)

                  if (isEditing) {
                    return (
                      <td key={col} className="px-2 py-1">
                        <div className="flex items-center gap-1">
                          <input
                            autoFocus
                            type={isDateCol ? 'datetime-local' : 'text'}
                            step={isDateCol ? 1 : undefined}
                            value={editVal}

                            onChange={(e) => setEditVal(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') saveEdit(row, col)
                              if (e.key === 'Escape') cancelEdit()
                            }}
                            className="w-32 px-2 py-1 text-xs rounded border border-accent
                                       bg-white dark:bg-[#0B1220] text-gray-900 dark:text-white
                                       focus:outline-none"
                          />

                          <button onClick={() => saveEdit(row, col)} className="text-green-600 hover:text-green-700" title="Save">
                            <Check size={13} />
                          </button>
                          <button onClick={cancelEdit} className="text-gray-400 hover:text-red-500" title="Cancel">
                            <X size={13} />
                          </button>
                        </div>
                      </td>
                    )
                  }

                  return (
                    <td
                      key={col}
                      className={`px-3 py-2 text-gray-700 dark:text-gray-300 group ${editable ? 'cursor-pointer' : ''}`}
                      onClick={() => editable && startEdit(rIdx, col, val)}
                    >
                      <span className="inline-flex items-center gap-1.5">
                        {isCompliantCol ? (
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              val.toLowerCase() === 'true'
                                ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300'
                                : 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300'
                            }`}
                          >
                            {val.toLowerCase() === 'true' ? 'Compliant' : 'Not Compliant'}
                          </span>
                        ) : (
                          <span>{(isDateCol ? formatDisplayDate(val) : val) || <span className="text-gray-300 dark:text-gray-600">—</span>}</span>
                        )}
                        {editable && (
                          <Pencil size={11} className="opacity-0 group-hover:opacity-60 text-accent shrink-0" />
                        )}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={columns.length || 1} className="px-3 py-10 text-center text-gray-400">
                  {loading ? 'Loading…' : 'No audit records. Extract reports or run Backfill.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
