import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import Button    from '../components/ui/Button'
import Spinner   from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import type { InsightsData } from '../types'

const PERIODS = ['day', 'week', 'month', 'year'] as const

export default function Insights() {
  const { get, loading } = useApi()
  const [data,   setData]   = useState<InsightsData | null>(null)
  const [period, setPeriod] = useState<string>('month')

  async function load(p: string) {
    const r = await get<InsightsData>(`/api/insights?period=${p}`)
    if (r) setData(r)
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
    </div>
  )
}
