import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import Button    from '../components/ui/Button'
import Spinner   from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import type { InsightsData, AuditStatsData } from '../types'

const PERIODS = ['day', 'week', 'month', 'year'] as const

export default function Insights() {
  const { get, loading } = useApi()
  const [data,   setData]   = useState<InsightsData | null>(null)
  const [audit,  setAudit]  = useState<AuditStatsData | null>(null)
  const [period, setPeriod] = useState<string>('month')

  async function load(p: string) {
    const [ins, aud] = await Promise.all([
      get<InsightsData>(`/api/insights?period=${p}`),
      get<AuditStatsData>(`/api/audit/stats?period=${p}`),
    ])
    if (ins) setData(ins)
    if (aud) setAudit(aud)
  }

  useEffect(() => { load(period) }, [period])


  return (
    <div className="p-7 max-w-5xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="page-title">Extraction Insights</h1>
          <p className="page-sub mt-0.5">Visualize extraction progress over time</p>
        </div>
        <div className="flex items-center gap-2">
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
          <Button size="sm" onClick={() => load(period)} disabled={loading}>
            {loading ? <Spinner size={12} /> : <RefreshCw size={12} />}
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: 'Total Files',    value: data.stats.total,     color: '#6C63FF' },
              { label: 'Completed',      value: data.stats.completed, color: '#22C55E' },
              { label: 'Pending',        value: data.stats.pending,   color: '#D97706' },
            ].map(s => (
              <div key={s.label} className="card p-5">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{s.label}</p>
                <p className="text-3xl font-bold" style={{ color: s.color }}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="card p-5">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.chart} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E4E7EF" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="completed" name="Completed" fill="#22C55E" radius={[4, 4, 0, 0]} />
                <Bar dataKey="pending"   name="Pending"   fill="#D97706" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* ── Audit / Compliance insights ─────────────────────────────────── */}
      {audit && (
        <>
          <div className="flex items-center gap-3 mt-8 mb-4">
            <span className="section-label">Compliance &amp; Onboarding</span>
            <div className="flex-1 h-px bg-border-light dark:bg-border-dark" />
          </div>

          <div className="grid grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Audited Records',          value: audit.stats.total,                     color: '#6C63FF' },
              { label: 'Compliant',                value: audit.stats.compliant,                 color: '#22C55E' },
              { label: 'Not Compliant',            value: audit.stats.non_compliant,             color: '#EF4444' },
              { label: 'Compliant · Onboarded',    value: audit.stats.compliant_with_onboarding, color: '#0D9488' },
            ].map(s => (
              <div key={s.label} className="card p-5">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{s.label}</p>
                <p className="text-3xl font-bold" style={{ color: s.color }}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Onboarding-over-time chart */}
          <div className="card p-5">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Onboarding by {period}
            </p>
            {audit.onboarding_chart.length === 0 ? (
              <p className="text-xs text-gray-400 py-10 text-center">
                No onboarding dates recorded yet.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={audit.onboarding_chart} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E7EF" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" name="Onboarded" fill="#6C63FF" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </>
      )}
    </div>
  )
}

