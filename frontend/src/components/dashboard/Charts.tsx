import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { generateChartData, generateRiskDistribution, generateFraudTypeData } from '@/lib/mockData'
import { useMemo } from 'react'

interface TooltipPayload { value: number; name: string; color: string }
interface CustomTooltipProps { active?: boolean; payload?: TooltipPayload[]; label?: string }

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      {label && <div className="text-gray-400 mb-1">{label}</div>}
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-gray-300 capitalize">{p.name}:</span>
          <span className="text-white font-medium">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export function TransactionVolumeChart() {
  const data = useMemo(() => generateChartData(24), [])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">Transaction Volume (24h)</h3>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="fraudGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} fill="url(#volGrad)" name="transactions" />
          <Area type="monotone" dataKey="fraud" stroke="#ef4444" strokeWidth={2} fill="url(#fraudGrad)" name="fraud" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function RiskDistributionChart() {
  const data = useMemo(() => generateRiskDistribution(), [])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">Risk Score Distribution</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="range" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} name="transactions">
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function FraudTypeChart() {
  const raw = useMemo(() => generateFraudTypeData(), [])
  const data = raw.map(d => ({ name: d.type, value: d.detected }))
  const CHART_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#06b6d4', '#22c55e']

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">Fraud Type Breakdown</h3>
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={140} height={140}>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={42} outerRadius={65} paddingAngle={2} dataKey="value">
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5">
          {raw.map((d, i) => (
            <div key={d.type} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                <span className="text-gray-400">{d.type}</span>
              </div>
              <span className="text-gray-300 font-medium">{d.rate}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function FraudTrendChart() {
  const data = useMemo(() => {
    const all = generateChartData(7 * 24)
    return all.filter((_, i) => i % 6 === 0)
  }, [])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-white mb-4">7-Day Fraud Trend</h3>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="fraudTrendGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 9 }} axisLine={false} tickLine={false} interval={6} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Area type="monotone" dataKey="fraud" stroke="#ef4444" strokeWidth={2} fill="url(#fraudTrendGrad)" name="fraud" />
          <Area type="monotone" dataKey="legitimate" stroke="#f59e0b" strokeWidth={1.5} fill="none" strokeDasharray="3 3" name="legitimate" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
